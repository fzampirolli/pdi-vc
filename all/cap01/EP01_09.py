# sua solução
import numpy as np

# Leitura das dimensões
L = int(input())
C = int(input())

# Criação da matriz utilizando a lógica de paridade
# Criamos uma matriz vazia para preencher ou usamos list comprehension
for i in range(L):
    linha = []
    for j in range(C):
        # A regra: (i + j) par -> 0, (i + j) ímpar -> 1
        if (i + j) % 2 == 0:
            linha.append(0)
        else:
            linha.append(1)

    # Impressão da linha com elementos separados por espaço
    print(*linha)
