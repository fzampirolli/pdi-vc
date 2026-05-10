#!/usr/bin/env python3
"""
dev.py — Loop de desenvolvimento PDI+VC
========================================
Uso:

  # Modo watch: detecta mudanças em all/ e regenera + renderiza
  python dev.py

  # Especificar combo e formato de saída
  python dev.py --langs cpp --locales en --render html

  # Build único (sem watch)
  python dev.py --once

  # Build único, capítulo específico
  python dev.py --once all/cap01/cap01.ipynb

  # Dry-run (sem API — placeholders)
  python dev.py --dry-run

Atalhos de teclado durante o watch:
  r  → rebuild tudo agora
  q  → sair
"""

import argparse
import os
import sys
import time
import hashlib
import threading
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from pipeline.config import LANGUAGES, LOCALES, Combo
from pipeline.cache import TranslationCache
from pipeline.bib import parse_bib
from pipeline.translators import TranslatorFactory
from pipeline.notebook_processor import NotebookProcessor
from pipeline.quarto_builder import QuartoBuilder, render_quarto
import nbformat

DIR_ALL = Path('all')
DIR_GEN = Path('gen')
BIB_DEFAULT = 'references.bib'


# ─────────────────────────────────────────────────────────────────────────────
# Fingerprint de arquivo (detecta mudanças)
# ─────────────────────────────────────────────────────────────────────────────

def _file_hash(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


class FileWatcher:
    """Rastreia hashes de arquivos e informa quais mudaram."""

    def __init__(self):
        self._hashes: dict[Path, str] = {}

    def snapshot(self, paths: list[Path]):
        """Atualiza snapshot sem reportar mudanças."""
        for p in paths:
            if p.exists():
                self._hashes[p] = _file_hash(p)

    def changed(self, paths: list[Path]) -> list[Path]:
        """Retorna arquivos que mudaram desde o último snapshot."""
        dirty = []
        for p in paths:
            if not p.exists():
                continue
            h = _file_hash(p)
            if self._hashes.get(p) != h:
                dirty.append(p)
                self._hashes[p] = h
        return dirty


# ─────────────────────────────────────────────────────────────────────────────
# Núcleo de build
# ─────────────────────────────────────────────────────────────────────────────

def find_sources(paths: list[str] | None = None) -> list[Path]:
    if paths:
        return [Path(p) for p in paths if Path(p).exists()]
    return sorted(DIR_ALL.glob('cap*/cap*.ipynb'))


def build_notebook(nb_path: Path, combo: Combo,
                   processor: NotebookProcessor) -> Path:
    cap_dir  = nb_path.parent.name
    stem     = nb_path.stem
    out_name = f'{stem}.{combo.key}.ipynb'
    out_dir  = DIR_GEN / combo.key / cap_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / out_name

    nb_out = processor.process(str(nb_path), combo)
    with open(out_path, 'w', encoding='utf-8') as f:
        nbformat.write(nb_out, f)

    return out_path


def run_build(sources: list[Path], combos: list[Combo],
              processor: NotebookProcessor, quarto_builder: QuartoBuilder,
              render_fmt: str | None, verbose: bool) -> dict[str, Path]:
    """Executa build completo; retorna {combo.key: quarto_dir}."""
    quarto_dirs: dict[str, Path] = {}

    for combo in combos:
        tag = '(base)' if combo.is_base() else ''
        print(f'\n── {combo.key} {tag}')
        for nb_path in sources:
            out = build_notebook(nb_path, combo, processor)
            print(f'  ✓ {out}')

        qdir = quarto_builder.build(combo)
        quarto_dirs[combo.key] = qdir

        if render_fmt:
            render_quarto(qdir, render_fmt, all_root=DIR_ALL, verbose=verbose)

    return quarto_dirs


def run_incremental(dirty: list[Path], combos: list[Combo],
                    processor: NotebookProcessor, quarto_builder: QuartoBuilder,
                    render_fmt: str | None, verbose: bool,
                    quarto_dirs: dict[str, Path]):
    """Rebuilda apenas os notebooks alterados e re-renderiza."""
    print(f'\n[{_ts()}] Mudança detectada:')
    for p in dirty:
        print(f'  • {p}')

    for combo in combos:
        for nb_path in dirty:
            out = build_notebook(nb_path, combo, processor)
            print(f'  ✓ {out}')

        if render_fmt and combo.key in quarto_dirs:
            render_quarto(quarto_dirs[combo.key], render_fmt, all_root=DIR_ALL, verbose=verbose)

    print(f'[{_ts()}] Pronto. Aguardando mudanças…')


def _ts() -> str:
    return time.strftime('%H:%M:%S')


# ─────────────────────────────────────────────────────────────────────────────
# Entrada de teclado não-bloqueante (Unix)
# ─────────────────────────────────────────────────────────────────────────────

def _kb_listener(cmd_queue):
    """Thread que lê teclas sem bloquear o loop principal."""
    try:
        import tty, termios
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            while True:
                ch = sys.stdin.read(1)
                cmd_queue.append(ch.lower())
                if ch.lower() == 'q':
                    break
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
    except Exception:
        # Windows ou ambiente sem tty — ignora
        pass


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog='dev.py',
        description='Watch + build para o livro PDI+VC.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument('sources', nargs='*',
                        help='Notebooks específicos (padrão: all/cap*/*.ipynb)')
    parser.add_argument('--langs', default='py',
                        help=f'Linguagens (padrão: py). Disponíveis: {",".join(LANGUAGES)}')
    parser.add_argument('--locales', default='pt',
                        help=f'Idiomas (padrão: pt). Disponíveis: {",".join(LOCALES)}')
    parser.add_argument('--render', choices=['html', 'pdf', 'all'], default=None,
                        help='Renderizar Quarto após build (padrão: apenas gera notebooks)')
    parser.add_argument('--once', action='store_true',
                        help='Build único, sem entrar no loop de watch')
    parser.add_argument('--dry-run', action='store_true',
                        help='Sem chamadas à API — usa placeholders')
    parser.add_argument('--interval', type=float, default=2.0,
                        help='Intervalo de polling em segundos (padrão: 2)')
    parser.add_argument('--bib', default=BIB_DEFAULT)
    parser.add_argument('--cache', default='.cache/translations.json')
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args()

    # ── Validar ───────────────────────────────────────────────────────────────
    langs   = [l.strip() for l in args.langs.split(',')]
    locales = [lo.strip() for lo in args.locales.split(',')]
    for l in langs:
        if l not in LANGUAGES:
            parser.error(f"Linguagem desconhecida: '{l}'. Disponíveis: {list(LANGUAGES)}")
    for lo in locales:
        if lo not in LOCALES:
            parser.error(f"Idioma desconhecido: '{lo}'. Disponíveis: {list(LOCALES)}")

    combos = [Combo(l, lo) for l in langs for lo in locales]

    # ── Inicializar dependências ───────────────────────────────────────────────
    bib       = parse_bib(args.bib)
    cache     = TranslationCache(Path(args.cache))
    factory   = TranslatorFactory(cache, dry_run=args.dry_run)
    processor = NotebookProcessor(factory, bib)
    builder   = QuartoBuilder()

    sources = find_sources(args.sources or None)
    if not sources:
        sys.exit(f'Nenhum notebook encontrado em {DIR_ALL}/')

    mode = '(dry-run)' if args.dry_run else '(API Anthropic)'
    print(f'📚 Fontes : {len(sources)} notebooks')
    print(f'🔀 Combos : {[c.key for c in combos]}')
    print(f'⚙  Modo   : {mode}')
    if args.render:
        print(f'🖨  Render : {args.render}')

    # ── Build inicial ─────────────────────────────────────────────────────────
    quarto_dirs = run_build(sources, combos, processor, builder,
                            args.render, args.verbose)
    cache.save()

    if args.once:
        print(f'\n✅ Build concluído.')
        _print_open_hints(quarto_dirs, args.render)
        return

    # ── Loop de watch ─────────────────────────────────────────────────────────
    watcher = FileWatcher()
    watcher.snapshot(sources)

    print(f'\n👀 Watching all/ a cada {args.interval}s — [r] rebuild  [q] sair\n')

    cmd_queue: list[str] = []
    kb_thread = threading.Thread(target=_kb_listener, args=(cmd_queue,),
                                 daemon=True)
    kb_thread.start()

    try:
        while True:
            time.sleep(args.interval)

            # Teclas
            while cmd_queue:
                ch = cmd_queue.pop(0)
                if ch == 'q':
                    print('\nSaindo.')
                    cache.save()
                    return
                elif ch == 'r':
                    print(f'[{_ts()}] Rebuild forçado…')
                    run_build(sources, combos, processor, builder,
                              args.render, args.verbose)
                    cache.save()
                    watcher.snapshot(sources)

            # Mudanças em disco
            dirty = watcher.changed(sources)
            if dirty:
                run_incremental(dirty, combos, processor, builder,
                                args.render, args.verbose, quarto_dirs)
                cache.save()

    except KeyboardInterrupt:
        print('\nInterrompido.')
        cache.save()


def _print_open_hints(quarto_dirs: dict[str, Path], render_fmt: str | None):
    if not render_fmt or not quarto_dirs:
        return
    print('\nAbrir resultado:')
    for key, qdir in quarto_dirs.items():
        book_dir = Path('gen') / 'book' / key
        if render_fmt in ('html', 'all') and (book_dir / 'index.html').exists():
            print(f'  open {book_dir}/index.html')
        if render_fmt in ('pdf', 'all'):
            pdfs = list(book_dir.glob('*.pdf'))
            for pdf in pdfs:
                print(f'  open {pdf}')


if __name__ == '__main__':
    main()
