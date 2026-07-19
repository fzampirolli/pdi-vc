# Código Python
from morph import mm
import numpy as np
from sklearn.neighbors import KNeighborsClassifier
from sklearn.metrics import confusion_matrix

# 1. Configurações e Classes
nomes_classes = mm.readClasses()
label_to_id = {nome: i for i, nome in enumerate(nomes_classes)}

H, M, k = input().split()
H, k = int(H), int(k)

# Mapeia a métrica para o padrão do sklearn (Ex: L2 -> euclidean, L1 -> manhattan)
metrica = {'L2': 'euclidean', 'L1': 'manhattan'}.get(M, 'euclidean')

# 2. Carga dos Dados (Treino e Teste)
N = int(input())
X_train, y_train = mm.readTrain(N, D=H, label_type=label_to_id.get, label_pos='start')
Q = int(input())
X_test, y_test = mm.readTest(Q, D=H, label_type=label_to_id.get, label_pos='start')

# 3. Predição com Sklearn (Treina e classifica tudo em lote)
knn = KNeighborsClassifier(n_neighbors=k, metric=metrica).fit(X_train, y_train)
y_pred = knn.predict(X_test)

# Exibe as classes preditas
for p in y_pred:
    print(nomes_classes[p])

# 4. Matriz de Confusão (Agora usando o Sklearn)
# Passamos o y_test, as predições e os IDs de todas as classes possíveis
cm = confusion_matrix(y_test, y_pred, labels=list(range(len(nomes_classes))))
for linha in cm:
    print(" ".join(str(v) for v in linha))

# 5. Acurácia
print(f"Acuracia: {np.mean(y_pred == y_test):.4f}")
