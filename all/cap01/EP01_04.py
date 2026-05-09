# sua solução
import numpy as np
import matplotlib.pyplot as plt
from morph import mm

import inspect
#print(inspect.getsource(mm.readImg))

h = int(input())
w = int(input())

m = mm.readImg(h, w)

print(f"Linhas: {h}")
print(f"Colunas: {w}")
print(f"Max: {m.max()}")
print(f"Min: {m.min()}")
print(f"Media: {m.mean():.2f}")
