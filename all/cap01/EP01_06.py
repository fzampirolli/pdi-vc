# sua solução
import numpy as np
from morph import mm

# Leitura das dimensões
L = int(input())
C = int(input())

# No formato de entrada deste EP, cada pixel possui 3 valores (R, G, B)
# mm.readImg(L, C*3) ou uma leitura customizada resolvem a captura dos dados
# Para facilitar a manipulação, lemos todos os dados e fazemos o reshape
dados = []
while len(dados) < L * C * 3:
    linha = input().split()
    for val in linha:
        dados.append(int(val))

# Transformamos em um array numpy com 3 colunas (R, G, B)
pixels_rgb = np.array(dados).reshape(L * C, 3)

# Aplicamos a fórmula ITU-R BT.601
# g = 0.299*R + 0.587*G + 0.114*B
pesos = np.array([0.299, 0.587, 0.114])
cinzas_float = np.dot(pixels_rgb, pesos)

# Arredondamento para o inteiro mais próximo (round)
cinzas_int = np.round(cinzas_float).astype(int)

# Redimensionamos para o formato da matriz de saída L x C
matriz_saida = cinzas_int.reshape(L, C)

# Impressão formatada
for i in range(L):
    print(*(matriz_saida[i]))
