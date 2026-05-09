# sua solução
import numpy as np
import matplotlib.pyplot as plt
from morph import mm

import inspect
#print(inspect.getsource(mm.readImg))

def readImg(h, w):
    m = np.zeros((h, w), dtype='uint8')
    for l in range(h):
        m[l] = [int(i) for i in input().split() if i]
    return m

h = int(input())
w = int(input())


m = readImg(h, w)
#m = mm.readImg(h, w)

print(f"Linhas: {h}")
print(f"Colunas: {w}")
print(f"Max: {m.max()}")
print(f"Min: {m.min()}")
print(f"Media: {m.mean():.2f}")
