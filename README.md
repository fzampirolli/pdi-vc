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
├── all/                          ← ✏️ FONTES — editar APENAS aqui
│   ├── _cap00/                   ← propostas, prompts e rascunhos de capítulos
│   └── capXX/                    (do cap01 ao cap09)
│       ├── capXX.ipynb           ← conteúdo principal (Teoria)
│       ├── capXX.EPs.ipynb       ← enunciados e códigos dos Exercícios Práticos[cite: 1]
│       ├── imagens/              ← badges, figuras estáticas e setups dos capítulos[cite: 1]
│       └── casos/                ← arquivos de teste (.cases) para validação dos EPs[cite: 1]
│
├── gen/                          ← 🤖 GERADO — não editar manualmente[cite: 1]
│   ├── py.pt/                    ← notebooks processados em Python/Português[cite: 1]
│   │   └── capXX/                ← notebooks finais e links de imagens[cite: 1]
│   └── quarto/                   ← ambiente de compilação do Quarto[cite: 1]
│       └── py.pt/                ← estrutura organizada com _quarto.yml para o build[cite: 1]
│           └── book/             ← saída final da renderização local (PDF e HTMLs)[cite: 1]
│
├── docs/                         ← 🌐 DEPLOY — pasta para publicação estática (GitHub Pages)[cite: 1]
│   ├── index.html                ← página inicial do site do livro[cite: 1]
│   ├── py.pt/                    ← versão web completa do livro (HTMLs, PDFs, imagens)[cite: 1]
│   └── eps/                      ← Exercícios Práticos extraídos individualmente[cite: 1]
│       ├── py.pt/                ← formato HTML para visualização direta[cite: 1]
│       └── py.pt_moodle/         ← formato HTML otimizado para o Moodle[cite: 1]
│
├── notebooks_alunos/             ← 📦 DISTRIBUIÇÃO — material limpo para os estudantes[cite: 1]
│   └── capXX/                    
│       ├── capXX_aluno.ipynb     ← teoria com lacunas/atividades[cite: 1]
│       ├── capXX.EPs_aluno.ipynb ← templates dos EPs para implementação[cite: 1]
│       ├── imagens/              ← imagens necessárias para rodar localmente[cite: 1]
│       └── casos/                ← casos de teste abertos[cite: 1]
│
├── pipeline/                     ← ⚙️ MOTOR — scripts do pipeline de compilação[cite: 1]
│   ├── config.py                 ← configurações gerais do projeto[cite: 1]
│   ├── cache.py                  ← gerenciamento de cache de processamento[cite: 1]
│   ├── notebook_processor.py     ← processador e limpador das células dos notebooks[cite: 1]
│   ├── quarto_builder.py         ← orquestrador do build via Quarto[cite: 1]
│   ├── index_builder.py          ← gerador automático de índices do site[cite: 1]
│   └── translators.py            ← gerenciador de tradução e chamadas de API[cite: 1]
│
├── includes/                     ← 🎨 ASSETS — elementos compartilhados de estilização[cite: 1]
│   ├── preamble.tex / .html      ← preâmbulos de configuração LaTeX e HTML[cite: 1]
│   ├── abnt.csl                  ← especificação de estilo de citação ABNT[cite: 1]
│   ├── emoji-filter.lua          ← filtro Pandoc para conversão de emojis[cite: 1]
│   └── prefacio.qmd              ← rascunho/metadados do prefácio[cite: 1]
│
├── morph/                        ← 📦 BIBLIOTECA — core de PDI e testes do projeto[cite: 1]
│   ├── morph.py / morph-large.py ← implementações de morfologia e PDI[cite: 1]
│   └── testsuite.py              ← framework de testes automáticos para os EPs[cite: 1]
│
├── runs/                         ← 📊 MODELOS — saídas e pesos de treinamento do YOLO[cite: 1]
│   └── detect/                   ← matrizes de confusão, curvas F1/PR e pesos (best.pt)[cite: 1]
│
├── dev.py                        ← CLI principal de desenvolvimento[cite: 1]
├── ep_tools.py                   ← utilitários para manipulação e extração dos EPs[cite: 1]
├── gerar_livro.py                ← script de geração em lote do livro[cite: 1]
├── gerar_notebooks_alunos.py     ← script que limpa e gera a pasta dos alunos[cite: 1]
├── run.sh / limpar.sh            ← scripts Bash para automação e limpeza de build[cite: 1]
├── Makefile                      ← atalhos de comandos rápidos[cite: 1]
├── references.bib                ← base de dados bibliográfica BibTeX[cite: 1]
└── requirements.txt              ← dependências Python do projeto[cite: 1]
```


## 🌐 Documentação e Artefatos Gerados (`docs/`)

A pasta `docs/` funciona como a raiz para o *deploy* estático (como GitHub Pages [fzampirolli.github.io/pdi-vc/](https://fzampirolli.github.io/pdi-vc/)) e concentra os resultados finais do *pipeline* de compilação:

```text
docs/
├── index.html                 # Página inicial da documentação/livro web
├── capa_girassol1.png         # Asset visual da capa do livro
│
├── eps/                       # Exercícios Práticos (EPs) extraídos individualmente
│   ├── py.pt/                 # EPs do Cap 1 ao 9 em formato HTML autônomo
│   └── py.pt_moodle/          # EPs formatados especificamente para importação no Moodle
│
└── py.pt/                     # Estrutura completa do livro renderizado
    ├── book-latex/            # Arquivos fontes, PDFs e figuras geradas via LaTeX
    ├── cap01/ até cap09/      # Capítulos convertidos em HTML com seus respectivos outputs/gráficos
    └── site_libs/             # Bibliotecas estáticas de suporte (Bootstrap, Quarto Search, etc.)
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