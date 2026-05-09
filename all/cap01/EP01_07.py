# sua solução
import numpy as np
from morph import mm

# Leitura das dimensões e do limiar
L = int(input())
C = int(input())
T = int(input())

# Leitura da matriz de pixels
# mm.readImg lida com a captura dos dados independentemente da quebra de linha
img = mm.readImg(L, C)

# Aplicação da regra de binarização:
# Se p > T, resultado é 255. Caso contrário, 0.
# Em NumPy, podemos usar a função where ou uma máscara booleana multiplicada por 255.
binaria = np.where(img > T, 255, 0)

# Impressão da matriz resultante
for i in range(L):
    # Converte os valores para inteiro e imprime separados por espaço
    print(*(binaria[i].astype(int)))
