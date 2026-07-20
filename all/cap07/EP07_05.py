# Código Python
from morph import mm
import numpy as np

USE_DIDATICO = True  # True -> usa a família de métodos didáticos (*0); False -> clássicos (sklearn)

# 1. Dimensões e parâmetros
linha_params = input().split()
n = int(linha_params[0])
B = int(linha_params[1])

# 2 e 3. Leitura das matrizes n x n usando o readImg genérico em float
magnitudes = mm.readImg(n, n, dtype="float64")
orientacoes = mm.readImg(n, n, dtype="float64")

# 4, 5 e 6. Processamento das etapas do HOG encapsuladas
if USE_DIDATICO:
    H, H_hat = mm.hog0(magnitudes, orientacoes, B)
else:
    raise NotImplementedError(
        "mm.hog (skimage) opera sobre uma imagem crua e calcula magnitude/orientação "
        "internamente — não existe forma pública de injetar magnitude/orientação já "
        "prontas. Portanto não há chamada de mm.hog equivalente a hog0(magnitudes, "
        "orientacoes, B) para este exercício."
    )

# 7. Saída formatada com espaçamento adequado e precisão exigida
print(" ".join(f"{val:.2f}" for val in H))
print(" ".join(f"{val:.4f}" for val in H_hat))
