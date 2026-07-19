# Código Python
from morph import mm
import numpy as np

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
    p = mm.knn_predict_multi(X_train, y_train, x, k, M, C)
    y_pred.append(p)
    print(nomes_classes[p])

# 7. Matriz de confusão
cm = mm.multi_confusion_matrix(y_test, np.array(y_pred), C)
for linha_cm in cm:
    print(" ".join(str(v) for v in linha_cm))

# 8 e 9. Acurácia
acuracia = np.sum(np.array(y_pred) == y_test) / Q
print(f"Acuracia: {acuracia:.4f}")
