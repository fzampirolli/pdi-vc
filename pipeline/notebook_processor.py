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

import ast
import copy
import re
from pathlib import Path
from typing import Optional
import re   # no topo do arquivo

try:
    import nbformat
except ImportError:
    raise ImportError("pip install nbformat")

from .config import BASE_LANG, BASE_LOCALE, LANGUAGES, LOCALES, Combo
from .translators import TranslatorFactory
from .bib import resolve_citations, resolve_bibliography
from .exec_validate import (inject_consumer_reads, inject_panel_writes,
                            inject_producer_writes)

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


# Badge "Executar no Colab" da 1ª célula markdown: no fonte o alvo está
# hardcoded (ora `notebooks_alunos/py.pt/capXX/...`, ora sem prefixo de
# combo `notebooks_alunos/capXX/...`, às vezes apontando pro capítulo
# errado). Os cadernos de aluno só existem em `<lang>.pt` (não há en/fr),
# então o alvo correto por combo é sempre
# `notebooks_alunos/<combo.lang>.pt/<cap_name>/<stem>_aluno.ipynb`.
_COLAB_BADGE_RE = re.compile(
    r'(https://colab\.research\.google\.com/github/fzampirolli/pdi-vc/blob/master/)'
    r'notebooks_alunos/[^)\s]+?_aluno\.ipynb'
)


def _fix_colab_badge(src: str, cap_name: str, is_eps: bool, lang: str) -> str:
    stem = f'{cap_name}.EPs' if is_eps else cap_name
    target = (f'\\1notebooks_alunos/{lang}.pt/{cap_name}/{stem}_aluno.ipynb')
    return _COLAB_BADGE_RE.sub(target, src)


# ── Placeholder vazio de EP (%%writefile EPxx_yy.py + "# sua solução") ──────
#
# _merge_ep_notebook() mescla incondicionalmente o notebook de EPs em
# qualquer combo — inclusive combos de linguagem (cpp, java, ...) ainda sem
# conteúdo real além do placeholder. Sem esta guarda, o LLMCodeTranslator
# receberia um comentário vazio pedindo pra "traduzir" e poderia alucinar
# uma solução completa do zero. Por isso: reconhecer o placeholder e só
# trocar a extensão/comentário, sem nunca chamar o LLM nesse caso.

# Subpasta (relativa ao diretório do capítulo) para os artefatos de build
# da trilha compilada: .cpp gerado, binário, PNG intermediário do MM_OUT e
# state/ da passagem de mm::Image entre células. Mantém o diretório do
# capítulo limpo (só .ipynb, imagens/, morph.hpp, EP*.cpp do aluno).
TMP_DIR = 'tmp'

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

_MM_WHITELIST = {'read', 'gray', 'randomImage', 'show', 'write', 'threshold', 'otsu', 'drawImg'}
_CV2_RE   = re.compile(r'\bcv2\.(\w+)')
# Símbolos cv2 que a cheat-sheet de tradução sabe mapear pra morph.hpp
# (cv2.threshold(..., THRESH_OTSU) -> mm::threshold + mm::otsu pro valor T).
# Uma célula com cv2 SÓ desses continua elegível; qualquer outro cv2.* não.
_CV2_WHITELIST = {'threshold', 'THRESH_BINARY', 'THRESH_BINARY_INV', 'THRESH_OTSU'}
_PLT_RE   = re.compile(r'\bplt\.')
_MM_CALL_RE = re.compile(r'\bmm\.(\w+)\s*\(')
_MM_SHOW_RE = re.compile(r'\bmm\.show\s*\(')
_LABEL_RE   = re.compile(r'^#\|\s*label:\s*(\S+)', re.MULTILINE)
_FIG_OPTION_RE = re.compile(r'^#\|\s*(label|fig-cap):', re.MULTILINE)
# Mesmo padrão usado em quarto_builder.py (HTML_TRIPLE_RE) pra achar células
# que montam HTML/JS embutido (simuladores interativos via IPython.display.HTML).
_HTML_TRIPLE_RE = re.compile(r'HTML\(\s*[a-zA-Z]{0,2}["\']{3}')

def _is_eligible_for_foreign_expansion(src: str) -> bool:
    """
    True só se `src` não usa matplotlib diretamente, não monta HTML/JS
    embutido (simuladores interativos — não fazem sentido em C++, e uma
    "tradução" que tente simular a interação via stdin pode travar esperando
    entrada que nunca chega), todo `cv2.*` usado está em _CV2_WHITELIST e
    todo `mm.*` chamado está na lista de funções com equivalente em
    morph.hpp. Fora disso, a célula fica como referência Python
    não-executada (nunca tenta traduzir).
    """
    if _PLT_RE.search(src) or _HTML_TRIPLE_RE.search(src):
        return False
    if any(sym not in _CV2_WHITELIST for sym in _CV2_RE.findall(src)):
        return False
    for m in _MM_CALL_RE.finditer(src):
        if m.group(1) not in _MM_WHITELIST:
            return False
    return True


# ── Estado mm::Image entre células (combos cpp) ─────────────────────────────
#
# Cada célula elegível vira um programa C++ standalone (`!g++ ... && ./...`),
# sem estado de kernel compartilhado como o Python tem entre células. Quando
# uma célula posterior referencia uma variável `mm::Image` criada por uma
# célula ANTERIOR (padrão comum no livro: ler → cinza → limiarizar → ...),
# a tradução isolada dessa célula não compila (a variável nunca foi
# declarada naquele programa). Ver plano em
# giggly-wandering-squirrel.md — persistência via round-trip em disco
# (state/<var>_<producer_idx>.png), injetada mecanicamente (nunca pelo LLM).

# Subconjunto de _MM_WHITELIST que de fato PRODUZ um mm::Image (mm.show/
# mm.write retornam void, mm.drawImg retorna string — nunca são produtoras).
_MM_IMAGE_PRODUCING_FNS = {'read', 'gray', 'randomImage', 'threshold'}

_AST_SCOPE_BOUNDARY = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)

_NON_VAR_NAMES = {'mm', 'np', 'os'} | set(__import__('builtins').__dict__)


def _walk_restricted(node):
    """
    Percorre `node` como `ast.walk`, mas nunca desce em FunctionDef/
    AsyncFunctionDef/ClassDef/Lambda — uma atribuição feita dentro de uma
    função/classe aninhada não vaza pro escopo de nível de célula (que vira
    o corpo de `main()` no C++ traduzido).
    """
    yield node
    for child in ast.iter_child_nodes(node):
        if isinstance(child, _AST_SCOPE_BOUNDARY):
            continue
        yield from _walk_restricted(child)


def _detect_mm_image_produced(tree) -> dict:
    """
    Nomes atribuídos, no nível da célula (via `_walk_restricted`), a partir
    de uma chamada `mm.<fn>(...)` com `fn` em `_MM_IMAGE_PRODUCING_FNS`, ou
    de `np.array(X)` onde `X` já foi produzido antes na MESMA célula (cobre
    o caso real do livro: `img_obj = mm.read(url); img = np.array(img_obj)`
    — sem esse hop, `img` passaria batido). Devolve {nome: lineno}.
    """
    produced: dict = {}
    for node in _walk_restricted(tree):
        if not isinstance(node, ast.Assign):
            continue
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        target = node.targets[0].id
        value = node.value
        if (isinstance(value, ast.Call)
                and isinstance(value.func, ast.Attribute)
                and isinstance(value.func.value, ast.Name)
                and value.func.value.id == 'mm'
                and value.func.attr in _MM_IMAGE_PRODUCING_FNS):
            produced[target] = node.lineno
            continue
        if (isinstance(value, ast.Call)
                and isinstance(value.func, ast.Attribute)
                and isinstance(value.func.value, ast.Name)
                and value.func.value.id == 'np'
                and value.func.attr == 'array'
                and len(value.args) == 1
                and isinstance(value.args[0], ast.Name)
                and value.args[0].id in produced):
            produced[target] = node.lineno
    return produced


def _locally_bound_names(tree) -> set:
    """
    Todo nome que a própria célula declara de alguma forma (atribuição,
    alvo de for/with/comprehension, parâmetro, import, def/class) — NUNCA
    tratado como referência a uma variável externa, mesmo que também
    apareça em `active_producers` (reatribuição local sempre "esconde" o
    valor vindo de fora).
    """
    bound: set = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            bound.add(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            bound.add(node.name)
            for arg in node.args.args:
                bound.add(arg.arg)
        elif isinstance(node, ast.ClassDef):
            bound.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                bound.add((alias.asname or alias.name).split('.')[0])
        elif isinstance(node, ast.comprehension) and isinstance(node.target, ast.Name):
            bound.add(node.target.id)
        elif isinstance(node, ast.withitem) and isinstance(node.optional_vars, ast.Name):
            bound.add(node.optional_vars.id)
    return bound


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


def _figure_option_lines(src: str) -> list:
    """
    Extrai as linhas `#| label: ...` / `#| fig-cap: ...` do topo de `src`
    (célula Python original) — são as únicas opções `#|` que precisam
    migrar pra célula sintética que de fato produz a saída de imagem
    (`display(Image(...))`), pois é nela que o Quarto procura a
    numeração/legenda/cross-ref da figura. Sem isso, `@fig-xx` no texto
    fica sem resolver (`?fig-xx` literal), mesmo com a figura aparecendo
    normalmente — achado ao validar o build cpp de ponta a ponta.
    """
    lines = src.split('\n')
    opts = []
    for line in lines:
        if not line.startswith('#|'):
            break
        if _FIG_OPTION_RE.match(line):
            opts.append(line)
    return opts


# Ordem de kwargs de mm.show() propagados pra célula-glue (só os que
# afetam layout/rotulagem — nada de estado).
_MM_SHOW_GLUE_KWARGS = ('titles', 'title', 'cols', 'rows', 'axis', 'figsize', 'dpi')


def _literal_namespace(src: str) -> dict:
    """`{nome: valor}` das atribuições `nome = <literal>` de nível de módulo
    em `src` — usado pra resolver títulos tipo `f"Binária (T={limiar})"`
    (onde `limiar = 128` aparece na mesma célula) em string estática."""
    ns: dict = {}
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return ns
    for node in getattr(tree, 'body', []):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name):
            try:
                ns[node.targets[0].id] = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                pass
    return ns


def _render_title(node: ast.AST, ns: dict, dynamic_ok: set) -> tuple:
    """Renderiza um nó de título pra glue:
      * `('lit', "texto")`  — literal / f-string totalmente resolvível
        contra `ns` (constantes da própria célula);
      * `('fstr', 'f"...{nome}..."')` — f-string em que TODA interpolação ou
        resolve contra `ns` (substituída inline) ou está em `dynamic_ok`
        (mantida como `{nome}`, a ser calculada no preâmbulo da glue).
    Levanta quando sobra interpolação que não é nenhum dos dois."""
    try:
        return ('lit', str(ast.literal_eval(node)))
    except (ValueError, TypeError):
        pass

    def _eval(expr):
        code = compile(ast.Expression(expr), '<title>', 'eval')
        return eval(code, {'__builtins__': {}}, dict(ns))  # noqa: S307 — ns só tem literais

    if not isinstance(node, ast.JoinedStr):
        val = _eval(node)
        if not isinstance(val, str):
            raise TypeError('título não-string')
        return ('lit', val)

    def _esc(t: str) -> str:            # texto literal dentro de f"..."
        return t.replace('\\', '\\\\').replace('"', '\\"') \
                .replace('{', '{{').replace('}', '}}')

    raw, esc, has_dyn = [], [], False
    for v in node.values:
        if isinstance(v, ast.Constant):
            raw.append(str(v.value))
            esc.append(_esc(str(v.value)))
        elif isinstance(v, ast.FormattedValue):
            name = v.value.id if isinstance(v.value, ast.Name) else None
            if name is not None and name in dynamic_ok:
                esc.append('{' + name + '}')
                raw.append('')
                has_dyn = True
            else:
                s = format(_eval(v.value))
                raw.append(s)
                esc.append(_esc(s))
        else:
            raise ValueError('f-string com parte inesperada')
    if has_dyn:
        return ('fstr', 'f"' + ''.join(esc) + '"')
    return ('lit', ''.join(raw))


def _otsu_from_cv2(tree: ast.AST, panel_names: list) -> list:
    """Acha `T, _ = cv2.threshold(<img>, ..., ...THRESH_OTSU...)` em que
    `<img>` é um dos painéis. Devolve [(T_name, panel_idx), ...] — a glue
    recalcula esse T no kernel Python (via `mm.otsu`) a partir do PNG do
    painel, já que o valor vive no processo C++ e não cruza pra cá."""
    out = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Tuple)):
            continue
        val = node.value
        if not (isinstance(val, ast.Call) and isinstance(val.func, ast.Attribute)
                and val.func.attr == 'threshold'
                and isinstance(val.func.value, ast.Name)
                and val.func.value.id == 'cv2'):
            continue
        if 'THRESH_OTSU' not in ' '.join(ast.unparse(a) for a in val.args):
            continue
        tgt = node.targets[0].elts
        img = val.args[0] if val.args else None
        if (tgt and isinstance(tgt[0], ast.Name)
                and isinstance(img, ast.Name) and img.id in panel_names):
            out.append((tgt[0].id, panel_names.index(img.id)))
    return out


def _parse_mm_show_panels(src: str) -> Optional[dict]:
    """
    Se `src` chama `mm.show([v1, v2, ...], titles=[...], cols=, axis=, ...)`
    com o 1º argumento uma LISTA DE NOMES SIMPLES, devolve
    `{'names', 'titles', 'kwargs', 'otsu'}` — o suficiente pra reconstruir a
    mesma figura na trilha C++ exibindo os painéis individualmente (com
    título/eixo), já que o `mm::show` do C++ achata tudo num PNG sem texto.

    `titles`: lista de `('lit'|'fstr', str)` (ver _render_title) ou None.
    `otsu`: `[(T_name, panel_idx), ...]` — T's de Otsu que a glue recalcula
    com `mm.otsu` a partir do PNG do painel (o valor vive no processo C++).

    Devolve None quando não é a forma de lista, quando os elementos não são
    nomes simples, quando um título é dinâmico de verdade, ou `src` não
    parseia.
    """
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None
    ns = _literal_namespace(src)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if not (isinstance(f, ast.Attribute) and f.attr == 'show'
                and isinstance(f.value, ast.Name) and f.value.id == 'mm'):
            continue
        if not node.args or not isinstance(node.args[0], ast.List):
            return None
        elts = node.args[0].elts
        if not elts or not all(isinstance(e, ast.Name) for e in elts):
            return None
        names = [e.id for e in elts]
        otsu = _otsu_from_cv2(tree, names)
        dynamic_ok = {t for t, _ in otsu}
        kwargs = {kw.arg: ast.unparse(kw.value)
                  for kw in node.keywords
                  if kw.arg in _MM_SHOW_GLUE_KWARGS and kw.arg not in ('titles', 'title')}
        titles = None
        for kw in node.keywords:
            if kw.arg not in ('titles', 'title'):
                continue
            elts_t = kw.value.elts if isinstance(kw.value, ast.List) else [kw.value]
            try:
                titles = [_render_title(e, ns, dynamic_ok) for e in elts_t]
            except Exception:
                return None
        # se nenhum título usa um T de Otsu, não precisa do preâmbulo cv2
        if titles is not None:
            used = any(kind == 'fstr' for kind, _ in titles)
            if not used:
                otsu = []
        return {'names': names, 'titles': titles, 'kwargs': kwargs, 'otsu': otsu}
    return None


def _parse_mm_show_figsize(src: str) -> Optional[str]:
    """`figsize=<expr>` da chamada `mm.show(...)` em `src` (string), ou None.
    Deixar a glue C++ usar o MESMO figsize da célula Python original — e
    OMITIR quando o original omite — faz o morph.py dimensionar igual nas
    duas trilhas."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == 'show'
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == 'mm'):
            for kw in node.keywords:
                if kw.arg == 'figsize':
                    return ast.unparse(kw.value)
            return None
    return None


def _panels_glue_lines(base: str, panels: dict) -> list:
    """Reconstrói `mm.show([mm.read(painel_i)...], titles=[...], ...)` — uma
    entrada por linha pra nada passar de ~90 colunas no PDF."""
    n = len(panels['names'])
    kw = panels['kwargs']            # já sem titles/title (ver _parse_mm_show_panels)
    out = []
    # Preâmbulo: o T de Otsu que aparece nos títulos é recalculado no kernel
    # Python a partir do PNG em tons de cinza do painel — o valor vive no
    # processo C++ e não cruza pra cá. `mm.otsu` espelha `mm::otsu` da
    # morph.hpp; sobre os mesmos pixels dá o mesmo T. Ver _otsu_from_cv2.
    if panels.get('otsu'):
        for tname, pidx in panels['otsu']:
            out.append(
                f'{tname} = mm.otsu('
                f'mm.read("{TMP_DIR}/{base}_{pidx}.png", grayscale=True))'
            )
    out += ['mm.show(', '    [']
    for i in range(n):
        out.append(f'        mm.read("{TMP_DIR}/{base}_{i}.png"),')
    out.append('    ],')
    if panels['titles'] is not None:
        out.append('    titles=[')
        for kind, text in panels['titles']:
            out.append(f'        {text if kind == "fstr" else repr(text)},')
        out.append('    ],')
    for k in _MM_SHOW_GLUE_KWARGS:
        if k in kw:
            out.append(f'    {k}={kw[k]},')
    out.append(')')
    return out


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
        r'^(?:<!--\s*)?[#\s`]*#\[\s*[\w.]+\s*\]#`?\s*(?:-->)?\s*$', re.MULTILINE
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

    def _iter_foreign_candidate_cells(self, nb, combo: Combo) -> list:
        """
        Replica, sem produzir saída, os mesmos filtros que o loop principal
        de `process()` aplica antes de chamar `_expand_foreign_code_cell` —
        usado só pela detecção de variáveis mm::Image entre células (ver
        `_detect_cross_cell_mm_vars`). Devolve [(idx, src), ...] na ordem
        original de `nb.cells`, onde `idx` é o índice em `nb.cells` (mesmo
        índice usado como `cell_idx` no loop de `process()`).
        """
        out = []
        for idx, cell in enumerate(nb.cells):
            cell = copy.deepcopy(cell)
            role = _cell_role(cell)
            if not self._filter_by_language_marker(cell, combo):
                continue
            src = _get_source(cell)
            if role == 'base_only' and not combo.is_base():
                continue
            if cell.cell_type == 'raw':
                continue
            if not (role == 'code' and cell.cell_type == 'code'):
                continue
            if _ep_placeholder_name(src) is not None:
                continue
            if _ep_testsuite_call_name(src) is not None:
                continue
            if not _is_eligible_for_foreign_expansion(src):
                continue
            out.append((idx, src))
        return out

    def _detect_cross_cell_mm_vars(self, nb, combo: Combo) -> dict:
        """
        Varre as células elegíveis pra expansão em combo.lang, em ordem, e
        detecta variáveis `mm::Image` atribuídas numa célula e referenciadas
        (sem atribuição local) numa célula POSTERIOR. Conservador por
        construção: perder um caso (aliasing simples, `.copy()`, mais de um
        hop) só custa uma otimização perdida — a célula cai no fallback
        `_reference_only_cell` já existente, nunca quebra o build.

        Devolve {'records': {"<var>#<producer_idx>": {...}}, ...} — ver
        _expand_foreign_code_cell pra como é consumido.
        """
        records: dict = {}
        by_producer_idx: dict = {}
        by_consumer_idx: dict = {}
        active_producers: dict = {}  # nome -> producer_idx mais recente

        for cell_idx, src in self._iter_foreign_candidate_cells(nb, combo):
            try:
                tree = ast.parse(src)
            except SyntaxError:
                continue

            produced_this_cell = _detect_mm_image_produced(tree)
            for name in produced_this_cell:
                active_producers[name] = cell_idx

            locally_bound = _locally_bound_names(tree)
            referenced = {
                node.id for node in ast.walk(tree)
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
            }

            for name in referenced:
                if name in locally_bound or name in _NON_VAR_NAMES:
                    continue
                producer_idx = active_producers.get(name)
                if producer_idx is None or producer_idx == cell_idx:
                    continue
                key = f'{name}#{producer_idx}'
                record = records.setdefault(key, {
                    'var_name': name, 'producer_idx': producer_idx, 'consumer_idxs': [],
                })
                if cell_idx not in record['consumer_idxs']:
                    record['consumer_idxs'].append(cell_idx)
                by_producer_idx.setdefault(producer_idx, [])
                if key not in by_producer_idx[producer_idx]:
                    by_producer_idx[producer_idx].append(key)
                by_consumer_idx.setdefault(cell_idx, [])
                if key not in by_consumer_idx[cell_idx]:
                    by_consumer_idx[cell_idx].append(key)

        return {
            'records': records,
            'by_producer_idx': by_producer_idx,
            'by_consumer_idx': by_consumer_idx,
        }

    def _expand_foreign_code_cell(self, cell, src: str, combo: Combo,
                                   code_tr, ctx: dict, cell_idx: int) -> list:
        """
        Expande UMA célula Python narrativa em N células executáveis pro
        combo.lang (write/compilar+rodar/[exibir]) — só chamada quando
        combo.lang != BASE_LANG e a célula não é placeholder de EP nem
        role 'common'. Ver notebook_processor.py (docstring do módulo) e o
        plano em giggly-wandering-squirrel.md pra desenho completo (state/
        entre células) e em snuggly-wishing-origami.md pro desenho original.
        """
        if not _is_eligible_for_foreign_expansion(src):
            return self._reference_only_cell(cell, src, combo)

        ext = LANGUAGES[combo.lang].extension
        base = _cell_base_name(src, ctx)
        needs_glue = bool(_MM_SHOW_RE.search(src))
        # `mm.show([v1, v2, ...], titles=[...])` — exibir os painéis
        # individualmente na glue (com título/eixo) em vez do composto
        # achatado do mm::show C++. None → composto único (comportamento
        # padrão). Confirmado/descartado após a injeção compilar.
        panels = _parse_mm_show_panels(src) if needs_glue else None
        # Artefatos de build da trilha compilada (fonte gerada, binário,
        # PNG intermediário do MM_OUT e state/ entre células) ficam em
        # tmp/ para não poluir o diretório do capítulo. A pasta é criada
        # na célula de configuração (os.makedirs("tmp/state")). Ver
        # também inject_producer_writes/inject_consumer_reads.
        png_name = f'{TMP_DIR}/{base}.png'

        cross = ctx.get('cross_cell_vars') or {
            'records': {}, 'by_producer_idx': {}, 'by_consumer_idx': {},
        }
        records = cross['records']
        produced_keys = cross['by_producer_idx'].get(cell_idx, [])
        consumed_keys = cross['by_consumer_idx'].get(cell_idx, [])

        # Dependência de EXECUÇÃO, não só de compilação: se o produtor de
        # alguma variável consumida aqui já caiu pra referência, o arquivo
        # state/... nunca vai existir em tempo de execução — essa célula
        # também precisa cair, senão mm::read lançaria em runtime e
        # derrubaria o render do Quarto inteiro (não só essa figura).
        failed_producers = ctx.setdefault('failed_producers', set())
        if consumed_keys and any(k in failed_producers for k in consumed_keys):
            return self._reference_only_cell(cell, src, combo)

        external_vars = sorted({records[k]['var_name'] for k in consumed_keys})
        persisted_vars = sorted({records[k]['var_name'] for k in produced_keys})

        # output_image_path precisa ir pro translate() ANTES da checagem de
        # compilação (Fase 3) — se o #define MM_OUT só fosse prefixado
        # depois, toda célula com mm.show() reprovaria a validação por
        # "MM_OUT não declarado", um motivo que não tem nada a ver com a
        # qualidade da tradução em si.
        translated = code_tr.translate(
            src, output_image_path=png_name if needs_glue else None,
            external_vars=external_vars or None,
            persisted_vars=persisted_vars or None,
        )
        if translated == src:
            # LLMCodeTranslator devolve o Python original quando a
            # compilação de validação falha (Fase 3) — rede de segurança:
            # nunca expandir em cima de uma tradução ruim.
            return self._reference_only_cell(cell, src, combo)

        if produced_keys or consumed_keys:
            # Injeção mecânica de state/<var>_<idx>.png (nunca pelo LLM) —
            # validada por um SEGUNDO compile_check, independente do que já
            # rodou dentro de code_tr.translate() e sem tocar o cache dele
            # (o cache guarda só a tradução pré-mutação).
            mutated = translated
            if consumed_keys:
                mutated = inject_consumer_reads(mutated, [records[k] for k in consumed_keys])
            if mutated is not None and produced_keys:
                mutated = inject_producer_writes(mutated, persisted_vars, cell_idx)

            ok = mutated is not None
            if ok:
                from .exec_validate import compile_check
                ok, err = compile_check('cpp', mutated)
                if not ok:
                    print(f'  ⚠ Injeção state/ falhou ao compilar; célula cai para referência.\n{err[:800]}')
            if not ok:
                failed_producers.update(produced_keys)
                return self._reference_only_cell(cell, src, combo)
            translated = mutated

        if panels is not None:
            # Injeção mecânica de um mm::write por painel (nunca pelo LLM),
            # validada por compile_check próprio — como a de state/. Se não
            # compilar (ex.: LLM renomeou uma variável da lista), cai pro
            # composto único sem quebrar o build.
            from .exec_validate import compile_check
            panel_mut = inject_panel_writes(translated, panels['names'], base)
            ok = panel_mut is not None
            if ok:
                ok, err = compile_check('cpp', panel_mut)
                if not ok:
                    print(f'  ⚠ Injeção de painéis não compilou; usando '
                          f'composto único.\n{err[:400]}')
            if ok:
                translated = panel_mut
            else:
                panels = None

        write_cell = copy.deepcopy(cell)
        _set_source(write_cell, f'%%writefile {TMP_DIR}/{base}{ext}\n{translated}')

        # `-I.` : com o .cpp em tmp/, o `#include "morph.hpp"` precisa do
        # diretório do capítulo no include path. Binário e execução também
        # em tmp/ (cwd continua o diretório do capítulo).
        #
        # Quebrado em várias linhas com `\` (continuação de shell, aceita
        # pelo `!` do IPython) pra nenhuma linha passar de ~90 colunas e
        # estourar a margem direita no PDF.
        run_parts = [
            f'!g++ -I. {TMP_DIR}/{base}{ext} -o {TMP_DIR}/{base}',
            f'./{TMP_DIR}/{base}',
        ]
        if needs_glue:
            run_parts.append(f'test -f "{png_name}"')
        run_line = ' \\\n  && '.join(run_parts)
        if needs_glue:
            run_line += f' \\\n  || echo "⚠ mm::show não gravou {png_name}"'
        run_cell = new_code_cell(run_line)

        out = [write_cell, run_cell]
        if needs_glue:
            fig_opts = _figure_option_lines(src)
            if panels is not None:
                # Painéis individuais (mm::write injetado acima) → reproduz
                # a figura Python com títulos/eixos, em vez do composto
                # achatado e sem texto do mm::show C++.
                glue_lines = fig_opts + _panels_glue_lines(base, panels)
            else:
                # Composto único (imagem só, ou fallback de painéis). Usa o
                # MESMO figsize da célula Python original — e OMITE quando o
                # original omite — pra o morph.py dimensionar igual nas duas
                # trilhas (senão a figura C++ sai com tamanho diferente da
                # py). Substitui IPython.display.Image (que mostraria o PNG
                # no tamanho nativo — o mm::show C++ compõe em escala 1:1
                # pixel, morph.hpp).
                fs = _parse_mm_show_figsize(src)
                call = f'mm.show(mm.read("{png_name}")'
                call += f', figsize={fs})' if fs else ')'
                glue_lines = fig_opts + [call]
            glue_cell = new_code_cell('\n'.join(glue_lines))
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

        _cap_name = Path(nb_path).parent.name          # ex.: 'cap01'
        _is_eps = '.EPs.' in Path(nb_path).name

        code_tr = self._factory.code_translator(combo.lang, combo.locale)
        text_tr = self._factory.text_translator(combo.locale)

        used_keys: set = set()
        out_cells = []
        # Só custa a varredura AST quando de fato pode haver mm::Image
        # cruzando células (combos cpp) — ver _detect_cross_cell_mm_vars.
        cross_cell_vars = (self._detect_cross_cell_mm_vars(nb, combo)
                            if combo.lang == 'cpp' else
                            {'records': {}, 'by_producer_idx': {}, 'by_consumer_idx': {}})
        expand_ctx: dict = {'cross_cell_vars': cross_cell_vars}

        for cell_idx, cell in enumerate(nb.cells):
            cell = copy.deepcopy(cell)
            role = _cell_role(cell)
            src  = _get_source(cell)


            # --- Filtro por marcador de linguagem/idioma ---
            if not self._filter_by_language_marker(cell, combo):
                continue

            src = _get_source(cell)  # ← adicionar esta linha

            # ── Badge "Executar no Colab" → aponta pro caderno de aluno do
            # combo (sempre <lang>.pt; não há en/fr de aluno).
            if (cell.cell_type == 'markdown'
                    and 'colab.research.google.com/github' in src):
                src = _fix_colab_badge(src, _cap_name, _is_eps, combo.lang)
                _set_source(cell, src)

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
                        cell, src, combo, code_tr, expand_ctx, cell_idx
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

            elif role == 'common' and cell.cell_type == 'code' and combo.locale != BASE_LOCALE:
                # 'common' mantém o código idêntico entre combos de LINGUAGEM
                # (nunca vira cpp/java/c) — mas os comentários ainda precisam
                # seguir o locale, senão sobra Português em EPs.ipynb de
                # qualquer combo não-pt (mesmo lang == BASE_LANG).
                comment_tr = self._factory.code_translator(BASE_LANG, combo.locale)
                translated = comment_tr.translate(src)
                self._tag_cache_key(cell, src, comment_tr)
                _set_source(cell, translated)

            elif role == 'common' and cell.cell_type == 'markdown' and combo.locale != BASE_LOCALE:
                # Mesma lógica acima, mas pro texto: 'common' compartilha a
                # prosa entre combos de linguagem, porém ela ainda precisa
                # seguir o locale (ex.: instruções "como rodar Java/C++/R no
                # Colab" em cap01.EPs.ipynb), senão sobra Português em
                # qualquer combo não-pt.
                translated = text_tr.translate(src)
                self._tag_cache_key(cell, src, text_tr)
                if not combo.is_base():
                    translated = postprocess_markdown(translated, self._bib, used_keys)
                _set_source(cell, translated)

            # common (locale == pt) → sem alteração

            _clean_cell(cell, is_base=combo.is_base())

            if _get_source(cell).strip():
                out_cells.append(cell)

        nb.cells = out_cells

        # --- Mesclagem do notebook de exercícios (EPs) ---
        nb = self._merge_ep_notebook(nb, Path(nb_path), combo)

        return nb