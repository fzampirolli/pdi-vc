## Capítulo 4: Filtragem no Domínio da Frequência e Restauração de Imagens - Exercícios Práticos

Estes exercícios abordam a aplicação da Transformada de Fourier e técnicas de filtragem no domínio da frequência, bem como métodos de restauração de imagens para lidar com ruídos e degradações.

### Exercício 4.1: Análise e Filtragem no Domínio da Frequência

**Objetivo:** Compreender a Transformada de Fourier Discreta (TFD) e sua aplicação na análise e filtragem de imagens.

1.  **TFD e Espectro de Magnitude:** Calcule a TFD de uma imagem em tons de cinza e visualize seu espectro de magnitude. Explique o que as diferentes regiões do espectro representam (baixas e altas frequências).
2.  **Filtros Passa-Baixa:** Implemente um filtro passa-baixa ideal, Butterworth e Gaussiano no domínio da frequência. Aplique-os à imagem e observe o efeito de suavização e remoção de detalhes.
3.  **Filtros Passa-Alta:** Implemente um filtro passa-alta ideal, Butterworth e Gaussiano no domínio da frequência. Aplique-os à imagem e observe o efeito de realce de bordas e detalhes.
4.  **Filtro Notch:** Crie um filtro notch para remover ruídos periódicos (ex: ruído de linha) de uma imagem. Simule a adição de um ruído periódico à imagem antes de aplicar o filtro.

**Dados:** Utilize uma imagem em tons de cinza com texturas variadas e, para o filtro notch, uma imagem com ruído periódico simulado.

### Exercício 4.2: Restauração de Imagens com Ruído

**Objetivo:** Aplicar e comparar diferentes técnicas de restauração para remover ruídos de imagens.

1.  **Adição de Ruído:** Adicione diferentes tipos de ruído (Gaussiano, Sal e Pimenta) a uma imagem original.
2.  **Filtros Espaciais para Ruído:** Aplique filtros espaciais como o filtro da média, mediana e gaussiano para remover os ruídos adicionados. Compare a eficácia de cada filtro para diferentes tipos de ruído.
3.  **Filtro Adaptativo:** Implemente um filtro adaptativo (ex: filtro da média adaptativa ou filtro da mediana adaptativa) e compare seu desempenho com os filtros não adaptativos.
4.  **Restauração Cega (Blind Deconvolution - Opcional):** Para alunos de pós-graduação, explore a aplicação de técnicas de restauração cega para estimar a função de espalhamento de ponto (PSF) e restaurar imagens borradas sem conhecimento prévio do borrão.

**Dados:** Utilize uma imagem colorida ou em tons de cinza, e adicione ruídos sintéticos para testar os algoritmos de restauração.

### Exercício 4.3: Restauração de Imagens Borradas (Deblurring)

**Objetivo:** Aplicar técnicas de restauração para remover borrões de movimento ou desfoque de imagens.

1.  **Simulação de Borrão:** Simule um borrão de movimento em uma imagem original, criando uma função de espalhamento de ponto (PSF) apropriada.
2.  **Filtro Inverso:** Implemente o filtro inverso para tentar remover o borrão. Discuta as limitações e a sensibilidade ao ruído deste método.
3.  **Filtro de Wiener:** Implemente o filtro de Wiener para restaurar a imagem borrada. Compare os resultados com o filtro inverso e discuta as vantagens do filtro de Wiener.

**Dados:** Utilize uma imagem com detalhes finos e aplique um borrão de movimento simulado.
