# PDI+VC — Processamento Digital de Imagens e Visão Computacional

**Material didático interativo para cursos de graduação e pós-graduação**
> Escreva **uma vez** em formato Quarto (Markdown+Python). O pipeline traduz o resto.

🚧 **Em construção!**
Este material está sendo preparado e aplicado em 3 turmas de PDI na UFABC (até o Capítulo 6 no momento).

[![Livro Online](https://img.shields.io/badge/Livro-Online-blue?logo=github)](https://fzampirolli.github.io/pdi-vc)
[![Abrir no Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/fzampirolli/pdi-vc/blob/master/notebooks_alunos/cap01/cap01_aluno.ipynb)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20784606.svg)](https://doi.org/10.5281/zenodo.20784606)
[![Licença](https://img.shields.io/badge/Licença-CC--BY--NC--SA--4.0-green)](LICENSE)

---

## Para o Aluno

### Onde encontrar o material

| Formato | Link |
|---------|------|
| **HTML** | [fzampirolli.github.io/pdi-vc](https://fzampirolli.github.io/pdi-vc/) — navegação interativa, simuladores |
| **PDF** | Disponível na página HTML (botão *Download PDF*) — para impressão e leitura offline |
| **Notebooks Jupyter/Colab** | Pasta `notebooks_alunos/capXX/` — prontos para execução, sem dependências do Quarto |

### Como usar os notebooks

1. Acesse [Google Colab](https://colab.research.google.com/) ou instale o [Jupyter](https://jupyter.org/)
2. Faça upload do notebook `capXX_aluno.ipynb` ou abra diretamente pelo GitHub
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
├── all/                          ← ✏️  FONTES — editar APENAS aqui
│   └── capXX/
│       ├── capXX.ipynb           ← conteúdo principal (Python + Português)
│       ├── capXX.EPs.ipynb       ← exercícios práticos com TestSuite
│       ├── imagens/              ← figuras estáticas + screenshots de simuladores
│       │   ├── fig-XX-nome.png   ← gerado automaticamente pelo Playwright
│       │   └── ...
│       └── casos/                ← casos de teste para o TestSuite
│           ├── EP01_01.cases
│           └── ...
│
├── gen/                          ← 🤖  GERADO — não editar manualmente
│   ├── py.pt/capXX/              ← Python + Português (passthrough)
│   ├── py.en/capXX/              ← Python + English  (texto traduzido)
│   ├── cpp.pt/capXX/             ← C++ + Português   (código traduzido)
│   ├── quarto/                   ← pasta Quarto auto-suficiente por versão
│   │   └── py.pt/
│   │       ├── _quarto.yml       ← gerado pelo pipeline
│   │       ├── capXX -> gen/py.pt/capXX  (symlink)
│   │       └── includes -> includes/     (symlink)
│   └── book/                     ← saída final
│       ├── py.pt/
│       │   ├── livro.pt.py.pdf
│       │   └── *.html
│       └── eps/                  ← EPs extraídos individualmente
│           └── py.pt/
│               ├── EP01_01.html
│               ├── EP01_02.html
│               └── ...
│
├── notebooks_alunos/             ← 📦  distribuição para alunos
│   └── capXX/
│       ├── capXX_aluno.ipynb
│       ├── capXX.EPs_aluno.ipynb
│       ├── imagens/
│       └── casos/
│
├── pipeline/                     ← motor de geração
│   ├── config.py                 ← registro de langs/locales
│   ├── cache.py                  ← cache de traduções em disco
│   ├── translators.py            ← CodeTranslator + TextTranslator (via API)
│   ├── notebook_processor.py     ← lê fonte, traduz, emite notebook filtrado
│   ├── quarto_builder.py         ← monta pasta Quarto + geração de PDF
│   ├── bib.py                    ← parser BibTeX + formatação ABNT
│   └── index_builder.py          ← gera gen/book/index.html
│
├── includes/                     ← assets compartilhados
│   ├── preamble.tex              ← pacotes LaTeX para PDF (emoji, fontes…)
│   ├── abnt.csl                  ← estilo de citação ABNT
│   ├── emoji-filter.lua          ← filtro Pandoc: converte emojis → \emoji{}
│   └── prefacio.qmd              ← prefácio do livro (suporta placeholders)
│
├── morph/
│   ├── morph.py                  ← biblioteca de PDI desenvolvida pelos autores
│   └── testsuite.py              ← validador automático de EPs
│
├── dev.py                        ← 🔑  CLI principal (watch + build)
├── extrair_eps.py                ← extrai cada EP em HTML individual
├── gerar_livro.py                ← CLI alternativo (batch)
├── gerar_notebooks_alunos.py     ← gera notebooks_alunos/
├── run.sh                        ← build rápido de PDF (limpa cache + make pdf)
├── Makefile                      ← atalhos de desenvolvimento
├── references.bib                ← referências bibliográficas (ABNT)
└── requirements.txt              ← dependências Python
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

Células com `HTML("""...""")` são simuladores interativos. O pipeline trata automaticamente:

- **HTML**: exibe o simulador normalmente
- **PDF**: substitui por screenshot PNG gerado via Playwright (salvo em `all/capXX/imagens/`)

Os PNGs são gerados na primeira execução e reutilizados nas seguintes.
Para regenerar, apague o PNG correspondente em `all/capXX/imagens/`.

Padrão de label obrigatório para simuladores:
```python
#| label: fig-XX-nome-do-simulador
#| fig-cap: "Descrição para a legenda"
#| echo: false
from IPython.display import HTML
HTML("""...""")
```

### Convenções de labels Quarto

```markdown
# Figura
![](imagens/exemplo.png){#fig-01-exemplo width=70%}
Citar: @fig-01-exemplo

# Equação
$$f(x) = g(x)$$ {#eq-01-nome}
Citar: @eq-01-nome

# Tabela
| A | B |
|---|---|
: Legenda {#tbl-01-dados}
```

**Atenção:**  labels de figura no Quarto não podem ter maiúsculas.

**Regra:** `{#prefixo-CAPITULO-nome}` — sempre com número do capítulo.

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

# Múltiplas versões
python dev.py --once --langs py,cpp --locales pt,en --render html

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
# Gera notebooks_alunos/ com referências ABNT resolvidas
python gerar_notebooks_alunos.py --batch references.bib --out-dir notebooks_alunos
```

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

## Adicionar nova linguagem de programação

**1.** Edite `pipeline/config.py`:
```python
LANGUAGES['java'] = Language('java', 'Java', '.java', base=False)
```

**2.** Gere:
```bash
python dev.py --once --langs py,cpp,java --locales pt --render html
```

## Adicionar novo idioma

**1.** Edite `pipeline/config.py`:
```python
LOCALES['de'] = Locale('de', 'Deutsch', 'de', base=False)
UI_STRINGS['de'] = {
    'book_subtitle': 'Praxisorientierter Ansatz mit {lang_label}',
    'part_1': 'Teil I — PDI-Grundlagen',
    # ...
}
```

**2.** Gere:
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

```bash
pip install -r requirements.txt
pip install playwright
playwright install chromium   # para screenshots de simuladores

# Sistema
# quarto   — https://quarto.org/docs/get-started/
# TinyTeX  — instalado automaticamente pelo Quarto (quarto install tinytex)
```

Pacotes LaTeX adicionais (instalar no TinyTeX):
```bash
~/Library/TinyTeX/bin/universal-darwin/tlmgr install emoji twemoji-colr luatexbase
```

---

## Licença

© 2026 Francisco de Assis Zampirolli — UFABC.
Creative Commons BY-NC-SA 4.0.