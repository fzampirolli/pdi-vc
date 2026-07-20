# Código Python
from morph import mm
import numpy as np

USE_DIDATICO = True  # True -> usa a família de métodos didáticos (*0); False -> clássicos (sklearn)

# 1. Quantidade de amostras
N = int(input())

# 2. Leitura da matriz N x 2 usando o método genérico readImg adaptado
dados = mm.readImg(N, 2, dtype='int32')

# Fatiamento das colunas: coluna 0 é o real (y), coluna 1 é o previsto (y_hat)
y_true = dados[:, 0]
y_pred = dados[:, 1]

# 3, 4 e 5. Extração da matriz e cálculo das métricas
if USE_DIDATICO:
    VP, FP, FN, VN, acuracia, precisao, revocacao = mm.confusion0(y_true, y_pred)
else:
    VP, FP, FN, VN, acuracia, precisao, revocacao = mm.confusion(y_true, y_pred)

# Pós-processamento: garante a convenção "indefinida" quando o denominador é zero
if VP + FP == 0:
    precisao = "indefinida"
if VP + FN == 0:
    revocacao = "indefinida"

# 6. Exibição formatada conforme a especificação do VPL
print(f"VP={VP} FP={FP} FN={FN} VN={VN}")
print(f"Acuracia: {acuracia:.4f}")
if isinstance(precisao, str):
    print(f"Precisao: {precisao}")
else:
    print(f"Precisao: {precisao:.4f}")
if isinstance(revocacao, str):
    print(f"Revocacao: {revocacao}")
else:
    print(f"Revocacao: {revocacao:.4f}")
