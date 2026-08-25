"""
Gerador automático em lote para o EP06_08 adaptado para morph.py.
Gera QR Codes reais e nítidos sem interpolação aritmética, garantindo 100% de leitura.
"""
import numpy as np
import random
import qrcode
import cv2

def desenhar_distrator_simples(cena, tipo, x, y, w, h, rng):
    cor = int(rng.randint(40, 110))
    L, C = cena.shape
    x2, y2 = min(C, x + w), min(L, y + h)
    
    if tipo == "retangulo":
        cena[y:y2, x:x2] = cor
    elif tipo == "linhas":
        passo = max(2, (y2 - y) // 4)
        for yy in range(y, y2, passo):
            cena[yy, x:x2] = cor
    elif tipo == "bloco_ruido":
        for i in range(y, y2):
            for j in range(x, x2):
                if rng.random() > 0.5:
                    cena[i, j] = cor

def gerar_caso_estavel(texto, L, C, n_distratores, seed, limiar_bin, tol_aspecto, forçar_erro=False):
    rng = random.Random(seed)
    cena = np.full((L, C), 255, dtype=np.uint8)
    
    if not forçar_erro and texto:
        # Usamos correção de erro média (M) para tornar o código mais robusto contra ruídos próximos
        qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=2, border=2)
        qr.add_data(texto)
        qr.make(fit=True)
        img_qr = qr.make_image(fill_color="black", back_color="white").convert('L')
        matriz_qr = np.array(img_qr, dtype=np.uint8)
        
        qr_h, qr_w = matriz_qr.shape
        
        qx = rng.randint(4, max(5, C - qr_w - 4))
        qy = rng.randint(4, max(5, L - qr_h - 4))
        
        cena[qy:qy+qr_h, qx:qx+qr_w] = matriz_qr
        
        binarizada_temp = np.where(cena < limiar_bin, 255, 0).astype(np.uint8)
        contornos, _ = cv2.findContours(binarizada_temp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        bbox_qr = (0, 0, 0, 0)
        maior_area = 0
        for c in contornos:
            rx, ry, rw, rh = cv2.boundingRect(c)
            area = rw * rh
            if abs((rw / rh) - 1.0) <= tol_aspecto:
                if area > maior_area:
                    maior_area = area
                    bbox_qr = (ry, rx, rh, rw)
        
        qr_tam_h, qr_tam_w = qr_h, qr_w
    else:
        bbox_qr = (0, 0, 0, 0)
        qr_tam_h, qr_tam_w = 0, 0
        qx, qy = -100, -100

    tipos_dist = ["retangulo", "linhas", "bloco_ruido"]
    colocados = 0
    tentativas = 0
    
    while colocados < n_distratores and tentativas < 200:
        tentativas += 1
        tipo = rng.choice(tipos_dist)
        w = rng.randint(12, 25)
        h = rng.randint(12, 25)
        x = rng.randint(0, C - w)
        y = rng.randint(0, L - h)
        
        if not forçar_erro and qr_tam_h > 0:
            if (x + w < qx - 4 or x > qx + qr_tam_w + 4) or (y + h < qy - 4 or y > qy + qr_tam_h + 4):
                desenhar_distrator_simples(cena, tipo, x, y, w, h, rng)
                colocados += 1
        else:
            desenhar_distrator_simples(cena, tipo, x, y, w, h, rng)
            colocados += 1
            
    return cena, bbox_qr

def salvar_em_bloco_vpl(arquivo_cases, nome_caso, cena, params, solucao_bbox, texto_solucao):
    L, C = cena.shape
    T, area_min, tol_aspecto, margem = params
    
    with open(arquivo_cases, "a", encoding="utf-8") as f:
        f.write(f"#### case={nome_caso}\n\n")
        f.write("input=" + f"{L}\n{C}\n{T} {area_min} {tol_aspecto} {margem}\n")
        for row in cena:
            f.write(" ".join(str(int(v)) for v in row) + "\n")
        f.write("output=")
        if texto_solucao:
            y, x, h, w = solucao_bbox
            f.write(f"{y} {x} {h} {w}\n{texto_solucao}\n\n")
        else:
            f.write("QRCODE_NAO_ENCONTRADO\n\n")

def salvar_imagem_pgm(caminho_pgm, cena):
    L, C = cena.shape
    with open(caminho_pgm, "w", encoding="utf-8") as f:
        f.write(f"P2\n{C} {L}\n255\n")
        for row in cena:
            f.write(" ".join(str(int(v)) for v in row) + "\n")

if __name__ == "__main__":
    ARQUIVO_CASES = "EP06_08.cases"
    
    with open(ARQUIVO_CASES, "w", encoding="utf-8") as f:
        f.write("# Suite de Casos de Teste Estabilizados para VPL\n\n")

    configuracoes_casos = [
        {"nome": "Caso1_Normal", "texto": "EP06_08 - PDI-VC | Parabens! Voce decodificou este QR Code!", "L": 180, "C": 180, "dist": 3, "seed": 10},
        {"nome": "Caso2_Complexo", "texto": "EP06_08 - PDI-VC | Parabens! Missao cumprida: QR Code detectado!", "L": 220, "C": 220, "dist": 5, "seed": 20},
        {"nome": "Caso3_MensagemSecreta", "texto": "EP06_08 - PDI-VC | Sucesso! Mensagem secreta encontrada com exito!!!", "L": 220, "C": 220, "dist": 4, "seed": 30},
        {"nome": "Caso4_Excelente", "texto": "EP06_08 - PDI-VC | Excelente! O QR Code foi decodificado com sucesso.", "L": 220, "C": 220, "dist": 3, "seed": 40},
        {"nome": "Caso5_Nao_Encontrado", "texto": "", "L": 150, "C": 150, "dist": 5, "seed": 50}
    ]

    print("Gerando casos de teste finais com compatibilidade ASCII garantida...")
    print("-" * 75)

    for idx, config in enumerate(configuracoes_casos, start=1):
        limiar, area_min, tol, margem = 127, 180, 0.22, 6
        forçar_erro = (config["texto"] == "")
        if forçar_erro:
            area_min = 45000 
            
        cena, bbox = gerar_caso_estavel(
            config["texto"], config["L"], config["C"], config["dist"], config["seed"], limiar, tol, forçar_erro
        )

        salvar_em_bloco_vpl(
            arquivo_cases=ARQUIVO_CASES,
            nome_caso=config["nome"],
            cena=cena,
            params=(limiar, area_min, tol, margem),
            solucao_bbox=bbox,
            texto_solucao=config["texto"]
        )
        
        nome_imagem_pgm = f"{config['nome']}.pgm"
        salvar_imagem_pgm(nome_imagem_pgm, cena)
        
        print(f"[{idx}/5] Sincronizado com Sucesso: '{config['nome']}' -> Coordenadas: {bbox}")

    print("-" * 75)
    print("Concluido! Todos os 5 casos estao prontos para rodar com 100% de aproveitamento.")