# Código Python
from morph import mm
import numpy as np

USE_DIDATICO = True  # True -> usa a família de métodos didáticos (*0); False -> clássicos (sklearn)

# 1. Quantidade de vizinhancas
T = int(input())

# 2, 4 e 8. Processamento sequencial de cada bloco 3x3
for _ in range(T):
    # Lê a matriz 3x3 usando o readImg genérico
    m = mm.readImg(3, 3, dtype="int32")
    # Extrai as métricas encapsuladas na biblioteca (pixel central do bloco 3x3)
    if USE_DIDATICO: # padrão usar implementação didática
        lbp, trans, classe = mm.lbp0(m, 1, 1)
    else:
        lbp_map = mm.lbp(m.astype(float), method='default')  # skimage local_binary_pattern
        codigo_sk = int(lbp_map[1, 1])
        # skimage numera os vizinhos em ordem diferente do didático (começa na direita,
        # sentido anti-horário); converte para a convenção didática (começa no canto
        # superior-esquerdo, sentido horário) via a permutação fixa i = (3 - j) mod 8
        bits_sk = [(codigo_sk >> j) & 1 for j in range(8)]
        lbp = sum(bits_sk[j] << ((3 - j) % 8) for j in range(8))
        bits = [(lbp >> i) & 1 for i in range(8)]
        trans = sum(bits[i] != bits[(i + 1) % 8] for i in range(8))
        classe = "UNIFORME" if trans <= 2 else "NAO_UNIFORME"
    # Impressão de saída formatada exigida pelo VPL
    print(f"LBP={lbp} transicoes={trans} {classe}")
