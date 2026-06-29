#!/usr/bin/env python3
"""
ep_tools.py — Ferramentas unificadas para extração de EPs de HTML Quarto.

Subcomandos:
  extrair   Extrai cada EP de cap*.html e salva em arquivo individual.
  limpar    Extrai o fragmento utilizável (compatível com Moodle/VPL) de cada EPxx_xx.html.

────────────────────────────────────────────────────────────────────────────
EXTRAIR — gera um HTML por EP a partir das páginas de capítulo do Quarto
────────────────────────────────────────────────────────────────────────────
  python ep_tools.py extrair                                  # processa gen/book/*/cap*/*.html
  python ep_tools.py extrair --input gen/book/py.pt           # versão específica
  python ep_tools.py extrair --input gen/book/py.pt/cap01/cap01.py.pt.html  # arquivo único
  python ep_tools.py extrair --out-dir output/eps             # pasta de saída customizada
  python ep_tools.py extrair --dry-run                        # só lista EPs encontrados

  Saída padrão: gen/book/eps/<versao>/EP01_02.html

────────────────────────────────────────────────────────────────────────────
LIMPAR — extrai o fragmento Moodle/VPL de cada EPxx_xx.html já extraído
────────────────────────────────────────────────────────────────────────────
  python ep_tools.py limpar <pasta_entrada> <pasta_saida>
  python ep_tools.py limpar gen/book/eps/py.pt gen/book/eps/py.pt_moodle

  Remove células Jupyter (%%writefile, TestSuite…run()) e descarta tudo fora
  do <div class="ep-container">. Pronto para colar no Moodle.
"""

import argparse
import re
import sys
from pathlib import Path
from bs4 import BeautifulSoup, Tag


# ══════════════════════════════════════════════════════════════════════════════
# PARTE 1 — EXTRAIR: extrai EPs de cap*.html  (extrair_eps.py)
# ══════════════════════════════════════════════════════════════════════════════

# Identifica o título de um EP: h2, h3 ou h4 cujo texto contém "EPXX_YY"
RE_EP_HEADING = re.compile(r'\bEP(\d{2})_(\d{2})\b')

# Identifica a célula %%writefile EPXX_YY.py que fecha o bloco do EP
RE_WRITEFILE = re.compile(r'%%writefile\s+(EP\d{2}_\d{2}\.py)')


HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="{lang}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{ep_id} — {title}</title>
  {styles}
</head>
<body class="ep-standalone">
<div class="ep-container" style="margin:0 auto; max-width:80ch">
{content}
</div>
{scripts}
</body>
</html>
"""


def extract_head_assets(soup: BeautifulSoup) -> tuple[str, str]:
    """
    Extrai <link rel="stylesheet"> e <script> do <head> do documento original
    para que o HTML gerado tenha o mesmo visual do livro.
    Retorna (styles_html, scripts_html).
    """
    styles_parts: list[str] = []
    scripts_parts: list[str] = []

    head = soup.find("head")
    if not head:
        return "", ""

    for tag in head.find_all(["link", "style"]):
        if tag.name == "link" and tag.get("rel") == ["stylesheet"]:
            styles_parts.append(str(tag))
        elif tag.name == "style":
            styles_parts.append(str(tag))

    # Scripts do head (ex: MathJax)
    for tag in head.find_all("script"):
        src = tag.get("src", "")
        if src and any(k in src for k in ("mathjax", "highlight", "quarto")):
            scripts_parts.append(str(tag))
        elif not src and tag.string and "MathJax" in tag.string:
            scripts_parts.append(str(tag))

    # Scripts do body (copy-to-clipboard, etc.)
    body = soup.find("body")
    if body:
        for tag in body.find_all("script"):
            src = tag.get("src", "")
            if src or (tag.string and len(tag.string.strip()) > 0):
                scripts_parts.append(str(tag))

    return "\n  ".join(styles_parts), "\n".join(scripts_parts)


def detect_lang(soup: BeautifulSoup) -> str:
    html_tag = soup.find("html")
    return html_tag.get("lang", "pt") if html_tag else "pt"


def find_ep_blocks(soup: BeautifulSoup) -> list[dict]:
    """
    Percorre o DOM e localiza cada bloco EP.

    Estratégia:
    1. Encontra todos os headings (h2/h3/h4) cujo texto casa com RE_EP_HEADING.
    2. Para cada heading, coleta todos os elementos irmãos seguintes até:
       a) encontrar a célula %%writefile EPXX_YY.py  → inclui e para
       b) encontrar outro heading EP                 → para (não inclui)
       c) encontrar heading de nível igual/superior  → para
    """
    heading_tags = {"h2", "h3", "h4"}
    eps: list[dict] = []

    main = (
        soup.find("main")
        or soup.find("article")
        or soup.find("div", class_=re.compile(r"content|chapter|book"))
        or soup.find("body")
    )
    if not main:
        return []

    ep_headings: list[tuple] = []
    for tag in main.find_all(heading_tags):
        text = tag.get_text(" ", strip=True)
        m = RE_EP_HEADING.search(text)
        if m:
            ep_headings.append((tag, m.group(0)))  # (tag, "EP01_02")

    for heading_tag, ep_id in ep_headings:
        title_text = heading_tag.get_text(" ", strip=True)
        title_text = re.sub(r'^\s*[\d.]+\s+', '', title_text)

        heading_level = int(heading_tag.name[1])  # h3 → 3

        block_elements: list[Tag] = [heading_tag]
        found_writefile = False

        sibling = heading_tag.find_next_sibling()
        while sibling:
            if isinstance(sibling, Tag):
                tag_name = sibling.name

                if tag_name in heading_tags:
                    sib_level = int(tag_name[1])
                    if sib_level <= heading_level:
                        break
                    sib_text = sibling.get_text(" ", strip=True)
                    if RE_EP_HEADING.search(sib_text):
                        break

                sib_text_full = sibling.get_text()
                wf_match = RE_WRITEFILE.search(sib_text_full)
                if wf_match and wf_match.group(1).startswith(ep_id):
                    block_elements.append(sibling)
                    found_writefile = True
                    break

                block_elements.append(sibling)

            sibling = sibling.find_next_sibling()

        eps.append({
            "ep_id": ep_id,
            "title": title_text,
            "elements": block_elements,
            "has_writefile": found_writefile,
        })

    return eps


def elements_to_html(elements: list[Tag]) -> str:
    return "\n".join(str(el) for el in elements)


def build_ep_html(ep: dict, styles: str, scripts: str, lang: str) -> str:
    content = elements_to_html(ep["elements"])
    return HTML_TEMPLATE.format(
        lang=lang,
        ep_id=ep["ep_id"],
        title=ep["title"],
        styles=styles,
        scripts=scripts,
        content=content,
    )


def process_html_file(
    html_path: Path,
    out_dir: Path,
    dry_run: bool = False,
    verbose: bool = True,
) -> list[str]:
    raw = html_path.read_text(encoding="utf-8")
    soup = BeautifulSoup(raw, "html.parser")

    lang = detect_lang(soup)
    styles, scripts = extract_head_assets(soup)
    eps = find_ep_blocks(soup)

    if not eps:
        if verbose:
            print(f"  ⚠️  Nenhum EP encontrado em {html_path.name}")
        return []

    extracted: list[str] = []
    for ep in eps:
        ep_id = ep["ep_id"]
        out_file = out_dir / f"{ep_id}.html"

        if dry_run:
            wf = "✓ writefile" if ep["has_writefile"] else "✗ sem writefile"
            print(f"  [{wf}] {ep_id}  →  {out_file}")
        else:
            out_file.parent.mkdir(parents=True, exist_ok=True)
            html_content = build_ep_html(ep, styles, scripts, lang)
            out_file.write_text(html_content, encoding="utf-8")
            size_kb = out_file.stat().st_size / 1024
            if verbose:
                wf = "✓" if ep["has_writefile"] else "⚠"
                print(f"  {wf} {ep_id}  →  {out_file}  ({size_kb:.0f} KB)")

        extracted.append(ep_id)

    return extracted


def collect_html_files(input_path: Path) -> list[tuple[Path, Path]]:
    pairs: list[tuple[Path, Path]] = []

    if input_path.is_file() and input_path.suffix == ".html":
        parts = input_path.parts
        try:
            book_idx = list(parts).index("book")
            versao_dir = Path(*parts[: book_idx + 2])
        except ValueError:
            versao_dir = input_path.parent
        pairs.append((input_path, versao_dir))

    elif input_path.is_dir():
        for html_file in sorted(input_path.rglob("cap*/*.html")):
            parts = html_file.parts
            try:
                book_idx = list(parts).index("book")
                versao_dir = Path(*parts[: book_idx + 2])
            except ValueError:
                versao_dir = input_path
            pairs.append((html_file, versao_dir))

    return pairs


def cmd_extrair(args: argparse.Namespace) -> None:
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ Caminho não encontrado: {input_path}", file=sys.stderr)
        sys.exit(1)

    pairs = collect_html_files(input_path)
    if not pairs:
        print(f"❌ Nenhum arquivo HTML de capítulo encontrado em: {input_path}", file=sys.stderr)
        sys.exit(1)

    verbose = not args.quiet
    total_eps: list[str] = []

    for html_file, versao_dir in pairs:
        if args.out_dir:
            out_dir = Path(args.out_dir)
        else:
            versao_name = versao_dir.name
            book_root = versao_dir.parent
            out_dir = book_root / "eps" / versao_name

        if verbose or args.dry_run:
            print(f"\n📄 {html_file}")

        extracted = process_html_file(
            html_path=html_file,
            out_dir=out_dir,
            dry_run=args.dry_run,
            verbose=verbose,
        )
        total_eps.extend(extracted)

    action = "encontrados" if args.dry_run else "gerados"
    print(f"\n{'─'*50}")
    print(f"✅ {len(total_eps)} EPs {action}: {', '.join(sorted(set(total_eps)))}")

    if not args.dry_run and total_eps and not args.out_dir:
        sample_versao = pairs[0][1].name
        book_root = pairs[0][1].parent
        print(f"📁 Saída: {book_root / 'eps' / sample_versao}/")


# ══════════════════════════════════════════════════════════════════════════════
# PARTE 2 — LIMPAR: extrai e sanitiza fragmento Moodle de EPxx_xx.html
# ══════════════════════════════════════════════════════════════════════════════
#
# Pipeline aplicada a cada arquivo:
#   1. Extrai <div class="ep-container"> ... </div>
#   2. Remove células Quarto/Jupyter (%%writefile, TestSuite, outputs)
#   3. Converte LaTeX inline/display para HTML semântico (sem MathJax)
#   4. Reescreve estrutura Quarto (h.anchored, section.level*, span.header-section-number,
#      quarto-float, figcaption, quarto-xref, data-* attrs) para HTML inline puro
#   5. Reescreve scripts de simulador: padrão init(root)+querySelector+dataset
#      → padrão getElementById direto (gabarito EP03_01, compatível com Moodle/TinyMCE)
#   6. Remove accent-color de inputs (causa erro #rrggbb no TinyMCE)
#
# ─────────────────────────────────────────────────────────────────────────────

# Remove células Quarto com id hexadecimal (%%writefile, TestSuite, outputs)
CELL_RE = re.compile(
    r'<div[^>]+class="cell"[^>]*id="[0-9a-f]{6,}"[\s\S]*?'
    r'(?=<div[^>]+class="cell"|</section>|</div>\s*</section>)',
    re.IGNORECASE,
)

# Remove quarto-float wrapper + figcaption, preservando o conteúdo interno
QUARTO_FLOAT_OUTER_RE = re.compile(
    r'<div[^>]+class="[^"]*cell-output[^"]*"[^>]*>\s*'
    r'<figure[^>]*>([\s\S]*?)</figure>\s*</div>',
    re.IGNORECASE,
)

# Converte <figcaption ...>...</figcaption> → remove
FIGCAPTION_RE = re.compile(r'<figcaption[^>]*>[\s\S]*?</figcaption>', re.IGNORECASE)

# Remove o div aria-describedby que envolve o simulador dentro do figure
ARIA_DIV_RE = re.compile(
    r'<div\s+aria-describedby="[^"]*">([\s\S]*?)</div>',
    re.IGNORECASE,
)


# ── Conversão LaTeX → HTML ────────────────────────────────────────────────────

def _cases_to_inline(m: re.Match) -> str:
    r"""\\begin{cases}...\\end{cases} → versão inline com ponto-e-vírgula."""
    body = m.group(1)
    # No HTML do Quarto, \\\\ (quebra de linha LaTeX) aparece como \\ (2 chars reais)
    cases = re.split(r'\\\\', body)
    parts = []
    for case in cases:
        case = re.sub(r'&amp;\s*', '', case)   # remove & de alinhamento (entidade HTML)
        case = re.sub(r'&\s*', '', case)        # remove & literal
        case = case.strip()
        if case:
            parts.append(case)
    return '; '.join(parts)


def latex_body_to_html(body: str) -> str:
    """Converte o corpo de uma expressão LaTeX (sem delimitadores) em HTML."""
    s = body.strip()

    # Decodificar entidades HTML que o Quarto injeta no LaTeX (&amp; → &, &lt; → <)
    s = s.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&nbsp;', ' ')

    # \begin{cases}...\end{cases} → inline
    s = re.sub(r'\\begin\{cases\}([\s\S]*?)\\end\{cases\}', _cases_to_inline, s)

    # Comandos LaTeX → entidades HTML / texto
    cmd_map = [
        (r'\\times',  '&times;'),
        (r'\\geq',    '&ge;'),
        (r'\\leq',    '&le;'),
        (r'\\neq',    '&ne;'),
        (r'\\cdot',   '&middot;'),
        (r'\\ldots',  '&hellip;'),
        (r'\\in',     '&isin;'),
        (r'\\alpha',  '&alpha;'),
        (r'\\beta',   '&beta;'),
        (r'\\gamma',  '&gamma;'),
        (r'\\sigma',  '&sigma;'),
        (r'\\mu',     '&mu;'),
        (r'\\pm',     '&plusmn;'),
        (r'\\infty',  '&infin;'),
        (r'\\sum',    '&sum;'),
        (r'\\sqrt\{([^}]*)\}', r'&radic;(\1)'),
        (r'\\frac\{([^}]*)\}\{([^}]*)\}', r'(\1)/(\2)'),
        (r'\\text\{([^}]*)\}', r'\1'),
        (r'\\mathbf\{([^}]*)\}', r'<strong>\1</strong>'),
        (r'\\mathrm\{([^}]*)\}', r'\1'),
        (r'\\_', '_'),
        (r'\\{', '{'),
        (r'\\}', '}'),
    ]
    for pat, repl in cmd_map:
        s = re.sub(pat, repl, s)

    # Variáveis de uma letra (p, T, L, C, k, n, f, g, …) → <em>
    s = re.sub(r'(?<![a-zA-Z&;{])([a-zA-Z])(?![a-zA-Z;={])', r'<em>\1</em>', s)

    # Remover chaves remanescentes e espaços redundantes
    s = s.replace('{', '').replace('}', '')
    s = re.sub(r'  +', ' ', s).strip()
    return s


def convert_math_spans(html: str) -> str:
    """Substitui <span class="math inline/display">\\(...\\)</span> por HTML limpo."""
    def repl_inline(m: re.Match) -> str:
        inner = re.sub(r'^\\\(|\\\)$', '', m.group(1)).strip()
        return latex_body_to_html(inner)

    def repl_display(m: re.Match) -> str:
        # IMPORTANTE: NÃO preservar LaTeX com \\ na versão Moodle.
        # O TinyMCE descarta barras invertidas ao salvar, corrompendo o JavaScript.
        # Converter para HTML puro (feio mas seguro). Link para versão completa
        # com MathJax é injetado como banner por inject_moodle_styles.
        inner = m.group(1)
        # Strip dos delimitadores \[ \] que o Quarto inclui no conteúdo
        inner = re.sub(r'^\s*\\\[\s*', '', inner)
        inner = re.sub(r'\s*\\\]\s*$', '', inner).strip()
        return latex_body_to_html(inner)

    html = re.sub(r'<span class="math inline">([\s\S]*?)</span>', repl_inline, html)
    html = re.sub(r'<span class="math display">([\s\S]*?)</span>', repl_display, html)
    return html


# ── Injeção de estilos inline (gabarito EP03_01) ─────────────────────────────
#
# Mapeamento emoji → caixa colorida (padrão EP03_01):
#   🧠  fundamentação teórica  → caixa verde
#   📋  diretrizes / cenário   → caixa cinza
#   📌  requisitos / exemplos  → caixa amarela
#   📦  especificação I/O      → caixa cinza
#
_EMOJI_BOX: dict[str, dict[str, str]] = {
    '🧠': {
        'div': 'background-color:#f0fff4;border-left:5px solid #2ecc71;padding:15px;margin-bottom:20px;',
        'h':   'margin-top:0;color:#1e7e34;',
    },
    '📋': {
        'div': 'background-color:#f8f9fa;padding:15px;border:1px solid #ccc;border-radius:5px;margin-bottom:20px;',
        'h':   'margin-top:0;color:#333;',
    },
    '📌': {
        'div': 'background-color:#fffde7;border-left:5px solid #fbc02d;padding:15px;margin-bottom:25px;',
        'h':   'margin-top:0;color:#856404;',
    },
    '📦': {
        'div': 'background-color:#f8f9fa;padding:15px;border:1px solid #ccc;border-radius:5px;margin-bottom:20px;',
        'h':   'margin-top:0;color:#333;',
    },
}

_TABLE_STYLE    = 'width:100%;border-collapse:collapse;background-color:#fff;text-align:left;margin-bottom:20px;'
_TH_STYLE       = 'padding:10px;border:1px solid #ddd;'
_TD_CODE_STYLE  = 'padding:10px;border:1px solid #ddd;font-family:monospace;vertical-align:top;'
_TD_TEXT_STYLE  = 'padding:10px;border:1px solid #ddd;vertical-align:top;'
_OUTER_STYLE    = ('font-family:sans-serif;line-height:1.6;color:#333;max-width:1200px;'
                   'margin:auto;border:1px solid #ddd;padding:20px;border-radius:8px;background:white;')
_H2_STYLE       = 'color:#0056b3;border-bottom:2px solid #0056b3;padding-bottom:10px;'


def _style_table(table: Tag, is_examples: bool = False) -> None:
    """Aplica estilos inline à tabela e suas células (padrão EP03_01)."""
    table['style'] = _TABLE_STYLE
    for tr in table.find_all('tr'):
        # Remove classes Quarto (header, odd, even)
        tr.attrs.pop('class', None)
        if tr.parent and tr.parent.name == 'thead':
            tr['style'] = 'background-color:#f1f1f1;'
            for th in tr.find_all('th'):
                th['style'] = _TH_STYLE
        else:
            tds = tr.find_all('td')
            for i, td in enumerate(tds):
                # Última coluna de exemplos = observação (sem monospace)
                if is_examples and i == len(tds) - 1:
                    td['style'] = _TD_TEXT_STYLE
                else:
                    td['style'] = _TD_CODE_STYLE


def _strip_section_number(text: str) -> str:
    """Remove '4.9.1.1 ' do início de um texto de heading."""
    return re.sub(r'^\s*[\d.]+\s+', '', text)


def inject_moodle_styles(fragment_html: str) -> str:
    """
    Recebe o fragmento ep-container (já com LaTeX convertido e quarto-float
    desenrolado) e:
      1. Converte o h3/h4 de título em <h2> com estilo azul
      2. Detecta o emoji de cada seção filha e injeta o style= da caixa colorida
      3. Converte headings das seções para <h4> com estilo inline
      4. Estiliza tabelas (thead cinza, th/td com bordas)
      5. Envolve tudo no wrapper externo do EP03_01
    """
    soup = BeautifulSoup(fragment_html, 'html.parser')
    container = soup.find('div', class_='ep-container')
    if not container:
        return fragment_html  # fallback: retorna intacto

    # ── 1. Título principal ───────────────────────────────────────────────────
    title_tag = container.find(['h2', 'h3', 'h4'])
    if title_tag:
        for span in title_tag.find_all('span', class_='header-section-number'):
            span.decompose()
        ep_title = _strip_section_number(title_tag.get_text(' ', strip=True))
        new_h2 = soup.new_tag('h2')
        new_h2['style'] = _H2_STYLE
        new_h2.string = ep_title
        title_tag.replace_with(new_h2)

    # ── 2. Seções filhas (section.level* ou div sem estilo) ───────────────────
    for child in list(container.children):
        if not isinstance(child, Tag):
            continue
        if child.name in ('h2', 'p'):
            continue  # título e parágrafo de introdução — não tocar

        # Encontrar o heading da seção
        heading = child.find(['h2', 'h3', 'h4'])
        if not heading:
            # Sem heading — só limpar attrs Quarto e converter section→div
            child.name = 'div'
            for attr in ['class', 'data-number', 'id']:
                child.attrs.pop(attr, None)
            continue

        # Limpar header-section-number
        for span in heading.find_all('span', class_='header-section-number'):
            span.decompose()
        h_text = _strip_section_number(heading.get_text(' ', strip=True))

        # Detectar emoji
        emoji = next((e for e in _EMOJI_BOX if e in h_text), None)

        # Converter section → div, limpar attrs Quarto
        child.name = 'div'
        for attr in ['class', 'data-number', 'id']:
            child.attrs.pop(attr, None)

        if emoji:
            box = _EMOJI_BOX[emoji]
            child['style'] = box['div']

            # Heading da seção → h4 com estilo inline
            heading.name = 'h4'
            heading['style'] = box['h']
            for attr in ['class', 'data-anchor-id', 'data-number']:
                heading.attrs.pop(attr, None)
            heading.string = h_text

            # Estilizar tabelas dentro da seção
            is_ex = bool(re.search(r'exemplo|example', h_text, re.IGNORECASE))
            for table in child.find_all('table'):
                # Remover classes Quarto da tabela
                table.attrs.pop('class', None)
                for colgroup in table.find_all('colgroup'):
                    colgroup.decompose()
                _style_table(table, is_examples=is_ex)
        else:
            # Emoji não reconhecido — só limpar heading
            heading.name = 'h4'
            for attr in ['class', 'data-anchor-id', 'data-number']:
                heading.attrs.pop(attr, None)

    # ── 3. Links quarto-xref → texto puro ────────────────────────────────────
    for a in container.find_all('a', class_='quarto-xref'):
        a.replace_with(a.get_text())

    # ── 4. Wrapper externo ────────────────────────────────────────────────────
    container['style'] = _OUTER_STYLE
    del container['class']

    return str(soup)


# ── Reescrita de scripts de simulador ────────────────────────────────────────

def rewrite_sim_script(script: str) -> str:
    """
    Reescreve o padrão Quarto:
        (function(){ function init(root){...} function tryInit(){querySelectorAll([id=...])...} setInterval... })()
    para o padrão EP03_01 (compatível com Moodle/TinyMCE):
        (function initXxx(){ var container = getElementById(...); if(!container){setTimeout...} ... })()

    Transforma:
      - root.querySelector('#id') → document.getElementById('id')
      - root.dataset.xyzReady     → removido (guarda de dupla execução)
      - tryInit() + setInterval   → removido (substituído por setTimeout fallback)
    """
    # Detectar id do container do simulador
    sim_id_m = re.search(r'\[id=["\']([^"\']+)["\']\]', script)
    if not sim_id_m:
        return script  # padrão não reconhecido — retorna intacto
    sim_id = sim_id_m.group(1)

    # Detectar nome da variável "root"
    root_m = re.search(r'function init\((\w+)\)', script)
    if not root_m:
        return script
    root_var = root_m.group(1)

    # Extrair o corpo de init(root) — tudo entre o primeiro { e seu } balanceado
    init_start = script.find(f'function init({root_var}){{')
    if init_start == -1:
        init_start = script.find(f'function init({root_var}) {{')
    if init_start == -1:
        return script

    # Avançar até o { de abertura
    brace_open = script.find('{', init_start)
    depth, pos = 0, brace_open
    while pos < len(script):
        if script[pos] == '{':
            depth += 1
        elif script[pos] == '}':
            depth -= 1
            if depth == 0:
                init_body = script[brace_open + 1: pos]
                break
        pos += 1
    else:
        return script

    # Limpar linhas de guarda (dataset e !root)
    init_body = re.sub(rf'\s*if\s*\(!{root_var}\)\s*return;\s*\n?', '\n', init_body)
    init_body = re.sub(
        rf'\s*if\s*\({root_var}\.dataset\.\w+\s*===\s*[\'"][^\'"]*[\'"]\)\s*return;\s*\n?',
        '\n', init_body,
    )
    init_body = re.sub(rf'\s*{root_var}\.dataset\.\w+\s*=\s*[\'"][^\'"]*[\'"];\s*\n?', '\n', init_body)
    # Remover guarda if(!slT || ...) return
    init_body = re.sub(r'\s*if\s*\(![^)]{5,}\)\s*return;\s*\n?', '\n', init_body)

    # Substituir root.querySelector('#id') → document.getElementById('id')
    init_body = re.sub(
        rf"{root_var}\.querySelector\(['\"]#([^'\"]+)['\"]\)",
        r"document.getElementById('\1')",
        init_body,
    )

    # Nome da IIFE a partir do sim_id (ex: sim-ep0401b → initSimEp0401b)
    iife_name = 'init' + re.sub(r'[^a-zA-Z0-9]', '_', sim_id).title().replace('_', '')

    new_script = (
        f'(function {iife_name}() {{\n'
        f'  var container = document.getElementById(\'{sim_id}\');\n'
        f'  if (!container) {{ setTimeout({iife_name}, 100); return; }}\n'
        f'{init_body}\n'
        f'}})();'
    )
    return new_script


def sanitize_scripts(html: str) -> str:
    """Aplica rewrite_sim_script a cada bloco <script>...</script> do fragmento."""
    def repl(m: re.Match) -> str:
        content = m.group(1)
        # Só reescrever scripts que têm o padrão Quarto (tryInit + querySelectorAll)
        if 'querySelectorAll' in content and 'tryInit' in content:
            content = rewrite_sim_script(content)
        return f'<script>\n{content}\n</script>'

    return re.sub(r'<script>([\s\S]*?)</script>', repl, html, flags=re.IGNORECASE)


# ── Localização do ep-container ───────────────────────────────────────────────

def find_container_span(html: str) -> tuple[int, int] | None:
    """Localiza o span [start, end) do <div class="ep-container"> mais externo."""
    start_match = re.search(r'<div class="ep-container">', html)
    if not start_match:
        return None

    depth = 0
    pos = start_match.start()
    tag_re = re.compile(r'<div\b[^>]*>|</div>', re.IGNORECASE)

    while True:
        m = tag_re.search(html, pos)
        if not m:
            return None
        token = m.group(0)
        depth += -1 if token.lower().startswith('</div') else 1
        pos = m.end()
        if depth == 0:
            return start_match.start(), pos

    return None


# ── Pipeline completa ─────────────────────────────────────────────────────────

def _unwrap_quarto_float(html: str) -> str:
    """Desenrola <div class="cell-output..."><figure>CONTEÚDO</figure></div> → CONTEÚDO."""
    def unwrap(m: re.Match) -> str:
        inner = FIGCAPTION_RE.sub('', m.group(1))
        inner = re.sub(r'<div\s+aria-describedby="[^"]*">([\s\S]*?)</div>', r'\1', inner)
        return inner.strip()
    return QUARTO_FLOAT_OUTER_RE.sub(unwrap, html)


def _fix_sim_header(html: str) -> str:
    """
    Corrige a estrutura do cabeçalho do simulador gerado pelo Quarto.

    Padrão errado (div de conteúdo aninhado dentro do div do título):
      <div style="...flex...">          ← barra de título
        🎮 Simulador: ...
        <span>...</span>
        <div style="padding:20px;...">  ← conteúdo fica DENTRO do título
          ...
        </div>
      </div>

    Padrão correto (EP03_01 — conteúdo é irmão do título):
      <div style="...flex...">          ← barra de título
        🎮 Simulador: ...
        <span>...</span>
      </div>
      <div style="padding:20px;...">    ← conteúdo como irmão
        ...
      </div>
    """
    soup = BeautifulSoup(html, 'html.parser')

    for sim in soup.find_all('div', id=re.compile(r'^sim-')):
        # Localizar o div de título (flex + fundo bege/cinza do simulador)
        title_div = sim.find(
            'div',
            style=re.compile(r'display\s*:\s*flex.*justify-content\s*:\s*space-between', re.S),
        )
        if not title_div:
            continue

        # Verificar se tem um div de conteúdo aninhado dentro do title_div
        content_div = title_div.find(
            'div',
            style=re.compile(r'padding\s*:\s*20px'),
            recursive=False,
        )
        if not content_div:
            continue

        # Extrair o content_div do interior do title_div e inserir após ele
        content_div.extract()
        title_div.insert_after(content_div)

    return str(soup)


    """Desenrola <div class="cell-output..."><figure>CONTEÚDO</figure></div> → CONTEÚDO."""
    def unwrap(m: re.Match) -> str:
        inner = FIGCAPTION_RE.sub('', m.group(1))
        inner = re.sub(r'<div\s+aria-describedby="[^"]*">([\s\S]*?)</div>', r'\1', inner)
        return inner.strip()
    return QUARTO_FLOAT_OUTER_RE.sub(unwrap, html)


def moodle_sanitize(fragment: str) -> str:
    """
    Pipeline completa de conversão Quarto → HTML Moodle (padrão EP03_01):
      1. Remove células Quarto com id hexadecimal (%%writefile, TestSuite, outputs)
      2. Desenrola quarto-float / figcaption wrappers
      3. Converte LaTeX inline/display → HTML semântico
      4. Remove accent-color de inputs (causa erro #rrggbb no TinyMCE)
      5. Injeta estilos inline: wrapper azul, caixas coloridas, tabelas estilizadas
      6. Reescreve scripts: init(root)+querySelector+dataset → getElementById (padrão EP03_01)
    """
    fragment = CELL_RE.sub('', fragment)            # 1. remove células hex
    fragment = _unwrap_quarto_float(fragment)        # 2. desenrola figure wrappers
    fragment = convert_math_spans(fragment)          # 3. LaTeX → HTML
    fragment = re.sub(                              # 4. accent-color
        r'\s*accent-color\s*:\s*[^;"\s]+\s*;?', '', fragment)
    fragment = inject_moodle_styles(fragment)        # 5. estilos inline EP03_01
    fragment = _fix_sim_header(fragment)             # 6. título do simulador no topo
    fragment = sanitize_scripts(fragment)            # 7. reescreve scripts
    return fragment


def _make_link_banner(ep_name: str, base_url: str) -> str:
    """Banner HTML com link para a versão completa do EP (fórmulas MathJax perfeitas)."""
    url = base_url.rstrip('/') + '/' + ep_name + '.html'
    lines = [
        '<div style="font-family:sans-serif;background:#e8f4fd;border-left:4px solid #2980b9;'
        'padding:10px 15px;margin-bottom:16px;border-radius:4px;font-size:13px;color:#1a5276;">',
        '📐 <strong>Versão com fórmulas matemáticas:</strong> '
        '<a href="' + url + '" target="_blank" style="color:#2980b9;">' + url + '</a>',
        '<br><span style="font-size:11px;color:#555;">'
        '(Fórmulas renderizadas pelo MathJax — abrir em nova aba)</span>',
        '</div>',
    ]
    return '\n'.join(lines)


def process_ep_file(path: Path, outdir: Path, base_url: str = '') -> bool:
    html = path.read_text(encoding='utf-8', errors='replace')
    span = find_container_span(html)
    if not span:
        print(f"[AVISO] '{path.name}': <div class=\"ep-container\"> não encontrado — pulando.")
        return False

    start, end = span
    fragment = moodle_sanitize(html[start:end])

    # Injetar banner com link para versão completa (MathJax) logo após o div raiz
    if base_url:
        ep_name = path.stem  # ex: EP04_01
        banner = _make_link_banner(ep_name, base_url)
        insert_at = fragment.find('>') + 1
        fragment = fragment[:insert_at] + '\n' + banner + fragment[insert_at:]

    # Relatório rápido de problemas remanescentes
    warnings = []
    if 'accent-color' in fragment:
        warnings.append('accent-color')
    if 'querySelector' in fragment:
        warnings.append('querySelector')
    if 'dataset.' in fragment:
        warnings.append('dataset.')
    if 'class="anchored"' in fragment:
        warnings.append('class=anchored')
    if 'class="math' in fragment:
        warnings.append('class=math')

    outpath = outdir / path.name
    outpath.write_text(fragment, encoding='utf-8')

    warn_str = '  ⚠ ' + ', '.join(warnings) if warnings else ''
    print(f"[OK] {path.name}: {len(html)} → {len(fragment)} bytes{warn_str}")
    return True


def cmd_limpar(args: argparse.Namespace) -> None:
    indir = Path(args.entrada)
    outdir = Path(args.saida)

    if not indir.is_dir():
        print(f"❌ Pasta de entrada não encontrada: {indir}", file=sys.stderr)
        sys.exit(1)

    outdir.mkdir(parents=True, exist_ok=True)
    base_url = getattr(args, 'base_url', '') or ''
    print(f"Entrada  : {indir}")
    print(f"Saída    : {outdir}")
    if base_url:
        print(f"Base URL : {base_url}")
    print()

    ok, fail = 0, 0
    for f in sorted(indir.glob("EP*.html")):
        if process_ep_file(f, outdir, base_url=base_url):
            ok += 1
        else:
            fail += 1

    print(f"\n{'─'*50}")
    print(f"✅ Concluído: {ok} sanitizados, {fail} com problema.")
    if ok:
        print(f"📁 Fragmentos prontos para Moodle em: {outdir}/")


# ══════════════════════════════════════════════════════════════════════════════
# CLI principal
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="ep_tools.py",
        description="Ferramentas unificadas para extração de EPs de HTML Quarto.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="cmd", metavar="SUBCOMANDO")
    sub.required = True

    # ── subcomando: extrair ──────────────────────────────────────────────────
    p_ext = sub.add_parser(
        "extrair",
        help="Extrai cada EP de cap*.html e salva em arquivo individual.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_ext.add_argument(
        "--input", "-i",
        default="gen/book",
        metavar="CAMINHO",
        help="Arquivo HTML ou diretório raiz (padrão: gen/book)",
    )
    p_ext.add_argument(
        "--out-dir", "-o",
        default=None,
        metavar="PASTA",
        help="Pasta de saída (padrão: gen/book/eps/<versao>/)",
    )
    p_ext.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Apenas lista EPs encontrados, não grava arquivos",
    )
    p_ext.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suprime saída detalhada",
    )
    p_ext.set_defaults(func=cmd_extrair)

    # ── subcomando: limpar ───────────────────────────────────────────────────
    p_lim = sub.add_parser(
        "limpar",
        help="Extrai fragmento Moodle/VPL de cada EPxx_xx.html já extraído.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_lim.add_argument(
        "entrada",
        metavar="PASTA_ENTRADA",
        help="Pasta com os EPxx_xx.html extraídos (ex: gen/book/eps/py.pt)",
    )
    p_lim.add_argument(
        "saida",
        metavar="PASTA_SAIDA",
        nargs="?",
        default=None,
        help="Pasta de saída (padrão: <PASTA_ENTRADA>_moodle)",
    )
    p_lim.add_argument(
        "--base-url", "-u",
        default="",
        metavar="URL",
        dest="base_url",
        help=(
            "URL base da versão completa dos EPs (com MathJax). "
            "Ex: https://fzampirolli.github.io/pdi-vc/eps/py.pt "
            "Quando fornecida, injeta um banner com link no topo de cada EP."
        ),
    )
    p_lim.set_defaults(func=cmd_limpar)

    args = parser.parse_args()

    # Valor padrão de saída para 'limpar'
    if args.cmd == "limpar" and args.saida is None:
        args.saida = str(Path(args.entrada).with_name(Path(args.entrada).name + "_moodle"))

    args.func(args)


if __name__ == "__main__":
    main()
