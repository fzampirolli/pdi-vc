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

  # Promover edições manuais feitas em gen/*.ipynb pro cache de tradução
  # (ver README § Editando o conteúdo gerado) — não gera nem builda nada
  python dev.py --promote-edits --langs cpp --locales en

  # Auditar o cache: aponta entradas cuja fonte não existe mais (correções
  # manuais órfãs viram aviso alto). --prune-cache remove as LLM órfãs.
  python dev.py --audit-cache [--prune-cache]

Atalhos de teclado durante o watch:
  r  → rebuild tudo agora
  q  → sair
"""

import argparse
import os
import re
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


def _gen_notebook_path(nb_path: Path, combo: Combo) -> Path:
    cap_dir  = nb_path.parent.name
    stem     = nb_path.stem
    out_name = f'{stem}.{combo.key}.ipynb'
    return DIR_GEN / combo.key / cap_dir / out_name


def build_notebook(nb_path: Path, combo: Combo,
                   processor: NotebookProcessor) -> Path:
    out_path = _gen_notebook_path(nb_path, combo)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    nb_out = processor.process(str(nb_path), combo)
    with open(out_path, 'w', encoding='utf-8') as f:
        nbformat.write(nb_out, f)

    return out_path


# ─────────────────────────────────────────────────────────────────────────────
# Promoção de edições manuais (gen/*.ipynb → cache)
# ─────────────────────────────────────────────────────────────────────────────

_WRITEFILE_HEAD_RE = re.compile(r'^%%writefile\s+\S+\n')


def _cell_text(cell) -> str:
    src = cell.get('source', '')
    return ''.join(src) if isinstance(src, list) else src


def promote_edits(sources: list[Path], combos: list[Combo],
                  processor: NotebookProcessor, cache: TranslationCache) -> None:
    """
    Cada célula traduzida por LLM carrega em metadata.pdi.ck a chave de
    cache que a gerou (ver notebook_processor.py::_tag_cache_key). Se o
    professor editar essa célula direto no notebook gerado (gen/<combo>/)
    e salvar, o conteúdo em disco passa a diferir do que o pipeline geraria
    — esta função detecta a diferença e grava a edição na mesma chave, pra
    que o próximo build reproduza a correção sem chamar o LLM de novo.

    Comparar direto contra `cache.get_raw(ck)` não funciona pra células de
    TEXTO: em combos não-base, `NotebookProcessor.process()` roda
    `postprocess_markdown()` (citações, figuras, cross-refs) DEPOIS de
    pegar o valor do cache, então o texto em disco nunca é igual ao valor
    cru cacheado, mesmo sem edição nenhuma — isso gerava falso-positivo em
    toda célula de texto. Por isso a comparação é contra uma regeneração
    de referência via `processor.process()` (mesmo caminho de um build
    normal, sem custo de API — todo cache hit), não contra o cache cru.
    Só entra em cache o texto de fato editado, já no formato final
    (pós-processado) — e por `postprocess_markdown` consumir os padrões
    que dispara (`@key`, `:::{#fig-...}:::`, `\\printbibliography`),
    reaplicá-lo em cima de um texto já processado é inofensivo, então essa
    é uma chave de cache válida pro próximo build.

    Não gera nem builda nada; só promove o que já está em disco.
    """
    promoted = 0
    for combo in combos:
        for nb_path in sources:
            gen_path = _gen_notebook_path(nb_path, combo)
            if not gen_path.exists():
                continue
            with open(gen_path, encoding='utf-8') as f:
                disk_nb = nbformat.read(f, as_version=4)
            ref_nb = processor.process(str(nb_path), combo)

            if len(disk_nb.cells) != len(ref_nb.cells):
                print(f'  ⚠ {gen_path}: número de células mudou desde a última '
                      f'geração (fonte em all/ foi editada?) — rode o build '
                      f'normal de novo antes de promover.')
                continue

            for i, (disk_cell, ref_cell) in enumerate(zip(disk_nb.cells, ref_nb.cells)):
                ck = ref_cell.get('metadata', {}).get('pdi', {}).get('ck')
                if not ck:
                    continue
                disk_src = _cell_text(disk_cell)
                if disk_src == _cell_text(ref_cell):
                    continue  # nada editado nesta célula

                # Célula %%writefile (expansão pra linguagem estrangeira):
                # o valor cacheado é só o corpo do arquivo, sem esse header.
                m = _WRITEFILE_HEAD_RE.match(disk_src)
                editable = disk_src[m.end():] if m else disk_src
                meta = {
                    'kind': 'manual',
                    'combo': combo.key,
                    'chapter': nb_path.parent.name,
                    'cell': i,
                    'preview': ' '.join(editable.split())[:160],
                }
                if cache.set_raw(ck, editable, meta=meta):
                    if promoted == 0:
                        bak = cache.backup()
                        if bak:
                            print(f'  💾 backup do cache anterior em {bak}')
                    promoted += 1
                    print(f'  ✏ promovido: {gen_path.relative_to(DIR_GEN)} célula {i}')
    cache.save()
    if promoted:
        print(f'\n✅ {promoted} célula(s) promovida(s) pro cache. '
              f'Rode o build normal de novo pra conferir.')
    else:
        print('\nNenhuma edição nova encontrada (nada promovido).')


def audit_cache(sources: list[Path], combos: list[Combo],
                processor: NotebookProcessor, cache: TranslationCache,
                prune: bool = False) -> None:
    """
    Confronta as chaves de `.cache/translations.json` com as chaves que o
    conjunto atual de fontes (all/) × combos realmente produz. Uma chave é
    endereçada por conteúdo (hash da célula-fonte); se a fonte mudar, a
    chave antiga vira órfã e nunca mais é consultada — o build re-traduz o
    texto novo via LLM sem avisar que havia uma tradução (ou uma correção
    manual) para o texto anterior.

    - Correções MANUAIS órfãs → aviso alto: dizem qual combo/capítulo/célula
      e o trecho da correção que será perdido.
    - Traduções LLM órfãs → só contagem; com `prune=True`, remove (após
      backup automático).

    Não chama a API: as chaves saem de `processor.process()` (que aqui roda
    todo em cache hit, ou dry-run) e independem da tradução real.
    """
    live: set[str] = set()
    for combo in combos:
        for nb_path in sources:
            try:
                ref_nb = processor.process(str(nb_path), combo)
            except Exception as e:  # noqa: BLE001 — combo/capítulo problemático não deve abortar o audit
                print(f'  ⚠ pulei {nb_path.parent.name}/{combo.key}: {e}')
                continue
            for cell in ref_nb.cells:
                ck = cell.get('metadata', {}).get('pdi', {}).get('ck')
                if ck:
                    live.add(ck)

    all_keys = cache.keys()
    orphans = all_keys - live
    manual_orphans = sorted(k for k in orphans if cache.is_manual(k))
    llm_orphans = sorted(orphans - set(manual_orphans))

    st = cache.stats()
    print(f'\n📊 cache: {st["entries"]} entradas ({st["manual"]} manuais), '
          f'{len(live)} vivas em {[c.key for c in combos]}.')

    if manual_orphans:
        print(f'\n⚠ {len(manual_orphans)} correção(ões) MANUAL(is) órfã(s) — a '
              f'fonte mudou; a correção NÃO será aplicada no próximo build:')
        for k in manual_orphans:
            m = cache.meta_for(k) or {}
            print(f'  • {m.get("combo","?")}/{m.get("chapter","?")} '
                  f'célula {m.get("cell","?")} (promovida {m.get("promoted_at","?")})')
            if m.get('preview'):
                print(f'      correção: "{m["preview"]}"')
            print(f'      → reveja gen/{m.get("combo","?")}/{m.get("chapter","?")}/*.ipynb, '
                  f'reaplique a correção e rode --promote-edits de novo')
    else:
        print('\n✅ nenhuma correção manual órfã.')

    if llm_orphans:
        print(f'\nℹ {len(llm_orphans)} tradução(ões) LLM órfã(s) '
              f'(fonte antiga, sem correção manual).')
        if prune:
            bak = cache.backup()
            if bak:
                print(f'  💾 backup em {bak}')
            n = cache.drop(llm_orphans)
            cache.save()
            print(f'  🧹 {n} entrada(s) removida(s).')
        else:
            print('  Rode com --prune-cache pra removê-las (backup automático).')
    else:
        print('\n✅ nenhuma tradução LLM órfã.')


def run_build(sources: list[Path], combos: list[Combo],
              processor: NotebookProcessor, quarto_builder: QuartoBuilder,
              render_fmt: str | None, verbose: bool) -> dict[str, Path]:
    """Executa build completo; retorna {combo.key: quarto_dir}."""
    quarto_dirs: dict[str, Path] = {}

    for combo in combos:
        tag = '(base)' if combo.is_base() else ''
        print(f'\n── {combo.key} {tag}')
        # A trilha C++ só foi portada/validada para o cap01 (7 funções de
        # morph.py). Os demais capítulos usam cv2/skimage sem equivalente e,
        # com error:false, uma célula quebrada aborta o render do combo cpp
        # inteiro — inclusive o cap01. Ver CPP_VALIDATION_NOTE no índice.
        combo_sources = sources
        if combo.lang == 'cpp':
            combo_sources = [s for s in sources if s.parent.name == 'cap01']
        for nb_path in combo_sources:
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
    parser.add_argument('--promote-edits', action='store_true',
                        help='Grava no cache as edições manuais feitas em gen/*.ipynb '
                             '(não gera nem builda nada — ver README § Editando o conteúdo gerado)')
    parser.add_argument('--audit-cache', action='store_true',
                        help='Aponta entradas do cache que a fonte atual não produz mais '
                             '(correções manuais órfãs viram aviso alto). Não chama a API.')
    parser.add_argument('--prune-cache', action='store_true',
                        help='Com --audit-cache: remove as traduções LLM órfãs (backup automático). '
                             'Nunca remove correção manual.')
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

    # O audit varre o cache inteiro — precisa do conjunto COMPLETO de combos
    # e de todas as fontes, senão entradas legítimas (outros combos) parecem
    # órfãs. Ignora --langs/--locales/sources e nunca deixa podar num recorte.
    if args.audit_cache:
        combos = [Combo(l, lo) for l in LANGUAGES for lo in LOCALES]
        if args.sources:
            parser.error('--audit-cache varre tudo; não passe arquivos específicos.')
    else:
        combos = [Combo(l, lo) for l in langs for lo in locales]

    # ── Inicializar dependências ───────────────────────────────────────────────
    bib       = parse_bib(args.bib)
    cache     = TranslationCache(Path(args.cache))
    # Audit não deve gastar API: as chaves independem da tradução real.
    factory   = TranslatorFactory(cache, dry_run=args.dry_run or args.audit_cache)
    processor = NotebookProcessor(factory, bib)
    builder   = QuartoBuilder()

    sources = find_sources(args.sources or None)
    if not sources:
        sys.exit(f'Nenhum notebook encontrado em {DIR_ALL}/')

    if args.audit_cache:
        audit_cache(sources, combos, processor, cache, prune=args.prune_cache)
        return

    if args.promote_edits:
        promote_edits(sources, combos, processor, cache)
        return

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
