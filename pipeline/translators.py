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

import os
import re
import textwrap
from abc import ABC, abstractmethod
from typing import Optional

from .cache import TranslationCache
from .config import BASE_LANG, BASE_LOCALE, LANGUAGES, LOCALES

# ─────────────────────────────────────────────────────────────────────────────
# Utilitário: chamada à API Anthropic
# ─────────────────────────────────────────────────────────────────────────────

def _call_llm_claude(system: str, user: str, max_tokens: int = 4096) -> str:
    """
    Chama claude-sonnet-4-20250514 via Anthropic Python SDK.
    Requer variável de ambiente ANTHROPIC_API_KEY.
    """
    try:
        import anthropic
    except ImportError:
        raise ImportError("pip install anthropic")

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    msg = client.messages.create(
        model="claude-sonnet-4-20250514",
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
    Preserva comentários, docstrings e lógica algorítmica.
    """
    kind = 'code'
    src_key = 'py'

    def __init__(self, tgt_lang: str, cache: TranslationCache,
                 dry_run: bool = False):
        super().__init__(cache, dry_run)
        self._tgt = tgt_lang

    @property
    def tgt_key(self) -> str:
        return self._tgt

    def translate(self, source: str, **_) -> str:
        if not source.strip():
            return source

        # Cache hit?
        cached = self.cache.get(source, self.kind, self.src_key, self.tgt_key)
        if cached is not None:
            return cached

        if self.dry_run:
            result = f'// [TODO: traduzir Python → {self.tgt_key}]\n{source}'
            self.cache.set(source, self.kind, self.src_key, self.tgt_key, result)
            return result

        lang_obj = LANGUAGES.get(self.tgt_key)
        lang_label = lang_obj.label if lang_obj else self.tgt_key

        system = textwrap.dedent(f"""
            You are an expert programming language converter.
            Convert Python code to {lang_label}, following these rules:
            - Preserve ALL comments (translate to {lang_label} conventions)
            - Preserve algorithm logic exactly
            - Use idiomatic {lang_label} style and standard library
            - For image processing: use OpenCV ({lang_label} bindings)
            - For morph.py functions: implement equivalent logic in {lang_label}
            - Return ONLY the translated code, no markdown fences, no explanation
            - Add a one-line compile/run comment at the top if applicable
        """).strip()

        user = f"Convert this Python code to {lang_label}:\n\n{source}"

        result = _call_llm(system, user)
        # Strip markdown fences if LLM added them
        result = re.sub(r'^```\w*\n?', '', result, flags=re.MULTILINE)
        result = re.sub(r'\n?```$', '', result, flags=re.MULTILINE)
        result = result.strip()

        self.cache.set(source, self.kind, self.src_key, self.tgt_key, result)

        result = self._filter_lang_directives(result, self.tgt_key)

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
            result = f'<!-- [TODO: traduzir pt → {self.tgt_key}] -->\n{source}'
            self.cache.set(source, self.kind, self.src_key, self.tgt_key, result)
            return result

        locale_obj = LOCALES.get(self.tgt_key)
        locale_label = locale_obj.label if locale_obj else self.tgt_key

        system = textwrap.dedent(f"""
            You are a scientific textbook translator (Portuguese → {locale_label}).
            Translate the Markdown text following these strict rules:
            1. Preserve ALL LaTeX math unchanged: $...$ and $$...$$
            2. Preserve ALL Quarto labels unchanged: {{#fig-X-Y}}, {{#eq-X-Y}}, {{#tbl-X-Y}}
            3. Preserve ALL Quarto cross-references unchanged: @fig-X-Y, @eq-X-Y
            4. Preserve ALL fenced code blocks unchanged (``` ... ```)
            5. Preserve ALL inline code unchanged (`...`)
            6. Preserve markdown structure: headings (#), lists, bold, italic
            7. Translate ONLY natural language prose and comments
            8. Use formal academic {locale_label} style
            9. Return ONLY the translated Markdown, no explanation
        """).strip()

        user = f"Translate this Markdown from Portuguese to {locale_label}:\n\n{source}"

        result = _call_llm(system, user)
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

    def code_translator(self, tgt_lang: str) -> Translator:
        if tgt_lang == BASE_LANG:
            return PythonPassthrough(self._cache, self._dry_run)
        return LLMCodeTranslator(tgt_lang, self._cache, self._dry_run)

    def text_translator(self, tgt_locale: str) -> Translator:
        if tgt_locale == BASE_LOCALE:
            return PassthroughText(self._cache, self._dry_run)
        return LLMTextTranslator(tgt_locale, self._cache, self._dry_run)
