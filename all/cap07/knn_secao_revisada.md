## Métrica de Distância

A proximidade entre duas amostras é normalmente quantificada pela
**distância euclidiana**, definida por

$$
d(x,x_i)=\|x-x_i\|_2=
\sqrt{\sum_{j=1}^{n}(x_j-x_{i,j})^2},
$$

em que:

-   $x$ é a amostra de teste;
-   $x_i$ é uma amostra do conjunto de treinamento;
-   $n$ é o número de características;
-   $x_j$ e $x_{i,j}$ representam a $j$-ésima característica.

Na implementação deste capítulo, $x$ corresponde a uma linha de `X_test`
e $x_i$ a uma linha de `X_train`. O método `predict()` calcula
automaticamente a distância entre $x$ e todas as amostras de
treinamento.

No exemplo da @tbl-knn-frutas:

$$
d(\text{teste}, \text{Fruta 1}) \approx 0{,}028,\qquad
d(\text{teste}, \text{Fruta 2}) \approx 0{,}860,\qquad
d(\text{teste}, \text{Fruta 3}) \approx 0{,}094.
$$

Como as menores distâncias correspondem às Frutas 1 e 3, essas amostras
serão utilizadas na etapa de decisão.

## Regra de Decisão

Após ordenar as distâncias, o algoritmo seleciona os $k$ vizinhos mais
próximos. Seja $N_k(x)$ esse conjunto. A classe predita é dada por

$$
\hat y=\operatorname{moda}\{\,y_i:x_i\in N_k(x)\,\},
$$

em que $y_i$ é o rótulo da amostra $x_i$ e $\hat y$ é a classe atribuída
à amostra de teste.

No exemplo, para $k=3$, os vizinhos são Fruta 1 (Maçã), Fruta 3 (Maçã) e
Fruta 2 (Banana). Como **Maçã** recebe dois votos, essa é a classe
predita.

::: callout-tip
### Classe `KNeighborsClassifier`

Neste capítulo, o algoritmo é implementado com a classe
`KNeighborsClassifier`, da biblioteca `scikit-learn`:

``` python
from sklearn.neighbors import KNeighborsClassifier

knn = KNeighborsClassifier(n_neighbors=3)
knn.fit(X_train, y_train)

y_pred = knn.predict(X_test)
```

em que:

-   `KNeighborsClassifier(n_neighbors=3)`: define o valor de $k$;
-   `fit(X_train, y_train)`: armazena as amostras de treinamento
    (`X_train`) e seus rótulos (`y_train`);
-   `predict(X_test)`: retorna as classes preditas para as amostras de
    `X_test`.

Internamente, `predict()` executa as etapas descritas anteriormente:
calcula as distâncias, identifica os $k$ vizinhos mais próximos e
determina a classe por votação majoritária.
:::

A @fig-07-knn-passo-passo ilustra esse procedimento em um conjunto
bidimensional. A figura destaca os vizinhos utilizados na classificação,
enquanto o console apresenta as etapas do algoritmo: cálculo das
distâncias, ordenação, seleção dos vizinhos, votação e predição da
classe.
