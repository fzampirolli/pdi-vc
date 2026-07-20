# Código Python
from morph import mm

USE_DIDATICO = True  # True -> usa a família de métodos didáticos (*0); False -> clássicos (sklearn)

# 1. Parâmetros iniciais
N, k = map(int, input().split())

# 2. Leitura padronizada de treino e teste
X_train, y_train = mm.readTrain(N, D=2)
Q = int(input())
X_test = mm.readTest(Q, D=2)

total_classe_1 = 0

# 3. Classificação do conjunto de teste (mm.knn = clássico, via sklearn)
for x_t in X_test:
    if USE_DIDATICO:
        pred = mm.knn0(X_train, y_train, x_t, k)
    else:
        pred = mm.knn(X_train, y_train, x_t, k)
    print(pred)
    if pred == 1: total_classe_1 += 1

print(f"Total classe 1: {total_classe_1}")
