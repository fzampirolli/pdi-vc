"""
pipeline/quarto_builder.py
===========================
Constrói uma pasta Quarto auto-suficiente para cada combo:

    gen/quarto/<combo>/
        _quarto.yml      ← gerado aqui
        index.qmd        ← gerado aqui (idioma correto)
        prefacio.qmd     ← gerado aqui (prefácio do livro)
        capa.tex         ← gerado aqui (capa do PDF, via include-before-body)
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
        content = prefacio_path.read_text(encoding='utf-8')
        print(f'  ✓ Prefácio lido de {prefacio_path}')
        lang_label = LANGUAGES[combo.lang].label
        content = content.replace('{{lang_label}}', lang_label)
        locale_label = LOCALES[combo.locale].label
        content = content.replace('{{locale_label}}', locale_label)
        return content
    else:
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

    for cap in ['cap01', 'cap02', 'cap03', 'cap04', 'cap05', 'cap06', 'cap07', 'cap08']:
        cap_dir = all_root / cap
        if not cap_dir.exists():
            continue

        for attachment in cap_dir.glob('*'):
            if attachment.is_file() and attachment.suffix in ['.png', '.jpg', '.jpeg', '.gif', '.csv', '.txt', '.pdf']:
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
        nb_root = nb_root or (self.root / DIR_GEN / combo.key)
        all_root = all_root or (self.root / 'all')
        qdir    = self.root / DIR_GEN / 'quarto' / combo.key
        qdir.mkdir(parents=True, exist_ok=True)

        (qdir / 'index.qmd').write_text(_index_qmd(combo), encoding='utf-8')
        (qdir / 'prefacio.qmd').write_text(_prefacio_qmd(combo), encoding='utf-8')
        (qdir / 'referencias.qmd').write_text(_refs_qmd(combo), encoding='utf-8')

        self._write_custom_css(qdir)

        self._symlink_caps(combo, qdir, nb_root)
        _process_attachments(combo, nb_root, qdir, all_root)

        self._symlink(qdir / 'references.bib', self.root / 'references.bib')
        self._symlink(qdir / 'includes',       self.root / 'includes')

        self._ensure_preamble_files()

        # ── Gera capa.tex para o PDF (include-before-body) ───────────────────
        cover_abs = (self.root / 'includes' / 'capa_girassol.png').resolve()
        self._write_cover_tex(qdir, cover_abs)

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
                all_imagens = self.root / 'all' / cap / 'imagens'
                gen_imagens = nb_root / cap / 'imagens'
                if all_imagens.exists() and not gen_imagens.exists():
                    gen_imagens.symlink_to(all_imagens.resolve())

    def _write_cover_tex(self, qdir: Path, cover_abs: Path):
        """
        Salva o path da capa para uso no pós-processamento do .tex.
        O cover_hook.tex é um marcador vazio — a capa é injetada por _fix_tex_cover().
        """
        (qdir / 'cover_hook.tex').unlink(missing_ok=True)
        (qdir / 'cover_hook.tex').write_text('', encoding='utf-8')

        # Salva o path para uso posterior em _fix_tex_cover
        (qdir / '.cover_abs').write_text(str(cover_abs), encoding='utf-8')
        # cover_hook.tex vazio — só carrega etoolbox sem fazer nada
        (qdir / 'cover_hook.tex').write_text('', encoding='utf-8')

        print('  ✓ Gerado cover_hook.tex')
        
    def _write_custom_css(self, qdir: Path):
        """
        Gera custom.css no qdir. Carregado via 'css:' no _quarto.yml,
        o que garante que ele vem DEPOIS do Bootstrap/Cosmo e vence
        qualquer regra do tema sem precisar de !important em tudo.
        """
        css = """\
/* ═══════════════════════════════════════════════════════════════
PDI+VC — custom.css   (gerado automaticamente)
═══════════════════════════════════════════════════════════════ */

/* ── Tipografia ─────────────────────────────────────────────── */
body, .quarto-title {
font-family: 'Source Serif 4', Georgia, serif;
}
code, pre, .sourceCode {
font-family: 'JetBrains Mono', monospace;
font-size: 0.875em;
}

/* ── Sidebar ─────────────────────────────────────────────────── */
#quarto-sidebar {
background: #2c3e55 !important;
}
#quarto-sidebar .sidebar-title a,
#quarto-sidebar .sidebar-title {
color: #fde8c0 !important;
font-weight: 700;
}
#quarto-sidebar a,
.sidebar-navigation .sidebar-item-text,
.sidebar-navigation a {
color: #c8ddf0 !important;
}
#quarto-sidebar a:hover,
.sidebar-navigation a:hover,
.sidebar-navigation .sidebar-item-text:hover {
color: #ffe0a0 !important;
background: rgba(255,255,255,0.09) !important;
border-radius: 4px;
}
.sidebar-item.sidebar-item-section > .sidebar-item-text {
color: #ffc97a !important;
font-weight: 600;
letter-spacing: 0.04em;
}
.sidebar-item .chapter-number {
color: #90b8d8 !important;
}

/* ── Títulos ─────────────────────────────────────────────────── */
h1, h2, h3 { color: #1a3a5c; }
h1 { border-bottom: 3px solid #f0c060; padding-bottom: 0.3em; }

/* ── Callouts ────────────────────────────────────────────────── */
.callout { border-left-width: 5px; border-radius: 4px; }

/* ── Código-fonte (input) ────────────────────────────────────── */
div.sourceCode {
  background: #f0f4ff !important;
  border-radius: 8px !important;
  border: 1px solid #c8d4f0 !important;
  border-left: 4px solid #7090d0 !important;
  box-shadow: none !important;
}
div.sourceCode pre,
div.sourceCode pre code {
  background: #f0f4ff !important;
  color: #1a2050 !important;
  border: none !important;
  box-shadow: none !important;
}

/* ── Outputs das células ─────────────────────────────────────── */
/* stdout / texto — âmbar pastel, UMA única borda */
.cell-output pre,
.cell-output code,
[class^="cell-output"] pre,
[class*=" cell-output"] pre {
  background:    #fdf6ec !important;
  color:         #2e1e05 !important;
  border:        1px solid #e8d8b8 !important;
  border-left:   4px solid #e8a840 !important;
  border-radius: 6px !important;
  padding:       0.75em 1em !important;
  font-family:   'JetBrains Mono', monospace !important;
  font-size:     0.83em !important;
  line-height:   1.55 !important;
  white-space:   pre-wrap !important;
}

/* stderr — rosado */
.cell-output-stderr pre,
.cell-output-stderr code {
  background:  #fff2f0 !important;
  color:       #5a1a10 !important;
  border:      1px solid #f0c8c0 !important;
  border-left: 4px solid #e06050 !important;
}

/* display_data (imagens, DataFrames, HTML rico):
   SEM borda própria — o pre interno já tem a borda âmbar acima.
   Isso elimina a faixa dupla. */
.cell-output-display {
  background:    transparent !important;
  border:        none !important;
  border-radius: 0 !important;
  padding:       0 !important;
  margin-top:    0.3em !important;
}
/* reseta o pre dentro de display para não herdar borda do pai */
.cell-output-display > pre,
.cell-output-display pre {
  background:  #fdf6ec !important;
  color:       #2e1e05 !important;
  border:      1px solid #e8d8b8 !important;
  border-left: 4px solid #e8a840 !important;
  border-radius: 6px !important;
  padding:     0.75em 1em !important;
}
/* imagens ficam sem caixa */
.cell-output-display img {
  background:    transparent;
  border-radius: 4px;
  display:       block;
}

/* ── Tabelas ─────────────────────────────────────────────────── */
table { border-collapse: collapse; width: 100%; }
thead tr { background: #2c4a6a !important; color: #faf0e0 !important; }
tbody tr:nth-child(even) { background: #f5f0e8; }
td, th { padding: 0.5em 0.8em; border: 1px solid #d0c8b8; }

/* ── Capa ────────────────────────────────────────────────────── */
.quarto-cover-image {
border-radius: 8px;
box-shadow: 0 8px 32px rgba(0,0,0,0.28);
max-height: 480px;
object-fit: cover;
}
"""
        (qdir / 'custom.css').write_text(css, encoding='utf-8')
        print('  ✓ Gerado custom.css')

    def _ensure_preamble_files(self):
        """Cria arquivos de preâmbulo se não existirem"""
        includes_dir = self.root / 'includes'
        includes_dir.mkdir(exist_ok=True)

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

\renewbibmacro*{finentry}{\finentry}
\renewcommand{\printbibliography}{\printbibliography[title=Referências]}

\usepackage[brazilian]{babel}
\usepackage{csquotes}
''', encoding='utf-8')
            print('  ✓ Criado includes/preamble.tex')

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
        emoji_filter = (self.root / 'includes' / 'emoji-filter.lua').resolve()
        cover_abs    = (self.root / 'includes' / 'capa_girassol.png').resolve()

        if not csl_path.exists():
            self._create_default_csl(csl_path)

        custom_filename = f"livro.{combo.file_key}"

        # NOTA: A capa do PDF é gerada via capa.tex (include-before-body).
        # NÃO use \AtBeginDocument no include-in-header para isso — o Quarto/Pandoc
        # insere conteúdo antes de \AtBeginDocument ser disparado, empurrando a capa
        # para a página 2. O include-before-body injeta o conteúdo imediatamente
        # após \begin{document}, garantindo que seja a primeira página.

        return f'''# Gerado por gerar_livro.py — NÃO editar manualmente.

project:
  type: book
  output-dir: "{output_dir}"

book:
  title: "Processamento Digital de Imagens e Visão Computacional"
  cover-image: "includes/capa_girassol.png"
  subtitle: "{subtitle}"
  author:
    - name: "Francisco de Assis Zampirolli"
      affiliation: "Universidade Federal do ABC"
  date: today
  language: {quarto_lang}
  downloads: [pdf]
  output-file: "livro.{combo.file_key}"

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
    css: custom.css          # ← carregado após o tema, vence Bootstrap
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
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link href="https://fonts.googleapis.com/css2?family=Source+Serif+4:ital,opsz,wght@0,8..60,300..900;1,8..60,300..900&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
        <script>
        document.addEventListener('DOMContentLoaded', function() {{
          document.querySelectorAll('a[href="./"], a[href="."]').forEach(function(a) {{
            a.setAttribute('href', '../index.html');
          }});
        }});
        </script>
  pdf:
    documentclass: book
    classoption: [openany, oneside, 12pt, a4paper]
    title-page: false
    output-file: "livro.{combo.file_key}.pdf"
    geometry:
      - left=1.5cm
      - right=1.5cm
      - top=2.0cm
      - bottom=2.0cm
      - headheight=14pt
    lang: {quarto_lang}
    toc: true
    lot: true
    lof: true
    number-sections: true
    colorlinks: true
    linkcolor: blue
    urlcolor: blue
    pdf-engine: lualatex
    latex-auto-install: false
    latex-max-runs: 3
    keep-tex: true
    cite-method: citeproc

    # ── Capa: injetada ANTES do corpo, garantindo página 1 ───────────────────
    # include-before-body é processado imediatamente após \\begin{{document}},
    # antes de qualquer conteúdo gerado pelo Pandoc — ao contrário de
    # \\AtBeginDocument (que chega tarde demais no fluxo do book).


    include-in-header:
      - file: cover_hook.tex
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
          \\usepackage{{graphicx}}
          \\usepackage{{geometry}}
          \\definecolor{{pdi-blue}}{{RGB}}{{21,101,192}}
          \\definecolor{{pdi-green}}{{RGB}}{{46,125,50}}
          \\definecolor{{darkblue}}{{RGB}}{{0,51,102}}
          \\definecolor{{codebg}}{{RGB}}{{240,244,255}}
          \\definecolor{{codeborder}}{{RGB}}{{112,144,208}}
          \\definecolor{{outputbg}}{{RGB}}{{253,246,236}}
          \\definecolor{{outputborder}}{{RGB}}{{232,168,64}}
          \\usepackage[skins,breakable]{{tcolorbox}}
          \\tcbset{{pdicode/.style={{enhanced,breakable,colback=codebg,colframe=codeborder,leftrule=4pt,rightrule=0.4pt,toprule=0.4pt,bottomrule=0.4pt,arc=4pt,boxsep=0pt,left=6pt,right=6pt,top=4pt,bottom=4pt,fontupper=\\small\\ttfamily}}}}
          \\tcbset{{pdioutput/.style={{enhanced,breakable,colback=outputbg,colframe=outputborder,leftrule=4pt,rightrule=0.4pt,toprule=0.4pt,bottomrule=0.4pt,arc=4pt,boxsep=0pt,left=6pt,right=6pt,top=4pt,bottom=4pt,fontupper=\\small\\ttfamily}}}}
          \\renewenvironment{{Shaded}}{{\\begin{{tcolorbox}}[pdicode]}}{{\\end{{tcolorbox}}}}
          \\usepackage{{alltt}}
          \\renewenvironment{{verbatim}}{{\\begin{{tcolorbox}}[pdioutput]\\begin{{alltt}}}}{{\\end{{alltt}}\\end{{tcolorbox}}}}
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

import subprocess
import os
from pathlib import Path

def _get_quarto_latex_path() -> str | None:
    """Descobre o path do LaTeX que o Quarto usa (TinyTeX)."""
    try:
        subprocess.run(['quarto', 'run', '--help'], capture_output=True, text=True)
    except FileNotFoundError:
        return None

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

    for cap_link in qdir.iterdir():
        if not re.match(r'cap\d+', cap_link.name):
            continue
        cap = cap_link.name
        img_dir = all_root / cap / 'imagens'
        img_dir.mkdir(parents=True, exist_ok=True)

        for nb_path in (all_root / cap).glob('*.ipynb'):
            nb = nbformat.read(nb_path, as_version=4)

            for cell in nb.cells:
                if cell.cell_type != 'code':
                    continue
                if 'HTML("""' not in cell.source and "HTML('''" not in cell.source:
                    continue

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

    nb_root = qdir.parent.parent / qdir.name

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
                cell.outputs = []
                cell.execution_count = None
                new_cells.append(cell)
                continue

            cap = None
            for part in nb_path.parts:
                if re.match(r'cap\d+', part):
                    cap = part
                    break

            png_rel = f'imagens/{label}.png'
            png_abs = all_root / cap / png_rel if cap else None
            png_exists = png_abs and png_abs.exists()

            if png_exists:
                new_cells.append(nbformat.v4.new_markdown_cell(
                    '::: {.content-visible when-format="html"}'
                ))
                cell.outputs = []
                cell.execution_count = None
                new_cells.append(cell)
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
                new_cells.append(nbformat.v4.new_markdown_cell(
                    '::: {.content-visible when-format="html"}'
                ))
                new_cells.append(cell)
                new_cells.append(nbformat.v4.new_markdown_cell(':::'))
                modified = True
                print(f'  ⚠ Patch sem imagem: {label}')

        if modified:
            nb.cells = new_cells
            nbformat.write(nb, nb_path)
            print(f'  ✓ Notebook patcheado: {nb_path.name}')

def _render_pdf_with_patched_tex(qdir: Path, env: dict):
    """
    1. Quarto render --to latex  → gera o .tex
    2. _fix_tex_cover()          → patcha capa + maketitle
    3. lualatex (3x)             → compila o PDF final
    4. _rename_pdf()             → renomeia para livro.<file_key>.pdf
    """
    combo_name = qdir.name
    parts = combo_name.split('.')
    file_key = f'{parts[1]}.{parts[0]}'
    output_dir = qdir.parent.parent / 'book' / combo_name

    print(f'  $ cd {qdir.name} && quarto render --to latex')
    r = subprocess.run(
        ['quarto', 'render', '--to', 'latex'],
        cwd=qdir,
        capture_output=True,
        text=True,
        timeout=600,
        env=env,
    )
    if r.returncode != 0:
        print('  ⚠ Erro ao gerar .tex:')
        for line in (r.stderr or '').split('\n')[-10:]:
            if line.strip():
                print(f'      {line}')
        return

    _fix_tex_cover(qdir)

    tex_files = [t for t in qdir.glob('*.tex')
                 if t.name not in ('cover_hook.tex', 'fvextra.tex')]
    if not tex_files:
        print('  ⚠ .tex não encontrado após patch')
        return

    tex_path = tex_files[0]
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f'  $ lualatex (3x) {tex_path.name}')
    for run in range(3):
        r = subprocess.run(
            ['lualatex', '--interaction=nonstopmode',
             f'--output-directory={output_dir}', str(tex_path)],
            cwd=qdir,
            capture_output=True,
            text=True,
            timeout=300,
            env=env,
        )
        if r.returncode != 0 and run == 2:
            print('  ⚠ Erro no lualatex:')
            for line in (r.stdout or '').split('\n')[-15:]:
                if line.strip():
                    print(f'      {line}')

    _rename_pdf(qdir, combo_name, file_key)


def _fix_tex_cover(qdir: Path):
    """..."""
    cover_abs_file = qdir / '.cover_abs'
    if not cover_abs_file.exists():
        print('  ⚠ .cover_abs não encontrado, pulando patch do .tex')
        return
    cover_abs = cover_abs_file.read_text(encoding='utf-8').strip()
    tex_files = [t for t in qdir.glob('*.tex')
                 if t.name not in ('cover_hook.tex', 'fvextra.tex')]
    if not tex_files:
        print('  ⚠ Nenhum .tex encontrado para patch')
        return
    tex_path = tex_files[0]
    content = tex_path.read_text(encoding='utf-8')
    
    # DEBUG: mostrar todas as ocorrências de titlepage e maketitle
    import re
    for i, line in enumerate(content.split('\n')):
        if any(x in line for x in ['titlepage', 'maketitle', 'capa', 'cover', 'AfterEnd', 'begin{document']):
            print(f'  DEBUG linha {i}: {line.strip()}')


    cover_block = rf"""
% ── Capa ─────────────────────────────────────────────────────────
\begin{{titlepage}}%
\thispagestyle{{empty}}%
\newgeometry{{margin=0pt}}%
\noindent%
\includegraphics[width=\paperwidth,height=\paperheight,keepaspectratio=false]{{{cover_abs}}}%
\begin{{picture}}(0,0)
  \put(-10,180){{%
    \begin{{minipage}}[b]{{0.92\paperwidth}}\centering
      {{\fontsize{{26}}{{31}}\selectfont\bfseries\color{{white}}%
        Processamento Digital de Imagens\\[0.35em]%
        e Visão Computacional\par}}%
      \vspace{{0.8em}}%
      {{\large\color{{white}}%
        Francisco de Assis Zampirolli\\[0.15em]%
        Universidade Federal do ABC\par}}%
    \end{{minipage}}%
  }}
\end{{picture}}
\restoregeometry%
\end{{titlepage}}%
\maketitle
\pagenumbering{{arabic}}
"""
    # Remove todas as capas já existentes (vindas do cover_hook.tex ou de runs anteriores)
    import re
    content = re.sub(
        r'\\begin\{titlepage\}.*?\\end\{titlepage\}%?\s*',
        '',
        content,
        flags=re.DOTALL
    )
    # Remove \maketitle soltos
    content = content.replace(r'\maketitle', '')

    # Insere capa + maketitle uma única vez após \begin{document}
    content = content.replace(
        r'\begin{document}',
        r'\begin{document}' + '\n\\pagenumbering{gobble}\n' + cover_block,
        1
    )
    tex_path.write_text(content, encoding='utf-8')
    print(f'  ✓ .tex patcheado: {tex_path.name}')


def _render_pdf_with_patched_tex(qdir: Path, env: dict):
    """..."""
    combo_name = qdir.name
    parts = combo_name.split('.')
    file_key = f'{parts[1]}.{parts[0]}'
    output_dir = qdir.parent.parent / 'book' / combo_name

    print(f'  $ cd {qdir.name} && quarto render --to latex')
    r = subprocess.run(
        ['quarto', 'render', '--to', 'latex'],
        cwd=qdir,
        capture_output=True,
        text=True,
        timeout=600,
        env=env,
    )
    if r.returncode != 0:
        print('  ⚠ Erro ao gerar .tex:')
        for line in (r.stderr or '').split('\n')[-10:]:
            if line.strip():
                print(f'      {line}')
        return

    _fix_tex_cover(qdir)

    tex_files = [t for t in qdir.glob('*.tex')
                 if t.name not in ('cover_hook.tex', 'fvextra.tex')]
    if not tex_files:
        print('  ⚠ .tex não encontrado após patch')
        return

    tex_path = tex_files[0]
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f'  $ lualatex (3x) {tex_path.name}')
    for run in range(3):
        r = subprocess.run(
            ['lualatex', '--interaction=nonstopmode',
             f'--output-directory={output_dir}', str(tex_path)],
            cwd=qdir,
            capture_output=True,
            text=True,
            timeout=300,
            env=env,
        )
        if r.returncode != 0 and run == 2:
            print('  ⚠ Erro no lualatex:')
            for line in (r.stdout or '').split('\n')[-15:]:
                if line.strip():
                    print(f'      {line}')

    # Remove a primeira página em branco do PDF gerado
    pdf_files = list(output_dir.glob('*.pdf'))
    if pdf_files:
        pdf_path = max(pdf_files, key=lambda p: p.stat().st_mtime)
        try:
            from pypdf import PdfReader, PdfWriter
            reader = PdfReader(str(pdf_path))
            writer = PdfWriter()
            for page in reader.pages[1:]:  # pula página 0 (em branco)
                writer.add_page(page)
            with open(str(pdf_path), 'wb') as f:
                writer.write(f)
            print(f'  ✓ Página em branco removida: {pdf_path.name}')
        except Exception as e:
            print(f'  ⚠ Falha ao remover página em branco: {e}')

    _rename_pdf(qdir, combo_name, file_key)

def render_quarto(qdir: Path, fmt: str, all_root: Path = Path('all'), verbose: bool = False):

    fmts = ['html', 'pdf'] if fmt == 'all' else [fmt]

    combo_name = qdir.name
    parts = combo_name.split('.')
    file_key = f'{parts[1]}.{parts[0]}'

    env = os.environ.copy()
    tinytex_path = _get_quarto_latex_path()
    if tinytex_path:
        env['PATH'] = tinytex_path + ':' + env['PATH']

    for f in fmts:

        if f == 'pdf':
            nb_root = qdir.parent.parent / qdir.name
            _screenshot_html_cells(qdir, all_root)
            _fix_html_outputs_for_pdf(nb_root)
            _patch_html_cells_for_pdf(qdir, all_root)
            env['QUARTO_FMT'] = 'pdf'
            # Quarto gera o .tex com keep-tex:true antes de compilar;
            # rodamos quarto render --to latex primeiro para obter o .tex,
            # patcheamos, depois compilamos manualmente com lualatex.
            _render_pdf_with_patched_tex(qdir, env)
            continue  # pula o subprocess.run genérico abaixo

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
    output_dir = qdir.parent.parent / 'book' / combo_name
    target = output_dir / f'livro.{file_key}.pdf'

    if not output_dir.exists():
        print(f'  ⚠ output-dir não encontrado: {output_dir}')
        return

    candidates = sorted(output_dir.glob('*.pdf'))

    if not candidates:
        print(f'  ⚠ Nenhum PDF encontrado em {output_dir}')
        print(f'    Conteúdo: {[p.name for p in output_dir.iterdir()]}')
        return

    candidates = [c for c in candidates if c != target]
    if not candidates:
        print(f'  ✓ PDF já existe com nome correto: {target}')
        return

    generated = max(candidates, key=lambda p: p.stat().st_mtime)
    shutil.move(str(generated), str(target))
    print(f'  ✓ PDF renomeado: {generated.name} → {target.name}')