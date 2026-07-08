"""
Protótipo do gerador de cenas com QRCode + objetos distratores,
usado para validar o formato de entrada/saída do EP06_08.
"""
import numpy as np
import cv2
import qrcode
import random
import argparse
import sys


def gerar_qrcode_array(texto, tamanho_px, border_modules=4):
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=border_modules,
    )
    qr.add_data(texto)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("L")
    arr = np.array(img, dtype=np.uint8)
    arr = cv2.resize(arr, (tamanho_px, tamanho_px), interpolation=cv2.INTER_NEAREST)
    return arr


def desenhar_distrator(cena, tipo, x, y, w, h, rng):
    cor = int(rng.integers(0, 120))
    if tipo == "quadrado_ruido":
        bloco = rng.integers(0, 256, size=(h, w), dtype=np.uint8)
        cena[y:y+h, x:x+w] = bloco
    elif tipo == "circulo":
        cv2.circle(cena, (x + w // 2, y + h // 2), min(w, h) // 2, cor, -1)
    elif tipo == "retangulo":
        cv2.rectangle(cena, (x, y), (x + w, y + h), cor, -1)
    elif tipo == "linhas":
        passo = max(2, h // 8)
        for yy in range(y, y + h, passo):
            cv2.line(cena, (x, yy), (x + w, yy), cor, 1)
    elif tipo == "falso_qr":
        # quadrado com "cantos" escuros, mas sem estrutura real de QR
        cena[y:y+h, x:x+w] = 255
        c = max(2, w // 6)
        for (cx, cy) in [(x, y), (x + w - c, y), (x, y + h - c)]:
            cena[cy:cy+c, cx:cx+c] = 0


def gerar_cena(texto, L, C, n_distratores, seed=42, sobreposicao_max=0.0):
    rng = np.random.default_rng(seed)
    py_rng = random.Random(seed)
    cena = np.full((L, C), 255, dtype=np.uint8)

    qr_tam = int(min(L, C) * py_rng.uniform(0.30, 0.40))
    qr_arr = gerar_qrcode_array(texto, qr_tam)

    max_x = C - qr_tam - 1
    max_y = L - qr_tam - 1
    qx = py_rng.randint(0, max(1, max_x))
    qy = py_rng.randint(0, max(1, max_y))
    cena[qy:qy+qr_tam, qx:qx+qr_tam] = qr_arr
    bbox_qr = (qy, qx, qr_tam, qr_tam)  # (linha, coluna, altura, largura)

    tipos = ["quadrado_ruido", "circulo", "retangulo", "linhas", "falso_qr"]
    tentativas = 0
    colocados = 0
    while colocados < n_distratores and tentativas < n_distratores * 20:
        tentativas += 1
        tipo = py_rng.choice(tipos)
        w = py_rng.randint(int(qr_tam * 0.4), int(qr_tam * 1.3))
        h = w if tipo in ("quadrado_ruido", "falso_qr") else py_rng.randint(int(qr_tam*0.3), int(qr_tam*1.3))
        x = py_rng.randint(0, max(1, C - w - 1))
        y = py_rng.randint(0, max(1, L - h - 1))
        # evita sobrepor fortemente o QR real (com uma pequena folga de segurança)
        folga = 4
        ix1, iy1 = max(x, qx - folga), max(y, qy - folga)
        ix2, iy2 = min(x+w, qx+qr_tam+folga), min(y+h, qy+qr_tam+folga)
        inter = max(0, ix2-ix1) * max(0, iy2-iy1)
        if inter > sobreposicao_max * w * h:
            continue
        desenhar_distrator(cena, tipo, x, y, w, h, rng)
        colocados += 1

    return cena, bbox_qr


def salvar_formato_vpl(cena, caminho_txt):
    L, C = cena.shape
    with open(caminho_txt, "w") as f:
        f.write(f"{L}\n{C}\n")
        for row in cena:
            f.write(" ".join(str(int(v)) for v in row) + "\n")


def segmentar_e_decodificar(cena, T=127, area_min=200, tol_aspecto=0.25, margem=6):
    """Mesmo algoritmo de referência descrito no enunciado do EP06_08,
    usado aqui apenas para VALIDAR se a cena gerada é de fato solucionável."""
    _, bin_img = cv2.threshold(cena, T, 255, cv2.THRESH_BINARY_INV)
    contornos, _ = cv2.findContours(bin_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidatos = []
    for c in contornos:
        x, y, w, h = cv2.boundingRect(c)
        area = w * h
        if area < area_min:
            continue
        aspecto = w / h if h > 0 else 0
        if abs(aspecto - 1.0) > tol_aspecto:
            continue
        candidatos.append((area, x, y, w, h))
    candidatos.sort(key=lambda t: -t[0])
    detector = cv2.QRCodeDetector()
    L, C = cena.shape
    for area, x, y, w, h in candidatos:
        x0, y0 = max(0, x - margem), max(0, y - margem)
        x1, y1 = min(C, x + w + margem), min(L, y + h + margem)
        roi = cena[y0:y1, x0:x1]
        texto, _, _ = detector.detectAndDecode(roi)
        if texto:
            return (y0, x0, y1 - y0, x1 - x0), texto
    return None, ""


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Gera cenas com um QRCode real e vários objetos distratores, "
                    "no mesmo formato de entrada usado pelos EPs (L, C, matriz)."
    )
    ap.add_argument("--texto", default="EP06_08 - PDI-VC\n🌻 Parabéns!\nSua câmera enxergou o que os pixels escondiam!", help="Texto a ser codificado no QRCode")
    ap.add_argument("--L", type=int, default=220, help="Altura da cena (linhas)")
    ap.add_argument("--C", type=int, default=220, help="Largura da cena (colunas)")
    ap.add_argument("--n_distratores", type=int, default=8, help="Quantidade de objetos distratores")
    ap.add_argument("--seed", type=int, default=42, help="Semente inicial (usada com --validar)")
    ap.add_argument("--saida_png", default="cena.png", help="Caminho de saída da imagem PNG")
    ap.add_argument("--saida_txt", default="cena_vpl.txt", help="Caminho de saída no formato texto (VPL)")
    ap.add_argument("--validar", action="store_true",
                    help="Tenta sementes sequenciais a partir de --seed até obter uma cena "
                         "em que o algoritmo de referência consiga segmentar e decodificar o QRCode")
    args = ap.parse_args()

    seed = args.seed
    tentativas = 0
    while True:
        cena, bbox = gerar_cena(args.texto, args.L, args.C, args.n_distratores, seed=seed)
        achado, texto_decodificado = segmentar_e_decodificar(cena)
        sucesso = (texto_decodificado == args.texto)
        tentativas += 1
        if not args.validar or sucesso or tentativas > 200:
            break
        seed += 1

    cv2.imwrite(args.saida_png, cena)
    salvar_formato_vpl(cena, args.saida_txt)

    print(f"Semente utilizada: {seed}")
    print(f"Imagem salva em: {args.saida_png}")
    print(f"Entrada (formato VPL) salva em: {args.saida_txt}")
    print(f"bbox real do QRCode (linha, coluna, altura, largura): {bbox}")
    print(f"Solução de referência (bbox, texto): {achado}, {texto_decodificado!r}")
    if args.validar:
        print("Cena validada:", "OK" if sucesso else "FALHOU (nenhuma semente testada funcionou)")
