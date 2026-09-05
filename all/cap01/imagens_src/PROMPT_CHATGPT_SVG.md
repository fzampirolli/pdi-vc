# Prompt para gerar SVG de diagrama (colar no ChatGPT, com a imagem em anexo)

Preciso que você recrie o diagrama em anexo como um arquivo **SVG editável**,
para uso num livro didático (versões em português, inglês e francês geradas
a partir do mesmo SVG, trocando só o texto).

## Requisitos técnicos (importantes — o SVG será renderizado com `rsvg-convert`,
não só em navegador, e depois editado programaticamente):

1. **Não use `<feDropShadow>`** — não é suportado pelo `rsvg-convert` (librsvg)
   e o elemento inteiro some. Se quiser sombra, monte manualmente com
   `<feGaussianBlur in="SourceAlpha">` + `<feOffset>` + `<feFlood>` +
   `<feComposite operator="in">` + `<feMerge>`.
2. **Cada texto deve ser um elemento `<text>` separado com `id` único e
   estável** (ex.: `id="text_titulo"`, `id="text_bullet1"`) — não agrupe
   várias frases num único `<text>` com múltiplos `<tspan>`. Isso é
   essencial porque eu vou gerar as versões en/fr trocando o conteúdo de
   cada `id`, sem tocar em posição/estilo.
3. **Não conte com preservação de espaço em branco** (`xml:space`) para
   separar rótulo de valor (ex.: "Rótulo: valor"). Em vez de
   `<tspan>Rótulo:</tspan><tspan> valor</tspan>`, use dois `<text>`
   independentes com `x` explícito e um **espaço generoso entre eles**
   (calcule a largura aproximada do texto do rótulo — não deixe o `x` do
   segundo texto colado no fim do primeiro). Prefira folga demais a
   folga de menos.
4. **Nenhuma forma pode sobrepor outra.** Confira visualmente antes de
   finalizar — elementos centrais (círculos/elipses grandes) não podem
   invadir a área de elementos vizinhos (ovais, caixas, textos).
5. Fontes: `Arial, Helvetica, sans-serif` (sem depender de fonte
   específica não-padrão).
6. `viewBox` com origem em `0 0`, dimensões parecidas com a imagem de
   referência.
7. Cores: siga a paleta da imagem de referência (mantenha consistência:
   azul para "Visão Computacional"/conceitos de interpretação, verde
   para "Processamento de Imagens"/preparação — se aplicável ao diagrama).
8. Pode usar gradientes (`<linearGradient>`) e um filtro de blur simples
   (`<feGaussianBlur>` sozinho funciona bem, sem drop-shadow) para halos
   suaves — isso é suportado.
9. Entregue o SVG completo em um bloco de código, pronto pra salvar como
   arquivo `.svg`.

## O que recriar

[DESCREVER AQUI o conteúdo do diagrama em anexo: título, textos, estrutura
visual (caixas, setas, ícones), e o que cada elemento representa — quanto
mais detalhado, melhor. Anexar a imagem de referência junto.]

## Referência de qualidade

Adoto o mesmo padrão de outro diagrama já validado do mesmo livro — pode
gerar num nível de polimento visual semelhante (gradientes suaves,
ícones de linha simples, caixas com cantos arredondados, callouts
tracejados com "rabicho" apontando pro elemento relacionado).
