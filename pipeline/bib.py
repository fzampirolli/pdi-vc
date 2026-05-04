"""
pipeline/bib.py
===============
Parser BibTeX mínimo + formatação ABNT inline e completa.
Isolado aqui para não duplicar em outros módulos.
"""

import re
from pathlib import Path
from typing import Optional


def parse_bib(bib_path: str | Path) -> dict:
    """Lê um .bib e retorna {chave: {campo: valor}}."""
    entries: dict = {}
    path = Path(bib_path)
    if not path.exists():
        return entries
    content = path.read_text(encoding='utf-8')
    for m in re.finditer(r'@(\w+)\{([^,]+),([^@]*)', content, re.DOTALL):
        key    = m.group(2).strip()
        body   = m.group(3)
        fields = {'_type': m.group(1).lower()}
        for fm in re.finditer(
            r'(\w+)\s*=\s*[{"](.+?)[}"],?\s*(?=\w+\s*=|\Z)', body, re.DOTALL
        ):
            fields[fm.group(1).lower()] = fm.group(2).strip().replace('\n', ' ')
        entries[key] = fields
    return entries


def _surname(author_str: str) -> str:
    first = author_str.split(' and ')[0].strip()
    parts = [p for p in first.split(',')[0].split() if p]
    return parts[-1] if parts else author_str


def cite_indirect(key: str, bib: dict) -> str:
    """[@key] → (SOBRENOME, ano)"""
    if key not in bib:
        return f'({key})'
    e = bib[key]
    return f'({_surname(e.get("author","?")).upper()}, {e.get("year","s.d.")})'


def cite_direct(key: str, bib: dict) -> str:
    """@key → Sobrenome (ano)"""
    if key not in bib:
        return key
    e = bib[key]
    return f'{_surname(e.get("author","?")).capitalize()} ({e.get("year","s.d.")})'


def format_ref_abnt(key: str, bib: dict) -> str:
    if key not in bib:
        return f'{key}.'
    e    = bib[key]
    auth = e.get('author', key).upper()
    year = e.get('year', 's.d.')
    title     = e.get('title', '')
    journal   = e.get('journal', '')
    publisher = e.get('publisher', '')
    url       = e.get('url', '')
    ref = f'{auth}. **{title}**.'
    if journal:
        ref += f' *{journal}*'
        v = e.get('volume', '')
        if v:
            ref += f', v. {v}'
        ref += f', {year}.'
    elif publisher:
        ref += f' {publisher}, {year}.'
    else:
        ref += f' {year}.'
    if url:
        ref += f' Disponível em: <{url}>.'
    return ref


def resolve_citations(src: str, bib: dict, used: set) -> str:
    """Substitui @key e [@key] por citações ABNT e coleta chaves usadas."""
    for m in re.finditer(r'@([A-Za-z0-9_:.-]+)', src):
        if m.group(1) in bib:
            used.add(m.group(1))
    src = re.sub(r'\[@([A-Za-z0-9_:.-]+)\]',
                 lambda m: cite_indirect(m.group(1), bib), src)
    src = re.sub(r'(?<!\[)@([A-Za-z0-9_:.-]+)',
                 lambda m: cite_direct(m.group(1), bib), src)
    return src


def resolve_bibliography(src: str, bib: dict, used: set) -> str:
    """Substitui \\printbibliography pela lista formatada ABNT."""
    if '\\printbibliography' not in src:
        return src
    lines = ['## Referências\n']
    for key in sorted(used):
        lines.append(f'- {format_ref_abnt(key, bib)}\n')
    return src.replace('\\printbibliography', '\n'.join(lines))
