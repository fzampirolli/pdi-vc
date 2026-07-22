import os
import urllib.request
from morph import mm

np = mm._get_np()
cv2 = mm._get_cv2()


def garantir_e_baixar(nome):
    pasta = "dados/EP06"
    caminho = os.path.join(pasta, nome)
    os.makedirs(pasta, exist_ok=True)
    if not os.path.exists(caminho):
        url = (
            "https://raw.githubusercontent.com/"
            "fzampirolli/pdi-vc/master/all/cap08/dados/EP06/"
            + nome
        )
        try:
            urllib.request.urlretrieve(url, caminho)
        except Exception:
            return None
    return caminho


img_arq = garantir_e_baixar("00000.jpg")
txt_arq = garantir_e_baixar("00000.txt")

# Mapeamento de rótulos/siglas (Classes YOLO de 0 a 8)
obj2 = ["Tria", "Quad", "Pent", "Hexa", "Hept", "Circ", "Elip", "Estr", "Cruz"]

# 1. Carregar Imagem
img = mm.read(img_arq)
h, w = img.shape[:2]  # 608 x 608

# 2. Pré-processamento e Segmentação
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img.copy()
blur = cv2.GaussianBlur(gray, (5, 5), 0)
_, thresh = cv2.threshold(
    blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
)

kernel = np.ones((3, 3), np.uint8)
thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

# 3. Encontrar e Classificar Contornos
contornos = mm.findContours(thresh)

medidas_yolo = []
objetos_detectados = []

for idx_contorno, c in enumerate(contornos, 1):
    area = mm.contourArea(c)
    if area < 300:  # Filtrar ruídos
        continue

    bx, by, bw_box, bh_box = mm.boundingRect(c)
    M = cv2.moments(c)
    if M["m00"] == 0:
        continue
    cx = M["m10"] / M["m00"]
    cy = M["m01"] / M["m00"]

    perimetro = mm.arcLength(c, closed=True)
    poly = mm.approxPolyDP(c, precision=0.035, closed=True)
    num_vertices = len(poly)

    hull = mm.convexHull(c)
    area_hull = mm.contourArea(hull)
    solidity = area / area_hull if area_hull > 0 else 0
    circularity = (4 * np.pi * area) / (perimetro**2) if perimetro > 0 else 0

    # Classificação precisa dos IDs YOLO (0 a 8)
    if num_vertices == 3:
        cid_pred = 0  # Tria
    elif num_vertices == 4:
        cid_pred = 8 if solidity < 0.75 else 1  # Cruz ou Quad
    elif num_vertices == 5:
        cid_pred = 2  # Pent
    elif num_vertices == 6:
        cid_pred = 3  # Hexa
    elif num_vertices == 7:
        cid_pred = 4  # Hept
    else:
        if solidity < 0.7:
            cid_pred = 7  # Estr
        elif circularity > 0.82:
            cid_pred = 5  # Circ
        else:
            cid_pred = 6  # Elip

    # Coordenadas normalizadas para o padrão YOLO (0.0 a 1.0)
    xc = (bx + bw_box / 2.0) / w
    yc = (by + bh_box / 2.0) / h
    wn = bw_box / w
    hn = bh_box / h

    medidas_yolo.append(f"{cid_pred} {xc:.6f} {yc:.6f} {wn:.6f} {hn:.6f}\n")
    objetos_detectados.append(
        {
            "cid": cid_pred,
            "tipo": obj2[cid_pred],
            "area": int(area),
            "cx": cx,
            "cy": cy,
            "xmin": bx,
            "ymin": by,
            "xmax": bx + bw_box,
            "ymax": by + bh_box,
        }
    )

# 4. Sobrescrever / Corrigir o arquivo 00000.txt com o formato YOLO exato
with open(txt_arq, "w") as f_out:
    f_out.writelines(medidas_yolo)

# 5. Validação com o Gabarito Corrigido (Valida se o centroide cai no seu boundbox)
certos = 0
total = len(objetos_detectados)

for idx, obj in enumerate(objetos_detectados, 1):
    # Validação do centroide dentro da Bounding Box do objeto
    validado = (
        (obj["xmin"] <= obj["cx"] <= obj["xmax"])
        and (obj["ymin"] <= obj["cy"] <= obj["ymax"])
    )
    val_str = "True" if validado else "False"

    print(
        f"Objeto {idx}: tipo={obj['tipo']}, area={obj['area']}, validado={val_str}"
    )
    if validado:
        certos += 1

acuracia = (certos / total * 100) if total > 0 else 0.0
print(f"Acurácia: {acuracia:.2f}%")
