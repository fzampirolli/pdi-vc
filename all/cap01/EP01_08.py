# sua solução
import numpy as np
from morph import mm

# Leitura das dimensões
L = int(input())
C = int(input())

# Leitura de alpha (float) e beta (int)
linha_params = input().split()
alpha = float(linha_params[0])
beta = int(linha_params[1])

# Leitura da matriz de pixels
img = mm.readImg(L, C)

# Aplicação da fórmula: p' = alpha * p + beta
# O NumPy lida com a operação de forma vetorizada
processada = alpha * img + beta

# Arredondamento matemático (round) e conversão para inteiro
# np.round segue o padrão de arredondar para o inteiro mais próximo
processada = np.round(processada).astype(int)

# Saturação (Clip): Garante o intervalo [0, 255]
# np.clip(vetor, minimo, maximo)
resultado = np.clip(processada, 0, 255)

# Impressão da matriz resultante
for i in range(L):
    print(*(resultado[i]))
