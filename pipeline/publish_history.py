#!/usr/bin/env python3
"""
Tabula tempos de `make publish-parallel` em PUBLISH_HISTORY.csv/.md
(raiz do repo) — não confundir com a tabela tbl-00-tempos do prefácio
(includes/prefacio*.qmd), que é conteúdo do livro e não é tocada aqui.

PUBLISH_HISTORY.csv é a fonte de dados (uma linha por execução); o .md é
sempre regenerado a partir dele, com uma linha de médias ao final.

Também calcula o grau de paralelismo real de cada execução (médio e
pico), a partir dos timestamps de início/fim de cada combo gravados em
gen/_publog/<combo>.rc ("<rc> <segundos> <início_epoch> <fim_epoch>") —
um sweep-line sobre os intervalos [início, fim] de cada combo que rodou
com sucesso. Arquivos .rc antigos (só "<rc> <segundos>", de antes dessa
mudança) não entram no cálculo de paralelismo, só no de duração.

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
from typing import NamedTuple, Optional

COMBOS = ['py.pt', 'py.en', 'py.fr', 'py.es', 'py.it',
          'cpp.pt', 'cpp.en', 'cpp.fr', 'cpp.es', 'cpp.it']

CSV_PATH = Path('PUBLISH_HISTORY.csv')
MD_PATH = Path('PUBLISH_HISTORY.md')

EXTRA_FIELDS = ['render_seconds', 'total_seconds', 'avg_parallelism', 'peak_parallelism', 'note']
FIELDNAMES = ['timestamp', 'pub_langs', 'pub_locales'] + COMBOS + EXTRA_FIELDS


class ComboResult(NamedTuple):
    seconds: int              # -1 = falhou
    start: Optional[int]      # epoch; None se .rc no formato antigo (sem timestamps)
    end: Optional[int]


def _read_rc(publog_dir: Path) -> dict[str, ComboResult]:
    """Lê gen/_publog/<combo>.rc. Formato novo: '<rc> <segundos> <início> <fim>'
    (epoch). Formato antigo (antes desta mudança): só '<rc> <segundos>' —
    ainda lido, mas sem dados pra paralelismo."""
    results: dict[str, ComboResult] = {}
    for combo in COMBOS:
        rc_file = publog_dir / f'{combo}.rc'
        if not rc_file.exists():
            continue
        parts = rc_file.read_text(encoding='utf-8').split()
        if len(parts) not in (2, 4):
            continue
        rc, secs = int(parts[0]), int(parts[1])
        secs = secs if rc == 0 else -1  # -1 = falhou, tempo descartado da média
        start = end = None
        if len(parts) == 4 and rc == 0:
            start, end = int(parts[2]), int(parts[3])
        results[combo] = ComboResult(secs, start, end)
    return results


def _parallelism(results: dict[str, ComboResult]) -> tuple[Optional[float], Optional[int]]:
    """Sweep-line sobre os intervalos [start, end] dos combos com timestamps
    válidos. Retorna (grau médio ponderado no tempo, grau de pico), ou
    (None, None) se não houver dados suficientes (ex.: .rc no formato antigo,
    ou só 1 combo sem sobreposição a medir)."""
    intervals = [(r.start, r.end) for r in results.values()
                 if r.start is not None and r.end is not None and r.end > r.start]
    if not intervals:
        return None, None

    events: list[tuple[int, int]] = []
    for s, e in intervals:
        events.append((s, 1))
        events.append((e, -1))
    events.sort()

    cur = 0
    peak = 0
    weighted = 0
    prev_t = events[0][0]
    for t, delta in events:
        if cur > 0:
            weighted += cur * (t - prev_t)
        cur += delta
        peak = max(peak, cur)
        prev_t = t

    span = events[-1][0] - events[0][0]
    avg = weighted / span if span > 0 else float(peak)
    return avg, peak


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
    results = _read_rc(publog_dir)
    avg_par, peak_par = _parallelism(results)

    row = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'pub_langs': pub_langs,
        'pub_locales': pub_locales,
        'render_seconds': render_seconds,
        'total_seconds': total_seconds,
        'avg_parallelism': f'{avg_par:.2f}' if avg_par is not None else '',
        'peak_parallelism': peak_par if peak_par is not None else '',
        'note': note,
    }
    for combo in COMBOS:
        r = results.get(combo)
        row[combo] = r.seconds if r is not None else ''

    # Lê linhas antigas (se existirem, mesmo com um header de esquema mais
    # velho — ex.: sem avg_parallelism/peak_parallelism) e reescreve o CSV
    # inteiro com o header atual, preenchendo campos novos ausentes com ''
    # nas linhas antigas. Evita desalinhar colunas quando o schema cresce.
    old_rows: list[dict] = []
    if CSV_PATH.exists():
        with CSV_PATH.open(encoding='utf-8') as f:
            old_rows = list(csv.DictReader(f))

    with CSV_PATH.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for old_row in old_rows:
            writer.writerow({k: old_row.get(k, '') for k in FIELDNAMES})
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
        '"—" = combo não incluído nessa execução (ou paralelismo não '
        'calculável para execuções antigas, sem timestamps no `.rc`) · '
        '"FALHA" = incluído mas terminou com erro (não entra na média).',
        '',
        '**Paralelismo médio/pico**: grau real de execução simultânea de '
        'combos durante o render, calculado a partir dos timestamps de '
        'início/fim de cada combo (sweep-line) — médio é ponderado no '
        'tempo, pico é o máximo de combos rodando ao mesmo tempo em '
        'algum instante.',
        '',
    ]

    header = (['Data', 'Langs', 'Locales'] + COMBOS +
              ['Render (parede)', 'Total (c/ deploy)', 'Paralel. médio', 'Paralel. pico', 'Obs.'])
    lines.append('| ' + ' | '.join(header) + ' |')
    lines.append('|' + '---|' * len(header))

    sums: dict[str, list[int]] = {c: [] for c in COMBOS}
    render_sums: list[int] = []
    total_sums: list[int] = []
    avg_par_sums: list[float] = []
    peak_par_sums: list[int] = []

    for row in rows:
        cells = [row['timestamp'], row['pub_langs'], row['pub_locales']]
        for combo in COMBOS:
            v = row.get(combo, '')
            cells.append(_fmt_time(v) if v != '' else '—')
            if v not in (None, '') and int(v) >= 0:
                sums[combo].append(int(v))
        cells.append(_fmt_time(row['render_seconds']))
        cells.append(_fmt_time(row['total_seconds']))

        avg_par_raw = row.get('avg_parallelism', '')
        peak_par_raw = row.get('peak_parallelism', '')
        cells.append(f'{float(avg_par_raw):.2f}x' if avg_par_raw else '—')
        cells.append(f'{peak_par_raw}x' if peak_par_raw else '—')
        cells.append(row.get('note', '') or '')
        lines.append('| ' + ' | '.join(cells) + ' |')

        if row['render_seconds']:
            render_sums.append(int(row['render_seconds']))
        if row['total_seconds']:
            total_sums.append(int(row['total_seconds']))
        if avg_par_raw:
            avg_par_sums.append(float(avg_par_raw))
        if peak_par_raw:
            peak_par_sums.append(int(peak_par_raw))

    if rows:
        avg_cells = [f'**Média ({len(rows)} execuções)**', '', '']
        for combo in COMBOS:
            vals = sums[combo]
            avg_cells.append(_fmt_time(round(sum(vals) / len(vals))) if vals else '—')
        avg_cells.append(_fmt_time(round(sum(render_sums) / len(render_sums))) if render_sums else '—')
        avg_cells.append(_fmt_time(round(sum(total_sums) / len(total_sums))) if total_sums else '—')
        avg_cells.append(f'{sum(avg_par_sums) / len(avg_par_sums):.2f}x' if avg_par_sums else '—')
        avg_cells.append(f'{sum(peak_par_sums) / len(peak_par_sums):.1f}x' if peak_par_sums else '—')
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
