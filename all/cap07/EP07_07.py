# Código Python
from morph import mm
import numpy as np

USE_DIDATICO = True  # True -> usa a família de métodos didáticos (*0); False -> clássicos (sklearn/skimage)

# 1 e 2. Leitura das dimensões e carregamento da imagem real do mosaico
L = int(input())
C = int(input())
f = mm.readImg(L, C, dtype='uint8')

# 3. Parâmetros da grade
linha_grade = input().split()
G = int(linha_grade[0])
S = int(linha_grade[1])

# 6. Protótipos de treinamento e mapeamentos
linha_classes = input().split()
Ncl = int(linha_classes[0])
nomes_classes = linha_classes[1:Ncl+1]
classe_para_id = {nome: i for i, nome in enumerate(nomes_classes)}

linha_knn = input().split()
M = linha_knn[0]
k = int(linha_knn[1])

# Treinamento — rótulo (nome da classe) no início da linha, histograma de 10 bins em seguida
N = int(input())
X_train, y_train = mm.readTrain(N, D=10, label_type=classe_para_id.get, label_pos='start')

# 4, 5 e 7. Varredura da grade: extração do histograma do bloco + classificação
y_pred = []

# No modo clássico, calculamos o mapa LBP completo primeiro para respeitar o skimage
if not USE_DIDATICO:
    mapa_lbp = mm.lbp(f.astype(float), P=8, R=1, method='default')

for i in range(G):
    for j in range(G):
        r_start = i * S
        c_start = j * S
        if USE_DIDATICO:
            H_hat = mm.lbp0(f, r_start, c_start, S)
            pred_id = mm.knn0(X_train, y_train, H_hat, k, metric=M, num_classes=Ncl, desempate='menor_id')
        else:
            # Para coincidir com a regra do EP (10 bins por contagem de bits), usamos lbp0 na extração de histograma
            # ou passamos f via lbp0 se os protótipos de treino usaram lbp0.
            H_hat = mm.lbp0(f, r_start, c_start, S)
            pred_id = mm.knn(X_train, y_train, H_hat, k, metric=M)

        y_pred.append(pred_id)
        print(nomes_classes[pred_id])

# 8. Rótulos reais e avaliação da classificação do mosaico
y_true_nomes = input().split()
y_true = np.array([classe_para_id[nome] for nome in y_true_nomes])
y_pred = np.array(y_pred)

# Matriz de confusão multi-classe e acurácia
if USE_DIDATICO:
    cm, _, _, _ = mm.confusion0(y_true, y_pred, num_classes=Ncl)
else:
    cm, _, _, _ = mm.confusion(y_true, y_pred, num_classes=Ncl)

for linha_matriz in cm:
    print(" ".join(map(str, linha_matriz)))
acuracia = np.sum(y_true == y_pred) / len(y_true)
print(f"Acuracia: {acuracia:.4f}")
