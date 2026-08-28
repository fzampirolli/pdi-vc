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
        'title':           'Processamento Digital de Imagens e Visão Computacional',
        'title_short':     'PDI e VC',
        'org_title':       'Organização',
        'book_subtitle':   'Abordagem Prática com {lang_label}',
        'part_1':          'Parte I — Fundamentos de PDI',
        'part_1_desc':     'Representação, histogramas, filtragem, morfologia',
        'part_2':          'Parte II — Visão Computacional',
        'part_2_desc':     'Segmentação, descritores, detecção, aprendizado profundo',
        'references_title':'Referências',
        'exercises_label': 'Exercícios',
        'note_code':       'Código {lang_label}',
        'welcome':         'Bem-vindo ao livro de PDI e Visão Computacional — versão {lang_label} / Português.',
        'pdf_subtitle':    'Livro interativo com {lang_label}',
        'brand_tag':        'PDI \\& VC',
        'contents_name':    'Sumário',
        'list_figures_name':'Lista de Figuras',
        'list_tables_name': 'Lista de Tabelas',
        'figure_name':       'Figura',
        'table_name':        'Tabela',
        'chapter_name':      'Capítulo',
        'part_name':         'Parte',
        'appendix_name':     'Apêndice',
        'cip_title':         'Ficha Catalográfica',
        'babel_lang':        'portuguese',
    },
    'en': {
        'title':           'Digital Image Processing and Computer Vision',
        'title_short':     'DIP and CV',
        'org_title':       'Organization',
        'book_subtitle':   'Practical Approach with {lang_label}',
        'part_1':          'Part I — PDI Fundamentals',
        'part_1_desc':     'Representation, histograms, filtering, morphology',
        'part_2':          'Part II — Computer Vision',
        'part_2_desc':     'Segmentation, descriptors, detection, deep learning',
        'references_title':'References',
        'exercises_label': 'Exercises',
        'note_code':       '{lang_label} Code',
        'welcome':         'Welcome to the PDI and Computer Vision textbook — {lang_label} / English version.',
        'pdf_subtitle':    'Interactive book with {lang_label}',
        'brand_tag':        'DIP \\& CV',
        'contents_name':    'Contents',
        'list_figures_name':'List of Figures',
        'list_tables_name': 'List of Tables',
        'figure_name':       'Figure',
        'table_name':        'Table',
        'chapter_name':      'Chapter',
        'part_name':         'Part',
        'appendix_name':     'Appendix',
        'cip_title':         'Cataloging-in-Publication (CIP) Data',
        'babel_lang':        'english',
    },
    'fr': {
        'title':           "Traitement Numérique d'Images & Vision par Ordinateur",
        'title_short':     'TNI & VO',
        'org_title':       'Organisation',
        'book_subtitle':   'Approche Pratique avec {lang_label}',
        'part_1':          'Partie I — Fondements du TNI',
        'part_1_desc':     'Représentation, histogrammes, filtrage, morphologie',
        'part_2':          'Partie II — Vision par Ordinateur',
        'part_2_desc':     'Segmentation, descripteurs, détection, apprentissage profond',
        'references_title':'Références',
        'exercises_label': 'Exercices',
        'note_code':       'Code {lang_label}',
        'welcome':         'Bienvenue dans le manuel TNI et Vision par Ordinateur — version {lang_label} / Français.',
        'pdf_subtitle':    'Livre interactif avec {lang_label}',
        'brand_tag':        'TNI \\& VO',
        'contents_name':    'Table des matières',
        'list_figures_name':'Liste des figures',
        'list_tables_name': 'Liste des tableaux',
        'figure_name':       'Figure',
        'table_name':        'Tableau',
        'chapter_name':      'Chapitre',
        'part_name':         'Partie',
        'appendix_name':     'Annexe',
        'cip_title':         'Fiche Cataloguée',
        'babel_lang':        'french',
    },
    'it': {
        'title':           'Elaborazione Digitale delle Immagini e Visione Artificiale',
        'title_short':     'EDI e VA',
        'org_title':       'Organizzazione',
        'book_subtitle':   'Approccio Pratico con {lang_label}',
        'part_1':          'Parte I — Fondamenti di EAI',
        'part_1_desc':     'Rappresentazione, istogrammi, filtraggio, morfologia',
        'part_2':          'Parte II — Visione Artificiale',
        'part_2_desc':     'Segmentazione, descrittori, rilevamento, apprendimento profondo',
        'references_title':'Riferimenti',
        'exercises_label': 'Esercizi',
        'note_code':       'Codice {lang_label}',
        'welcome':         'Benvenuti nel libro EAI e Visione Artificiale — versione {lang_label} / Italiano.',
        'pdf_subtitle':    'Libro interattivo con {lang_label}',
        'brand_tag':        'EDI \\& VA',
        'contents_name':    'Indice',
        'list_figures_name':'Elenco delle Figure',
        'list_tables_name': 'Elenco delle Tabelle',
        'figure_name':       'Figura',
        'table_name':        'Tabella',
        'chapter_name':      'Capitolo',
        'part_name':         'Parte',
        'appendix_name':     'Appendice',
        'cip_title':         'Scheda Catalografica',
        'babel_lang':        'italian',
    },
    'es': {
        'title':           'Procesamiento Digital de Imágenes y Visión por Computador',
        'title_short':     'PDI y VC',
        'org_title':       'Organización',
        'book_subtitle':   'Enfoque Práctico con {lang_label}',
        'part_1':          'Parte I — Fundamentos de PDI',
        'part_1_desc':     'Representación, histogramas, filtrado, morfología',
        'part_2':          'Parte II — Visión por Computador',
        'part_2_desc':     'Segmentación, descriptores, detección, aprendizaje profundo',
        'references_title':'Referencias',
        'exercises_label': 'Ejercicios',
        'note_code':       'Código {lang_label}',
        'welcome':         'Bienvenido al libro PDI y Visión por Computador — versión {lang_label} / Español.',
        'pdf_subtitle':    'Libro interactivo con {lang_label}',
        'brand_tag':        'PDI \\& VC',
        'contents_name':    'Índice',
        'list_figures_name':'Lista de Figuras',
        'list_tables_name': 'Lista de Tablas',
        'figure_name':       'Figura',
        'table_name':        'Tabla',
        'chapter_name':      'Capítulo',
        'part_name':         'Parte',
        'appendix_name':     'Apéndice',
        'cip_title':         'Ficha Catalográfica',
        'babel_lang':        'spanish',
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
    def file_key(self) -> str:          # ← NOVO: ordem locale.lang para o nome do arquivo
        return f'{self.locale}.{self.lang}'

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
