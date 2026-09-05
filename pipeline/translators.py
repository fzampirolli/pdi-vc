"""
pipeline/translators.py
=======================
Padrão Strategy: cada tradutor é uma classe que implementa translate().

Hierarquia:
    Translator (ABC)
    ├── CodeTranslator     — converte código Python → outra linguagem
    │   ├── PythonPassthrough   (identidade — py→py)
    │   ├── LLMCodeTranslator   (py → cpp | java | c  via Anthropic API)
    │   └── (extensível: adicionar KotlinTranslator, etc.)
    └── TextTranslator     — traduz texto Markdown entre idiomas
        ├── PassthroughText     (identidade — pt→pt)
        └── LLMTextTranslator   (pt → en | fr | it | es  via Anthropic API)

O LLM é chamado apenas quando não há cache.
"""

from __future__ import annotations

import ast
import difflib
import io
import json
import os
import random
import re
import textwrap
import tokenize
from abc import ABC, abstractmethod
from html.parser import HTMLParser
from typing import Optional

from .cache import TranslationCache
from .config import BASE_LANG, BASE_LOCALE, LANGUAGES, LOCALES

# ─────────────────────────────────────────────────────────────────────────────
# Utilitário: chamada à API Anthropic
# ─────────────────────────────────────────────────────────────────────────────

def _call_llm_claude(system: str, user: str, max_tokens: int = 4096) -> str:
    """
    Chama claude-sonnet-5 via Anthropic Python SDK.
    Requer variável de ambiente ANTHROPIC_API_KEY.
    """
    try:
        import anthropic
    except ImportError:
        raise ImportError("pip install anthropic")

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    msg = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return msg.content[0].text.strip()


def _call_llm(system: str, user: str, max_tokens: int = 4096) -> str:
    """
    Chama DeepSeek via API compatível com OpenAI.
    Requer variável de ambiente DEEPSEEK_API_KEY.
    """
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("pip install openai")

    client = OpenAI(
        api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
        base_url="https://api.deepseek.com",
    )
    response = client.chat.completions.create(
        model="deepseek-chat",
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
    )
    return response.choices[0].message.content.strip()


def _call_llm_retrying_if_unchanged(system: str, user: str, original: str,
                                    max_tokens: int = 4096, retries: int = 2) -> str:
    """
    Chama `_call_llm` e, se o resultado vier IDÊNTICO a `original` (sinal de
    que o modelo só ecoou o texto-fonte em vez de traduzir), tenta de novo
    com um nonce aleatório prefixado ao prompt.

    Motivo: a API do DeepSeek cacheia contexto do lado do servidor — um par
    (system, user) repetido byte a byte pode voltar com a resposta cacheada
    de uma chamada anterior. Reproduzido na prática: um texto que "traduziu"
    pra Français devolvendo o Português sem alteração nenhuma, de forma
    determinística (3 tentativas idênticas, mesmo resultado) — variar o
    prompt com um nonce quebrou o cache e traduziu corretamente de primeira.
    Não corrige um erro de tradução em si, só o eco do texto original.
    """
    result = _call_llm(system, user, max_tokens)
    attempt = 0
    while result.strip() == original.strip() and attempt < retries:
        attempt += 1
        nonce = f'[req {random.randint(100000, 999999)}] '
        result = _call_llm(system, nonce + user, max_tokens)
    return result

# ─────────────────────────────────────────────────────────────────────────────
# Proteção de tokens "@..." (citações e cross-refs Quarto: @fig-x, @tbl-x,
# @eq-x, @chave-bib) contra alteração pelo LLM de tradução.
#
# A instrução "preserve @fig-X-Y unchanged" no prompt nem sempre é obedecida
# à risca — o "@" às vezes é descartado pelo modelo (observado em produção:
# "@fig-01-representacao" virou "fig-01-representacao" na tradução en/fr,
# quebrando o link e a numeração da figura). Mascarar o token antes de
# mandar pro LLM e restaurar depois é uma garantia estrutural, não depende
# de o modelo seguir a instrução corretamente.
# ─────────────────────────────────────────────────────────────────────────────

_PROTECTED_TOKEN_RE = re.compile(
    r'\[-?@[^\]]*\]'                      # citação/crossref entre colchetes: [@key], [-@fig-x], [@k1; @k2]
    r'|\{#[\w-]+\}'                       # rótulo Quarto: {#fig-x}
    r'|@[A-Za-z][\w:.#$%&\-+?<>~/]*'      # citação/crossref solto: @fig-x, @key
)
_MASK_PLACEHOLDER_RE = re.compile(r'ZQREF(\d+)Z')


def _mask_protected_tokens(text: str) -> tuple[str, list[str]]:
    tokens: list[str] = []

    def _repl(m: re.Match) -> str:
        tokens.append(m.group(0))
        return f'ZQREF{len(tokens) - 1}Z'

    return _PROTECTED_TOKEN_RE.sub(_repl, text), tokens


def _unmask_protected_tokens(text: str, tokens: list[str]) -> str:
    def _repl(m: re.Match) -> str:
        idx = int(m.group(1))
        return tokens[idx] if idx < len(tokens) else m.group(0)

    return _MASK_PLACEHOLDER_RE.sub(_repl, text)


_MM_OUT_LINE_RE = re.compile(r'^#define MM_OUT "[^"]*"\n')


def _apply_mm_out(code: str, path: Optional[str]) -> str:
    """
    Normaliza a linha `#define MM_OUT "<path>"` no topo do C++ traduzido.

    MM_OUT é detalhe de deploy (onde o binário grava o PNG — hoje em tmp/),
    não da tradução em si: NUNCA entra na chave nem no valor do cache. É
    removida antes do `cache.set` e reaplicada (com o path atual) tanto no
    cache-hit quanto no retorno da tradução nova. Assim mudar o diretório
    de saída não invalida o cache de tradução.
    """
    code = _MM_OUT_LINE_RE.sub('', code, count=1)
    if path:
        code = f'#define MM_OUT "{path}"\n' + code
    return code

# ─────────────────────────────────────────────────────────────────────────────
# ABC base
# ─────────────────────────────────────────────────────────────────────────────

class Translator(ABC):
    def __init__(self, cache: TranslationCache, dry_run: bool = False):
        self.cache = cache
        self.dry_run = dry_run   # se True, retorna placeholder sem chamar API

    @abstractmethod
    def translate(self, source: str, **kwargs) -> str: ...

    @property
    @abstractmethod
    def kind(self) -> str: ...     # 'code' ou 'text'

    @property
    @abstractmethod
    def src_key(self) -> str: ...  # ex: 'py'

    @property
    @abstractmethod
    def tgt_key(self) -> str: ...  # ex: 'cpp'


# ─────────────────────────────────────────────────────────────────────────────
# Code Translators  (Strategy: código)
# ─────────────────────────────────────────────────────────────────────────────

class PythonPassthrough(Translator):
    """py → py: identidade."""
    kind = 'code'; src_key = 'py'; tgt_key = 'py'

    def translate(self, source: str, **_) -> str:
        return source


class LLMCodeTranslator(Translator):
    """
    Converte código Python para outra linguagem usando LLM.
    Preserva comentários (traduzidos para o locale alvo), docstrings e
    lógica algorítmica.
    """
    kind = 'code'
    src_key = 'py'

    def __init__(self, tgt_lang: str, tgt_locale: str, cache: TranslationCache,
                 dry_run: bool = False):
        super().__init__(cache, dry_run)
        self._tgt_lang = tgt_lang
        self._tgt_locale = tgt_locale

    @property
    def tgt_key(self) -> str:
        # Inclui o locale na chave: sem isso, um build cpp.pt e um cpp.en
        # colidiriam no mesmo cache e um dos dois sairia com comentário no
        # idioma errado.
        return f'{self._tgt_lang}.{self._tgt_locale}'

    def translate(self, source: str, output_image_path: Optional[str] = None,
                  external_vars: Optional[list[str]] = None,
                  persisted_vars: Optional[list[str]] = None, **_) -> str:
        """
        `output_image_path`: quando a célula original chama mm.show(...), o
        chamador (NotebookProcessor) já sabe o nome do PNG (derivado do
        próprio #| label: da célula) e passa aqui — precisa estar presente
        ANTES da checagem de compilação (senão MM_OUT não está definido e
        toda célula com mm::show() reprovaria na validação por um motivo
        que não tem nada a ver com a tradução em si).

        `external_vars`/`persisted_vars`: nomes de variáveis `mm::Image`
        que atravessam células (ver
        `notebook_processor._detect_cross_cell_mm_vars`) — só avisam o LLM
        pra não redeclarar/renomear; a persistência real (mm::write/
        mm::read em state/) é injetada mecanicamente DEPOIS deste método
        retornar, em `notebook_processor._expand_foreign_code_cell`, e por
        isso propositalmente NÃO entram na chave de cache (mesma escolha
        já feita pra `output_image_path`) — o grafo de dependência entre
        células pode mudar sem o texto desta célula mudar, e recalcular a
        injeção a cada build (barata, mecânica) é mais seguro que arriscar
        uma dica de prompt desatualizada presa num cache hit.
        """
        if not source.strip():
            return source

        # Cache hit?
        cached = self.cache.get(source, self.kind, self.src_key, self.tgt_key)
        if cached is not None:
            if self._tgt_lang == 'cpp':
                return _apply_mm_out(cached, output_image_path)
            return cached

        if self.dry_run:
            # Não grava no cache: é só uma prévia, não pode "grudar" e ser
            # reaproveitada por uma execução real posterior.
            return f'// [TODO: traduzir Python → {self.tgt_key}]\n{source}'

        lang_obj = LANGUAGES.get(self._tgt_lang)
        lang_label = lang_obj.label if lang_obj else self._tgt_lang
        locale_obj = LOCALES.get(self._tgt_locale)
        locale_label = locale_obj.label if locale_obj else self._tgt_locale

        if self._tgt_lang == 'cpp':
            # Só as células já filtradas por elegibilidade (ver
            # notebook_processor._is_eligible_for_foreign_expansion) chegam
            # aqui — por isso a cheat-sheet pode ser fechada nesta lista
            # exata, sem precisar cobrir o resto da morph.py.
            mm_cheatsheet = textwrap.dedent("""
                When translating code that uses the `mm.*` didactic image
                library, target this exact C++ API (already available via
                `#include "morph.hpp"` — no other includes needed for it):

                  mm::Image                                             // .h, .w, .channels, .data; .at(y,x,c)
                  mm::Image mm::read(std::string path_or_url, bool grayscale=false)
                  mm::Image mm::gray(const mm::Image&)
                  mm::Image mm::randomImage(int h, int w, int maxValue=9)
                  void      mm::show(const mm::Image&, std::string out_path, std::string title="")
                  void      mm::show(const std::vector<mm::Image>&, std::string out_path,
                                      std::vector<std::string> titles={}, int cols=3)
                  void      mm::write(const mm::Image&, std::string path)
                  mm::Image mm::threshold(const mm::Image&, std::optional<int> limiar=std::nullopt)  // Otsu if omitted
                  int       mm::otsu(const mm::Image&)                  // Otsu threshold value T (same T mm::threshold uses)
                  std::string mm::drawImg(const mm::Image&)

                Rules:
                - `mm::Image` already holds raw pixel data; there is no
                  `pil=` concept in Python's mm.read(url, pil=True) — drop it.
                - For every call to mm::show(...), pass the literal macro
                  token MM_OUT as the out_path argument (a
                  #define MM_OUT "..." line will be prepended for you
                  automatically) — never invent a filename yourself.
                - Do NOT use OpenCV. Do NOT #include anything beyond
                  "morph.hpp" and the C++ standard library. In particular,
                  `T, bin = cv2.threshold(img, 0, 255, THRESH_BINARY+THRESH_OTSU)`
                  maps to two lines:
                    int T = mm::otsu(img);
                    mm::Image bin = mm::threshold(img);   // same T, Otsu when the arg is omitted
                  `mm::otsu` returns the computed threshold, so KEEP a
                  `print(f'... T = {T_otsu}')` — translate it to
                  `std::cout << "... T = " << T_otsu << "\\n";`.
                  Do NOT change the mm::show(...) call to carry T: keep its
                  titles exactly as the simple flat vector they already are
                  (a plain "Binária (Otsu)" element is fine) — the signature
                  is still mm::show(std::vector<mm::Image>{...}, MM_OUT,
                  std::vector<std::string>{...}, cols); never drop MM_OUT,
                  never spread the titles out as separate arguments.
                - Do NOT invent mm:: functions beyond the list above — in
                  particular there is NO mm::zeros / mm::ones. NumPy array
                  creation and indexing map directly onto mm::Image, which
                  is already zero-initialized:
                    np.zeros((h, w), dtype='uint8')   ->  mm::Image img(h, w);
                    np.ones((h, w), dtype='uint8')*255 -> mm::Image img(h, w); std::fill(img.data.begin(), img.data.end(), 255);
                    img[y, x] = v                     ->  img.at(y, x) = v;
                    img[y, x, ch] / img[y, x][ch]     ->  img.at(y, x, ch)   (ch: 0=R,1=G,2=B)
                    img.copy()                        ->  mm::Image c = img;  (mm::Image tem semântica de valor)
                - `img.at(...)` devolve `unsigned char` — para IMPRIMIR o
                  valor numérico, faça o cast: `std::cout << (int)img.at(y,x)`
                  (sem o cast, o std::cout imprime o caractere, não o número).
                - Python keyword arguments (e.g. maxValue=255) have no C++
                  equivalent here — pass the value positionally instead
                  (e.g. mm::randomImage(4, 6, 255)), in the same parameter
                  order as the signatures above.
            """).strip()
            if external_vars:
                mm_cheatsheet += '\n\n' + (
                    'Still write a COMPLETE, self-contained program exactly '
                    'as usual — all necessary #include lines, and your own '
                    '`int main() { ... }` wrapping all the logic below, '
                    'exactly like every other translation. The only '
                    'difference: the variables below will be assigned a '
                    'valid value by a line inserted automatically as the '
                    'VERY FIRST statement inside your `int main() {` — as if '
                    'they were already initialized right there. Do NOT '
                    'declare or initialize them yourself, do NOT call '
                    'mm::read/mm::gray/etc. to obtain them, just reference '
                    'them directly in your logic as already-valid variables:\n'
                    + '\n'.join(f'  - {v} (mm::Image)' for v in sorted(external_vars))
                )
            if persisted_vars:
                mm_cheatsheet += '\n\n' + (
                    'The variables below must still hold their final, '
                    'fully-computed value at the end of your `main()` (a '
                    'line will be appended automatically, after all your '
                    'code, to persist them) — do not rename them, reassign '
                    'them to something else, or let them go out of scope '
                    'before the end of `main()`:\n'
                    + '\n'.join(f'  - {v} (mm::Image)' for v in sorted(persisted_vars))
                )
            system = textwrap.dedent(f"""
                You are an expert programming language converter.
                Convert Python code to {lang_label}, following these rules:
                - Preserve ALL comments, translating their text into {locale_label}
                - Preserve algorithm logic exactly
                - Use idiomatic {lang_label} style and standard library
                - Return ONLY the translated code, no markdown fences, no explanation
                - Add a one-line compile/run comment at the top if applicable

                {mm_cheatsheet}
            """).strip()
        else:
            system = textwrap.dedent(f"""
                You are an expert programming language converter.
                Convert Python code to {lang_label}, following these rules:
                - Preserve ALL comments, translating their text into {locale_label}
                - Preserve algorithm logic exactly
                - Use idiomatic {lang_label} style and standard library
                - For image processing: use OpenCV ({lang_label} bindings)
                - For morph.py functions: implement equivalent logic in {lang_label}
                - Return ONLY the translated code, no markdown fences, no explanation
                - Add a one-line compile/run comment at the top if applicable
            """).strip()

        user = f"Convert this Python code to {lang_label}:\n\n{source}"

        result = _call_llm_retrying_if_unchanged(system, user, source)
        # Strip markdown fences if LLM added them
        result = re.sub(r'^```\w*\n?', '', result, flags=re.MULTILINE)
        result = re.sub(r'\n?```$', '', result, flags=re.MULTILINE)
        result = result.strip()

        result = self._filter_lang_directives(result, self._tgt_lang)

        if self._tgt_lang == 'cpp':
            # `#define MM_OUT` entra só pro compile_check abaixo e no
            # retorno — NUNCA no `result` que vai pro cache (ver
            # _apply_mm_out). Assim trocar o diretório de saída do PNG
            # (ex.: mover pra tmp/) não invalida o cache de tradução.

            # Rede de segurança: sem isso, uma tradução C++ quebrada seria
            # cacheada e só apareceria como erro no dia do render (ou nem
            # isso — o kernel Python não entende C++, então falha
            # silenciosamente). Nunca cacheia uma tradução que não compila;
            # devolve o Python original, que o chamador (NotebookProcessor)
            # reconhece como "tradução indisponível" por comparação de
            # igualdade, sem precisar de um segundo canal de erro.
            #
            # `external_vars`: o código gerado genuinamente NÃO declara essas
            # variáveis em lugar nenhum (o prompt pede pra tratá-las como já
            # disponíveis) — sem um stub aqui, este compile_check reprovaria
            # por "não declarado" uma tradução correta. O stub existe só pra
            # esta checagem; nunca é cacheado nem chega ao chamador (a
            # injeção REAL, com o caminho de state/ de verdade, acontece
            # depois, em NotebookProcessor._expand_foreign_code_cell, com seu
            # próprio compile_check independente sobre o código já mutado).
            from .exec_validate import compile_check, inject_stub_declares
            check_target = _apply_mm_out(result, output_image_path)
            if external_vars:
                check_target = inject_stub_declares(check_target, external_vars)
                if check_target is None:
                    print('  ⚠ Não achei int main() pra stubar external_vars; mantendo código original.')
                    return source
            ok, err = compile_check('cpp', check_target)
            if not ok:
                print(f'  ⚠ Compilação C++ falhou; mantendo código original.\n{err[:800]}')
                return source

        self.cache.set(source, self.kind, self.src_key, self.tgt_key, result)

        if self._tgt_lang == 'cpp':
            return _apply_mm_out(result, output_image_path)
        return result

    def _filter_lang_directives(self, code: str, target_lang: str) -> str:
        """Remove comentários de diretivas que não são para a linguagem alvo"""
        import re
        
        # Lista de linguagens que têm diretivas especiais
        all_langs = ['cpp', 'java', 'c', 'rust', 'go']
        
        # Para cada linguagem que NÃO é o alvo, remove suas diretivas
        for lang in all_langs:
            if lang != target_lang:
                # Remove linhas que começam com # @lang: ou // @lang:
                code = re.sub(r'(?m)^\s*(#|//)\s*@' + lang + r'\s+.*$\n?', '', code)
                # Remove // @lang: no meio da linha
                code = re.sub(r'\s*(//|#)\s*@' + lang + r'\s+[^\n]*', '', code)
        
        # Limpa linhas vazias extras
        code = re.sub(r'\n\s*\n+', '\n\n', code)
        
        return code
    
_DISPLAY_STRING_KWARGS = {'title', 'titles'}


def _string_literal_spans(node, _offset, source: str) -> list[tuple[int, int, str]]:
    """
    Span(s) de string literal de `node` (`ast.Constant` str ou `ast.JoinedStr`
    f-string) — inclui aspas/prefixo `f`, pronto pra mandar pro LLM igual a
    um span de comentário/docstring. Vazio se `node` não é uma string
    literal (ex.: variável, expressão) — nesse caso não há o que traduzir.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        start = _offset(node.lineno, node.col_offset)
        end = _offset(node.end_lineno, node.end_col_offset)
        return [(start, end, source[start:end])]

    if isinstance(node, ast.JoinedStr):
        # NÃO devolver a f-string inteira: se o LLM recebe `f"{nome:<18}"` ele
        # "traduz" o nome da variável (nome→nom, dados→données) e o código
        # quebra com NameError em tempo de execução — sem falhar o ast.parse,
        # então a rede de segurança de sintaxe não pega. Extrai só os pedaços
        # LITERAIS (ast.Constant entre os `{...}`); os FormattedValue nunca vão
        # pro LLM. Posições internas de f-string são confiáveis no Python 3.12
        # (PEP 701).
        out: list[tuple[int, int, str]] = []
        for part in node.values:
            if not (isinstance(part, ast.Constant) and isinstance(part.value, str)):
                continue
            if not part.value.strip():
                continue
            try:
                start = _offset(part.lineno, part.col_offset)
                end = _offset(part.end_lineno, part.end_col_offset)
            except Exception:
                continue
            if 0 <= start < end <= len(source):
                out.append((start, end, source[start:end]))
        return out

    return []


def _extract_comment_spans(source: str) -> list[tuple[int, int, str]]:
    """
    Localiza, no código-fonte Python `source`, todo comentário de linha
    (`#...`), toda docstring (módulo, classe ou função) e toda string
    literal exibida ao usuário — argumentos de `print(...)` e os kwargs
    `title=`/`titles=` de `mm.show(...)` — devolvendo uma lista ordenada de
    (start, end, texto_original) — `start`/`end` são offsets de CARACTERE
    no `source` original.

    Só strings LITERAIS (`"..."` ou f-string) contam — uma variável ou
    expressão passada pra `print()`/`title=` não é uma string traduzível,
    fica de fora por construção (não dá pra saber o que ela vai conter em
    tempo de execução). Escopo deliberadamente restrito a print/title: são
    os únicos lugares onde texto solto em código vira saída visível pro
    aluno; qualquer outra string literal (caminho de arquivo, modo de
    abertura, chave de dicionário) é preservada intacta.

    Usar offsets do texto original (em vez de linha/coluna recalculada a
    cada substituição) é o que permite reconstruir o arquivo por fatiamento
    simples, garantindo que tudo fora dos spans permaneça byte a byte
    idêntico ao original.
    """
    lines = source.splitlines(keepends=True)
    line_starts = [0]
    for line in lines:
        line_starts.append(line_starts[-1] + len(line))

    def _offset(row: int, col: int) -> int:
        return line_starts[row - 1] + col  # tokenize usa offset de CARACTER, linha 1-based

    def _ast_offset(row: int, byte_col: int) -> int:
        # ast.col_offset/end_col_offset são offsets em BYTES utf-8 dentro da
        # linha (documentado, diferente de tokenize) — precisam ser
        # convertidos pra offset de caractere antes de indexar `source`
        # (str), senão qualquer acento antes/dentro do span desalinha a
        # fatia (ex.: span de f-string com "ç"/"õ" engolindo o caractere
        # seguinte, tipicamente o `)` que fecha o print()).
        line = lines[row - 1] if row - 1 < len(lines) else ''
        char_col = len(line.encode('utf-8')[:byte_col].decode('utf-8'))
        return line_starts[row - 1] + char_col

    spans: list[tuple[int, int, str]] = []

    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type == tokenize.COMMENT:
                # Diretivos de célula Quarto (`#| chave: valor`) são, por
                # padrão, dados de máquina — não texto — e nunca podem
                # passar pelo LLM: `label:` é o identificador de
                # cross-reference (usado por @fig-... e pelo pareamento de
                # nome de arquivo em _symlink_imagens_locale_aware /
                # _screenshot_png_path); `echo:`/`eval:`/`output:`/
                # `quarto-raw:` são booleanos literais (`true`/`false`) que
                # o Quarto exige inalterados — um build fr real pegou
                # `quarto-raw: true` virando `quarto-raw: vrai`, quebrando o
                # parser de fenced div (só aparece em locales onde "true"
                # tem tradução; en mascarava o bug por coincidência).
                # `out-width:` é um valor numérico/percentual. Só
                # `fig-cap:`/`tbl-cap:` (a legenda) têm texto de verdade e
                # devem mesmo ser traduzidos — protege por padrão, com essas
                # duas exceções, em vez de tentar listar cada diretivo de
                # dado que possa aparecer no futuro.
                if re.match(r'#\|\s*[a-zA-Z_-]+\s*:', tok.string) and not re.match(r'#\|\s*(fig-cap|tbl-cap)\s*:', tok.string):
                    continue
                spans.append((_offset(*tok.start), _offset(*tok.end), tok.string))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        pass

    try:
        tree = ast.parse(source)
    except SyntaxError:
        tree = None

    if tree is not None:
        doc_holders = [tree] + [
            n for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        ]
        for node in doc_holders:
            if not node.body:
                continue
            first = node.body[0]
            if (isinstance(first, ast.Expr)
                    and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)):
                const = first.value
                start = _ast_offset(const.lineno, const.col_offset)
                end = _ast_offset(const.end_lineno, const.end_col_offset)
                spans.append((start, end, source[start:end]))

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name) and node.func.id == 'print':
                for arg in node.args:
                    spans.extend(_string_literal_spans(arg, _ast_offset, source))
            elif isinstance(node.func, ast.Attribute) and node.func.attr == 'show':
                for kw in node.keywords:
                    if kw.arg not in _DISPLAY_STRING_KWARGS:
                        continue
                    if isinstance(kw.value, (ast.List, ast.Tuple)):
                        for elt in kw.value.elts:
                            spans.extend(_string_literal_spans(elt, _ast_offset, source))
                    else:
                        spans.extend(_string_literal_spans(kw.value, _ast_offset, source))

    spans.sort(key=lambda s: s[0])
    return spans


# ─────────────────────────────────────────────────────────────────────────────
# Extração de texto SEGURO de simuladores interativos (HTML/JS embutidos)
#
# Um simulador é uma célula `IPython.display.HTML("""...""")` — a string
# inteira contém HTML+CSS+JS (ids referenciados por getElementById, atributos
# de estilo, lógica de interação). Mandar esse blob inteiro pro LLM seria
# arriscado (pode alterar ids, aspas, template literals). Em vez disso,
# igual à extração de comentários acima, localizamos só os pedaços de texto
# realmente seguros de traduzir — por regras mecânicas fixas, nunca por
# decisão do LLM — e devolvemos spans (start, end, texto) no MESMO formato
# de `_extract_comment_spans`, prontos pra fatiamento.
# ─────────────────────────────────────────────────────────────────────────────

_HTML_CALL_QUOTE_RE = re.compile(r'''^[rRbBfFuU]{0,2}('''
                                  + "'''" + r'''|"""|'|")''')

_HAS_PROSE_RE = re.compile(r'[A-Za-zÀ-ÖØ-öø-ÿ]{2,}')


def _looks_translatable(text: Optional[str]) -> bool:
    return bool(text) and bool(_HAS_PROSE_RE.search(text)) and len(text) <= 400


_WIDGET_ATTR_RE = re.compile(
    r'\b(?:title|placeholder|aria-label|alt)\s*=\s*"([^"]*)"'
    r'''|\b(?:title|placeholder|aria-label|alt)\s*=\s*'([^']*)' '''
)

_WIDGET_SCRIPT_BLOCK_RE = re.compile(r'<script\b[^>]*>.*?</script>',
                                      re.IGNORECASE | re.DOTALL)

_WIDGET_TEXTCONTENT_RE = re.compile(
    r'''\.textContent\s*=\s*"([^"\\]*)"|\.textContent\s*=\s*'([^'\\]*)' '''
)

_WIDGET_FILLTEXT_RE = re.compile(
    r'''\bfillText\(\s*"([^"\\]*)"|\bfillText\(\s*'([^'\\]*)' '''
)


class _WidgetHTMLTextExtractor(HTMLParser):
    """
    Extrai nós de texto de um fragmento HTML (fora de <script>/<style>),
    com offset de CARACTERE absoluto dentro do texto original — mesma
    técnica de line_starts usada em `_extract_comment_spans`.
    """

    def __init__(self, source: str):
        super().__init__(convert_charrefs=False)
        self._source = source
        line_starts = [0]
        for line in source.splitlines(keepends=True):
            line_starts.append(line_starts[-1] + len(line))
        self._line_starts = line_starts
        self._skip = 0
        self.spans: list[tuple[int, int, str]] = []

    def _offset(self, line: int, col: int) -> int:
        return self._line_starts[line - 1] + col

    def handle_starttag(self, tag, attrs):
        if tag.lower() in ('script', 'style'):
            self._skip += 1

    def handle_endtag(self, tag):
        if tag.lower() in ('script', 'style') and self._skip > 0:
            self._skip -= 1

    def handle_data(self, data):
        if self._skip or not _looks_translatable(data):
            return
        line, col = self.getpos()
        start = self._offset(line, col)
        end = start + len(data)
        # Defesa: se o offset calculado não reproduzir o texto exato (ex.:
        # entidade HTML no meio confundindo a contagem), descarta o span em
        # vez de arriscar uma posição errada.
        if self._source[start:end] != data:
            return
        self.spans.append((start, end, data))


def _extract_widget_text_spans(html_js_text: str) -> list[tuple[int, int, str]]:
    """
    Localiza, dentro do HTML/JS de um simulador, só o texto seguro de
    traduzir: nós de texto HTML, atributos title/placeholder/aria-label/alt,
    e dois padrões JS bem restritos (`.textContent = "..."` e
    `fillText("...", ...)`) — sempre string literal PURA (nunca
    concatenação nem template literal, que ficam de fora por construção).
    Nunca toca em `id=`, atributos de estilo, nomes de função/variável ou
    qualquer outra lógica JS.
    """
    spans: list[tuple[int, int, str]] = []

    parser = _WidgetHTMLTextExtractor(html_js_text)
    try:
        parser.feed(html_js_text)
        parser.close()
    except Exception:
        pass
    spans.extend(parser.spans)

    for m in _WIDGET_ATTR_RE.finditer(html_js_text):
        group_idx = 1 if m.group(1) is not None else 2
        value = m.group(group_idx)
        if not _looks_translatable(value):
            continue
        spans.append((m.start(group_idx), m.end(group_idx), value))

    script_ranges = [m.span() for m in _WIDGET_SCRIPT_BLOCK_RE.finditer(html_js_text)]
    for pattern in (_WIDGET_TEXTCONTENT_RE, _WIDGET_FILLTEXT_RE):
        for m in pattern.finditer(html_js_text):
            if not any(s <= m.start() < e for s, e in script_ranges):
                continue
            group_idx = 1 if m.group(1) is not None else 2
            value = m.group(group_idx)
            if not _looks_translatable(value):
                continue
            spans.append((m.start(group_idx), m.end(group_idx), value))

    # Remove sobreposições (mantém o primeiro span de cada região; na
    # prática as três fontes acima não deveriam colidir, mas é uma rede de
    # segurança barata contra um regex pegar algo já coberto pelo parser).
    spans.sort(key=lambda s: s[0])
    dedup: list[tuple[int, int, str]] = []
    last_end = -1
    for s, e, t in spans:
        if s < last_end:
            continue
        dedup.append((s, e, t))
        last_end = e
    return dedup


def _extract_widget_spans(source: str) -> list[tuple[int, int, str]]:
    """
    Localiza chamadas HTML(...) com uma string triplamente-citada
    (simuladores interativos embutidos em células de código) no
    código-fonte Python `source` e devolve, pra
    cada uma, os spans de texto seguro de traduzir de dentro delas (ver
    `_extract_widget_text_spans`) — offsets já convertidos pra posição
    absoluta em `source`, no mesmo formato de `_extract_comment_spans`.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    line_starts = [0]
    for line in source.splitlines(keepends=True):
        line_starts.append(line_starts[-1] + len(line))

    def _offset(row: int, col: int) -> int:
        return line_starts[row - 1] + col

    spans: list[tuple[int, int, str]] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == 'HTML' and len(node.args) == 1
                and not node.keywords):
            continue
        arg = node.args[0]
        if not (isinstance(arg, ast.Constant) and isinstance(arg.value, str)):
            continue
        arg_start = _offset(arg.lineno, arg.col_offset)
        arg_end = _offset(arg.end_lineno, arg.end_col_offset)
        arg_text = source[arg_start:arg_end]
        m = _HTML_CALL_QUOTE_RE.match(arg_text)
        if not m:
            continue
        quote = m.group(1)
        inner_start = arg_start + m.end()
        inner_end = arg_end - len(quote)
        if inner_end <= inner_start:
            continue
        inner_text = source[inner_start:inner_end]
        for local_start, local_end, text in _extract_widget_text_spans(inner_text):
            spans.append((inner_start + local_start, inner_start + local_end, text))

    spans.sort(key=lambda s: s[0])
    return spans


_ID_ATTR_RE = re.compile(r'''\bid\s*=\s*"([^"]*)"|\bid\s*=\s*'([^']*)' ''')


def _widget_structure_fingerprint(text: str) -> tuple:
    """
    "Impressão digital" estrutural de um trecho com simuladores: conjunto
    de todos os `id="..."` (usados por getElementById — não podem mudar)
    e contagem de `<script>`/`</script>`. Comparar essa impressão antes e
    depois da tradução é a rede de segurança final contra qualquer bug de
    offset na extração — se divergir, a tradução é descartada.
    """
    ids = tuple(sorted((m.group(1) or m.group(2)) for m in _ID_ATTR_RE.finditer(text)))
    n_open = len(re.findall(r'<script\b', text, re.IGNORECASE))
    n_close = len(re.findall(r'</script>', text, re.IGNORECASE))
    return (ids, n_open, n_close)


def _translate_snippets_batch(spans: list[tuple[int, int, str]], system: str,
                               label: str) -> Optional[dict]:
    """
    Traduz uma lista de (start, end, texto) em lote via LLM (uma chamada,
    JSON array in/out, ordem preservada) — mesma mecânica de retry contra
    eco/cache do DeepSeek de `_call_llm_retrying_if_unchanged`, adaptada
    pra lote (o "eco" aqui é a lista inteira igual à original).
    Devolve {(start, end): texto_traduzido}, ou None se a chamada falhar
    (loga aviso) — o chamador decide o fallback (manter o span original).
    """
    originals = [text for (_, _, text) in spans]
    user = json.dumps(originals, ensure_ascii=False)

    def _ask(prompt_user: str) -> list:
        raw = _call_llm(system, prompt_user)
        raw = re.sub(r'^```\w*\n?', '', raw.strip())
        raw = re.sub(r'\n?```$', '', raw.strip())
        parsed = json.loads(raw)
        if not isinstance(parsed, list) or len(parsed) != len(spans):
            raise ValueError('resposta com formato ou contagem inesperados')
        return parsed

    try:
        translations = _ask(user)
        attempt = 0
        while translations == originals and attempt < 2:
            attempt += 1
            nonce = f'[req {random.randint(100000, 999999)}] '
            translations = _ask(nonce + user)
    except Exception as exc:
        print(f'  ⚠ Tradução de {label} falhou ({exc}); mantendo trechos originais.')
        return None

    return {
        (start, end): (new_text if isinstance(new_text, str) and new_text.strip() else original)
        for (start, end, original), new_text in zip(spans, translations)
    }


_WIDGET_SYSTEM_TEMPLATE = """
You translate short, ISOLATED user-interface text fragments from
Portuguese to {locale_label}. They were mechanically extracted from an
interactive HTML/JavaScript widget embedded in a textbook — you do NOT see
the surrounding code and must not try to reconstruct or reference it.
You receive a JSON array of raw fragments. Each one is one of:
  - a plain text fragment (originally between HTML tags)
  - the value of an HTML attribute (title/placeholder/aria-label/alt)
  - a short label assigned via JavaScript (.textContent) or drawn on a
    <canvas> (fillText)
Rules:
1. Return a JSON array with EXACTLY the same number of items, in the same
   order — one translated fragment per input item.
2. Translate ONLY the fragment's own text. It has no surrounding quotes —
   return bare translated text, nothing added, nothing wrapped.
3. Preserve emoji, numbers, units, punctuation, HTML entities (e.g.
   &nbsp;) and any code-like token exactly as they are.
4. If a fragment is not natural-language prose (e.g. just a symbol,
   formula, or code token), return it unchanged.
5. Keep translations short — these are UI labels/tooltips, not prose.
6. Return ONLY the JSON array — no explanation, no markdown fence.
""".strip()


class LLMCommentTranslator(Translator):
    """
    py → py: a LINGUAGEM não muda, só o locale dos comentários/docstrings.

    Ao contrário do LLMCodeTranslator, NÃO manda o código inteiro pro LLM
    reescrever. Extrai apenas os spans de comentário/docstring via
    tokenize/ast — e, se a célula contiver um simulador interativo
    (chamada HTML(...) com string triplamente-citada), também os spans de
    texto seguro de dentro dele (ver `_extract_widget_spans`) — traduz
    cada grupo em lote (uma chamada
    por grupo, via JSON) e recola tudo nas posições exatas do texto
    original. O restante do arquivo (incluindo `id`s, atributos de estilo e
    toda a lógica JS dos simuladores) nunca passa pelo modelo — a lógica
    não pode mudar por construção, não por obediência do prompt.

    Rede de segurança: se o resultado reconstruído não for Python
    sintaticamente válido, se a estrutura do(s) simulador(es) mudar (ids/
    contagem de `<script>` — ver `_widget_structure_fingerprint`), ou se a
    resposta do LLM vier com formato/contagem inesperados, descarta a
    tradução (do grupo afetado, ou da célula inteira no caso da checagem
    estrutural) e devolve o código-fonte original sem alteração (loga
    aviso).
    """
    kind = 'code'
    src_key = 'py'

    def __init__(self, tgt_locale: str, cache: TranslationCache,
                 dry_run: bool = False):
        super().__init__(cache, dry_run)
        self._locale = tgt_locale

    @property
    def tgt_key(self) -> str:
        return f'py.{self._locale}'

    def translate(self, source: str, **_) -> str:
        if not source.strip():
            return source

        cached = self.cache.get(source, self.kind, self.src_key, self.tgt_key)
        if cached is not None:
            return cached

        comment_spans = _extract_comment_spans(source)
        widget_spans = _extract_widget_spans(source)
        if not comment_spans and not widget_spans:
            return source

        if self.dry_run:
            return source  # sem prosa pra traduzir aqui — sem custo de API

        locale_obj = LOCALES.get(self._locale)
        locale_label = locale_obj.label if locale_obj else self._locale

        translated: dict = {}

        if comment_spans:
            system = textwrap.dedent(f"""
                You translate pieces of Python source code from Portuguese to
                {locale_label}. You receive a JSON array of raw snippets, each
                one of:
                  - a full `#`-comment (with the `#` included)
                  - a full docstring literal (including its exact quote characters)
                  - a string literal passed to `print(...)` or to the
                    `title=`/`titles=` argument of `mm.show(...)` — this is
                    text shown to the student when the cell runs, including its
                    exact quote characters and, if present, the leading `f`
                Rules:
                1. Return a JSON array with EXACTLY the same number of items,
                   in the same order — one translated snippet per input item.
                2. Preserve the wrapper characters exactly: keep the leading
                   `#` for comments, and the exact quote characters
                   (\"\"\" or ''' or \" or ', with leading `f` if present) for
                   docstrings and print/title strings.
                3. For an f-string snippet, translate ONLY the literal text
                   outside `{{...}}`. Copy every `{{...}}` expression verbatim,
                   character-for-character, in the exact same position — never
                   translate, reformat, or drop what's inside the braces.
                4. Translate ONLY natural-language prose. Leave shebang lines
                   (`#!...`), encoding cookies (`# -*- coding: ... -*-`),
                   lint/type directives (`# noqa`, `# type: ignore`) and
                   commented-out code UNCHANGED.
                5. Preserve inline code, LaTeX and punctuation as-is.
                6. Return ONLY the JSON array — no explanation, no markdown fence.
            """).strip()
            batch = _translate_snippets_batch(comment_spans, system, 'comentários')
            if batch:
                translated.update(batch)

        if widget_spans:
            system = _WIDGET_SYSTEM_TEMPLATE.format(locale_label=locale_label)
            batch = _translate_snippets_batch(widget_spans, system, 'texto de simulador')
            if batch:
                translated.update(batch)

        if not translated:
            # Nenhum dos dois lotes rendeu tradução aproveitável — nada a
            # fazer, mas ainda cacheia pra não tentar de novo em toda build.
            self.cache.set(source, self.kind, self.src_key, self.tgt_key, source)
            return source

        all_spans = sorted(comment_spans + widget_spans, key=lambda s: s[0])
        out = []
        cursor = 0
        for (start, end, original) in all_spans:
            out.append(source[cursor:start])
            out.append(translated.get((start, end), original))
            cursor = end
        out.append(source[cursor:])
        result = ''.join(out)

        # Guard de `#| fig-cap:`: algumas traduções (sobretudo fr) trocam as
        # aspas "..." do valor por guillemets « … » e/ou adicionam um espaço
        # antes do `:` da chave. Sem aspas, um `:` dentro da legenda (comum em
        # fr: "Crédit : ...") quebra o parser YAML do Quarto
        # ("mapping values are not allowed here"). Renormaliza a linha.
        def _fix_fig_cap(line: str) -> str:
            m = re.match(r'^(\s*#\|\s*fig-cap)\s*:\s*(.*?)\s*$', line)
            if not m:
                return line
            val = m.group(2)
            if val[:1] == '«' and val[-1:] == '»':
                val = val[1:-1].strip()
            if not (val[:1] == '"' and val[-1:] == '"'):
                val = '"' + val.replace('"', "'") + '"'
            return f'{m.group(1)}: {val}'
        if '#| fig-cap' in result:
            result = '\n'.join(_fix_fig_cap(ln) for ln in result.split('\n'))

        # Só valida sintaxe se o original já era Python "puro" — células
        # com magics do Jupyter (`!pip install`, `%matplotlib inline`)
        # nunca passam no ast.parse, com ou sem tradução, então validar
        # nesse caso só geraria falso-positivo e descartaria traduções boas.
        try:
            ast.parse(source)
            source_is_valid_python = True
        except SyntaxError:
            source_is_valid_python = False

        if source_is_valid_python:
            try:
                ast.parse(result)
            except SyntaxError as exc:
                print(f'  ⚠ Código traduzido ficou sintaticamente inválido ({exc}); mantendo original.')
                result = source

        # Rede de segurança específica de simulador: ids (getElementById) e
        # contagem de <script> têm que ser idênticos antes/depois. Como o
        # splice é fatiamento puro, isso só falharia por bug de offset na
        # extração — mas descarta a célula inteira nesse caso, não arrisca.
        if widget_spans and _widget_structure_fingerprint(source) != _widget_structure_fingerprint(result):
            print('  ⚠ Tradução de simulador alterou estrutura (ids/<script>); mantendo original.')
            result = source

        self.cache.set(source, self.kind, self.src_key, self.tgt_key, result)
        return result


# ─────────────────────────────────────────────────────────────────────────────
# Text Translators  (Strategy: Markdown)
# ─────────────────────────────────────────────────────────────────────────────

class PassthroughText(Translator):
    """pt → pt: identidade."""
    kind = 'text'; src_key = 'pt'; tgt_key = 'pt'

    def translate(self, source: str, **_) -> str:
        return source


class LLMTextTranslator(Translator):
    """
    Traduz texto Markdown entre idiomas usando LLM.
    Preserva LaTeX, labels Quarto, código inline e blocos de código.
    """
    kind = 'text'
    src_key = 'pt'

    def __init__(self, tgt_locale: str, cache: TranslationCache,
                 dry_run: bool = False):
        super().__init__(cache, dry_run)
        self._tgt = tgt_locale

    @property
    def tgt_key(self) -> str:
        return self._tgt

    def translate(self, source: str, **_) -> str:
        if not source.strip():
            return source

        cached = self.cache.get(source, self.kind, self.src_key, self.tgt_key)
        if cached is not None:
            return cached

        if self.dry_run:
            # Não grava no cache: é só uma prévia, não pode "grudar" e ser
            # reaproveitada por uma execução real posterior.
            return f'<!-- [TODO: traduzir pt → {self.tgt_key}] -->\n{source}'

        locale_obj = LOCALES.get(self.tgt_key)
        locale_label = locale_obj.label if locale_obj else self.tgt_key

        system = textwrap.dedent(f"""
            You are a scientific textbook translator (Portuguese → {locale_label}).
            Translate the Markdown text following these strict rules:
            1. Preserve ALL LaTeX math unchanged: $...$ and $$...$$
            2. Preserve ALL placeholder tokens of the form ZQREF<number>Z exactly
               as they are, character-for-character, including their exact
               position relative to surrounding punctuation. Never translate,
               reword, or drop them — they are opaque IDs, not words.
            3. (covered by rule 2 — cross-references and labels are masked as
               ZQREF tokens before you see this text)
            4. Preserve ALL fenced code blocks unchanged (``` ... ```)
            5. Preserve ALL inline code unchanged (`...`)
            6. Preserve markdown structure: headings (#), lists, bold, italic
            7. Translate ONLY natural language prose and comments
            8. Use formal academic {locale_label} style
            9. Return ONLY the translated Markdown, no explanation
        """).strip()

        masked_source, tokens = _mask_protected_tokens(source)
        user = f"Translate this Markdown from Portuguese to {locale_label}:\n\n{masked_source}"

        result = _call_llm_retrying_if_unchanged(system, user, masked_source)
        # Eco: o modelo devolveu o texto-fonte (incidente de API / eco de cache
        # do servidor persistindo mesmo com o nonce). Detecta eco APROXIMADO —
        # o DeepSeek às vezes devolve o Português com perturbações mínimas
        # (pontuação, espaço) que passariam por uma comparação exata e seriam
        # cacheadas como "tradução", congelando Português no livro fr/en/it/es
        # pra sempre. NÃO cacheia: cache vazio faz o próximo build tentar de
        # novo — o eco se auto-corrige, sem precisar de --promote-edits.
        echo_ratio = difflib.SequenceMatcher(
            None, result.strip(), masked_source.strip()).ratio()
        if echo_ratio >= 0.92:
            print(f'  ⚠ Tradução pt→{self.tgt_key} voltou ~idêntica ao original '
                  f'(similaridade {echo_ratio:.0%}) mesmo após retry — NÃO '
                  f'cacheada; o próximo build tenta de novo.')
            return _unmask_protected_tokens(result, tokens)
        result = _unmask_protected_tokens(result, tokens)
        self.cache.set(source, self.kind, self.src_key, self.tgt_key, result)
        return result


# ─────────────────────────────────────────────────────────────────────────────
# Factory  — cria o Translator certo para um combo
# ─────────────────────────────────────────────────────────────────────────────

class TranslatorFactory:
    """
    Fábrica de tradutores.
    Padrão Factory Method + registro extensível.

    Para adicionar Java:
        factory.register_code('java', LLMCodeTranslator)
    """

    def __init__(self, cache: TranslationCache, dry_run: bool = False):
        self._cache = cache
        self._dry_run = dry_run

    def code_translator(self, tgt_lang: str, tgt_locale: str) -> Translator:
        if tgt_lang == BASE_LANG:
            if tgt_locale == BASE_LOCALE:
                return PythonPassthrough(self._cache, self._dry_run)
            # Mesma linguagem, locale diferente: só os comentários mudam.
            return LLMCommentTranslator(tgt_locale, self._cache, self._dry_run)
        return LLMCodeTranslator(tgt_lang, tgt_locale, self._cache, self._dry_run)

    def text_translator(self, tgt_locale: str) -> Translator:
        if tgt_locale == BASE_LOCALE:
            return PassthroughText(self._cache, self._dry_run)
        return LLMTextTranslator(tgt_locale, self._cache, self._dry_run)
