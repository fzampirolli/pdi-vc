# Código Python
from morph import mm
import numpy as np

USE_DIDATICO = True  # True -> usa a família de métodos didáticos (*0); False -> clássicos (sklearn)

# 1. Classes
nomes_classes = mm.readClasses()
label_to_id = {nome: i for i, nome in enumerate(nomes_classes)}
C = len(nomes_classes)

# 2. Configuração
H, M, k = input().split()
H, k = int(H), int(k)

# 3. Treinamento — rótulo no início da linha, convertido via label_to_id
N = int(input())
X_train, y_train = mm.readTrain(N, D=H, label_type=label_to_id.get, label_pos='start')

# 4. Teste — mesmo formato, também com rótulo real no início
Q = int(input())
X_test, y_test = mm.readTest(Q, D=H, label_type=label_to_id.get, label_pos='start')

# 5 e 6. Classificação k-NN amostra a amostra
y_pred = []
for x in X_test:
    if USE_DIDATICO:
        p = mm.knn0(X_train, y_train, x, k, metric=M, num_classes=C, desempate='menor_id')
    else:
        p = mm.knn(X_train, y_train, x, k, metric=M)
    y_pred.append(p)
    print(nomes_classes[p])

# 7. Matriz de confusão
if USE_DIDATICO:
    cm, _, _, _ = mm.confusion0(y_test, np.array(y_pred), num_classes=C)
else:
    cm, _, _, _ = mm.confusion(y_test, np.array(y_pred), num_classes=C)
for linha_cm in cm:
    print(" ".join(str(v) for v in linha_cm))

# 8 e 9. Acurácia
acuracia = np.sum(np.array(y_pred) == y_test) / Q
print(f"Acuracia: {acuracia:.4f}")
