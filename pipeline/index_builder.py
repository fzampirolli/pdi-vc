"""
pipeline/index_builder.py
=========================
Gera página principal minimalista com links para cada versão.
O index.html fica em gen/book/index.html (junto com as versões geradas).

Em cada versão (ex: gen/book/py.pt/index.html), substitui o bloco nativo de
metadados do Quarto (Autor, Afiliação, Data de Publicação, Modified, etc.)
por um único PAINEL unificado, organizado em três seções rotuladas:

  1) Sobre esta edição  -> pills com Autor / Afiliação / Última Atualização
  2) Acesso rápido       -> botões para Simuladores, EPs e PDF
  3) Capas do livro      -> Capa Principal e Contracapa lado a lado

O objetivo é priorizar a informação (rótulos claros, agrupamento visual)
e manter a mesma identidade visual (navy + dourado + serifada) do portal
principal, em vez de vários blocos soltos com estilos diferentes.
"""

from __future__ import annotations

import json
import re
import shutil
from html import escape as html_escape
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple, Optional

from .config import LANGUAGES, LOCALES, BASE_LANG, BASE_LOCALE

DIR_GEN = Path('gen')
DIR_BOOK = DIR_GEN / 'book'


class IndexBuilder:
    """Constrói página principal com links para os índices de cada versão."""

    def __init__(self, project_root: Path = Path('.')):
        self.root = project_root.resolve()
        self.gen_dir = self.root / DIR_GEN
        self.book_dir = self.root / DIR_BOOK
        self.index_path = self.book_dir / 'index.html'

    def scan_versions(self) -> List[Dict]:
        """Escaneia gen/book/ e retorna informações de cada versão."""
        versions = []

        if not self.book_dir.exists():
            return versions

        for combo_dir in sorted(self.book_dir.iterdir()):
            if not combo_dir.is_dir():
                continue

            parts = combo_dir.name.split('.')
            if len(parts) != 2:
                continue

            lang_key, locale_key = parts
            lang_info = LANGUAGES.get(lang_key)
            locale_info = LOCALES.get(locale_key)

            if not lang_info or not locale_info:
                continue

            index_file = combo_dir / 'index.html'
            has_index = index_file.exists()

            # Tenta o nome canônico primeiro; se não existir, pega qualquer .pdf na pasta
            pdf_file = combo_dir / f'livro.{locale_key}.{lang_key}.pdf'
            if not pdf_file.exists():
                found = sorted(combo_dir.glob('*.pdf'))
                pdf_file = found[0] if found else pdf_file

            has_pdf = pdf_file.exists()

            index_relative = f"{combo_dir.name}/index.html"
            pdf_relative = (
                f"{combo_dir.name}/{pdf_file.name}"
                if has_pdf else None
            )

            versions.append({
                'key': combo_dir.name,
                'lang_key': lang_key,
                'lang_label': lang_info.label,
                'locale_key': locale_key,
                'locale_label': locale_info.label,
                'quarto_lang': locale_info.quarto_lang,
                'index_path': index_file,
                'index_relative': index_relative,
                'pdf_relative': pdf_relative,
                'has_index': has_index,
                'has_pdf': has_pdf,
                'last_modified': datetime.fromtimestamp(combo_dir.stat().st_mtime)
            })

        return versions

    # ------------------------------------------------------------------
    # Helpers genéricos para manipulação segura de HTML com divs aninhadas
    # ------------------------------------------------------------------

    _TAG_RE = re.compile(r'<div\b[^>]*>|</div>', flags=re.IGNORECASE)

    @classmethod
    def _find_matching_div_end(cls, content: str, start: int) -> int:
        m = cls._TAG_RE.match(content, start)
        if not m or not m.group(0).lower().startswith('<div'):
            return -1

        depth = 1
        pos = m.end()
        while depth > 0:
            m = cls._TAG_RE.search(content, pos)
            if not m:
                return -1
            if m.group(0).lower().startswith('<div'):
                depth += 1
            else:
                depth -= 1
            pos = m.end()
        return pos

    @classmethod
    def _find_class_divs(cls, content: str, region_start: int, region_end: int, class_name: str) -> List[Tuple[int, int]]:
        pattern = re.compile(
            rf'<div[^>]*class="[^"]*{re.escape(class_name)}[^"]*"[^>]*>',
            flags=re.IGNORECASE
        )
        results = []
        for m in pattern.finditer(content, region_start, region_end):
            end = cls._find_matching_div_end(content, m.start())
            if end == -1 or end > region_end:
                continue
            results.append((m.start(), end))
        return results

    @staticmethod
    def _div_text(content: str, start: int, end: int) -> str:
        raw = content[start:end]
        raw = re.sub(r'<[^>]+>', ' ', raw)
        return re.sub(r'\s+', ' ', raw).strip()

    # ------------------------------------------------------------------
    # Painel unificado (metadados + acesso rápido + capas) do index.html
    # de cada versão
    # ------------------------------------------------------------------

    DATE_HEADING_RE = re.compile(
        r'(Data\s+de\s+Publica[çc][ãa]o|Publicado(\s+em)?|Published|'
        r'[ÚU]ltima\s+Atualiza[çc][ãa]o|Last\s+updated|Modified|'
        r'Data\s+de\s+Modifica[çc][ãa]o|^Data$|^Date$)',
        flags=re.IGNORECASE
    )

    META_CONTAINER_RE = re.compile(
        r'<div[^>]*class="[^"]*quarto-title-meta[^"]*"[^>]*>',
        flags=re.IGNORECASE
    )

    # Cobre nativa do Quarto (quando ele já injeta a capa como <img>/<p>)
    NATIVE_COVER_RE = re.compile(
        r'(?:<p[^>]*>\s*)?<img[^>]*class="[^"]*quarto-cover-image[^"]*"[^>]*/?>(?:\s*</p>)?',
        flags=re.IGNORECASE
    )

    PANEL_MARKER = '<!-- pdivc-panel -->'
    PANEL_STYLE_MARKER = '<!-- pdivc-panel-style -->'
    FONTS_MARKER = '<!-- pdivc-fonts -->'

    # Textos fixos do painel injetado em CADA versão (gen/book/<combo>/index.html)
    # — ao contrário do PORTAL_STRINGS (que tem um toggle na mesma página),
    # aqui não tem troca em tempo real: cada versão já É de um locale fixo,
    # então o painel dela é gerado direto no idioma certo (v['locale_key']).
    PANEL_STRINGS: Dict[str, Dict[str, str]] = {
        'pt': {
            'about-edition': 'Sobre esta edição',
            'last-updated':  'Última Atualização',
            'quick-access':  'Acesso rápido',
            'simulators':    'Simuladores Interativos',
            'exercises':     'Exercícios de Programação',
            'download-pdf':  'Baixar PDF',
            'covers':        'Capas do livro',
            'cover-main':    'Capa Principal',
            'cover-back':    'Contracapa',
        },
        'en': {
            'about-edition': 'About this edition',
            'last-updated':  'Last updated',
            'quick-access':  'Quick access',
            'simulators':    'Interactive Simulators',
            'exercises':     'Programming Exercises',
            'download-pdf':  'Download PDF',
            'covers':        'Book covers',
            'cover-main':    'Main Cover',
            'cover-back':    'Back Cover',
        },
        'fr': {
            'about-edition': 'À propos de cette édition',
            'last-updated':  'Dernière mise à jour',
            'quick-access':  'Accès rapide',
            'simulators':    'Simulateurs Interactifs',
            'exercises':     'Exercices de Programmation',
            'download-pdf':  'Télécharger le PDF',
            'covers':        'Couvertures du livre',
            'cover-main':    'Couverture Principale',
            'cover-back':    'Quatrième de Couverture',
        },
    }

    @classmethod
    def _panel_str(cls, locale: str, key: str) -> str:
        return cls.PANEL_STRINGS.get(locale, cls.PANEL_STRINGS['en']).get(
            key, cls.PANEL_STRINGS['en'][key]
        )

    FONTS_LINK_HTML = f'''{FONTS_MARKER}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=Source+Serif+4:ital,opsz,wght@0,8..60,300;0,8..60,400;0,8..60,600;1,8..60,300&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
'''

    PANEL_STYLE_CSS = f'''{PANEL_STYLE_MARKER}
<style>
  .pdivc-panel {{
    position: relative;
    margin: 1.85rem 0 2.6rem;
    padding: 1.7rem 1.85rem 1.9rem;
    background: linear-gradient(150deg, #faf7f2 0%, #f0ebe0 100%);
    border: 1px solid #dcd4c2;
    border-radius: 14px;
    box-shadow: 0 4px 22px rgba(26,22,18,0.09);
    overflow: hidden;
  }}
  .pdivc-panel-accent {{
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 4px;
    background: linear-gradient(90deg, #1a2e4a 0%, #c8963c 100%);
  }}
  .pdivc-panel-section {{
    padding: 1.1rem 0;
    border-bottom: 1px dashed #d8d0c0;
  }}
  .pdivc-panel-section:first-of-type {{ padding-top: 0.35rem; }}
  .pdivc-panel-section-last {{ border-bottom: none; padding-bottom: 0.15rem; }}
  .pdivc-panel-caption {{
    font-family: 'JetBrains Mono', 'Courier New', monospace;
    font-size: 0.68rem;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #8a7f70;
    margin-bottom: 0.9rem;
  }}

  /* Seção 1: pills de metadados */
  .pdivc-pills-row {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.6rem 0.8rem;
  }}
  .pdivc-pill {{
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
    background: #ffffff;
    border: 1px solid #e2d9c8;
    border-radius: 8px;
    padding: 0.5rem 0.9rem;
    min-width: 150px;
  }}
  .pdivc-pill-label {{
    font-family: 'JetBrains Mono', 'Courier New', monospace;
    font-size: 0.62rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #8a7f70;
  }}
  .pdivc-pill-value {{
    font-family: 'Source Serif 4', Georgia, serif;
    font-size: 0.96rem;
    font-weight: 600;
    color: #1a2e4a;
    line-height: 1.3;
  }}
  .pdivc-pill-updated {{
    background: #fff8ea;
    border-color: #ecd49a;
  }}
  .pdivc-pill-updated .pdivc-pill-label {{ color: #a8721c; }}
  .pdivc-pill-updated .pdivc-pill-value {{ color: #8a5c10; }}

  /* Seção 2: ações rápidas */
  .pdivc-actions-row {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
  }}
  .pdivc-action {{
    display: inline-flex;
    align-items: center;
    gap: 0.55rem;
    padding: 0.65rem 1.15rem;
    border-radius: 8px;
    text-decoration: none;
    font-family: 'JetBrains Mono', 'Courier New', monospace;
    font-size: 0.82rem;
    font-weight: 600;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    transition: transform 0.18s ease, box-shadow 0.18s ease;
  }}
  .pdivc-action:hover {{
    transform: translateY(-2px);
    box-shadow: 0 6px 16px rgba(0,0,0,0.14);
  }}
  .pdivc-action-navy   {{ background: #1a2e4a; color: #fff; }}
  .pdivc-action-gold   {{ background: #c8963c; color: #fff; }}
  .pdivc-action-outline {{ background: #fff; color: #1a2e4a; border: 1px solid #d8d0c0; }}
  .pdivc-action-icon {{ font-size: 1rem; line-height: 1; }}

  /* Seção 3: capas */
  .pdivc-covers-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 1.4rem;
  }}
  .pdivc-cover-card {{
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    background: #ffffff;
    padding: 0.9rem;
    border-radius: 10px;
    border: 1px solid rgba(0,0,0,0.06);
    box-shadow: 0 4px 14px rgba(26,22,18,0.07);
    transition: transform 0.22s ease, box-shadow 0.22s ease;
  }}
  .pdivc-cover-card:hover {{
    transform: translateY(-4px);
    box-shadow: 0 10px 24px rgba(26,22,18,0.13);
  }}
  .pdivc-cover-card img {{
    width: 100%;
    max-height: 420px;
    object-fit: contain;
    border-radius: 6px;
  }}
  .pdivc-cover-label {{
    margin-top: 0.75rem;
    font-family: 'JetBrains Mono', 'Courier New', monospace;
    font-size: 0.72rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #1a2e4a;
    font-weight: 600;
  }}

  @media (max-width: 640px) {{
    .pdivc-panel {{ padding: 1.3rem 1.1rem 1.5rem; }}
    .pdivc-pill {{ min-width: 130px; flex: 1 1 auto; }}
    .pdivc-action {{ flex: 1 1 auto; justify-content: center; }}
  }}
</style>
'''

    # ------------------------------------------------------------------
    # Construção das partes do painel
    # ------------------------------------------------------------------

    def _extract_meta_fields(self, content: str, region_start: int, region_end: int) -> List[Tuple[str, str]]:
        """Extrai pares (rótulo, valor) do bloco de metadados nativo do Quarto,
        descartando qualquer campo relacionado a data (será substituído pelo
        pill de 'Última Atualização')."""
        headings = self._find_class_divs(content, region_start, region_end, 'quarto-title-meta-heading')
        contents = self._find_class_divs(content, region_start, region_end, 'quarto-title-meta-contents')

        fields: List[Tuple[str, str]] = []
        for h, c in zip(headings, contents):
            heading_text = self._div_text(content, *h)
            content_text = self._div_text(content, *c)
            if not content_text or self.DATE_HEADING_RE.search(heading_text):
                continue
            fields.append((heading_text, content_text))
        return fields

    @classmethod
    def _build_pills_html(cls, fields: List[Tuple[str, str]], updated_str: str, locale: str) -> str:
        pills = ''
        for label, value in fields:
            pills += f'''
      <div class="pdivc-pill">
        <span class="pdivc-pill-label">{label}</span>
        <span class="pdivc-pill-value">{value}</span>
      </div>'''
        pills += f'''
      <div class="pdivc-pill pdivc-pill-updated">
        <span class="pdivc-pill-label">{cls._panel_str(locale, 'last-updated')}</span>
        <span class="pdivc-pill-value">{updated_str}</span>
      </div>'''
        return pills

    @classmethod
    def _build_actions_html(cls, combo_key: str, has_pdf: bool, pdf_relative: Optional[str],
                            locale: str) -> str:
        simuladores_url = f"https://fzampirolli.github.io/pdi-vc/simuladores/{combo_key}/index.html"
        eps_url = f"https://fzampirolli.github.io/pdi-vc/eps/{combo_key}/index.html"

        # Usa URL absoluta (mesmo padrão dos botões acima) para não depender
        # da resolução de caminho relativo da página atual — evita duplicar
        # o diretório da versão (ex: py.pt/py.pt/...).
        pdf_filename = Path(pdf_relative).name if pdf_relative else None
        pdf_url = (
            f"https://fzampirolli.github.io/pdi-vc/{combo_key}/{pdf_filename}"
            if pdf_filename else None
        )

        actions = f'''
      <a class="pdivc-action pdivc-action-navy" href="{simuladores_url}" target="_blank" rel="noopener">
        <span class="pdivc-action-icon">🕹️</span><span>{cls._panel_str(locale, 'simulators')}</span>
      </a>
      <a class="pdivc-action pdivc-action-gold" href="{eps_url}" target="_blank" rel="noopener">
        <span class="pdivc-action-icon">📝</span><span>{cls._panel_str(locale, 'exercises')}</span>
      </a>'''

        if has_pdf and pdf_url:
            actions += f'''
      <a class="pdivc-action pdivc-action-outline" href="{pdf_url}" target="_blank" rel="noopener">
        <span class="pdivc-action-icon">📄</span><span>{cls._panel_str(locale, 'download-pdf')}</span>
      </a>'''

        return actions

    @classmethod
    def _build_covers_html(cls, locale: str) -> str:
        cover_main = cls._panel_str(locale, 'cover-main')
        cover_back = cls._panel_str(locale, 'cover-back')
        return f'''
      <div class="pdivc-covers-grid">
        <div class="pdivc-cover-card">
          <img src="girassol_capa.png" alt="{cover_main}">
          <div class="pdivc-cover-label">{cover_main}</div>
        </div>
        <div class="pdivc-cover-card">
          <img src="girassol_contracapa.png" alt="{cover_back}">
          <div class="pdivc-cover-label">{cover_back}</div>
        </div>
      </div>'''

    def _build_panel_html(self, pills_html: str, actions_html: str, covers_html: str,
                          locale: str) -> str:
        return f'''{self.PANEL_MARKER}
<div class="pdivc-panel">
  <div class="pdivc-panel-accent"></div>
  <section class="pdivc-panel-section">
    <div class="pdivc-panel-caption">{self._panel_str(locale, 'about-edition')}</div>
    <div class="pdivc-pills-row">{pills_html}
    </div>
  </section>
  <section class="pdivc-panel-section">
    <div class="pdivc-panel-caption">{self._panel_str(locale, 'quick-access')}</div>
    <div class="pdivc-actions-row">{actions_html}
    </div>
  </section>
  <section class="pdivc-panel-section pdivc-panel-section-last">
    <div class="pdivc-panel-caption">{self._panel_str(locale, 'covers')}</div>{covers_html}
  </section>
</div>
'''

    def _ensure_fonts(self, content: str) -> str:
        if self.FONTS_MARKER in content or '</head>' not in content:
            return content
        return content.replace('</head>', self.FONTS_LINK_HTML + '</head>', 1)

    def _ensure_panel_style(self, content: str) -> str:
        if self.PANEL_STYLE_MARKER in content:
            return content
        if '</head>' in content:
            return content.replace('</head>', self.PANEL_STYLE_CSS + '</head>', 1)
        return self.PANEL_STYLE_CSS + content

    def inject_last_updated_in_subversions(self, versions: List[Dict], updated: Dict[str, str]) -> None:
        """Substitui o bloco nativo de metadados do Quarto por um painel único
        (metadados + acesso rápido + capas) em cada index.html de versão."""
        for v in versions:
            index_file: Path = v['index_path']
            if not index_file.exists():
                continue

            content = index_file.read_text(encoding='utf-8')

            if self.PANEL_MARKER in content:
                print(f'  → Painel já presente, pulando: {index_file}')
                continue

            # Remove qualquer capa nativa do Quarto, já que teremos nossa própria
            content = self.NATIVE_COVER_RE.sub('', content)

            m = self.META_CONTAINER_RE.search(content)
            fields: List[Tuple[str, str]] = []
            replace_start: Optional[int] = None
            replace_end: Optional[int] = None

            if m:
                container_start = m.start()
                container_end = self._find_matching_div_end(content, container_start)
                if container_end != -1:
                    insert_at = m.end()
                    inner_region_end = container_end - len('</div>')
                    fields = self._extract_meta_fields(content, insert_at, inner_region_end)
                    replace_start, replace_end = container_start, container_end

            locale = v['locale_key']
            updated_str = updated.get(locale, updated['en'])
            pills_html = self._build_pills_html(fields, updated_str, locale)
            actions_html = self._build_actions_html(v['key'], v['has_pdf'], v['pdf_relative'], locale)
            covers_html = self._build_covers_html(locale)
            panel_html = self._build_panel_html(pills_html, actions_html, covers_html, locale)

            if replace_start is not None and replace_end is not None:
                content = content[:replace_start] + panel_html + content[replace_end:]
            elif '</header>' in content:
                content = content.replace('</header>', '</header>\n' + panel_html, 1)
            else:
                content = panel_html + content

            content = self._ensure_fonts(content)
            content = self._ensure_panel_style(content)

            index_file.write_text(content, encoding='utf-8')
            print(f'  ✓ Painel unificado (metadados + links + capas) organizado em: {index_file}')

    # Só py.pt (fonte canônica, escrita à mão) é considerado validado. As
    # demais combinações são geradas por LLM e mostram, ao passar o mouse,
    # o que falta pra validar — o texto no idioma da própria versão, não
    # no idioma de quem está mantendo o livro. {combo} e {locale} são
    # preenchidos por versão (ver _build_validation_hint), então a dica já
    # sai com o caminho e o marcador certos pra aquele card específico.
    VALIDATION_HINT_TEMPLATES: Dict[str, str] = {
        'pt': ('Conteúdo gerado automaticamente — ainda sem revisão humana completa. '
               'Para validar:\n'
               '✏ Código/texto: edite a célula em gen/{combo}/capXX/ e rode '
               '"python dev.py --promote-edits".\n'
               '🖼 Imagem errada: crie um arquivo com sufixo ao lado do original, '
               'ex. nome.{locale}.png, em all/capXX/imagens/.\n'
               '🔒 Célula manual só p/ este combo: comece a linha com '
               '#[{combo}]#.'),
        'en': ('Automatically generated content — not yet fully reviewed by a human. '
               'To validate:\n'
               '✏ Code/text: edit the cell in gen/{combo}/capXX/ and run '
               '"python dev.py --promote-edits".\n'
               '🖼 Wrong image: add a suffixed file next to the original, '
               'e.g. name.{locale}.png, in all/capXX/imagens/.\n'
               '🔒 Manual cell for this combo only: start the line with '
               '#[{combo}]#.'),
        'fr': ('Contenu généré automatiquement — pas encore entièrement révisé par un '
               'humain. Pour valider :\n'
               '✏ Code/texte : modifiez la cellule dans gen/{combo}/capXX/ puis lancez '
               '"python dev.py --promote-edits".\n'
               '🖼 Image incorrecte : ajoutez un fichier avec suffixe à côté de '
               "l'original, ex. nom.{locale}.png, dans all/capXX/imagens/.\n"
               '🔒 Cellule manuelle réservée à ce combo : commencez la ligne par '
               '#[{combo}]#.'),
    }

    def _build_validation_hint(self, v: Dict) -> str:
        template = self.VALIDATION_HINT_TEMPLATES.get(
            v['locale_key'], self.VALIDATION_HINT_TEMPLATES['en']
        )
        return template.format(combo=v['key'], locale=v['locale_key'], lang=v['lang_key'])

    # Textos fixos do PORTAL (gen/book/index.html) — não confundir com
    # VALIDATION_HINT_TEMPLATES, que é por card/combo. O toggle PT/EN no
    # topo da página troca só isso, via JS, sem recarregar. {updated} é
    # preenchido em generate_html() com a data já formatada no idioma certo.
    PORTAL_STRINGS: Dict[str, Dict[str, str]] = {
        'pt': {
            'title-tag':    'PDI+VC — Livro Interativo',
            'eyebrow':      'UFABC · Material didático interativo',
            'hero-title':   'Processamento Digital<br>de Imagens e<br><em>Visão Computacional</em>',
            'hero-sub':     ('Livro aberto, multi-linguagem e multi-idioma para cursos de '
                              'graduação e pós-graduação em Computação e Engenharias.'),
            'stat-versions':'versões',
            'stat-langs':   'linguagens',
            'stat-locales': 'idiomas',
            'scroll':       'Ver todas as versões',
            'section-title':'Versões disponíveis',
            'cta-available':'📖 Acessar livro',
            'cta-soon':     '⏳ Em breve',
            'pdf-btn':      '📄 PDF',
            'pdf-title':    'Baixar PDF',
            'pdf-soon':     '📄 Em breve',
            'validated':    '✓ Validado',
            'footer-title': 'PDI+VC — Processamento Digital de Imagens e Visão Computacional',
            'footer-license':'Material didático aberto sob licença',
            'updated-prefix':'⏱ Atualizado em {date}',
        },
        'en': {
            'title-tag':    'PDI+VC — Interactive Book',
            'eyebrow':      'UFABC · Interactive teaching material',
            'hero-title':   'Digital Image<br>Processing and<br><em>Computer Vision</em>',
            'hero-sub':     ('Open, multi-language, multi-locale book for undergraduate and '
                              'graduate Computing and Engineering courses.'),
            'stat-versions':'versions',
            'stat-langs':   'languages',
            'stat-locales': 'locales',
            'scroll':       'See all versions',
            'section-title':'Available versions',
            'cta-available':'📖 Open book',
            'cta-soon':     '⏳ Coming soon',
            'pdf-btn':      '📄 PDF',
            'pdf-title':    'Download PDF',
            'pdf-soon':     '📄 Coming soon',
            'validated':    '✓ Validated',
            'footer-title': 'PDI+VC — Digital Image Processing and Computer Vision',
            'footer-license':'Open teaching material under license',
            'updated-prefix':'⏱ Updated on {date}',
        },
        'fr': {
            'title-tag':    'PDI+VC — Livre Interactif',
            'eyebrow':      'UFABC · Matériel pédagogique interactif',
            'hero-title':   'Traitement Numérique<br>d\'Images et<br><em>Vision par Ordinateur</em>',
            'hero-sub':     ('Livre ouvert, multi-langage et multilingue pour les cours de '
                              'licence et master en Informatique et Ingénierie.'),
            'stat-versions':'versions',
            'stat-langs':   'langages',
            'stat-locales': 'langues',
            'scroll':       'Voir toutes les versions',
            'section-title':'Versions disponibles',
            'cta-available':'📖 Ouvrir le livre',
            'cta-soon':     '⏳ Bientôt disponible',
            'pdf-btn':      '📄 PDF',
            'pdf-title':    'Télécharger le PDF',
            'pdf-soon':     '📄 Bientôt disponible',
            'validated':    '✓ Validé',
            'footer-title': "PDI+VC — Traitement Numérique d'Images et Vision par Ordinateur",
            'footer-license':'Matériel pédagogique ouvert sous licence',
            'updated-prefix':'⏱ Mis à jour le {date}',
        },
    }

    MESES_PT = ['', 'janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
                'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']
    MESES_EN = ['', 'January', 'February', 'March', 'April', 'May', 'June',
                'July', 'August', 'September', 'October', 'November', 'December']
    MESES_FR = ['', 'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
                'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']

    def _updated_strings(self, now: datetime) -> Dict[str, str]:
        """Data/hora formatada por locale — SEM prefixo (usado tanto na pill
        'Última Atualização' do painel de cada versão quanto, com o prefixo
        '⏱ Atualizado em'/'⏱ Updated on' montado à parte, no hero do portal)."""
        pt = f"{now.day} de {self.MESES_PT[now.month]} de {now.year} às {now.strftime('%H:%M')}"
        en = f"{self.MESES_EN[now.month]} {now.day}, {now.year} at {now.strftime('%H:%M')}"
        fr = f"{now.day} {self.MESES_FR[now.month]} {now.year} à {now.strftime('%H:%M')}"
        return {'pt': pt, 'en': en, 'fr': fr}

    def generate_html(self, versions: List[Dict], updated: Dict[str, str]) -> str:
        """Gera o HTML principal com design editorial refinado."""
        cover_img = 'girassol_all.png'

        by_lang: dict = {}
        for v in versions:
            lang = v['lang_key']
            if lang not in by_lang:
                by_lang[lang] = []
            by_lang[lang].append(v)

        lang_icons = {'py': '🐍', 'cpp': '⚙️', 'java': '☕', 'c': '🔧', 'rust': '🦀', 'go': '🏃'}

        cards_html = ''
        # py sempre primeiro (é a linguagem-base, tem a versão validada);
        # as demais seguem em ordem alfabética.
        for lang_key, vlist in sorted(by_lang.items(), key=lambda kv: (kv[0] != BASE_LANG, kv[0])):
            icon = lang_icons.get(lang_key, '💻')
            lang_label = vlist[0]['lang_label']
            cards_html += f'''
      <div class="lang-group">
        <div class="lang-label">
          <span class="lang-icon">{icon}</span>
          <span>{lang_label}</span>
        </div>
        <div class="cards-row">'''
            for v in vlist:
                link       = v['index_relative'] if v['has_index'] else '#'
                pdf_link   = v['pdf_relative'] or '#'
                disabled   = 'disabled' if not v['has_index'] else ''
                is_validated = v['lang_key'] == BASE_LANG and v['locale_key'] == BASE_LOCALE
                validated_cls = 'version-card-validated' if is_validated else ''
                ribbon = ('<span class="validated-ribbon" data-i18n="validated">✓ Validado</span>'
                          if is_validated else '')
                tooltip_attr = ''
                if not is_validated:
                    hint = self._build_validation_hint(v)
                    tooltip_attr = f' data-tooltip="{html_escape(hint)}"'
                pdf_badge  = (
                    f'<a class="badge badge-pdf" href="{pdf_link}" '
                    f'title="Baixar PDF" data-i18n-title="pdf-title" data-i18n="pdf-btn">📄 PDF</a>'
                    if v['has_pdf'] else
                    '<span class="badge badge-soon" data-i18n="pdf-soon">📄 Em breve</span>'
                )
                cta_key = 'cta-available' if v['has_index'] else 'cta-soon'
                cta_text = '📖 Acessar livro' if v['has_index'] else '⏳ Em breve'
                cards_html += f'''
          <div class="version-card {disabled} {validated_cls}"{tooltip_attr}>
            {ribbon}
            <a class="card-main" href="{link}">
              <div class="card-locale">{v["locale_label"]}</div>
              <div class="card-lang-code">{v["quarto_lang"].upper()}</div>
              <div class="card-cta" data-i18n="{cta_key}">{cta_text}</div>
            </a>
            <div class="card-footer">
              {pdf_badge}
            </div>
          </div>'''
            cards_html += '''
        </div>
      </div>'''

        n_versions = len(versions)
        n_langs    = len(set(v['lang_key'] for v in versions))
        n_locales  = len(set(v['locale_key'] for v in versions))

        i18n = {
            lang: {**strings, 'updated': strings['updated-prefix'].format(
                date=updated.get(lang, updated['en'])
            )}
            for lang, strings in self.PORTAL_STRINGS.items()
        }
        # Evita fechar a tag <script> se algum texto contiver "</script>".
        i18n_json = json.dumps(i18n, ensure_ascii=False).replace('</script', '<\\/script')
        hero_updated_pt = i18n['pt']['updated']

        html = f'''<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title data-i18n="title-tag">PDI+VC — Livro Interativo</title>
  <link rel="icon" type="image/x-icon" href="favicon.ico">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=Source+Serif+4:ital,opsz,wght@0,8..60,300;0,8..60,400;1,8..60,300&family=JetBrains+Mono:wght@400&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    :root {{
      --ink:      #1a1612;
      --paper:    #faf7f2;
      --cream:    #f0ebe0;
      --gold:     #c8963c;
      --gold-lt:  #e8c070;
      --navy:     #1a2e4a;
      --navy-lt:  #2a4a6a;
      --muted:    #6b6058;
      --border:   #d8d0c0;
      --radius:   10px;
      --shadow:   0 4px 24px rgba(26,22,18,0.13);
    }}

    html {{ scroll-behavior: smooth; }}

    body {{
      font-family: 'Source Serif 4', Georgia, serif;
      background: var(--paper);
      color: var(--ink);
      min-height: 100vh;
    }}

    .hero {{
      position: relative;
      width: 100%;
      min-height: 100vh;
      display: grid;
      grid-template-columns: 1fr 1fr;
      overflow: hidden;
    }}

    .hero-cover {{
      position: relative;
      overflow: hidden;
    }}
    .hero-cover img {{
      width: 100%;
      height: 100%;
      object-fit: cover;
      object-position: center center;
      display: block;
    }}
    .hero-cover::after {{
      content: '';
      position: absolute;
      inset: 0;
      background: linear-gradient(to right, transparent 70%, var(--navy) 100%);
      pointer-events: none;
    }}

    .hero-text {{
      background: var(--navy);
      display: flex;
      flex-direction: column;
      justify-content: center;
      padding: 4rem 3.5rem;
      gap: 2rem;
    }}

    .hero-eyebrow {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.72rem;
      letter-spacing: 0.22em;
      text-transform: uppercase;
      color: var(--gold-lt);
      opacity: 0.85;
    }}

    .hero-title {{
      font-family: 'Playfair Display', Georgia, serif;
      font-weight: 900;
      font-size: clamp(2rem, 3.2vw, 3rem);
      line-height: 1.15;
      color: #fff;
    }}
    .hero-title em {{
      color: var(--gold-lt);
      font-style: normal;
    }}

    .hero-sub {{
      font-size: 1rem;
      color: #c8d8e8;
      line-height: 1.7;
      max-width: 36ch;
    }}

    .hero-stats {{
      display: flex;
      gap: 1.6rem;
      flex-wrap: wrap;
    }}
    .stat {{
      display: flex;
      flex-direction: column;
      align-items: flex-start;
      gap: 0.1rem;
    }}
    .stat-num {{
      font-family: 'Playfair Display', Georgia, serif;
      font-size: 2.4rem;
      font-weight: 700;
      color: var(--gold-lt);
      line-height: 1;
    }}
    .stat-label {{
      font-size: 0.78rem;
      letter-spacing: 0.08em;
      color: #a0b8cc;
      text-transform: uppercase;
    }}

    .hero-updated {{
      font-size: 0.75rem;
      color: #6888a0;
      font-family: 'JetBrains Mono', monospace;
    }}

    .hero-scroll {{
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
      color: var(--gold-lt);
      font-size: 0.85rem;
      text-decoration: none;
      opacity: 0.8;
      transition: opacity 0.2s;
      margin-top: auto;
    }}
    .hero-scroll:hover {{ opacity: 1; }}
    .hero-scroll-arrow {{
      animation: bounce 1.6s ease-in-out infinite;
    }}
    @keyframes bounce {{
      0%, 100% {{ transform: translateY(0); }}
      50%       {{ transform: translateY(5px); }}
    }}

    .lang-toggle {{
      position: absolute;
      top: 1.4rem;
      right: 1.4rem;
      z-index: 10;
      display: inline-flex;
      background: rgba(255,255,255,0.12);
      border: 1px solid rgba(255,255,255,0.28);
      border-radius: 999px;
      padding: 0.2rem;
      backdrop-filter: blur(4px);
    }}
    .lang-toggle-btn {{
      border: none;
      background: transparent;
      color: #cfe0ee;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.72rem;
      font-weight: 600;
      letter-spacing: 0.06em;
      padding: 0.32rem 0.75rem;
      border-radius: 999px;
      cursor: pointer;
      transition: background 0.18s, color 0.18s;
    }}
    .lang-toggle-btn:hover {{ color: #fff; }}
    .lang-toggle-btn.active {{
      background: var(--gold-lt);
      color: var(--navy);
    }}

    #versions {{
      max-width: 1060px;
      margin: 0 auto;
      padding: 5rem 2rem 4rem;
    }}

    .section-header {{
      display: flex;
      align-items: baseline;
      gap: 1rem;
      margin-bottom: 3rem;
      border-bottom: 2px solid var(--border);
      padding-bottom: 1rem;
    }}
    .section-title {{
      font-family: 'Playfair Display', Georgia, serif;
      font-size: 1.9rem;
      font-weight: 700;
      color: var(--navy);
    }}
    .section-rule {{
      flex: 1;
      height: 1px;
      background: var(--border);
    }}

    .lang-group {{ margin-bottom: 2.8rem; }}
    .lang-label {{
      display: flex;
      align-items: center;
      gap: 0.6rem;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.78rem;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      color: var(--muted);
      margin-bottom: 1rem;
      padding-left: 0.2rem;
    }}
    .lang-icon {{ font-size: 1.1rem; }}

    .cards-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 1.2rem;
    }}

    .version-card {{
      position: relative;
      background: #fff;
      border: 1px solid var(--border);
      border-radius: var(--radius);
      overflow: visible;
      width: 220px;
      box-shadow: var(--shadow);
      transition: transform 0.22s ease, box-shadow 0.22s ease;
    }}
    .version-card:not(.disabled):hover {{
      transform: translateY(-5px);
      box-shadow: 0 10px 32px rgba(26,22,18,0.18);
    }}
    .version-card.disabled {{ opacity: 0.52; cursor: not-allowed; }}

    /* py.pt — fonte canônica, escrita à mão, sem tradução de LLM */
    .version-card-validated {{
      border-color: #2e7d4f;
      box-shadow: 0 4px 18px rgba(46,125,79,0.25);
    }}
    .version-card-validated .card-main {{
      background: linear-gradient(150deg, var(--navy) 55%, #1f5c3d 100%);
    }}
    .validated-ribbon {{
      position: absolute;
      top: 0.6rem;
      right: 0.6rem;
      z-index: 2;
      background: #2e7d4f;
      color: #fff;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.6rem;
      font-weight: 700;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      padding: 0.22rem 0.5rem;
      border-radius: 5px;
      box-shadow: 0 2px 6px rgba(0,0,0,0.2);
      pointer-events: none;
    }}

    /* Demais combos: tooltip com o que falta validar, no idioma da versão */
    .version-card[data-tooltip] {{ cursor: help; }}
    .version-card[data-tooltip]:hover::after {{
      content: attr(data-tooltip);
      white-space: pre-line;
      position: absolute;
      bottom: calc(100% + 10px);
      left: 50%;
      transform: translateX(-50%);
      width: 300px;
      text-align: left;
      background: var(--navy);
      color: #e8eef4;
      font-family: 'Source Serif 4', Georgia, serif;
      font-size: 0.76rem;
      line-height: 1.55;
      padding: 0.8rem 0.95rem;
      border-radius: 8px;
      box-shadow: 0 10px 28px rgba(0,0,0,0.28);
      z-index: 30;
      pointer-events: none;
    }}

    .card-main {{
      display: block;
      background: var(--navy);
      border-radius: var(--radius) var(--radius) 0 0;
      padding: 1.5rem 1.2rem 1.2rem;
      text-decoration: none;
      color: #fff;
      transition: background 0.2s;
    }}
    .version-card:not(.disabled) .card-main:hover {{ background: var(--navy-lt); }}

    .card-locale {{
      font-family: 'Playfair Display', Georgia, serif;
      font-size: 1.2rem;
      font-weight: 700;
      margin-bottom: 0.3rem;
    }}
    .card-lang-code {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.7rem;
      letter-spacing: 0.12em;
      color: var(--gold-lt);
      margin-bottom: 1rem;
    }}
    .card-cta {{ font-size: 0.8rem; color: #a8c0d8; }}

    .card-footer {{
      padding: 0.7rem 1.2rem;
      display: flex;
      gap: 0.5rem;
      flex-wrap: wrap;
      background: var(--cream);
      border-top: 1px solid var(--border);
      border-radius: 0 0 var(--radius) var(--radius);
    }}
    .badge {{
      font-size: 0.73rem;
      padding: 0.25rem 0.6rem;
      border-radius: 4px;
      text-decoration: none;
      font-family: 'JetBrains Mono', monospace;
    }}
    .badge-pdf {{
      background: #fff0f0;
      color: #c0392b;
      border: 1px solid #f0c0b8;
      transition: background 0.15s;
    }}
    .badge-pdf:hover {{ background: #ffe0d8; }}
    .badge-soon {{
      background: var(--cream);
      color: var(--muted);
      border: 1px solid var(--border);
    }}

    footer {{
      background: var(--navy);
      color: #7898b0;
      text-align: center;
      padding: 2rem 1rem;
      font-size: 0.82rem;
      font-family: 'JetBrains Mono', monospace;
    }}
    footer a {{ color: var(--gold-lt); text-decoration: none; }}
    footer a:hover {{ text-decoration: underline; }}

    @media (max-width: 820px) {{
      .hero {{
        grid-template-columns: 1fr;
        min-height: auto;
      }}
      .hero-cover {{
        height: 70vw;
        max-height: 420px;
      }}
      .hero-cover img {{
        object-position: center center;
      }}
      .hero-cover::after {{
        background: linear-gradient(to bottom, transparent 55%, var(--navy) 100%);
      }}
      .hero-text {{
        padding: 2.5rem 1.5rem;
      }}
      #versions {{ padding: 3rem 1rem 3rem; }}
      .version-card {{ width: 100%; max-width: 340px; }}
    }}

    @media (max-width: 400px) {{
      .hero-cover {{
        height: 80vw;
        max-height: 320px;
      }}
    }}
  </style>
</head>
<body>

<section class="hero">
  <div class="lang-toggle">
    <button class="lang-toggle-btn active" data-lang="pt">PT</button>
    <button class="lang-toggle-btn" data-lang="en">EN</button>
    <button class="lang-toggle-btn" data-lang="fr">FR</button>
  </div>
  <div class="hero-cover">
    <img src="{cover_img}" alt="Capa do livro — girassol processado digitalmente">
  </div>
  <div class="hero-text">
    <p class="hero-eyebrow" data-i18n="eyebrow">UFABC · Material didático interativo</p>
    <h1 class="hero-title" data-i18n="hero-title">
      Processamento Digital<br>de Imagens e<br>
      <em>Visão Computacional</em>
    </h1>
    <p class="hero-sub" data-i18n="hero-sub">
      Livro aberto, multi-linguagem e multi-idioma para cursos de
      graduação e pós-graduação em Computação e Engenharias.
    </p>
    <div class="hero-stats">
      <div class="stat">
        <span class="stat-num">{n_versions}</span>
        <span class="stat-label" data-i18n="stat-versions">versões</span>
      </div>
      <div class="stat">
        <span class="stat-num">{n_langs}</span>
        <span class="stat-label" data-i18n="stat-langs">linguagens</span>
      </div>
      <div class="stat">
        <span class="stat-num">{n_locales}</span>
        <span class="stat-label" data-i18n="stat-locales">idiomas</span>
      </div>
    </div>
    <p class="hero-updated" data-i18n="updated">{hero_updated_pt}</p>
    <a class="hero-scroll" href="#versions">
      <span class="hero-scroll-arrow">↓</span>
      <span data-i18n="scroll">Ver todas as versões</span>
    </a>
  </div>
</section>

<main id="versions">
  <div class="section-header">
    <h2 class="section-title" data-i18n="section-title">Versões disponíveis</h2>
    <div class="section-rule"></div>
  </div>
{cards_html}
</main>

<footer class="sim-frame-footer">
  <p>
    <strong><a href="https://fzampirolli.github.io/pdi-vc/index.html" target="_blank" data-i18n="footer-title">PDI+VC — Processamento Digital de Imagens e Visão Computacional</a></strong><br>
    © {datetime.now().year} <a href="https://sites.google.com/site/fzampirolli/" target="_blank">Francisco de Assis Zampirolli</a> — <a href="https://sites.google.com/site/fzampirolli/" target="_blank">Universidade Federal do ABC (UFABC)</a>.<br>
    <span data-i18n="footer-license">Material didático aberto sob licença</span> <a href="https://creativecommons.org/licenses/by-sa/4.0" target="_blank">CC BY-SA 4.0</a> ·
    DOI: <a href="https://doi.org/10.5281/zenodo.20784606" target="_blank">10.5281/zenodo.20784606</a>
  </p>
</footer>

<script>
  const I18N = {i18n_json};

  function applyLang(lang) {{
    if (!I18N[lang]) return;
    document.documentElement.lang = (lang === 'pt') ? 'pt-BR' : 'en';
    document.querySelectorAll('[data-i18n]').forEach(function (el) {{
      const key = el.getAttribute('data-i18n');
      if (I18N[lang][key] !== undefined) el.innerHTML = I18N[lang][key];
    }});
    document.querySelectorAll('[data-i18n-title]').forEach(function (el) {{
      const key = el.getAttribute('data-i18n-title');
      if (I18N[lang][key] !== undefined) el.setAttribute('title', I18N[lang][key]);
    }});
    document.querySelectorAll('.lang-toggle-btn').forEach(function (btn) {{
      btn.classList.toggle('active', btn.getAttribute('data-lang') === lang);
    }});
    try {{ localStorage.setItem('pdivc-lang', lang); }} catch (e) {{}}
  }}

  document.querySelectorAll('.lang-toggle-btn').forEach(function (btn) {{
    btn.addEventListener('click', function () {{ applyLang(btn.getAttribute('data-lang')); }});
  }});

  let savedLang = 'pt';
  try {{ savedLang = localStorage.getItem('pdivc-lang') || 'pt'; }} catch (e) {{}}
  if (savedLang !== 'pt') applyLang(savedLang);
</script>

</body>
</html>
'''
        return html

    def build(self) -> Path:
        """Constrói a página index.html principal dentro de gen/book/ e atualiza subversões."""
        self.book_dir.mkdir(parents=True, exist_ok=True)

        versions = self.scan_versions()

        if not versions:
            print('⚠️ Nenhuma versão encontrada em gen/book/')
            print('   Execute o pipeline primeiro: make build LANGS=py,cpp LOCALES=pt,en')
            return self.index_path

        # Copia capa principal e favicon para a raiz de gen/book/
        cover_src = self.root / 'includes' / 'girassol_all.png'
        cover_dst = self.book_dir / 'girassol_all.png'
        if cover_src.exists():
            shutil.copy2(cover_src, cover_dst)
            print(f'  ✓ Capa copiada para {cover_dst}')

        fav_src = self.root / 'includes' / 'favicon.ico'
        fav_dst = self.book_dir / 'favicon.ico'
        if fav_src.exists():
            shutil.copy2(fav_src, fav_dst)
            print(f'  ✓ Favicon copiado para {fav_dst}')

        # Copia girassol_capa.png e girassol_contracapa.png para dentro de cada
        # versão gerada (ex: gen/book/py.pt/) — com override por locale
        # (girassol_capa.<locale>.png), mesma convenção de all/capXX/imagens/
        # (ver quarto_builder.py::_locale_asset).
        girassol_capa = self.root / 'includes' / 'girassol_capa.png'
        girassol_contracapa_src = self.root / 'includes' / 'girassol_contracapa.png'

        def _cover_for_locale(base: Path, locale: str) -> Path:
            if locale == BASE_LOCALE:
                return base
            localized = base.parent / f'{base.stem}.{locale}{base.suffix}'
            return localized if localized.exists() else base

        for v in versions:
            combo_dir = self.book_dir / v['key']
            if combo_dir.exists():
                capa_src = _cover_for_locale(girassol_capa, v['locale_key'])
                if capa_src.exists():
                    shutil.copy2(capa_src, combo_dir / 'girassol_capa.png')
                contracapa_src = _cover_for_locale(girassol_contracapa_src, v['locale_key'])
                if contracapa_src.exists():
                    shutil.copy2(contracapa_src, combo_dir / 'girassol_contracapa.png')

        now = datetime.now()
        updated_texts = self._updated_strings(now)

        # 1. Injeta o painel unificado (metadados + acesso rápido + capas) em cada
        #    versão, já no idioma daquela versão (v['locale_key'])
        self.inject_last_updated_in_subversions(versions, updated_texts)

        # 2. Gera o portal principal gen/book/index.html
        html_content = self.generate_html(versions, updated_texts)
        self.index_path.write_text(html_content, encoding='utf-8')

        print(f'✅ Página principal gerada: {self.index_path}')
        print(f'   📊 {len(versions)} versões encontradas')
        print(f'\n🌐 Abrir no navegador: file://{self.index_path.absolute()}')

        return self.index_path


if __name__ == '__main__':
    builder = IndexBuilder()
    builder.build()