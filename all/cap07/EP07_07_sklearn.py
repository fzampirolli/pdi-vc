# Código Python
from morph import mm
import numpy as np
from sklearn.neighbors import KNeighborsClassifier
from sklearn.metrics import confusion_matrix

# 1 e 2. Leitura das dimensões e carregamento da imagem real do mosaico
L = int(input())
C = int(input())
f = mm.readImg(L, C, dtype='uint8')

# 3. Parâmetros da grade
G, S = map(int, input().split())

# 4. Cálculo dos mapas estruturais LBP por pixel (usando o original do morph)
lbp_map, trans_map = mm.compute_lbp_map(f)

# 6. Protótipos de treinamento e mapeamentos
nomes_classes = mm.readClasses()
classe_para_id = {nome: i for i, nome in enumerate(nomes_classes)}
Ncl = len(nomes_classes)

# Configuração do k-NN (Métrica e K)
M, k = input().split()
k = int(k)

metric_map = {'euclidian': 'euclidean', 'euclidiana': 'euclidean', 'manhattan': 'manhattan'}
sklearn_metric = metric_map.get(M.lower(), M)

# 3. Treinamento — Lê as N linhas usando a função do morph
N = int(input())
X_train, y_train = mm.readTrain(N, D=58, label_type=classe_para_id.get, label_pos='start') 
# Nota: Ajuste o 'D' (dimensão) se o histograma do LBP tiver um tamanho fixo diferente (geralmente 58 para LBP u2)

# Inicializa e treina o k-NN do sklearn
knn = KNeighborsClassifier(n_neighbors=k, metric=sklearn_metric)
knn.fit(X_train, y_train)

# 5 e 7. Varredura da grade por linha e coluna para extração
X_test_blocks = []
for i in range(G):
    for j in range(G):
        r_start = i * S
        c_start = j * S

        # Extrai o histograma usando a função do morph
        H_hat = mm.extract_block_histogram(lbp_map, trans_map, r_start, c_start, S, L, C)
        X_test_blocks.append(H_hat)

# Predição em lote (batch) com sklearn
y_pred = knn.predict(X_test_blocks)

for pred_id in y_pred:
    print(nomes_classes[pred_id])

# 8. Rótulos reais e avaliação da classificação do mosaico
y_true_nomes = input().split()
y_true = np.array([classe_para_id[nome] for nome in y_true_nomes])

# Matriz de confusão usando sklearn
cm = confusion_matrix(y_true, y_pred, labels=range(Ncl))
for linha_matriz in cm:
    print(" ".join(map(str, linha_matriz)))

acuracia = np.sum(y_true == y_pred) / len(y_true)
print(f"Acuracia: {acuracia:.4f}")