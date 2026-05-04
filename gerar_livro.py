#!/usr/bin/env python3
"""
gerar_livro.py — PDI+VC  (orquestrador CLI)
============================================
Copyright © 2026 Francisco de Assis Zampirolli — UFABC.

FONTES  :  all/capXX/cap01.ipynb        (Python + Português, canônico)
SAÍDAS  :  gen/<lang>.<locale>/capXX/   (gerado — não editar)

O script lê cada notebook-fonte e, para cada combo solicitado,
chama a API Anthropic para:
  • Traduzir código Python → C++ / Java / C / … (via LLM)
  • Traduzir texto Português → English / Français / … (via LLM)

As traduções são armazenadas em cache (.cache/translations.json) e
reutilizadas nas execuções seguintes — a API só é chamada para
conteúdo novo ou modificado.

Uso rápido
──────────
  # Todas as combinações ativas (py+cpp × pt+en)
  python gerar_livro.py --langs py,cpp --locales pt,en

  # Só Python × todos os idiomas ativos
  python gerar_livro.py --langs py --locales pt,en,fr

  # Dry-run: gera notebooks sem chamar a API (placeholders)
  python gerar_livro.py --langs py,cpp --locales pt,en --dry-run

  # Gerar + renderizar HTML
  python gerar_livro.py --langs py,cpp --locales pt,en --render html

  # Capítulo específico
  python gerar_livro.py --langs cpp --locales en all/cap01/cap01.ipynb

Adicionar nova linguagem / idioma
──────────────────────────────────
  Edite pipeline/config.py (LANGUAGES / LOCALES / UI_STRINGS).
  Nenhuma alteração necessária neste arquivo.
"""

import argparse
import sys
from pathlib import Path

# Garantir que o pacote pipeline seja encontrado
sys.path.insert(0, str(Path(__file__).parent))

from pipeline.config   import (LANGUAGES, LOCALES, BASE_LANG, BASE_LOCALE,
                                Combo, all_combos, parse_combo)
from pipeline.cache    import TranslationCache
from pipeline.bib      import parse_bib
from pipeline.translators      import TranslatorFactory
from pipeline.notebook_processor import NotebookProcessor
from pipeline.quarto_builder   import QuartoBuilder, render_quarto
from pipeline.index_builder import IndexBuilder

import nbformat

DIR_ALL = Path('all')
DIR_GEN = Path('gen')
BIB_DEFAULT = 'references.bib'


# ─────────────────────────────────────────────────────────────────────────────
# Descoberta de notebooks-fonte
# ─────────────────────────────────────────────────────────────────────────────

def find_sources(paths: list[str] | None = None) -> list[Path]:
    if paths:
        found = [Path(p) for p in paths if Path(p).exists()]
    else:
        found = sorted(DIR_ALL.glob('cap*/cap*.ipynb'))
    # Excluir notebooks já gerados (com padrão cap01.py.pt.ipynb)
    return [p for p in found if not any(
        p.stem.endswith(f'.{l}.{lo}')
        for l in LANGUAGES for lo in LOCALES
    )]


# ─────────────────────────────────────────────────────────────────────────────
# Geração de um notebook para um combo
# ─────────────────────────────────────────────────────────────────────────────

def generate_notebook(nb_path: Path, combo: Combo,
                      processor: NotebookProcessor) -> Path:
    """
    Processa nb_path para combo e salva em:
      gen/<combo.key>/<cap>/<stem>.<combo.key>.ipynb
    """
    cap_dir  = nb_path.parent.name              # cap01
    stem     = nb_path.stem                     # cap01  (ou cap01.ex)
    out_name = f'{stem}.{combo.key}.ipynb'

    out_dir = DIR_GEN / combo.key / cap_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / out_name

    nb_out = processor.process(str(nb_path), combo)
    with open(out_path, 'w', encoding='utf-8') as f:
        nbformat.write(nb_out, f)

    return out_path


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog='gerar_livro.py',
        description='Gera versões do livro PDI+VC por linguagem e idioma via LLM.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        'sources', nargs='*',
        help='Notebooks-fonte específicos (padrão: todos em all/cap*/*.ipynb)')
    parser.add_argument(
        '--langs', default='py',
        help='Linguagens separadas por vírgula (padrão: py). '
             f'Disponíveis: {",".join(LANGUAGES)}')
    parser.add_argument(
        '--locales', default='pt',
        help='Idiomas separados por vírgula (padrão: pt). '
             f'Disponíveis: {",".join(LOCALES)}')
    parser.add_argument(
        '--bib', default=BIB_DEFAULT,
        help=f'Arquivo .bib (padrão: {BIB_DEFAULT})')
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Gerar notebooks com placeholders, sem chamar a API')
    parser.add_argument(
        '--render', choices=['html', 'pdf', 'all'],
        help='Renderizar Quarto após gerar (html | pdf | all)')
    parser.add_argument(
        '--no-quarto', action='store_true',
        help='Não gerar pasta Quarto (apenas notebooks)')
    parser.add_argument(
        '--cache', default='.cache/translations.json',
        help='Arquivo de cache de traduções (padrão: .cache/translations.json)')
    parser.add_argument(
        '--verbose', action='store_true',
        help='Mostrar saída completa do quarto render')
    args = parser.parse_args()

    # ── Validar langs e locales ───────────────────────────────────────────────
    langs   = [l.strip() for l in args.langs.split(',')]
    locales = [lo.strip() for lo in args.locales.split(',')]

    for l in langs:
        if l not in LANGUAGES:
            parser.error(f"Linguagem desconhecida: '{l}'. Disponíveis: {list(LANGUAGES)}")
    for lo in locales:
        if lo not in LOCALES:
            parser.error(f"Idioma desconhecido: '{lo}'. Disponíveis: {list(LOCALES)}")

    combos = [Combo(l, lo) for l in langs for lo in locales]

    # ── Carregar BibTeX ───────────────────────────────────────────────────────
    bib = parse_bib(args.bib)
    print(f'✓ BibTeX: {len(bib)} entradas')

    # ── Cache ─────────────────────────────────────────────────────────────────
    cache = TranslationCache(Path(args.cache))
    print(f'✓ Cache : {cache.stats()["entries"]} entradas ({args.cache})')

    # ── Factory + Processor ───────────────────────────────────────────────────
    factory   = TranslatorFactory(cache, dry_run=args.dry_run)
    processor = NotebookProcessor(factory, bib)

    # ── Notebooks-fonte ───────────────────────────────────────────────────────
    sources = find_sources(args.sources or None)
    if not sources:
        sys.exit(f'Nenhum notebook encontrado em {DIR_ALL}/')

    mode = '(dry-run)' if args.dry_run else '(via API Anthropic)'
    print(f'\n📚 Fontes   : {len(sources)} notebooks')
    print(f'🔀 Combos   : {[c.key for c in combos]}')
    print(f'⚙  Modo     : {mode}\n')

    # ── Geração ───────────────────────────────────────────────────────────────
    total = 0
    quarto_builder = QuartoBuilder()
    quarto_dirs: dict[str, Path] = {}

    for combo in combos:
        print(f'── {combo.key} {"(base — sem chamadas API)" if combo.is_base() else ""} ───')
        generated: list[Path] = []

        for nb_path in sources:
            out = generate_notebook(nb_path, combo, processor)
            print(f'  ✓ {out}')
            generated.append(out)
            total += 1

        if not args.no_quarto:
            qdir = quarto_builder.build(combo)
            quarto_dirs[combo.key] = qdir

        if args.render and combo.key in quarto_dirs:
            render_quarto(quarto_dirs[combo.key], args.render,
                          verbose=args.verbose)
        print()

    # ── Salvar cache ──────────────────────────────────────────────────────────
    cache.save()

    # ── Resumo ────────────────────────────────────────────────────────────────
    print(f'✅ {total} notebooks gerados em gen/')
    if quarto_dirs:
        print('\nPara renderizar manualmente:')
        for key, qdir in quarto_dirs.items():
            print(f'  cd {qdir} && quarto render --to html')
            print(f'  cd {qdir} && quarto render --to pdf')


    if args.render:  # ou sempre gerar
        index_builder = IndexBuilder()
        index_builder.build()
        print(f'\n🌐 Página principal: file://{index_builder.index_path.absolute()}')



if __name__ == '__main__':
    main()


