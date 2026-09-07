#!/usr/bin/env python3
"""
check_combos.py — validações de consistência entre combos gerados.

Dois checks:

  1. locale-consistency (fácil): dentro da MESMA linguagem, os notebooks
     dos 3 idiomas (pt/en/fr) devem ter a MESMA estrutura — mesmo nº de
     células de código e markdown, mesma lista ordenada de `#| label:`,
     e o HTML renderizado deve ter a mesma contagem de figuras, zero
     cross-refs quebrados (`?@fig`/`?@tbl`/…) e zero erros de execução.
     Só o TEXTO muda entre idiomas; a estrutura, não.

  2. lang-parity (difícil): entre py e cpp (mesmo idioma, pt por padrão),
     toda figura/tabela rotulada (`#| label:`) presente na trilha py deve
     aparecer também na cpp — uma célula de código py vira N células em
     cpp (writefile / g++ / glue), mas os LABELS têm que casar. Nenhuma
     célula pode ter caído para "referência conceitual" (`não portado`),
     e o HTML das duas não pode ter cross-ref quebrado.

Uso:
    python check_combos.py                      # os dois checks, caps padrão
    python check_combos.py --locale-consistency
    python check_combos.py --lang-parity --locale pt
    python check_combos.py --chapters cap01,cap02
    python check_combos.py --langs py,cpp --locales pt,en,fr

Sai com código != 0 se algum check FALHAR (uso em CI / `make check-combos`).
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
import sys
from pathlib import Path

try:
    from pipeline.config import CPP_CHAPTERS
except Exception:                     # execução fora do venv / sem pipeline
    CPP_CHAPTERS = {'cap01', 'cap02', 'cap03', 'cap04'}

ROOT = Path(__file__).resolve().parent
GEN = ROOT / 'gen'
BOOK = GEN / 'book'

_LABEL_RE = re.compile(r'^\s*(?://|#)\|\s*label:\s*(\S+)', re.M)
# cross-ref não resolvido: Quarto emite `?@fig-x` no texto e/ou a classe abaixo
_BROKEN_REF_RE = re.compile(r'\?@(?:fig|tbl|eq|sec|lst|thm)-[\w-]+'
                            r'|class="quarto-unresolved-ref"')
_CELL_OUT_RE = re.compile(r'<div class="cell-output[^"]*">.*?</div>', re.S)
_FIG_IMG_RE = re.compile(r'<img\b[^>]*\bsrc="[^"]*(?:fig-|figure-html)[^"]*"')


# ─────────────────────────────────────────────────────────────────────────────
# helpers
# ─────────────────────────────────────────────────────────────────────────────
def _src(cell) -> str:
    s = cell.get('source', '')
    return ''.join(s) if isinstance(s, list) else s


def _load_nb(path: Path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


_MARKER_RE = re.compile(r'^\s*(?:<!--\s*)?#\[(py|cpp)\]#', re.M)
_EP_PLACEHOLDER_RE = re.compile(r'^\s*%%writefile\s+EP\d+_\d+\.py\s*$', re.M)


def _nb_stats(path: Path) -> dict:
    nb = _load_nb(path)
    code = [c for c in nb['cells'] if c['cell_type'] == 'code']
    md = [c for c in nb['cells'] if c['cell_type'] == 'markdown']
    labels = []            # todos os labels
    marked_labels = set()   # labels em célula #[py]#/#[cpp]# (single-track de propósito)
    refs = 0                # células "não portado" (exclui placeholders de EP)
    for c in nb['cells']:
        s = _src(c)
        found = _LABEL_RE.findall(s)
        labels += found
        if _MARKER_RE.search(s):
            marked_labels.update(found)
        if ('não portado para esta linguagem' in s
                or 'not yet ported to this language' in s):
            if not _EP_PLACEHOLDER_RE.search(s):
                refs += 1
    return {
        'code': len(code), 'md': len(md),
        'labels': labels, 'label_set': set(labels),
        'marked_labels': marked_labels,
        'shared_label_set': set(labels) - marked_labels,
        'ref_cells': refs, 'path': path,
    }


def _html_stats(path: Path) -> dict | None:
    if not path.exists():
        return None
    html = path.read_text(encoding='utf-8', errors='replace')
    outs = _CELL_OUT_RE.findall(html)
    errs = sum(1 for b in outs
               if 'Traceback (most recent call last)' in b
               or 'An error occurred while executing' in b)
    broken = len(_BROKEN_REF_RE.findall(html))
    figs = len(_FIG_IMG_RE.findall(html))
    return {'errors': errs, 'broken_refs': broken, 'figs': figs}


def _source_marked_labels(cap: str) -> set[str]:
    """Labels que, NO FONTE (all/capNN/*.ipynb + .EPs), estão numa célula
    marcada `#[py]#`/`#[cpp]#` — logo são single-track de propósito e não
    precisam existir nas duas trilhas."""
    marked: set[str] = set()
    for name in (f'{cap}.ipynb', f'{cap}.EPs.ipynb'):
        p = ROOT / 'all' / cap / name
        if not p.exists():
            continue
        for c in _load_nb(p)['cells']:
            s = _src(c)
            if _MARKER_RE.search(s):
                marked.update(_LABEL_RE.findall(s))
    return marked


def _gen_nb(lang: str, loc: str, cap: str) -> Path:
    return GEN / f'{lang}.{loc}' / cap / f'{cap}.{lang}.{loc}.ipynb'


def _book_html(lang: str, loc: str, cap: str) -> Path:
    return BOOK / f'{lang}.{loc}' / cap / f'{cap}.{lang}.{loc}.html'


class Report:
    def __init__(self):
        self.fail = 0
        self.warn = 0

    def ok(self, msg):    print(f'  \033[32m✓\033[0m {msg}')
    def bad(self, msg):   print(f'  \033[31m✗ FAIL\033[0m {msg}'); self.fail += 1
    def wrn(self, msg):   print(f'  \033[33m! WARN\033[0m {msg}'); self.warn += 1
    def info(self, msg):  print(f'    {msg}')


# ─────────────────────────────────────────────────────────────────────────────
# check 1 — consistência entre idiomas (mesma linguagem)
# ─────────────────────────────────────────────────────────────────────────────
def check_locale_consistency(langs, locales, chapters, rep: Report):
    print('\n=== locale-consistency (estrutura pt vs en vs fr) ===')
    for lang in langs:
        locs = [lo for lo in locales if _gen_nb(lang, lo, chapters[0]).exists()
                or any(_gen_nb(lang, lo, c).exists() for c in chapters)]
        locs = [lo for lo in locales
                if any(_gen_nb(lang, lo, c).exists() for c in chapters)]
        if len(locs) < 2:
            rep.info(f'{lang}: <2 idiomas gerados ({locs or "nenhum"}) — pulando')
            continue
        for cap in chapters:
            nbs = {lo: _gen_nb(lang, lo, cap) for lo in locs if _gen_nb(lang, lo, cap).exists()}
            if len(nbs) < 2:
                continue
            stats = {lo: _nb_stats(p) for lo, p in nbs.items()}
            base_lo = 'pt' if 'pt' in stats else sorted(stats)[0]
            base = stats[base_lo]
            tag = f'{lang} {cap}'
            for lo, st in stats.items():
                if lo == base_lo:
                    continue
                diffs = []
                if st['code'] != base['code']:
                    diffs.append(f"code {st['code']}≠{base['code']}")
                if st['md'] != base['md']:
                    diffs.append(f"md {st['md']}≠{base['md']}")
                cb, cl = Counter(base['labels']), Counter(st['labels'])
                if cb != cl:
                    only_b = sorted(base['label_set'] - st['label_set'])
                    only_l = sorted(st['label_set'] - base['label_set'])
                    if only_b or only_l:
                        diffs.append(f"labels: só em {base_lo}={only_b[:5]} só em {lo}={only_l[:5]}")
                    else:
                        cntd = sorted(k for k in cb if cb[k] != cl[k])
                        ex = cntd[0] if cntd else '?'
                        diffs.append(f"labels iguais mas repetições diferem "
                                     f"(ex.: {ex} ×{cb.get(ex)} em {base_lo} vs ×{cl.get(ex)} em {lo})")
                if diffs:
                    rep.bad(f'{tag}: {lo} vs {base_lo} — ' + ' | '.join(diffs))
                else:
                    rep.ok(f'{tag}: {lo} estrutura == {base_lo} '
                           f'({base["code"]} code, {len(base["labels"])} labels)')
            # HTML
            for lo, st in stats.items():
                h = _html_stats(_book_html(lang, lo, cap))
                if h is None:
                    rep.wrn(f'{tag} {lo}: HTML não renderizado')
                    continue
                if h['errors']:
                    rep.bad(f'{tag} {lo}: {h["errors"]} erro(s) de execução no HTML')
                if h['broken_refs']:
                    rep.bad(f'{tag} {lo}: {h["broken_refs"]} cross-ref quebrado no HTML')
            # figuras iguais entre idiomas?
            hs = {lo: _html_stats(_book_html(lang, lo, cap)) for lo in stats}
            hs = {lo: v for lo, v in hs.items() if v}
            if len(hs) >= 2:
                figset = {v['figs'] for v in hs.values()}
                if len(figset) > 1:
                    rep.bad(f'{tag}: contagem de figuras difere entre idiomas '
                            + ', '.join(f'{lo}={v["figs"]}' for lo, v in hs.items()))
                else:
                    rep.ok(f'{tag}: {figset.pop()} figuras em todos os idiomas')


# ─────────────────────────────────────────────────────────────────────────────
# check 2 — paridade py vs cpp (mesmo idioma)
# ─────────────────────────────────────────────────────────────────────────────
def check_lang_parity(locale, chapters, rep: Report):
    print(f'\n=== lang-parity (py vs cpp, locale={locale}) ===')
    for cap in chapters:
        if cap not in CPP_CHAPTERS:
            rep.info(f'{cap}: fora de CPP_CHAPTERS — pulando')
            continue
        py_p = _gen_nb('py', locale, cap)
        cp_p = _gen_nb('cpp', locale, cap)
        if not py_p.exists() or not cp_p.exists():
            rep.wrn(f'{cap}: gen ausente (py={py_p.exists()}, cpp={cp_p.exists()})')
            continue
        py, cp = _nb_stats(py_p), _nb_stats(cp_p)
        marked = _source_marked_labels(cap)   # single-track de propósito (fonte)

        py_shared = py['label_set'] - marked
        missing = sorted(py_shared - cp['label_set'])
        extra = sorted((cp['label_set'] - marked) - py['label_set'])
        n_marked = len(py['label_set'] & marked)
        if missing:
            rep.bad(f'{cap}: {len(missing)} figura(s)/tabela(s) sem marcador em py '
                    f'que sumiram no cpp: {missing}')
        elif extra:
            rep.wrn(f'{cap}: cpp tem label(s) que py não tem: {extra}')
        else:
            note = f' (+{n_marked} #[py]#/#[cpp]#-only)' if n_marked else ''
            rep.ok(f'{cap}: {len(py_shared)} labels compartilhados presentes em py e cpp{note}')

        if cp['ref_cells']:
            rep.bad(f'{cap}: cpp tem {cp["ref_cells"]} célula(s) em "referência conceitual" '
                    f'(não portado) — deveria ser 0')
        else:
            rep.ok(f'{cap}: cpp sem células caídas para referência')

        hpy = _html_stats(_book_html('py', locale, cap))
        hcp = _html_stats(_book_html('cpp', locale, cap))
        for name, h in (('py', hpy), ('cpp', hcp)):
            if h is None:
                rep.wrn(f'{cap}: HTML {name} não renderizado')
                continue
            if h['errors']:
                rep.bad(f'{cap}: {h["errors"]} erro(s) de execução no HTML {name}')
            if h['broken_refs']:
                rep.bad(f'{cap}: {h["broken_refs"]} cross-ref quebrado no HTML {name}')
        if hpy and hcp:
            if hpy['figs'] == hcp['figs']:
                rep.ok(f'{cap}: {hpy["figs"]} figuras em py e cpp')
            else:
                rep.wrn(f'{cap}: figuras py={hpy["figs"]} cpp={hcp["figs"]} '
                        f'(esperado se há células #[py]#/#[cpp]# de matplotlib)')


# ─────────────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--locale-consistency', action='store_true',
                    help='só o check de estrutura entre idiomas')
    ap.add_argument('--lang-parity', action='store_true',
                    help='só o check de paridade py vs cpp')
    ap.add_argument('--langs', default='py,cpp')
    ap.add_argument('--locales', default='pt,en,fr')
    ap.add_argument('--locale', default='pt', help='idioma do check lang-parity')
    ap.add_argument('--chapters', default=None,
                    help='ex.: cap01,cap02 (padrão: CPP_CHAPTERS ordenado)')
    args = ap.parse_args()

    chapters = (args.chapters.split(',') if args.chapters
                else sorted(CPP_CHAPTERS))
    langs = args.langs.split(',')
    locales = args.locales.split(',')

    run_loc = args.locale_consistency or not (args.locale_consistency or args.lang_parity)
    run_par = args.lang_parity or not (args.locale_consistency or args.lang_parity)

    rep = Report()
    if run_loc:
        check_locale_consistency(langs, locales, chapters, rep)
    if run_par:
        check_lang_parity(args.locale, chapters, rep)

    print()
    if rep.fail:
        print(f'\033[31m{rep.fail} FALHA(S)\033[0m'
              + (f', {rep.warn} aviso(s)' if rep.warn else ''))
        sys.exit(1)
    print(f'\033[32mOK\033[0m — 0 falhas'
          + (f', {rep.warn} aviso(s)' if rep.warn else ''))


if __name__ == '__main__':
    main()
