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
import io
import json
import os
import random
import re
import textwrap
import tokenize
from abc import ABC, abstractmethod
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

    def translate(self, source: str, output_image_path: Optional[str] = None, **_) -> str:
        """
        `output_image_path`: quando a célula original chama mm.show(...), o
        chamador (NotebookProcessor) já sabe o nome do PNG (derivado do
        próprio #| label: da célula) e passa aqui — precisa estar presente
        ANTES da checagem de compilação (senão MM_OUT não está definido e
        toda célula com mm::show() reprovaria na validação por um motivo
        que não tem nada a ver com a tradução em si).
        """
        if not source.strip():
            return source

        # Cache hit?
        cached = self.cache.get(source, self.kind, self.src_key, self.tgt_key)
        if cached is not None:
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
                  std::string mm::drawImg(const mm::Image&)

                Rules:
                - `mm::Image` already holds raw pixel data; there is no
                  `pil=` concept in Python's mm.read(url, pil=True) — drop it.
                - For every call to mm::show(...), pass the literal macro
                  token MM_OUT as the out_path argument (a
                  #define MM_OUT "..." line will be prepended for you
                  automatically) — never invent a filename yourself.
                - Do NOT use OpenCV. Do NOT #include anything beyond
                  "morph.hpp" and the C++ standard library.
                - Do NOT invent mm:: functions beyond the list above — in
                  particular there is NO mm::zeros / mm::ones. NumPy array
                  creation and indexing map directly onto mm::Image, which
                  is already zero-initialized:
                    np.zeros((h, w), dtype='uint8')   ->  mm::Image img(h, w);
                    np.ones((h, w), dtype='uint8')*255 -> mm::Image img(h, w); std::fill(img.data.begin(), img.data.end(), 255);
                    img[y, x] = v                     ->  img.at(y, x) = v;
                - Python keyword arguments (e.g. maxValue=255) have no C++
                  equivalent here — pass the value positionally instead
                  (e.g. mm::randomImage(4, 6, 255)), in the same parameter
                  order as the signatures above.
            """).strip()
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
            if output_image_path is not None:
                # Precisa entrar ANTES do compile_check: o prompt instrui o
                # LLM a chamar mm::show(img, MM_OUT, ...) usando o token
                # literal, então sem essa macro definida a validação
                # reprovaria por "MM_OUT não declarado" — um motivo que não
                # tem nada a ver com a qualidade da tradução em si.
                result = f'#define MM_OUT "{output_image_path}"\n' + result

            # Rede de segurança: sem isso, uma tradução C++ quebrada seria
            # cacheada e só apareceria como erro no dia do render (ou nem
            # isso — o kernel Python não entende C++, então falha
            # silenciosamente). Nunca cacheia uma tradução que não compila;
            # devolve o Python original, que o chamador (NotebookProcessor)
            # reconhece como "tradução indisponível" por comparação de
            # igualdade, sem precisar de um segundo canal de erro.
            from .exec_validate import compile_check
            ok, err = compile_check('cpp', result)
            if not ok:
                print(f'  ⚠ Compilação C++ falhou; mantendo código original.\n{err[:800]}')
                return source

        self.cache.set(source, self.kind, self.src_key, self.tgt_key, result)

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
        pass
    elif isinstance(node, ast.JoinedStr):
        pass
    else:
        return []
    start = _offset(node.lineno, node.col_offset)
    end = _offset(node.end_lineno, node.end_col_offset)
    return [(start, end, source[start:end])]


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


class LLMCommentTranslator(Translator):
    """
    py → py: a LINGUAGEM não muda, só o locale dos comentários/docstrings.

    Ao contrário do LLMCodeTranslator, NÃO manda o código inteiro pro LLM
    reescrever. Extrai apenas os spans de comentário/docstring via
    tokenize/ast, traduz só esses trechos (uma chamada por célula, em lote
    via JSON) e recola nas posições exatas do texto original. O restante do
    arquivo nunca passa pelo modelo — a lógica não pode mudar por
    construção, não por obediência do prompt.

    Rede de segurança: se o resultado reconstruído não for Python
    sintaticamente válido, ou se a resposta do LLM vier com formato/
    contagem inesperados, descarta a tradução e devolve o código-fonte
    original sem alteração (loga aviso).
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

        spans = _extract_comment_spans(source)
        if not spans:
            return source

        if self.dry_run:
            return source  # sem prosa pra traduzir aqui — sem custo de API

        locale_obj = LOCALES.get(self._locale)
        locale_label = locale_obj.label if locale_obj else self._locale

        originals = [text for (_, _, text) in spans]

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
            # Mesmo cache de contexto do DeepSeek de _call_llm_retrying_if_unchanged
            # (ver docstring lá) — aqui o "eco" é a lista inteira igual à
            # original em vez de uma string igual.
            while translations == originals and attempt < 2:
                attempt += 1
                nonce = f'[req {random.randint(100000, 999999)}] '
                translations = _ask(nonce + user)
        except Exception as exc:
            print(f'  ⚠ Tradução de comentários falhou ({exc}); mantendo código original.')
            self.cache.set(source, self.kind, self.src_key, self.tgt_key, source)
            return source

        out = []
        cursor = 0
        for (start, end, original), new_text in zip(spans, translations):
            out.append(source[cursor:start])
            out.append(new_text if isinstance(new_text, str) and new_text.strip() else original)
            cursor = end
        out.append(source[cursor:])
        result = ''.join(out)

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
        if result.strip() == masked_source.strip():
            print(f'  ⚠ Tradução pt→{self.tgt_key} voltou idêntica ao original '
                  f'mesmo após retry — cacheando assim mesmo (revisar/corrigir '
                  f'depois com dev.py --promote-edits).')
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
