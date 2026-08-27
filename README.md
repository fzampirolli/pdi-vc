# PDI+VC — Processamento Digital de Imagens e Visão Computacional

**Material didático interativo para cursos de graduação e pós-graduação**
> Escreva **uma vez** em formato Quarto (Markdown+Python). O pipeline traduz o resto.

🚧 **Em construção!**
Os 9 capítulos estão ativos no build e foram aplicados em turmas de PDI na UFABC. O livro é publicado em 6 combos: **Python** × **pt/en/fr** (livro completo) e **C++** × **pt/en/fr** (por ora só o Capítulo 1 — ver "Execução real de código em C++").

[![Livro Online](https://img.shields.io/badge/Livro-Online-blue?logo=github)](https://fzampirolli.github.io/pdi-vc)
[![Abrir no Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/fzampirolli/pdi-vc/blob/master/notebooks_alunos/py.pt/cap01/cap01_aluno.ipynb)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20784606.svg)](https://doi.org/10.5281/zenodo.20784606)
[![Licença](https://img.shields.io/badge/Licença-CC--BY--NC--SA--4.0-green)](LICENSE)

---

## Para o Aluno

### Onde encontrar o material

| Formato | Link |
|---------|------|
| **HTML** | [fzampirolli.github.io/pdi-vc](https://fzampirolli.github.io/pdi-vc/) — navegação interativa, simuladores |
| **PDF** | Disponível na página HTML (botão *Download PDF*) — para impressão e leitura offline |
| **Notebooks Jupyter/Colab** | Uma árvore por combo em `notebooks_alunos/<combo>/capXX/` — `<combo>` ∈ {`py.pt`, `py.en`, `py.fr`, `cpp.pt`, `cpp.en`, `cpp.fr`}. Prontos para execução, sem dependências do Quarto (C++: só `cap01`). |

### Como usar os notebooks

1. Acesse [Google Colab](https://colab.research.google.com/) ou instale o [Jupyter](https://jupyter.org/)
2. Abra o notebook `notebooks_alunos/<combo>/capXX/capXX_aluno.ipynb` — pelo botão **Executar Colab** no início de cada capítulo (aponta para o combo correspondente) ou direto pelo GitHub
3. Execute as células com **Shift+Enter** ou pelo botão ▶️
4. Os notebooks de EPs (`capXX.EPs_aluno.ipynb`) contêm os exercícios práticos com validação automática via `TestSuite`

### Estrutura dos notebooks de EP

Cada EP segue o padrão:

```
EP01_01 — Descrição do problema
  ├── Enunciado
  ├── Simulador interativo (HTML — apenas na versão web)
  ├── Código-template para completar
  └── TestSuite("EP01_01.py").run()  ← valida sua solução
```

---

## Para o Professor / Desenvolvedor

### Princípio fundamental

O notebook-fonte em `all/capXX/capXX.ipynb` é **canônico**: Python puro, Português puro.
O pipeline gera automaticamente versões em outras linguagens (C++, Java…) e idiomas (Inglês, Francês…)
via API Anthropic. As traduções ficam em cache (`.cache/`) e só são rechamadas quando o conteúdo muda.

### Estrutura do projeto

```
pdi-vc/
│
├── all/                          ← ✏️ FONTES — editar APENAS aqui
│   ├── _cap00/                   ← propostas, prompts e rascunhos de capítulos
│   └── capXX/                    (do cap01 ao cap09)
│       ├── capXX.ipynb           ← conteúdo principal (Teoria)
│       ├── capXX.EPs.ipynb       ← enunciados e códigos dos Exercícios Práticos
│       ├── imagens/              ← badges, figuras estáticas e setups dos capítulos
│       └── casos/                ← arquivos de teste (.cases) para validação dos EPs
│
├── gen/                          ← 🤖 GERADO — não editar manualmente
│   ├── py.pt/                    ← notebooks processados em Python/Português
│   │   └── capXX/                ← notebooks finais e links de imagens
│   └── quarto/                   ← ambiente de compilação do Quarto
│       └── py.pt/                ← estrutura organizada com _quarto.yml para o build
│           └── book/             ← saída final da renderização local (PDF e HTMLs)
│
├── docs/                         ← 🌐 DEPLOY — pasta para publicação estática (GitHub Pages)
│   ├── index.html                ← página inicial do site do livro
│   ├── py.pt/                    ← versão web completa do livro (HTMLs, PDFs, imagens)
│   └── eps/                      ← Exercícios Práticos extraídos individualmente
│       ├── py.pt/                ← formato HTML para visualização direta
│       └── py.pt_moodle/         ← formato HTML otimizado para o Moodle
│
├── notebooks_alunos/             ← 📦 DISTRIBUIÇÃO — material limpo para os estudantes
│   └── capXX/                    
│       ├── capXX_aluno.ipynb     ← teoria com lacunas/atividades
│       ├── capXX.EPs_aluno.ipynb ← templates dos EPs para implementação
│       ├── imagens/              ← imagens necessárias para rodar localmente
│       └── casos/                ← casos de teste abertos
│
├── pipeline/                     ← ⚙️ MOTOR — scripts do pipeline de compilação
│   ├── config.py                 ← configurações gerais do projeto
│   ├── cache.py                  ← gerenciamento de cache de processamento
│   ├── notebook_processor.py     ← processador e limpador das células dos notebooks
│   ├── quarto_builder.py         ← orquestrador do build via Quarto
│   ├── index_builder.py          ← gerador automático de índices do site
│   └── translators.py            ← gerenciador de tradução e chamadas de API
│
├── includes/                     ← 🎨 ASSETS — elementos compartilhados de estilização
│   ├── preamble.tex / .html      ← preâmbulos de configuração LaTeX e HTML
│   ├── abnt.csl                  ← especificação de estilo de citação ABNT
│   ├── emoji-filter.lua          ← filtro Pandoc para conversão de emojis
│   └── prefacio.qmd              ← rascunho/metadados do prefácio
│
├── morph/                        ← 📦 BIBLIOTECA — core de PDI e testes do projeto
│   ├── morph.py / morph-large.py ← implementações de morfologia e PDI
│   └── testsuite.py              ← framework de testes automáticos para os EPs
│
├── runs/                         ← 📊 MODELOS — saídas e pesos de treinamento do YOLO
│   └── detect/                   ← matrizes de confusão, curvas F1/PR e pesos (best.pt)
│
├── utils/                        ← 🛠️ UTILITÁRIOS — scripts auxiliares de manutenção e checagem
│   ├── check-correspondencia.sh  ← checagem de integridade e correspondências
│   ├── find_label_mismatches.sh  ← validação de labels e inconsistências
│   ├── limpar.sh                 ← limpeza de temporários e artefatos
│   ├── mermaid2png.sh            ← conversão de diagramas Mermaid para PNG
│   ├── netshow_morph_candidato.py← visualização/inspeção de redes e morfologia
│   ├── rename_dirs.sh            ← renomeação em lote de diretórios
│   ├── run.sh                    ← rotinas de execução auxiliar
│   └── trocar.sh                 ← substituição em lote de termos/padrões
│
├── dev.py                        ← CLI principal de desenvolvimento
├── ep_tools.py                   ← utilitários para manipulação e extração dos EPs
├── gerar_livro.py                ← script de geração em lote do livro
├── gerar_notebooks_alunos.py     ← script que limpa e gera a pasta dos alunos
├── setup.sh                      ← 🛠️ script único de configuração do ambiente (TinyTeX + venv)
├── requirements.txt              ← dependências Python do projeto
├── run.sh / limpar.sh            ← scripts Bash para automação e limpeza de build
├── Makefile                      ← atalhos de comandos rápidos
└── references.bib                ← base de dados bibliográfica BibTeX
```

## 🌐 Documentação e Artefatos Gerados (`docs/`)

A pasta `docs/` funciona como a raiz para o *deploy* estático (como GitHub Pages [fzampirolli.github.io/pdi-vc/](https://fzampirolli.github.io/pdi-vc/)) e concentra os resultados finais do *pipeline* de compilação:

```text
docs/
├── index.html                 # Portal — cards para cada combo
├── capa_girassol1.png         # Asset visual da capa do livro
│
├── eps/                       # Exercícios Práticos (EPs) extraídos individualmente
│   ├── <combo>/               # EPs em HTML autônomo (um por combo publicado)
│   └── <combo>_moodle/        # EPs formatados para importação no Moodle
│
├── simuladores/<combo>/       # Galeria de simuladores interativos por combo
│
└── <combo>/                   # Livro renderizado — <combo> ∈ {py.pt, py.en,
    │                          #   py.fr, cpp.pt, cpp.en, cpp.fr}
    ├── book-latex/            # Fontes .tex, PDFs e figuras geradas via LaTeX
    ├── livro.<locale>.<lang>.pdf   # PDF do combo
    ├── cap01/ … cap09/        # Capítulos em HTML (cpp: só cap01)
    └── site_libs/             # Bibliotecas estáticas (Bootstrap, Quarto Search…)
```

### Metadados das células

Cada célula do notebook-fonte pode ter metadados `pdi.role`:

| `role` | Tipo | Comportamento |
|--------|------|---------------|
| `"code"` (padrão) | código | traduzido py→cpp pelo LLM |
| `"text"` (padrão) | markdown | traduzido pt→en pelo LLM |
| `"common"` | qualquer | mantido sem alteração em todas as versões |
| `"base_only"` | qualquer | aparece apenas na versão py.pt |
| `"exercise"` | markdown | traduzido como texto |

Exemplo:
```json
{
  "cell_type": "code",
  "metadata": {"pdi": {"role": "common"}},
  "source": ["$$E = mc^2$$"]
}
```

### Simuladores interativos

Células com `HTML("""...""")` são simuladores interativos. O *pipeline* trata automaticamente:

- **HTML**: exibe o simulador normalmente
- **PDF**: substitui por *screenshot* PNG gerado via `Playwright` (salvo em `all/capXX/imagens/`)

Os PNGs são gerados na primeira execução e reutilizados nas seguintes.
Para regenerar, apague o PNG correspondente em `all/capXX/imagens/`.

Padrão de *label* obrigatório para simuladores:
```python
#| label: fig-XX-nome-do-simulador
#| fig-cap: "Descrição para a legenda"
#| echo: false
from IPython.display import HTML
HTML("""...""")
```

**Evite usar a tag `<svg>` diretamente no HTML do simulador.** O *script* de *screenshot* dá um tratamento especial a blocos que já têm um `<svg>` pronto no código, o que pode gerar um PNG em branco se o seu gráfico for desenhado via JavaScript. Para gráficos e desenhos, prefira montar tudo com `<div>`s estilizados (como no simulador do EP07_05, que pode ser usado como modelo) em vez de manipular um elemento `<svg>` — assim o PNG sai correto sem ajustes extras.

#### Tradução do texto dos simuladores (en/fr/...)

A célula `HTML("""...""")` de um simulador é uma única *string* Python — o
tradutor de código normal (que só mexe em comentários, docstrings e
`print`/`title=`) nunca a toca, e mandar o bloco inteiro (HTML+CSS+JS, às
vezes >40KB) pro LLM reescrever seria arriscado: ele pode alterar `id`s
usados por `getElementById`, aspas ou *template literals*, quebrando o
simulador sem erro nenhum no build. Por isso o pipeline usa **extração
mecânica de spans seguros** (nunca uma reescrita livre) — mesmo princípio
do tradutor de comentários, aplicado ao conteúdo do simulador:

- **Traduzido automaticamente**: texto entre tags HTML, os atributos
  `title=`/`placeholder=`/`aria-label=`/`alt=`, e — dentro de
  `<script>` — só `elemento.textContent = "texto literal"` e
  `ctx.fillText("texto literal", x, y)`, sempre que o argumento for uma
  *string* literal pura (aspas simples ou duplas).
- **Nunca tocado, por construção**: `id="..."`, atributos de estilo,
  nomes de função/variável, qualquer lógica JS, e qualquer *string*
  montada por concatenação (`"a" + b`) ou *template literal*
  (`` `${x}` ``) — se o rótulo dinâmico do seu simulador precisa mudar
  conforme o idioma, monte-o com `.textContent = "texto fixo"` seguido de
  concatenação da parte variável em linha separada, em vez de uma
  *template literal* só, senão ele fica de fora da tradução.
  Comentários HTML (`<!-- ... -->`) e comentários JS (`// ...`) também
  ficam de fora — não são visíveis ao aluno.
- **Rede de segurança**: depois de colar a tradução de volta, o pipeline
  compara um "fingerprint" estrutural (conjunto de `id`s + contagem de
  `<script>`/`</script>`) antes/depois. Se divergir — ou se a chamada ao
  LLM falhar/vier em formato inesperado — a tradução é descartada e a
  célula volta pro texto original em Português, sem quebrar o build.

Implementação em `pipeline/translators.py`: `_extract_widget_spans` (localiza
as chamadas `HTML(...)`), `_extract_widget_text_spans` (extrai os spans de
dentro) e `LLMCommentTranslator.translate` (traduz em lote e faz a
validação). Nenhuma ação extra é necessária de quem escreve o simulador —
só vale ter em mente os dois pontos acima ao escrever o JavaScript, se
quiser que um rótulo dinâmico seja traduzido também.

---

### Convenções de *labels* Quarto

```markdown
# Figura (Abaixo da imagem, sem espaço)
![](imagens/exemplo.png){#fig-01-exemplo width=70%}

Citar no texto: Veja a @fig-01-exemplo.

# Equação (Na mesma linha do fechamento dos blocos $$)
$$f(x) = g(x)$$ {#eq-01-nome}

Citar no texto: Conforme a @eq-01-nome.

# Tabela (Alinhado à sintaxe de cross-reference do Quarto)
| A | B |
|---|---|

: Legenda da Tabela {#tbl-01-dados}

Citar no texto: Dados na @tbl-01-dados.

```

⚠️ **Atenção sobre *Labels* (Figuras, Tabelas e Equações):**
* **Apenas minúsculas:** O Quarto não aceita letras maiúsculas ou underscores (`_`) em IDs de referência cruzada (ex: use `{#fig-01-exemplo}`, nunca `{#fig-01-Exemplo}`).
* **Regra de nomenclatura:** `{#prefixo-CAPITULO-nome}` — inclua sempre o número do capítulo com dois dígitos (ex: `01`, `02`) para garantir a consistência no sumário e na indexação geral do livro.

🚫 **Restrição Crítica do *Pipeline* PDF (`quarto render --to pdf`):**
* O motor LaTeX/Pandoc falhará ao compilar se houver blocos de código formatados (`inline code` com crases, ex: `mm.show`) dentro de legendas (`captions`) de figuras ou tabelas.
* **Como corrigir:** Remova as crases nas legendas e use formatação de texto comum ou itálico simples (ex: *mm.show*).

---

## Comandos

### Desenvolvimento diário

```bash
# Build rápido: limpa cache LaTeX e gera PDF
./run.sh

# Watch: rebuild automático ao salvar arquivos em all/
make pdf        # PDF
make html       # HTML
make all-formats  # ambos

# Build único sem watch
make build      # HTML
make build-pdf  # PDF
make build-all  # HTML + PDF
```

### Geração de versões

```bash
# Padrão: Python × Português
python dev.py --once --langs py --locales pt --render pdf

# Múltiplas versões (os 6 combos em produção)
python dev.py --once --langs py,cpp --locales pt,en,fr --render html

# Sem chamar API (modo seco para revisar estrutura)
python dev.py --once --dry-run
```

### Extração de EPs em HTML individual

O script `extrair_eps.py` percorre todos os `gen/book/*/cap*/*.html` gerados pelo Quarto e salva cada EP em um arquivo HTML autônomo, com o mesmo visual do livro (CSS/JS herdados do original).

```bash
# Extrai todos os EPs de todas as versões disponíveis
python extrair_eps.py

# Versão específica (ex: py.pt)
python extrair_eps.py --input gen/book/py.pt

# Arquivo único
python extrair_eps.py --input gen/book/py.pt/cap01/cap01.py.pt.html

# Pasta de saída customizada
python extrair_eps.py --out-dir output/eps

# Lista EPs encontrados sem gravar arquivos
python extrair_eps.py --dry-run
```

Saída padrão: `gen/book/eps/<versao>/EPXX_YY.html`

Cada arquivo contém o bloco completo do EP: do heading `EPXX_YY` até a célula `%%writefile EPXX_YY.py` (inclusive). Via Makefile:

```bash
make eps        # extrai EPs da versão padrão (LOCALES=pt)
make eps-all    # extrai EPs de todas as versões em gen/book/
make eps-dry    # dry-run — só lista, não grava
```

#### Uso como atividades VPL no Moodle

Os HTMLs gerados podem ser usados diretamente para criar atividades **VPL (*Virtual Programming Lab*)** no Moodle, com correção automática das submissões dos alunos:

1. Criar uma atividade VPL no Moodle e colar o conteúdo do `EPXX_YY.html` como enunciado;
2. Importar os arquivos `.cases` correspondentes (em `all/capXX/casos/`) como casos de teste do VPL;
3. Configurar as linguagens suportadas — os mesmos casos de teste funcionam para Python, Java, C++, C, JavaScript e R.

Os arquivos `.cases` utilizados pelo `TestSuite` nos *notebooks* são **diretamente compatíveis** com o VPL do Moodle: o mesmo conjunto que valida a solução no Colab corrige automaticamente as submissões na plataforma, sem necessidade de reescrever os testes.

### Notebooks para alunos

```bash
# Uma árvore por combo em notebooks_alunos/<lang>.<locale>/, com
# referências ABNT resolvidas. Para (lang,locale) != (py,pt) lê o
# capítulo já traduzido de gen/<lang>.<locale>/ (rode `make build` antes).
python gerar_notebooks_alunos.py --batch references.bib --out-dir notebooks_alunos            # py.pt
python gerar_notebooks_alunos.py --batch references.bib --out-dir notebooks_alunos --lang py  --locale fr
python gerar_notebooks_alunos.py --batch references.bib --out-dir notebooks_alunos --lang cpp --locale en
```

`make publish` já gera todas as árvores (`LANGS` × `LOCALES`).

### Publicação

```bash
make publish    # build + docs/ + git push
```

### Limpeza

```bash
make clean          # apaga gen/, docs/ e .cache/
make clean-cache    # apaga só .cache/translations.json
make clean-gen      # apaga só gen/ e docs/
```

---

## ⚙️ Execução real de código em C++ (cap01)

Diferente de uma tradução decorativa, o combo `cpp` já **compila e executa de verdade**. Uma célula Python elegível do notebook-fonte vira, no notebook gerado, várias células que fazem exatamente o que o EP01_01 já demonstra manualmente com as 6 linguagens (`all/cap01/cap01.EPs.ipynb`, células `role: common`): `%%writefile` grava o código-fonte, uma célula de *shell magic* compila e roda (`!g++ arquivo.cpp -o arquivo && ./arquivo`), e — quando a célula original chama `mm.show()` — uma célula final exibe o PNG gerado (`IPython.display.Image`). Não existe kernel C++ no Quarto; tudo roda através do kernel Python via `!comando`, o mesmo mecanismo que já valida os EPs em 6 linguagens.

**Como uma célula vira C++:**

1. **Elegibilidade** (`pipeline/notebook_processor.py::_is_eligible_for_foreign_expansion`) — calculada sempre sobre o **código Python original**, nunca sobre a saída do LLM. Uma célula só é candidata se não usar `cv2.*`/`matplotlib` diretamente, não montar `HTML("""...""")` (simulador interativo — não faz sentido em C++ e travaria esperando `stdin`), e só chamar funções `mm.*` da lista com equivalente em C++.
2. **Tradução** (`pipeline/translators.py::LLMCodeTranslator`) — o LLM recebe uma *cheat-sheet* da API real de `morph.hpp`, com regra explícita de nunca inventar função fora da lista.
3. **Validação por compilação** (`pipeline/exec_validate.py::compile_check`) — a tradução só é aceita e cacheada se **compilar de verdade** (`g++` num diretório temporário). Nenhuma tradução quebrada é publicada; falhas nunca são cacheadas (tentam de novo no próximo build, caso um ajuste de prompt/biblioteca resolva).
4. **Fallback seguro**: célula inelegível ou que não compilou vira uma única célula de referência — o Python original, com `#| eval: false` (nunca executada) e um comentário deixando claro que é conceitual, não a fonte da figura ao lado.

**`morph/cpp/morph.hpp`** é a porta mínima da `morph.py` pra C++ — só as 7 funções usadas no cap01: `read` (com download por URL via `fork`/`execlp`, sem shell), `gray`, `randomImage`, `show`, `write`, `threshold` (com Otsu quando o limiar é omitido), `drawImg`. Usa `stb_image`/`stb_image_write` vendorizadas (`morph/cpp/THIRD_PARTY_LICENSES.md`) — sem depender de OpenCV, então `g++ arquivo.cpp -o arquivo` compila sem `apt install` adicional.

**Escopo atual (v0):** só cap01, só essas 7 funções. **Limitação estrutural conhecida:** cada célula compila como programa C++ isolado (mesmo modelo do EP01_01) — uma célula que reusa uma variável definida numa célula Python anterior (ex.: `img`) não enxerga esse estado e cai em referência não-executada.

```bash
# Gerar o capítulo 1 em C++ (PT), HTML apenas
python dev.py --once --langs cpp --locales pt --render html

# Build completo dos 6 combos em produção: py × pt,en,fr (9 caps) e
# cpp × pt,en,fr (só cap01), HTML+PDF
./utils/rebuild.sh py,cpp pt,en,fr
```

> Os capítulos 02–09 em C++ ainda não foram portados (usam `cv2`/`skimage`
> sem equivalente na `morph.hpp`); o build restringe automaticamente os
> combos `cpp` ao `cap01` (`dev.py::run_build` + `_chapter_blocks`).

Pra estender esse mecanismo — outro capítulo, ou outra linguagem além de `cpp` — a peça que falta pra cada nova linguagem é o equivalente a `morph.hpp` (um `morph.<ext>` com as mesmas funções) mais registrar seu comando de compilar em `morph/testsuite.py::compile_run_table` (fonte única, já usada pelos EPs em 6 linguagens) e em `pipeline/exec_validate.py`.

### ✏️ Editando o conteúdo gerado (código, texto e imagens)

`all/capXX/capXX.ipynb` é a única fonte editável em Python/Português. Tudo em
`gen/<combo>/` (C++, inglês, etc.) é gerado por LLM a cada build e
**reescrito do zero** — editar esses arquivos direto não sobrevive ao
próximo `dev.py`. Ainda assim é possível corrigir um erro pontual (um C++
traduzido errado, um trecho de texto mal traduzido) sem esperar o LLM
acertar sozinho:

**Código e texto:**

```bash
# 1. Gerar (ou já ter gerado) o combo com o erro
python dev.py --once --langs cpp --locales en

# 2. Abrir gen/cpp.en/cap01/cap01.cpp.en.ipynb (Jupyter/VS Code) e corrigir
#    a célula errada direto no notebook. Salvar.

# 3. Promover a correção pro cache — não gera nem builda nada, só grava
#    a edição na mesma chave de cache da célula original
python dev.py --promote-edits --langs cpp --locales en

# 4. Rebuildar normalmente — a correção volta sem chamar o LLM de novo
python dev.py --once --langs cpp --locales en --render html
```

Só células que passaram por tradução real (marcadas internamente com
`metadata.pdi.ck`) podem ser promovidas — células `role: common`, EPs
vazios e referências Python não-traduzidas não têm o que promover. Rodar
`--promote-edits` sem ter editado nada é seguro (não faz nada, só relata
"nenhuma edição encontrada"). **Limitação:** se a célula-fonte em `all/`
mudar depois de uma promoção, a correção antiga fica órfã no cache (não
suja nada, só some silenciosamente na próxima tradução daquela célula).

**Imagens** (ex.: uma figura com texto em português que precisa de versão
em inglês): adicionar um arquivo com sufixo de locale ao lado do original,
na mesma pasta `all/capXX/imagens/` — sem mudar nada no notebook-fonte:

```
all/cap04/imagens/fig-04-algoritmo.png       ← padrão (usado por pt e por
                                                qualquer locale sem override)
all/cap04/imagens/fig-04-algoritmo.en.png    ← usado só quando --locales en
```

Vale tanto pra figuras estáticas quanto pros PNGs de simuladores
interativos gerados por Playwright (que sempre partem do notebook em
Português) — nos dois casos o override é pego automaticamente no próximo
build daquele locale. Depois de atualizar pra essa versão do pipeline pela
primeira vez, rode `make clean-gen` uma vez (symlinks antigos de pasta
inteira em `gen/` não são convertidos automaticamente pro novo formato por
arquivo).

**Célula manual travada num (ou vários) combo(s) específico(s):** pra
escrever à mão o conteúdo de uma célula só pra determinados combos, sem
passar pelo LLM neles, comece a célula com uma linha só com o marcador
`#[token]#`, onde `token` é uma lista de partes separadas por ponto — cada
parte é uma chave de `LANGUAGES` (`py`, `cpp`, ...) ou de `LOCALES` (`pt`,
`en`, ...). Dentro do mesmo eixo várias partes combinam em **OU**; entre os
dois eixos (linguagem × idioma) combina em **E**:

```python
#[cpp.pt]#
// Só aparece em cpp.pt — linguagem=cpp E idioma=pt.

#[py.pt.cpp]#
# Aparece em py.pt e em cpp.pt (qualquer linguagem em {py, cpp}), mas
# some em py.en/cpp.en — linguagem ∈ {py, cpp} E idioma ∈ {pt}.
```

A linha do marcador é sempre removida do resultado (em qualquer combo). Um
único token filtra só por aquele eixo (`#[cpp]#` só linguagem, `#[pt]#` só
idioma); a ordem das partes não importa. Nenhuma célula em `all/` usa isso
hoje (o mecanismo existe no pipeline,
`pipeline/notebook_processor.py::_filter_by_language_marker`, mas ainda
não foi usado em conteúdo real).

---

## 🌐 Adicionar Nova Linguagem de Programação

**1.** Edite o arquivo `pipeline/config.py` e adicione a nova linguagem dentro do dicionário literal `LANGUAGES`:

```python
LANGUAGES: dict[str, Language] = {
    'py':   Language('py',   'Python', '.py',  base=True,  quarto_engine='python'),
    'cpp':  Language('cpp',  'C++',    '.cpp', base=False, quarto_engine='python'),
    'java': Language('java', 'Java',   '.java',base=False, quarto_engine='python'),
    'c':    Language('c',    'C',      '.c',   base=False, quarto_engine='python'),
    'rs':   Language('rs',   'Rust',   '.rs',  base=False, quarto_engine='python'), # ← Exemplo
}

```

⚙️ **Nota de Implementação:** Após registrar no `config.py`, você deve implementar a respectiva estratégia de tradução de sintaxe de código em `pipeline/translators.py`.

**2.** Teste a compilação gerando os artefatos com a nova linguagem:

```bash
python dev.py --once --langs py,cpp,rs --locales pt --render html

```

---

## 🌍 Adicionar Novo Idioma (Locale)

**1.** Edite o arquivo `pipeline/config.py` para incluir o novo idioma no dicionário `LOCALES` e seu respectivo mapeamento de interface em `UI_STRINGS`:

```python
LOCALES: dict[str, Locale] = {
    'pt': Locale('pt', 'Português', 'pt',    base=True),
    'en': Locale('en', 'English',   'en',    base=False),
    # ...
    'de': Locale('de', 'Deutsch',   'de',    base=False), # ← Adicionar aqui
}

```

No mesmo arquivo, adicione o bloco de tradução das chaves de interface em `UI_STRINGS`:

```python
UI_STRINGS: dict[str, dict[str, str]] = {
    'pt': { ... },
    'en': { ... },
    # ...
    'de': {
        'book_subtitle':   'Praxisorientierter Ansatz mit {lang_label}',
        'part_1':          'Teil I — PDI-Grundlagen',
        'part_2':          'Teil II — Computer Vision',
        'references_title':'Literaturverzeichnis',
        'exercises_label': 'Übungen',
        'note_code':       '{lang_label}-Code',
        'welcome':         'Willkommen im Lehrbuch für PDI und Computer Vision — Version {lang_label} / Deutsch.',
    },
}

```

**2.** Teste a compilação incluindo o novo idioma nos alvos de renderização:

```bash
python dev.py --once --langs py --locales pt,en,de --render html

```

---

## 🔄 Git Workflow (Para Co-autores)

**Importante:** Nunca trabalhe diretamente na pasta `pdi-vc`. Todo o desenvolvimento ocorre em `si-md2`.

1. **Início:** 

```bash
# Para deixar o repositório exatamente igual ao GitHub, faça:
git fetch origin
git reset --hard origin/master
git clean -fd
```

2. **Desenvolvimento:** Edite os arquivos `.ipynb` ou `.qmd`.
3. **Limpeza:** Antes de enviar, você pode rodar `./limpar.sh` para não enviar lixo de cache.
4. **Envio:** 

```bash
git add .
git commit -m "Descrição clara da alteração"
git push origin master
```

---

## Dependências

A forma recomendada de preparar o ambiente (TinyTeX + ambiente virtual Python) é rodar o script único:

```bash
chmod +x setup.sh
./setup.sh              # instala o esquema completo do TeX Live (recomendado, alguns GB)
# ou
./setup.sh --minimal    # instala apenas os pacotes LaTeX especificamente necessários
```

O `setup.sh` cuida de:
1. Configurar o repositório do TinyTeX e atualizar o `tlmgr`;
2. Instalar os pacotes LaTeX necessários para `quarto render --to pdf` (idioma `pt`, engine `lualatex`, classe `book`);
3. Criar o `.venv` e instalar as dependências Python fixadas em `requirements.txt`.

Depois de rodar o script, ative o ambiente virtual:

```bash
source .venv/bin/activate
```

### Instalação manual (caso prefira não usar o `setup.sh`)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install playwright
playwright install chromium   # para screenshots de simuladores
```

```bash
# Sistema
# quarto   — https://quarto.org/docs/get-started/
# TinyTeX  — instalado automaticamente pelo Quarto (quarto install tinytex)
```

Pacotes LaTeX adicionais necessários no TinyTeX (Linux):

```bash
TLMGR=~/.TinyTeX/bin/x86_64-linux/tlmgr

$TLMGR option repository https://tlnet.yihui.org/
$TLMGR update --self

$TLMGR install \
  luatexbase \
  ctablestack \
  babel-portuges \
  hyphen-portuguese \
  selnolig \
  fvextra \
  emoji \
  twemoji-colr \
  upquote \
  xcolor \
  framed \
  csquotes \
  booktabs \
  longtable \
  array \
  multirow \
  wrapfig \
  float \
  colortbl \
  hyperref \
  bookmark \
  footnotehyper \
  pdflscape \
  tabu \
  varwidth \
  threeparttable \
  threeparttablex \
  makecell \
  xltabular \
  ltablex \
  environ \
  trimspaces \
  titling \
  etoolbox

$TLMGR update --all
```

> ⚠️ **Nota:** o nome correto do pacote de suporte ao Português no `babel` é **`babel-portuges`** (sem o "e" final) — `babel-portuguese` não existe no CTAN e causa erro de instalação. Em macOS, substitua `~/.TinyTeX/bin/x86_64-linux/` por `~/Library/TinyTeX/bin/universal-darwin/`.

Se `quarto render --to pdf` ainda falhar com `LaTeX Error: File 'X.sty' not found`, identifique o pacote pelo nome do arquivo faltante e instale com `$TLMGR install <pacote>`, ou simplesmente rode `./setup.sh` (sem `--minimal`) para instalar o esquema completo e evitar esse ciclo.

---

## Licença

© 2026 Francisco de Assis Zampirolli — UFABC.
Creative Commons BY-NC-SA 4.0.
