#!/usr/bin/env python3
"""
Atualiza os números de Páginas/Tempo de renderização da tabela
`tbl-00-tempos` em `includes/prefacio*.qmd` (5 idiomas) a partir da
última linha de `PUBLISH_HISTORY.csv` (tempos reais de um
`make publish-parallel` completo) e da contagem de páginas dos PDFs
publicados em `docs/<combo>/livro.<locale>.<lang>.pdf`.

Também remove o rodapé "¹ Primeira geração do idioma..." e o
superíndice "¹" nas linhas de `py.es`/`py.it` — essa ressalva só valia
enquanto o cache de tradução desses locales estava vazio, o que não é
mais o caso.

Rodar isto IMEDIATAMENTE depois de um `make publish-parallel` com todos
os 10 combos (senão a última linha do CSV não cobre todos eles).

**Decisão do usuário (2026-09-20): 1 rodada só, tabela sempre defasada.**
Como a tabela é conteúdo do livro, ela só aparece no HTML/PDF publicado
na PRÓXIMA vez que o livro for renderizado — não há como uma publicação
"assar" no próprio HTML/PDF dela o tempo que ela mesma levou. Rodar
`make publish-parallel` de novo só pra isso (2 rodadas completas) foi
tentado uma vez e descartado por ser caro demais pro ganho. Fluxo
adotado: publish → roda este script → commita. A tabela fica sempre
com os números da publicação ANTERIOR (defasagem de uma rodada, avisada
implicitamente pela ordem de grandeza — não é um problema prático).

Uso:
    python -m pipeline.update_prefacio_tempos
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

from pypdf import PdfReader

from pipeline.publish_history import COMBOS, CSV_PATH

PREFACIO_FILES = {
    'pt': Path('includes/prefacio.qmd'),
    'en': Path('includes/prefacio_en.qmd'),
    'fr': Path('includes/prefacio_fr.qmd'),
    'es': Path('includes/prefacio_es.qmd'),
    'it': Path('includes/prefacio_it.qmd'),
}


def _last_row() -> dict:
    with CSV_PATH.open(encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise SystemExit(f'{CSV_PATH} vazio — rode make publish-parallel primeiro.')
    return rows[-1]


def _page_count(combo: str) -> int | None:
    lang, locale = combo.split('.')
    pdf = Path('docs') / combo / f'livro.{locale}.{lang}.pdf'
    if not pdf.exists():
        print(f'  ! {pdf} não encontrado, mantendo página antiga de {combo}')
        return None
    return len(PdfReader(str(pdf)).pages)


def _fmt_minutes(seconds) -> str | None:
    if seconds in (None, '', 'FALHA'):
        return None
    n = int(seconds)
    if n < 0:
        return None
    minutes = max(1, round(n / 60))
    return f'~{minutes} min'


_ROW_RE_CACHE: dict[str, re.Pattern] = {}


def _row_re(combo: str) -> re.Pattern:
    if combo not in _ROW_RE_CACHE:
        _ROW_RE_CACHE[combo] = re.compile(
            r'^\|\s*`' + re.escape(combo) + r'`\s*\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|$',
            re.MULTILINE,
        )
    return _ROW_RE_CACHE[combo]


def update_table(text: str, times: dict[str, str | None], pages: dict[str, int | None]) -> str:
    for combo in COMBOS:
        t = times.get(combo)
        p = pages.get(combo)

        def _sub(m: re.Match, t=t, p=p, combo=combo) -> str:
            track, lang_cell, old_pages, old_time = m.groups()
            lang_cell = lang_cell.replace('¹', '').strip()
            new_pages = str(p) if p is not None else old_pages.strip()
            new_time = t if t is not None else old_time.strip()
            return f'| `{combo}` | {track.strip()} | {lang_cell} | {new_pages} | {new_time} |'

        text = _row_re(combo).sub(_sub, text)

    # Remove a cláusula obsoleta "¹ Primeira geração..." da legenda da tabela
    # (o cache de tradução es/it já está populado, não é mais 1ª geração).
    text = re.sub(r' ¹[^{]*(\{#tbl-00-tempos\})', r' \1', text)
    return text


def main() -> None:
    row = _last_row()
    print(f"Usando linha de {row['timestamp']} (langs={row['pub_langs']}, locales={row['pub_locales']})")

    times = {c: _fmt_minutes(row.get(c)) for c in COMBOS}
    pages = {c: _page_count(c) for c in COMBOS}

    for combo in COMBOS:
        print(f'  {combo}: páginas={pages[combo]} tempo={times[combo]}')

    for locale, path in PREFACIO_FILES.items():
        if not path.exists():
            print(f'  ! {path} não encontrado, pulando')
            continue
        original = path.read_text(encoding='utf-8')
        updated = update_table(original, times, pages)
        if updated != original:
            path.write_text(updated, encoding='utf-8')
            print(f'  ✓ {path} atualizado')
        else:
            print(f'  = {path} sem mudanças')


if __name__ == '__main__':
    main()
