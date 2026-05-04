"""
pipeline/quarto_builder.py
===========================
Constrói uma pasta Quarto auto-suficiente para cada combo:

    gen/quarto/<combo>/
        _quarto.yml      ← gerado aqui
        index.qmd        ← gerado aqui (idioma correto)
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
        return '\n'.join(blocks) if blocks else '    - index.qmd'

    def _quarto_yml(self, combo: Combo, nb_root: Path) -> str:
        lang_obj    = LANGUAGES[combo.lang]
        locale_obj  = LOCALES[combo.locale]
        lang_label  = lang_obj.label
        quarto_lang = locale_obj.quarto_lang

        subtitle = (UI_STRINGS[combo.locale]['book_subtitle']
                    .format(lang_label=lang_label))
        chapters = self._chapter_blocks(combo, nb_root)

        # output-dir absoluto
        output_dir = str((self.root / 'gen' / 'book' / combo.key).resolve())

        # Caminhos absolutos para bib e csl (evita problemas)
        bib_path = (self.root / 'references.bib').resolve()
        csl_path = (self.root / 'includes' / 'abnt.csl').resolve()
        
        # Verifica se CSL existe, se não, cria um básico
        if not csl_path.exists():
            self._create_default_csl(csl_path)

        html_inc = ('    include-in-header: includes/preamble.html\n'
                    if (self.root / 'includes' / 'preamble.html').exists() else '')
        pdf_inc  = ('    include-in-header: includes/preamble.tex\n'
                    if (self.root / 'includes' / 'preamble.tex').exists() else '')

        return f'''# Gerado por gerar_livro.py — NÃO editar manualmente.
# Render: cd gen/quarto/{combo.key} && quarto render --to html

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
{chapters}
  appendices:
    - referencias.qmd

bibliography: "{bib_path}"
csl: "{csl_path}"

format:
  html:
    theme: cosmo
    toc: true
    toc-depth: 3
    number-sections: true
    code-fold: false
    code-tools: true
    code-copy: true
    highlight-style: github
    lang: {quarto_lang}
{html_inc}
  pdf:
    documentclass: book
    classoption: [openany, oneside, 12pt, a4paper]
    lang: {quarto_lang}
    toc: true
    number-sections: true
    colorlinks: true
    linkcolor: blue
    urlcolor: blue
    pdf-engine: pdflatex
    cite-method: biblatex
    biblio-style: abnt
    biblatexoptions:
      - backend=biber
      - style=abnt
      - citestyle=abnt
{pdf_inc}

execute:
  freeze: auto
  cache: true
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

def render_quarto(qdir: Path, fmt: str, verbose: bool = False):
    """cd qdir && quarto render --to <fmt>"""
    fmts = ['html', 'pdf'] if fmt == 'all' else [fmt]
    for f in fmts:
        print(f'  $ cd {qdir.name} && quarto render --to {f}')
        try:
            r = subprocess.run(
                ['quarto', 'render', '--to', f],
                cwd=qdir, capture_output=not verbose,
                text=True, timeout=600
            )
            if r.returncode != 0:
                print(f'  ⚠ Erro ao renderizar {f}:')
                # Mostra as últimas linhas do erro
                error_lines = r.stderr.split('\n')[-10:] if r.stderr else []
                for line in error_lines:
                    if line.strip():
                        print(f'      {line}')
            else:
                # Verifica se o PDF foi gerado
                if f == 'pdf':
                    pdf_path = qdir / f'{qdir.name}.pdf'
                    if pdf_path.exists():
                        print(f'  ✓ PDF gerado: {pdf_path}')
                    else:
                        # Procura por index.pdf
                        index_pdf = qdir / 'index.pdf'
                        if index_pdf.exists():
                            # Renomeia para o nome do combo
                            shutil.move(str(index_pdf), str(pdf_path))
                            print(f'  ✓ PDF gerado: {pdf_path}')
                        else:
                            print(f'  ⚠ PDF não encontrado em {qdir}')
                else:
                    print(f'  ✓ {f} → gen/book/{qdir.name}/')
        except FileNotFoundError:
            print('  ⚠ quarto não encontrado no PATH')
        except subprocess.TimeoutExpired:
            print('  ⚠ Timeout ao renderizar (mais de 600 segundos)')