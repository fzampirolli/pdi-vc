"""
pipeline/quarto_builder.py
===========================
Constrói uma pasta Quarto auto-suficiente para cada combo:

    gen/quarto/<combo>/
        _quarto.yml      ← gerado aqui
        index.qmd        ← gerado aqui (idioma correto)
        prefacio.qmd     ← gerado aqui (prefácio do livro)
        apendice*.qmd    ← apêndices estáticos, lidos de all/apendices/*.qmd
        apendice_f/      ← apêndice-notebook, symlink → gen/<combo>/apendices/apendice_f/
                            (fonte: all/apendices/apendice_f/apendice_f.ipynb)
        capa.tex         ← gerado aqui (capa do PDF, via include-before-body)
        capXX/           ← symlink → gen/<combo>/capXX/
        references.bib   ← symlink → ../../references.bib
        includes/        ← symlink → ../../includes/

Render (sem --config):
    cd gen/quarto/py.pt && quarto render --to html
    cd gen/quarto/py.pt && quarto render --to pdf

    
Tamanho da fonte de código e de sua saída:

HTML:
# 1. Bloco geral de tipografia (topo do CSS):
code, pre, .sourceCode {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.80em;          # ← aqui
}

# 2. Bloco de células e outputs (mais abaixo):
div.sourceCode,
.cell-output pre,
...
{
    font-size: 0.80em !important;   # ← e aqui
}

PDF:
\normalsizepadrão (11pt no seu caso)
\small          um passo abaixo (~10pt)
\footnotesize   dois passos abaixo (~9pt)
\scriptsize     três passos abaixo (~8pt)  ← atual
    
\\tcbset{{pdicode/.style={{...fontupper=\\footnotesize\\ttfamily}}}}
\\tcbset{{pdioutput/.style={{...fontupper=\\footnotesize\\ttfamily}}}}

# _fix_tex_cover → custom_header:
pdicode/.style={...fontupper=\footnotesize\ttfamily},
pdioutput/.style={...fontupper=\footnotesize\ttfamily}
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional
import nbformat
import os
import re
import ast
from nbclient import NotebookClient
from playwright.sync_api import sync_playwright

from .config import (
    Combo, UI_STRINGS, LOCALES, LANGUAGES, CPP_CHAPTERS,
    BASE_LANG, BASE_LOCALE, parse_combo,
)

DIR_GEN = Path('gen')

# ─────────────────────────────────────────────────────────────────────────────
# Templates dos arquivos auxiliares
# ─────────────────────────────────────────────────────────────────────────────

def _index_qmd(combo: Combo) -> str:
    lang_label   = LANGUAGES[combo.lang].label
    locale_label = LOCALES[combo.locale].label
    strings      = UI_STRINGS[combo.locale]
    welcome      = strings['welcome'].format(lang_label=lang_label)
    title_short  = strings['title_short']
    org_title    = strings['org_title']
    part1        = strings['part_1']
    part1_desc   = strings['part_1_desc']
    part2        = strings['part_2']
    part2_desc   = strings['part_2_desc']
    refs_title   = strings['references_title']
    return (
        f'## {title_short} — {lang_label} {{.unnumbered}}\n\n'
        f'{welcome}\n\n'
        f'### {org_title} {{.unnumbered}}\n\n'
        f'- **{part1}** — {part1_desc}\n'
        f'- **{part2}** — {part2_desc}\n\n'
        '---\n'
    )

import platform

DIR_GEN = Path('gen')

def _get_emoji_font() -> str:
    """Retorna a fonte de emoji correta para o SO atual."""
    system = platform.system()
    if system == 'Darwin':
        return 'TwemojiMozilla'
    elif system == 'Linux':
        return 'Noto Color Emoji'
    else:
        return 'Segoe UI Emoji'

# ── Fonte de emoji dependente do SO ──────────────────────────────────────────
EMOJI_FONT = _get_emoji_font()


def _locale_asset(base_path: Path, locale: str) -> Path:
    """
    Resolve um asset de includes/ (capa, contracapa, ...) com override por
    locale: se existir <nome>.<locale><ext> ao lado do arquivo padrão, usa
    esse; senão usa o padrão. Mesma convenção de all/capXX/imagens/ (ver
    _symlink_imagens_locale_aware) — nunca precisa mudar onde o arquivo é
    referenciado, só adicionar o arquivo com sufixo.
    """
    if locale == BASE_LOCALE:
        return base_path
    localized = base_path.parent / f'{base_path.stem}.{locale}{base_path.suffix}'
    return localized if localized.exists() else base_path

def _read_include_qmd(filename: str, combo: Combo) -> Optional[str]:
    """
    Lê um .qmd de includes/<filename>, aplicando substituição i18n.
    Se existir uma versão traduzida includes/<nome>_<locale><ext> para o
    locale do combo (ex.: prefacio_en.qmd), ela é usada no lugar do arquivo
    em Português. Retorna None se nenhum dos dois existir (quem chama decide
    o fallback).
    """
    path = Path('includes') / filename
    if combo.locale != BASE_LOCALE:
        stem, ext = os.path.splitext(filename)
        localized = Path('includes') / f'{stem}_{combo.locale}{ext}'
        if localized.exists():
            path = localized
    if not path.exists():
        return None
    content = path.read_text(encoding='utf-8')
    print(f'  ✓ {path.name} lido de {path}')
    lang_label = LANGUAGES[combo.lang].label
    content = content.replace('{{lang_label}}', lang_label)
    locale_label = LOCALES[combo.locale].label
    content = content.replace('{{locale_label}}', locale_label)
    return content


# def _prefacio_qmd(combo: Combo) -> str:
#     """
#     Lê o prefácio do arquivo includes/prefacio.qmd.
#     Se o arquivo não existir, gera um prefácio padrão com suporte a i18n.
#     """
#     content = _read_include_qmd('prefacio.qmd', combo)
#     if content is not None:
#         return content

#     content = prefacio_path.read_text(encoding='utf-8')
#     print(f'  ✓ Prefácio lido de {prefacio_path}')
#     lang_label = LANGUAGES[combo.lang].label
#     content = content.replace('{{lang_label}}', lang_label)
#     locale_label = LOCALES[combo.locale].label
#     content = content.replace('{{locale_label}}', locale_label)
#     return content

# Override de front-matter YAML por página, pra desligar `code-tools` em
# páginas sem NENHUMA célula de código executável (prefácio, ficha
# catalográfica, referências, apêndices estáticos). Achado real: com
# `code-tools: true` ligado no nível do livro (format.html), o Quarto quebra
# o parsing de fenced div (`::: {.callout-*}`) especificamente em páginas
# .qmd puras sem código — o `:::` vaza como texto literal em vez de virar a
# caixa colorida. Confirmado com um book mínimo reproduzível (1 página, 1
# callout, só `code-tools: true`) — não depende de tradução, filtro custom
# ou include-in-header; reproduz até em pt. Não afeta os capítulos (vêm de
# .ipynb, sempre têm células de código). Front-matter por documento
# sobrescreve a config do livro pra essa página específica.
_NO_CODE_TOOLS_FM = '---\ncode-tools: false\n---\n\n'

# Regex do bloco de front-matter YAML no INÍCIO de um .qmd (--- ... ---).
_LEADING_FM_RE = re.compile(r'\A---\n(.*?)\n---\n', re.DOTALL)


def _with_no_code_tools(content: str) -> str:
    """
    Garante `code-tools: false` no front-matter de `content` SEM criar um
    segundo bloco `--- ... ---`. Se o arquivo já começa com um front-matter
    (caso da ficha catalográfica, que traz `unnumbered: true`), a chave é
    inserida DENTRO desse bloco; senão, um bloco novo é prefixado.

    Prefixar cegamente `_NO_CODE_TOOLS_FM` num arquivo que já tinha
    front-matter fazia o Pandoc ler só o 1º bloco e renderizar o 2º como
    texto — no caso da ficha, um heading espúrio e NUMERADO ("unnumbered:
    true"), que empurrava a numeração de todos os capítulos em +1.
    """
    m = _LEADING_FM_RE.match(content)
    if m:
        if re.search(r'^\s*code-tools\s*:', m.group(1), re.MULTILINE):
            return content
        return f'---\n{m.group(1)}\ncode-tools: false\n---\n' + content[m.end():]
    return _NO_CODE_TOOLS_FM + content


def _prefacio_qmd(combo: Combo) -> str:
    """
    Lê o prefácio do arquivo includes/prefacio.qmd e acrescenta o gatilho
    \\mainmatter (raw LaTeX, ignorado em HTML) ao final.
    """
    content = _read_include_qmd('prefacio.qmd', combo)
    if content is None:
        raise FileNotFoundError(
            'includes/prefacio.qmd não encontrado — arquivo obrigatório.'
        )

    content += (
        '\n\n```{=latex}\n'
        '\\mainmatter\n'
        '```\n'
    )
    return _with_no_code_tools(content)

APENDICES_ROOT = Path('all/apendices')

def _apendice_entries() -> list[Path]:
    """
    Descobre os apêndices disponíveis em all/apendices/, na ordem alfabética
    do nome (garante A, B, C, D... em ordem, mesmo misturando os dois formatos
    suportados):

      - arquivo solto  apendice_X_*.qmd        → apêndice estático (texto)
      - diretório      apendice_X_*/*.ipynb    → apêndice executável (notebook),
                                                   tratado como um "capítulo",
                                                   igual a capXX/

    Retorna a lista de Paths: arquivos .qmd, ou diretórios que contêm um .ipynb.
    """
    if not APENDICES_ROOT.exists():
        return []
    # Sufixos de override de idioma (ex.: apendice_a_mctest.en.qmd) não são
    # apêndices próprios — são a variante localizada de um arquivo base, lida
    # por `_read_apendice_qmd` na mesma convenção usada pelas imagens (ver
    # `_symlink_imagens_locale_aware`) e pelos screenshots dos simuladores
    # (ver `_resolve_screenshot_png`). Sem esse filtro, cada override viraria
    # um apêndice extra e duplicado no sumário.
    locale_suffixes = tuple(f'.{loc}.qmd' for loc in LOCALES if loc != BASE_LOCALE)
    entries: list[Path] = []
    for p in sorted(APENDICES_ROOT.iterdir()):
        if p.is_file() and p.suffix == '.qmd':
            if p.name.endswith(locale_suffixes):
                continue
            entries.append(p)
        elif p.is_dir() and next(p.glob('*.ipynb'), None) is not None:
            entries.append(p)
    return entries

def _read_apendice_qmd(path: Path, combo: Combo) -> Optional[str]:
    """
    Lê um apêndice .qmd de all/apendices/<arquivo>, aplicando substituição i18n.
    Se existir uma variante localizada `<nome>.<locale>.qmd` ao lado do
    arquivo base (mesma convenção de `_symlink_imagens_locale_aware`), ela é
    usada no lugar para locales != BASE_LOCALE. Retorna None se nem o arquivo
    localizado nem o base existirem.
    """
    if combo.locale != BASE_LOCALE:
        localized = path.with_name(f'{path.stem}.{combo.locale}{path.suffix}')
        if localized.exists():
            path = localized
    if not path.exists():
        return None
    content = path.read_text(encoding='utf-8')
    print(f'  ✓ {path.name} lido de {path}')
    lang_label = LANGUAGES[combo.lang].label
    content = content.replace('{{lang_label}}', lang_label)
    locale_label = LOCALES[combo.locale].label
    content = content.replace('{{locale_label}}', locale_label)
    return _with_no_code_tools(content)

def _ficha_catalografica_qmd(combo: Combo) -> Optional[str]:
    """
    Lê a ficha catalográfica de includes/ficha_catalografica.qmd.
    Retorna None se o arquivo não existir (nesse caso, a página não é incluída).
    """
    content = _read_include_qmd('ficha_catalografica.qmd', combo)
    return None if content is None else _with_no_code_tools(content)

def _refs_qmd(combo: Combo) -> str:
    title = UI_STRINGS[combo.locale].get('references_title', 'Referências')
    return _with_no_code_tools(f'# {title} {{.unnumbered}}\n\n::: {{#refs}}\n:::\n')


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

    # ── Anexos soltos em all/apendices/ (arquivos direto na raiz, referenciados
    #    por algum apêndice .qmd — ex.: imagens que não têm pasta própria) ─────
    apendices_dir = all_root / 'apendices'
    if apendices_dir.exists():
        for attachment in apendices_dir.glob('*'):
            if attachment.is_file() and attachment.suffix in ['.png', '.jpg', '.jpeg', '.gif', '.csv', '.txt', '.pdf']:
                target_dir = attachments_dir / 'apendices'
                target_dir.mkdir(exist_ok=True)
                target_file = target_dir / attachment.name
                shutil.copy2(attachment, target_file)
                print(f'  ✓ Anexo: apendices/{attachment.name}')


def _mainmatter_qmd() -> str:
    """
    Marcador que dispara \mainmatter no PDF (reinicia numeração em 1, arábico,
    e reativa numeração de capítulos). Ignorado nos demais formatos (HTML etc.).
    """
    return '```{=latex}\n\\mainmatter\n```\n'

# ─────────────────────────────────────────────────────────────────────────────
# Builder
# ─────────────────────────────────────────────────────────────────────────────

class QuartoBuilder:
    """
    Monta a pasta gen/quarto/<combo>/ e o _quarto.yml interno.
    O render NÃO usa --config: roda de dentro da pasta.
    """

    CAPS_PART1 = [f'cap{i:02d}' for i in range(1, 6)]
    CAPS_PART2 = [f'cap{i:02d}' for i in range(6, 11)]

    def __init__(self, project_root: Path = Path('.')):
        self.root = project_root.resolve()

    def build(self, combo: Combo, nb_root: Optional[Path] = None, all_root: Optional[Path] = None,
              include_apendices: bool = True) -> Path:
        nb_root = nb_root or (self.root / DIR_GEN / combo.key)
        all_root = all_root or (self.root / 'all')
        qdir    = self.root / DIR_GEN / 'quarto' / combo.key
        qdir.mkdir(parents=True, exist_ok=True)

        (qdir / 'index.qmd').write_text(_index_qmd(combo), encoding='utf-8')

        ficha = _ficha_catalografica_qmd(combo)
        if ficha is not None:
            (qdir / 'ficha_catalografica.qmd').write_text(ficha, encoding='utf-8')

        (qdir / 'prefacio.qmd').write_text(_prefacio_qmd(combo), encoding='utf-8')

        (qdir / 'prefacio.qmd').write_text(_prefacio_qmd(combo), encoding='utf-8')
        (qdir / 'referencias.qmd').write_text(_refs_qmd(combo), encoding='utf-8')

        # ── Apêndices do livro (all/apendices/apendice_a_*.qmd, .../apendice_f/, ...) ──
        # Puláveis via include_apendices=False (ex.: build rápido de 1 capítulo,
        # `make capNN`) — não fazem parte do capítulo pedido e alguns são
        # notebooks executáveis, custando tempo de render à toa nesse caso.
        apendice_files = (self._write_apendice_entries(qdir, combo, nb_root)
                           if include_apendices else [])

        (qdir / 'mainmatter.qmd').write_text(_mainmatter_qmd(), encoding='utf-8')

        self._write_custom_css(qdir)

        self._symlink_caps(combo, qdir, nb_root)
        _process_attachments(combo, nb_root, qdir, all_root)

        self._symlink(qdir / 'references.bib', self.root / 'references.bib')
        self._merge_includes_dir(qdir, combo)

        self._ensure_preamble_files()

        # ── Gera capa.tex para o PDF (include-before-body) ───────────────────
        cover_abs = _locale_asset(self.root / 'includes' / 'girassol_capa.png',
                                  combo.locale).resolve()
        self._write_cover_tex(qdir, cover_abs)

        yml = self._quarto_yml(combo, nb_root, apendice_files=apendice_files)
        (qdir / '_quarto.yml').write_text(yml, encoding='utf-8')
        shutil.copy2(self.root / 'includes' / 'favicon.ico', qdir / 'favicon.ico')
        (qdir / 'fvextra.tex').write_text(
            r'\usepackage{fvextra}' + '\n'
            r'\DefineVerbatimEnvironment{Highlighting}{Verbatim}'
            r'{breaklines=true,breaksymbolleft={},commandchars=\\\{\}}',
            encoding='utf-8'
        )

        print(f'  ✓ Quarto dir: {qdir.relative_to(self.root)}')
        if apendice_files:
            print(f'    apêndices:  {", ".join(apendice_files)}')
        print(f'    render  :  cd {qdir.relative_to(self.root)} && quarto render --to html')
        return qdir

    # ── Internos ──────────────────────────────────────────────────────────────

    @staticmethod
    def _symlink(link: Path, target: Path):
        # `link` normalmente é symlink ou arquivo comum, mas pode virar um
        # DIRETÓRIO REAL: se uma célula executada (ex.: fig-01-natureza)
        # roda com cwd == link.parent e faz os.makedirs("imagens")+escreve
        # nele, o que era pra ser um symlink apontando pra all/capXX/imagens
        # passa a ser um diretório de verdade com conteúdo. `.unlink()`
        # só serve pra arquivo/symlink e quebra com IsADirectoryError nesse
        # caso — como gen/ é sempre saída descartável, é seguro remover e
        # recriar o symlink do zero.
        if link.is_symlink() or link.is_file():
            link.unlink()
        elif link.is_dir():
            shutil.rmtree(link)
        link.symlink_to(target.resolve())

    def _merge_includes_dir(self, qdir: Path, combo: Combo):
        """
        Monta qdir/includes/ como um diretório REAL (não um único symlink),
        contendo symlinks por arquivo vindos de duas origens:

          1. includes/                → recursos globais do livro (capa,
                                          favicon, CSL, ficha catalográfica,
                                          prefácio, imagens de outros
                                          apêndices legados, etc.)
          2. all/apendices/imagens/   → imagens específicas dos apêndices,
                                          na mesma convenção de nome já usada
                                          por all/capXX/imagens/. Referenciadas
                                          de dentro de all/apendices/apendice_*.qmd
                                          como caminho relativo `includes/<arquivo>`
                                          (ex.: includes/apendice-a-simulado4-
                                          morfologia.png) — o texto do .qmd não
                                          muda; só a origem física do arquivo é
                                          diferente de onde ele é exposto.

        Antes, qdir/includes era um único symlink para includes/ — por isso
        imagens colocadas em all/apendices/imagens/ não apareciam no
        caminho relativo `includes/...` que os .qmd dos apêndices usam.
        Funciona igualmente para `quarto render --to html` e `--to pdf`,
        já que ambos resolvem os caminhos das imagens a partir da mesma
        árvore de arquivos em qdir/.

        Em caso de nome de arquivo duplicado nas duas origens, o de
        all/apendices/imagens/ tem prioridade (mais específico).

        Arquivos com sufixo de locale (ex.: girassol_capa.en.png, mesma
        convenção de all/capXX/imagens/) sobrepõem o arquivo padrão sob o
        NOME BASE — quem referencia `includes/girassol_capa.png` (o YAML
        do livro, o .tex da capa) nunca precisa saber que existe um
        override; ver _symlink_imagens_locale_aware.
        """
        dest = qdir / 'includes'
        dest.mkdir(parents=True, exist_ok=True)  # diretório real, não symlink

        root_includes = self.root / 'includes'
        if root_includes.exists():
            for f in root_includes.iterdir():
                if f.is_dir():
                    self._symlink(dest / f.name, f)
            self._symlink_imagens_locale_aware(root_includes, dest, combo.locale)

        apendices_imagens = self.root / 'all' / 'apendices' / 'imagens'
        if apendices_imagens.exists():
            for f in apendices_imagens.iterdir():
                self._symlink(dest / f.name, f)  # sobrescreve em conflito de nome

    def _symlink_caps(self, combo: Combo, qdir: Path, nb_root: Path):
        morph_cpp_dir = self.root / 'morph' / 'cpp'
        # morph.py / testsuite.py da árvore de trabalho, ao lado de cada
        # capítulo: `config.setup` só baixa do GitHub master `if not
        # os.path.exists(f)`, então sem isto uma build usaria a versão
        # publicada (defasada) — ex.: `mm.crop`/`mm.subsample` novas quebram
        # com AttributeError até serem commitadas+push. O symlink local
        # vence o download.
        morph_py_files = [self.root / 'morph' / 'morph.py',
                          self.root / 'morph' / 'testsuite.py']
        for cap in self.CAPS_PART1 + self.CAPS_PART2:
            cap_dir = nb_root / cap
            if cap_dir.exists():
                dest = qdir / cap
                dest.mkdir(parents=True, exist_ok=True)  # diretório real, não symlink

                # Precisa rodar ANTES do loop de symlink abaixo: numa build
                # do zero, nb_root/cap/imagens ainda não existe nesse ponto
                # — se populada depois, cap_dir.iterdir() já passou por ela
                # e nunca mais volta a checar, então qdir/cap/imagens fica
                # sem symlink nenhum (nem diretório) até uma célula
                # executada pelo Quarto criar um diretório real ali com
                # os.makedirs("imagens") na hora de salvar uma figura solta
                # — aí "imagens/" vira um diretório órfão contendo só essa
                # figura, sem nada de all/capXX/imagens (todas as outras
                # imagens do capítulo, simuladores inclusive, "somem" do
                # PDF). Ver também o comentário em `_symlink` sobre esse
                # mesmo cenário.
                all_imagens = self.root / 'all' / cap / 'imagens'
                gen_imagens = nb_root / cap / 'imagens'
                if all_imagens.exists() and not gen_imagens.exists():
                    gen_imagens.mkdir(parents=True, exist_ok=True)
                    self._symlink_imagens_locale_aware(
                        all_imagens, gen_imagens, combo.locale
                    )

                for f in cap_dir.iterdir():
                    self._symlink(dest / f.name, f)      # symlinks apenas dos arquivos

                for f in morph_py_files:
                    if f.exists():
                        self._symlink(dest / f.name, f)

                # combos cpp: os headers de morph.hpp (+ stb vendorizadas)
                # precisam estar ao lado do .cpp gerado pra `!g++` achar via
                # #include "morph.hpp" sem precisar de -I na célula.
                if combo.lang == 'cpp' and morph_cpp_dir.exists():
                    for f in morph_cpp_dir.glob('*.h*'):
                        self._symlink(dest / f.name, f)

    @classmethod
    def _symlink_imagens_locale_aware(cls, all_imagens: Path, gen_imagens: Path,
                                       locale: str):
        """
        Symlinka cada arquivo de `all_imagens` individualmente (não a pasta
        inteira) pra permitir override por locale: uma imagem com texto
        embutido em português (ex.: fig-04-algoritmo.png) pode ter uma
        variante fig-04-algoritmo.en.png ao lado, na MESMA pasta — se
        existir, é usada no lugar da padrão pra esse locale, sem que o
        markdown/notebook-fonte precise referenciar um nome diferente.

        `Path.stem`/`Path.suffix` só removem a última extensão, então
        'fig-04-algoritmo.en.png' → stem 'fig-04-algoritmo.en' → nome-base
        'fig-04-algoritmo.png'. Nunca toca em all/capXX/imagens/ — só cria
        symlinks na pasta de saída (por combo, já isolada em gen/<combo>/).
        """
        suffix = f'.{locale}'
        overrides: dict[str, Path] = {}
        plain: dict[str, Path] = {}
        for f in all_imagens.iterdir():
            if not f.is_file():
                continue
            if locale != BASE_LOCALE and f.stem.endswith(suffix):
                base_name = f.stem[:-len(suffix)] + f.suffix
                overrides[base_name] = f
            else:
                plain[f.name] = f

        for name, f in plain.items():
            cls._symlink(gen_imagens / name, overrides.get(name, f))
        # Override sem arquivo padrão correspondente (nome-base nunca
        # existe sozinho) — symlinka também com o próprio nome, caso algo
        # referencie o sufixo diretamente.
        for base_name, f in overrides.items():
            if base_name not in plain:
                cls._symlink(gen_imagens / f.name, f)

    def _write_apendice_entries(self, qdir: Path, combo: Combo, nb_root: Path) -> list[str]:
        """
        Escreve/linka em qdir os apêndices descobertos em all/apendices/,
        na ordem em que devem entrar no livro. Suporta dois formatos:

          - apendice_X_*.qmd       → escrito como texto estático em qdir/,
                                       com substituição i18n (comportamento
                                       idêntico ao anterior, só muda a origem).

          - apendice_X_*/*.ipynb   → tratado como um "capítulo": o notebook já
                                       processado (traduzido/executado para o
                                       combo atual) é lido de
                                       nb_root/apendices/<pasta>/ e symlinkado
                                       em qdir/<pasta>/ — exatamente como
                                       _symlink_caps faz para capXX/. A pasta
                                       nb_root/apendices/<pasta>/ precisa ter
                                       sido gerada previamente pelo mesmo
                                       pipeline que gera nb_root/capXX/ a
                                       partir de all/capXX/capXX.ipynb.

        Retorna a lista de caminhos (relativos a qdir), na ordem correta, para
        entrar no bloco `appendices:` do _quarto.yml.
        """
        written: list[str] = []
        for entry in _apendice_entries():
            if entry.suffix == '.qmd':
                content = _read_apendice_qmd(entry, combo)
                if content is None:
                    continue
                (qdir / entry.name).write_text(content, encoding='utf-8')
                written.append(entry.name)
                print(f'  ✓ Apêndice escrito: {entry.name}')
                continue

            # entry é um diretório, ex.: all/apendices/apendice_f
            dirname = entry.name
            src_dir = nb_root / 'apendices' / dirname
            using_raw_fallback = False

            if not src_dir.exists():
                # Pipeline de tradução/execução por combo ainda não processou
                # este apêndice (o mesmo que gera nb_root/capXX/ a partir de
                # all/capXX/capXX.ipynb ainda não conhece all/apendices/).
                # Fallback: usa o .ipynb cru direto de all/apendices/<dirname>/,
                # sem i18n por combo, apenas para não sumir do livro.
                src_dir = entry  # all/apendices/apendice_f
                using_raw_fallback = True
                print(f'  ⚠ Apêndice-notebook ainda não processado por combo — '
                      f'usando .ipynb cru (sem i18n): {dirname}')

            nb_name = f'{dirname}.{combo.key}.ipynb'
            if not (src_dir / nb_name).exists():
                # Fallback: usa o único .ipynb presente, se o nome não bater
                # com o padrão <pasta>.<combo>.ipynb usado pelos capítulos
                # (é sempre o caso do fallback "cru", que não tem sufixo de combo).
                nb_candidates = sorted(src_dir.glob('*.ipynb'))
                if not nb_candidates:
                    print(f'  ⚠ Nenhum .ipynb encontrado em {src_dir} (pulado)')
                    continue
                nb_name = nb_candidates[0].name

            # dest = qdir / dirname
            # dest.mkdir(parents=True, exist_ok=True)  # diretório real, não symlink
            # for f in src_dir.iterdir():
            #     self._symlink(dest / f.name, f)       # symlinks (arquivos e pastas, ex.: imagens/)

            # if not using_raw_fallback:
            #     all_imagens = self.root / 'all' / 'apendices' / dirname / 'imagens'
            #     gen_imagens = src_dir / 'imagens'
            #     if all_imagens.exists() and not gen_imagens.exists():
            #         gen_imagens.symlink_to(all_imagens.resolve())

            # written.append(f'{dirname}/{nb_name}')
            # print(f'  ✓ Apêndice (notebook) linkado: {dirname}/{nb_name}'
            #       + (' [fallback cru]' if using_raw_fallback else ''))


            dest = qdir / dirname
            dest.mkdir(parents=True, exist_ok=True)  # diretório real, não symlink
            for f in src_dir.iterdir():
                if f.name == nb_name:
                    # O notebook pode ser executado pelo Quarto (ex.: apendice_f, que tem
                    # células de código gerando parâmetros usados no texto). Se fosse
                    # symlink, a execução regravaria outputs direto no arquivo fonte em
                    # all/apendices/. Copiamos para isolar gen/ do fonte.
                    shutil.copy2(f, dest / f.name)
                else:
                    self._symlink(dest / f.name, f)       # symlinks (imagens/, .qmd etc.)
            if not using_raw_fallback:
                all_imagens = self.root / 'all' / 'apendices' / dirname / 'imagens'
                gen_imagens = src_dir / 'imagens'
                if all_imagens.exists() and not gen_imagens.exists():
                    gen_imagens.symlink_to(all_imagens.resolve())
            written.append(f'{dirname}/{nb_name}')
            print(f'  ✓ Apêndice (notebook) copiado: {dirname}/{nb_name}'
                + (' [fallback cru]' if using_raw_fallback else ''))


        return written

    # def _write_cover_tex(self, qdir: Path, cover_abs: Path):
    #     """
    #     Salva o path da capa para uso no pós-processamento do .tex.
    #     O cover_hook.tex é um marcador vazio — a capa é injetada por _fix_tex_cover().
    #     """
    #     (qdir / 'cover_hook.tex').unlink(missing_ok=True)
    #     (qdir / 'cover_hook.tex').write_text('', encoding='utf-8')

    #     # Salva o path para uso posterior em _fix_tex_cover
    #     (qdir / '.cover_abs').write_text(str(cover_abs), encoding='utf-8')
    #     # cover_hook.tex vazio — só carrega etoolbox sem fazer nada
    #     (qdir / 'cover_hook.tex').write_text('', encoding='utf-8')

    #     print('  ✓ Gerado cover_hook.tex')
            
    def _write_cover_tex(self, qdir: Path, cover_abs: Path) -> None:
        # 1. Garante que cover_hook.tex exista (evita o erro FATAL do Quarto)
        cover_hook_file = qdir / 'cover_hook.tex'
        cover_hook_file.write_text('', encoding='utf-8')

        # 2. Gera o arquivo capa.tex com os comandos LaTeX
        content = (
            r'\frontmatter' + '\n'
            r'\thispagestyle{empty}' + '\n'
            r'\begin{center}' + '\n'
            r'\vspace*{\fill}' + '\n'
            rf'\includegraphics[width=\textwidth]{{{cover_abs}}}' + '\n'
            r'\vspace*{\fill}' + '\n'
            r'\end{center}' + '\n'
            r'\clearpage' + '\n'
        )
        (qdir / 'capa.tex').write_text(content, encoding='utf-8')

        # 3. Salva o caminho absoluto da capa no arquivo oculto .cover_abs
        (qdir / '.cover_abs').write_text(str(cover_abs), encoding='utf-8')

        print('  ✓ Gerados cover_hook.tex e capa.tex')
        
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
font-size: 0.75em;      /* tamanho menor para código, para caber melhor no PDF sem quebrar tanto */
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
/* ── Código-fonte (input) e outputs — base compartilhada ─────── */
div.sourceCode,
.cell-output pre,
.cell-output code,
[class^="cell-output"] pre,
[class*=" cell-output"] pre {
  border-radius: 8px !important;
  border: 1px solid transparent !important;   /* sobrescrito abaixo */
  border-left-width: 4px !important;
  box-shadow: none !important;
  font-family: 'JetBrains Mono', monospace !important;
  font-size: 0.75em !important;       /* tamanho menor para código, para caber melhor no PDF sem quebrar tanto */
  line-height: 1.55 !important;
  padding: 0.75em 1em !important;
  white-space: pre-wrap !important;
}

/* ── Código-fonte: azul ──────────────────────────────────────── */
div.sourceCode {
  background: #f0f4ff !important;
  border-color: #c8d4f0 !important;
  border-left-color: #7090d0 !important;
  color: #1a2050 !important;
}
div.sourceCode pre,
div.sourceCode pre code {
  background: #f0f4ff !important;
  color: #1a2050 !important;
  border: none !important;
  box-shadow: none !important;
}

/* ── Output (stdout): mesma estrutura, fundo âmbar ──────────── */
.cell-output pre,
.cell-output code,
[class^="cell-output"] pre,
[class*=" cell-output"] pre {
  background: #fdf6ec !important;
  border-color: #e8d8b8 !important;
  border-left-color: #e8a840 !important;
  color: #2e1e05 !important;
}

/* ── stderr: mesma estrutura, fundo rosado ───────────────────── */
.cell-output-stderr pre,
.cell-output-stderr code {
  background: #fff2f0 !important;
  border-color: #f0c8c0 !important;
  border-left-color: #e06050 !important;
  color: #5a1a10 !important;
}

/* O <code> DENTRO do <pre> (saída de stream: <pre><code>...</code></pre>)
   não pode reganhar caixa/borda/padding próprios — senão vira uma
   "janela dentro da outra". Só o <pre> externo desenha a moldura,
   idêntico ao que já se faz com div.sourceCode acima. */
.cell-output pre code,
[class^="cell-output"] pre code,
[class*=" cell-output"] pre code {
  background: transparent !important;
  border: none !important;
  border-radius: 0 !important;
  border-left-width: 0 !important;
  padding: 0 !important;
  box-shadow: none !important;
  color: inherit !important;
  font-size: inherit !important;
}

/* ── display_data (imagens, HTML rico): sem caixa própria ─────── */
.cell-output-display {
  background: transparent !important;
  border: none !important;
  padding: 0 !important;
  margin-top: 0.3em !important;
}
.cell-output-display > pre,
.cell-output-display pre {
  background: #fdf6ec !important;
  border: 1px solid #e8d8b8 !important;
  border-left: 4px solid #e8a840 !important;
  border-radius: 8px !important;
  padding: 0.75em 1em !important;
  color: #2e1e05 !important;
}
.cell-output-display img {
  background: transparent;
  border-radius: 4px;
  display: block;
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
/* ── Botões de expansão (Sidebar / Índice) ─────────────────── */
.toggle-layout-btn {
  background: transparent;
  border: 1px solid rgba(0, 0, 0, 0.08);
  color: rgba(85, 85, 85, 0.65);
  padding: 3px 7px;
  font-size: 0.7rem;
  font-weight: 300;
  line-height: 1;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s ease;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  opacity: 0.55;
}
.toggle-layout-btn:hover {
  background: rgba(0, 0, 0, 0.04);
  color: #1a3a5c;
  border-color: rgba(26, 58, 92, 0.4);
  opacity: 1;
}

#toggle-sidebar-btn {
  position: fixed;
  top: 12px;
  left: 15px;
  z-index: 1100;
  background: #ffffff;
  box-shadow: 0 1px 2px rgba(0,0,0,0.06);
}

#toggle-toc-btn {
  position: fixed;
  top: 12px;
  right: 15px;
  z-index: 1100;
  background: #ffffff;
  box-shadow: 0 1px 2px rgba(0,0,0,0.06);
}

/* Classes para alternar a largura e esconder elementos */
body.sidebar-hidden #quarto-sidebar {
  display: none !important;
}
body.sidebar-hidden #quarto-document-content,
body.sidebar-hidden .content,
body.sidebar-hidden page-columns {
  grid-column: 1 / -1 !important;
  max-width: 100% !important;
  padding-left: 5mm !important;
}
body.toc-hidden #TOC,
body.toc-hidden #quarto-margin-sidebar {
  display: none !important;
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

%\usepackage[brazilian]{babel}
\usepackage[portuguese]{babel}
\babelprovide[main, import]{portuguese}
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
        DEBUG_CAPS = []  # 'cap03' ← remova depois do teste; [] = todos

        parts = [
            (UI_STRINGS[combo.locale]['part_1'], self.CAPS_PART1),
            (UI_STRINGS[combo.locale]['part_2'], self.CAPS_PART2),
        ]
        blocks = []
        for title, caps in parts:
            chaps = []
            for cap in caps:
                if DEBUG_CAPS and cap not in DEBUG_CAPS:  # ← filtro
                    continue
                # C++ só está portado/validado para os capítulos em
                # CPP_CHAPTERS (ver CPP_VALIDATION_NOTE em index_builder). Não
                # inclua os demais nos livros cpp mesmo que exista um .ipynb
                # gerado (stale) — cv2/skimage sem equivalente quebram o render.
                if combo.lang == 'cpp' and cap not in CPP_CHAPTERS:
                    continue
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

    def _quarto_yml(self, combo: Combo, nb_root: Path,
                        apendice_files: Optional[list[str]] = None) -> str:
        lang_obj    = LANGUAGES[combo.lang]
        locale_obj  = LOCALES[combo.locale]
        lang_label  = lang_obj.label
        quarto_lang = locale_obj.quarto_lang

        apendice_files = apendice_files or []

        book_title = UI_STRINGS[combo.locale]['title']
        subtitle = (UI_STRINGS[combo.locale]['book_subtitle']
                    .format(lang_label=lang_label))

        chapters = self._chapter_blocks(combo, nb_root)

        appendices_block = ''
        if apendice_files:
            items = '\n'.join(f'    - {f}' for f in apendice_files)
            appendices_block = f'\n  appendices:\n{items}'

        output_dir   = str((self.root / 'gen' / 'book' / combo.key).resolve())
        bib_path     = (self.root / 'references.bib').resolve()
        csl_path     = (self.root / 'includes' / 'abnt.csl').resolve()
        emoji_filter = (self.root / 'includes' / 'emoji-filter.lua').resolve()
        # cover-image (abaixo) referencia includes/girassol_capa.png por nome
        # fixo — o override por locale (girassol_capa.<locale>.png) já é
        # resolvido no symlink de qdir/includes/ (ver _merge_includes_dir).

        if not csl_path.exists():
            self._create_default_csl(csl_path)

        custom_filename = f"livro.{combo.file_key}"

        # Combos não-base chegam com outputs/execution_count limpos
        # (NotebookProcessor._clean_cell) — sem `enabled: true` explícito, o
        # engine ipynb do Quarto trata "outputs já presentes (mesmo vazios)"
        # como "já executado" e só exibe o código-fonte, sem rodar nada
        # (confirmado: só `quarto render --execute` força a execução; sem a
        # flag, nenhuma figura é gerada para combos não-base). O combo base
        # (py.pt) mantém os outputs originais do autor — não force reexecução
        # aqui para não mudar esse comportamento já validado.
        execute_enabled = '' if combo.is_base() else '  enabled: true\n'

        # NOTA: A capa do PDF é gerada via capa.tex (include-before-body).
        # NÃO use \AtBeginDocument no include-in-header para isso — o Quarto/Pandoc
        # insere conteúdo antes de \AtBeginDocument ser disparado, empurrando a capa
        # para a página 2. O include-before-body injeta o conteúdo imediatamente
        # após \begin{document}, garantindo que seja a primeira página.

        return f'''# Gerado por gerar_livro.py — NÃO editar manualmente.

project:
  type: book
  output-dir: "{output_dir}"

lang: {quarto_lang}

book:
  title: "{book_title}"
  cover-image: "includes/girassol_capa.png"
  subtitle: "{subtitle}"
  author:
    - name: "Francisco de Assis Zampirolli"
      affiliation: "Universidade Federal do ABC"
  # date: today
  downloads: [pdf]
  output-file: "livro.{combo.file_key}"

  chapters:
    - index.qmd
    - ficha_catalografica.qmd
    - prefacio.qmd
{chapters}
{appendices_block}
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
    favicon: favicon.ico
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
        <link rel="icon" type="image/x-icon" href="includes/favicon.ico">
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link href="https://fonts.googleapis.com/css2?family=Source+Serif+4:ital,opsz,wght@0,8..60,300..900;1,8..60,300..900&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
        
        <script>
        document.addEventListener('DOMContentLoaded', function() {{
          // ── Redireciona o título da barra lateral para o index.html geral ────
          const sidebarTitleLink = document.querySelector('.sidebar-title a, a.sidebar-title');
          if (sidebarTitleLink) {{
            sidebarTitleLink.setAttribute('href', '../index.html');
          }}

          // 1. Botão flutuante na esquerda (menu lateral)
          const btnSidebar = document.createElement('button');
          btnSidebar.id = 'toggle-sidebar-btn';
          btnSidebar.className = 'toggle-layout-btn';
          btnSidebar.innerHTML = '◀';
          btnSidebar.title = 'Esconder/Mostrar Menu Lateral';
          document.body.appendChild(btnSidebar);

          btnSidebar.addEventListener('click', function() {{
            document.body.classList.toggle('sidebar-hidden');
            btnSidebar.innerHTML = document.body.classList.contains('sidebar-hidden') ? '▶' : '◀';
          }});

          // 2. Botão flutuante na direita (índice / TOC), mesmo espaçamento do botão esquerdo
          const btnToc = document.createElement('button');
          btnToc.id = 'toggle-toc-btn';
          btnToc.className = 'toggle-layout-btn';
          btnToc.innerHTML = '▶';
          btnToc.title = 'Esconder/Mostrar Índice';
          document.body.appendChild(btnToc);

          btnToc.addEventListener('click', function() {{
            document.body.classList.toggle('toc-hidden');
            btnToc.innerHTML = document.body.classList.contains('toc-hidden') ? '◀' : '▶';
          }});
        }});
        </script>


  pdf:
    documentclass: book
    date: today   # <-- ADICIONE AQUI
    #classoption: [openany, oneside, 11pt, a4paper] 
    classoption: [openright, twoside, 11pt, a4paper] # frente e verso
    title-page: false
    output-file: "livro.{combo.file_key}.pdf"
    block-headings: false   # <-- adicionar isso
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
    number-depth: 3   # Apenas numera até h3 (\subsubsection)
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
    #
    # Antes, capa.tex era gerado em disco mas NUNCA referenciado aqui no YAML —
    # só era injetado via patch manual em Python (_fix_tex_cover), que só roda
    # dentro do pipeline `make pdf`. Por isso `quarto render --to pdf` rodado
    # direto (sem passar pelo pipeline) sempre saía sem capa. Com o
    # include-before-body abaixo, a capa entra nos dois casos: no
    # `quarto render --to pdf` nativo (via este YAML) e no pipeline `make pdf`
    # (onde o conteúdo é removido e reinserido pelo _fix_tex_cover, então não
    # duplica).
    include-before-body:
        - file: capa.tex

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
          \\setemojifont{{{EMOJI_FONT}}}
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
          \\usepackage{{alltt}}

          \\AtBeginDocument{{%
            \\renewenvironment{{Shaded}}{{\\begin{{tcolorbox}}[pdicode]}}{{\\end{{tcolorbox}}}}%
            %\\renewenvironment{{verbatim}}{{\\begin{{tcolorbox}}[pdioutput]\\begin{{alltt}}}}{{\\end{{alltt}}\\end{{tcolorbox}}}}%
            \\renewenvironment{{verbatim}}{{\\VerbatimEnvironment\\begin{{tcolorbox}}[pdioutput]\\begin{{Verbatim}}[breaklines=true,breaksymbol={{}}]}}{{\\end{{Verbatim}}\\end{{tcolorbox}}}}%
          }}
          \\usepackage{{fancyhdr}}
          \\pagestyle{{fancy}}
          \\fancyhf{{}}
          \\fancyhead[L]{{\\small\\textcolor{{darkblue}}{{\\textit{{{UI_STRINGS[combo.locale]['brand_tag']}}}}}}}
          \\fancyhead[R]{{\\small\\href{{https://github.com/fzampirolli/pdi-vc}}{{github.com/fzampirolli/pdi-vc}}}}
          \\fancyfoot[L]{{\\small\\textcolor{{darkblue}}{{\\textit{{UFABC}}}}}}
          \\fancyfoot[R]{{\\thepage}}
          \\renewcommand{{\\headrulewidth}}{{0.4pt}}
          \\renewcommand{{\\footrulewidth}}{{0.4pt}}
          \\fancypagestyle{{plain}}{{
            \\fancyhf{{}}
            \\fancyhead[L]{{\\small\\textcolor{{darkblue}}{{\\textit{{{UI_STRINGS[combo.locale]['brand_tag']}}}}}}}
            \\fancyhead[R]{{\\small\\href{{https://github.com/fzampirolli/pdi-vc}}{{github.com/fzampirolli/pdi-vc}}}}
            \\fancyfoot[L]{{\\small\\textcolor{{darkblue}}{{\\textit{{UFABC}}}}}}
            \\fancyfoot[R]{{\\thepage}}
            \\renewcommand{{\\headrulewidth}}{{0.4pt}}
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
{execute_enabled}  freeze: false
  cache: false
  echo: true      # ← GARANTE que o código-fonte das células SERÁ renderizado no PDF
  warning: false  # ← Oculta avisos do compilador/Python no PDF
  error: false    # ← Oculta mensagens de erro de execução no PDF
  env:
    QUARTO_RENDER: "1"
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

def extract_html(cell_source):
    # Remove magic commands antes do parse
    lines = cell_source.split('\n')
    clean_lines = []
    for line in lines:
        if not line.strip().startswith('%'):
            clean_lines.append(line)
    
    clean_source = '\n'.join(clean_lines)
    
    try:
        tree = ast.parse(clean_source)

        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "HTML"
                and len(node.args) == 1
            ):
                arg = node.args[0]

                # HTML("""...""")
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    return arg.value

                # HTML(f"""...""")
                if isinstance(arg, ast.JoinedStr):
                    parts = []
                    for v in arg.values:
                        if isinstance(v, ast.Constant):
                            parts.append(v.value)
                        else:
                            # Expressões {x}
                            parts.append("{expr}")
                    return "".join(parts)

    except SyntaxError:
        # Fallback: extração manual
        return NotImplemented
    
def _screenshot_png_path(all_root: Path, cap: str, label: str, locale: str) -> Path:
    """
    Caminho de ESCRITA do screenshot de um simulador pra um locale — mesma
    convenção de override já usada por `_symlink_imagens_locale_aware` pra
    imagens manuais: `{label}.png` é a versão canônica (pt), `{label}.
    {locale}.png` é a variante localizada, lado a lado em
    all/capXX/imagens/. Necessário porque, com a tradução de texto dos
    simuladores (ver LLMCommentTranslator em translators.py), o HTML de
    cada locale é diferente — screenshots não podem mais compartilhar um
    único arquivo `{label}.png` pra todos os locales sem sobrescrever o PDF
    de um idioma com a imagem de outro.
    """
    img_dir = all_root / cap / 'imagens'
    if locale == BASE_LOCALE:
        return img_dir / f'{label}.png'
    return img_dir / f'{label}.{locale}.png'


def _resolve_screenshot_png(all_root: Path, cap: str, label: str, locale: str) -> Path:
    """
    Caminho de LEITURA do screenshot de um simulador pra um locale: usa a
    variante localizada `{label}.{locale}.png` se ela já existir; senão cai
    pro canônico `{label}.png` (pt) — mesmo fallback de
    `_symlink_imagens_locale_aware`, aplicado ao PDF (que referencia
    all/capXX/imagens/ diretamente, sem passar pela farm de symlinks usada
    no HTML).
    """
    localized = _screenshot_png_path(all_root, cap, label, locale)
    if locale != BASE_LOCALE and localized.exists():
        return localized
    return all_root / cap / 'imagens' / f'{label}.png'


def _screenshot_html_cells(qdir: Path, all_root: Path, scale: float = 1.0):
    """
    Lê os notebooks JÁ TRADUZIDOS do combo sendo buildado (symlinks em
    `qdir/capXX/` apontando pra `gen/<combo>/capXX/`) — não mais os
    originais de `all/`, senão o screenshot de um simulador ficaria sempre
    em Português mesmo num PDF en/fr. Salva em `all/capXX/imagens/`, com
    sufixo de locale (ver `_screenshot_png_path`) pra não sobrescrever a
    versão de outro idioma.
    """
    combo_name = qdir.name
    locale = combo_name.split('.')[-1]
    from playwright.sync_api import sync_playwright

    for cap_link in qdir.iterdir():
        if not re.match(r'cap\d+', cap_link.name):
            continue
        cap = cap_link.name
        img_dir = all_root / cap / 'imagens'
        img_dir.mkdir(parents=True, exist_ok=True)

        for nb_path in cap_link.glob('*.ipynb'):
            nb = nbformat.read(nb_path, as_version=4)
            for cell in nb.cells:
                if cell.cell_type != 'code':
                    continue

                html_content = extract_html(cell.source)
                if html_content is None:
                    continue

                label = None
                for line in cell.source.splitlines():
                    m = re.match(r'#\|\s*label:\s*(\S+)', line)
                    if m:
                        label = m.group(1)
                        break

                if not label:
                    continue

                png_path = _screenshot_png_path(all_root, cap, label, locale)
                if png_path.exists():
                    print(f'  ✓ Screenshot já existe: {png_path.name}')
                    continue

                # Modificação: Extrair apenas o fluxograma (última aba)
                # O fluxograma está no painel com id "{PREFIX}-p-4"
                # Precisamos encontrar o prefixo usado no HTML
                prefix_match = re.search(r'PREFIX\s*=\s*"([^"]+)"', cell.source)
                if prefix_match:
                    prefix = prefix_match.group(1)
                else:
                    # Fallback: usar o padrão se não encontrar
                    prefix = "lbl2"
                
                # Extrair apenas o SVG do fluxograma (última aba)
                svg_match = re.search(r'<svg[^>]*>.*?</svg>', html_content, re.DOTALL)
                if svg_match:
                    svg_content = svg_match.group(0)
                    
                    # Criar HTML com apenas o SVG do fluxograma
                    final_html = f'''<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
    body {{ margin: 0; background: white; display: flex; justify-content: center; align-items: center; min-height: 100vh; }}
    svg {{ max-width: 100%; height: auto; }}
</style>
</head><body>
{svg_content}
</body></html>'''
                else:
                    # Se não encontrar SVG, usar o HTML completo mas mostrando apenas a última aba
                    # Modificar o HTML para mostrar apenas a última aba por padrão
                    final_html = html_content
                    # Forçar a última aba a ficar ativa
                    final_html = final_html.replace(
                        'active" data-idx="4"',
                        'active" data-idx="4" style="display:block !important;"'
                    )
                    # Esconder as outras abas
                    for i in range(5):
                        if i != 4:
                            final_html = final_html.replace(
                                f'id="{prefix}-p-{i}"',
                                f'id="{prefix}-p-{i}" style="display:none !important;"'
                            )
                    # Adicionar estilo para remover as tabs
                    final_html = final_html.replace(
                        f'<div class="{prefix}-tabs"',
                        f'<div class="{prefix}-tabs" style="display:none;"'
                    )

                tmp_html = qdir / f'_tmp_{label}.html'
                tmp_html.write_text(final_html, encoding='utf-8')

                try:
                    with sync_playwright() as p:
                        browser = p.chromium.launch()

                        # 1ª passagem: mede as dimensões reais do conteúdo
                        page = browser.new_page(viewport={'width': 900, 'height': 600},
                                                device_scale_factor=scale)
                        page.goto(f'file://{tmp_html.resolve()}')
                        page.wait_for_timeout(1500)

                        dims = page.evaluate('''() => ({
                            width:  document.body.scrollWidth,
                            height: document.body.scrollHeight
                        })''')

                        real_w = max(dims['width'], 1)
                        real_h = max(dims['height'], 1)

                        # 2ª passagem: viewport exato → screenshot sem corte
                        page.set_viewport_size({'width': real_w, 'height': real_h})
                        page.wait_for_timeout(300)  # re-render após resize
                        page.screenshot(path=str(png_path), full_page=False)

                        browser.close()

                    # Grava o DPI real refletindo o device_scale_factor usado.
                    # Sem isso, o PNG fica com pixels 'scale'x maiores do que o
                    # tamanho físico intencionado, e qualquer cálculo posterior
                    # (ex.: _patch_html_cells_for_pdf) que faça w/dpi vai achar
                    # a imagem maior do que realmente é.
                    if scale != 1.0:
                        with Image.open(png_path) as im:
                            im.save(png_path, dpi=(96 * scale, 96 * scale))

                    print(f'  📸 Screenshot: {png_path.name}')
                except Exception as e:
                    print(f'  ⚠ Falha screenshot {label}: {e}')
                finally:
                    tmp_html.unlink(missing_ok=True)

def _fix_html_outputs_for_pdf(nb_root: Path):
    """Remove 'text/plain: <IPython.core.display.HTML object>' de todos os outputs."""

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

from PIL import Image

def _capture_html_output_as_png(html_content: str, out_path: Path,
                                  width: int = 900, height: int = 600,
                                  target_dpi: int = 175,
                                  max_print_width_in: float = 6.3,
                                  max_print_height_in: float = 9.0) -> bool:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    wrapper = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  body {{ margin: 0; padding: 12px; background: white; font-family: sans-serif; }}
</style>
</head>
<body>
{html_content}
</body></html>"""

    tmp_html = out_path.with_suffix('.tmp.html')
    tmp_html.write_text(wrapper, encoding='utf-8')

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={'width': width, 'height': height})
            page.goto(f'file://{tmp_html.resolve()}')
            page.wait_for_timeout(800)

            content_size = page.evaluate("""
                () => ({
                    width: Math.ceil(document.documentElement.scrollWidth),
                    height: Math.ceil(document.documentElement.scrollHeight)
                })
            """)
            page.set_viewport_size({
                'width': max(content_size['width'], width),
                'height': max(content_size['height'], height)
            })
            page.wait_for_timeout(200)
            page.screenshot(path=str(out_path), full_page=True)
            browser.close()

        # ── Pós-processamento: redimensiona pro DPI de impressão-alvo ──
        with Image.open(out_path) as im:
            w, h = im.size

            # Tamanho máximo em pixels permitido pra caber na página, no DPI escolhido
            max_w_px = int(max_print_width_in * target_dpi)
            max_h_px = int(max_print_height_in * target_dpi)

            scale = min(max_w_px / w, max_h_px / h, 1.0)  # nunca amplia, só reduz

            if scale < 1.0:
                new_w, new_h = int(w * scale), int(h * scale)
                im = im.resize((new_w, new_h), Image.LANCZOS)

            im.save(out_path, dpi=(target_dpi, target_dpi), optimize=True)

        return True
    except Exception as e:
        print(f'    ✗ Falha ao capturar {out_path.name}: {e}')
        return False
    finally:
        tmp_html.unlink(missing_ok=True)

def _verify_and_fix_screenshots(qdir: Path, all_root: Path = Path('all')):
    """Verifica e corrige o caminho das imagens."""
    
    # A imagem deve estar em: all/cap04/imagens/fig-04-algoritmo-rotulagem2.png
    img_path = all_root / 'cap04' / 'imagens' / 'fig-04-algoritmo-rotulagem2.png'
    
    print(f'  ℹ Verificando imagem: {img_path}')
    print(f'  ℹ Existe? {img_path.exists()}')
    
    if not img_path.exists():
        # Tentar encontrar em outro local
        alt_path = qdir / 'cap04' / 'imagens' / 'fig-04-algoritmo-rotulagem2.png'
        print(f'  ℹ Procurando em: {alt_path}')
        print(f'  ℹ Existe? {alt_path.exists()}')
        
        if alt_path.exists():
            # Copiar para o local correto
            img_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(alt_path, img_path)
            print(f'  ✓ Imagem copiada para: {img_path}')
    
    return img_path.exists()
                 
def _patch_html_cells_for_pdf(qdir: Path, all_root: Path = Path('all')):

    nb_root = qdir.parent.parent / qdir.name
    locale = qdir.name.split('.')[-1]
    import re

    HTML_TRIPLE_RE = re.compile(r'HTML\(\s*[a-zA-Z]{0,2}["\']{3}')

    for nb_path in nb_root.rglob('*.ipynb'):
        real_path = nb_path.resolve()
        nb = nbformat.read(real_path, as_version=4)
        modified = False
        new_cells = []

        # Detecta se há alguma célula HTML(""" ... """) sem PNG correspondente
        # ANTES de decidir se precisa executar o notebook (evita custo desnecessário)
        needs_execution = False
        cap_guess = None
        for part in nb_path.parts:
            if re.match(r'cap\d+', part):
                cap_guess = part
                break

                
        for cell in nb.cells:
            if cell.cell_type != 'code' or not HTML_TRIPLE_RE.search(cell.source):
                continue
            
            m_label = re.search(r'#\|\s*label:\s*(\S+)', cell.source)
            if not m_label or not cap_guess:
                continue
            label = m_label.group(1)
            png_abs = _resolve_screenshot_png(all_root, cap_guess, label, locale)
            if not png_abs.exists():
                needs_execution = True
                break

        executed_nb = None
        if needs_execution:
            try:
                print(f'  ⚙ Executando notebook para gerar PNGs ausentes: {nb_path.name}')
                executed_nb = nbformat.from_dict(nb)
                client = NotebookClient(
                    executed_nb, timeout=120, kernel_name='python3',
                    resources={'metadata': {'path': str(real_path.parent)}}
                )
                client.execute()
            except Exception as e:
                print(f'    ✗ Erro ao executar notebook {nb_path.name}: {e}')
                executed_nb = None

        for idx, cell in enumerate(nb.cells):
            if cell.cell_type != 'code' or not HTML_TRIPLE_RE.search(cell.source):
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

            # png_abs: qual arquivo LER (localizado, com fallback pro
            # canônico pt) — png_target: onde ESCREVER se precisar gerar um
            # novo (sempre o slot do locale atual, nunca sobrescreve o pt).
            png_abs = _resolve_screenshot_png(all_root, cap, label, locale) if cap else None
            png_target = _screenshot_png_path(all_root, cap, label, locale) if cap else None
            png_exists = png_abs and png_abs.exists()

            # ── Geração automática se ainda não existir ──────────────────
            if not png_exists and executed_nb is not None and png_target is not None:
                try:
                    exec_cell = executed_nb.cells[idx]
                    html_out = None
                    for out in exec_cell.get('outputs', []):
                        if out.get('output_type') == 'execute_result':
                            html_out = out.get('data', {}).get('text/html')
                            if html_out:
                                break
                    if html_out:
                        ok = _capture_html_output_as_png(html_out, png_target)
                        if ok:
                            print(f'  ✓ PNG gerado automaticamente: {png_target.name}')
                            png_abs = png_target
                            png_exists = True
                        else:
                            print(f'  ⚠ Falha ao gerar PNG: {label}')
                    else:
                        print(f'  ⚠ Sem output HTML para gerar PNG: {label}')
                except Exception as e:
                    print(f'  ⚠ Erro gerando PNG de {label}: {e}')

            # A referência no markdown usa sempre o nome-base (sem sufixo de
            # locale) — dentro de gen/<combo>/capXX/imagens/ esse nome já é
            # um symlink pro arquivo certo (localizado, se existir; senão o
            # canônico pt), via `_symlink_imagens_locale_aware`. Referenciar
            # o nome com sufixo aqui quebraria: esse arquivo só existe em
            # all/capXX/imagens/ (fonte), não dentro da árvore do combo.
            png_rel = f'imagens/{label}.png'

            if png_exists:
                new_cells.append(nbformat.v4.new_markdown_cell(
                    '::: {.content-visible when-format="html"}'
                ))
                cell.outputs = []
                cell.execution_count = None
                new_cells.append(cell)
                cap_str = fig_cap or label

                width_attr = ''
                try:
                    from PIL import Image
                    with Image.open(png_abs) as im:
                        w, h = im.size

                    aspect = w / h

                    PAGE_CONTENT_WIDTH_IN = 7.09
                    PAGE_CONTENT_HEIGHT_IN = 10.12

                    CM_TO_IN = 1 / 2.54
                    CAPTION_RESERVE_IN = 1 * CM_TO_IN  # ~0.3937in reservado pra legenda

                    # altura útil real, descontando a legenda
                    AVAILABLE_HEIGHT_IN = PAGE_CONTENT_HEIGHT_IN - CAPTION_RESERVE_IN

                    height_at_full_width_in = PAGE_CONTENT_WIDTH_IN / aspect

                    if height_at_full_width_in <= AVAILABLE_HEIGHT_IN:
                        width_attr = ' width=100%'
                    else:
                        # força largura total + altura no limite (já descontando legenda) -> distorce levemente
                        width_attr = f' width=100% height={AVAILABLE_HEIGHT_IN:.3f}in'

                    # exceção manual: simulador cdil fica exagerado em 100%, forçar 50%
                    # if png_abs.stem == 'fig-04-sim-cdil':
                    #     width_attr = ' width=50%'

                except Exception:
                    pass

                new_cells.append(nbformat.v4.new_markdown_cell(':::'))
                new_cells.append(nbformat.v4.new_markdown_cell(
                    f'::: {{.content-visible when-format="pdf"}}\n'
                    f'![ {cap_str} ]({png_rel}){{#fig-{label[4:]}{width_attr}}}\n'
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

def _autocrop_screenshots(all_root: Path, exclude: set = None) -> None:
    """Remove bordas brancas sobrando dos PNGs de simuladores gerados via screenshot.
    Roda depois de toda a geração/patch de imagens, antes da renderização do PDF.
    """
    from PIL import Image, ImageChops

    def _bbox_is_full(bbox, size, tol=3):
        """Considera 'já cortado' se o bbox está a poucos pixels da borda total."""
        l, t, r, b = bbox
        w, h = size
        return l <= tol and t <= tol and (w - r) <= tol and (h - b) <= tol

    exclude = exclude or set()
    pngs = list(all_root.glob('cap*/imagens/*.png'))
    changed = 0

    for png_path in pngs:
        if png_path.name in exclude:
            continue
        try:
            img = Image.open(png_path).convert('RGB')
            bg = Image.new('RGB', img.size, img.getpixel((0, 0)))
            diff = ImageChops.difference(img, bg)
            diff = diff.point(lambda p: 255 if p > 8 else 0)
            bbox = diff.getbbox()
            if bbox is None or _bbox_is_full(bbox, img.size):
                continue
            img.crop(bbox).save(png_path)
            changed += 1
        except Exception as e:
            print(f'    ⚠ Autocrop falhou em {png_path.name}: {e}')

    print(f'    ✂ {changed}/{len(pngs)} imagens ajustadas')

def _render_pdf_with_patched_tex(qdir: Path, env: dict):
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
        timeout=3000,
        env=env,
    )
    if r.returncode != 0:
        print('  ⚠ Erro ao gerar .tex:')
        for line in (r.stderr or '').split('\n')[-10:]:
            if line.strip():
                print(f'      {line}')
        return

    _fix_tex_cover(qdir)

    # Busca .tex em qdir E em output_dir
    def _find_tex(search_dir: Path):
        return [
            t for t in search_dir.rglob('*.tex')   # ← rglob em vez de glob
            if t.name not in ('cover_hook.tex', 'fvextra.tex', 'capa.tex', 'preamble.tex')
            # Exclui qualquer .tex dentro de includes/ (recurso, nunca saída do
            # Quarto) — necessário desde que qdir/includes virou diretório real
            # com symlinks por arquivo (para mesclar includes/ + all/apendices/
            # imagens/): rglob agora desce nele, e sem este filtro pegava
            # includes/preamble.tex como se fosse o .tex do livro.
            and 'includes' not in t.relative_to(search_dir).parts
        ]

    tex_files = _find_tex(qdir)
    if not tex_files and output_dir.exists():
        tex_files = _find_tex(output_dir)

    if not tex_files:
        print('  ⚠ .tex não encontrado após patch')
        return

    tex_path = tex_files[0]
    output_dir.mkdir(parents=True, exist_ok=True)

    log_path = output_dir / f'{tex_path.stem}.log'
    RERUN_MARKERS = ('Rerun to get', 'Please rerun', 'Rerun LaTeX')
    FATAL_MARKERS = ('Emergency stop', 'Fatal error occurred')
    MIN_RUNS, MAX_RUNS = 3, 6

    print(f'  $ lualatex {tex_path.name} (até {MAX_RUNS}x, com checagem de convergência)')
    last_result = None
    log_text = ''
    fatal = False
    for run in range(1, MAX_RUNS + 1):
        last_result = subprocess.run(
            ['lualatex', '--interaction=nonstopmode',
             f'--output-directory={output_dir}', str(tex_path)],
            cwd=qdir,
            capture_output=True,
            text=True,
            timeout=3000,
            env=env,
        )

        log_text = log_path.read_text(encoding='utf-8', errors='replace') if log_path.exists() else ''
        fatal = any(m in log_text for m in FATAL_MARKERS)

        if fatal:
            print(f'  ⚠ Erro fatal no lualatex (run {run}/{MAX_RUNS}):')
            for line in (last_result.stdout or '').split('\n')[-15:]:
                if line.strip():
                    print(f'      {line}')
            break

        needs_rerun = any(m in log_text for m in RERUN_MARKERS)
        print(f'    run {run}/{MAX_RUNS}: {"precisa rerun (xref/TOC/geometria)" if needs_rerun else "convergiu"}')

        if run >= MIN_RUNS and not needs_rerun:
            break
    else:
        if any(m in log_text for m in RERUN_MARKERS):
            print(f'  ⚠ lualatex não convergiu totalmente após {MAX_RUNS} runs '
                  f'(ainda pede rerun) — TOC/numeração de página podem estar '
                  f'desatualizados no PDF final.')

    if not fatal and last_result is not None and last_result.returncode != 0:
        print('  ⚠ lualatex terminou com erro (não fatal) na última run:')
        for line in (last_result.stdout or '').split('\n')[-15:]:
            if line.strip():
                print(f'      {line}')

    # Removido o corte automático "pula as 2 primeiras páginas" que existia
    # aqui: era um remendo para 3 bugs reais na raiz (LaTeX) — comando
    # \KOMAoption órfão vazando texto literal na p.1, \fvset com chave só
    # do fvextra (não carregado) travando logo no \begin{document}, e
    # \newgeometry na capa despachando uma p.1 em branco por causa do seu
    # \clearpage embutido. Cortar sempre 2 páginas escondia isso em pt/en
    # mas desalinhava fr (contagem de página crua diferente por locale).
    # Com as 3 causas corrigidas na fonte, o PDF já sai com a paginação
    # certa sem precisar remendar depois.

    _rename_pdf(qdir, combo_name, file_key)

def _fix_tex_cover(qdir: Path):

    # ═════════════════════════════════════════════════════════════
    # INSERÇÃO DE HIPERLINKS CLICÁVEIS NOS SIMULADORES DO PDF
    # ═════════════════════════════════════════════════════════════
    combo_name = qdir.name
    _combo = parse_combo(combo_name)
    # UI_STRINGS['fr']['title'] tem um "&" literal (e outros locales podem
    # ganhar um no futuro) — escapa pra LaTeX antes de injetar no
    # cover_block (LaTeX puro, não passa pelo escaping automático do
    # Pandoc como o \title{} que ele mesmo gera). Sem isso o "&" já vazio
    # some silenciosamente da folha de rosto em vez de dar erro óbvio.
    _cover_title = UI_STRINGS[_combo.locale]['title'].replace('&', r'\&')
    _cover_subtitle = (UI_STRINGS[_combo.locale]['pdf_subtitle']
                       .format(lang_label=LANGUAGES[_combo.lang].label)
                       .replace('&', r'\&'))


    def _replace_sim_with_link(match):
        full_fig_env = match.group(0)
        
        # FILTRO RÍGIDO: Procura especificamente por rótulos de simuladores válidos (-sim-ep ou -sim-[nome])
        # Ignora qualquer outra imagem (como botões, logos ou figuras comuns)
        label_match = re.search(r'\\label\{(fig-\d+-sim-(?:ep\d{4}[a-z]?|[a-z0-9-]+))\}', full_fig_env)
        
        if not label_match:
            return full_fig_env # Retorna a figura intacta se não for um simulador válido!
            
        label_full = label_match.group(1) # ex: fig-01-sim-ep0101-distancia
        
        # Remove o prefixo fig-XX- para isolar o nome interno do simulador
        sim_name = re.sub(r'^fig-\d+-', '', label_full) # ex: sim-ep0101-distancia
        
        # Se porventura ainda restar algum nome antigo não unificado, força a conversão canônica
        if sim_name == 'sim-metricas-distancia':
            sim_name = 'sim-ep0101-distancia'
        elif sim_name == 'sim-estatisticas-pixels':
            sim_name = 'sim-ep0104-estatisticas'
        elif sim_name == 'sim-filtro-maximo-1d':
            sim_name = 'sim-ep0111-filtro-maximo'
            
        # Descobre o número correto do capítulo a partir do label
        cap_match = re.search(r'fig-(\d+)-', label_full)
        if cap_match:
            cap_num = cap_match.group(1)
            cap_folder = f"cap{cap_num}"
        else:
            cap_folder = "cap01"
        
        # Correção de consistência para o Ransac
        if sim_name == 'sim-ransac_registro':
            sim_name = 'sim-ransac-registro'
        
        # Monta a URL oficial correta no GitHub Pages
        target_url = f"https://fzampirolli.github.io/pdi-vc/simuladores/{combo_name}/{cap_folder}/{sim_name}.html"
        
        # 1. Envolve a imagem com o link do hyperref (\href)
        linked_fig = re.sub(
            r'(\\includegraphics[^}]+\}{[^}]+\})',
            r'\\href{' + target_url + r'}{\1}',
            full_fig_env
        )
        
        # 2. Insere o texto com o link clicável logo antes do comando \caption (com espaçamento reduzido)
        link_text = rf'\vspace{{0mm}}\noindent\small\textbf{{Versão interativa:}} \url{{{target_url}}}\par\vspace{{-2mm}}'
        linked_fig = linked_fig.replace(r'\caption', f'{link_text}\n\\caption')

        return linked_fig


    cover_abs_file = qdir / '.cover_abs'
    if not cover_abs_file.exists():
        print('  ⚠ .cover_abs não encontrado, pulando patch do .tex')
        return
    cover_abs = cover_abs_file.read_text(encoding='utf-8').strip()

    combo_name = qdir.name
    output_dir = qdir.parent.parent / 'book' / combo_name

    def _find_tex(search_dir: Path):
        return [
            t for t in search_dir.rglob('*.tex')
            if t.name not in ('cover_hook.tex', 'fvextra.tex', 'capa.tex', 'preamble.tex')
            and 'includes' not in t.relative_to(search_dir).parts
        ]

    tex_files = _find_tex(qdir)
    if not tex_files and output_dir.exists():
        tex_files = _find_tex(output_dir)
        
    if not tex_files:
        print('  ⚠ Nenhum .tex encontrado para patch')
        return

    tex_path = tex_files[0]
    content = tex_path.read_text(encoding='utf-8')

    # ── Extrai a ficha catalográfica do corpo e prepara para mover
    #    para a contracapa (verso da folha de rosto) ──────────────
    ficha_match = re.search(
        r'% FICHA_CATALOGRAFICA_START.*?% FICHA_CATALOGRAFICA_END',
        content,
        flags=re.DOTALL,
    )
    if ficha_match:
        ficha_tex = ficha_match.group(0)
        content = content.replace(ficha_tex, '', 1)
        
        # Remove a casca do capítulo vazio gerada pelo Quarto no corpo do .tex.
        # O título renderizado depende do locale (ver UI_STRINGS[locale]['cip_title']
        # e includes/ficha_catalografica_<locale>.qmd) — sem cobrir todas as
        # variantes, o capítulo residual só era removido em pt, sobrando um
        # "Cataloging-in-Publication (CIP) Data" duplicado no corpo do en/fr.
        # `\s+` (não um espaço literal) entre as palavras: o pandoc quebra
        # títulos longos em várias linhas dentro do próprio \chapter{...},
        # então "(CIP)" e "Data" acabam separados por uma quebra de linha,
        # não um espaço — um espaço literal no regex não bate com \n.
        cip_title_re = r'\s+'.join(
            re.escape(w) for w in UI_STRINGS[_combo.locale]['cip_title'].split(' ')
        )
        content = re.sub(
            r'\\chapter\*?\{' + cip_title_re + r'\}.*?(?=\\chapter|\\part|\\bookmarksetup|\Z)',
            '',
            content,
            flags=re.DOTALL
        )
        print('  ✓ Ficha catalográfica extraída do corpo e capítulo residual removido')
    else:
        ficha_tex = ''
        print('  ⚠ Marcadores da ficha catalográfica não encontrados — posição não alterada')
        
    # Remove babel do Pandoc para evitar conflito com o nosso
    content = re.sub(
        r'\\usepackage\[.*?babel.*?\]\{babel\}|\\usepackage\{babel\}',
        '',
        content
    )
    content = re.sub(
        r'\\babelprovide\[.*?\]\{.*?\}',
        '',
        content
    )

    # ── 1. Ajusta a Classe do Documento e Remove Lixo do KOMA ──────────
    # Substitui qualquer documentclass antigo pelo padrão correto diretamente
    content = re.sub(
        r'\\documentclass\[.*?\]\{(?:scrreprt|scrbook|book)\}',
        #r'\\documentclass[a4paper,11pt,oneside,openany]{book}',
        r'\\documentclass[a4paper,11pt,twoside,openright]{book}', # frente e verso
        content,
        count=1,
        flags=re.DOTALL
    )
    content = re.sub(r'\\KOMAoptions\{.*?\}', '', content, flags=re.DOTALL)
    # \KOMAoption{...}{...} (singular, dois argumentos) é outro comando do
    # KOMA-script que o Pandoc também emite (ex.: \KOMAoption{captions}
    # {tableheading}) e que o regex acima (plural, um argumento) não pega.
    # Como trocamos a classe pra `book` puro (não-KOMA) alguns parágrafos
    # abaixo, esse comando fica indefinido — em vez de erro, o LaTeX larga
    # os argumentos como texto literal na página ("captionstableheading"),
    # que sobrava bem no topo da primeira página do livro.
    content = re.sub(r'\\KOMAoption\{.*?\}\{.*?\}', '', content, flags=re.DOTALL)
    content = re.sub(r'\\setkomafont\{.*?\}\{.*?\}', '', content)
    print('  ✓ Classe de página e KOMA ajustados')

    # ── 2. Remove cabeçalhos e TOC nativos do Pandoc ───────────────────
    # Remove tudo entre \begin{document} e \bookmarksetup
    content = re.sub(
        r'(\\begin\{document\})\s*.*?(?=\\bookmarksetup)',
        r'\1\n',
        content,
        count=1,
        flags=re.DOTALL
    )
    # Remove limpezas residuais do bookmark e TOC antigo do Pandoc
    content = re.sub(
        r'\\bookmarksetup\{startatroot\}\s*'
        r'(?:\\renewcommand\*?\\contentsname.*?'
        r'\\(?:tableofcontents|bookmarksetup).*?\n)?',
        r'\\bookmarksetup{startatroot}\n',
        content,
        flags=re.DOTALL
    )
    content = re.sub(r'\{\\hypersetup.*?\\tableofcontents\s*\}\s*', '', content, flags=re.DOTALL)

    # ── 3. Preparação dos Blocos de Injeção (Preâmbulo e Capa) ─────────
    custom_header = r"""
% ─────────────────────────────────────────────────────────────
% fvextra — precisa vir cedo: \AtBeginDocument mais abaixo chama
% \fvset{breaksymbolleft=...}, uma chave que só existe no fvextra (extensão
% do fancyvrb), não no fancyvrb puro que o Pandoc já carrega sozinho. Sem
% isso, \fvset falha logo em \begin{document} com "Package keyval Error:
% breaksymbolleft undefined" — e a tentativa do LaTeX de se recuperar do
% erro comia parte do conteúdo seguinte, incluindo a capa (por isso as
% páginas em branco no início do PDF, mesmo depois de corrigido o
% \KOMAoption e a estrutura de titlepage).
\usepackage{fvextra}
\usepackage{eso-pic}
% ─────────────────────────────────────────────────────────────
% Layout geral e Cores
% ─────────────────────────────────────────────────────────────
\usepackage{geometry}
\geometry{
  a4paper, left=1.5cm, right=1.5cm, top=2.0cm, bottom=2.0cm,
  headheight=14pt, headsep=0.7cm, footskip=1.0cm
}
\usepackage{xcolor}
\definecolor{darkblue}{RGB}{18,52,86}
\definecolor{lightblue}{RGB}{90,125,170}
\definecolor{codebg}{RGB}{240,244,255}
\definecolor{codeborder}{RGB}{112,144,208}
\definecolor{outputbg}{RGB}{253,246,236}
\definecolor{outputborder}{RGB}{232,168,64}

% ─────────────────────────────────────────────────────────────
% Links & Cabeçalho/Rodapé Frente e Verso (fancyhdr)
% ─────────────────────────────────────────────────────────────
\usepackage{fancyhdr}
\pagestyle{fancy}
\fancyhf{} % Limpa tudo

\setlength{\headheight}{15pt}
\renewcommand{\headrulewidth}{0.3pt}
\renewcommand{\footrulewidth}{0.3pt}
\renewcommand{\headrule}{\hbox to\headwidth{\color{lightblue}\leaders\hrule height \headrulewidth\hfill}}
\renewcommand{\footrule}{\hbox to\headwidth{\color{lightblue}\leaders\hrule height \footrulewidth\hfill}}

% ── CABEÇALHO (TOPO) ──
% LE (Par / Esquerda - Borda Externa): Número da página
\fancyhead[LE]{\small\bfseries\textcolor{darkblue}{\thepage}}
% RE (Par / Direita - Borda Interna): Título Geral do Livro
\fancyhead[RE]{\small\textcolor{darkblue}{\textsc{BRAND_TAG_PLACEHOLDER}}}

% LO (Ímpar / Esquerda - Borda Interna): Capítulo Atual
\fancyhead[LO]{\small\textcolor{gray}{\nouppercase{\leftmark}}}
% RO (Ímpar / Direita - Borda Externa): Número da página
\fancyhead[RO]{\small\bfseries\textcolor{darkblue}{\thepage}}

% ── RODAPÉ (BOTTOM) ──
% Informações discretas no rodapé
\fancyfoot[LE]{\small\textcolor{gray}{Francisco de Assis Zampirolli}}
\fancyfoot[RE]{\small\textcolor{lightblue}{UFABC}}
\fancyfoot[LO]{\small\textcolor{lightblue}{UFABC}}
\fancyfoot[RO]{\small\textcolor{gray}{Francisco de Assis Zampirolli}}

% ── ESTILO PLAIN (1ª página de cada capítulo) ──
% Agora também exibe cabeçalho, igual às demais páginas
\fancypagestyle{plain}{
  \fancyhf{}
  \renewcommand{\headrulewidth}{0.3pt}
  \renewcommand{\footrulewidth}{0.3pt}
  \renewcommand{\headrule}{\hbox to\headwidth{\color{lightblue}\leaders\hrule height \headrulewidth\hfill}}
  \renewcommand{\footrule}{\hbox to\headwidth{\color{lightblue}\leaders\hrule height \footrulewidth\hfill}}
  \fancyhead[LE]{\small\bfseries\textcolor{darkblue}{\thepage}}
  \fancyhead[RE]{\small\textcolor{darkblue}{\textsc{BRAND_TAG_PLACEHOLDER}}}
  \fancyhead[LO]{\small\textcolor{gray}{\nouppercase{\leftmark}}}
  \fancyhead[RO]{\small\bfseries\textcolor{darkblue}{\thepage}}
  \fancyfoot[LE]{\small\textcolor{gray}{Francisco de Assis Zampirolli}}
  \fancyfoot[RE]{\small\textcolor{lightblue}{UFABC}}
  \fancyfoot[LO]{\small\textcolor{lightblue}{UFABC}}
  \fancyfoot[RO]{\small\textcolor{gray}{Francisco de Assis Zampirolli}}
}

% Faz com que páginas em branco geradas automaticamente não tenham cabeçalho/rodapé
\makeatletter
\def\cleardoublepage{\clearpage\if@twoside \ifodd\c@page\else
  \hbox{}
  \thispagestyle{empty}
  \newpage
  \if@twocolumn\hbox{}\newpage\fi\fi\fi}
\makeatother

% ─────────────────────────────────────────────────────────────
% Estilização de Títulos e Blocos de Código
% ─────────────────────────────────────────────────────────────
\usepackage{titlesec}
\titleformat{\chapter}[display]{\normalfont\bfseries}{\filleft\Huge\textcolor{lightblue}{\chaptertitlename}\hspace{0.5em}\textcolor{darkblue}{\thechapter}}{1ex}{\titlerule[1pt]\vspace{1.5ex}\Huge\color{darkblue}\filleft}[\vspace{1ex}\titlerule]
\titlespacing*{\chapter}{0pt}{0pt}{28pt}
\titleformat{\section}{\Large\bfseries\color{darkblue}}{\thesection}{0.7em}{}
\titleformat{\subsection}{\large\bfseries\color{darkblue}}{\thesubsection}{0.6em}{}

\usepackage[skins,breakable]{tcolorbox}
\tcbset{
  pdicode/.style={enhanced, breakable, colback=codebg, colframe=codeborder, leftrule=4pt, rightrule=0.4pt, toprule=0.4pt, bottomrule=0.4pt, arc=4pt, boxsep=0pt, left=6pt, right=6pt, top=4pt, bottom=4pt, fontupper=\small\ttfamily},
  pdioutput/.style={enhanced, breakable, colback=outputbg, colframe=outputborder, leftrule=4pt, rightrule=0.4pt, toprule=0.4pt, bottomrule=0.4pt, arc=4pt, boxsep=0pt, left=6pt, right=6pt, top=4pt, bottom=4pt, fontupper=\small\ttfamily}
}

% ─────────────────────────────────────────────────────────────
% Idioma e Tradução Global
% ─────────────────────────────────────────────────────────────
\usepackage[BABEL_LANG_PLACEHOLDER]{babel}
\babelprovide[main, import]{BABEL_LANG_PLACEHOLDER}
% O \AtBeginDocument do próprio Pandoc (que reaplica \contentsname etc. a
% partir da tradução do babel) é registrado ANTES deste ponto no .tex —
% \renewcommand direto aqui roda na hora (durante o preâmbulo, antes de
% \begin{document}), então o hook do Pandoc, que só dispara em
% \begin{document}, rodaria DEPOIS e desfaria nossos nomes (pt virava
% "Índice" de novo mesmo com isto setado pra "Sumário"). Hooks de
% \AtBeginDocument disparam na ordem de registro — colocando o nosso
% também em \AtBeginDocument, e depois do bloco do Pandoc no arquivo,
% garante que o nosso rode por último e vença.
\AtBeginDocument{
\renewcommand{\contentsname}{CONTENTS_NAME_PLACEHOLDER}
\renewcommand{\listfigurename}{LIST_FIGURES_NAME_PLACEHOLDER}
\renewcommand{\listtablename}{LIST_TABLES_NAME_PLACEHOLDER}
\renewcommand{\figurename}{FIGURE_NAME_PLACEHOLDER}
\renewcommand{\tablename}{TABLE_NAME_PLACEHOLDER}
\renewcommand{\chaptername}{CHAPTER_NAME_PLACEHOLDER}
\renewcommand{\partname}{PART_NAME_PLACEHOLDER}
\renewcommand{\appendixname}{APPENDIX_NAME_PLACEHOLDER}
}

\usepackage{emoji}
\setemojifont{EMOJI_FONT_PLACEHOLDER}

\AtBeginDocument{
  \fvset{breaklines=true, breaksymbolleft={}}

  \renewenvironment{Shaded}{\begin{tcolorbox}[pdicode]}{\end{tcolorbox}}
  \renewenvironment{verbatim}{\VerbatimEnvironment\begin{tcolorbox}[pdioutput]\begin{Verbatim}[breaklines=true,breaksymbol={}]}{\end{Verbatim}\end{tcolorbox}}
  
}
""".replace('EMOJI_FONT_PLACEHOLDER', EMOJI_FONT) \
    .replace('BRAND_TAG_PLACEHOLDER', UI_STRINGS[_combo.locale]['brand_tag']) \
    .replace('BABEL_LANG_PLACEHOLDER', UI_STRINGS[_combo.locale]['babel_lang']) \
    .replace('CONTENTS_NAME_PLACEHOLDER', UI_STRINGS[_combo.locale]['contents_name']) \
    .replace('LIST_FIGURES_NAME_PLACEHOLDER', UI_STRINGS[_combo.locale]['list_figures_name']) \
    .replace('LIST_TABLES_NAME_PLACEHOLDER', UI_STRINGS[_combo.locale]['list_tables_name']) \
    .replace('FIGURE_NAME_PLACEHOLDER', UI_STRINGS[_combo.locale]['figure_name']) \
    .replace('TABLE_NAME_PLACEHOLDER', UI_STRINGS[_combo.locale]['table_name']) \
    .replace('CHAPTER_NAME_PLACEHOLDER', UI_STRINGS[_combo.locale]['chapter_name']) \
    .replace('PART_NAME_PLACEHOLDER', UI_STRINGS[_combo.locale]['part_name']) \
    .replace('APPENDIX_NAME_PLACEHOLDER', UI_STRINGS[_combo.locale]['appendix_name'])

    cover_block = rf"""
% NOTA: \begin{{titlepage}}...\end{{titlepage}} do LaTeX faz \newpage (e
% \setcounter{{page}}{{1}}) já no \begin — usado como primeiro elemento do
% documento (nada ainda foi despachado), esse \newpage força uma página
% em branco extra antes do conteúdo aparecer. Por isso as 3 seções abaixo
% (capa, verso em branco, folha de rosto) usam \thispagestyle{{empty}} +
% \clearpage manualmente, sem o ambiente titlepage, evitando a página
% fantasma. \frontmatter também foi trocado por só \pagenumbering{{roman}}
% (mais abaixo) pelo mesmo motivo: seu \cleardoublepage embutido, chamado
% antes de qualquer conteúdo existir, também gera uma página em branco.

% ── 1. Imagem da Capa (Página 1 - Ímpar / Frente) ─────────────────
% \newgeometry (usado antes pra zerar a margem só na capa) tem um
% \clearpage embutido. Chamado logo no \begin{{document}}, antes de
% qualquer conteúdo existir na página, esse \clearpage despachava uma
% página 1 EM BRANCO (nada acumulado ainda pra "descarregar") antes da
% capa aparecer só na página 2 — a real origem da página em branco no
% início do PDF (o \KOMAoption e o fvextra, corrigidos acima, eram
% bugs reais mas não este). eso-pic evita o problema: desenha a capa
% como imagem de fundo em posição absoluta, sem precisar mudar a
% geometria da página (logo sem o \clearpage embutido do \newgeometry).
\AddToShipoutPictureBG*{{%
  \put(0,0){{\includegraphics[width=\paperwidth, height=\paperheight]{{{cover_abs}}}}}%
}}
\thispagestyle{{empty}}
\mbox{{}}
\clearpage

% ── 2. Verso da Capa (Página 2 - Par / Página em Branco) ──────────
\thispagestyle{{empty}}
\null
\clearpage

% ── 3. Folha de Rosto (Página 3 - Ímpar / Frente) ─────────────────
\thispagestyle{{empty}}
\vspace*{{3cm}}
\begin{{center}}
{{\Huge\bfseries\color{{darkblue}} {_cover_title}\par}}
\vspace{{1.2cm}}
{{\Large {_cover_subtitle}\par}}
\vspace{{3cm}}
{{\Large Francisco de Assis Zampirolli\par}}
\vfill
{{\large Universidade Federal do ABC\par}}
\vspace{{0.5cm}}
{{\large \today\par}}
\end{{center}}
\clearpage

% ── 4. Ficha catalográfica (Página 4 - Par / Verso da folha de rosto) ──
{ficha_tex}

% ── Ajustes do Sumário e Início do Texto ────────────────────────
\cleardoublepage
\pagenumbering{{roman}}
\pagestyle{{plain}}
\makeatother
\tableofcontents
\cleardoublepage
\listoffigures
\cleardoublepage
\listoftables
\cleardoublepage
\mainmatter
\pagestyle{{fancy}}
"""

    # Varre as figuras do .tex garantindo que o pattern exija a estrutura de um simulador real
    content = re.sub(
        r'\\begin\{figure\}(?:(?!\\end\{figure\}).)*?\\label\{fig-\d+-sim-(?:ep\d{4}[a-z]?|[a-z0-9-]+)\}(?:(?!\\end\{figure\}).)*?\\end\{figure\}',
        _replace_sim_with_link,
        content,
        flags=re.DOTALL
    )
    print('  ✓ Links interativos injetados estritamente nos simuladores válidos')
    # ═════════════════════════════════════════════════════════════

    # Injeta o preâmbulo e a capa em uma única substituição estruturada
    content = content.replace(
        r'\begin{document}',
        f"{custom_header}\n\\begin{{document}}\n{cover_block}",
        1
    )
    print('  ✓ Preâmbulo e Capa injetados com sucesso')

    # Nomes de Sumário/Lista de Figuras/Lista de Tabelas/etc. já saem no
    # idioma certo via custom_header (UI_STRINGS[_combo.locale]) — o bloco
    # que existia aqui sobrescrevia esses nomes para português de forma
    # incondicional (resquício de quando o livro era só em pt), quebrando
    # os nomes corretos que o próprio Pandoc já gera para en/fr.


    # ── Contracapa ───────────────────────────────────────────────
    project_root = qdir.parent.parent.parent
    back_cover_abs = _locale_asset(
        project_root / 'includes' / 'girassol_contracapa.png', _combo.locale
    ).resolve()

    if back_cover_abs.exists():
        back_cover_block = rf"""
\clearpage
% Garante que a contracapa externa fique em página par
\ifodd\value{{page}}
  \thispagestyle{{empty}}
  \mbox{{}}
  \clearpage
\fi
\thispagestyle{{empty}}
\newgeometry{{margin=0pt}}
\noindent
\includegraphics[width=\paperwidth, height=\paperheight]{{{back_cover_abs}}}
\restoregeometry
"""
        content = content.replace(
            r'\end{document}',
            f"{back_cover_block}\n\\end{{document}}",
            1
        )
        print('  ✓ Contracapa injetada com sucesso')
    else:
        print(f'  ⚠ Arquivo de contracapa não encontrado: {back_cover_abs}')


    # ═════════════════════════════════════════════════════════════
    # SEU NOVO BLOCO DE CAPTURA/AUDITORIA AQUI:
    # ═════════════════════════════════════════════════════════════
    todos_os_codigos = re.findall(r'\\begin\{Highlighting\}(.*?)\\end\{Highlighting\}', content, flags=re.DOTALL)
    todas_as_saidas  = re.findall(r'\\begin\{verbatim\}(.*?)\\end\{verbatim\}', content, flags=re.DOTALL)
    
    # Exemplo: Salvando um relatório rápido se você quiser debugar
    print(f"  ℹ Total de blocos de código encontrados no .tex: {len(todos_os_codigos)}")
    print(f"  ℹ Total de saídas de texto encontradas no .tex: {len(todas_as_saidas)}")
    # ═════════════════════════════════════════════════════════════

    # Salva o arquivo final atualizado
    tex_path.write_text(content, encoding='utf-8')
    print(f'  ✓ .tex patcheado: {tex_path.name}')

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

def _inject_favicon_into_generated_htmls(qdir: Path):
    """
    Varre a pasta final do livro e injeta o link do favicon.ico correto
    com base na profundidade do arquivo HTML.
    """
    # Descobre onde a pasta final de build (gen/book/...) está localizada
    combo_name = qdir.name
    book_dir = qdir.parent.parent / 'book' / combo_name
    
    if not book_dir.exists():
        return

    print(f'  🔧 Ajustando favicon em todos os HTMLs de {book_dir.name}...')

    # Copia o favicon.ico para a raiz da pasta final se não existir
    fav_src = qdir / 'favicon.ico'
    if fav_src.exists():
        shutil.copy2(fav_src, book_dir / 'favicon.ico')

    # Varre todos os arquivos .html gerados
    for html_path in book_dir.rglob('*.html'):
        text = html_path.read_text(encoding='utf-8')
        
        # Se já tiver alguma tag de favicon antiga inserida, removemos para evitar duplicatas
        text = re.sub(r'<link rel="[^"]*icon"[^>]*>', '', text)
        
        # Calcula a distância do arquivo até a pasta raiz (book_dir)
        # Se estiver na raiz (index.html), href="favicon.ico"
        # Se estiver em cap01/, href="../favicon.ico"
        # Se estiver em cap01/subfolder/, href="../../favicon.ico"
        depth = len(html_path.relative_to(book_dir).parts) - 1
        prefix = '../' * depth if depth > 0 else './'
        
        favicon_tag = f'<link rel="icon" type="image/x-icon" href="{prefix}favicon.ico">'
        
        # Injeta a tag logo após a abertura do <head>
        if '<head>' in text and favicon_tag not in text:
            text = text.replace('<head>', f'<head>\n  {favicon_tag}', 1)
            html_path.write_text(text, encoding='utf-8')

def render_quarto(qdir: Path, fmt: str, all_root: Path = Path('all'), verbose: bool = False):
    # Cria arquivo sentinela para testsuite.py detectar ambiente Quarto
    sentinela = qdir / '.quarto_render'
    sentinela.write_text('1', encoding='utf-8')

    def _fix_spurious_closing_div(qdir: Path, combo_name: str):
        """
        Corrige </main></div> espúrio gerado pelo Quarto/Pandoc no meio do documento.
        Causa: células com HTML grande (>~20KB) podem confundir o parser,
        que fecha </main> prematuramente dentro de uma figura.
        Fix: remove o </main></div> espúrio e reinsere </main> no lugar correto.
        """
        book_dir = qdir.parent.parent / 'book' / combo_name
        for html_path in book_dir.rglob('*.html'):
            text = html_path.read_text(encoding='utf-8')
            if '</main></div>' not in text or '<!-- /main -->' not in text:
                continue
            # 1. Remove </main></div> espúrio no meio do documento
            fixed = re.sub(r'((?:</section>)+)</main></div>', r'\1', text, count=1)
            # 2. Insere </main> antes de <!-- /main -->
            fixed = fixed.replace('<!-- /main -->', '</main>\n\n <!-- /main -->', 1)
            if fixed != text:
                html_path.write_text(fixed, encoding='utf-8')
                print(f'  ✓ Fix </main> espúrio: {html_path.name}')
    
    try:
        
          
      fmts = ['html', 'pdf'] if fmt == 'all' else [fmt]

      combo_name = qdir.name
      parts = combo_name.split('.')
      file_key = f'{parts[1]}.{parts[0]}'

      # Informa o locale ao kernel Python que executa os notebooks (lido por
      # morph/config.py via PDI_VC_LOCALE) para que mensagens como
      # "Ambiente pronto" saiam no idioma do combo sendo renderizado.
      os.environ['PDI_VC_LOCALE'] = parts[1]

      env = os.environ.copy()
      tinytex_path = _get_quarto_latex_path()
      if tinytex_path:
          env['PATH'] = tinytex_path + ':' + env['PATH']

      for f in fmts:
          env['QUARTO_FMT'] = f  

          if f == 'pdf':
            nb_root = qdir.parent.parent / qdir.name
            
            # 1. PRIMEIRO: gerar todos os screenshots
            print('  📸 Gerando screenshots...')
            _screenshot_html_cells(qdir, all_root, scale=2.0)
            
            # 2. SEGUNDO: verificar se as imagens existem
            print('  🔍 Verificando imagens...')
            _verify_and_fix_screenshots(qdir, all_root)
            
            # 3. TERCEIRO: aplicar o patch nos notebooks
            print('  📝 Aplicando patch nos notebooks...')
            _fix_html_outputs_for_pdf(nb_root)
            _patch_html_cells_for_pdf(qdir, all_root)
            
            # 3.5. Remover bordas brancas sobrando dos screenshots
            print('  ✂ Aplicando autocrop nos screenshots...')
            _autocrop_screenshots(all_root)
            
            # 4. QUARTO: renderizar o PDF
            print('  📄 Renderizando PDF...')
            print('  📄 Renderizando PDF...')
            env['QUARTO_FMT'] = 'pdf'
            _render_pdf_with_patched_tex(qdir, env)
            continue
            
          print(f'  $ cd {qdir.name} && quarto render --to {f}')
          try:
              r = subprocess.run(
                  ['quarto', 'render', '--to', f] +
                  (['--pdf-engine', 'lualatex'] if f == 'pdf' else []),
                  cwd=qdir,
                  capture_output=not verbose,
                  text=True,
                  timeout=3000,
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
                    _fix_spurious_closing_div(qdir, combo_name)
                    _inject_favicon_into_generated_htmls(qdir)


          except FileNotFoundError:
              print('  ⚠ quarto não encontrado no PATH')
          except subprocess.TimeoutExpired:
              print('  ⚠ Timeout ao renderizar (mais de 600 segundos)')
    finally:
        sentinela.unlink(missing_ok=True)