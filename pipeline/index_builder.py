"""
pipeline/index_builder.py
=========================
Gera página principal minimalista com links para cada versão.
O index.html fica em gen/book/index.html (junto com as versões geradas).
"""

from __future__ import annotations

from pathlib import Path
from datetime import datetime
from typing import List, Dict

from .config import LANGUAGES, LOCALES

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

            # PDF no formato:
            # livro.<locale>.<lang>.pdf
            # exemplo: livro.pt.py.pdf

            pdf_file = combo_dir / f'livro.{locale_key}.{lang_key}.pdf'
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
    
    def generate_html(self, versions: List[Dict]) -> str:
        """Gera o HTML principal com design editorial refinado."""
        
        # Caminho relativo da imagem de capa a partir de gen/book/
        # A imagem fica em includes/capa_girassol1.png → relativo: ../../includes/capa_girassol1.png
        cover_img = '../../includes/capa_girassol1.png'
        cover_img = 'https://raw.githubusercontent.com/fzampirolli/pdi-vc/main/includes/capa_girassol1.png'

        by_lang: dict = {}
        for v in versions:
            lang = v['lang_key']
            if lang not in by_lang:
                by_lang[lang] = []
            by_lang[lang].append(v)

        lang_icons = {'py': '🐍', 'cpp': '⚙️', 'java': '☕', 'c': '🔧', 'rust': '🦀', 'go': '🏃'}

        # ── Gera os cards de versão ───────────────────────────────────────────
        cards_html = ''
        for lang_key, vlist in sorted(by_lang.items()):
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
                pdf_badge  = (
                    f'<a class="badge badge-pdf" href="{pdf_link}" title="Baixar PDF">⬇ PDF</a>'
                    if v['has_pdf'] else
                    '<span class="badge badge-soon">PDF em breve</span>'
                )
                cards_html += f'''
          <div class="version-card {disabled}">
            <a class="card-main" href="{link}">
              <div class="card-locale">{v["locale_label"]}</div>
              <div class="card-lang-code">{v["quarto_lang"].upper()}</div>
              <div class="card-cta">{"📖 Acessar livro" if v["has_index"] else "⏳ Em breve"}</div>
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
        updated    = datetime.now().strftime('%d/%m/%Y %H:%M')

        html = f'''<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PDI+VC — Livro Interativo</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=Source+Serif+4:ital,opsz,wght@0,8..60,300;0,8..60,400;1,8..60,300&family=JetBrains+Mono:wght@400&display=swap" rel="stylesheet">
  <style>
    /* ── Reset & base ────────────────────────────────────────────────── */
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

    /* ── Hero ────────────────────────────────────────────────────────── */
    .hero {{
      position: relative;
      width: 100%;
      min-height: 100vh;
      display: grid;
      grid-template-columns: 1fr 1fr;
      overflow: hidden;
    }}

    /* Lado esquerdo: imagem de capa */
    .hero-cover {{
      position: relative;
      overflow: hidden;
    }}
    .hero-cover img {{
      width: 100%;
      height: 100%;
      object-fit: cover;
      object-position: center top;
      display: block;
    }}
    /* overlay sutil para garantir legibilidade da faixa direita */
    .hero-cover::after {{
      content: '';
      position: absolute;
      inset: 0;
      background: linear-gradient(to right, transparent 70%, var(--navy) 100%);
      pointer-events: none;
    }}

    /* Lado direito: texto */
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

    /* ── Versions section ────────────────────────────────────────────── */
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

    /* ── Language group ──────────────────────────────────────────────── */
    .lang-group {{
      margin-bottom: 2.8rem;
    }}
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
    .lang-icon {{
      font-size: 1.1rem;
    }}

    .cards-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 1.2rem;
    }}

    /* ── Version card ────────────────────────────────────────────────── */
    .version-card {{
      background: #fff;
      border: 1px solid var(--border);
      border-radius: var(--radius);
      overflow: hidden;
      width: 220px;
      box-shadow: var(--shadow);
      transition: transform 0.22s ease, box-shadow 0.22s ease;
    }}
    .version-card:not(.disabled):hover {{
      transform: translateY(-5px);
      box-shadow: 0 10px 32px rgba(26,22,18,0.18);
    }}
    .version-card.disabled {{
      opacity: 0.52;
      cursor: not-allowed;
    }}

    .card-main {{
      display: block;
      background: var(--navy);
      padding: 1.5rem 1.2rem 1.2rem;
      text-decoration: none;
      color: #fff;
      transition: background 0.2s;
    }}
    .version-card:not(.disabled) .card-main:hover {{
      background: var(--navy-lt);
    }}

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
    .card-cta {{
      font-size: 0.8rem;
      color: #a8c0d8;
    }}

    .card-footer {{
      padding: 0.7rem 1.2rem;
      display: flex;
      gap: 0.5rem;
      flex-wrap: wrap;
      background: var(--cream);
      border-top: 1px solid var(--border);
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

    /* ── Footer ──────────────────────────────────────────────────────── */
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

    /* ── Responsive ──────────────────────────────────────────────────── */
    @media (max-width: 820px) {{
      .hero {{ grid-template-columns: 1fr; min-height: auto; }}
      .hero-cover {{ height: 55vw; max-height: 380px; }}
      .hero-cover::after {{ background: linear-gradient(to bottom, transparent 60%, var(--navy) 100%); }}
      .hero-text {{ padding: 2.5rem 1.5rem; }}
      #versions {{ padding: 3rem 1rem 3rem; }}
      .version-card {{ width: 100%; max-width: 340px; }}
    }}
  </style>
</head>
<body>

<!-- ── Hero ──────────────────────────────────────────────────────────── -->
<section class="hero">
  <div class="hero-cover">
    <img src="{cover_img}" alt="Capa do livro — girassol processado digitalmente">
  </div>
  <div class="hero-text">
    <p class="hero-eyebrow">UFABC · Material didático interativo</p>
    <h1 class="hero-title">
      Processamento Digital<br>de Imagens e<br>
      <em>Visão Computacional</em>
    </h1>
    <p class="hero-sub">
      Livro aberto, multi-linguagem e multi-idioma para cursos de
      graduação e pós-graduação em Computação e Engenharias.
    </p>
    <div class="hero-stats">
      <div class="stat">
        <span class="stat-num">{n_versions}</span>
        <span class="stat-label">versões</span>
      </div>
      <div class="stat">
        <span class="stat-num">{n_langs}</span>
        <span class="stat-label">linguagens</span>
      </div>
      <div class="stat">
        <span class="stat-num">{n_locales}</span>
        <span class="stat-label">idiomas</span>
      </div>
    </div>
    <p class="hero-updated">⏱ Atualizado em {updated}</p>
    <a class="hero-scroll" href="#versions">
      <span class="hero-scroll-arrow">↓</span>
      Ver todas as versões
    </a>
  </div>
</section>

<!-- ── Versions ──────────────────────────────────────────────────────── -->
<main id="versions">
  <div class="section-header">
    <h2 class="section-title">Versões disponíveis</h2>
    <div class="section-rule"></div>
  </div>
{cards_html}
</main>

<!-- ── Footer ────────────────────────────────────────────────────────── -->
<footer>
  <p>© {datetime.now().year} <a href="https://github.com/fzampirolli/pdi-vc">Francisco de Assis Zampirolli</a> — UFABC</p>
  <p style="margin-top:0.4rem;">
    Gerado automaticamente pelo pipeline PDI+VC ·
    <a href="https://github.com/fzampirolli/pdi-vc">github.com/fzampirolli/pdi-vc</a>
  </p>
</footer>

</body>
</html>
'''
        return html
    
    def build(self) -> Path:
        """Constrói a página index.html principal dentro de gen/book/."""
        self.book_dir.mkdir(parents=True, exist_ok=True)
        
        versions = self.scan_versions()
        
        if not versions:
            print('⚠️ Nenhuma versão encontrada em gen/book/')
            print('   Execute o pipeline primeiro: make build LANGS=py,cpp LOCALES=pt,en')
            return self.index_path
        
        html_content = self.generate_html(versions)
        self.index_path.write_text(html_content, encoding='utf-8')
        
        print(f'✅ Página principal gerada: {self.index_path}')
        print(f'   📊 {len(versions)} versões encontradas')
        print(f'\n🌐 Abrir no navegador: file://{self.index_path.absolute()}')
        
        return self.index_path


if __name__ == '__main__':
    builder = IndexBuilder()
    builder.build()