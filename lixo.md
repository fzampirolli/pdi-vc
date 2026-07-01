## Compressão de Imagens

Enquanto as *wavelets* estabelecem a fundação teórica do padrão JPEG 2000, o padrão JPEG tradicional baseia-se na **Transformada Discreta de Cossenos (DCT, *Discrete Cosine Transform*)**. Apesar das diferenças estruturais, ambas as abordagens compartilham o mesmo princípio fundamental: compactar a energia da imagem em um número reduzido de coeficientes e descartar as componentes de menor relevância com impacto visual mínimo.

O objetivo central da compressão é reduzir o volume de dados necessário para o armazenamento ou transmissão de uma imagem. Esse processo é viabilizado pela identificação e eliminação de **redundâncias** estruturais e perceptuais.

### Taxonomia das Redundâncias

O desenvolvimento de algoritmos de compressão fundamenta-se na identificação e eliminação de três categorias principais de redundância, sintetizadas na @tbl-05-redundancias.

| Tipo | Definição | Abordagem de Exploração |
|:---|:---|:---|
| **Espacial (interpixel)** | Alta correlação e dependência estatística entre pixels vizinhos. | DCT, DWT e codificação preditiva. |
| **Espectral (intercanal)** | Correlação estatística entre os canais de cor de uma mesma imagem. | Transformações de espaço de cor (ex: RGB para $YC_bC_r$). |
| **Psicovisual** | Insensibilidade do sistema visual humano (SVH) a variações de alta frequência e baixo contraste. | Processos de quantização seletiva de coeficientes. |

: Categorias de redundância em imagens digitais e seus respectivos mecanismos de exploração. {#tbl-05-redundancias}

A depender da preservação da informação original após o processo de decodificação, os métodos de compressão dividem-se em duas classes fundamentais:

* **Sem perda (*lossless*):** Garante uma reconstrução bit a bit idêntica à imagem original. É empregada em cenários onde a integridade dos dados é estritamente crítica, como em imagens médicas, diagnósticos por imagem e armazenamento de documentos textuais.
* **Com perda (*lossy*):** Admite a introdução de uma distorção controlada no sinal em troca de taxas de compressão substancialmente mais elevadas. É a abordagem padrão para fotografias de consumo e *streaming* de vídeo, ecossistemas nos quais o SVH tolera pequenas atenuações de alta frequência sem percepção de degradação da qualidade visual.

### Transformada de Cossenos Discreta (DCT-II 2D)

A **Transformada de Cossenos Discreta** (DCT) constitui a operação central do padrão JPEG. Diferentemente da DFT, que utiliza uma base complexa, a DCT baseia-se em funções trigonométricas puramente reais. Para um bloco de imagem $f(x,y)$ de dimensões $N \times N$, a **DCT-II 2D** mapeia o sinal espacial para o domínio das frequências espaciais, gerando a matriz de coeficientes $C(u,v)$ por meio de:

$$
C(u,v) = \alpha(u)\,\alpha(v) \sum_{x=0 Barth}^{N-1}\sum_{y=0}^{N-1} f(x,y)\,
\cos\!\left[\frac{\pi(2x+1)u}{2N}\right]
\cos\!\left[\frac{\pi(2y+1)v}{2N}\right]
$$ {#eq-05-dct}

onde os fatores de normalização ortogonal são dados por $\alpha(0) = \sqrt{1/N}$ e $\alpha(k) = \sqrt{2/N}$ para $k > 0$. 

Cada coeficiente $C(u,v)$ quantifica a contribuição — ou "peso" — de uma frequência espacial específica dentro daquele bloco. O termo $C(0,0)$ é denominado **componente DC** e representa a intensidade média do bloco (frequência nula). Os demais coeficientes, chamados de **componentes AC**, correspondem às frequências espaciais progressivamente maiores.

### As Funções de Base da DCT

Sob uma perspectiva geométrica, a @eq-05-dct realiza a projeção do bloco de pixels sobre um conjunto de funções ortogonais. Para o caso padrão do JPEG ($N=8$), o bloco espacial é decomposto em uma combinação linear de **64 funções de base** bidimensionais, denotadas por $B_{u,v}(x,y)$ e geradas pelo produto de funções cossenoidais:

$$B_{u,v}(x,y) = \cos\left[ \frac{\pi (2x+1)u}{16} \right] \cos\left[ \frac{\pi (2y+1)v}{16} \right]$$

Dessa forma, a operação inversa pode ser interpretada como a reconstrução exata do bloco original por meio da soma ponderada dessas 64 matrizes de base, onde cada coeficiente $C(u,v)$ atua como o peso analítico de sua respectiva componente harmônica. 

A **frequência espacial** indicada pelos índices $(u,v)$ determina o número de ciclos de oscilação ao longo das dimensões horizontais e verticais do bloco. Como ilustrado na @fig-05-dct-basis — cujo código isola cada base aplicando a transformação inversa sobre impulsos unitários —, essas 64 funções são organizadas em uma matriz $8 \times 8$. O canto superior esquerdo ($u=0, v=0$) exibe o padrão uniforme de frequência nula (DC), enquanto o avanço para a direita (eixo $u$) ou para baixo (eixo $v$) mapeia variações harmônicas progressivamente maiores, representando transições rápidas, bordas e texturas nas orientações horizontais, verticais e diagonais.

::: {.callout-note}
### DCT vs DFT: Vantagem da Compactação de Energia {.unnumbered}
Tanto a DCT quanto a DFT mapeiam um bloco $N \times N$ espacial em uma matriz de coeficientes de mesma dimensão. Contudo, para imagens naturais, a DCT apresenta maior eficiência na **compactação de energia** nas baixas frequências. Isso ocorre porque a DCT assume implicitamente uma simetria par do sinal nas fronteiras do bloco, o que equivale a uma extensão periódica contínua, minimizando o efeito de espalhamento espectral (*ringing*). Como consequência, a maioria dos coeficientes AC decai rapidamente para valores próximos de zero, otimizando o pipeline de compressão sem introduzir degradação visual perceptível.
:::

### Concentração de Energia e Reconstrução Progressiva

Antes da aplicação da DCT, os pixels do bloco de intensidade são rotineiramente transladados (subtraindo-se $128$ para imagens de 8 bits) a fim de centralizar o sinal em torno de zero, eliminando componentes contínuas desnecessárias. Ao computar a DCT sobre o bloco resultante, a propriedade de **compactação de energia** torna-se evidente: a quase totalidade da variância e da informação da imagem original concentra-se no coeficiente DC ($C(0,0)$) e nos primeiros harmônicos AC de baixa frequência.

A @fig-05-dct-bloco demonstra esse fenômeno por meio de uma reconstrução progressiva por truncamento abrupto. Em vez de utilizar todos os 64 coeficientes, o algoritmo preserva apenas os $k$ primeiros componentes — selecionados com base em uma varredura que prioriza as baixas frequências espaciais — e anula os demais. 

A síntese inversa (**IDCT**) realizada com apenas uma fração dos coeficientes (como 15% ou 30%) já é capaz de recuperar as estruturas e a iluminação macro do bloco original de pixels. À medida que harmônicos de frequências mais altas são progressivamente reincorporados, os detalhes finos e as transições rápidas são restaurados. Esse comportamento valida o princípio da compressão perceptual: as altas frequências descartadas possuem pouca energia e sua ausência, em condições normais, gera um impacto visual secundário na percepção do observador.

### O Pipeline de Compressão JPEG

O padrão JPEG opera dividindo a imagem em blocos disjuntos de $8 \times 8$ pixels, processados por meio de uma sequência de transformações espaciais, perceptuais e estatísticas. O pipeline completo de codificação é estruturado em seis etapas principais:

$$
\text{RGB} \xrightarrow{\text{(1) } YC_bC_r} \xrightarrow{\text{(2) Subamostragem}} \xrightarrow{\text{(3) Blocos } 8 \times 8} \xrightarrow{\text{(4) DCT}} \xrightarrow{\text{(5) Quantização}} \xrightarrow{\text{(6) Codificação Entrópica}}
$$

A @tbl-05-pipeline-jpeg detalha a função analítica e o fundamento perceptual que justifica cada uma dessas etapas.

| Etapa | Operação | Fundamento Perceptual e Estatístico |
|:---:|:---|:---|
| **1** | Conversão $RGB \rightarrow YC_bC_r$ | Separa a luminância ($Y$) da crominância ($C_b, C_r$). O sistema visual humano (SVH) apresenta maior sensibilidade a variações de brilho do que de cor. |
| **2** | Subamostragem de crominância (ex: 4:2:0) | Reduz a resolução espacial dos canais de cor pela metade, descartando dados redundantes com impacto visual desprezível. |
| **3–4** | Centralização e aplicação da DCT $8 \times 8$ | Translada os pixels para o intervalo $[-128, 127]$ e compacta a energia espectral do bloco nos coeficientes de baixa frequência. |
| **5** | Quantização linear seletiva | Divide cada coeficiente $C(u,v)$ pelo elemento correspondente da matriz $Q(u,v)$, aplicando arredondamento inteiro. Constitui a principal fonte de compressão com perda. |
| **6** | Varredura em ziguezague e codificação | Ordena os coeficientes quantizados para maximizar sequências nulas consecutivas, otimizando a codificação por comprimento de corrida (RLE) e a codificação de Huffman. |

: Etapas do pipeline de compressão JPEG e seus respectivos fundamentos de projeto. {#tbl-05-pipeline-jpeg}

A **matriz de quantização** $Q(u,v)$ é o mecanismo central de controle do compromisso entre taxa de compressão e qualidade visual. No algoritmo prático da @fig-05-jpeg-pipeline, o fator de qualidade estipulado pelo usuário (escala de 1 a 100) é convertido em um escalar que parametriza a severidade da matriz $Q$. Valores reduzidos de qualidade expandem os divisores de $Q(u,v)$, forçando o truncamento em massa dos coeficientes AC para zero. Quando essa eliminação é excessiva, a descontinuidade nas fronteiras dos blocos adjacentes não é atenuada na reconstrução, gerando os denominados **artefatos de bloco** (*blocking artifacts*).

#### A Lógica da Varredura em Ziguezague {.unnumbered}

A eficiência do codificador entrópico subsequente à quantização depende diretamente da ordenação dos dados. Como a DCT concentra a energia vital no vértice superior esquerdo da matriz (baixas frequências) e empurra os coeficientes nulos para as extremidades opostas, a leitura linear por linhas ou colunas fragmentaria as sequências de zeros. 

A ordenação em ziguezague soluciona essa limitação ao percorrer a matriz diagonalmente em ordem crescent de frequência espacial. Esse mapeamento agrupa os coeficientes significativos no início do vetor e concentra os coeficientes nulos em uma única sequência contínua ao final do arranjo, permitindo que o algoritmo RLE codifique grandes blocos de dados de forma compacta e eficiente.

## Comparação de Formatos de Imagem

A escolha de um formato de armazenamento digital impacta diretamente o compromisso entre qualidade visual, tamanho de arquivo e custo computacional de decodificação. Os três formatos de maior relevância para arquiteturas web e sistemas de computação visual são o JPEG, o PNG e o WebP.

### Características dos Formatos

A @tbl-05-formatos sintetiza as propriedades estruturais dos principais formatos de imagem rasterizados.

| Característica | JPEG | PNG | WebP |
|:---|:---:|:---:|:---:|
| **Compressão** | Com perda | Sem perda | Com e sem perda. |
| **Transparência (canal alfa)** | Não | Sim | Sim. |
| **Suporte a animação** | Não | Limitado (APNG) | Sim. |
| **Algoritmo base** | DCT + Huffman | DEFLATE (LZ77 + Huffman) | VP8 / VP8L. |
| **Melhor para** | Fotografia | Gráficos, texto e ícones | Uso universal em ambiente Web. |
| **Pior para** | Texto e bordas nítidas | Imagens fotográficas complexas | Compatibilidade legada. |

: Comparação estrutural entre os principais formatos de imagem rasterizados. {#tbl-05-formatos}

### Métricas de Avaliação de Qualidade

Duas métricas objetivas são amplamente adotadas para quantificar a distorção introduzida por processos de compressão:

**Pico da Relação Sinal-Ruído (PSNR, *Peak Signal-to-Noise Ratio*):**
$$
\text{PSNR} = 10\,\log_{10}\!\left(\frac{L^2}{\text{MSE}}\right) \quad [\text{dB}]
$$ {#eq-05-psnr}

onde $L = 255$ para imagens quantizadas em 8 bits e $\text{MSE}$ representa o **Erro Quadrático Médio** (*Mean Squared Error*). Valores de PSNR acima de 40 dB indicam excelente fidelidade; entre 30 dB e 40 dB representam boa qualidade; e valores inferiores a 30 dB correspondem a degradações visuais facilmente perceptíveis.

**Índice de Similaridade Estrutural (SSIM, *Structural Similarity Index*):**
$$
\text{SSIM}(f,g) = \frac{(2\mu_f\mu_g + c_1)(2\sigma_{fg} + c_2)}{(\mu_f^2+\mu_g^2+c_1)(\sigma_f^2+\sigma_g^2+c_2)}
$$ {#eq-05-ssim}

O SSIM avalia janelas locais da imagem com base em três componentes complementares: **luminância** ($\mu_f, \mu_g$), **contraste** ($\sigma_f, \sigma_g$) e **estrutura** ($\sigma_{fg}$), ponderados por constantes de estabilidade $c_1$ e $c_2$. O índice varia no intervalo $[-1, 1]$, onde a unidade representa a identidade perfeita. Ao contrário do PSNR, o SSIM considera a organização espacial dos erros, alinhando-se à percepção do sistema visual humano (SVH).

::: {.callout-note}
### PSNR vs SSIM: Aplicação de Métricas Perceptuais {.unnumbered}
O PSNR possui formulação matemática simples e baixo custo computacional, contudo, tende a superestimar a qualidade em imagens com distorções localizadas ou subestimá-la em variações globais de brilho toleradas pelo observador. O SSIM modela com maior fidelidade a percepção biológica, mas exige maior esforço de processamento. Para análises rigorosas de codificadores, recomenda-se reportar ambas as métricas estatísticas em caráter complementar.
:::

### Inspeção Visual: Natureza dos Artefatos de Compressão

A natureza matemática do codificador dita o tipo de degradação introduzida em taxas de bits reduzidas. Conforme ilustrado na @fig-05-zoom-artefatos, a compressão agressiva via DCT no padrão JPEG segmenta a imagem em malhas rígidas, gerando os **artefatos de bloco** (*blocking artifacts*). Em contrapartida, algoritmos baseados em codificação preditiva ou representações submetidas a transformadas espaciais avançadas (como o WebP e o JPEG 2000) eliminam as descontinuidades de bloco, mas introduzem perda de textura fina e borramentos característicos ao redor de bordas de alto contraste.

### Avaliação Quantitativa e Espacial da Compressão

A validação dos algoritmos de compressão com perda exige uma análise que correlacione o custo de armazenamento à fidelidade do sinal reconstruído. Essa avaliação é realizada de forma complementar através de curvas de desempenho global e pelo mapeamento local das distorções induzidas pelos codificadores.

#### Curvas de Taxa-Distorção

A @fig-05-formatos-comparacao apresenta a avaliação empírica do pipeline JPEG e WebP por meio de **curvas de taxa-distorção**, que monitoram o ganho de compressão (tamanho do arquivo em KB) em função do PSNR. O formato PNG atua como linha de base ideal ($\text{PSNR} = \infty$), pois sua natureza *lossless* impede qualquer degradação, embora demande um volume de dados substancialmente maior. 

A análise das curvas demonstra a superioridade e a eficiência do padrão WebP sobre o JPEG tradicional: para atingir um mesmo patamar de fidelidade matemática (como a faixa de excelente qualidade, onde $\text{PSNR} > 40\text{ dB}$), o codificador WebP gera arquivos significativamente menores. Esse comportamento traduz o impacto prático da evolução dos algoritmos na otimização de sistemas de transmissão e armazenamento digital.

#### Mapeamento Espacial de Erros e Correlação Perceptual

Embora o PSNR ofereça um indicativo numérico rápido, métricas globais falham em discriminar como a perda de informação se distribui geometricamente sobre a imagem. A @fig-05-ssim-artefatos soluciona essa limitação ao associar as reconstruções em diferentes qualidades aos seus respectivos mapas de erro absoluto e ao SSIM.

Os mapas residuais — obtidos pela diferença absoluta normalizada entre a imagem original e a comprimida — revelam a assinatura espacial intrínseca de cada arquitetura de codificação:

* **Em altas qualidades ($Q=95$ a $Q=75$):** As distorções concentram-se predominantemente ao redor de transições abruptas de intensidade (bordas), fruto do espelhamento espectral decorrente do descarte de altas frequências. O índice SSIM permanece próximo à unidade, atestando a integridade das estruturas originais.
* **Em qualidades agressivas ($Q=50$ a $Q=25$):** O erro assume uma estrutura de malha ortogonal regularizada. Esse padrão geométrico evidencia o surgimento dos **artefatos de bloco** (*blocking artifacts*), indicando que a quantização severa corrompeu a correlação espacial entre blocos adjacentes de $8 \times 8$ pixels. 

O SSIM captura essa degradação morfológica de forma muito mais sensível que o PSNR, penalizando o escore final à medida que a organização estrutural e as texturas finas — às quais o sistema visual humano é altamente responsivo — são eliminadas pelo codificador.
