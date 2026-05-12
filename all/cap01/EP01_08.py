# sua solução
import numpy as np
from morph import mm

L = int(input())
C = int(input())

linha_params = input().split()
T  = int(linha_params[0])
d1 = int(linha_params[1])
d2 = int(linha_params[2])

img = mm.readImg(L, C)

# Aplica transformação condicional por faixa
result = np.where(img < T, img + d1, img + d2)

print(mm.drawImage(result))
