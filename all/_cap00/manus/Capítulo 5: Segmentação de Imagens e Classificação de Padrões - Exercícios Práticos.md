## Capítulo 5: Segmentação de Imagens e Classificação de Padrões - Exercícios Práticos

Estes exercícios abordam as principais técnicas de segmentação de imagens e introduzem conceitos de classificação de padrões, essenciais para a análise e interpretação de cenas em Visão Computacional.

### Exercício 5.1: Segmentação por Limiarização e Detecção de Bordas

**Objetivo:** Aplicar e comparar diferentes métodos de limiarização e detecção de bordas para segmentar objetos em imagens.

1.  **Limiarização Global:** Implemente a limiarização global (manual e Otsu) em uma imagem em tons de cinza. Avalie a eficácia para diferentes tipos de imagens.
2.  **Limiarização Adaptativa:** Implemente a limiarização adaptativa (média e Gaussiana) e compare com a limiarização global, especialmente em imagens com iluminação não uniforme.
3.  **Detecção de Bordas para Segmentação:** Utilize operadores de borda (Sobel, Canny) para identificar contornos de objetos. Discuta como as bordas podem ser usadas como base para a segmentação.
4.  **Segmentação Baseada em Regiões (Crescimento de Regiões - Opcional):** Implemente um algoritmo simples de crescimento de regiões, onde a segmentação começa a partir de um ponto semente e se expande para pixels vizinhos com propriedades semelhantes.

**Dados:** Utilize imagens com objetos bem definidos e fundos variados, incluindo imagens com variações de iluminação.

### Exercício 5.2: Segmentação por Clusterização (K-Means)

**Objetivo:** Aplicar o algoritmo K-Means para segmentar imagens com base em características de pixel (cor, intensidade).

1.  **Segmentação por Cor:** Aplique o K-Means para segmentar uma imagem colorida em `k` clusters de cores. Visualize os resultados para diferentes valores de `k`.
2.  **Segmentação por Intensidade:** Aplique o K-Means para segmentar uma imagem em tons de cinza em `k` clusters de intensidade. Compare com os métodos de limiarização.
3.  **Análise de Textura (Opcional):** Combine K-Means com características de textura (ex: GLCM - Gray-Level Co-occurrence Matrix) para segmentar regiões com texturas distintas.

**Dados:** Utilize imagens coloridas com diferentes regiões de cor e imagens em tons de cinza com variações de intensidade.

### Exercício 5.3: Segmentação por Watershed

**Objetivo:** Utilizar o algoritmo Watershed para segmentar objetos conectados ou sobrepostos.

1.  **Preparação da Imagem:** Prepare uma imagem (ex: gradiente morfológico) para ser usada como entrada para o algoritmo Watershed.
2.  **Marcadores:** Crie marcadores para o fundo e para os objetos de interesse. Experimente diferentes métodos para gerar esses marcadores (ex: limiarização e operações morfológicas).
3.  **Aplicação do Watershed:** Aplique o algoritmo Watershed e visualize os resultados da segmentação. Discuta a importância dos marcadores para evitar super-segmentação ou sub-segmentação.

**Dados:** Utilize imagens com objetos sobrepostos ou conectados, como células em uma lâmina de microscópio ou grãos de arroz.

### Exercício 5.4: Introdução à Classificação de Padrões

**Objetivo:** Introduzir conceitos básicos de classificação de padrões utilizando características extraídas de imagens.

1.  **Extração de Características:** Para um conjunto de objetos segmentados (ex: formas geométricas simples), extraia características como área, perímetro, circularidade, razão de aspecto.
2.  **Classificador Simples:** Implemente um classificador simples (ex: k-NN - k-Nearest Neighbors ou SVM - Support Vector Machine) para classificar os objetos com base nas características extraídas.
3.  **Avaliação:** Avalie o desempenho do classificador usando métricas como acurácia, precisão e recall.

**Dados:** Crie um pequeno dataset de imagens com diferentes formas geométricas (círculos, quadrados, triângulos) e use-o para treinar e testar o classificador.
