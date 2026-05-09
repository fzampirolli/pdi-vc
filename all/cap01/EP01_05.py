# sua solução
import numpy as np
from morph import mm

# Leitura das dimensões
L = int(input())
C = int(input())

# Leitura da matriz utilizando a biblioteca morph (ou via input padrão)
# mm.readImg retorna uma matriz numpy baseada nas dimensões fornecidas
img = mm.readImg(L, C)

# Cálculo do negativo
# Em numpy, a operação é vetorizada: 255 subtrai de cada elemento
negativo = 255 - img

# Impressão da matriz resultante
for i in range(L):
    # Converte cada linha para string separada por espaços
    print(*(negativo[i].astype(int)))
