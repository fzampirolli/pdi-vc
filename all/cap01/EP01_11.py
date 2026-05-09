# sua solução
import numpy as np

# Leitura do tamanho do vetor
try:
    n = int(input())
except EOFError:
    n = 0

v1 = []
# Leitura dos n elementos (pode estar um por linha ou na mesma linha)
while len(v1) < n:
    linha = input().split()
    for x in linha:
        v1.append(int(x))

v2 = []

# Processamento do Filtro de Máximo 1D
for i in range(n):
    # Define os limites da vizinhança tratando as bordas
    # i-1 pode ser negativo (borda esquerda)
    # i+1 pode exceder n-1 (borda direita)
    inicio = max(0, i - 1)
    fim = min(n, i + 2) # i+2 pois o fatiamento em Python é exclusivo no fim

    # Extrai a vizinhança (fatia do vetor)
    vizinhanca = v1[inicio:fim]

    # Calcula o máximo da vizinhança
    v2.append(max(vizinhanca))

# Saída formatada conforme especificação VPL
print("v2:")
for val in v2:
    print(val)
