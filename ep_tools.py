#!/usr/bin/env python3
"""
ep_tools.py — Ferramentas unificadas para extração de EPs de HTML Quarto.

Subcomandos:
  extrair   Extrai cada EP de cap*.html e salva em arquivo individual com emolduração, navegação e índice raiz.
  limpar    Extrai o fragmento utilizável (compatível com Moodle/VPL) de cada EPxx_xx.html.

────────────────────────────────────────────────────────────────────────────
EXTRAIR — gera um HTML por EP a partir das páginas de capítulo do Quarto
────────────────────────────────────────────────────────────────────────────
  python ep_tools.py extrair                                  # processa gen/book/*/cap*/*.html
  python ep_tools.py extrair --input gen/book/py.pt           # versão específica
  python ep_tools.py extrair --input gen/book/py.pt/cap01/cap01.py.pt.html  # arquivo único
  python ep_tools.py extrair --out-dir output/eps             # pasta de saída customizada
  python ep_tools.py extrair --dry-run                        # só lista EPs encontrados

  Saída padrão: gen/book/eps/<versao>/EP01_02.html e index.html raiz

────────────────────────────────────────────────────────────────────────────
LIMPAR — extrai o fragmento Moodle/VPL de cada EPxx_xx.html já extraído
────────────────────────────────────────────────────────────────────────────
  python ep_tools.py limpar <pasta_entrada> <pasta_saida>
  python ep_tools.py limpar gen/book/eps/py.pt gen/book/eps/py.pt_moodle

  Remove células Jupyter (%%writefile, TestSuite…run()) e descarta tudo fora
  do <div class="ep-container">. Pronto para colar no Moodle.
"""

import argparse
import re
import sys
from pathlib import Path
from bs4 import BeautifulSoup, Tag


# ══════════════════════════════════════════════════════════════════════════════
# PARTE 1 — EXTRAIR: extrai EPs de cap*.html  (extrair_eps.py)
# ══════════════════════════════════════════════════════════════════════════════

# Identifica o título de um EP: h2, h3 ou h4 cujo texto contém "EPXX_YY"
RE_EP_HEADING = re.compile(r'\bEP(\d{2})_(\d{2})\b')

# Identifica a célula %%writefile EPXX_YY.py que fecha o bloco do EP
RE_WRITEFILE = re.compile(r'%%writefile\s+(EP\d{2}_\d{2}\.py)')

# Expressão para detectar o capítulo
RE_CAP_FILE = re.compile(r'cap(\d{2})', re.IGNORECASE)


HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="{lang}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{ep_id} — {title} | PDI+VC</title>
  {favicon} 
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=Source+Serif+4:ital,opsz,wght@0,8..60,300;0,8..60,400;1,8..60,300&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
  {styles}
  <style>
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

    body.ep-standalone {{
      font-family: 'Source Serif 4', Georgia, serif;
      background-color: var(--paper);
      color: var(--ink);
      margin: 0;
      padding: 0;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }}

    /* ── Header do Frame ───────────────────────────────────────────── */
    .ep-frame-header {{
      background: var(--navy);
      color: #fff;
      padding: 1.2rem 2rem;
      border-bottom: 3px solid var(--gold);
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 1rem;
      box-shadow: 0 2px 10px rgba(0,0,0,0.15);
    }}

    .ep-frame-brand {{
      display: flex;
      flex-direction: column;
    }}

    .ep-frame-eyebrow {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.7rem;
      letter-spacing: 0.18em;
      text-transform: uppercase;
      color: var(--gold-lt);
    }}

    .ep-frame-title {{
      font-family: 'Playfair Display', Georgia, serif;
      font-size: 1.25rem;
      font-weight: 700;
      color: #fff;
      margin: 0;
    }}

    .ep-frame-nav {{
      display: flex;
      align-items: center;
      gap: 0.5rem;
      flex-wrap: wrap;
    }}

    .ep-btn {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.78rem;
      padding: 0.4rem 0.8rem;
      border-radius: 6px;
      text-decoration: none;
      transition: all 0.2s ease;
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
    }}

    .ep-btn-primary {{
      background: var(--gold);
      color: var(--navy);
      font-weight: 600;
    }}

    .ep-btn-primary:hover {{
      background: var(--gold-lt);
    }}

    .ep-btn-outline {{
      border: 1px solid #4a6a8a;
      color: #c8d8e8;
    }}

    .ep-btn-outline:hover {{
      border-color: var(--gold-lt);
      color: #fff;
      background: rgba(255,255,255,0.05);
    }}

    .ep-btn-nav {{
      background: rgba(255,255,255,0.08);
      border: 1px solid #3a5a7a;
      color: #fff;
    }}

    .ep-btn-nav:hover {{
      background: var(--navy-lt);
      border-color: var(--gold-lt);
    }}

    /* ── Container Principal do EP ───────────────────────────────────── */
    .ep-main-wrapper {{
      flex: 1;
      padding: 2.5rem 1.5rem;
      max-width: 120ch;
      width: 100%;
      margin: 0 auto;
      box-sizing: border-box;
    }}

    .ep-card-frame {{
      background: #fff;
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 2rem;
      box-shadow: var(--shadow);
    }}

    /* ── Footer do Frame (Consolidado) ───────────────────────────────── */
    .ep-frame-footer {{
      background: var(--navy);
      color: #7898b0;
      text-align: center;
      padding: 2rem 1rem;
      font-size: 0.82rem;
      font-family: 'JetBrains Mono', monospace;
      margin-top: auto;
      border-top: 1px solid var(--navy-lt);
      line-height: 1.6;
    }}

    .ep-frame-footer strong {{
      color: #fff;
    }}

    .ep-frame-footer a {{
      color: var(--gold-lt);
      text-decoration: none;
    }}

    .ep-frame-footer a:hover {{
      text-decoration: underline;
    }}

    @media (max-width: 600px) {{
      .ep-frame-header {{
        padding: 1rem;
      }}
      .ep-main-wrapper {{
        padding: 1rem 0.5rem;
      }}
      .ep-card-frame {{
        padding: 1rem;
      }}
    }}
  </style>
</head>
<body class="ep-standalone">

<!-- CABEÇALHO COM ESTILO DO LIVRO E NAVEGAÇÃO -->
<header class="ep-frame-header">
  <div class="ep-frame-brand">
    <span class="ep-frame-eyebrow">PDI+VC · Exercício de Programação</span>
    <h1 class="ep-frame-title">{ep_id} — {title}</h1>
  </div>
  <nav class="ep-frame-nav">
    {prev_btn}
    {next_btn}
    <a href="./index.html" class="ep-btn ep-btn-outline">📂 Índice geral</a>
    <a href="https://fzampirolli.github.io/pdi-vc/" target="_blank" class="ep-btn ep-btn-outline">📖 Ver livro</a>
    <a href="https://github.com/fzampirolli/pdi-vc" target="_blank" class="ep-btn ep-btn-primary">💻 GitHub</a>
  </nav>
</header>

<!-- CONTEÚDO DO EP ENQUADRADO -->
<main class="ep-main-wrapper">
  <div class="ep-card-frame">
    <div class="ep-container">
      {content}
    </div>
  </div>
</main>

<!-- RODAPÉ COMPLETO E ÚNICO -->
<footer class="ep-frame-footer">
  <p>
    <strong><a href="https://fzampirolli.github.io/pdi-vc/" target="_blank">PDI+VC — Processamento Digital de Imagens e Visão Computacional</a></strong><br>
    © 2026 <a href="https://sites.google.com/site/fzampirolli/" target="_blank">Francisco de Assis Zampirolli</a> — <a href="https://ufabc.edu.br/" target="_blank">Universidade Federal do ABC (UFABC)</a>.<br>
    Material didático aberto sob licença <a href="https://creativecommons.org/licenses/by-sa/4.0" target="_blank">CC BY-SA 4.0</a> · 
    DOI: <a href="https://doi.org/10.5281/zenodo.20784606" target="_blank">10.5281/zenodo.20784606</a>
  </p>
</footer>

{scripts}
</body>
</html>
"""

INDEX_TEMPLATE = """\
<!DOCTYPE html>
<html lang="pt">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Exercícios de Programação (EPs) | PDI+VC</title>
  <link rel="icon" type="image/x-icon" href="../../favicon.ico">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=Source+Serif+4:ital,opsz,wght@0,8..60,300;0,8..60,400;1,8..60,300&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
  <style>
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
    body {{
      font-family: 'Source Serif 4', Georgia, serif;
      background-color: var(--paper);
      color: var(--ink);
      margin: 0;
      padding: 0;
      display: flex;
      flex-direction: column;
      min-height: 100vh;
    }}
    header {{
      background: var(--navy);
      color: #fff;
      padding: 2rem;
      border-bottom: 3px solid var(--gold);
      text-align: center;
    }}
    header h1 {{
      font-family: 'Playfair Display', Georgia, serif;
      font-size: 2rem;
      margin: 0 0 0.5rem 0;
    }}
    header p {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.85rem;
      color: var(--gold-lt);
      margin: 0;
    }}
    main {{
      max-width: 90ch;
      width: 100%;
      margin: 2.5rem auto;
      padding: 0 1rem;
      box-sizing: border-box;
      flex: 1;
    }}
    .chapter-card {{
      background: #fff;
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 1.5rem 2rem;
      margin-bottom: 1.5rem;
      box-shadow: var(--shadow);
    }}
    .chapter-card h2 {{
      font-family: 'Playfair Display', Georgia, serif;
      font-size: 1.3rem;
      color: var(--navy);
      margin-top: 0;
      border-bottom: 2px solid var(--cream);
      padding-bottom: 0.5rem;
    }}
    .ep-list {{
      list-style: none;
      padding: 0;
      margin: 0;
      display: flex;
      flex-direction: column;
      gap: 0.6rem;
    }}
    .ep-list li a {{
      display: block;
      background: var(--cream);
      padding: 0.6rem 1rem;
      border-radius: 6px;
      color: var(--navy);
      text-decoration: none;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.84rem;
      border: 1px solid var(--border);
      transition: all 0.2s ease;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .ep-list li a:hover {{
      background: var(--navy);
      color: #fff;
      border-color: var(--navy);
    }}
    footer {{
      background: var(--navy);
      color: #7898b0;
      text-align: center;
      padding: 2rem 1rem;
      font-size: 0.82rem;
      font-family: 'JetBrains Mono', monospace;
      border-top: 1px solid var(--navy-lt);
    }}
    footer a {{
      color: var(--gold-lt);
      text-decoration: none;
    }}
    footer a:hover {{
      text-decoration: underline;
    }}
  </style>
</head>
<body>
  <header>
    <h1>PDI+VC · Exercícios de Programação (EPs)</h1>
    <p>Processamento Digital de Imagens e Visão Computacional</p>
  </header>
  <main>
    {chapters_html}
  </main>
  <footer>
    <p>
      <strong><a href="https://fzampirolli.github.io/pdi-vc/" target="_blank">PDI+VC — Processamento Digital de Imagens e Visão Computacional</a></strong><br>
      © 2026 <a href="https://sites.google.com/site/fzampirolli/" target="_blank">Francisco de Assis Zampirolli</a> — <a href="https://sites.google.com/site/fzampirolli/" target="_blank">Universidade Federal do ABC (UFABC)</a>.<br>
      <a href="https://fzampirolli.github.io/pdi-vc/py.pt" target="_blank">📖 Voltar para o Livro</a>
    </p>
  </footer>
</body>
</html>
"""


def extract_head_assets(soup: BeautifulSoup) -> tuple[str, str]:
    styles_parts: list[str] = []
    scripts_parts: list[str] = []

    head = soup.find("head")
    if not head:
        return "", ""

    for tag in head.find_all(["link", "style"]):
        if tag.name == "link" and tag.get("rel") == ["stylesheet"]:
            styles_parts.append(str(tag))
        elif tag.name == "style":
            styles_parts.append(str(tag))

    for tag in head.find_all("script"):
        src = tag.get("src", "")
        if src and any(k in src for k in ("mathjax", "highlight", "quarto")):
            scripts_parts.append(str(tag))
        elif not src and tag.string and "MathJax" in tag.string:
            scripts_parts.append(str(tag))

    body = soup.find("body")
    if body:
        for tag in body.find_all("script"):
            src = tag.get("src", "")
            if src or (tag.string and len(tag.string.strip()) > 0):
                scripts_parts.append(str(tag))

    return "\n  ".join(styles_parts), "\n".join(scripts_parts)


def detect_lang(soup: BeautifulSoup) -> str:
    html_tag = soup.find("html")
    return html_tag.get("lang", "pt") if html_tag else "pt"


def detect_chapter_folder(html_path: Path, ep_id: str) -> str:
    for part in reversed(html_path.parts):
        m = RE_CAP_FILE.search(part)
        if m:
            return f"cap{m.group(1)}"

    # Fallback extraindo do próprio EP01_02 -> cap01
    m_ep = re.match(r'^EP(\d{2})_', ep_id)
    if m_ep:
        return f"cap{m_ep.group(1)}"

    return "cap_geral"


def find_ep_blocks(soup: BeautifulSoup) -> list[dict]:
    heading_tags = {"h2", "h3", "h4"}
    eps: list[dict] = []

    main = (
        soup.find("main")
        or soup.find("article")
        or soup.find("div", class_=re.compile(r"content|chapter|book"))
        or soup.find("body")
    )
    if not main:
        return []

    ep_headings: list[tuple] = []
    for tag in main.find_all(heading_tags):
        text = tag.get_text(" ", strip=True)
        m = RE_EP_HEADING.search(text)
        if m:
            ep_headings.append((tag, m.group(0)))

    for heading_tag, ep_id in ep_headings:
        title_text = heading_tag.get_text(" ", strip=True)
        title_text = re.sub(r'^\s*[\d.]+\s+', '', title_text)
        title_text = re.sub(rf'^\s*{re.escape(ep_id)}\s*[:—\-–]?\s*', '', title_text, flags=re.IGNORECASE)

        heading_level = int(heading_tag.name[1])

        block_elements: list[Tag] = [heading_tag]
        found_writefile = False

        sibling = heading_tag.find_next_sibling()
        while sibling:
            if isinstance(sibling, Tag):
                tag_name = sibling.name

                if tag_name in heading_tags:
                    sib_level = int(tag_name[1])
                    if sib_level <= heading_level:
                        break
                    sib_text = sibling.get_text(" ", strip=True)
                    if RE_EP_HEADING.search(sib_text):
                        break

                sib_text_full = sibling.get_text()
                wf_match = RE_WRITEFILE.search(sib_text_full)
                if wf_match and wf_match.group(1).startswith(ep_id):
                    block_elements.append(sibling)
                    found_writefile = True
                    break

                block_elements.append(sibling)

            sibling = sibling.find_next_sibling()

        eps.append({
            "ep_id": ep_id,
            "title": title_text.strip(),
            "elements": block_elements,
            "has_writefile": found_writefile,
        })

    return eps


def elements_to_html(elements: list[Tag]) -> str:
    return "\n".join(str(el) for el in elements)


def build_ep_html(ep: dict, styles: str, scripts: str, lang: str, prev_id: str | None = None, next_id: str | None = None) -> str:
    content = elements_to_html(ep["elements"])
    favicon_tag = '<link rel="icon" type="image/x-icon" href="../../favicon.ico">'
    
    prev_btn = f'<a href="{prev_id}.html" class="ep-btn ep-btn-nav">← {prev_id}</a>' if prev_id else ''
    next_btn = f'<a href="{next_id}.html" class="ep-btn ep-btn-nav">{next_id} →</a>' if next_id else ''

    return HTML_TEMPLATE.format(
        lang=lang,
        ep_id=ep["ep_id"],
        title=ep["title"],
        favicon=favicon_tag,
        styles=styles,
        scripts=scripts,
        content=content,
        prev_btn=prev_btn,
        next_btn=next_btn,
    )


def collect_html_files(input_path: Path) -> list[tuple[Path, Path]]:
    pairs: list[tuple[Path, Path]] = []

    if input_path.is_file() and input_path.suffix == ".html":
        parts = input_path.parts
        try:
            book_idx = list(parts).index("book")
            versao_dir = Path(*parts[: book_idx + 2])
        except ValueError:
            versao_dir = input_path.parent
        pairs.append((input_path, versao_dir))

    elif input_path.is_dir():
        for html_file in sorted(input_path.rglob("cap*/*.html")):
            parts = html_file.parts
            try:
                book_idx = list(parts).index("book")
                versao_dir = Path(*parts[: book_idx + 2])
            except ValueError:
                versao_dir = input_path
            pairs.append((html_file, versao_dir))

    return pairs


def cmd_extrair(args: argparse.Namespace) -> None:
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ Caminho não encontrado: {input_path}", file=sys.stderr)
        sys.exit(1)

    pairs = collect_html_files(input_path)
    if not pairs:
        print(f"❌ Nenhum arquivo HTML de capítulo encontrado em: {input_path}", file=sys.stderr)
        sys.exit(1)

    verbose = not args.quiet
    
    all_ep_entries = []
    for html_file, versao_dir in pairs:
        raw = html_file.read_text(encoding="utf-8", errors="replace")
        soup = BeautifulSoup(raw, "html.parser")
        lang = detect_lang(soup)
        styles, scripts = extract_head_assets(soup)
        eps = find_ep_blocks(soup)

        if args.out_dir:
            out_dir = Path(args.out_dir)
        else:
            versao_name = versao_dir.name
            book_root = versao_dir.parent
            out_dir = book_root / "eps" / versao_name

        for ep in eps:
            cap_folder = detect_chapter_folder(html_file, ep["ep_id"])
            all_ep_entries.append({
                "ep": ep,
                "cap_folder": cap_folder,
                "out_dir": out_dir,
                "styles": styles,
                "scripts": scripts,
                "lang": lang,
                "html_file": html_file
            })

    # Ordena globalmente por ep_id para garantir a travessia contínua de todo o livro
    all_ep_entries = sorted(all_ep_entries, key=lambda x: x["ep"]["ep_id"])

    # Agrupa por capítulo para montar o index.html formatado
    cap_groups: dict[str, list[dict]] = {}
    for entry in all_ep_entries:
        c = entry["cap_folder"]
        cap_groups.setdefault(c, []).append(entry)

    total_eps: list[str] = []
    chapters_index_html = []

    for cap_folder in sorted(cap_groups.keys()):
        group_entries = sorted(cap_groups[cap_folder], key=lambda x: x["ep"]["ep_id"])
        
        chapter_items_html = ""
        for i, entry in enumerate(group_entries):
            ep = entry["ep"]
            ep_id = ep["ep_id"]
            out_dir = entry["out_dir"]
            out_file = out_dir / f"{ep_id}.html"

            # Global prev/next para a navegação interna dos EPs
            global_idx = all_ep_entries.index(entry)
            prev_id = all_ep_entries[global_idx - 1]["ep"]["ep_id"] if global_idx > 0 else None
            next_id = all_ep_entries[global_idx + 1]["ep"]["ep_id"] if global_idx < len(all_ep_entries) - 1 else None

            if args.dry_run:
                if verbose:
                    print(f"  [Found] {ep_id}  →  {out_file}")
            else:
                out_dir.mkdir(parents=True, exist_ok=True)
                html_content = build_ep_html(
                    ep, entry["styles"], entry["scripts"], entry["lang"], 
                    prev_id=prev_id, next_id=next_id
                )
                out_file.write_text(html_content, encoding="utf-8")
                size_kb = out_file.stat().st_size / 1024
                if verbose:
                    wf = "✓" if ep["has_writefile"] else "⚠"
                    print(f"  {wf} {ep_id}  →  {out_file}  ({size_kb:.0f} KB)")

            total_eps.append(ep_id)
            chapter_items_html += f'<li><a href="{ep_id}.html" title="{ep["title"]}"><code>{ep_id}</code> — {ep["title"]}</a></li>\n'

        cap_display_name = cap_folder.replace("cap", "Capítulo ").upper()
        chapters_index_html.append(f"""\
        <div class="chapter-card">
          <h2>{cap_display_name}</h2>
          <ul class="ep-list">
            {chapter_items_html}
          </ul>
        </div>
        """)

    # GERA O index.html NA RAIZ DA PASTA DE EPs PARA EVITAR O ERRO 404 DO GITHUB PAGES
    if not args.dry_run and total_eps:
        sample_versao = pairs[0][1].name if pairs[0][1].name != "book" else "default"
        book_root = pairs[0][1].parent if pairs[0][1].name != "book" else pairs[0][1]
        default_out_dir = book_root / "eps" / sample_versao if not args.out_dir else Path(args.out_dir)
        
        index_file = default_out_dir / "index.html"
        default_out_dir.mkdir(parents=True, exist_ok=True)
        index_content = INDEX_TEMPLATE.format(chapters_html="\n".join(chapters_index_html))
        index_file.write_text(index_content, encoding="utf-8")
        if verbose:
            print(f"📁 Índice geral gerado: {index_file}")

    action = "encontrados" if args.dry_run else "gerados"
    print(f"\n{'─'*50}")
    print(f"✅ {len(total_eps)} EPs {action}: {', '.join(sorted(set(total_eps)))}")

    if not args.dry_run and total_eps and not args.out_dir:
        sample_versao = pairs[0][1].name
        book_root = pairs[0][1].parent
        print(f"📁 Saída raiz: {book_root / 'eps' / sample_versao}/index.html")


# ══════════════════════════════════════════════════════════════════════════════
# PARTE 2 — LIMPAR: extrai e sanitiza fragmento Moodle de EPxx_xx.html (MANTIDO INTACTO)
# ══════════════════════════════════════════════════════════════════════════════

CELL_RE = re.compile(
    r'<div[^>]+class="cell"[^>]*id="[0-9a-f]{6,}"[\s\S]*?'
    r'(?=<div[^>]+class="cell"|</section>|</div>\s*</section>)',
    re.IGNORECASE,
)

QUARTO_FLOAT_OUTER_RE = re.compile(
    r'<div[^>]+class="[^"]*cell-output[^"]*"[^>]*>\s*'
    r'<figure[^>]*>([\s\S]*?)</figure>\s*</div>',
    re.IGNORECASE,
)

FIGCAPTION_RE = re.compile(r'<figcaption[^>]*>[\s\S]*?</figcaption>', re.IGNORECASE)

ARIA_DIV_RE = re.compile(
    r'<div\s+aria-describedby="[^"]*">([\s\S]*?)</div>',
    re.IGNORECASE,
)

def _cases_to_inline(m: re.Match) -> str:
    body = m.group(1)
    cases = re.split(r'\\\\', body)
    parts = []
    for case in cases:
        case = re.sub(r'&amp;\s*', '', case)
        case = re.sub(r'&\s*', '', case)
        case = case.strip()
        if case:
            parts.append(case)
    return '; '.join(parts)

def latex_body_to_html(body: str) -> str:
    s = body.strip()
    s = s.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&nbsp;', ' ')
    s = re.sub(r'\\begin\{cases\}([\s\S]*?)\\end\{cases\}', _cases_to_inline, s)
    cmd_map = [
        (r'\\times',  '&times;'),
        (r'\\geq',    '&ge;'),
        (r'\\leq',    '&le;'),
        (r'\\neq',    '&ne;'),
        (r'\\cdot',   '&middot;'),
        (r'\\ldots',  '&hellip;'),
        (r'\\in',     '&isin;'),
        (r'\\alpha',  '&alpha;'),
        (r'\\beta',   '&beta;'),
        (r'\\gamma',  '&gamma;'),
        (r'\\sigma',  '&sigma;'),
        (r'\\mu',     '&mu;'),
        (r'\\pm',     '&plusmn;'),
        (r'\\infty',  '&infin;'),
        (r'\\sum',    '&sum;'),
        (r'\\sqrt\{([^}]*)\}', r'&radic;(\1)'),
        (r'\\frac\{([^}]*)\}\{([^}]*)\}', r'(\1)/(\2)'),
        (r'\\text\{([^}]*)\}', r'\1'),
        (r'\\mathbf\{([^}]*)\}', r'<strong>\1</strong>'),
        (r'\\mathrm\{([^}]*)\}', r'\1'),
        (r'\\_', '_'),
        (r'\\{', '{'),
        (r'\\}', '}'),
    ]
    for pat, repl in cmd_map:
        s = re.sub(pat, repl, s)
    s = re.sub(r'(?<![a-zA-Z&;{])([a-zA-Z])(?![a-zA-Z;={])', r'<em>\1</em>', s)
    s = s.replace('{', '').replace('}', '')
    s = re.sub(r'  +', ' ', s).strip()
    return s

def convert_math_spans(html: str) -> str:
    def repl_inline(m: re.Match) -> str:
        inner = re.sub(r'^\\\(|\\\)$', '', m.group(1)).strip()
        return latex_body_to_html(inner)

    def repl_display(m: re.Match) -> str:
        inner = m.group(1)
        inner = re.sub(r'^\s*\\\[\s*', '', inner)
        inner = re.sub(r'\s*\\\]\s*$', '', inner).strip()
        return latex_body_to_html(inner)

    html = re.sub(r'<span class="math inline">([\s\S]*?)</span>', repl_inline, html)
    html = re.sub(r'<span class="math display">([\s\S]*?)</span>', repl_display, html)
    return html

_EMOJI_BOX: dict[str, dict[str, str]] = {
    '🧠': {
        'div': 'background-color:#eafaf1;border-left:5px solid #7dcea0;padding:15px;border-radius:8px;margin-bottom:20px;',
        'h':   'margin-top:0;color:#1e8449;',
    },
    '📋': {
        'div': 'background-color:#f4f6fb;border-left:5px solid #a3b1cc;padding:15px;border-radius:8px;margin-bottom:20px;',
        'h':   'margin-top:0;color:#4a5a78;',
    },
    '📌': {
        'div': 'background-color:#fef9e7;border-left:5px solid #f7dc6f;padding:15px;border-radius:8px;margin-bottom:25px;',
        'h':   'margin-top:0;color:#9a7d0a;',
    },
    '📦': {
        'div': 'background-color:#f5eef8;border-left:5px solid #c39bd3;padding:15px;border-radius:8px;margin-bottom:20px;',
        'h':   'margin-top:0;color:#7d3c98;',
    },
}

_TABLE_STYLE    = 'width:100%;border-collapse:collapse;background-color:#fff;text-align:left;margin-bottom:20px;'
_TH_STYLE       = 'padding:10px;border:1px solid #ddd;'
_TD_CODE_STYLE  = 'padding:10px;border:1px solid #ddd;font-family:monospace;vertical-align:top;'
_TD_TEXT_STYLE  = 'padding:10px;border:1px solid #ddd;vertical-align:top;'
_OUTER_STYLE    = ('font-family:sans-serif;line-height:1.6;color:#333;max-width:1200px;'
                   'margin:auto;border:1px solid #ddd;padding:20px;border-radius:8px;background:white;')
_H2_STYLE       = 'color:#0056b3;border-bottom:2px solid #0056b3;padding-bottom:10px;'

def _style_table(table: Tag, is_examples: bool = False) -> None:
    table['style'] = _TABLE_STYLE
    for tr in table.find_all('tr'):
        tr.attrs.pop('class', None)
        if tr.parent and tr.parent.name == 'thead':
            tr['style'] = 'background-color:#f1f1f1;'
            for th in tr.find_all('th'):
                th['style'] = _TH_STYLE
        else:
            tds = tr.find_all('td')
            for i, td in enumerate(tds):
                if is_examples and i == len(tds) - 1:
                    td['style'] = _TD_TEXT_STYLE
                else:
                    td['style'] = _TD_CODE_STYLE

def _strip_section_number(text: str) -> str:
    return re.sub(r'^\s*[\d.]+\s+', '', text)

def inject_moodle_styles(fragment_html: str) -> str:
    soup = BeautifulSoup(fragment_html, 'html.parser')
    container = soup.find('div', class_='ep-container')
    if not container:
        return fragment_html

    title_tag = container.find(['h2', 'h3', 'h4'])
    if title_tag:
        for span in title_tag.find_all('span', class_='header-section-number'):
            span.decompose()
        ep_title = _strip_section_number(title_tag.get_text(' ', strip=True))
        new_h2 = soup.new_tag('h2')
        new_h2['style'] = _H2_STYLE
        new_h2.string = ep_title
        title_tag.replace_with(new_h2)

    for child in list(container.children):
        if not isinstance(child, Tag):
            continue
        if child.name in ('h2', 'p'):
            continue

        heading = child.find(['h2', 'h3', 'h4'])
        if not heading:
            child.name = 'div'
            for attr in ['class', 'data-number', 'id']:
                child.attrs.pop(attr, None)
            continue

        for span in heading.find_all('span', class_='header-section-number'):
            span.decompose()
        h_text = _strip_section_number(heading.get_text(' ', strip=True))

        emoji = next((e for e in _EMOJI_BOX if e in h_text), None)

        child.name = 'div'
        for attr in ['class', 'data-number', 'id']:
            child.attrs.pop(attr, None)

        sim_divs = child.find_all('div', id=re.compile(r'^sim-'))
        extracted_sims: list[Tag] = []
        for sim_div in sim_divs:
            sim_div.extract()
            extracted_sims.append(sim_div)

        if emoji:
            box = _EMOJI_BOX[emoji]
            child['style'] = box['div']

            heading.name = 'h4'
            heading['style'] = box['h']
            for attr in ['class', 'data-anchor-id', 'data-number']:
                heading.attrs.pop(attr, None)
            heading.string = h_text

            is_ex = bool(re.search(r'exemplo|example', h_text, re.IGNORECASE))
            for table in child.find_all('table'):
                table.attrs.pop('class', None)
                for colgroup in table.find_all('colgroup'):
                    colgroup.decompose()
                _style_table(table, is_examples=is_ex)
        else:
            heading.name = 'h4'
            for attr in ['class', 'data-anchor-id', 'data-number']:
                heading.attrs.pop(attr, None)

        anchor = child
        for sim_div in extracted_sims:
            anchor.insert_after(sim_div)
            anchor = sim_div

    for a in container.find_all('a', class_='quarto-xref'):
        a.replace_with(a.get_text())

    container['style'] = _OUTER_STYLE
    del container['class']

    return str(soup)

def rewrite_sim_script(script: str) -> str:
    sim_id_m = re.search(r'\[id=["\']([^"\']+)["\']\]', script)
    if not sim_id_m:
        return script
    sim_id = sim_id_m.group(1)

    root_m = re.search(r'function init\((\w+)\)', script)
    if not root_m:
        return script
    root_var = root_m.group(1)

    init_start = script.find(f'function init({root_var}){{')
    if init_start == -1:
        init_start = script.find(f'function init({root_var}) {{')
    if init_start == -1:
        return script

    brace_open = script.find('{', init_start)
    depth, pos = 0, brace_open
    while pos < len(script):
        if script[pos] == '{':
            depth += 1
        elif script[pos] == '}':
            depth -= 1
            if depth == 0:
                init_body = script[brace_open + 1: pos]
                break
        pos += 1
    else:
        return script

    init_body = re.sub(rf'\s*if\s*\(!{root_var}\)\s*return;\s*\n?', '\n', init_body)
    init_body = re.sub(
        rf'\s*if\s*\({root_var}\.dataset\.\w+\s*===\s*[\'"][^\'"]*[\'"]\)\s*return;\s*\n?',
        '\n', init_body,
    )
    init_body = re.sub(rf'\s*{root_var}\.dataset\.\w+\s*=\s*[\'"][^\'"]*[\'"];\s*\n?', '\n', init_body)
    init_body = re.sub(r'\s*if\s*\(![^)]{5,}\)\s*return;\s*\n?', '\n', init_body)

    init_body = re.sub(
        rf"{root_var}\.querySelector\(['\"]#([^'\"]+)['\"]\)",
        r"document.getElementById('\1')",
        init_body,
    )

    iife_name = 'init' + re.sub(r'[^a-zA-Z0-9]', '_', sim_id).title().replace('_', '')

    new_script = (
        f'(function {iife_name}() {{\n'
        f'  var container = document.getElementById(\'{sim_id}\');\n'
        f'  if (!container) {{ setTimeout({iife_name}, 100); return; }}\n'
        f'{init_body}\n'
        f'}})();'
    )
    return new_script

def sanitize_scripts(html: str) -> str:
    def repl(m: re.Match) -> str:
        content = m.group(1)
        if 'querySelectorAll' in content and 'tryInit' in content:
            content = rewrite_sim_script(content)
        return f'<script>\n{content}\n</script>'

    return re.sub(r'<script>([\s\S]*?)</script>', repl, html, flags=re.IGNORECASE)

def find_container_span(html: str) -> tuple[int, int] | None:
    # Aceita class="ep-container", class="ep-card-frame ep-container", etc.
    start_match = re.search(r'<div[^>]*class="[^"]*\bep-container\b[^"]*"[^>]*>', html)
    if not start_match:
        return None

    depth = 0
    pos = start_match.start()
    tag_re = re.compile(r'<div\b[^>]*>|</div>', re.IGNORECASE)

    while True:
        m = tag_re.search(html, pos)
        if not m:
            return None
        token = m.group(0)
        depth += -1 if token.lower().startswith('</div') else 1
        pos = m.end()
        if depth == 0:
            return start_match.start(), pos

    return None

def _unwrap_quarto_float(html: str) -> str:
    def unwrap(m: re.Match) -> str:
        inner = FIGCAPTION_RE.sub('', m.group(1))
        inner = re.sub(r'<div\s+aria-describedby="[^"]*">([\s\S]*?)</div>', r'\1', inner)
        return inner.strip()
    return QUARTO_FLOAT_OUTER_RE.sub(unwrap, html)

def _fix_sim_header(html: str) -> str:
    soup = BeautifulSoup(html, 'html.parser')

    for sim in soup.find_all('div', id=re.compile(r'^sim-')):
        title_div = sim.find(
            'div',
            style=re.compile(r'display\s*:\s*flex.*justify-content\s*:\s*space-between', re.S),
        )
        if not title_div:
            continue

        content_div = title_div.find(
            'div',
            style=re.compile(r'padding\s*:\s*20px'),
            recursive=False,
        )
        if not content_div:
            continue

        content_div.extract()
        title_div.insert_after(content_div)

    return str(soup)

def moodle_sanitize(fragment: str) -> str:
    fragment = CELL_RE.sub('', fragment)
    fragment = _unwrap_quarto_float(fragment)
    fragment = convert_math_spans(fragment)
    fragment = re.sub(r'\s*accent-color\s*:\s*[^;"\s]+\s*;?', '', fragment)
    fragment = inject_moodle_styles(fragment)
    fragment = _fix_sim_header(fragment)
    fragment = sanitize_scripts(fragment)
    return fragment

def _make_link_banner(ep_name: str, base_url: str) -> str:
    url = base_url.rstrip('/') + '/' + ep_name + '.html'
    lines = [
        '<div style="font-family:sans-serif;background:#e8f4fd;border-left:4px solid #2980b9;'
        'padding:10px 15px;margin-bottom:16px;border-radius:4px;font-size:13px;color:#1a5276;">',
        '📐 <strong>Versão com fórmulas matemáticas:</strong> '
        '<a href="' + url + '" target="_blank" style="color:#2980b9;">' + url + '</a>',
        '<br><span style="font-size:11px;color:#555;">'
        '(Fórmulas renderizadas pelo MathJax — abrir em nova aba)</span>',
        '</div>',
    ]
    return '\n'.join(lines)

def process_ep_file(path: Path, outdir: Path, base_url: str = '') -> bool:
    html = path.read_text(encoding='utf-8', errors='replace')
    span = find_container_span(html)
    if not span:
        print(f"[AVISO] '{path.name}': <div class=\"ep-container\"> não encontrado — pulando.")
        return False

    start, end = span
    fragment = moodle_sanitize(html[start:end])

    if base_url:
        ep_name = path.stem
        banner = _make_link_banner(ep_name, base_url)
        insert_at = fragment.find('>') + 1
        fragment = fragment[:insert_at] + '\n' + banner + fragment[insert_at:]

    warnings = []
    if 'accent-color' in fragment:
        warnings.append('accent-color')
    if 'querySelector' in fragment:
        warnings.append('querySelector')
    if 'dataset.' in fragment:
        warnings.append('dataset.')
    if 'class="anchored"' in fragment:
        warnings.append('class=anchored')
    if 'class="math' in fragment:
        warnings.append('class=math')

    outpath = outdir / path.name
    outpath.write_text(fragment, encoding='utf-8')

    warn_str = '  ⚠ ' + ', '.join(warnings) if warnings else ''
    print(f"[OK] {path.name}: {len(html)} → {len(fragment)} bytes{warn_str}")
    return True

def cmd_limpar(args: argparse.Namespace) -> None:
    indir = Path(args.entrada)
    outdir = Path(args.saida)

    if not indir.is_dir():
        print(f"❌ Pasta de entrada não encontrada: {indir}", file=sys.stderr)
        sys.exit(1)

    outdir.mkdir(parents=True, exist_ok=True)
    base_url = getattr(args, 'base_url', '') or ''
    print(f"Entrada  : {indir}")
    print(f"Saída    : {outdir}")
    if base_url:
        print(f"Base URL : {base_url}")
    print()

    ok, fail = 0, 0
    for f in sorted(indir.glob("EP*.html")):
        if process_ep_file(f, outdir, base_url=base_url):
            ok += 1
        else:
            fail += 1

    print(f"\n{'─'*50}")
    print(f"✅ Concluído: {ok} sanitizados, {fail} com problema.")
    if ok:
        print(f"📁 Fragmentos prontos para Moodle em: {outdir}/")


# ══════════════════════════════════════════════════════════════════════════════
# CLI principal
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="ep_tools.py",
        description="Ferramentas unificadas para extração de EPs de HTML Quarto.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="cmd", metavar="SUBCOMANDO")
    sub.required = True

    p_ext = sub.add_parser(
        "extrair",
        help="Extrai cada EP de cap*.html e salva em arquivo individual com botões de navegação contínua.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_ext.add_argument(
        "--input", "-i",
        default="gen/book",
        metavar="CAMINHO",
        help="Arquivo HTML ou diretório raiz (padrão: gen/book)",
    )
    p_ext.add_argument(
        "--out-dir", "-o",
        default=None,
        metavar="PASTA",
        help="Pasta de saída (padrão: gen/book/eps/<versao>/)",
    )
    p_ext.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Apenas lista EPs encontrados, não grava arquivos",
    )
    p_ext.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suprime saída detalhada",
    )
    p_ext.set_defaults(func=cmd_extrair)

    p_lim = sub.add_parser(
        "limpar",
        help="Extrai fragmento Moodle/VPL de cada EPxx_xx.html já extraído.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_lim.add_argument(
        "entrada",
        metavar="PASTA_ENTRADA",
        help="Pasta com os EPxx_xx.html extraídos (ex: gen/book/eps/py.pt)",
    )
    p_lim.add_argument(
        "saida",
        metavar="PASTA_SAIDA",
        nargs="?",
        default=None,
        help="Pasta de saída (padrão: <PASTA_ENTRADA>_moodle)",
    )
    p_lim.add_argument(
        "--base-url", "-u",
        default="",
        metavar="URL",
        dest="base_url",
        help=(
            "URL base da versão completa dos EPs (com MathJax). "
            "Ex: https://fzampirolli.github.io/pdi-vc/eps/py.pt "
            "Quando fornecida, injeta um banner com link no topo de cada EP."
        ),
    )
    p_lim.set_defaults(func=cmd_limpar)

    args = parser.parse_args()

    if args.cmd == "limpar" and args.saida is None:
        args.saida = str(Path(args.entrada).with_name(Path(args.entrada).name + "_moodle"))

    args.func(args)


if __name__ == "__main__":
    main()