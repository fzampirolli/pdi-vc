# Código Python
from morph import mm
import numpy as np

# 1 e 2. Leitura das dimensões e carregamento da imagem real do mosaico
L = int(input())
C = int(input())
f = mm.readImg(L, C, dtype='uint8')

# 3. Parâmetros da grade
linha_grade = input().split()
G = int(linha_grade[0])
S = int(linha_grade[1])

# 4. Cálculo dos mapas estruturais LBP por pixel
lbp_map, trans_map = mm.compute_lbp_map(f)

# 6. Protótipos de treinamento e mapeamentos
linha_classes = input().split()
Ncl = int(linha_classes[0])
nomes_classes = linha_classes[1:Ncl+1]
classe_para_id = {nome: i for i, nome in enumerate(nomes_classes)}

# CORREÇÃO AQUI: No EP07_07 a linha contém apenas a métrica e o k (ex: "euclidiana 1")
linha_knn = input().split()
M = linha_knn[0]
k = int(linha_knn[1])

N = int(input())
X_train = []
y_train = []
for _ in range(N):
    linha = input().split()
    y_train.append(classe_para_id[linha[0]])
    X_train.append([float(val) for val in linha[1:]])
X_train = np.array(X_train)
y_train = np.array(y_train)

# 5 e 7. Varredura da grade por linha e coluna para extração e classificação
y_pred = []
for i in range(G):
    for j in range(G):
        r_start = i * S
        c_start = j * S

        # Extrai o histograma normalizado do bloco tratando as restrições de borda global
        H_hat = mm.extract_block_histogram(lbp_map, trans_map, r_start, c_start, S, L, C)

        # Classifica por k-NN
        pred_id = mm.knn_predict_multi(X_train, y_train, H_hat, k, M, Ncl)
        y_pred.append(pred_id)
        print(nomes_classes[pred_id])

# 8. Rótulos reais e avaliação da classificação do mosaico
y_true_nomes = input().split()
y_true = np.array([classe_para_id[nome] for nome in y_true_nomes])
y_pred = np.array(y_pred)

# Matriz de confusão multi-classe e acurácia
cm = mm.multi_confusion_matrix(y_true, y_pred, Ncl)
for linha_matriz in cm:
    print(" ".join(map(str, linha_matriz)))

acuracia = np.sum(y_true == y_pred) / len(y_true)
print(f"Acuracia: {acuracia:.4f}")
