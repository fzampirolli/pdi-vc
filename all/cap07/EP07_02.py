# Código Python
from morph import mm
import numpy as np

USE_DIDATICO = True  # True -> usa a família de métodos didáticos (*0); False -> clássicos (sklearn)

# 1. Parâmetros iniciais
linha_params = input().split()
N = int(linha_params[0])
k = int(linha_params[1])
D = 2  # Dimensão (Área e Circularidade)

# 2. Leitura padronizada dos dados
X_train, y_train = mm.readTrain(N, D)
Q = int(input())
X_test = mm.readTest(Q, D)

# 3. Normalização usando a biblioteca didática
X_train_norm, X_test_norm = mm.zscore0(X_train, X_test)

divergencias = 0
# 4. Classificação e Comparação (Sem vs Com Normalização)
for i in range(Q):
    if USE_DIDATICO:
        pred_sem = mm.knn0(X_train, y_train, X_test[i], k)
        pred_com = mm.knn0(X_train_norm, y_train, X_test_norm[i], k)
    else:
        pred_sem = mm.knn(X_train, y_train, X_test[i], k)
        pred_com = mm.knn(X_train_norm, y_train, X_test_norm[i], k)

    print(f"SemNorm={pred_sem} ComNorm={pred_com}")
    if pred_sem != pred_com:
        divergencias += 1
print(f"Divergiu: {divergencias}")
