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

from .config import BASE_LANG, LANGUAGES, LOCALES, Combo
from .translators import TranslatorFactory
from .bib import resolve_citations, resolve_bibliography

from nbformat.v4 import new_markdown_cell, new_code_cell

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


# ── Placeholder vazio de EP (%%writefile EPxx_yy.py + "# sua solução") ──────
#
# _merge_ep_notebook() mescla incondicionalmente o notebook de EPs em
# qualquer combo — inclusive combos de linguagem (cpp, java, ...) ainda sem
# conteúdo real além do placeholder. Sem esta guarda, o LLMCodeTranslator
# receberia um comentário vazio pedindo pra "traduzir" e poderia alucinar
# uma solução completa do zero. Por isso: reconhecer o placeholder e só
# trocar a extensão/comentário, sem nunca chamar o LLM nesse caso.

_EP_PLACEHOLDER_COMMENT_PREFIX = {
    '.py': '#', '.java': '//', '.c': '//', '.cpp': '//', '.js': '//', '.r': '#',
}
_EP_PLACEHOLDER_PHRASE = {
    'pt': 'sua solução',
    'en': 'your solution',
}

_EP_WRITEFILE_HEAD_RE = re.compile(r'^%%writefile\s+(EP\d+_\d+)\.py\s*$')


def _ep_placeholder_name(src: str) -> Optional[str]:
    """
    Se `src` for o placeholder vazio de um EP (%%writefile EPxx_yy.py seguido
    só de comentário/linha em branco), devolve o nome do EP (ex.: "EP01_02").
    Caso contrário (linguagem não bate, ou já tem código de verdade), None.
    """
    lines = src.splitlines()
    if not lines:
        return None
    m = _EP_WRITEFILE_HEAD_RE.match(lines[0])
    if not m:
        return None
    for line in lines[1:]:
        stripped = line.strip()
        if stripped and not stripped.startswith('#'):
            return None  # tem código de verdade — não é placeholder
    return m.group(1)


_EP_TESTSUITE_CALL_RE = re.compile(
    r'^TestSuite\(\s*["\'](EP\d+_\d+)\.py["\']\s*\)\.run\(\)\s*$'
)


def _ep_testsuite_call_name(src: str) -> Optional[str]:
    """
    Se `src` for exatamente `TestSuite("EPxx_yy.py").run()` — a célula
    companheira do placeholder de EP, sempre logo depois do `%%writefile` —
    devolve o nome do EP. Mandar isso pro LLM não faz sentido (não há nada
    pra traduzir, é só uma chamada) e o modelo historicamente devolve texto
    em prosa em vez de código, gastando uma chamada de API à toa e sempre
    reprovando a compilação.
    """
    m = _EP_TESTSUITE_CALL_RE.match(src.strip())
    return m.group(1) if m else None


# ── Expansão 1 célula → N células (combos de linguagem não-Python) ──────────
#
# Uma célula Python narrativa (não-EP) só pode virar código C++/Java/...
# executável se usar exclusivamente as operações que têm equivalente em
# morph.hpp (Fase 4). A checagem roda sobre o CÓDIGO PYTHON ORIGINAL — nunca
# sobre a saída do LLM — porque a decisão de "isso é seguro de expandir"
# precisa ser garantida por construção, não por o modelo ter obedecido o
# prompt.

_MM_WHITELIST = {'read', 'gray', 'randomImage', 'show', 'write', 'threshold', 'drawImg'}
_CV2_RE   = re.compile(r'\bcv2\.')
_PLT_RE   = re.compile(r'\bplt\.')
_MM_CALL_RE = re.compile(r'\bmm\.(\w+)\s*\(')
_MM_SHOW_RE = re.compile(r'\bmm\.show\s*\(')
_LABEL_RE   = re.compile(r'^#\|\s*label:\s*(\S+)', re.MULTILINE)
# Mesmo padrão usado em quarto_builder.py (HTML_TRIPLE_RE) pra achar células
# que montam HTML/JS embutido (simuladores interativos via IPython.display.HTML).
_HTML_TRIPLE_RE = re.compile(r'HTML\(\s*[a-zA-Z]{0,2}["\']{3}')

def _is_eligible_for_foreign_expansion(src: str) -> bool:
    """
    True só se `src` não usa cv2/matplotlib diretamente, não monta HTML/JS
    embutido (simuladores interativos — não fazem sentido em C++, e uma
    "tradução" que tente simular a interação via stdin pode travar esperando
    entrada que nunca chega), e todo `mm.*` chamado está na lista de funções
    com equivalente em morph.hpp. Fora disso, a célula fica como referência
    Python não-executada (nunca tenta traduzir).
    """
    if _CV2_RE.search(src) or _PLT_RE.search(src) or _HTML_TRIPLE_RE.search(src):
        return False
    for m in _MM_CALL_RE.finditer(src):
        if m.group(1) not in _MM_WHITELIST:
            return False
    return True


def _cell_base_name(src: str, ctx: dict) -> str:
    """
    Nome-base pro arquivo gerado: deriva do `#| label: fig-xx` da própria
    célula (já garantido único pelo Quarto) — sem label, usa um contador
    estável no `ctx` do notebook.
    """
    m = _LABEL_RE.search(src)
    if m:
        return re.sub(r'[^A-Za-z0-9_]', '_', m.group(1))
    ctx['counter'] = ctx.get('counter', 0) + 1
    return f'mm_out_{ctx["counter"]}'


def _clean_cell(cell, is_base: bool = False):
    """Remove outputs e execution_count (preserva outputs no combo base)."""
    if 'outputs' in cell and not is_base:
        cell['outputs'] = []
    if 'execution_count' in cell:
        cell['execution_count'] = None
    pdi = cell.get('metadata', {}).get('pdi', {})
    cell['metadata'] = {'pdi': pdi} if pdi else {}


# ─────────────────────────────────────────────────────────────────────────────
# Pós-processamento Markdown (citações)
# ─────────────────────────────────────────────────────────────────────────────

def postprocess_markdown(src: str, bib: dict, used_keys: set) -> str:
    """
    Aplica os pós-processamentos Markdown.

    Só resolve citações (ABNT) — NÃO toca em nenhuma sintaxe Quarto
    (`:::{#fig-x}`, `:::{.callout-x}`, `{.unnumbered}`, `@fig-x`...): o
    mesmo notebook gerado aqui é o que o Quarto renderiza pra virar o
    livro HTML/PDF, em TODOS os combos — inclusive não-base. Reescrever ou
    "limpar" parcialmente essa sintaxe antes do Quarto processá-la quebra o
    parser dele: comprovado tanto pra figuras (contador de crossref nativo
    passava a numerar só o que sobrava e divergia dos links `@fig-x` no
    texto) quanto pros divs (_remove_quarto_attrs tirava a linha `:::` de
    FECHAMENTO de QUALQUER div — inclusive as de figura/tabela que agora
    ficam intactas — deixando o div "aberto" e o Quarto engolindo todo o
    conteúdo seguinte como subfloat dele). Confirmado comparando com o
    combo base (py.pt, nunca pós-processado): renderiza perfeito porque o
    Quarto já lida nativamente com tudo isso, inclusive localizando rótulos
    (Figure/Figura/Tableau) via o `lang:` do YAML. Não-base deve se
    comportar EXATAMENTE como base pra qualquer sintaxe Quarto — só o texto
    em si (e citações) muda.
    """
    src = resolve_citations(src, bib, used_keys)
    src = resolve_bibliography(src, bib, used_keys)
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

    @staticmethod
    def _tag_cache_key(cell, src: str, translator) -> None:
        """
        Grava em `cell.metadata.pdi.ck` a chave de cache correspondente à
        tradução de `src` por `translator` — permite que `dev.py
        --promote-edits` reconheça uma edição manual feita direto no
        notebook gerado e a devolva pra mesma entrada do cache. Só marca
        tradutores não-identidade (`tgt_key != src_key`): PythonPassthrough/
        PassthroughText nunca passam pelo LLM, não há o que promover.
        """
        if translator.tgt_key == translator.src_key:
            return
        key = translator.cache.key_for(
            src, translator.kind, translator.src_key, translator.tgt_key
        )
        cell.setdefault('metadata', {}).setdefault('pdi', {})['ck'] = key

    # Uma linha só com o marcador `#[token]#` trava a célula. `token` é uma
    # lista de partes separadas por ponto, cada uma uma chave de LANGUAGES
    # ou LOCALES — mesmo formato de combo.key (gen/cpp.pt/, cache, etc.).
    # Dentro de um eixo, várias partes combinam em OR; entre os dois eixos
    # combina em AND: `#[py.pt.cpp]#` = (linguagem ∈ {py, cpp}) E
    # (idioma ∈ {pt}) — "só python e cpp, em português". Um único token
    # continua funcionando como antes: `#[cpp]#` só linguagem, `#[pt]#` só
    # idioma. Sem marcador reconhecido, a célula passa normal em todo combo.
    _MARKER_TOKEN_RE = re.compile(r'#\[\s*([\w.]+)\s*\]#')
    _MARKER_LINE_RE = re.compile(
        r'^[#\s`]*#\[\s*[\w.]+\s*\]#`?\s*$', re.MULTILINE
    )

    def _filter_by_language_marker(self, cell, combo: Combo) -> bool:
        src = _get_source(cell)
        lines = src.splitlines(keepends=True)
        idx_to_remove = -1
        token: Optional[str] = None
        for i, line in enumerate(lines):
            if self._MARKER_LINE_RE.match(line):
                token = self._MARKER_TOKEN_RE.search(line).group(1)
                idx_to_remove = i
                break

        if idx_to_remove == -1:
            return True

        # Remove a linha inteira onde o marcador apareceu.
        lines.pop(idx_to_remove)
        _set_source(cell, ''.join(lines))

        langs: set = set()
        locales: set = set()
        for part in token.split('.'):
            if part in LANGUAGES:
                langs.add(part)
            elif part in LOCALES:
                locales.add(part)
            else:
                print(f'  ⚠ Marcador "#[{token}]#": parte "{part}" não é '
                      f'linguagem nem idioma conhecidos — ignorada.')

        if not langs and not locales:
            return True  # nada reconhecido no marcador — não filtra
        if langs and combo.lang not in langs:
            return False
        if locales and combo.locale not in locales:
            return False
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
    
    def _reference_only_cell(self, cell, src: str, combo: Combo):
        """
        Fallback pra célula narrativa que não pode (ou não conseguiu) virar
        código executável no combo.lang: mantém o Python original (só com
        comentários traduzidos pro locale, mesmo mecanismo de py→py), com um
        aviso de cabeçalho deixando claro que é referência, não executada
        nesta versão. Nunca emite um scaffold de código quebrado.

        Crucial: `#| eval: false` precisa entrar de verdade nas opções da
        célula — não basta um comentário dizendo "não executada". Com
        `execute: enabled: true` (ver quarto_builder._quarto_yml), o Quarto
        tentaria rodar essa célula de qualquer jeito, e ela quase sempre
        depende de nomes definidos numa célula ANTERIOR que talvez tenha
        virado outra coisa (ou nem exista mais) neste combo — sem o
        `eval: false`, isso derruba o build inteiro com um NameError, não
        só degrada uma figura.
        """
        ref_cell = copy.deepcopy(cell)
        py_tr = self._factory.code_translator(BASE_LANG, combo.locale)
        translated_src = py_tr.translate(src)
        # A célula de referência continua sendo código PYTHON (nunca é
        # traduzida pra combo.lang) — o comentário de cabeçalho tem que
        # usar sintaxe Python (`#`) em qualquer locale, não `//`.
        header = {
            'pt': '# Ainda não portado para esta linguagem nesta versão — referência conceitual em Python.\n',
        }.get(combo.locale,
              '# Not yet ported to this language in this version — conceptual reference in Python.\n')

        # #| eval: false precisa ficar junto das outras opções #| já
        # existentes (label/fig-cap/echo/...), que têm que continuar sendo
        # as primeiras linhas da célula pro Quarto reconhecer como opções.
        lines = translated_src.split('\n')
        i = 0
        while i < len(lines) and lines[i].startswith('#|'):
            i += 1
        option_lines = lines[:i] + ['#| eval: false']
        rest_lines = lines[i:]
        final_src = '\n'.join(option_lines) + '\n' + header + '\n'.join(rest_lines)

        _set_source(ref_cell, final_src)
        return [ref_cell]

    def _expand_foreign_code_cell(self, cell, src: str, combo: Combo,
                                   code_tr, ctx: dict) -> list:
        """
        Expande UMA célula Python narrativa em N células executáveis pro
        combo.lang (write/compilar+rodar/[exibir]) — só chamada quando
        combo.lang != BASE_LANG e a célula não é placeholder de EP nem
        role 'common'. Ver notebook_processor.py (docstring do módulo) e o
        plano em snuggly-wishing-origami.md pra desenho completo.
        """
        if not _is_eligible_for_foreign_expansion(src):
            return self._reference_only_cell(cell, src, combo)

        ext = LANGUAGES[combo.lang].extension
        base = _cell_base_name(src, ctx)
        needs_glue = bool(_MM_SHOW_RE.search(src))
        png_name = f'{base}.png'

        # output_image_path precisa ir pro translate() ANTES da checagem de
        # compilação (Fase 3) — se o #define MM_OUT só fosse prefixado
        # depois, toda célula com mm.show() reprovaria a validação por
        # "MM_OUT não declarado", um motivo que não tem nada a ver com a
        # qualidade da tradução em si.
        translated = code_tr.translate(
            src, output_image_path=png_name if needs_glue else None
        )
        if translated == src:
            # LLMCodeTranslator devolve o Python original quando a
            # compilação de validação falha (Fase 3) — rede de segurança:
            # nunca expandir em cima de uma tradução ruim.
            return self._reference_only_cell(cell, src, combo)

        write_cell = copy.deepcopy(cell)
        _set_source(write_cell, f'%%writefile {base}{ext}\n{translated}')

        run_line = f'!g++ {base}{ext} -o {base} && ./{base}'
        if needs_glue:
            run_line += (f' && test -f "{png_name}" '
                         f'|| echo "⚠ mm::show não gravou {png_name}"')
        run_cell = new_code_cell(run_line)

        out = [write_cell, run_cell]
        if needs_glue:
            glue_cell = new_code_cell(
                'from IPython.display import Image, display\n'
                f'display(Image(filename="{png_name}"))'
            )
            out.append(glue_cell)

        for c in out:
            c['metadata'] = {'pdi': {'role': 'code', 'synthetic': True}}
        # Só o write_cell tem conteúdo vindo do cache; run/glue são
        # sintéticos (comando de shell) e nunca passaram pelo LLM.
        self._tag_cache_key(write_cell, src, code_tr)
        return out

    def process(self, nb_path: str, combo: Combo) -> nbformat.NotebookNode:
        with open(nb_path, encoding='utf-8') as f:
            nb = nbformat.read(f, as_version=4)

        code_tr = self._factory.code_translator(combo.lang, combo.locale)
        text_tr = self._factory.text_translator(combo.locale)

        used_keys: set = set()
        out_cells = []
        expand_ctx: dict = {}

        for cell in nb.cells:
            cell = copy.deepcopy(cell)
            role = _cell_role(cell)
            src  = _get_source(cell)


            # --- Filtro por marcador de linguagem/idioma ---
            if not self._filter_by_language_marker(cell, combo):
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
                ep_name = (None if combo.lang == BASE_LANG
                           else _ep_placeholder_name(src))
                ts_ep_name = (None if combo.lang == BASE_LANG
                              else _ep_testsuite_call_name(src))
                if ep_name is not None:
                    ext = LANGUAGES[combo.lang].extension
                    comment = _EP_PLACEHOLDER_COMMENT_PREFIX.get(ext, '//')
                    phrase = _EP_PLACEHOLDER_PHRASE.get(
                        combo.locale, _EP_PLACEHOLDER_PHRASE['en']
                    )
                    _set_source(cell, f'%%writefile {ep_name}{ext}\n{comment} {phrase}')
                elif ts_ep_name is not None:
                    # TestSuite(...) é uma chamada de API fixa, não algoritmo
                    # — nunca precisa de LLM, só trocar a extensão do arquivo
                    # alvo (vale tanto pro placeholder vazio quanto pra uma
                    # EP já preenchida futuramente).
                    ext = LANGUAGES[combo.lang].extension
                    _set_source(cell, f'TestSuite("{ts_ep_name}{ext}").run()')
                elif combo.lang == BASE_LANG:
                    translated = code_tr.translate(src)
                    self._tag_cache_key(cell, src, code_tr)
                    _set_source(cell, translated)
                else:
                    # Fase 2: pode virar várias células (write/compilar+
                    # rodar/exibir) — trata e insere direto em out_cells,
                    # pula a cauda de limpeza/append de célula única abaixo.
                    expanded = self._expand_foreign_code_cell(
                        cell, src, combo, code_tr, expand_ctx
                    )
                    for c in expanded:
                        _clean_cell(c, is_base=combo.is_base())
                        if _get_source(c).strip():
                            out_cells.append(c)
                    continue

            elif role in ('text', 'exercise') and cell.cell_type == 'markdown':
                translated = text_tr.translate(src)
                self._tag_cache_key(cell, src, text_tr)
                if not combo.is_base():
                    translated = postprocess_markdown(translated, self._bib, used_keys)
                _set_source(cell, translated)

            # common → sem alteração

            _clean_cell(cell, is_base=combo.is_base())

            if _get_source(cell).strip():
                out_cells.append(cell)

        nb.cells = out_cells

        # --- Mesclagem do notebook de exercícios (EPs) ---
        nb = self._merge_ep_notebook(nb, Path(nb_path), combo)

        return nb