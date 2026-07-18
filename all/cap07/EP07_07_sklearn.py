# Código Python
from morph import mm
import numpy as np
from sklearn.neighbors import KNeighborsClassifier
from sklearn.metrics import confusion_matrix, accuracy_score

# 1 e 2. Leitura da imagem
L, C = int(input()), int(input())
f = mm.readImg(L, C, dtype='uint8')

# 3. Parâmetros da grade
linha_grade = input().split()
G, S = int(linha_grade[0]), int(linha_grade[1])

# 4. Cálculo dos mapas via morph
lbp_map, trans_map = mm.compute_lbp_map(f)

# 6. Protótipos de treinamento e mapeamentos
linha_classes = input().split()
Ncl = int(linha_classes[0])
nomes_classes = linha_classes[1:Ncl+1]
classe_para_id = {nome: i for i, nome in enumerate(nomes_classes)}

# CORREÇÃO AQUI: No EP07_07 a linha contém apenas a métrica e o k (ex: "euclidiana 1")
linha_knn = input().split()
M = 'euclidean' if linha_knn[0] == 'euclidiana' else 'manhattan'
k = int(linha_knn[1])

N = int(input())
X_train, y_train = [], []
for _ in range(N):
    linha = input().split()
    y_train.append(classe_para_id[linha[0]])
    X_train.append([float(val) for val in linha[1:]])
X_train, y_train = np.array(X_train), np.array(y_train)

# Inicializa o classificador do scikit-learn
knn = KNeighborsClassifier(n_neighbors=k, algorithm='brute', metric=M)
knn.fit(X_train, y_train)

# 5 e 7. Varredura da grade e predição clássica
X_test = []
for i in range(G):
    for j in range(G):
        r_start, c_start = i * S, j * S
        H_hat = mm.extract_block_histogram(lbp_map, trans_map, r_start, c_start, S, L, C)
        X_test.append(H_hat)
X_test = np.array(X_test)

# Predição mantendo critérios determinísticos de desempate por prob
probabilidades = knn.predict_proba(X_test)
y_pred = []
for prob in probabilidades:
    max_prob = np.max(prob)
    classes_empatadas = np.where(prob == max_prob)[0]
    pred_id = classes_empatadas[0]
    y_pred.append(pred_id)
    print(nomes_classes[pred_id])

y_pred = np.array(y_pred)

# 8. Avaliação
y_true_nomes = input().split()
y_true = np.array([classe_para_id[nome] for nome in y_true_nomes])

# Matriz e acurácia via scikit-learn
cm = confusion_matrix(y_true, y_pred, labels=list(range(Ncl)))
for linha_matriz in cm:
    print(" ".join(map(str, linha_matriz)))

acuracia = accuracy_score(y_true, y_pred)
print(f"Acuracia: {acuracia:.4f}")# Código Python
from morph import mm
import numpy as np
from sklearn.neighbors import KNeighborsClassifier
from sklearn.metrics import confusion_matrix, accuracy_score

# 1 e 2. Leitura da imagem
L, C = int(input()), int(input())
f = mm.readImg(L, C, dtype='uint8')

# 3. Parâmetros da grade
linha_grade = input().split()
G, S = int(linha_grade[0]), int(linha_grade[1])

# 4. Cálculo dos mapas via morph
lbp_map, trans_map = mm.compute_lbp_map(f)

# 6. Protótipos de treinamento e mapeamentos
linha_classes = input().split()
Ncl = int(linha_classes[0])
nomes_classes = linha_classes[1:Ncl+1]
classe_para_id = {nome: i for i, nome in enumerate(nomes_classes)}

# CORREÇÃO AQUI: No EP07_07 a linha contém apenas a métrica e o k (ex: "euclidiana 1")
linha_knn = input().split()
M = 'euclidean' if linha_knn[0] == 'euclidiana' else 'manhattan'
k = int(linha_knn[1])

N = int(input())
X_train, y_train = [], []
for _ in range(N):
    linha = input().split()
    y_train.append(classe_para_id[linha[0]])
    X_train.append([float(val) for val in linha[1:]])
X_train, y_train = np.array(X_train), np.array(y_train)

# Inicializa o classificador do scikit-learn
knn = KNeighborsClassifier(n_neighbors=k, algorithm='brute', metric=M)
knn.fit(X_train, y_train)

# 5 e 7. Varredura da grade e predição clássica
X_test = []
for i in range(G):
    for j in range(G):
        r_start, c_start = i * S, j * S
        H_hat = mm.extract_block_histogram(lbp_map, trans_map, r_start, c_start, S, L, C)
        X_test.append(H_hat)
X_test = np.array(X_test)

# Predição mantendo critérios determinísticos de desempate por prob
probabilidades = knn.predict_proba(X_test)
y_pred = []
for prob in probabilidades:
    max_prob = np.max(prob)
    classes_empatadas = np.where(prob == max_prob)[0]
    pred_id = classes_empatadas[0]
    y_pred.append(pred_id)
    print(nomes_classes[pred_id])

y_pred = np.array(y_pred)

# 8. Avaliação
y_true_nomes = input().split()
y_true = np.array([classe_para_id[nome] for nome in y_true_nomes])

# Matriz e acurácia via scikit-learn
cm = confusion_matrix(y_true, y_pred, labels=list(range(Ncl)))
for linha_matriz in cm:
    print(" ".join(map(str, linha_matriz)))

acuracia = accuracy_score(y_true, y_pred)
print(f"Acuracia: {acuracia:.4f}")
