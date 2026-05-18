"""
wikimedia_nature_brazil.py
--------------------------
Busca imagens de natureza do Brasil no Wikimedia Commons com dados de GPS,
retorna URLs de download e gera captions prontos para uso em livros Quarto.

Uso:
    python wikimedia_nature_brazil.py

    Ou como módulo:
        from wikimedia_nature_brazil import buscar_imagens, gerar_caption_quarto

Novidades v3:
    - Paginação automática (cmcontinue) varre toda a categoria
    - GPS do EXIF: converte DMS (graus/min/seg) → decimal
    - Link direto para Google Maps a partir do GPS
    - URL de download limpa (sem ?utm_*)
    - formatar_gps_exif() para usar nas células do livro
"""

import re
import requests
from dataclasses import dataclass, field
from typing import Optional
from fractions import Fraction


# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

API_URL = "https://commons.wikimedia.org/w/api.php"
HEADERS = {"User-Agent": "NatureBrazilBot/1.0 (livro didático; contato@exemplo.com)"}

CATEGORIAS_NATUREZA = [
    # --- Substitutos para Testes Históricos de PDI ---
    "Mandrillus sphinx",           # O "Mandril" (substituto clássico da Lena para texturas/filtros)
    "Cameraman (test image)",      # A famosa imagem de teste do homem com a câmera
    "Standard test images",        # Imagens padrão de calibração e teste técnico
    
    # --- Para Segmentação por Cor e Contornos (Moedas/Objetos) ---
    "coins",             # Moedas brasileiras (excelente substituto para a busca genérica 'coins')
    "Dice",                        # Dados (perfeito para detecção de círculos/Hough e limiarização)
    "bee",         # Categoria de imagens segmentadas (desafiadoras para PDI)
    
    # --- Felinos do Brasil (Corrigindo a busca por Panteras) ---
    "Panthera onca",               # Onça-Pintada (Pantera das Américas)
    "Puma concolor",               # Suçuarana / Puma
    
    # --- Biodiversidade Brasileira (Ótimas para Histogramas e Filtros) ---
    "Fauna of Brazil",             # Categoria macro de fauna
    "Flora of Brazil",             # Categoria macro de flora
    "Birds of Brazil",             # Pássaros (geralmente fotos de alta nitidez com fundo desfocado)
    "Ramphastidae",                # Tucanos (altíssimo contraste de cores para segmentação)
    "Anura of Brazil",             # Sapos e anfíbios (excelentes texturas de pele)
    
    # --- Biomas com alta densidade de fotos geolocalizadas ---
    "Pantanal",                    # Cenários abertos com ótimos gradientes de céu
    "Amazon Rainforest",           # Desafio de PDI: filtragem de alta frequência (folhas)
    "Fernando de Noronha",         # Alto contraste mar/céu/rochas
]


BUSCA = CATEGORIAS_NATUREZA[3]

BUSCAS_TEXTO = [
    "scanned text",
    "historical manuscript",
    "printed page",
    "document scan",
    "newspaper page",
    "OCR test image",
    "book page",
    "typed text",
    "handwritten text",
    "license plate",
    "street signs",
]

BUSCA = BUSCAS_TEXTO[0]

# A API retorna strings como "CC BY-SA 4.0", "CC BY 3.0", "CC0", "Public domain"
LICENCAS_LIVRO_KEYWORDS = {
    "cc by", "cc by-sa", "cc0", "public domain", "cc-by", "cc-zero",
}


# ---------------------------------------------------------------------------
# Estrutura de dados
# ---------------------------------------------------------------------------

@dataclass
class ImagemCommons:
    titulo: str
    url_download: str          # URL limpa, sem ?utm_*
    url_pagina: str
    autor: str
    licenca: str               # valor exato da API, ex: "CC BY-SA 4.0"
    licenca_url: str
    descricao: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    data_captura: Optional[str] = None
    camera_make: Optional[str] = None
    camera_model: Optional[str] = None
    categorias: list = field(default_factory=list)

    @property
    def tem_gps(self) -> bool:
        return self.latitude is not None and self.longitude is not None

    @property
    def google_maps_url(self) -> Optional[str]:
        if not self.tem_gps:
            return None
        return f"https://www.google.com/maps?q={self.latitude:.6f},{self.longitude:.6f}"

    @property
    def licenca_display(self) -> str:
        return self.licenca


# ---------------------------------------------------------------------------
# Utilitários de GPS
# ---------------------------------------------------------------------------

def _dms_para_decimal(dms_raw, hemisferio: str = "") -> Optional[float]:
    """
    Converte coordenada GPS para graus decimais.
    Aceita: float, int, Fraction, string decimal, tupla/lista DMS.
    """
    if dms_raw is None:
        return None

    if isinstance(dms_raw, (int, float)):
        graus_dec = float(dms_raw)
    elif isinstance(dms_raw, Fraction):
        graus_dec = float(dms_raw)
    elif isinstance(dms_raw, str):
        try:
            graus_dec = float(dms_raw.replace(",", "."))
        except ValueError:
            partes = [p.strip() for p in dms_raw.replace(";", ",").split(",")]
            if len(partes) == 3:
                try:
                    g, m, s = [float(p) for p in partes]
                    graus_dec = g + m / 60 + s / 3600
                except ValueError:
                    return None
            else:
                return None
    elif isinstance(dms_raw, (tuple, list)):
        partes = []
        for item in dms_raw:
            if isinstance(item, (tuple, list)) and len(item) == 2:
                partes.append(item[0] / item[1] if item[1] != 0 else 0.0)
            elif isinstance(item, Fraction):
                partes.append(float(item))
            else:
                partes.append(float(item))
        if len(partes) == 3:
            g, m, s = partes
            graus_dec = g + m / 60 + s / 3600
        elif len(partes) == 1:
            graus_dec = partes[0]
        else:
            return None
    else:
        try:
            graus_dec = float(dms_raw)
        except (TypeError, ValueError):
            return None

    if isinstance(hemisferio, str) and hemisferio.upper() in ("S", "W"):
        graus_dec = -abs(graus_dec)

    return graus_dec


def _gps_do_exif_pil(gps_info: dict) -> tuple:
    """
    Extrai (lat, lon) de um dict GPSInfo do PIL._getexif().

    Exemplo de entrada (tag IDs como chave):
        {1: 'S', 2: (24.0, 35.2773, 0.0), 3: 'W', 4: (48.0, 37.7855, 0.0)}
    """
    lat_ref = gps_info.get(1, "N")
    lon_ref = gps_info.get(3, "E")
    lat = _dms_para_decimal(gps_info.get(2), lat_ref)
    lon = _dms_para_decimal(gps_info.get(4), lon_ref)
    return lat, lon


def formatar_gps_exif(gps_info: dict) -> str:
    """
    Formata o dict GPSInfo do PIL de forma legível com link Google Maps.

    Uso nas células do livro:
        exif = img_pil._getexif()
        gps_raw = exif.get(34853)   # tag 34853 = GPSInfo
        if gps_raw:
            print(formatar_gps_exif(gps_raw))
    """
    try:
        from PIL.ExifTags import GPSTAGS
    except ImportError:
        GPSTAGS = {}

    lat, lon = _gps_do_exif_pil(gps_info)
    linhas = ["GPS Info:"]

    for tag_id, valor in gps_info.items():
        nome = GPSTAGS.get(tag_id, f"Tag {tag_id}")
        linhas.append(f"  {nome:25s}: {valor}")

    if lat is not None and lon is not None:
        linhas.append(f"\n  Coordenadas decimais : {lat:.6f}, {lon:.6f}")
        linhas.append(f"  Google Maps          : https://www.google.com/maps?q={lat:.6f},{lon:.6f}")

    return "\n".join(linhas)


# ---------------------------------------------------------------------------
# Funções de busca na API
# ---------------------------------------------------------------------------

def _get(params: dict) -> dict:
    resp = requests.get(API_URL, params=params, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _limpar_url(url: str) -> str:
    return url.split("?")[0] if "?" in url else url


def _limpar_html(texto: str) -> str:
    return re.sub(r"<[^>]+>", "", texto).strip()


def _to_float(valor) -> Optional[float]:
    if valor is None:
        return None
    try:
        return float(str(valor).replace(",", "."))
    except (ValueError, TypeError):
        return None


def _licenca_compativel(licenca: str) -> bool:
    lic = licenca.lower().strip()
    return any(kw in lic for kw in LICENCAS_LIVRO_KEYWORDS)


def buscar_por_categoria(categoria: str, alvo: int = 100) -> list:
    """
    Retorna títulos de arquivos de uma categoria, paginando com cmcontinue
    até atingir `alvo` títulos ou esgotar a categoria.
    """
    ext_validas = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"}
    titulos = []
    continuar = None

    while len(titulos) < alvo:
        params = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": f"Category:{categoria}",
            "cmtype": "file",
            "cmlimit": 50,
            "format": "json",
        }
        if continuar:
            params["cmcontinue"] = continuar

        data = _get(params)
        for m in data.get("query", {}).get("categorymembers", []):
            if any(m["title"].lower().endswith(e) for e in ext_validas):
                titulos.append(m["title"])

        continuar = data.get("continue", {}).get("cmcontinue")
        if not continuar:
            break

    return titulos[:alvo]


def buscar_por_geosearch(lat: float, lon: float, raio_m: int = 10_000, limite: int = 50) -> list:
    """Retorna títulos de arquivos com GPS próximos às coordenadas dadas."""
    params = {
        "action": "query",
        "list": "geosearch",
        "gscoord": f"{lat}|{lon}",
        "gsradius": min(raio_m, 10_000),   # API limita a 10 km
        "gsnamespace": 6,
        "gslimit": min(limite, 50),
        "format": "json",
    }
    data = _get(params)
    return [r["title"] for r in data.get("query", {}).get("geosearch", [])]


def obter_metadados(titulo: str, debug: bool = False) -> Optional[ImagemCommons]:
    """Consulta a API e extrai metadados. Retorna None se licença incompatível."""
    params = {
        "action": "query",
        "titles": titulo,
        "prop": "imageinfo|categories",
        "iiprop": "url|extmetadata|metadata",
        "iiextmetadatafilter": (
            "LicenseShortName|LicenseUrl|Artist|ImageDescription|"
            "DateTimeOriginal|GPSLatitude|GPSLongitude"
        ),
        "format": "json",
    }
    data = _get(params)
    pages = data.get("query", {}).get("pages", {})
    page = next(iter(pages.values()))

    if "imageinfo" not in page:
        return None

    info = page["imageinfo"][0]
    meta = info.get("extmetadata", {})
    exif_raw = info.get("metadata", []) or []
    exif = {item["name"]: item["value"] for item in exif_raw if isinstance(item, dict)}

    licenca = meta.get("LicenseShortName", {}).get("value", "").strip()
    licenca_url = meta.get("LicenseUrl", {}).get("value", "")

    if debug:
        gps_v = meta.get("GPSLatitude", {}).get("value", "—")
        print(f"    [debug] licença='{licenca}' | gps={gps_v} | {titulo.replace('File:','')[:55]}")

    if not licenca or not _licenca_compativel(licenca):
        return None

    autor = _limpar_html(meta.get("Artist", {}).get("value", "Autor desconhecido"))

    # GPS: extmetadata (já decimal) ou fallback para EXIF bruto (DMS)
    lat = _dms_para_decimal(meta.get("GPSLatitude", {}).get("value"))
    lon = _dms_para_decimal(meta.get("GPSLongitude", {}).get("value"))
    if lat is None and "GPSLatitude" in exif:
        lat = _dms_para_decimal(exif["GPSLatitude"], exif.get("GPSLatitudeRef", "N"))
        lon = _dms_para_decimal(exif.get("GPSLongitude"), exif.get("GPSLongitudeRef", "E"))

    cats = [c["title"].replace("Category:", "") for c in page.get("categories", [])]

    return ImagemCommons(
        titulo=titulo.replace("File:", ""),
        url_download=_limpar_url(info["url"]),
        url_pagina=info["descriptionurl"],
        autor=autor,
        licenca=licenca,
        licenca_url=licenca_url,
        descricao=_limpar_html(meta.get("ImageDescription", {}).get("value", "")),
        latitude=lat,
        longitude=lon,
        data_captura=meta.get("DateTimeOriginal", {}).get("value", ""),
        camera_make=exif.get("Make", ""),
        camera_model=exif.get("Model", ""),
        categorias=cats,
    )


# ---------------------------------------------------------------------------
# Geração de captions Quarto
# ---------------------------------------------------------------------------

def gerar_caption_quarto(
    img: ImagemCommons,
    label: str,
    descricao_custom: str = "",
    mostrar_gps: bool = True,
) -> str:
    """
    Gera célula Quarto/Jupyter pronta para colar no livro.

    O fig-cap é limitado a uma linha sem quebras, para evitar SyntaxError no YAML.
    A função formatar_gps_exif é embutida inline para não depender de import externo.
    """
    # Descrição: remove quebras de linha e trunca para não estourar o YAML
    descricao_raw = descricao_custom or img.descricao or img.titulo
    descricao = " ".join(descricao_raw.split())       # colapsa espaços/\n
    descricao = descricao.replace('"', "'")          # evita fechar o fig-cap
    if len(descricao) > 120:
        descricao = descricao[:117] + "..."

    credito = f"Crédito: {img.autor} ({img.licenca_display})."
    partes = [descricao]
    if mostrar_gps and img.tem_gps:
        partes.append(f"GPS: ({img.latitude:.5f}, {img.longitude:.5f}).")
    partes.append(credito)
    caption = " ".join(partes)

    # Função auxiliar embutida como lista de linhas (evita SyntaxError no Quarto)
    gps_helper_linhas = [
        "def _formatar_gps(gps_info):",
        "    from fractions import Fraction",
        "    def dms(raw, hem=''):",
        "        if raw is None: return None",
        "        if isinstance(raw, (int, float, Fraction)): v = float(raw)",
        "        elif isinstance(raw, (tuple, list)):",
        "            p = [x[0]/x[1] if isinstance(x,(tuple,list)) and x[1] else float(x) for x in raw]",
        "            v = p[0]+p[1]/60+p[2]/3600 if len(p)==3 else p[0]",
        "        else:",
        "            try: v = float(raw)",
        "            except: return None",
        "        return -abs(v) if str(hem).upper() in ('S','W') else v",
        "    lat = dms(gps_info.get(2), gps_info.get(1,'N'))",
        "    lon = dms(gps_info.get(4), gps_info.get(3,'E'))",
        "    rows = [f'  LatRef: {gps_info.get(1)}  Lat: {gps_info.get(2)}',",
        "            f'  LonRef: {gps_info.get(3)}  Lon: {gps_info.get(4)}']",
        "    if lat is not None:",
        "        rows += [f'  Decimal    : {lat:.6f}, {lon:.6f}',",
        "                 f'  Google Maps: https://www.google.com/maps?q={lat:.6f},{lon:.6f}']",
        "    return 'GPS Info:\\n' + '\\n'.join(rows)",
    ]
    gps_helper = "\n".join(gps_helper_linhas)

    linhas = [
        f"#| label: {label}",
        f'#| fig-cap: "{caption}"',
        "#| echo: true",
        "",
        "import requests",
        "from PIL import Image",
        "from PIL.ExifTags import TAGS",
        "from io import BytesIO",
        "",
        f'url = "{img.url_download}"',
        f"# Fonte : {img.url_pagina}",
    ]
    if img.tem_gps:
        linhas.append(f"# Mapa  : {img.google_maps_url}")
    linhas += [
        gps_helper,
        "res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})",
        "img_pil = Image.open(BytesIO(res.content))",
        "exif = img_pil._getexif()",
        "",
        "if exif:",
        "    tags = ['Make', 'Model', 'DateTime']",
        "    info = {TAGS.get(k, k): v for k, v in exif.items() if TAGS.get(k, k) in tags}",
        '    print(f"Dados de Aquisição:\\n{info}")',
        "    gps_raw = exif.get(34853)  # tag 34853 = GPSInfo",
        "    if gps_raw:",
        "        print(_formatar_gps(gps_raw))",
        "",
        "img_pil.show()",
    ]
    return "\n".join(linhas)


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def buscar_imagens(
    categoria: str = BUSCA,
    limite: int = 5,
    apenas_com_gps: bool = True,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    raio_m: int = 10_000,
    debug: bool = False,
) -> list:
    """
    Busca imagens de natureza do Brasil no Wikimedia Commons.

    Parâmetros:
        categoria     : categoria do Commons (ignorado se lat/lon fornecidos)
        limite        : número máximo de resultados
        apenas_com_gps: filtra apenas imagens com coordenadas GPS
        lat, lon      : coordenadas para busca geográfica (opcional)
        raio_m        : raio em metros (máx 10 km por limitação da API)
        debug         : imprime licença e GPS de cada candidata
    """
    gps_str = "com GPS " if apenas_com_gps else ""
    print(f"🔍 Buscando imagens {gps_str}...")

    # Varrer ~20x mais candidatas para compensar a baixa taxa de GPS
    alvo_candidatos = max(limite * 20, 100)

    if lat is not None and lon is not None:
        titulos = buscar_por_geosearch(lat, lon, raio_m, 50)
        print(f"   GeoSearch ({lat:.4f}, {lon:.4f}) raio {raio_m/1000:.0f} km "
              f"→ {len(titulos)} candidatos")
    else:
        titulos = buscar_por_categoria(categoria, alvo=alvo_candidatos)
        print(f"   Categoria '{categoria}' → {len(titulos)} candidatos varridos")

    imagens = []
    for titulo in titulos:
        if len(imagens) >= limite:
            break
        img = obter_metadados(titulo, debug=debug)
        if img is None:
            continue
        if apenas_com_gps and not img.tem_gps:
            if debug:
                print(f"    [debug] sem GPS: {titulo[:65]}")
            continue
        imagens.append(img)
        status = "📍 GPS" if img.tem_gps else "   sem GPS"
        print(f"   {status}  {img.titulo[:65]}")

    print(f"\n✅ {len(imagens)} imagem(ns) encontrada(s) com licença compatível.\n")
    return imagens


# ---------------------------------------------------------------------------
# Execução direta
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    # Opção A — por categoria (recomendado para natureza do Brasil)
    imagens = buscar_imagens(
        categoria=BUSCA,
        limite=50,
        apenas_com_gps=False,
        debug=False,
    )

    # Opção B — por coordenadas (Pantanal, MS)
    # imagens = buscar_imagens(lat=-19.0, lon=-57.0, raio_m=10_000, limite=5)

    # Opção C — sem filtro GPS (mais resultados)
    # imagens = buscar_imagens(categoria="Flora of Brazil", limite=10, apenas_com_gps=False)

    # ------------------------------------------------------------------
    print("=" * 72)
    print("RESULTADOS")
    print("=" * 72)

    for i, img in enumerate(imagens, 1):
        print(f"\n[{i}] {img.titulo}")
        print(f"    URL download  : {img.url_download}")
        print(f"    Página Commons: {img.url_pagina}")
        print(f"    Autor         : {img.autor}")
        print(f"    Licença       : {img.licenca_display}")
        if img.tem_gps:
            print(f"    GPS           : {img.latitude:.6f}, {img.longitude:.6f}")
            print(f"    Google Maps   : {img.google_maps_url}")
        if img.data_captura:
            print(f"    Data captura  : {img.data_captura}")
        if img.camera_model:
            print(f"    Câmera        : {img.camera_make} {img.camera_model}")

    # ------------------------------------------------------------------
    print("\n" + "=" * 72)
    print("CAPTIONS QUARTO  (copie para seu livro)")
    print("=" * 72)

    for i, img in enumerate(imagens, 1):
        label = f"fig-{i:02d}-natureza"
        print(f"\n{'─' * 72}")
        print(f"  Célula {i} — {img.titulo[:60]}")
        print(f"{'─' * 72}")
        print(gerar_caption_quarto(img, label=label))
        print()