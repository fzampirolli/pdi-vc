"""
pipeline/notebook_processor.py
================================
Lê um notebook-fonte (Python/Português canônico) e gera uma versão
filtrada para o combo (lang, locale) solicitado.

Anatomia de um notebook-fonte (all/capXX/cap01.ipynb)
───────────────────────────────────────────────────────
Cada célula tem um campo de metadados `pdi` opcional:

  Célula de CÓDIGO Python:
    metadata: {"pdi": {"role": "code"}}   ← padrão; omissível
    source: código Python

  Célula de TEXTO (Markdown):
    metadata: {"pdi": {"role": "text"}}   ← padrão; omissível
    source: texto em Português

  Célula COMUM (aparece em todas as versões sem tradução):
    metadata: {"pdi": {"role": "common"}}

  Célula EXCLUÍDA de versões não-base:
    metadata: {"pdi": {"role": "base_only"}}

  Célula de EXERCÍCIO:
    metadata: {"pdi": {"role": "exercise"}}

Se o campo `pdi` estiver ausente, a célula é tratada como:
  - "code"   se for célula de código
  - "text"   se for célula Markdown

Processo de geração para combo (lang, locale):
  code cells   → CodeTranslator(lang).translate(source)
  text cells   → TextTranslator(locale).translate(source)
  common cells → mantidas sem alteração
  base_only    → removidas se não for combo base
"""

from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Optional
import re   # no topo do arquivo

try:
    import nbformat
except ImportError:
    raise ImportError("pip install nbformat")

from .config import BASE_LANG, BASE_LOCALE, Combo
from .translators import TranslatorFactory
from .bib import resolve_citations, resolve_bibliography

from nbformat.v4 import new_markdown_cell

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _cell_role(cell: nbformat.NotebookNode) -> str:
    """Retorna o papel da célula: code | text | common | base_only | exercise."""
    pdi = cell.get('metadata', {}).get('pdi', {})
    if pdi and 'role' in pdi:
        return pdi['role']
    # Inferência por tipo de célula
    return 'code' if cell.cell_type == 'code' else 'text'


def _get_source(cell) -> str:
    src = cell.get('source', '')
    return ''.join(src) if isinstance(src, list) else src


def _set_source(cell, src: str):
    cell['source'] = src


def _clean_cell(cell, is_base: bool = False):
    """Remove outputs e execution_count (preserva outputs no combo base)."""
    if 'outputs' in cell and not is_base:
        cell['outputs'] = []
    if 'execution_count' in cell:
        cell['execution_count'] = None
    pdi = cell.get('metadata', {}).get('pdi', {})
    cell['metadata'] = {'pdi': pdi} if pdi else {}


# ─────────────────────────────────────────────────────────────────────────────
# Pós-processamento Markdown (referências Quarto, figuras, callouts)
# ─────────────────────────────────────────────────────────────────────────────

CALLOUT_EMOJI = {
    'tip': '💡', 'note': '📝', 'warning': '⚠️',
    'important': '❗', 'caution': '🔴',
}


def _process_figures(src: str) -> str:
    def _fig(m):
        fig_id  = m.group(1)
        content = m.group(2).strip()
        lines   = content.split('\n')
        img_line = next((l for l in lines if l.strip().startswith('!')), '')
        caption  = ' '.join(l for l in lines if l.strip() and not l.strip().startswith('!'))
        img_m    = re.match(r'!\[.*?\]\((.+?)\)', img_line)
        img_src  = img_m.group(1) if img_m else ''
        num      = re.sub(r'fig-(\d+)-(\w+)', lambda x: f'{x.group(1)}.{x.group(2)}', fig_id)
        return (
            f'<figure id="{fig_id}">\n'
            f'<img src="{img_src}" alt="{caption}" '
            f'style="max-width:80%;display:block;margin:auto"/>\n'
            f'<figcaption><strong>Figura {num}:</strong> {caption}</figcaption>\n'
            f'</figure>'
        )
    return re.sub(r':::\s*\{#(fig-[\w-]+)\}(.*?):::', _fig, src, flags=re.DOTALL)


def _process_cross_refs(src: str) -> str:
    src = re.sub(r'\[-@(fig-(\d+)-(\w+))\]',
                 lambda m: f'[{m.group(2)}.{m.group(3)}](#{m.group(1)})', src)
    src = re.sub(r'@(fig-(\d+)-(\w+))',
                 lambda m: f'[Figura {m.group(2)}.{m.group(3)}](#{m.group(1)})', src)
    src = re.sub(r'@(tbl-(\d+)-(\w+))',
                 lambda m: f'[Tabela {m.group(2)}.{m.group(3)}](#{m.group(1)})', src)
    src = re.sub(r'@(eq-(\d+)-(\w+))',
                 lambda m: f'[Eq. {m.group(2)}.{m.group(3)}](#{m.group(1)})', src)
    return src


def _process_callouts(src: str) -> str:
    def _call(m):
        ctype = m.group(1).lower()
        body  = m.group(2).strip()
        emoji = CALLOUT_EMOJI.get(ctype, '📌')
        title_m = re.match(r'^#+\s+(.+)\n', body)
        if title_m:
            title = title_m.group(1)
            body  = body[title_m.end():]
        else:
            title = ctype.capitalize()
        quoted = '\n'.join(f'> {l}' for l in body.split('\n'))
        return f'> {emoji} **{title}**\n>\n{quoted}'
    return re.sub(r':::\s*\{\.callout-(\w+)\}(.*?):::',
                  _call, src, flags=re.DOTALL)


def _remove_quarto_attrs(src: str) -> str:
    src = re.sub(r'\{\.unnumbered[^}]*\}', '', src)
    src = re.sub(r'^:::+\s*$', '', src, flags=re.MULTILINE)
    return src


def postprocess_markdown(src: str, bib: dict, used_keys: set,
                         for_ipynb: bool = True) -> str:
    """Aplica todos os pós-processamentos Markdown."""
    src = resolve_citations(src, bib, used_keys)
    src = resolve_bibliography(src, bib, used_keys)
    if for_ipynb:
        src = _process_figures(src)
        src = _process_cross_refs(src)
        src = _process_callouts(src)
        src = _remove_quarto_attrs(src)
    return src


# ─────────────────────────────────────────────────────────────────────────────
# Processador principal
# ─────────────────────────────────────────────────────────────────────────────

class NotebookProcessor:
    """
    Processa um notebook-fonte para um Combo (lang, locale).

    Uso:
        proc = NotebookProcessor(factory, bib)
        out_nb = proc.process('all/cap01/cap01.ipynb', Combo('cpp', 'en'))
        nbformat.write(out_nb, open('gen/cpp.en/cap01/cap01.cpp.en.ipynb', 'w'))
    """

    def __init__(self, factory: TranslatorFactory, bib: dict):
        self._factory = factory
        self._bib = bib


    def _filter_by_language_marker(self, cell, target_lang: str) -> bool:
        src = _get_source(cell)
        lines = src.splitlines(keepends=True)
        # Procura em todas as linhas um marcador #[lang]#
        lang_found = None
        idx_to_remove = -1
        pattern = re.compile(r'^[#\s`]*#\[\s*(\w+)\s*\]#`?\s*$', re.MULTILINE)
        for i, line in enumerate(lines):
            if pattern.search(line):
                lang_found = pattern.search(line).group(1)
                idx_to_remove = i
                break

        if lang_found is not None:
            # Remove a linha inteira onde o marcador apareceu
            lines.pop(idx_to_remove)
            new_src = ''.join(lines)
            _set_source(cell, new_src)
            # Mantém a célula apenas se a linguagem for a desejada
            return lang_found == target_lang
        return True
    
    # --- Mesclagem do notebook de exercícios (EPs) ---
    def _merge_ep_notebook(self, main_nb, nb_path: Path, combo: Combo):
        ep_path = nb_path.parent / f"{nb_path.stem}.EPs.ipynb"
        if not ep_path.exists():
            return main_nb
        print(f"  📘 EP encontrado: {ep_path.name} — mesclando...")
        ep_nb = self.process(str(ep_path), combo)

        # --- Rebaixar títulos nível 1 para nível 2 ---
        def rebaixar_titulos(src: str) -> str:
            lines = src.split('\n')
            out = []
            in_code = False
            for line in lines:
                if line.strip().startswith('```'):
                    in_code = not in_code
                if not in_code and line.startswith('# ') and not line.startswith('## '):
                    line = '#' + line
                out.append(line)
            return '\n'.join(out)

        for cell in ep_nb.cells:
            if cell.cell_type == 'markdown':
                src = _get_source(cell)
                src = rebaixar_titulos(src)
                _set_source(cell, src)

        # --- Adicionar apenas separador visual sem título ---
        separator = new_markdown_cell("---\n")
        main_nb.cells.append(separator)
        main_nb.cells.extend(ep_nb.cells)
        return main_nb
    
    def process(self, nb_path: str, combo: Combo,
                for_ipynb: bool = True) -> nbformat.NotebookNode:
        with open(nb_path, encoding='utf-8') as f:
            nb = nbformat.read(f, as_version=4)

        code_tr = self._factory.code_translator(combo.lang)
        text_tr = self._factory.text_translator(combo.locale)

        used_keys: set = set()
        out_cells = []

        for cell in nb.cells:
            cell = copy.deepcopy(cell)
            role = _cell_role(cell)
            src  = _get_source(cell)


            # --- Filtro por marcador de linguagem ---
            if not self._filter_by_language_marker(cell, combo.lang):
                continue

            src = _get_source(cell)  # ← adicionar esta linha
            
            # ── Filtrar células base_only
            if role == 'base_only' and not combo.is_base():
                continue

            # ── Células raw (YAML frontmatter do Quarto) → descartar
            if cell.cell_type == 'raw':
                continue

            # ── Traduzir conforme papel
            if role == 'code' and cell.cell_type == 'code':
                translated = code_tr.translate(src)
                _set_source(cell, translated)

            elif role in ('text', 'exercise') and cell.cell_type == 'markdown':
                translated = text_tr.translate(src)
                if not combo.is_base():
                    translated = postprocess_markdown(
                        translated, self._bib, used_keys, for_ipynb=for_ipynb
                    )
                _set_source(cell, translated)

            # common → sem alteração

            _clean_cell(cell, is_base=combo.is_base())

            if _get_source(cell).strip():
                out_cells.append(cell)

        nb.cells = out_cells

        # --- Mesclagem do notebook de exercícios (EPs) ---
        nb = self._merge_ep_notebook(nb, Path(nb_path), combo)

        return nb