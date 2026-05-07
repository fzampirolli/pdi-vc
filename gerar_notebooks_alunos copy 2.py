#!/usr/bin/env python3
"""
gerar_notebooks_alunos.py
--------------------
Pos-processa notebooks Quarto (.ipynb) para distribuicao no Colab/Jupyter.
Resolve citacoes bibliograficas @key, referencias cruzadas de figuras @fig-*,
tabelas @tbl-* e equacoes @eq-*, injeta lista de referencias e copia imagens.
Zero dependencias externas.

--- MODO UNICO ---
    python gerar_notebooks_alunos.py <notebook.ipynb> <references.bib> [-o saida.ipynb]

--- MODO BATCH ---
    python gerar_notebooks_alunos.py --batch <references.bib> [--out-dir notebooks_alunos]

Sintaxe Quarto suportada:
    Citacao direta:          @russell2004              -> Russell e Norvig (2004)
    Citacao indireta:        [@russell2004]            -> (RUSSELL; NORVIG, 2004)
    Multiplas indiretas:     [@han2008; @tan2009]      -> (HAN; KAMBER, 2008; TAN et al., 2009)
    Ref de figura:           @fig-1-1                  -> [Figura 1.1](#fig-1-1)
    Def de figura:           ![alt](img){#fig-X-Y}     -> <figure> com legenda
    Ref de tabela:           @tbl-2-1                  -> [Tabela 2.1](#tbl-2-1)
    Def tabela-imagem:       ![alt](img){#tbl-X-Y}     -> <figure> com legenda "Tabela"
    Def tabela Markdown:     | col |...{#tbl-X-Y}      -> <div> com legenda "Tabela"
    Ref de equacao:          @eq-1-1                   -> [Equacao 1.1](#eq-1-1)
    Def de equacao:          $$ ... $$ {#eq-X-Y}       -> HTML com numero (X.Y)
    Callout/div Quarto:      ::: {.callout-tip} ... ::: -> blockquote HTML
    Div generico:            ::: {.qualquer} ... :::    -> conteudo sem marcas
"""

import json
import re
import shutil
import argparse
import glob
from pathlib import Path


# Adicione após os imports (por volta da linha 30)

# ---------------------------------------------------------------------------
# 1.5. Sistema de numeração de seções
# ---------------------------------------------------------------------------

class SectionNumbering:
    """Gerencia a numeração de capítulos, seções e subseções."""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.numbers = {
            'chapter': 0,
            'section': 0,
            'subsection': 0,
            'subsubsection': 0
        }
    
    def set_chapter(self, chapter: int):
        """Define o número do capítulo diretamente sem incrementar."""
        self.numbers['chapter'] = chapter
        self.numbers['section'] = 0
        self.numbers['subsection'] = 0
        self.numbers['subsubsection'] = 0
    
    def inc_chapter(self) -> str:
        # Se já está no capítulo correto (>=1), não incrementa na primeira vez
        if self.numbers['chapter'] == 0:
            self.numbers['chapter'] = 1
        else:
            self.numbers['chapter'] += 1
        self.numbers['section'] = 0
        self.numbers['subsection'] = 0
        self.numbers['subsubsection'] = 0
        return self.get_chapter()
    
    def inc_section(self) -> str:
        self.numbers['section'] += 1
        self.numbers['subsection'] = 0
        self.numbers['subsubsection'] = 0
        return self.get_section()
    
    def inc_subsection(self) -> str:
        self.numbers['subsection'] += 1
        self.numbers['subsubsection'] = 0
        return self.get_subsection()
    
    def inc_subsubsection(self) -> str:
        self.numbers['subsubsection'] += 1
        return self.get_subsubsection()
    
    def get_chapter(self) -> str:
        return str(self.numbers['chapter'])
    
    def get_section(self) -> str:
        return f"{self.numbers['chapter']}.{self.numbers['section']}"
    
    def get_subsection(self) -> str:
        return f"{self.numbers['chapter']}.{self.numbers['section']}.{self.numbers['subsection']}"
    
    def get_subsubsection(self) -> str:
        return f"{self.numbers['chapter']}.{self.numbers['section']}.{self.numbers['subsection']}.{self.numbers['subsubsection']}"

# Instância global para o processamento
_section_numbering = SectionNumbering()

# ---------------------------------------------------------------------------
# 1. Parser BibTeX
# ---------------------------------------------------------------------------

def parse_bib(bib_path: str) -> dict:
    text = Path(bib_path).read_text(encoding="utf-8")
    entries = {}
    entry_re = re.compile(r'@\w+\s*\{\s*([^,]+),\s*(.*?)\n\}', re.DOTALL)
    field_re = re.compile(r'(\w+)\s*=\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}', re.DOTALL)
    for m in entry_re.finditer(text):
        key  = m.group(1).strip()
        body = m.group(2)
        fields = {f.group(1).lower(): f.group(2).strip()
                  for f in field_re.finditer(body)}
        entries[key] = fields
    return entries


# ---------------------------------------------------------------------------
# 2. Formatador ABNT
# ---------------------------------------------------------------------------

def format_authors(raw: str) -> str:
    authors = [a.strip() for a in raw.split(" and ")]
    
    def format_single_name(author_str):
        parts = author_str.split(",")
        if len(parts) == 2:
            return f"{parts[0].strip().upper()}, {parts[1].strip()}"
        else:
            tokens = author_str.split()
            if tokens:
                iniciais = ". ".join(t[0] for t in tokens[:-1]) + "." if len(tokens) > 1 else ""
                return f"{tokens[-1].upper()}, {iniciais}".strip(", ")
            return author_str

    if len(authors) > 3:
        # Retorna o primeiro autor e o et al. em itálico
        res = f"{format_single_name(authors[0])} *et al*"
    else:
        # Retorna 1 ou 2 autores separados por ponto e vírgula
        res = "; ".join(format_single_name(a) for a in authors)
    
    # Remove ponto final residual para evitar o ".." na função format_entry
    return res.rstrip('.')

def format_entry(key: str, fields: dict) -> str:
    parts = []
    if "author" in fields:
        parts.append(format_authors(fields["author"]))
    parts.append(f"**{fields.get('title', 'Sem titulo')}**")
    pub = [fields[k] for k in ("address", "publisher", "year") if k in fields]
    if pub:
        parts.append(", ".join(pub))
    return ". ".join(parts) + "."




# ---------------------------------------------------------------------------
# 2b. Formatadores de citacao ABNT no texto
# ---------------------------------------------------------------------------

def _last_names(raw_author: str) -> list:
    """
    Extrai lista de sobrenomes de um campo 'author' do BibTeX.
    Suporta 'Sobrenome, Nome' e 'Nome Sobrenome'.
    """
    surnames = []
    for author in raw_author.split(" and "):
        author = author.strip()
        if "," in author:
            # "Forouzan, B." -> "Forouzan"
            surnames.append(author.split(",")[0].strip())
        else:
            # "Behrouz Forouzan" -> "Forouzan"
            parts = author.split()
            if parts:
                surnames.append(parts[-1].strip())
    return surnames


def cite_direct(fields: dict) -> str:
    """
    Citacao DIRETA: autor no texto, ano entre parenteses.
    ABNT NBR 10520:
      1 autor:  Forouzan (2011)
      2 autores: Forouzan e Mosharraf (2011)
      3+ autores: Tan et al. (2009)
    """
    year = fields.get("year", "s.d.")
    surnames = _last_names(fields.get("author", ""))

    if not surnames:
        return f"({year})"

    if len(surnames) == 1:
        name_part = surnames[0]
    elif len(surnames) == 2:
        name_part = f"{surnames[0]} e {surnames[1]}"
    else:
        name_part = f"{surnames[0]} et al."

    return f"{name_part} ({year})"


def cite_indirect(fields: dict) -> str:
    """
    Citacao INDIRETA: autor e ano entre parenteses, sobrenome em caixa alta.
    ABNT NBR 10520:
      1 autor:  (FOROUZAN, 2011)
      2 autores: (FOROUZAN; MOSHARRAF, 2011)
      3+ autores: (TAN et al., 2009)
    """
    year = fields.get("year", "s.d.")
    surnames = _last_names(fields.get("author", ""))

    if not surnames:
        return f"({year})"

    upper = [s.upper() for s in surnames]

    if len(upper) == 1:
        name_part = upper[0]
    elif len(upper) == 2:
        name_part = f"{upper[0]}; {upper[1]}"
    else:
        name_part = f"{upper[0]} et al."

    return f"({name_part}, {year})"

# ---------------------------------------------------------------------------
# 3. Utilitarios de source Jupyter
# ---------------------------------------------------------------------------

def source_to_str(source) -> str:
    if isinstance(source, list):
        return "".join(source)
    return source or ""


def str_to_source(text: str) -> list:
    if not text:
        return []
    return text.splitlines(keepends=True)


# ---------------------------------------------------------------------------
# 4. Prefixos de cross-references Quarto (nao sao citacoes bibliograficas)
# ---------------------------------------------------------------------------

CROSSREF_RE = re.compile(
    r'^(fig|tbl|sec|eq|lst|thm|lem|cor|prp|def|exm|exr|rem)-'
)


# ---------------------------------------------------------------------------
# 5. Padroes de definicao Quarto
# ---------------------------------------------------------------------------

# ![alt](path){#fig-X-Y ...}  ou  ![alt](path){#tbl-X-Y ...}
IMG_DEF_RE = re.compile(
    r'!\[([^\]]*)\]\(([^)\s"\']+)[^)]*\)\{#((fig|tbl)-[\w-]+)[^}]*\}'
)

# Tabela Markdown: aceita AMBAS as sintaxes:
#   Sintaxe antiga:  | col |...\n{#tbl-X-Y}
#   Sintaxe Quarto:  | col |...\n\n: Legenda {#tbl-X-Y}
# Grupos: (1) bloco tabela  (2) legenda Quarto  (3) id Quarto  (4) id antiga
# TBL_MD_RE = re.compile(
#     r'((?:[ \t]*\|[^\n]+\n)+)'           # bloco de linhas | col |
#     r'(?:'
#         r'\n?[ \t]*: ([^\n{]*?)\s*\{#(tbl-[\w-]+)[^}]*\}'  # Quarto: : Legenda {#tbl-X}
#         r'|'
#         r'[ \t]*\{#(tbl-[\w-]+)[^}]*\}'  # antiga: {#tbl-X} direto
#     r')',
#     re.MULTILINE
# )
# Tabela Markdown: busca o ID {#tbl- explicitamente para não confundir com LaTeX \frac{}{}
# TBL_MD_RE = re.compile(
#     r'((?:[ \t]*\|[^\n]+\n)+)'           # bloco de linhas | col |
#     r'(?:'
#         r'\n?[ \t]*: ([^\n{]*?)\s*\{#(tbl-[\w-]+)[^}]*\}'  # Quarto: : Legenda {#tbl-X}
#         r'|'
#         r'[ \t]*\{#(tbl-[\w-]+)[^}]*\}'  # antiga: {#tbl-X} direto
#     r')',
#     re.MULTILINE | re.DOTALL
# )
# Tabela Markdown: busca o ID {#tbl- explicitamente e suporta LaTeX na legenda
TBL_MD_RE = re.compile(
    r'((?:[ \t]*\|[^\n]+\n)+)'           # 1. Bloco de linhas da tabela
    r'(?:\n[ \t]*: (.*?)\s*\{#(tbl-[\w-]+)[^}]*\})' # 2. Legenda Quarto e 3. ID
    r'|'                                 # OU
    r'((?:[ \t]*\|[^\n]+\n)+)'           # 4. Bloco de linhas (caso sem legenda : )
    r'(?:[ \t]*\{#(tbl-[\w-]+)[^}]*\})', # 5. ID (sintaxe antiga)
    re.MULTILINE | re.DOTALL
)

# Equacao: $$ ... $$ (possivelmente multiline) seguida de {#eq-X-Y}
# Usa [\s\S]*? em vez de .*? com re.DOTALL para nao ser guloso
# entre multiplos blocos $$ na mesma celula
EQ_DEF_RE = re.compile(
    r'(\$\$[\s\S]*?\$\$)'       # bloco $$ ... $$ (multiline, nao guloso)
    r'[ \t]*\n?[ \t]*'
    r'\{#(eq-[\w-]+)[^}]*\}',    # {#eq-X-Y}
)

# ---------------------------------------------------------------------------
# Callouts e divs Quarto:  ::: {.callout-*}  ...  :::
# Suporta callout-note, callout-tip, callout-warning, callout-important,
# callout-caution, e divs genericos ::: {.qualquer-classe}
# ---------------------------------------------------------------------------

# Mapeamento de tipo de callout -> emoji + titulo padrao
CALLOUT_STYLE = {
    "callout-note":      ("📝", "Nota"),
    "callout-tip":       ("💡", "Dica"),
    "callout-warning":   ("⚠️", "Atenção"),
    "callout-important": ("❗", "Importante"),
    "callout-caution":   ("🔔", "Cuidado"),
}

# Regex para abertura de bloco div/callout: ::: {.classe ...} ou ::: {#id .classe}
DIV_OPEN_RE = re.compile(
    r'^:::+\s*\{([^}]*)\}\s*$',
    re.MULTILINE
)

def md_inline_to_html(text: str) -> str:
    """
    Converte Markdown inline e blocos simples para HTML puro, necessario dentro
    de blocos HTML (como <blockquote>) onde o Jupyter/Colab nao processa Markdown.
      > texto          ->  conteudo sem o '> ' (ja esta num blockquote)
      **[texto](url)** ->  <strong><a href="url">texto</a></strong>
      *[texto](url)*   ->  <em><a href="url">texto</a></em>
      [texto](url)     ->  <a href="url">texto</a>
      **texto**        ->  <strong>texto</strong>  (suporta multiline)
      *texto*          ->  <em>texto</em>
      `codigo`         ->  <code>codigo</code>

    Trechos LaTeX sao protegidos antes das substituicoes de Markdown e
    convertidos para os delimitadores que o MathJax processa dentro de HTML:
      $...$   ->  \\(...\\)
      $$...$$ ->  \\[...\\]
    """
    # ── 1. Proteger e converter delimitadores LaTeX ───────────────────────────
    # Dentro de <blockquote> HTML o Jupyter/MathJax nao processa $...$,
    # mas processa \(...\) e \[...\].
    placeholders = {}
    counter = [0]

    def _stash(m):
        key = "\x00LATEX{}\x00".format(counter[0])
        latex = m.group(0)
        if latex.startswith('$$'):
            inner = latex[2:-2]
            placeholders[key] = '\\[' + inner + '\\]'
        else:
            inner = latex[1:-1]
            placeholders[key] = '\\(' + inner + '\\)'
        counter[0] += 1
        return key

    # Display math $$...$$ (multiline, nao guloso) — deve vir antes do inline $
    text = re.sub(r'\$\$[\s\S]*?\$\$', _stash, text)
    # Inline math $...$ — nao cruza quebras de linha
    text = re.sub(r'\$[^\$\n]+?\$', _stash, text)

    # ── 2. Transformacoes Markdown ─────────────────────────────────────────────
    # Remove marcas de blockquote Markdown (> ) — ja estamos dentro de um <blockquote>
    text = re.sub(r'^> ?', '', text, flags=re.MULTILINE)

    # Negrito + link: **[texto](url)**
    text = re.sub(
        r'\*\*\[([^\]]+)\]\(([^)]+)\)\*\*',
        r'<strong><a href="\2">\1</a></strong>', text)
    # Italico + link: *[texto](url)*
    text = re.sub(
        r'\*\[([^\]]+)\]\(([^)]+)\)\*',
        r'<em><a href="\2">\1</a></em>', text)
    # Link simples: [texto](url)
    text = re.sub(
        r'\[([^\]]+)\]\(([^)]+)\)',
        r'<a href="\2">\1</a>', text)
    # Negrito: **texto** — re.DOTALL para capturar frases que cruzam linhas
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text, flags=re.DOTALL)
    # Italico: *texto* — apenas inline, sem cruzar linhas
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    # Codigo inline: `texto`
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)

    # ── 3. Restaurar LaTeX ─────────────────────────────────────────────────────
    for key, original in placeholders.items():
        text = text.replace(key, original)

    return text


def md_table_to_html(md: str) -> str:
    """
    Converte uma tabela Markdown simples para HTML puro.
    Necessário dentro de blocos HTML onde o Jupyter/Colab não processa Markdown.
    """
    lines = [l.strip() for l in md.strip().splitlines() if l.strip()]
    if not lines:
        return ""

    rows = []
    for line in lines:
        # Remove pipes externos e divide colunas
        cells = [c.strip() for c in line.strip('|').split('|')]
        rows.append(cells)

    if len(rows) < 2:
        return md  # Não é tabela válida, retorna original

    header_cells = rows[0]
    # Linha 1 é o separador (--- | ---), pula
    data_rows = rows[2:]

    th_html = "".join(
        f'<th style="border:1px solid #ccc; padding:4px 8px; background:#f0f0f0; text-align:left;">{c}</th>'
        for c in header_cells
    )
    tr_rows = ""
    for row in data_rows:
        tds = "".join(
            f'<td style="border:1px solid #ccc; padding:4px 8px;">{c}</td>'
            for c in row
        )
        tr_rows += f'<tr>{tds}</tr>\n'

    return (
        f'<table style="border-collapse:collapse; width:100%;">\n'
        f'<thead><tr>{th_html}</tr></thead>\n'
        f'<tbody>\n{tr_rows}</tbody>\n'
        f'</table>'
    )

def resolve_crossrefs_to_html(text: str, elem_map: dict) -> str:
    """Resolve @tbl-*, @fig-*, @eq-* para <a href> HTML (não Markdown)."""
    def _replace(m):
        elem_id = m.group(1)
        info = elem_map.get(elem_id)
        if not info:
            return m.group(0)
        kind = info.get("kind", elem_id.split('-')[0])
        prefix = "Tabela" if kind == "tbl" else "Figura" if kind == "fig" else "Equação"
        num = info.get("num_str", "")
        return f'<a href="#{elem_id}">{prefix} {num}</a>'
    return re.sub(r'@((fig|tbl|eq)-[\w-]+)', _replace, text)

def convert_callouts(text: str, elem_map: dict) -> str:
    """
    Converte blocos ::: {.callout-*} ... ::: e blocos de figuras/tabelas agrupadas
    ::: {#fig-ID layout-ncol=2} ... ::: para HTML/Markdown compatível com Colab.
    """
    lines = text.split('\n')
    out   = []
    i     = 0

    while i < len(lines):
        line = lines[i]
        # Detecta abertura de ::: {atributos}
        m = re.match(r'^(:::+)\s*\{([^}]*)\}\s*$', line)

        if m:
            fence_len = len(m.group(1))
            attrs     = m.group(2).strip()

            # 1. Verifica se é um Callout conhecido
            callout_type = None
            for ct in CALLOUT_STYLE:
                if ct in attrs:
                    callout_type = ct
                    break

            # 2. Verifica se é um grupo de figuras/tabelas com ID e Layout
            # Ex: ::: {#fig-2-2 layout-ncol=2}
            group_id_m = re.search(r'#((?:fig|tbl)-[\w-]+)', attrs)
            has_layout = "layout-ncol" in attrs or "layout=" in attrs or "layout-nrow" in attrs

            # Coleta o conteúdo interno do bloco ::: até o fechamento
            # Usa pilha de fence_len para rastrear blocos aninhados corretamente
            i += 1
            fence_stack = [fence_len]
            inner = []
            title_override = None

            while i < len(lines) and fence_stack:
                l = lines[i]
                open_m = re.match(r'^(:::+)\s*\{', l)
                close_m = re.match(r'^(:::+)\s*$', l)
                if close_m:
                    close_len = len(close_m.group(1))
                    if fence_stack and close_len >= fence_stack[-1]:
                        fence_stack.pop()
                        if not fence_stack:
                            i += 1
                            break
                        else:
                            inner.append(l)
                    else:
                        inner.append(l)
                elif open_m:
                    fence_stack.append(len(open_m.group(1)))
                    inner.append(l)
                else:
                    hm = re.match(r'^#{1,4}\s+(.+)$', l)
                    if hm and title_override is None and callout_type:
                        title_override = hm.group(1).strip()
                    else:
                        inner.append(l)
                i += 1

            inner_text = '\n'.join(inner).strip()

            # Lógica de Renderização:
            if callout_type:
                # Renderiza como blockquote Markdown nativo (> )
                # Compativel com VSCode, JupyterLab e Colab: aceita $...$ e $$...$$
                emoji, default_title = CALLOUT_STYLE[callout_type]
                title = title_override or default_title
                # Prefixa cada linha do conteudo interno com "> "
                inner_lines = inner_text.splitlines()
                inner_quoted = '\n'.join(
                    ('> ' + l) if l.strip() else '>'
                    for l in inner_lines
                )
                block = (
                    f'> ### {emoji} {title}\n'
                    f'>\n'
                    f'{inner_quoted}'
                )
                out.append(block)

            elif group_id_m and has_layout:
                elem_id = group_id_m.group(1)
                info = elem_map.get(elem_id)
                
                # 1. Quebra o conteúdo interno pelos blocos ::: das subfiguras
                subblocks = re.split(r':::+\s*\{#(?:fig|tbl)-[\w-]+\}', inner_text)
                # Remove o primeiro elemento se estiver vazio (texto antes da primeira subfigura)
                subblocks = [b for b in subblocks if b.strip()]

                # 2. Identifica a legenda principal (última parte do texto fora dos blocos)
                # Geralmente está após o último ::: das subfiguras
                main_caption = ""
                last_parts = subblocks[-1].split(':::')
                if len(last_parts) > 1:
                    main_caption = last_parts[-1].strip()
                    # Remove a legenda principal do último bloco de subfigura
                    subblocks[-1] = last_parts[0]

                cols_html = ""
                for idx, block in enumerate(subblocks):
                    # Extrai o caminho da imagem
                    img_m = re.search(r'!\[.*?\]\(([^)]+)\)', block)
                    # Extrai o texto (sublegenda): remove a linha da imagem e as cercas :::
                    sub_text = re.sub(r'!\[.*?\]\([^)]+\)(?:\{.*?\})?', '', block)
                    sub_text = sub_text.replace(':::', '').strip()
                    
                    if img_m:
                        path = img_m.group(1).strip()
                        label_prefix = f'({chr(ord("a") + idx)})'
                        cols_html += (
                            f'<td style="text-align:center; border:none; padding:4px;">'
                            f'<img src="{path}" style="width:100%;" />'
                            f'<br/><small>{label_prefix} {sub_text}</small>'
                            f'</td>'
                        )
                
                if cols_html and info:
                    block = (
                        f'<figure id="{elem_id}" style="text-align:center; margin:1em 0;">\n'
                        f'  <table style="width:100%; border:none;"><tr style="border:none;">{cols_html}</tr></table>\n'
                        f'  <figcaption><strong>{info["label_prefix"]}</strong> {main_caption}</figcaption>\n'
                        f'</figure>'
                    )
                    out.append(block)
                else:
                    out.append(inner_text)
            
            elif group_id_m and not has_layout:
                elem_id = group_id_m.group(1)
                kind    = elem_id.split('-')[0]
                info    = elem_map.get(elem_id)
                subfig_ids = re.findall(r'^:::+\s*\{#((fig|tbl)-[\w-]+)', inner_text, re.MULTILINE)

                if subfig_ids:
                    inner_lines = inner_text.split('\n')
                    caption = ""
                    body_end = len(inner_lines)
                    for idx in range(len(inner_lines) - 1, -1, -1):
                        s = inner_lines[idx].strip()
                        if s and not s.startswith(':::') and not s.startswith('!'):
                            caption = s
                            body_end = idx
                            break
                    for sub_idx, (sub_id, _) in enumerate(subfig_ids):
                        if sub_id in elem_map and elem_map[sub_id].get("is_subfig"):
                            elem_map[sub_id]["label_prefix"] = f'({chr(ord("a") + sub_idx)})'
                    inner_body = '\n'.join(inner_lines[:body_end])
                    processed_inner = convert_callouts(inner_body, elem_map)
                    if info:
                        lp = info.get("label_prefix") or (info.get("label", "") + ":")
                        if not lp.endswith(":"):
                            lp += ":"
                        block = (
                            f'<figure id="{elem_id}" style="text-align:center; margin:1em 0;">\n'
                            f'  {processed_inner}\n'
                            f'  <figcaption><strong>{lp}</strong> {caption}</figcaption>\n'
                            f'</figure>'
                        )
                        out.append(block)
                    else:
                        out.append(processed_inner)
                else:
                    img_m = re.search(r'!\[([^\]]*)\]\(([^)]+)\)', inner_text)
                    caption_lines = [
                        l.strip() for l in inner_text.split('\n')
                        if l.strip() and not l.strip().startswith('!')
                    ]
                    caption = caption_lines[-1] if caption_lines else ""
                    if img_m and info:
                        img_alt  = img_m.group(1)
                        img_path = img_m.group(2)
                        lp = info.get("label_prefix") or info.get("label", "")
                        is_subfig = info.get("is_subfig", False)
                        if not is_subfig and lp and not lp.endswith(":"):
                            lp += ":"
                        img_tag = f'<img src="{img_path.strip()}" alt="{img_alt}" style="max-width:60%; display:block; margin:auto;" />'
                        figcap  = f'<figcaption><strong>{lp}</strong> {caption}</figcaption>'
                        body = img_tag + "\n  " + figcap if kind != "tbl" else figcap + "\n  " + img_tag
                        block = f'<figure id="{elem_id}" style="text-align:center; margin:1em 0;">\n  {body}\n</figure>'
                        out.append(block)
                    else:
                        if inner_text:
                            out.append(inner_text)

                
            elif ".text-center" in attrs:
                # Suporte para centralização
                block = f'<div style="text-align:center;">\n\n{inner_text}\n\n</div>'
                out.append(block)

            elif has_layout and not group_id_m:
                # layout-ncol=N sem ID de grupo: divide tabelas Markdown em colunas HTML
                # Ex: ::: {layout-ncol=4} com 4 tabelas Markdown
                ncol_m = re.search(r'layout-ncol\s*=\s*(\d+)', attrs)
                ncols = int(ncol_m.group(1)) if ncol_m else 2

                # Separa o inner_text em blocos de tabela individuais
                # Cada tabela começa com uma linha que começa com '|'
                # e pode ter legenda ': Título {#tbl-...}' após
                tbl_block_re = re.compile(
                    r'((?:[ \t]*\|[^\n]+\n)+'           # linhas da tabela
                    r'(?:\n?[ \t]*: [^\n{]*\{#tbl-[\w-]+[^}]*\})?'  # legenda Quarto opcional
                    r'(?:\n?[ \t]*\{#tbl-[\w-]+[^}]*\})?)',          # legenda antiga opcional
                    re.MULTILINE
                )
                tbl_blocks = tbl_block_re.findall(inner_text)

                if tbl_blocks:
                    # Monta uma linha de <td> para cada tabela
                    col_width = f"{100 // ncols}%"
                    cells_html = ""
                    for tbl_src in tbl_blocks:
                        tbl_src = tbl_src.strip()
                        # Extrai legenda e id, se existirem
                        cap_m = re.search(
                            r'\n?[ \t]*: ([^\n{]*?)\s*\{#(tbl-[\w-]+)[^}]*\}', tbl_src)
                        if cap_m:
                            cap_text = cap_m.group(1).strip()
                            tbl_id   = cap_m.group(2)
                            tbl_src  = tbl_src[:cap_m.start()].strip()
                        else:
                            old_m = re.search(r'\{#(tbl-[\w-]+)[^}]*\}', tbl_src)
                            tbl_id   = old_m.group(1) if old_m else None
                            cap_text = ""
                            if old_m:
                                tbl_src = tbl_src[:old_m.start()].strip()

                        # info = elem_map.get(tbl_id) if tbl_id else None
                        # if info:
                        #     cap_label = f'<strong>{info["label_prefix"]}</strong> {cap_text}' if cap_text else f'<strong>{info["label_prefix"]}</strong>'
                        #     anchor    = f'<a id="{tbl_id}"></a>\n'
                        # else:
                        #     cap_label = f'<strong>{cap_text}</strong>' if cap_text else ""
                        #     anchor    = f'<a id="{tbl_id}"></a>\n' if tbl_id else ""

                        # Resolve @tbl-* @fig-* na legenda ANTES de montar o HTML
                        cap_text = resolve_crossrefs_to_html(cap_text, elem_map)

                        info = elem_map.get(tbl_id) if tbl_id else None
                        if info:
                            cap_label = f'<strong>{info["label_prefix"]}</strong> {cap_text}' if cap_text else f'<strong>{info["label_prefix"]}</strong>'
                            anchor    = f'<a id="{tbl_id}"></a>\n'
                        else:
                            cap_label = f'<strong>{cap_text}</strong>' if cap_text else ""
                            anchor    = f'<a id="{tbl_id}"></a>\n' if tbl_id else ""

                        cap_html = f'<div style="text-align:left; font-size:0.9em; margin-bottom:4px;">{cap_label}</div>' if cap_label else ""
                        cells_html += (
                            f'<td style="vertical-align:top; padding:4px; width:{col_width}; border:none;">'
                            f'{anchor}{cap_html}\n\n{tbl_src}\n\n'
                            f'</td>\n'
                        )

                    block = (
                        f'<table style="width:100%; border:none; border-collapse:collapse;">'
                        f'<tr style="border:none;">\n{cells_html}</tr></table>'
                    )
                    out.append(block)
                else:
                    # Sem tabelas reconhecíveis: fallback ao conteúdo processado
                    if inner_text:
                        processed = convert_callouts(inner_text, elem_map)
                        out.append(processed)

            else:
                # Div genérico (ex: layout="[[1,1]]"): processa sub-blocos ::: recursivamente
                # O restante (tabelas, imagens) será processado pelas etapas seguintes do process_cell
                if inner_text:
                    processed = convert_callouts(inner_text, elem_map)
                    out.append(processed)
        else:
            out.append(line)
            i += 1

    return '\n'.join(out)

# ---------------------------------------------------------------------------
# 6. Extrai label -> numero de todos os elementos do notebook
# ---------------------------------------------------------------------------

def _chapter_from_id(label_id: str) -> str:
    """Extrai o numero do capitulo do id: fig-1-X -> '1', eq-2-3 -> '2', tbl-X -> ''"""
    m = re.match(r'(?:fig|tbl|eq|sec|lst)-(\d+)', label_id)
    return m.group(1) if m else ""

# No início do arquivo, após as definições, adicione uma função de reset
def reset_section_numbering():
    """Reseta o contador de seções para um novo notebook."""
    global _section_numbering
    _section_numbering.reset()

def extract_chapter_number(notebook: dict) -> str:
    """
    Extrai o número do capítulo do marcador <!-- cap X --> no início do notebook.
    Retorna "1" como padrão se não encontrar.
    """
    for cell in notebook.get("cells", []):
        if cell.get("cell_type") == "markdown":
            source = source_to_str(cell.get("source", []))
            # Procura por <!-- cap X --> no início do texto
            m = re.search(r'<!--\s*cap\s+(\d+)\s*-->', source, re.IGNORECASE)
            if m:
                print(f"  📖 Marcador de capítulo encontrado: {m.group(1)}")
                return m.group(1)
            # Se não encontrar o marcador, procura por "Capítulo X"
            m = re.search(r'^#\s+Cap[ií]tulo\s+(\d+)', source, re.MULTILINE | re.IGNORECASE)
            if m:
                print(f"  📖 Capítulo detectado pelo título: {m.group(1)}")
                return m.group(1)
    print(f"  ⚠ Capítulo não detectado, usando padrão: 1")
    return "1"

def build_element_map(notebook: dict) -> dict:
    """
    Varre o notebook e cria um mapa unificado de todos os elementos numerados.
    """
    # 🔧 RESETA O CONTADOR GLOBAL no início
    global _section_numbering
    _section_numbering.reset()
    
    # 🔧 Extrai o número do capítulo do marcador
    current_chapter = extract_chapter_number(notebook)
    
    # Ajusta o contador para o capítulo correto (capítulo 1 = contador 1)
    _section_numbering.numbers['chapter'] = int(current_chapter) - 2
    
    counters = {"fig": 0, "tbl": 0, "eq": 0}
    elem_map = {}

    def make_num_str(kind: str, elem_id: str) -> str:
        """Gera num_str incremental: '<capitulo>.<contador>'."""
        counters[kind] += 1
        # Extrai número do capítulo do elem_id ou usa o atual
        chap = _chapter_from_id(elem_id)
        if not chap or chap == '':
            chap = current_chapter
        return f"{chap}.{counters[kind]}"

    prefixes = {
        "fig": "Figura",
        "tbl": "Tabela",
        "eq":  "Equacao",
    }

    for cell in notebook.get("cells", []):
        if cell.get("cell_type") != "markdown":
            if cell.get("cell_type") == "code":
                src = source_to_str(cell.get("source", []))
                label_m = re.search(r'#\|\s*label:\s*((fig|tbl)-[\w-]+)', src)
                caption_m = re.search(r'#\|\s*(?:tbl-cap|fig-cap):\s*["\']([^"\']+)["\']', src)
                if label_m:
                    elem_id = label_m.group(1)
                    kind = label_m.group(2)
                    caption = caption_m.group(1) if caption_m else ""
                    if elem_id not in elem_map:
                        num_str = make_num_str(kind, elem_id)
                        elem_map[elem_id] = {
                            "kind": kind,
                            "num_str": num_str,
                            "label": f"{prefixes[kind]} {num_str}",
                            "caption": caption,
                            "from_code": True,
                            "alt": None,
                            "path": None,
                            "content": None,
                        }
            continue
        
        source = source_to_str(cell.get("source", []))
        
        # Detecção de blocos ::: {#fig-ID}
        for m in re.finditer(r'^:::+\s*\{#((fig|tbl)-[\w-]+)[^}]*\}', source, re.MULTILINE):
            elem_id = m.group(1)
            kind = m.group(2)
            if elem_id not in elem_map:
                is_subfig = bool(re.search(r'\d[a-z]$', elem_id))
                if is_subfig:
                    parent_id = elem_id[:-1]
                    parent_info = elem_map.get(parent_id)
                    parent_num = parent_info["num_str"] if parent_info else _chapter_from_id(elem_id)
                    sub_num_str = f"{parent_num}{elem_id[-1]}" if parent_num else elem_id
                    elem_map[elem_id] = {
                        "kind": kind,
                        "is_subfig": True,
                        "num_str": sub_num_str,
                        "label_prefix": None,
                        "caption": "",
                        "from_group": True
                    }
                else:
                    num_str = make_num_str(kind, elem_id)
                    prefix = "Figura" if kind == "fig" else "Tabela"
                    elem_map[elem_id] = {
                        "kind": kind,
                        "num_str": num_str,
                        "label_prefix": f"{prefix} {num_str}:",
                        "caption": "",
                        "from_group": True
                    }
        
        # Figuras e tabelas-imagem
        source_no_div = re.sub(r':::.*?:::', '', source, flags=re.DOTALL)
        for m in IMG_DEF_RE.finditer(source_no_div):
            alt = m.group(1)
            path = m.group(2)
            elem_id = m.group(3)
            kind = m.group(4)
            if elem_id not in elem_map:
                num_str = make_num_str(kind, elem_id)
                elem_map[elem_id] = {
                    "kind": kind,
                    "num_str": num_str,
                    "label": f"{prefixes[kind]} {num_str}",
                    "alt": alt,
                    "path": path,
                    "content": None,
                }
        
        # Tabelas Markdown
        for m in TBL_MD_RE.finditer(source):
            tbl_body = m.group(1)
            tbl_caption = (m.group(2) or "").strip()
            elem_id = m.group(3) or m.group(4)
            if elem_id and elem_id not in elem_map:
                num_str = make_num_str("tbl", elem_id)
                elem_map[elem_id] = {
                    "kind": "tbl",
                    "num_str": num_str,
                    "label_prefix": f"Tabela {num_str}:",
                    "caption": tbl_caption,
                    "content": tbl_body.rstrip(),
                }
        
        # Equações
        for m in EQ_DEF_RE.finditer(source):
            eq_body = m.group(1)
            elem_id = m.group(2)
            if elem_id not in elem_map:
                num_str = make_num_str("eq", elem_id)
                elem_map[elem_id] = {
                    "kind": "eq",
                    "num_str": num_str,
                    "label": f"Equacao {num_str}",
                    "alt": None,
                    "path": None,
                    "content": eq_body,
                }
    
    return elem_map


# ---------------------------------------------------------------------------
# 7. Renderers HTML para cada tipo
# ---------------------------------------------------------------------------

def render_img_element(alt: str, path: str, elem_id: str, label: str, kind: str = "fig") -> str:
    """Figura ou tabela-imagem -> <figure> com ancora e legenda.
    Tabelas: legenda acima da imagem. Figuras: legenda abaixo.
    """
    caption = f'  <figcaption><strong>{label}:</strong> {alt}</figcaption>\n'
    img     = f'  <img src="{path}" alt="{alt}" style="max-width:80%" />\n'
    if kind == "tbl":
        body = caption + img
    else:
        body = img + caption
    return f'<figure id="{elem_id}">\n' + body + '</figure>'

def render_figure_group(content: str, elem_id: str, label_prefix: str, caption: str) -> str:
    """
    Renderiza um grupo de imagens em colunas (layout-ncol=2) com uma única legenda.
    """
    # Tenta extrair as imagens do conteúdo original para colocá-las em uma tabela HTML
    img_find = re.findall(r'!\[.*?\]\((.*?)\)\{.*?width=(.*?)\%?\}', content)
    
    if img_find:
        cols_html = ""
        for path, width in img_find:
            cols_html += f'<td style="text-align:center;"><img src="{path}" style="width:{width}%" /></td>'
        
        table_html = f'<table style="width:100%; border:none;"><tr style="border:none;">{cols_html}</tr></table>'
        
        return (
            f'<figure id="{elem_id}" style="text-align:center;">\n'
            f'  {table_html}\n'
            f'  <figcaption style="margin-top:10px;"><strong>{label_prefix}</strong> {caption}</figcaption>\n'
            f'</figure>'
        )
    return content # Caso não consiga processar, retorna o original

def render_tbl_markdown(tbl_body: str, elem_id: str, label_prefix: str, caption: str) -> str:
    """
    Renderiza a tabela no Colab com prefixo em negrito e 
    permite LaTeX/Links na legenda.
    """
    # Monta a legenda: apenas o prefixo em negrito
    full_caption = f"**{label_prefix}** {caption}" if caption else f"**{label_prefix}**"
    
    # <a> invisível para o link de referência, legenda em Markdown e a tabela
    return (
        f'<a id="{elem_id}"></a>\n\n'
        f'{full_caption}\n\n'
        f'{tbl_body}\n'
    )

def render_equation(eq_body: str, elem_id: str, num_str: str) -> str:
    """
    Equacao LaTeX -> Renderiza com numero (X.Y) alinhado a direita usando \tag.
    Esta abordagem e a mais estável para Google Colab e Jupyter.
    """
    # Remove os $$ externos para limpar o conteúdo
    inner = eq_body.strip()
    if inner.startswith("$$") and inner.endswith("$$"):
        inner = inner[2:-2].strip()

    # Mantém a sua lógica de conversão de cores
    inner = re.sub(r'\\textcolor\{([^}]+)\}\{([^}]+)\}', r'{\\color{\1}{\2}}', inner)

    # Usa \tag para a numeração e \label para permitir links internos
    # O <a> invisível serve como âncora para referências cruzadas @eq-*
    return (
        f'<a id="{elem_id}"></a>\n'
        f'$$\n{inner} \\tag{{{num_str}}}\n$$\n'
    )

# ---------------------------------------------------------------------------
# 8. Processa uma celula: substitui definicoes e referencias
# ---------------------------------------------------------------------------

def fix_textcolor_inline(text: str) -> str:
    # 1. Protege blocos de equações para não misturar Markdown/HTML lá dentro
    placeholders = {}
    def hide_math(m):
        key = f"\x00MATH{len(placeholders)}\x00"
        body = m.group(0)
        
        # Dentro da equação, apenas corrigimos \textcolor para \color
        # e garantimos que \textbf continue sendo LaTeX
        body = re.sub(
            r'\\textcolor\{([^}]+)\}\{([^}]+)\}',
            r'{\\color{\1}{\2}}',
            body
        )
        # Opcional: converter \textbf para \mathbf se quiser negrito matemático
        # body = body.replace(r'\textbf', r'\mathbf')
        
        placeholders[key] = body
        return key
    
    # Esconde equações $...$ e $$...$$
    text = re.sub(r'\$\$[\s\S]*?\$\$', hide_math, text)
    text = re.sub(r'\$[^\$\n]+\$', hide_math, text)

    # NOVO: Tratar badges/botões com links e width (ex: Colab/GitHub)
    # Transforma [![](img){width="16%"}] -> [<img src="img" width="16%">]
    text = re.sub(
        r'\[\!\[\]\(([^)]+)\)\{width="([^"]+)"\}\] \(([^)]+)\)',
        r'<a href="\3"><img src="\1" style="width:\2; vertical-align:middle;"></a>',
        text
    )
    
    # Caso o badge não tenha link, apenas limpa a sintaxe de width para HTML
    text = re.sub(
        r'\!\[\]\(([^)]+)\)\{width="([^"]+)"\}',
        r'<img src="\1" style="width:\2; vertical-align:middle;">',
        text
    )

    # 2. Agora aplica as conversões APENAS no texto Markdown (fora das equações)
    # \textcolor{cor}{texto} -> <font color="cor">texto</font>
    text = re.sub(
        r'\\textcolor\{([^}]+)\}\{((?:[^{}]|\{[^{}]*\})*)\}',
        r'<font color="\1">\2</font>',
        text
    )

    # [texto]{style="color: X;"} -> <font color="X">texto</font>
    text = re.sub(
        r'\[([^\]]+)\]\{style="color:\s*([^;}"]+);?"\}',
        r'<font color="\2">\1</font>',
        text
    )

    # \textbf{texto} para **texto** (APENAS fora de equações)
    text = re.sub(r'\\textbf\{((?:[^{}]|\{[^{}]*\})*)\}', r'**\1**', text)

    # 3. Restaura as equações intactas
    for key, val in placeholders.items():
        text = text.replace(key, val)
        
    return text

def process_cell(source, key_to_num: dict, elem_map: dict, bib: dict, numbering: bool = True) -> list:
    """
    Aplica em ordem:
      1. Numeração de seções (capítulos, seções, subseções) - se numbering=True
      2. Equações
      3. Tabelas
      4. Imagens
      5. Referências cruzadas
      6. Citações bibliográficas
    """
    text = source_to_str(source)

    # --- NUMERAÇÃO DE SEÇÕES (condicional) ---
    if numbering:
        lines = text.splitlines()
        new_lines = []
        in_code_block = False
        
        for line in lines:
            # Detecta blocos de código
            if line.strip().startswith('```'):
                in_code_block = not in_code_block
                new_lines.append(line)
                continue
            
            # Detecta headings Markdown
            heading_match = re.match(r'^(#{1,6})\s+(.+)$', line)
            if heading_match:
                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()
                
                # Ignora headings que já possuem {.unnumbered} ou estão dentro de callouts
                if '{.unnumbered}' in title:
                    new_lines.append(line)
                    continue
                
                # Remove atributos Quarto do título para numeração limpa
                title_clean = re.sub(r'\s*\{[^}]*\}\s*$', '', title)
                if heading_match:
                    level = len(heading_match.group(1))
                    title = heading_match.group(2).strip()
                    
                    # Remove o marcador <!-- cap X --> se estiver na mesma linha
                    title = re.sub(r'<!--\s*cap\s+\d+\s*-->', '', title)
                    
                    # Remove qualquer numeração existente
                    title = re.sub(r'^\d+(?:\.\d+)*\s+', '', title)
                    # Remove "Capítulo X" ou "Capítulo X -" ou "Capítulo X –"
                    title = re.sub(r'^Cap[ií]tulo\s+\d+\s*[-–]?\s*', '', title, flags=re.IGNORECASE)
                    
                    # Adiciona numeração baseada no nível
                    if level == 1:  # Capítulo
                        num = _section_numbering.inc_chapter()
                        numbered_title = f"{num} {title}"
                    elif level == 2:  # Seção
                        num = _section_numbering.inc_section()
                        numbered_title = f"{num} {title}"
                    elif level == 3:  # Subseção
                        num = _section_numbering.inc_subsection()
                        numbered_title = f"{num} {title}"
                    elif level == 4:  # Subsubseção
                        num = _section_numbering.inc_subsubsection()
                        numbered_title = f"{num} {title}"
                    else:
                        numbered_title = title
                    
                    new_lines.append('#' * level + ' ' + numbered_title)
                    continue
            
            new_lines.append(line)
        
        text = '\n'.join(new_lines)
    
    # Remove tags de pagebreak
    text = re.sub(r'\{\{<\s*pagebreak\s*>\}\}\n?', '', text)

    # 0. Converte callouts e divs Quarto (::: {.callout-*} ... :::)
    text = convert_callouts(text, elem_map)

    # 0c. textcolor inline (fora de $$)
    text = fix_textcolor_inline(text)

    # 0b. Remove APENAS atributos Quarto ({.class} ou {#id}), ignorando comandos LaTeX
    text = re.sub(r'(#{1,6}[^\n]+?)\s*\{([.#][^}]*)\}', r'\1', text)

    # 1b. Converte \textcolor em \color em TODO bloco $$, numerado ou não
    def fix_textcolor(m):
        body = m.group(0)
        return re.sub(
            r'\\textcolor\{([^}]+)\}\{([^}]+)\}',
            r'{\\color{\1}{\2}}',
            body
        )
    text = re.sub(r'\$\$[\s\S]*?\$\$', fix_textcolor, text)

    # 1. Equacoes
    def replace_eq(m):
        eq_body = m.group(1)
        elem_id = m.group(2)
        info = elem_map.get(elem_id)
        if info:
            num_str = info["num_str"]
        else:
            num_str = _chapter_from_id(elem_id) or elem_id
        return render_equation(eq_body, elem_id, num_str)

    text = EQ_DEF_RE.sub(replace_eq, text)

    # 2. Tabelas Markdown 
    def replace_tbl_md(m):
        tbl_body = m.group(1).rstrip()
        elem_id  = m.group(3) or m.group(4)
        info = elem_map.get(elem_id)
        if info:
            return render_tbl_markdown(tbl_body, elem_id, info["label_prefix"], info["caption"])
        else:
            return render_tbl_markdown(tbl_body, elem_id, f"Tabela {_chapter_from_id(elem_id)}:", "")
        
    text = TBL_MD_RE.sub(replace_tbl_md, text)

    # 3. Imagens (fig e tbl-imagem)
    def replace_img(m):
        alt     = m.group(1)
        path    = m.group(2)
        elem_id = m.group(3)
        kind    = m.group(4)  # "fig" ou "tbl"
        info = elem_map.get(elem_id)
        label = info["label"] if info else \
            ("Figura" if kind == "fig" else "Tabela") + \
            f" {_chapter_from_id(elem_id) or elem_id}"
        return render_img_element(alt, path, elem_id, label, kind)

    text = IMG_DEF_RE.sub(replace_img, text)

    def _num_str_for(elem_id: str) -> str:
        """Retorna o num_str do elemento ou fallback."""
        info = elem_map.get(elem_id)
        if info:
            return info.get("num_str") or elem_id
        return _chapter_from_id(elem_id) or elem_id

    def _prefix_for(elem_id: str) -> str:
        """Retorna o prefixo textual (Figura/Tabela/Equação)."""
        info = elem_map.get(elem_id)
        kind_raw = info["kind"] if info else elem_id.split('-')[0]
        return "Tabela" if kind_raw == "tbl" else \
            "Figura" if kind_raw == "fig" else "Equação"

    def replace_crossref_bracket(m):
        """[-@id] -> numero so;  [Texto @id] -> Texto numero."""
        inner = m.group(1)
        id_m = re.search(r'@((fig|tbl|eq)-[\w-]+)', inner)
        if not id_m:
            return m.group(0)
        elem_id = id_m.group(1)
        num = _num_str_for(elem_id)
        prefix_text = inner[:id_m.start()].strip().lstrip('-').strip()
        if prefix_text:
            label_curto = f"{prefix_text} {num}"
        else:
            label_curto = num
        return f"[{label_curto}](#{elem_id})"

    def replace_crossref_bare(m):
        """@id isolado (fora de []) -> [Figura/Tabela/Equação X.Y](#id)."""
        elem_id = m.group(1)
        if CROSSREF_RE.match(elem_id):
            num = _num_str_for(elem_id)
            prefix = _prefix_for(elem_id)
            return f"[{prefix} {num}](#{elem_id})"
        return m.group(0)

    # Primeiro: colchetes com @
    text = re.sub(r'\[([^\]]*@(?:fig|tbl|eq)-[\w-]+[^\]]*)\]',
                  replace_crossref_bracket, text)
    # Depois: @id isolado
    text = re.sub(r'(?<!\[)@((fig|tbl|eq)-[\w-]+)', replace_crossref_bare, text)

    # 5. Citacoes bibliograficas
    def _fmt_key(key: str, mode: str) -> str:
        key = key.strip().lstrip("@")
        if key not in bib:
            return f"?{key}"
        if mode == "direct":
            return cite_direct(bib[key])
        else:
            return cite_indirect(bib[key])

    def replace_indirect(m):
        inner = m.group(1)
        keys = [k.strip() for k in re.split(r'[;,]', inner)]
        parts = []
        for k in keys:
            k = k.lstrip("@").strip()
            if not k:
                continue
            if k not in bib:
                parts.append(f"?{k}")
                continue
            fields = bib[k]
            year = fields.get("year", "s.d.")
            surnames = _last_names(fields.get("author", ""))
            upper = [s.upper() for s in surnames]
            if not upper:
                parts.append(f"({year})")
            elif len(upper) == 1:
                parts.append(f"{upper[0]}, {year}")
            elif len(upper) == 2:
                parts.append(f"{upper[0]}; {upper[1]}, {year}")
            else:
                parts.append(f"{upper[0]} et al., {year}")
        return "(" + "; ".join(parts) + ")"

    def replace_direct(m):
        key = m.group(1)
        if key.upper() in ["RELATION", "ATTRIBUTE", "DATA"]:
            return "@" + key
        if CROSSREF_RE.match(key):
            return m.group(0)
        return _fmt_key(key, "direct")
    
    # Protege \@palavra
    ESCAPED_AT = "\x00ESCAPED_AT\x00"
    text = re.sub(r'\\@([\w:-]+)', lambda m: f'{ESCAPED_AT}{m.group(1)}', text)

    text = re.sub(r'\[@([\w:;@\s,-]+)\]', replace_indirect, text)
    text = re.sub(r'(?<!\[)@([\w:-]+)', replace_direct, text)

    # Footnotes
    footnote_defs = {}
    def extract_fn(m):
        fn_id = m.group(1)
        content = m.group(2).strip()
        content = md_inline_to_html(content)
        footnote_defs[fn_id] = content
        return ""

    text = re.sub(r'^\[\^([^\]]+)\]:\s*(.*?)(?=\n\[\^|\n\n|\Z)', extract_fn, text, flags=re.MULTILINE | re.DOTALL)

    def replace_fn_ref(m):
        fn_id = m.group(1)
        return f'<sup title="{fn_id}">[{fn_id}]</sup>'
    
    text = re.sub(r'\[\^([^\]]+)\]', replace_fn_ref, text)

    if footnote_defs:
        notes_html = '<hr><div style="font-size: 0.85em; color: #555;"><strong>Notas:</strong><br>\n'
        for fn_id, content in footnote_defs.items():
            content = content.replace('\n', ' ')
            notes_html += f'[{fn_id}] {content}<br>\n'
        notes_html += '</div>'
        text += "\n\n" + notes_html

    text = text.replace(ESCAPED_AT, '@')
    return str_to_source(text)


# ---------------------------------------------------------------------------
# 9. Extrai citacoes bibliograficas (exclui cross-refs)
# ---------------------------------------------------------------------------
def extract_citations(notebook: dict) -> list:
    seen, ordered = set(), []
    # Captura @key mas NÃO precedido de \ (ex: \@relation é escape Quarto, não citação)
    cite_re = re.compile(r'(?<!\\)@([\w:-]+)')
    escaped_re = re.compile(r'\\@[\w:-]+')    # \@palavra — escape Quarto, nao e citacao

    for cell in notebook.get("cells", []):
        if cell.get("cell_type") != "markdown":
            continue
        source = source_to_str(cell.get("source", []))
        # Remove ocorrencias escapadas antes de buscar citacoes
        source_clean = escaped_re.sub('', source)
        
        for m in cite_re.finditer(source_clean):
            key = m.group(1)
            if CROSSREF_RE.match(key):
                continue
            if key not in seen:
                seen.add(key)
                ordered.append(key)
    return ordered

def extract_image_paths(notebook: dict) -> list:
    found = set()
    md_img_re = re.compile(r'!\[.*?\]\(([^)\s"\']+)', re.DOTALL)

    html_img_re = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']')
    for cell in notebook.get("cells", []):
        if cell.get("cell_type") != "markdown":
            continue
        source = source_to_str(cell.get("source", []))
        for m in md_img_re.finditer(source):
            found.add(m.group(1))
        for m in html_img_re.finditer(source):
            found.add(m.group(1))
    return sorted(p for p in found if not re.match(r'https?://|data:', p))




# ---------------------------------------------------------------------------
# 10. Limpeza do notebook para distribuicao
# ---------------------------------------------------------------------------

# Padrao para detectar celulas de secao de referencias do Quarto
REF_SECTION_RE = re.compile(
    r'##\s+Refer[eê]ncias?\s+(do\s+)?Cap[ií]tulo|'
    r'##\s+Refer[eê]ncias?\s+Bibliogr[aá]ficas?',
    re.IGNORECASE
)


def clean_notebook(notebook: dict) -> dict:
    """
    Limpa o notebook para distribuicao aos alunos:
      - Remove metadados 'quarto' do notebook
      - Remove celulas raw YAML (--- ... ---)
      - Remove celulas de codigo vazias
      - Remove celulas de secao de referencias antiga
      - Remove marcadores <!-- cap X -->
    """
    # Remove metadados quarto
    meta = notebook.get("metadata", {})
    for key in ("quarto", "quarto-version"):
        meta.pop(key, None)

    cleaned = []
    removed = {
        "yaml": 0,
        "empty_code": 0,
        "ref_section": 0,
        "quarto_params": 0,
        "html_only": 0,
        "markers": 0,  # NOVO: conta marcadores removidos
    }

    # Rastreia se estamos dentro de um bloco html-only
    inside_html_only = False

    for cell in notebook.get("cells", []):
        src = source_to_str(cell.get("source", []))
        kind = cell.get("cell_type", "")

        # 🔧 NOVO: Remove células que contêm apenas o marcador <!-- cap X -->
        if kind == "markdown":
            stripped = src.strip()
            if re.match(r'<!--\s*cap\s+\d+\s*-->', stripped):
                removed["markers"] += 1
                continue    

        # Detecta delimitadores ::: {.content-visible when-format="html"} e :::
        # As células markdown delimitadoras são removidas (não fazem sentido no Colab).
        # As células de código DENTRO do bloco são mantidas: o output (botão HTML)
        # deve aparecer no Colab; o código é ocultado via echo:false / cellView:form.
        if kind == "markdown":
            src_stripped = src.strip()
            if re.match(r'^:::\s*\{[^}]*content-visible[^}]*when-format=["\']html["\'][^}]*\}', src_stripped):
                inside_html_only = True
                removed["html_only"] += 1
                continue   # remove a célula delimitadora de abertura
            if inside_html_only and re.match(r'^:::\s*$', src_stripped):
                inside_html_only = False
                removed["html_only"] += 1
                continue   # remove a célula delimitadora de fechamento
            # Células markdown comuns dentro do bloco (ex: instruções "Utilize o botão...")
            # também são removidas — são instruções só para HTML/PDF, não para Colab
            if inside_html_only:
                removed["html_only"] += 1
                continue

        # Limpa parâmetros Quarto e injeta tag de ocultar no Colab
        if kind == "code":
            lines = src.splitlines(keepends=True)
            
            # 1. Verifica se deve esconder (echo: false)
            #should_hide = any("echo: false" in l for l in lines)
            has_output = bool(cell.get("outputs"))
            should_hide = any("echo: false" in l for l in lines) and has_output
            
            # 2. Filtra: remove linhas #| E remove qualquer # @title que já exista
            # para evitar a duplicação que você observou
            new_lines = [
                l for l in lines 
                if not l.strip().startswith("#|") and 
                not l.strip().startswith("# @title")
            ]
            
            # 3. Se houve limpeza de parâmetros Quarto
            if len(new_lines) != len(lines):
                removed["quarto_params"] += 1
                
                # Une as linhas e remove linhas em branco do topo
                src = "".join(new_lines).lstrip('\n').lstrip('\r')
                
                # 4. Injeta a tag apenas UMA vez se for echo: false
                if should_hide:
                    src = "# @title { display-mode: \"form\" }\n" + src
                
                cell["source"] = str_to_source(src)
                
                # 5. Ajusta metadados para garantir que o Colab oculte
                if should_hide:
                    if "metadata" not in cell: cell["metadata"] = {}
                    cell["metadata"]["cellView"] = "form"
                    cell["metadata"]["jupyter"] = {"source_hidden": True}

        # Celulas raw YAML (--- ... ---)
        if kind == "raw" and src.strip().startswith("---"):
            removed["yaml"] += 1
            continue

        # Celulas de codigo vazias
        if kind == "code" and not src.strip():
            removed["empty_code"] += 1
            continue

        # Secao de referencias antiga (sera substituida pela injetada)
        if kind == "markdown" and REF_SECTION_RE.search(src):
            removed["ref_section"] += 1
            # Guarda o parágrafo introdutório (linhas que não são ## título nem \printbibliography)
            intro_lines = [
                l for l in src.splitlines()
                if l.strip()
                and not REF_SECTION_RE.match(l.strip())
                and not l.strip().startswith("\\printbibliography")
                and not l.strip().startswith("\\")
            ]
            notebook["_ref_intro"] = "\n".join(intro_lines)
            continue

        cleaned.append(cell)

    notebook["cells"] = cleaned

    if any(removed.values()):
        parts = []
        if removed["yaml"]:        parts.append(f"{removed['yaml']} celulas YAML")
        if removed["empty_code"]:  parts.append(f"{removed['empty_code']} cod.vazias")
        if removed["ref_section"]: parts.append(f"{removed['ref_section']} secoes-ref antigas")
        if removed["html_only"]:   parts.append(f"{removed['html_only']} celulas html-only")
        print(f"  Limpeza: removidas {', '.join(parts)}")
        
    return notebook

# ---------------------------------------------------------------------------
# 11. Lista de referencias bibliograficas
# ---------------------------------------------------------------------------
def build_reference_list(citations: list, bib: dict, intro_paragraph: str = "") -> tuple:
    """
    Constrói a lista de referências ordenada alfabeticamente pelo 
    sobrenome do primeiro autor ou pelo título.
    """
    # 1. Filtra as chaves que realmente existem no arquivo .bib
    valid_keys = [k for k in citations if k in bib]
    missing_keys = [k for k in citations if k not in bib]

    # 2. Define uma função auxiliar para criar a chave de ordenação
    def get_sort_key(key):
        fields = bib[key]
        # Tenta pegar o autor; se não houver, usa o título
        author_raw = fields.get("author", "").strip()
        if author_raw:
            # Extrai o primeiro sobrenome para ordenar
            # Ex: "ZAMPIROLLI, Francisco" -> "ZAMPIROLLI"
            first_author = author_raw.split(" and ")[0]
            surname = first_author.split(",")[0] if "," in first_author else first_author.split()[-1]
            return surname.upper()
        return fields.get("title", "").upper()

    # 3. Ordena as chaves alfabeticamente
    sorted_keys = sorted(valid_keys, key=get_sort_key)

    key_to_num = {}
    lines = ["## Referências do Capítulo\n"]

    if intro_paragraph.strip():
        lines.append(intro_paragraph.strip())
        
    # 4. Gera o texto das referências ordenadas
    for i, key in enumerate(sorted_keys, start=1):
        key_to_num[key] = i
        ref_text = format_entry(key, bib[key])
        lines.append(ref_text)
    
    # Adiciona avisos para chaves não encontradas ao final (opcional)
    for key in missing_keys:
        lines.append(f"*Referência não encontrada para: {key}*")

    return "\n\n".join(lines), key_to_num

# ---------------------------------------------------------------------------
# 12b. Processa um unico notebook para EPUB
# ---------------------------------------------------------------------------

def process_notebook_epub(nb_path: Path, bib: dict, out_path: Path) -> list:
    """
    Gera versao do notebook para EPUB — identico ao modo --batch (alunos),
    pois ambos resolvem citacoes e refs em texto simples por capitulo.
    A unica diferenca e o nome do arquivo de saida (_epub.ipynb).
    """
    return process_notebook(nb_path, bib, out_path)



# ---------------------------------------------------------------------------
# 12. Processa um unico notebook
# ---------------------------------------------------------------------------

def process_notebook(nb_path: Path, bib: dict, out_path: Path, numbering: bool = True) -> list:
    """
    Processa um notebook.
    numbering: se True, adiciona numeração automática às seções
    """
    notebook = json.loads(nb_path.read_text(encoding="utf-8"))
    elem_map = build_element_map(notebook)
    citations = extract_citations(notebook)
    image_paths = extract_image_paths(notebook)

    # Log
    figs = {k: v for k, v in elem_map.items() if v["kind"] == "fig"}
    tbls = {k: v for k, v in elem_map.items() if v["kind"] == "tbl"}
    eqs  = {k: v for k, v in elem_map.items() if v["kind"] == "eq"}
    if figs: print(f"  Figuras  ({len(figs)}): {list(figs.keys())}")
    if tbls: print(f"  Tabelas  ({len(tbls)}): {list(tbls.keys())}")
    if eqs:  print(f"  Equacoes ({len(eqs)}):  {list(eqs.keys())}")
    if not citations:
        print(f"  [!] Nenhuma citacao bibliografica encontrada.")
    else:
        print(f"  Citacoes ({len(citations)}): {citations}")
    if image_paths:
        print(f"  Imagens  ({len(image_paths)}): {image_paths}")

    # Limpeza antes de processar (extrai _ref_intro da célula de referências)
    notebook = clean_notebook(notebook)

    intro_raw = notebook.pop("_ref_intro", "")
    intro_resolved = source_to_str(
        process_cell(str_to_source(intro_raw), {}, elem_map, bib)
    )
    ref_markdown, key_to_num = build_reference_list(citations, bib,
                                                    intro_paragraph=intro_resolved)

    # Remove atributo 'scoped' inválido no EPUB gerado pelo pandas
    for cell in notebook.get("cells", []):
        for output in cell.get("outputs", []):
            if "text/html" in output.get("data", {}):
                html = output["data"]["text/html"]
                if isinstance(html, list):
                    html = "".join(html)
                html = html.replace("<style scoped>", "<style>")
                output["data"]["text/html"] = str_to_source(html)

    # Processa celulas com numeração condicional
    for cell in notebook.get("cells", []):
        if cell.get("cell_type") == "markdown":
            cell["source"] = process_cell(
                cell.get("source", []), key_to_num, elem_map, bib, numbering=numbering
            )

    # Processa celulas
    for cell in notebook.get("cells", []):
        if cell.get("cell_type") == "markdown":
            cell["source"] = process_cell(
                cell.get("source", []), key_to_num, elem_map, bib
            )

    # Mapa fingerprint -> elem_id para células de código com #| label: fig-*/tbl-*
    # Feito ANTES do clean_notebook apagar as linhas #|
    # O fingerprint é o conteúdo sem linhas #| (que sobrevive ao clean_notebook)
    notebook_orig = json.loads(nb_path.read_text(encoding="utf-8"))
    fingerprint_to_label = {}
    for cell in notebook_orig.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        src_orig = source_to_str(cell.get("source", []))
        m = re.search(r'#\|\s*label:\s*((fig|tbl)-[\w-]+)', src_orig)
        if m:
            # Fingerprint: linhas sem #| e sem # @title, stripped
            fp_lines = [l for l in src_orig.splitlines()
                        if not l.strip().startswith("#|")]
            fp = "\n".join(fp_lines).strip()
            fingerprint_to_label[fp] = m.group(1)

    # Injeta legendas e lista de referencias
    new_cells, ref_injected = [], False
    for cell in notebook.get("cells", []):
        src = source_to_str(cell.get("source", []))

        # Injeta legenda para células fig-*/tbl-* de código:
        #   tbl (echo:false): legenda ANTES (código oculto, tabela aparece logo)
        #   fig (echo:true):  legenda DEPOIS (código visível, figura aparece após)
        legend_cell = None
        if cell.get("cell_type") == "code":
            fp_lines = [l for l in src.splitlines()
                        if not l.strip().startswith("# @title")]
            fp = "\n".join(fp_lines).strip()
            elem_id = fingerprint_to_label.get(fp)
            if elem_id:
                info = elem_map.get(elem_id)
                if info and info.get("from_code"):
                    caption = info.get("caption", "")
                    legenda = f"**{info['label']}:** {caption}" if caption \
                        else f"**{info['label']}**"
                    legend_cell = {
                        "cell_type": "markdown",
                        "metadata":  {},
                        "source":    str_to_source(legenda)
                    }
                    if info.get("kind") == "tbl":
                        # tbl: injeta legenda logo antes do output da tabela,
                        # preservando prints anteriores acima da legenda.
                        # A tabela é identificada como o primeiro output com
                        # text/html ou text/markdown (pandas Markdown via Markdown()).
                        outputs = cell.get("outputs", [])
                        tbl_idx = next(
                            (i for i, o in enumerate(outputs)
                             if "text/html" in o.get("data", {})
                             or "text/markdown" in o.get("data", {})
                             or o.get("output_type") == "display_data"),
                            None
                        )
                        legend_output = {
                            "output_type": "display_data",
                            "metadata": {},
                            "data": {
                                "text/markdown": [legenda + "\n"],
                                "text/plain":    [legenda]
                            }
                        }
                        if tbl_idx is not None:
                            outputs.insert(tbl_idx, legend_output)
                        else:
                            outputs.insert(0, legend_output)
                        cell["outputs"] = outputs
                        legend_cell = None  # já inserida nos outputs
                    else:
                        # fig: injeta legenda como output logo após o output de imagem
                        outputs = cell.get("outputs", [])
                        img_idx = next(
                            (i for i, o in enumerate(outputs)
                             if "image/png" in o.get("data", {})
                             or o.get("output_type") == "display_data"),
                            None
                        )
                        legend_output = {
                            "output_type": "display_data",
                            "metadata": {},
                            "data": {
                                "text/markdown": [legenda + "\n"],
                                "text/plain":    [legenda]
                            }
                        }
                        if img_idx is not None:
                            outputs.insert(img_idx + 1, legend_output)
                        else:
                            outputs.append(legend_output)
                        cell["outputs"] = outputs
                        legend_cell = None  # já inserida nos outputs

        if "\\\\printbibliography" in src:
            cell["source"] = str_to_source(ref_markdown)
            ref_injected = True
        new_cells.append(cell)


    if not ref_injected and citations:
        new_cells.append({
            "cell_type": "markdown",
            "metadata":  {},
            "source":    str_to_source(ref_markdown)
        })

    notebook["cells"] = new_cells
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(notebook, ensure_ascii=False, indent=1),
        encoding="utf-8"
    )
    print(f"  -> Salvo: {out_path}")
    return image_paths


# ---------------------------------------------------------------------------
# 13. Copia imagens
# ---------------------------------------------------------------------------

def copy_images(nb_source_dir: Path, out_dir: Path, image_paths: list):
    for img_rel in image_paths:
        src = nb_source_dir / img_rel
        dst = out_dir / img_rel
        if src.exists() and src.resolve() != dst.resolve():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            print(f"  -> Imagem: {img_rel}")
        elif not src.exists():
            alt_src = Path(img_rel)
            if alt_src.exists() and alt_src.resolve() != dst.resolve():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(alt_src, dst)
                print(f"  -> Imagem (raiz): {img_rel}")
            else:
                print(f"  [!] Imagem nao encontrada: {src}")


# ---------------------------------------------------------------------------
# 14b. Modo batch EPUB
# ---------------------------------------------------------------------------

QUARTO_EPUB_YML = """\
# _quarto_epub.yml
# Gerado automaticamente por gerar_notebooks_alunos.py --epub
# Use: quarto render --config _quarto_epub.yml --to epub

project:
  type: book
  output-dir: _book

book:
  title: "Sistemas Inteligentes e Mineração de Dados"
  subtitle: "2ª Edição: Do Weka ao Python"
  author: "José Artur Quilici-Gonzalez, Francisco de Assis Zampirolli e Fábio Rezende de Souza"
  date: "today"
  chapters:
    - index.qmd
{chapters}

lang: pt-BR

format:
  epub:
    toc: true
    number-sections: true
    #css: styles.css 
"""

def run_batch_epub(bib_path: str, out_dir: str):
    """
    Gera notebooks pre-processados para EPUB em <out_dir>/capXX/capXX_epub.ipynb
    e cria _quarto_epub.yml apontando para eles.
    As refs ja estao resolvidas como texto simples por capitulo.

    Uso posterior:
        quarto render --config _quarto_epub.yml --to epub
    """
    bib      = parse_bib(bib_path)
    out_root = Path(out_dir)
    EXCLUDE  = ("_dist", "_executado", "_fixed", "_aluno", "_epub")
    notebooks = sorted([
        Path(p) for p in glob.glob("all/cap*/cap*.ipynb")
        if not any(s in Path(p).stem for s in EXCLUDE)
    ])
    if not notebooks:
        print("Nenhum notebook encontrado com o padrao: all/cap*/cap*.ipynb")
        return

    print(f"[EPUB] Encontrados {len(notebooks)} notebooks:\n")
    chapter_lines = []
    total_imgs = 0

    for nb_path in notebooks:
        cap_name   = nb_path.parent.name
        out_cap    = out_root / cap_name
        epub_name  = nb_path.stem + "_epub.ipynb"
        out_nb     = out_cap / epub_name
        print(f"[{cap_name}] {nb_path}")
        image_paths = process_notebook_epub(nb_path, bib, out_nb)
        if image_paths:
            copy_images(nb_path.parent, out_cap, image_paths)
            total_imgs += len(image_paths)
        # Caminho relativo para o _quarto_epub.yml
        chapter_lines.append(f"    - {out_nb.as_posix()}")
        print()

    # Gera _quarto_epub.yml
    yml_path = Path("_quarto_epub.yml")
    yml_content = QUARTO_EPUB_YML.format(
        chapters="\n".join(chapter_lines)
    )
    yml_path.write_text(yml_content, encoding="utf-8")
    print(f"_quarto_epub.yml gerado.")

    # Gera render_epub.sh
    sh_content = (
        "#!/usr/bin/env bash\n"
        "# render_epub.sh - Gerado por gerar_notebooks_alunos.py --epub\n"
        "# Substitui temporariamente _quarto.yml pelo config EPUB, renderiza e restaura.\n"
        "set -e\n"
        "ORIGINAL=\"_quarto.yml\"\n"
        "EPUB_CFG=\"_quarto_epub.yml\"\n"
        "BACKUP=\"_quarto_backup.yml\"\n"
        "if [ ! -f \"$EPUB_CFG\" ]; then\n"
        "  echo \"Erro: $EPUB_CFG nao encontrado. Rode primeiro:\"\n"
        "  echo \"  python gerar_notebooks_alunos.py --epub references.bib\"\n"
        "  exit 1\n"
        "fi\n"
        "echo \"Salvando $ORIGINAL -> $BACKUP\"\n"
        "cp \"$ORIGINAL\" \"$BACKUP\"\n"
        "echo \"Ativando config EPUB...\"\n"
        "cp \"$EPUB_CFG\" \"$ORIGINAL\"\n"
        "echo \"Renderizando EPUB...\"\n"
        "quarto render --to epub\n"
        "STATUS=$?\n"
        "echo \"Restaurando $BACKUP -> $ORIGINAL\"\n"
        "cp \"$BACKUP\" \"$ORIGINAL\"\n"
        "rm \"$BACKUP\"\n"
        "if [ $STATUS -eq 0 ]; then\n"
        "  echo \"\"; echo \"EPUB gerado com sucesso em _book/\"\n"
        "else\n"
        "  echo \"\"; echo \"Erro (codigo $STATUS). _quarto.yml restaurado.\"\n"
        "  exit $STATUS\n"
        "fi\n"
    )
    sh_path = Path("render_epub.sh")
    sh_path.write_text(sh_content, encoding="utf-8")
    sh_path.chmod(sh_path.stat().st_mode | 0o755)
    print(f"render_epub.sh gerado.")
    print(f"\nPara gerar o EPUB, execute:")
    print(f"  ./render_epub.sh")
    print(f"\nConcluido! {len(notebooks)} notebooks e {total_imgs} imagens em '{out_root}/'")


# ---------------------------------------------------------------------------
# 14. Modo batch (alunos)
# ---------------------------------------------------------------------------

def run_batch(bib_path: str, out_dir: str, numbering: bool = True):
    bib = parse_bib(bib_path)
    out_root = Path(out_dir)
    EXCLUDE = ("_dist", "_executado", "_fixed")
    notebooks = sorted([
        Path(p) for p in glob.glob("all/cap*/cap*.ipynb")
        if not any(s in Path(p).stem for s in EXCLUDE)
    ])
    
    if not notebooks:
        print("Nenhum notebook encontrado com o padrao: all/cap*/cap*.ipynb")
        return

    print(f"Encontrados {len(notebooks)} notebooks:\n")
    total_imgs = 0
    
    for nb_path in notebooks:
        # 🔧 RESETA O CONTADOR GLOBAL antes de cada notebook
        if numbering:
            reset_section_numbering()  # ← chama a função local
        
        cap_name = nb_path.parent.name
        out_cap = out_root / cap_name
        aluno_name = nb_path.stem + "_aluno.ipynb"
        out_nb = out_cap / aluno_name
        print(f"[{cap_name}] {nb_path}")
        
        image_paths = process_notebook(nb_path, bib, out_nb, numbering=numbering)
        if image_paths:
            copy_images(nb_path.parent, out_cap, image_paths)
            total_imgs += len(image_paths)
        print()
        
    # Gera README.md
    readme = out_root / "README.md"
    readme.write_text(
        "# Notebooks para Alunos\n\n"
        "Notebooks dos capítulos com referências bibliográficas, "
        "figuras, tabelas e equações renderizadas para Jupyter/Colab.\n\n"
        "## Estrutura\n"
        "`capXX/capXX_aluno.ipynb` — notebook do capítulo XX\n"
        "`capXX/images/` — imagens do capítulo\n\n"
        "## Como usar\n"
        "```bash\n"
        "jupyter lab cap01/cap01_aluno.ipynb\n"
        "```\n\n"
        "## Características\n"
        "- Referências bibliográficas formatadas (ABNT)\n"
        "- Figuras com legenda numerada\n"
        "- Tabelas com legenda acima\n"
        "- Equações numeradas\n"
        "- Sem metadados Quarto\n",
        encoding="utf-8"
    )
    print(f"README.md gerado em '{readme}'")

    print(
        f"Concluido! {len(notebooks)} notebooks e {total_imgs} imagens "
        f"exportados para '{out_root}/'"
    )


# ---------------------------------------------------------------------------
# 15. CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Injeta referencias em notebooks Quarto para distribuicao.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("--batch", action="store_true",
                        help="Processa todos all/cap*/cap*.ipynb para distribuicao (Jupyter/Colab)")
    parser.add_argument("--epub", action="store_true",
                        help="Processa todos all/cap*/cap*.ipynb para EPUB (refs por capitulo em texto)")
    parser.add_argument("--out-dir", default="notebooks_alunos",
                        help="Pasta de saida no modo batch/epub (padrao: notebooks_alunos)")
    parser.add_argument("--no-numbering", action="store_true",
                        help="Nao adiciona numeracao automatica de secoes")
    parser.add_argument("notebook", nargs="?",
                        help="Caminho para o .ipynb (modo unico)")
    parser.add_argument("bib", help="Caminho para o references.bib")
    parser.add_argument("--output", "-o", help="Saida do .ipynb no modo unico")
    args = parser.parse_args()

    # Define o valor de numbering
    numbering = not args.no_numbering  # True por padrão, False se --no-numbering

    if args.epub:
        run_batch_epub(args.bib, args.out_dir, numbering=numbering)
    elif args.batch:
        run_batch(args.bib, args.out_dir, numbering=numbering)
    else:
        if not args.notebook:
            parser.error("Informe o notebook ou use --batch ou --epub")
        nb_path = Path(args.notebook)
        out_path = Path(args.output) if args.output else \
                   nb_path.parent / (nb_path.stem + "_dist.ipynb")
        bib = parse_bib(args.bib)
        print(f"Processando: {nb_path}")
        image_paths = process_notebook(nb_path, bib, out_path, numbering=numbering)
        if image_paths:
            copy_images(nb_path.parent, out_path.parent, image_paths)


if __name__ == "__main__":
    main()