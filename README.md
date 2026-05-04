# PDI+VC Livro — Guia do Autor

**Processamento Digital de Imagens e Visão Computacional**

---

## Princípio fundamental

> **Escreva UMA VEZ em Python + Português. O pipeline traduz o resto.**

O notebook-fonte em `all/cap01/cap01.ipynb` é **canônico**: Python puro, Português puro.
O script `gerar_livro.py` chama a API Anthropic para gerar automaticamente as versões
em C++, Java, Inglês, Francês, etc. As traduções ficam em cache (`.cache/`) e só são
rechamadas quando o conteúdo muda.

---

## Estrutura

```
pdi-vc/
│
├── all/                      ← ✏️  FONTES — editar APENAS aqui
│   └── capXX/
│       ├── capXX.ipynb       ← Python + Português (canônico)
│       ├── capXX.ex.ipynb    ← Exercícios (Python + Português)
│       ├── imagens/
│       └── dados/
│
├── gen/                      ← 🤖  GERADO — não editar
│   ├── py.pt/capXX/          ← Python + Português  (passthrough)
│   ├── py.en/capXX/          ← Python + English    (texto traduzido)
│   ├── cpp.pt/capXX/         ← C++ + Português     (código traduzido)
│   ├── cpp.en/capXX/         ← C++ + English       (ambos traduzidos)
│   ├── quarto/               ← _quarto.yml por versão (render de dentro)
│   │   ├── py.pt/
│   │   ├── py.en/
│   │   ├── cpp.pt/
│   │   └── cpp.en/
│   └── book/                 ← HTML + PDF finais
│
├── pipeline/                 ← Motor de geração
│   ├── config.py             ← Registro de langs/locales (extensível)
│   ├── cache.py              ← Cache de traduções em disco
│   ├── translators.py        ← Strategy: CodeTranslator + TextTranslator
│   ├── notebook_processor.py ← Lê fonte, traduz, emite notebook filtrado
│   ├── quarto_builder.py     ← Monta pasta Quarto auto-suficiente
│   └── bib.py                ← Parser BibTeX + formatação ABNT
│
├── morph/                    ← Biblioteca morph.py (Python)
├── testes/                   ← Casos de teste VPL/MCTest
├── includes/                 ← preamble.tex, preamble.html, abnt.csl
│
├── gerar_livro.py            ← 🔑  CLI principal
├── publish_all.sh            ← Pipeline completo
├── limpar.sh                 ← Limpeza de caches
├── references.bib            ← Referências (ABNT)
├── requirements.txt          ← Dependências Python
└── .cache/translations.json  ← Cache de traduções LLM
```

---

## Como escrever um notebook-fonte

Cada célula tem metadados `pdi.role`:

| Papel (`role`) | Tipo de célula | O que acontece |
|----------------|----------------|----------------|
| `"code"` (padrão) | código | traduzido py→cpp pelo LLM |
| `"text"` (padrão) | markdown | traduzido pt→en pelo LLM |
| `"common"` | qualquer | mantido sem alteração |
| `"base_only"` | qualquer | só aparece na versão py.pt |
| `"exercise"` | markdown | traduzido como texto |

Exemplo mínimo de célula de código:
```json
{
  "cell_type": "code",
  "metadata": {"pdi": {"role": "code"}},
  "source": ["img = mm.read('lena.jpg')\nmm.show(img)"]
}
```

Célula common (aparece em todas as versões sem tradução):
```json
{
  "cell_type": "markdown",
  "metadata": {"pdi": {"role": "common"}},
  "source": ["$$E = mc^2$$"]
}
```

---

## Adicionar nova linguagem de programação

**1.** Edite `pipeline/config.py`:
```python
LANGUAGES['java'] = Language('java', 'Java', '.java', base=False)
```

**2.** (Opcional) Adicione prompt especializado em `pipeline/translators.py`
se a linguagem precisar de instruções específicas — caso contrário o
`LLMCodeTranslator` genérico já funciona.

**3.** Gere:
```bash
python gerar_livro.py --langs py,cpp,java --locales pt,en
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
python gerar_livro.py --langs py --locales pt,en,de
```

---

## Comandos

```bash
# Gerar padrão: py × pt
python gerar_livro.py

# Sem chamar API (placeholders para revisão de estrutura)
python gerar_livro.py --dry-run

# Gerar + renderizar HTML
python gerar_livro.py --render html

# Publicação completa
./publish_all.sh

# Pipeline personalizado
LANGS=py,cpp,java LOCALES=pt,en,fr ./publish_all.sh

# Renderizar manualmente uma versão
cd gen/quarto/cpp.en && quarto render --to html
cd gen/quarto/py.pt  && quarto render --to pdf
```

---

## Comandos Make

```bash
# Build único py×pt + HTML (recomendado para desenvolvimento)
make build

# Watch py×pt + render HTML ao salvar (Ctrl+C para sair)
make html

# Watch py×pt + render PDF ao salvar
make pdf

# Build sem chamar a API (placeholders para revisar estrutura)
make build-dry

# Capítulo específico
make cap CAP=all/cap01/cap01.ipynb

# Todas as linguagens × pt + HTML
make all-langs

# py × todos os idiomas + HTML
make all-locales

# Tudo × tudo + HTML + PDF
make full

# Limpeza
make clean        # apaga gen/ e .cache/
make clean-cache  # apaga só o cache de traduções
make clean-gen    # apaga só gen/

# Overrides
make build LANGS=cpp LOCALES=en
```

---

## Padronização Quarto (labels, figuras, equações)

```markdown
# Figura
::: {#fig-1-exemplo}
![](imagens/exemplo.png){width=70% fig-align="center"}
Legenda da figura.
:::
Citar: @fig-1-exemplo → Figura 1.1

# Equação
$$f(x,y) = g(x) \cdot h(y)$$ {#eq-1-separavel}
Citar: @eq-1-separavel

# Tabela
| A | B |
|---|---|
| x | y |
: Legenda {#tbl-1-dados}
```

**Regra de ouro para labels:** `{#prefixo-CAPITULO-nome}` — sempre com número do capítulo.

---

## Dependências

```bash
pip install -r requirements.txt
# Sistema: quarto, texlive-full (PDF)
```

---

## Licença

© 2026 Francisco de Assis Zampirolli — UFABC.  
Creative Commons BY-NC-SA 4.0.
