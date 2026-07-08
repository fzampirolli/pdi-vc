# Código Python
import numpy as np
import cv2
from morph import mm

def resolver_ep():
    try:
        L = int(input())
        C = int(input())
    except EOFError:
        return

    linha_params = input().split()
    T = int(linha_params[0])
    area_min = int(linha_params[1])
    tol = float(linha_params[2])
    margem = int(linha_params[3])

    # Carrega a matriz usando morph.py
    f = mm.readImg(L, C)

    # Binarização invertida
    binarizada = np.where(f < T, 255, 0).astype(np.uint8)

    # Encontra os contornos externos
    contornos, _ = cv2.findContours(binarizada, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    candidatos = []
    for c in contornos:
        x, y, w, h = cv2.boundingRect(c)
        area = w * h
        if area > area_min:
            if abs((w / h) - 1.0) <= tol:
                candidatos.append((area, y, x, h, w))

    # Ordena decrescente por área
    candidatos.sort(key=lambda item: item[0], reverse=True)

    qrcode_encontrado = False
    detector = cv2.QRCodeDetector()

    for area, y, x, h, w in candidatos:
        y_ini = max(0, y - margem)
        x_ini = max(0, x - margem)
        y_fim = min(L, y + h + margem)
        x_fim = min(C, x + w + margem)

        recorte = f[y_ini:y_fim, x_ini:x_fim]
        dados, _, _ = detector.detectAndDecode(recorte)

        if dados:
            print(f"{y} {x} {h} {w}")
            print(dados)
            qrcode_encontrado = True
            break

    if not qrcode_encontrado:
        print("QRCODE_NAO_ENCONTRADO")

if __name__ == "__main__":
    resolver_ep()
