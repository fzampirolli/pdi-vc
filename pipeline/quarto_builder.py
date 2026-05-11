"""
pipeline/quarto_builder.py
===========================
Constrói uma pasta Quarto auto-suficiente para cada combo:

    gen/quarto/<combo>/
        _quarto.yml      ← gerado aqui
        index.qmd        ← gerado aqui (idioma correto)
        prefacio.qmd     ← gerado aqui (prefácio do livro)
        capXX/           ← symlink → gen/<combo>/capXX/
        references.bib   ← symlink → ../../references.bib
        includes/        ← symlink → ../../includes/

Render (sem --config):
    cd gen/quarto/py.pt && quarto render --to html
    cd gen/quarto/py.pt && quarto render --to pdf
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional

from .config import (
    Combo, UI_STRINGS, LOCALES, LANGUAGES,
    BASE_LANG, BASE_LOCALE,
)

DIR_GEN = Path('gen')

# ─────────────────────────────────────────────────────────────────────────────
# Templates dos arquivos auxiliares
# ─────────────────────────────────────────────────────────────────────────────

def _index_qmd(combo: Combo) -> str:
    lang_label   = LANGUAGES[combo.lang].label
    locale_label = LOCALES[combo.locale].label
    welcome      = UI_STRINGS[combo.locale]['welcome'].format(lang_label=lang_label)
    part1        = UI_STRINGS[combo.locale]['part_1']
    part2        = UI_STRINGS[combo.locale]['part_2']
    refs_title   = UI_STRINGS[combo.locale]['references_title']
    return (
        f'## PDI e VC — {lang_label} {{.unnumbered}}\n\n'
        f'{welcome}\n\n'
        f'### {UI_STRINGS[combo.locale].get("org_title","Organização")} {{.unnumbered}}\n\n'
        f'- **{part1}** — Representação, histogramas, filtragem, morfologia\n'
        f'- **{part2}** — Segmentação, descritores, detecção, deep learning\n\n'
        '---\n'
    )


def _prefacio_qmd(combo: Combo) -> str:
    """
    Lê o prefácio do arquivo includes/prefacio.qmd.
    Se o arquivo não existir, gera um prefácio padrão com suporte a i18n.
    """
    prefacio_path = Path('includes/prefacio.qmd')
    
    if prefacio_path.exists():
        # Lê o arquivo de prefácio externo
        content = prefacio_path.read_text(encoding='utf-8')
        print(f'  ✓ Prefácio lido de {prefacio_path}')
        
        # Substitui placeholders de localização se existirem
        # Ex: {{lang_label}} será substituído pelo nome do idioma
        lang_label = LANGUAGES[combo.lang].label
        content = content.replace('{{lang_label}}', lang_label)
        
        # Substitui outros placeholders úteis
        locale_label = LOCALES[combo.locale].label
        content = content.replace('{{locale_label}}', locale_label)
        
        return content
    else:
        # Fallback: gera prefácio padrão
        print(f'  ⚠ Arquivo {prefacio_path} não encontrado. Gerando prefácio padrão.')
        return _generate_default_prefacio(combo)


def _generate_default_prefacio(combo: Combo) -> str:
    """Gera um prefácio padrão (fallback quando não há arquivo externo)."""
    lang_label   = LANGUAGES[combo.lang].label
    
    prefacio_title = UI_STRINGS[combo.locale].get('preface_title', 'Prefácio')
    projeto_titulo = UI_STRINGS[combo.locale].get('preface_project_title', 'Um livro vivo')
    projeto_texto  = UI_STRINGS[combo.locale].get('preface_project_text',
        'Este não é um livro estático. O conteúdo está em constante evolução: exemplos são refinados, '
        'novas seções são adicionadas e abordagens pedagógicas são aprimoradas com base no feedback '
        'de alunos e professores. Por isso, tratamos este material como um *projeto inicial* — '
        'uma base sólida que continuará crescendo.')
    
    producao_titulo = UI_STRINGS[combo.locale].get('preface_production_title', 'Como este livro é produzido')
    producao_texto  = UI_STRINGS[combo.locale].get('preface_production_text',
        'Todo o conteúdo é escrito em **Quarto**, um sistema de publicação científica e técnica '
        'que permite renderizar o mesmo código-fonte para múltiplos formatos.')
    
    # ... (resto da função com os mesmos textos da versão anterior)
    # Mantenha o restante do conteúdo conforme a versão anterior
    
    return f'''# {prefacio_title} {{.unnumbered}}

Este livro é um **projeto em construção** sobre **Processamento Digital de Imagens (PDI) e Visão Computacional (VC)**,
concebido como material didático interativo para cursos de graduação e pós-graduação em Computação, Engenharias e áreas afins.

## {projeto_titulo} {{.unnumbered}}

{projeto_texto}

## {producao_titulo} {{.unnumbered}}

{producao_texto}

| Formato | Descrição |
|---------|-----------|
| **HTML** — Versão web completa, com navegação interativa, disponível em [fzampirolli.github.io/pdi-vc](https://fzampirolli.github.io/pdi-vc/) |
| **PDF** — Versão para impressão ou leitura offline |
| **Notebooks para alunos** — Versão `.ipynb` processada por um filtro personalizado que resolve citações, numera figuras, tabelas e equações, e gera referências formatadas no estilo ABNT — ideal para uso no Jupyter e Google Colab |

O filtro de pós-processamento (`quarto_ipynb_refs.py`) prepara os notebooks para distribuição aos alunos,
garantindo que funcionem perfeitamente em ambientes interativos mesmo sem depender do Quarto instalado.

## Sobre as linguagens de programação {{.unnumbered}}

Nesta versão inicial, utilizamos **Python** como linguagem principal, com as bibliotecas
`morph.py` (desenvolvida pelos autores), OpenCV, NumPy e Matplotlib. No entanto,
a arquitetura do projeto é flexível: no futuro, exemplos e capítulos podem ser adaptados
para outras linguagens como R, Julia ou C++, dependendo das demandas da comunidade.

## Código aberto {{.unnumbered}}

Este livro é um projeto de código aberto. Todo o conteúdo — texto, código-fonte,
imagens e scripts de processamento — está disponível publicamente em:

👉 **[github.com/fzampirolli/pdi-vc](https://github.com/fzampirolli/pdi-vc/)**

Você pode:

- 📖 **Ler e estudar** gratuitamente
- 🐛 **Reportar erros** ou sugerir melhorias abrindo uma *issue*
- 🤝 **Contribuir** com correções, novos exemplos ou traduções via *pull requests*
- 🔧 **Adaptar** o material para suas próprias turmas

## Como usar os notebooks {{.unnumbered}}

Cada capítulo do livro está disponível como um *notebook* interativo.
Se você nunca usou um notebook Jupyter ou Google Colab, veja a seção
"Antes de começar: Notebooks em Python" a seguir para um guia rápido.

## Agradecimentos {{.unnumbered}}

Agradecemos aos alunos, colegas e colaboradores que testam, questionam e contribuem
com este projeto. Este livro é feito para vocês e por vocês.

---

## Antes de começar: Notebooks em Python {{.unnumbered}}

O que é este documento? Você já ouviu falar em ***Literate Programming*** (Programação Literária)?
O conceito foi criado por Donald Knuth em 1984 [@knuth_literate_1984]
— autor de *The Art of Computer Programming* [@knuth_art_1997]
e criador do sistema de tipografia TeX, base sobre a qual Leslie Lamport desenvolveu
posteriormente o LaTeX — e propõe que os programas sejam escritos como uma narrativa
lógica, combinando código e documentação em uma única obra.

Isto é um *notebook*: um documento que intercala textos explicativos — as **células de texto**
no formato [Markdown](https://colab.research.google.com/notebooks/markdown_guide.ipynb) —
com códigos de programas em [Python](https://www.python.org/) — as **células de código**.

É fácil distinguir as células de código: elas são precedidas por `[ ]`.
Para executar uma célula de código, basta selecioná-la e pressionar
<kbd>Shift</kbd> + <kbd>Enter</kbd>. Antes de começar, algumas observações
importantes sobre o ambiente:

- **No computador:** no Colab ou Jupyter, você também pode executar uma célula
  clicando no botão de ▶️ (*play*) que aparece ao passar o mouse sobre os colchetes `[ ]`.
- **No celular:** no Colab, o atalho <kbd>Shift</kbd> + <kbd>Enter</kbd> pode não funcionar.
  Nesse caso, toque no botão de ▶️ (*play*).
- **Execução local:** você pode rodar este notebook no seu computador instalando o
  [Jupyter Notebook](https://jupyter.org).
- **Google Colab:** para executar no seu navegador, vá em **Arquivo → Salvar uma cópia no Drive**
  e abra o arquivo **Cópia de aula01.ipynb**, que ficará na pasta **Colab Notebooks** do seu Drive.

O resultado será exibido logo abaixo da célula executada.

::: {{.callout-note}}
### Nota sobre o formato {{.unnumbered}}

Você pode estar acessando este conteúdo de diferentes maneiras. Se estiver executando
este notebook no [Jupyter](https://jupyter.org/) ou no [Google Colab](https://colab.research.google.com/),
as células de código são interativas: você pode executá-las pressionando
<kbd>Shift</kbd> + <kbd>Enter</kbd> ou clicando no botão de *play*. Se estiver lendo
a versão renderizada em HTML ou PDF, o código aparecerá como blocos estáticos,
mas o conteúdo e as explicações permanecem os mesmos — a única diferença é que
você não poderá executar o código diretamente no documento.
:::
'''


def _refs_qmd(combo: Combo) -> str:
    title = UI_STRINGS[combo.locale].get('references_title', 'Referências')
    return f'# {title} {{.unnumbered}}\n\n::: {{#refs}}\n:::\n'


def _process_attachments(combo: Combo, nb_root: Path, qdir: Path, all_root: Path):
    """
    Processa anexos do diretório all/ e copia para gen/quarto/<combo>/attachments/
    """
    attachments_dir = qdir / 'attachments'
    attachments_dir.mkdir(parents=True, exist_ok=True)
    
    # Procura por anexos no diretório all/capXX/
    for cap in ['cap01', 'cap02', 'cap03', 'cap04', 'cap05', 'cap06', 'cap07', 'cap08']:
        cap_dir = all_root / cap
        if not cap_dir.exists():
            continue
            
        # Procura arquivos anexos (imagens, dados, etc)
        for attachment in cap_dir.glob('*'):
            if attachment.is_file() and attachment.suffix in ['.png', '.jpg', '.jpeg', '.gif', '.csv', '.txt', '.pdf']:
                # Copia para attachments/capXX/
                target_dir = attachments_dir / cap
                target_dir.mkdir(exist_ok=True)
                target_file = target_dir / attachment.name
                
                shutil.copy2(attachment, target_file)
                print(f'  ✓ Anexo: {cap}/{attachment.name}')


# ─────────────────────────────────────────────────────────────────────────────
# Builder
# ─────────────────────────────────────────────────────────────────────────────

class QuartoBuilder:
    """
    Monta a pasta gen/quarto/<combo>/ e o _quarto.yml interno.
    O render NÃO usa --config: roda de dentro da pasta.
    """

    CAPS_PART1 = [f'cap{i:02d}' for i in range(1, 5)]
    CAPS_PART2 = [f'cap{i:02d}' for i in range(5, 9)]

    def __init__(self, project_root: Path = Path('.')):
        self.root = project_root.resolve()

    def build(self, combo: Combo, nb_root: Optional[Path] = None, all_root: Optional[Path] = None) -> Path:
        """
        Constrói a pasta Quarto para o combo.
        nb_root: pasta que contém capXX/ com os notebooks filtrados (gen/<combo>/)
        all_root: pasta que contém os notebooks originais e anexos (all/)
        Retorna o caminho da pasta criada.
        """
        nb_root = nb_root or (self.root / DIR_GEN / combo.key)
        all_root = all_root or (self.root / 'all')  # Diretório original
        qdir    = self.root / DIR_GEN / 'quarto' / combo.key
        qdir.mkdir(parents=True, exist_ok=True)

        # Arquivos de texto
        (qdir / 'index.qmd').write_text(_index_qmd(combo), encoding='utf-8')
        (qdir / 'prefacio.qmd').write_text(_prefacio_qmd(combo), encoding='utf-8')
        (qdir / 'referencias.qmd').write_text(_refs_qmd(combo), encoding='utf-8')

        # Symlinks para capítulos
        self._symlink_caps(combo, qdir, nb_root)
        
        # Processa anexos
        _process_attachments(combo, nb_root, qdir, all_root)

        # Symlinks para assets partilhados
        self._symlink(qdir / 'references.bib', self.root / 'references.bib')
        self._symlink(qdir / 'includes',       self.root / 'includes')

        # Cria arquivo de preâmbulo para PDF se não existir
        self._ensure_preamble_files()

        # _quarto.yml
        yml = self._quarto_yml(combo, nb_root)
        (qdir / '_quarto.yml').write_text(yml, encoding='utf-8')
        (qdir / 'fvextra.tex').write_text(
            r'\usepackage{fvextra}' + '\n'
            r'\DefineVerbatimEnvironment{Highlighting}{Verbatim}'
            r'{breaklines=true,breaksymbolleft={},commandchars=\\\{\}}',
            encoding='utf-8'
        )

        print(f'  ✓ Quarto dir: {qdir.relative_to(self.root)}')
        print(f'    render  :  cd {qdir.relative_to(self.root)} && quarto render --to html')
        return qdir

    # ── Internos ──────────────────────────────────────────────────────────────

    @staticmethod
    def _symlink(link: Path, target: Path):
        if link.exists() or link.is_symlink():
            link.unlink()
        link.symlink_to(target.resolve())

    def _symlink_caps(self, combo: Combo, qdir: Path, nb_root: Path):
        for cap in self.CAPS_PART1 + self.CAPS_PART2:
            cap_dir = nb_root / cap
            if cap_dir.exists():
                self._symlink(qdir / cap, cap_dir)
                # Symlink imagens: gen/py.pt/cap01/imagens → all/cap01/imagens
                all_imagens = self.root / 'all' / cap / 'imagens'
                gen_imagens = nb_root / cap / 'imagens'
                if all_imagens.exists() and not gen_imagens.exists():
                    gen_imagens.symlink_to(all_imagens.resolve())

    def _ensure_preamble_files(self):
        """Cria arquivos de preâmbulo se não existirem"""
        includes_dir = self.root / 'includes'
        includes_dir.mkdir(exist_ok=True)
        

        # Cria preamble.tex para PDF
        preamble_tex = includes_dir / 'preamble.tex'
        if not preamble_tex.exists():
            preamble_tex.write_text(r'''
% Configuração para PDF com ABNT
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{amsmath}
\usepackage{amsfonts}
\usepackage{amssymb}

% Configuração de bibliografia para evitar erro do \printbibliography
\usepackage[backend=biber, style=abnt, citestyle=abnt, hyperref=true]{biblatex}
\addbibresource{references.bib}

% Redefine o comando de bibliografia
\renewbibmacro*{finentry}{\finentry}

% Comando seguro para bibliografia
\renewcommand{\printbibliography}{\printbibliography[title=Referências]}

% Ajustes para ABNT
\usepackage[brazilian]{babel}
\usepackage{csquotes}
''', encoding='utf-8')
            print('  ✓ Criado includes/preamble.tex')
        
        # Cria preamble.html para HTML
        preamble_html = includes_dir / 'preamble.html'
        if not preamble_html.exists():
            preamble_html.write_text('''
<!-- Configurações para HTML -->
<style>
code {
  font-size: 0.9em;
}
pre {
  background-color: #f5f5f5;
  padding: 1em;
  border-radius: 4px;
}
</style>
''', encoding='utf-8')
            print('  ✓ Criado includes/preamble.html')

    def _chapter_blocks(self, combo: Combo, nb_root: Path) -> str:
        parts = [
            (UI_STRINGS[combo.locale]['part_1'], self.CAPS_PART1),
            (UI_STRINGS[combo.locale]['part_2'], self.CAPS_PART2),
        ]
        blocks = []
        for title, caps in parts:
            chaps = []
            for cap in caps:
                nb_name = f'{cap}.{combo.key}.ipynb'
                if (nb_root / cap / nb_name).exists():
                    chaps.append(f'        - {cap}/{nb_name}')
            if chaps:
                blocks.append(
                    f'    - part: "{title}"\n      chapters:\n' +
                    '\n'.join(chaps)
                )
        blocks.append('    - referencias.qmd')
        return '\n'.join(blocks) if blocks else '    - index.qmd'


    def _quarto_yml(self, combo: Combo, nb_root: Path) -> str:
        lang_obj    = LANGUAGES[combo.lang]
        locale_obj  = LOCALES[combo.locale]
        lang_label  = lang_obj.label
        quarto_lang = locale_obj.quarto_lang

        subtitle = (UI_STRINGS[combo.locale]['book_subtitle']
                    .format(lang_label=lang_label))
        chapters = self._chapter_blocks(combo, nb_root)

        output_dir   = str((self.root / 'gen' / 'book' / combo.key).resolve())
        bib_path     = (self.root / 'references.bib').resolve()
        csl_path     = (self.root / 'includes' / 'abnt.csl').resolve()
        emoji_filter = (self.root / 'includes' / 'emoji-filter.lua').resolve()  # ← absoluto

        if not csl_path.exists():
            self._create_default_csl(csl_path)

        custom_filename = f"livro.{combo.file_key}"

        return f'''# Gerado por gerar_livro.py — NÃO editar manualmente.

project:
  type: book
  output-dir: "{output_dir}"

book:
  title: "Processamento Digital de Imagens e Visão Computacional"
  subtitle: "{subtitle}"
  author:
    - name: "Francisco de Assis Zampirolli"
      affiliation: "Universidade Federal do ABC"
  date: today
  language: {quarto_lang}
  downloads: [pdf]

  chapters:
    - index.qmd
    - prefacio.qmd
{chapters}


bibliography: "{bib_path}"
csl: "{csl_path}"

filters:
  - "{emoji_filter}"

format:
  html:
    theme: cosmo
    grid:
      body-width: 1100px
      sidebar-width: 250px
      margin-width: 250px
    toc: true
    toc-depth: 3
    number-sections: true
    code-fold: false
    code-tools: true
    code-copy: true
    highlight-style: github
    lang: {quarto_lang}
    include-in-header:
      text: |
        <style>
        code {{ font-size: 0.9em; }}
        pre {{ background-color: #f5f5f5; padding: 1em; border-radius: 4px; }}
        </style>

  pdf:
    documentclass: book
    classoption: [openany, oneside, 12pt, a4paper]
    geometry:
      - left=1.5cm
      - right=1.5cm
      - top=2.0cm
      - bottom=2.0cm
      - headheight=14pt
    lang: {quarto_lang}
    toc: true
    lot: true      # list of tables
    lof: true      # list of figures
    number-sections: true
    colorlinks: true
    linkcolor: blue
    urlcolor: blue
    pdf-engine: lualatex
    latex-auto-install: false
    latex-max-runs: 3
    keep-tex: true
    cite-method: citeproc

    include-in-header:
      - text: |
          \\usepackage{{url}}
          \\def\\UrlBreaks{{\\do\\/\\do-}}
          \\usepackage{{adjustbox}}
          \\def\\pandocbounded#1{{\\adjustbox{{max width=\\linewidth, keepaspectratio}}{{#1}}}}
          \\usepackage{{microtype}}
          \\usepackage{{amsmath,amssymb}}
          \\usepackage{{booktabs}}
          \\usepackage{{makecell}}
          \\renewcommand{{\\cellalign}}{{tl}}
          \\usepackage{{longtable}}
          \\usepackage{{array}}
          \\usepackage{{float}}
          \\usepackage{{subcaption}}
          \\usepackage{{xcolor}}
          \\usepackage{{fancyvrb}}
          \\usepackage{{csquotes}}
          \\usepackage{{emoji}}
          \\setemojifont{{TwemojiMozilla}}
          \\definecolor{{pdi-blue}}{{RGB}}{{21,101,192}}
          \\definecolor{{pdi-green}}{{RGB}}{{46,125,50}}
          \\definecolor{{darkblue}}{{RGB}}{{0,51,102}}


          \\usepackage{{fancyhdr}}
          \\pagestyle{{fancy}}
          \\fancyhf{{}}

          \\fancyhead[L]{{\\small\\textcolor{{darkblue}}{{\\textit{{Processamento Digital de Imagens e Visão Computacional}}}}}}
          \\fancyhead[R]{{\\small\\href{{https://github.com/fzampirolli/pdi-vc}}{{github.com/fzampirolli/pdi-vc}}}}
          \\fancyfoot[L]{{\\small\\textcolor{{darkblue}}{{\\textit{{UFABC}}}}}}
          \\fancyfoot[R]{{\\thepage}}
          \\renewcommand{{\\headrulewidth}}{{0.4pt}}
          \\renewcommand{{\\footrulewidth}}{{0.4pt}}
          \\fancypagestyle{{plain}}{{
            \\fancyhf{{}}
            \\fancyfoot[L]{{\\small\\textcolor{{darkblue}}{{\\textit{{UFABC}}}}}}
            \\fancyfoot[R]{{\\thepage}}
            \\renewcommand{{\\headrulewidth}}{{0pt}}
            \\renewcommand{{\\footrulewidth}}{{0.4pt}}
          }}

          \\usepackage{{titlesec}}
          \\titleformat{{\\chapter}}[display]
            {{\\normalfont\\huge\\bfseries\\color{{darkblue}}}}
            {{\\filleft\\Large\\chaptertitlename\\ \\thechapter}}
            {{1ex}}
            {{\\titlerule\\vspace{{2ex}}\\Huge\\filleft}}
            [{{\\vspace{{2ex}}}}]
          \\titlespacing*{{\\chapter}}{{0pt}}{{5pt}}{{20pt}}
          \\titleformat{{\\part}}[display]
            {{\\normalfont\\Huge\\bfseries\\color{{darkblue}}\\centering}}
            {{\\Large\\partname\\ \\thepart}}
            {{1ex}}
            {{\\titlerule[2pt]\\vspace{{2ex}}}}
            [{{\\vspace{{2ex}}\\titlerule[2pt]}}]
      - file: fvextra.tex

execute:
  freeze: false
  cache: false
  echo: true
  warning: false
  error: false
'''

    def _create_default_csl(self, csl_path: Path):
        """Cria um arquivo CSL básico se não existir"""
        csl_path.parent.mkdir(parents=True, exist_ok=True)
        csl_path.write_text('''<?xml version="1.0" encoding="utf-8"?>
<style xmlns="http://purl.org/net/xbiblio/csl" class="in-text" version="1.0" demote-non-dropping-particle="sort-only" default-locale="pt-BR">
  <info>
    <title>Associação Brasileira de Normas Técnicas (ABNT)</title>
    <id>http://www.zotero.org/styles/abnt</id>
    <link href="http://www.zotero.org/styles/abnt" rel="self"/>
    <author>
      <name>ABNT</name>
    </author>
    <category citation-format="author-date"/>
    <category field="engineering"/>
    <summary>Estilo ABNT para trabalhos acadêmicos</summary>
    <updated>2020-01-01T00:00:00+00:00</updated>
    <rights license="http://creativecommons.org/licenses/by-sa/3.0/">This work is licensed under a Creative Commons Attribution-ShareAlike 3.0 License</rights>
  </info>
  <macro name="author">
    <names variable="author">
      <name sort-separator=", " name-as-sort-order="all" et-al-min="3" et-al-use-first="1" et-al-subsequent-min="3" et-al-subsequent-use-first="1" delimiter=", "/>
      <label form="short" prefix=" (" suffix=")" strip-periods="true"/>
    </names>
  </macro>
  <macro name="title">
    <choose>
      <if type="book thesis" match="any">
        <text variable="title" font-style="italic"/>
      </if>
      <else>
        <text variable="title"/>
      </else>
    </choose>
  </macro>
  <citation et-al-min="3" et-al-use-first="1" disambiguate-add-year-suffix="true" disambiguate-add-names="true" disambiguate-add-givenname="true" collapse="year">
    <sort>
      <key variable="issued"/>
    </sort>
    <layout prefix="(" suffix=")" delimiter="; ">
      <group delimiter=", ">
        <text macro="author"/>
        <date variable="issued">
          <date-part name="year"/>
        </date>
      </group>
    </layout>
  </citation>
  <bibliography hanging-indent="true" et-al-min="3" et-al-use-first="1">
    <sort>
      <key macro="author"/>
      <key variable="issued"/>
    </sort>
    <layout>
      <text macro="author"/>
      <date variable="issued" prefix=" (" suffix=")">
        <date-part name="year"/>
      </date>
      <text macro="title" prefix=". "/>
      <text variable="container-title" prefix=". " font-style="italic"/>
      <text variable="volume" prefix=". "/>
      <text variable="page" prefix=". "/>
      <text variable="DOI" prefix=". doi:"/>
    </layout>
  </bibliography>
</style>''', encoding='utf-8')
        print(f'  ✓ Criado CSL padrão: {csl_path}')


# ─────────────────────────────────────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────────────────────────────────────

# Em render_quarto — corrigir onde procura o PDF:


import subprocess
import os
from pathlib import Path

def _get_quarto_latex_path() -> str | None:
    """Descobre o path do LaTeX que o Quarto usa (TinyTeX)."""
    try:
        r = subprocess.run(
            ['quarto', 'run', '--help'],  # qualquer chamada quarto
            capture_output=True, text=True
        )
    except FileNotFoundError:
        return None
    
    # TinyTeX fica em ~/Library/TinyTeX em macOS e Linux
    candidates = [
        Path.home() / 'Library' / 'TinyTeX' / 'bin' / 'universal-darwin',
        Path.home() / '.TinyTeX' / 'bin' / 'x86_64-linux',
        Path.home() / '.TinyTeX' / 'bin' / 'aarch64-linux',
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    return None

def _screenshot_html_cells(qdir: Path, all_root: Path):
    """Lê notebooks ORIGINAIS de all/ para gerar screenshots."""
    import nbformat
    import re
    from playwright.sync_api import sync_playwright

    # Descobre os caps disponíveis em qdir
    for cap_link in qdir.iterdir():
        if not re.match(r'cap\d+', cap_link.name):
            continue
        cap = cap_link.name
        img_dir = all_root / cap / 'imagens'
        img_dir.mkdir(parents=True, exist_ok=True)

        # Lê notebooks ORIGINAIS de all/capXX/
        for nb_path in (all_root / cap).glob('*.ipynb'):
            nb = nbformat.read(nb_path, as_version=4)

            for cell in nb.cells:
                if cell.cell_type != 'code':
                    continue
                if 'HTML("""' not in cell.source and "HTML('''" not in cell.source:
                    continue

                # Extrai label
                label = None
                for line in cell.source.splitlines():
                    m = re.match(r'#\|\s*label:\s*(\S+)', line)
                    if m:
                        label = m.group(1)
                        break
                if not label:
                    continue

                png_path = img_dir / f'{label}.png'
                if png_path.exists():
                    print(f'  ✓ Screenshot já existe: {png_path.name}')
                    continue

                # Extrai HTML
                m = re.search(r'HTML\("""(.*?)"""\)', cell.source, re.DOTALL)
                if not m:
                    m = re.search(r"HTML\('''(.*?)'''\)", cell.source, re.DOTALL)
                if not m:
                    continue

                html_content = m.group(1)
                tmp_html = qdir / f'_tmp_{label}.html'
                tmp_html.write_text(f'''<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>body {{ margin: 0; background: white; }}</style>
</head><body>{html_content}</body></html>''', encoding='utf-8')

                try:
                    with sync_playwright() as p:
                        browser = p.chromium.launch()
                        page = browser.new_page(viewport={'width': 900, 'height': 600})
                        page.goto(f'file://{tmp_html.resolve()}')
                        page.wait_for_timeout(1500)
                        page.screenshot(path=str(png_path), full_page=False)
                        browser.close()
                    print(f'  📸 Screenshot: {png_path.name}')
                except Exception as e:
                    print(f'  ⚠ Falha screenshot {label}: {e}')
                finally:
                    tmp_html.unlink(missing_ok=True)


def _fix_html_outputs_for_pdf(nb_root: Path):
    """Remove 'text/plain: <IPython.core.display.HTML object>' de todos os outputs."""
    import nbformat
    import os

    for root, dirs, files in os.walk(nb_root, followlinks=True):
        for fname in files:
            if not fname.endswith('.ipynb'):
                continue
            nb_path = Path(root) / fname
            nb = nbformat.read(nb_path, as_version=4)
            modified = False

            for cell in nb.cells:
                if cell.cell_type != 'code':
                    continue
                for output in cell.outputs:
                    data = output.get('data', {})
                    if data.get('text/plain', '') == '<IPython.core.display.HTML object>':
                        del output['data']['text/html']
                        data['text/plain'] = ''
                        modified = True

            if modified:
                nbformat.write(nb, nb_path)
                print(f'  ✓ HTML outputs limpos: {fname}')

def _patch_html_cells_for_pdf(qdir: Path, all_root: Path = Path('all')):
    import nbformat
    import re

    nb_root = qdir.parent.parent / qdir.name  # gen/py.pt

    for nb_path in nb_root.rglob('*.ipynb'):
        real_path = nb_path.resolve()
        nb = nbformat.read(real_path, as_version=4)
        modified = False
        new_cells = []

        for cell in nb.cells:
            if cell.cell_type != 'code' or (
                'HTML("""' not in cell.source and "HTML('''" not in cell.source
            ):
                new_cells.append(cell)
                continue

            # Extrai label e fig-cap dos metadados da célula
            label = None
            fig_cap = None
            for line in cell.source.splitlines():
                m = re.match(r'#\|\s*label:\s*(\S+)', line)
                if m:
                    label = m.group(1)
                m = re.match(r'#\|\s*fig-cap:\s*["\']?(.*?)["\']?\s*$', line)
                if m:
                    fig_cap = m.group(1).strip('"\'')

            if not label:
                # Limpa output salvo (Quarto re-executa no HTML)
                cell.outputs = []
                cell.execution_count = None
                # Célula de código original (sem alteração)
                new_cells.append(cell)
                continue

            # Descobre o cap pelo caminho do notebook
            cap = None
            for part in nb_path.parts:
                if re.match(r'cap\d+', part):
                    cap = part
                    break

            # Caminho relativo da imagem a partir do notebook
            png_rel = f'imagens/{label}.png'
            png_abs = all_root / cap / png_rel if cap else None
            png_exists = png_abs and png_abs.exists()

            if png_exists:
                # Célula markdown: abre bloco html-only
                new_cells.append(nbformat.v4.new_markdown_cell(
                    '::: {.content-visible when-format="html"}'
                ))

                # Célula de código original (sem alteração)
                cell.outputs = []
                cell.execution_count = None
                new_cells.append(cell)

                # Célula markdown: fecha html-only, abre pdf-only com imagem
                cap_str = fig_cap or label
                new_cells.append(nbformat.v4.new_markdown_cell(
                    f':::\n\n'
                    f'::: {{.content-visible when-format="pdf"}}\n'
                    f'![ {cap_str} ]({png_rel}){{#fig-{label[4:]}}}\n'
                    f':::'
                ))
                modified = True
                print(f'  ✓ Patch condicional: {label}')
            else:
                # Sem PNG: só esconde no PDF
                new_cells.append(nbformat.v4.new_markdown_cell(
                    '::: {.content-visible when-format="html"}'
                ))
                new_cells.append(cell)
                new_cells.append(nbformat.v4.new_markdown_cell(':::'))
                modified = True
                print(f'  ⚠ Patch sem imagem: {label}')

        if modified:
            nb.cells = new_cells
            # Salva diretamente no arquivo real (gen/py.pt/capXX/)
            nbformat.write(nb, nb_path)
            print(f'  ✓ Notebook patcheado: {nb_path.name}')


def render_quarto(qdir: Path, fmt: str, all_root: Path = Path('all'), verbose: bool = False):
    
    fmts = ['html', 'pdf'] if fmt == 'all' else [fmt]
    
    combo_name = qdir.name          # ← adicionar: ex: "py.pt"
    parts = combo_name.split('.')
    file_key = f'{parts[1]}.{parts[0]}'  # ← adicionar: ex: "pt.py"

    env = os.environ.copy()
    tinytex_path = _get_quarto_latex_path()
    if tinytex_path:
        env['PATH'] = tinytex_path + ':' + env['PATH']

    for f in fmts:

        if f == 'pdf':
            nb_root = qdir.parent.parent / qdir.name  # gen/py.pt
            _screenshot_html_cells(qdir, all_root)
            _fix_html_outputs_for_pdf(nb_root)
            _patch_html_cells_for_pdf(qdir, all_root)
            env['QUARTO_FMT'] = 'pdf'
            
        print(f'  $ cd {qdir.name} && quarto render --to {f}')
        try:
            r = subprocess.run(
                ['quarto', 'render', '--to', f] +
                (['--pdf-engine', 'lualatex'] if f == 'pdf' else []),
                cwd=qdir,
                capture_output=not verbose,
                text=True,
                timeout=600,
                env=env,
            )
            if r.returncode != 0:
                print(f'  ⚠ Erro ao renderizar {f}:')
                for line in (r.stderr or '').split('\n')[-10:]:
                    if line.strip():
                        print(f'      {line}')
            else:
                if f == 'pdf':
                    _rename_pdf(qdir, combo_name, file_key)
                else:
                    print(f'  ✓ html → gen/book/{combo_name}/')

        except FileNotFoundError:
            print('  ⚠ quarto não encontrado no PATH')
        except subprocess.TimeoutExpired:
            print('  ⚠ Timeout ao renderizar (mais de 600 segundos)')


def _rename_pdf(qdir: Path, combo_name: str, file_key: str):
    """
    Quarto Book gera o PDF no output-dir com nome imprevisível.
    Procura qualquer .pdf gerado e renomeia para livro.<file_key>.pdf
    """
    output_dir = qdir.parent.parent / 'book' / combo_name  # ← era .parent.parent.parent
    target = output_dir / f'livro.{file_key}.pdf'

    if not output_dir.exists():
        print(f'  ⚠ output-dir não encontrado: {output_dir}')
        return

    # Quarto pode gerar "index.pdf" ou slug do título
    candidates = sorted(output_dir.glob('*.pdf'))
    
    if not candidates:
        print(f'  ⚠ Nenhum PDF encontrado em {output_dir}')
        print(f'    Conteúdo: {[p.name for p in output_dir.iterdir()]}')
        return

    # Remove o próprio target dos candidatos para não confundir com o PDF gerado
    candidates = [c for c in candidates if c != target]
    if not candidates:
        print(f'  ✓ PDF já existe com nome correto: {target}')
        return
    
    # Renomeia o mais recente (não o mais antigo)
    generated = max(candidates, key=lambda p: p.stat().st_mtime)
    shutil.move(str(generated), str(target))
    print(f'  ✓ PDF renomeado: {generated.name} → {target.name}')