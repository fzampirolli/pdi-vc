#!/usr/bin/env python3
"""
Tabula tempos de `make publish-parallel` em PUBLISH_HISTORY.csv/.md
(raiz do repo) — não confundir com a tabela tbl-00-tempos do prefácio
(includes/prefacio*.qmd), que é conteúdo do livro e não é tocada aqui.

PUBLISH_HISTORY.csv é a fonte de dados (uma linha por execução); o .md é
sempre regenerado a partir dele, com uma linha de médias ao final.

Uso (chamado pelo alvo `publish-parallel` do Makefile):
    python -m pipeline.publish_history --publog-dir gen/_publog \
        --render-seconds $TR --total-seconds $TT \
        --pub-langs "$(_PUB_LANGS)" --pub-locales "$(_PUB_LOCALES)"
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime
from pathlib import Path
from typing import Optional

COMBOS = ['py.pt', 'py.en', 'py.fr', 'py.es', 'py.it',
          'cpp.pt', 'cpp.en', 'cpp.fr', 'cpp.es', 'cpp.it']

CSV_PATH = Path('PUBLISH_HISTORY.csv')
MD_PATH = Path('PUBLISH_HISTORY.md')

FIELDNAMES = ['timestamp', 'pub_langs', 'pub_locales'] + COMBOS + \
             ['render_seconds', 'total_seconds', 'note']


def _read_rc(publog_dir: Path) -> dict[str, Optional[int]]:
    """Lê gen/_publog/<combo>.rc ('<rc> <segundos>'). None = não incluído
    nesta execução; vazio = incluído mas falhou (rc != 0)."""
    times: dict[str, Optional[int]] = {}
    for combo in COMBOS:
        rc_file = publog_dir / f'{combo}.rc'
        if not rc_file.exists():
            continue
        parts = rc_file.read_text(encoding='utf-8').split()
        if len(parts) != 2:
            continue
        rc, secs = int(parts[0]), int(parts[1])
        times[combo] = secs if rc == 0 else -1  # -1 = falhou, tempo descartado da média
    return times


def _fmt_time(secs) -> str:
    if secs is None or secs == '':
        return '—'
    secs = int(secs)
    if secs < 0:
        return 'FALHA'
    m, s = divmod(secs, 60)
    return f'{m}m{s:02d}s'


def append_run(publog_dir: Path, render_seconds: int, total_seconds: int,
               pub_langs: str, pub_locales: str, note: str) -> None:
    times = _read_rc(publog_dir)
    row = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'pub_langs': pub_langs,
        'pub_locales': pub_locales,
        'render_seconds': render_seconds,
        'total_seconds': total_seconds,
        'note': note,
    }
    for combo in COMBOS:
        row[combo] = times.get(combo, '')

    is_new = not CSV_PATH.exists()
    with CSV_PATH.open('a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if is_new:
            writer.writeheader()
        writer.writerow(row)

    _regenerate_md()


def _regenerate_md() -> None:
    if not CSV_PATH.exists():
        return
    with CSV_PATH.open(encoding='utf-8') as f:
        rows = list(csv.DictReader(f))

    lines = [
        '# Histórico de tempos de publish-parallel',
        '',
        'Gerado a partir de `PUBLISH_HISTORY.csv` por '
        '`pipeline/publish_history.py`, chamado no final de '
        '`make publish-parallel`. Não é a tabela `tbl-00-tempos` do '
        'prefácio (`includes/prefacio*.qmd`) — essa é conteúdo do livro '
        'e é editada manualmente; esta aqui é só um log operacional.',
        '',
        '"—" = combo não incluído nessa execução · "FALHA" = incluído mas '
        'terminou com erro (não entra na média).',
        '',
    ]

    header = ['Data', 'Langs', 'Locales'] + COMBOS + ['Render (parede)', 'Total (c/ deploy)', 'Obs.']
    lines.append('| ' + ' | '.join(header) + ' |')
    lines.append('|' + '---|' * len(header))

    sums: dict[str, list[int]] = {c: [] for c in COMBOS}
    render_sums: list[int] = []
    total_sums: list[int] = []

    for row in rows:
        cells = [row['timestamp'], row['pub_langs'], row['pub_locales']]
        for combo in COMBOS:
            v = row.get(combo, '')
            cells.append(_fmt_time(v) if v != '' else '—')
            if v not in (None, '') and int(v) >= 0:
                sums[combo].append(int(v))
        cells.append(_fmt_time(row['render_seconds']))
        cells.append(_fmt_time(row['total_seconds']))
        cells.append(row.get('note', '') or '')
        lines.append('| ' + ' | '.join(cells) + ' |')

        if row['render_seconds']:
            render_sums.append(int(row['render_seconds']))
        if row['total_seconds']:
            total_sums.append(int(row['total_seconds']))

    if rows:
        avg_cells = [f'**Média ({len(rows)} execuções)**', '', '']
        for combo in COMBOS:
            vals = sums[combo]
            avg_cells.append(_fmt_time(round(sum(vals) / len(vals))) if vals else '—')
        avg_cells.append(_fmt_time(round(sum(render_sums) / len(render_sums))) if render_sums else '—')
        avg_cells.append(_fmt_time(round(sum(total_sums) / len(total_sums))) if total_sums else '—')
        avg_cells.append('')
        lines.append('| ' + ' | '.join(avg_cells) + ' |')

    MD_PATH.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--publog-dir', default='gen/_publog')
    ap.add_argument('--render-seconds', type=int, required=True)
    ap.add_argument('--total-seconds', type=int, required=True)
    ap.add_argument('--pub-langs', default='')
    ap.add_argument('--pub-locales', default='')
    ap.add_argument('--note', default='')
    args = ap.parse_args()

    append_run(Path(args.publog_dir), args.render_seconds, args.total_seconds,
               args.pub_langs, args.pub_locales, args.note)
    print(f'  ✓ Tempos registrados em {CSV_PATH} / {MD_PATH}')


if __name__ == '__main__':
    main()
