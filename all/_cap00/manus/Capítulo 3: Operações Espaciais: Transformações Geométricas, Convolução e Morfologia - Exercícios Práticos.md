## Capítulo 3: Operações Espaciais: Transformações Geométricas, Convolução e Morfologia - Exercícios Práticos

Estes exercícios visam consolidar o entendimento dos conceitos de transformações geométricas, convolução e morfologia matemática em imagens digitais, com foco na implementação prática utilizando Python e bibliotecas de processamento de imagens.

### Exercício 3.1: Transformações Geométricas Interativas

**Objetivo:** Implementar e visualizar diferentes transformações geométricas em uma imagem, permitindo a interação do usuário com os parâmetros.

1.  **Translação:** Crie uma função que translade uma imagem em `(dx, dy)` pixels. Permita que o usuário insira `dx` e `dy`.
2.  **Rotação:** Implemente uma função para rotacionar uma imagem em um ângulo `theta` (em graus) em torno de um ponto central. O usuário deve poder definir `theta`.
3.  **Escala:** Desenvolva uma função para redimensionar uma imagem por um fator de escala `sx` e `sy`. Permita que o usuário ajuste esses fatores.
4.  **Cisalhamento (Shear):** Crie uma função que aplique cisalhamento horizontal e vertical à imagem. O usuário deve fornecer os fatores de cisalhamento.
5.  **Combinação:** Crie uma interface simples (pode ser via `matplotlib` ou `OpenCV` com sliders/trackbars) onde o usuário possa aplicar sequencialmente translação, rotação e escala a uma imagem, observando o efeito combinado.

**Dados:** Utilize uma imagem colorida de sua escolha (sem restrições de copyright, como as do [Pexels](https://www.pexels.com/) ou [Unsplash](https://unsplash.com/)).

### Exercício 3.2: Detecção de Bordas com Convolução

**Objetivo:** Aplicar diferentes kernels de convolução para detecção de bordas e comparar os resultados.

1.  **Filtros Pré-definidos:** Implemente os filtros de Sobel (horizontal e vertical), Prewitt e Laplace. Aplique-os a uma imagem em tons de cinza.
2.  **Comparação:** Exiba a imagem original e os resultados de cada filtro lado a lado. Discuta as diferenças na detecção de bordas e a sensibilidade ao ruído de cada filtro.
3.  **Kernel Personalizado:** Permita que o usuário defina um kernel 3x3 personalizado e aplique-o à imagem. Explore o efeito de diferentes kernels (ex: suavização, realce).

**Dados:** Utilize uma imagem em tons de cinza com detalhes e texturas variadas (ex: uma foto de paisagem ou arquitetura).

### Exercício 3.3: Operações Morfológicas para Análise de Formas

**Objetivo:** Utilizar operações morfológicas para extrair informações sobre formas e estruturas em imagens binárias.

1.  **Binarização:** Comece com uma imagem em tons de cinza e aplique um limiar para convertê-la em uma imagem binária.
2.  **Erosão e Dilatação:** Aplique operações de erosão e dilatação com diferentes elementos estruturantes (ex: quadrado 3x3, cruz 5x5). Observe como essas operações afetam o tamanho e a forma dos objetos.
3.  **Abertura e Fechamento:** Implemente as operações de abertura e fechamento. Explique como elas podem ser usadas para remover ruído e preencher pequenos buracos, respectivamente.
4.  **Contagem de Objetos:** Utilize uma sequência de operações morfológicas (ex: abertura seguida de dilatação) para limpar uma imagem binária e, em seguida, conte o número de objetos distintos presentes na imagem.

**Dados:** Utilize uma imagem com objetos bem definidos e alguns ruídos (ex: uma imagem de células, letras ou formas geométricas simples).
