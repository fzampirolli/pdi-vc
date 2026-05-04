"""
pipeline/config.py
==================
Registro central de linguagens e idiomas suportados.

Para ADICIONAR uma linguagem (ex: Java):
    1. Acrescente uma entrada em LANGUAGES
    2. Implemente a Strategy correspondente em translators/code.py

Para ADICIONAR um idioma (ex: Francês):
    1. Acrescente uma entrada em LOCALES
    2. Acrescente strings de UI em UI_STRINGS
"""

from dataclasses import dataclass, field
from typing import Optional

# ─────────────────────────────────────────────────────────────────────────────
# Registro de linguagens de programação
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Language:
    key: str          # identificador curto  (ex: 'py')
    label: str        # rótulo legível       (ex: 'Python')
    extension: str    # extensão de arquivo  (ex: '.py')
    base: bool        # True = linguagem-base (fonte canônico)
    quarto_engine: str = 'python'   # kernel do Quarto/Jupyter

LANGUAGES: dict[str, Language] = {
    'py':   Language('py',   'Python', '.py',  base=True,  quarto_engine='python'),
    'cpp':  Language('cpp',  'C++',    '.cpp', base=False, quarto_engine='python'),
    'java': Language('java', 'Java',   '.java',base=False, quarto_engine='python'),
    'c':    Language('c',    'C',      '.c',   base=False, quarto_engine='python'),
}

BASE_LANG = 'py'   # fonte canônico — editar apenas em Python

# ─────────────────────────────────────────────────────────────────────────────
# Registro de idiomas (locales)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Locale:
    key: str          # identificador curto  (ex: 'pt')
    label: str        # rótulo legível       (ex: 'Português')
    quarto_lang: str  # tag BCP-47 para Quarto/pandoc
    base: bool        # True = idioma-base (fonte canônico)

LOCALES: dict[str, Locale] = {
    'pt': Locale('pt', 'Português', 'pt',    base=True),
    'en': Locale('en', 'English',   'en',    base=False),
    'fr': Locale('fr', 'Français',  'fr',    base=False),
    'it': Locale('it', 'Italiano',  'it',    base=False),
    'es': Locale('es', 'Español',   'es',    base=False),
}

BASE_LOCALE = 'pt'   # idioma canônico — escrever apenas em Português

# ─────────────────────────────────────────────────────────────────────────────
# Strings de UI por idioma  (títulos de partes, índice, referências, etc.)
# ─────────────────────────────────────────────────────────────────────────────

UI_STRINGS: dict[str, dict[str, str]] = {
    'pt': {
        'book_subtitle':   'Abordagem Prática com {lang_label}',
        'part_1':          'Parte I — Fundamentos de PDI',
        'part_2':          'Parte II — Visão Computacional',
        'references_title':'Referências',
        'exercises_label': 'Exercícios',
        'note_code':       'Código {lang_label}',
        'welcome':         'Bem-vindo ao livro de PDI e Visão Computacional — versão {lang_label} / Português.',
    },
    'en': {
        'book_subtitle':   'Practical Approach with {lang_label}',
        'part_1':          'Part I — PDI Fundamentals',
        'part_2':          'Part II — Computer Vision',
        'references_title':'References',
        'exercises_label': 'Exercises',
        'note_code':       '{lang_label} Code',
        'welcome':         'Welcome to the PDI and Computer Vision textbook — {lang_label} / English version.',
    },
    'fr': {
        'book_subtitle':   'Approche Pratique avec {lang_label}',
        'part_1':          'Partie I — Fondements du TIN',
        'part_2':          'Partie II — Vision par Ordinateur',
        'references_title':'Références',
        'exercises_label': 'Exercices',
        'note_code':       'Code {lang_label}',
        'welcome':         'Bienvenue dans le manuel TIN et Vision par Ordinateur — version {lang_label} / Français.',
    },
    'it': {
        'book_subtitle':   'Approccio Pratico con {lang_label}',
        'part_1':          'Parte I — Fondamenti di EAI',
        'part_2':          'Parte II — Visione Artificiale',
        'references_title':'Riferimenti',
        'exercises_label': 'Esercizi',
        'note_code':       'Codice {lang_label}',
        'welcome':         'Benvenuti nel libro EAI e Visione Artificiale — versione {lang_label} / Italiano.',
    },
    'es': {
        'book_subtitle':   'Enfoque Práctico con {lang_label}',
        'part_1':          'Parte I — Fundamentos de PDI',
        'part_2':          'Parte II — Visión por Computador',
        'references_title':'Referencias',
        'exercises_label': 'Ejercicios',
        'note_code':       'Código {lang_label}',
        'welcome':         'Bienvenido al libro PDI y Visión por Computador — versión {lang_label} / Español.',
    },
}

def ui(locale_key: str, string_key: str, **fmt) -> str:
    """Retorna string de UI para o locale dado, com formatação opcional."""
    s = UI_STRINGS.get(locale_key, UI_STRINGS['en']).get(string_key, string_key)
    return s.format(**fmt) if fmt else s

# ─────────────────────────────────────────────────────────────────────────────
# Combos ativos (subconjunto dos produtos cartesianos possíveis)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Combo:
    lang: str
    locale: str

    @property
    def key(self) -> str:
        return f'{self.lang}.{self.locale}'

    @property
    def lang_obj(self) -> Language:
        return LANGUAGES[self.lang]

    @property
    def locale_obj(self) -> Locale:
        return LOCALES[self.locale]

    def is_base(self) -> bool:
        return self.lang == BASE_LANG and self.locale == BASE_LOCALE

def parse_combo(s: str) -> Combo:
    parts = s.split('.')
    if len(parts) != 2 or parts[0] not in LANGUAGES or parts[1] not in LOCALES:
        raise ValueError(
            f"Combo inválido: '{s}'. Use <lang>.<locale>. "
            f"Langs: {list(LANGUAGES)}. Locales: {list(LOCALES)}."
        )
    return Combo(parts[0], parts[1])

def all_combos(langs=None, locales=None) -> list[Combo]:
    """Retorna todos os combos do produto cartesiano langs × locales."""
    langs   = langs   or list(LANGUAGES.keys())
    locales = locales or list(LOCALES.keys())
    return [Combo(l, lo) for l in langs for lo in locales]
