#!/usr/bin/env python3
"""
sim_tools.py — Extração de Simuladores em HTMLs Quarto agrupados por capítulo.

Extrai estritamente os simuladores reais do livro, gerando um índice centralizador (index.html)
na raiz para evitar erros 404 no GitHub Pages e ordenando os EPs antes dos conceituais.

Uso:
  python sim_tools.py extrair                               # Varre gen/book/*/cap*/*.html
  python sim_tools.py extrair --input gen/book/py.pt
  python sim_tools.py extrair --out-dir output/simuladores  # Pasta customizada
  python sim_tools.py extrair --dry-run                       # Apenas lista simuladores
"""

import argparse
import os
import re
import sys
import shutil
from pathlib import Path
from bs4 import BeautifulSoup, Tag

# Regra de busca estrita: ID da tag DEVE conter "-sim-" ou começar com "sim-"
RE_STRICT_SIM_ID = re.compile(r'(^sim-|-sim-|^sim\d{2})', re.IGNORECASE)

# Descarte explícito de elementos de interface do Quarto e de código
RE_CAPTION_ID = re.compile(r'-caption-[0-9a-f-]{36}', re.IGNORECASE)
RE_CELL_ID = re.compile(r'^cell-fig-', re.IGNORECASE)

# Lista negra rigorosa de fragmentos internos do DOM ou variáveis de script que vazaram
RE_SUB_ELEMENTS = re.compile(
    r'(?:'
    r'^sim-btn|^sim-frame|^sim-card|^sim-main|^sim-caption|'
    r'_stepctrl|_animctrl|_root|_debug|_bits|_canvas|_btn|_sl|_vl|_grid|_box|_panel|_pill|_v_|_cards|_tbody|_badge|_x1|_x2|_y1|_y2|_dx|_tau|_a|_b|_c4|_c8|_angVal|_hammVal|_pairsVal|'
    r'^sim-dil0$|^sim-ero0$|^sim-cdil$|^sim-avancado$|^sim-desc$|^sim-cdil_info$|^sim-edt_sste$'
    r')', 
    re.IGNORECASE
)

# Expressões regulares de apoio
RE_CAP_FILE = re.compile(r'cap(\d{2})', re.IGNORECASE)
RE_CAP_SIM = re.compile(r'(?:sim|fig)[-_]?(?:ep)?(\d{2})', re.IGNORECASE)

STOP_WORDS = {"sim", "fig", "ep", "cap", "cap01", "cap02", "cap03", "cap04", "cap05", "cap06", "cap07", "cap08", "cap09", "1d", "2d", "3d", "pixels", "imagem", "imagens"}

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="{lang}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{sim_title} | PDI+VC</title>
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

    body.sim-standalone {{
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
    .sim-frame-header {{
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

    .sim-frame-brand {{
      display: flex;
      flex-direction: column;
      max-width: 60%;
    }}

    .sim-frame-eyebrow {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.7rem;
      letter-spacing: 0.18em;
      text-transform: uppercase;
      color: var(--gold-lt);
    }}

    .sim-frame-title {{
      font-family: 'Playfair Display', Georgia, serif;
      font-size: 1.15rem;
      font-weight: 700;
      color: #fff;
      margin: 0;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}

    .sim-frame-nav {{
      display: flex;
      align-items: center;
      gap: 0.5rem;
      flex-wrap: wrap;
    }}

    .sim-btn {{
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

    .sim-btn-primary {{
      background: var(--gold);
      color: var(--navy);
      font-weight: 600;
    }}

    .sim-btn-primary:hover {{
      background: var(--gold-lt);
    }}

    .sim-btn-outline {{
      border: 1px solid #4a6a8a;
      color: #c8d8e8;
    }}

    .sim-btn-outline:hover {{
      border-color: var(--gold-lt);
      color: #fff;
      background: rgba(255,255,255,0.05);
    }}

    .sim-btn-nav {{
      background: rgba(255,255,255,0.08);
      border: 1px solid #3a5a7a;
      color: #fff;
    }}

    .sim-btn-nav:hover {{
      background: var(--navy-lt);
      border-color: var(--gold-lt);
    }}

    /* ── Container Principal do Simulador ────────────────────────────── */
    .sim-main-wrapper {{
      flex: 1;
      padding: 2.5rem 1.5rem;
      max-width: 120ch;
      width: 100%;
      margin: 0 auto;
      box-sizing: border-box;
    }}

    .sim-card-frame {{
      background: #fff;
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 2rem;
      box-shadow: var(--shadow);
    }}

    /* ── Legenda Posicionada Abaixo do Simulador ─────────────────────── */
    .sim-caption-below {{
      margin-top: 1.5rem;
      padding: 1rem 1.2rem;
      background-color: var(--cream);
      border-left: 4px solid var(--gold);
      border-radius: 0 6px 6px 0;
      font-size: 0.88rem;
      line-height: 1.6;
      color: var(--ink);
    }}

    .sim-caption-below strong {{
      color: var(--navy);
    }}

    /* ── Footer do Frame (Consolidado) ───────────────────────────────── */
    .sim-frame-footer {{
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

    .sim-frame-footer strong {{
      color: #fff;
    }}

    .sim-frame-footer a {{
      color: var(--gold-lt);
      text-decoration: none;
    }}

    .sim-frame-footer a:hover {{
      text-decoration: underline;
    }}

    @media (max-width: 820px) {{
      .sim-frame-brand {{
        max-width: 100%;
      }}
      .sim-frame-header {{
        padding: 1rem;
      }}
      .sim-main-wrapper {{
        padding: 1rem 0.5rem;
      }}
      .sim-card-frame {{
        padding: 1rem;
      }}
    }}
  </style>
</head>
<body class="sim-standalone">

<!-- CABEÇALHO COM ESTILO DO LIVRO E NAVEGAÇÃO -->
<header class="sim-frame-header">
  <div class="sim-frame-brand">
    <span class="sim-frame-eyebrow">PDI+VC · Simulador Interativo</span>
    <h1 class="sim-frame-title" title="{full_title}">{sim_title}</h1>
  </div>
  <nav class="sim-frame-nav">
    {prev_btn}
    {next_btn}
    <a href="../" class="sim-btn sim-btn-outline">📂 Índice geral</a>
    <a href="https://fzampirolli.github.io/pdi-vc/py.pt" target="_blank" class="sim-btn sim-btn-outline">📖 Ver livro</a>
    <a href="https://github.com/fzampirolli/pdi-vc" target="_blank" class="sim-btn sim-btn-primary">💻 GitHub</a>
  </nav>
</header>

<!-- CONTEÚDO DO SIMULADOR ENQUADRADO -->
<main class="sim-main-wrapper">
  <div class="sim-card-frame">
    {content}
    {caption_html}
  </div>
</main>

<!-- RODAPÉ COMPLETO E ÚNICO -->
<footer class="sim-frame-footer">
  <p>
    <strong><a href="https://github.com/fzampirolli/pdi-vc" target="_blank">PDI+VC — Processamento Digital de Imagens e Visão Computacional</a></strong><br>
    © 2026 <a href="https://sites.google.com/site/fzampirolli/" target="_blank">Francisco de Assis Zampirolli</a> — <a href="https://sites.google.com/site/fzampirolli/" target="_blank">Universidade Federal do ABC (UFABC)</a>.<br>
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
  <title>Simuladores Interativos | PDI+VC</title>
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
    .sim-list {{
      list-style: none;
      padding: 0;
      margin: 0;
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
      gap: 0.6rem;
    }}
    .sim-list li a {{
      display: block;
      background: var(--cream);
      padding: 0.6rem 1rem;
      border-radius: 6px;
      color: var(--navy);
      text-decoration: none;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.82rem;
      border: 1px solid var(--border);
      transition: all 0.2s ease;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .sim-list li a:hover {{
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
    <h1>PDI+VC · Simuladores Interativos</h1>
    <p>Processamento Digital de Imagens e Visão Computacional</p>
  </header>
  <main>
    {chapters_html}
  </main>
  <footer>
    <p>
      <strong><a href="https://github.com/fzampirolli/pdi-vc" target="_blank">PDI+VC — Processamento Digital de Imagens e Visão Computacional</a></strong><br>
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
    if head:
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

    return "\n  ".join(styles_parts), "\n".join(scripts_parts)

def detect_lang(soup: BeautifulSoup) -> str:
    html_tag = soup.find("html")
    return html_tag.get("lang", "pt") if html_tag else "pt"

def detect_chapter_folder(html_path: Path, sim_id: str) -> str:
    for part in reversed(html_path.parts):
        m = RE_CAP_FILE.search(part)
        if m:
            return f"cap{m.group(1)}"

    m_sim = RE_CAP_SIM.search(sim_id)
    if m_sim:
        return f"cap{m_sim.group(1)}"

    return "cap_geral"

def truncate_text(text: str, max_chars: int = 80) -> str:
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars - 3].rstrip() + "..."

def is_top_level_sim_container(tag: Tag) -> bool:
    if tag.name == "figure":
        return True
    classes = " ".join(tag.get("class", []))
    if "cell-output" in classes or "quarto-float" in classes:
        return True
    tag_id = tag.get("id", "")
    style = tag.get("style", "")
    has_interactive = bool(tag.find(["canvas", "button", "input", "svg", "select", "table"]))
    if has_interactive and ("background" in style or "border-radius" in style or tag_id.startswith("sim-ep") or tag_id.startswith("sim0")):
        return True
    return False

def normalize_sim_id(raw_id: str, cap_num: str = "") -> str:
    raw_id = re.sub(r'^sim-cap\d+-', 'sim-', raw_id, flags=re.I)
    m_ep_short = re.match(r'^sim(?:\d{2}_ep|[-_]?ep)(\d{2})([a-z]?)$', raw_id, re.I)
    if m_ep_short and cap_num:
        return f"sim-ep{cap_num}{m_ep_short.group(1)}{m_ep_short.group(2)}"

    m_ep_full = re.match(r'^sim[-_]?ep(\d{4}[a-z]?(?:-[a-z0-9-]+)?)$', raw_id, re.I)
    if m_ep_full:
        return f"sim-ep{m_ep_full.group(1).lower()}"

    m_fig_ep = re.match(r'^fig-(\d{2})-sim-ep(\d{2})([a-z]?)$', raw_id, re.I)
    if m_fig_ep:
        return f"sim-ep{m_fig_ep.group(1)}{m_fig_ep.group(2)}{m_fig_ep.group(3)}"

    m_fig = re.match(r'^fig-\d+-sim-(.+)$', raw_id, re.I)
    if m_fig:
        return f"sim-{m_fig.group(1).lower()}"

    m_sim = re.match(r'^sim\d{2}_(.+)$', raw_id, re.I)
    if m_sim:
        return f"sim-{m_sim.group(1).lower()}"

    return raw_id.lower()

def extract_key_tokens(sim_id: str) -> set[str]:
    clean = re.sub(r'^sim-(?:ep\d{4}[a-z]?-)?', '', sim_id, flags=re.I)
    tokens = set(re.findall(r'[a-z0-9]+', clean.lower()))
    return tokens - STOP_WORDS

def tokens_match_generically(gen_tokens: set[str], ep_tokens: set[str]) -> bool:
    if not gen_tokens or not ep_tokens:
        return False
    if gen_tokens.issubset(ep_tokens) or bool(gen_tokens & ep_tokens):
        return True
    for gt in gen_tokens:
        if len(gt) >= 3:
            for et in ep_tokens:
                if len(et) >= 3 and (gt.startswith(et) or et.startswith(gt)):
                    return True
    return False

def find_sim_blocks(soup: BeautifulSoup, html_file: Path) -> list[dict]:
    sims: list[dict] = []
    m_cap = RE_CAP_FILE.search(str(html_file))
    cap_num = m_cap.group(1) if m_cap else ""

    candidate_tags = soup.find_all(lambda tag: tag.get("id") and RE_STRICT_SIM_ID.search(tag.get("id")))
    page_scripts = soup.find_all("script")

    for sim_tag in candidate_tags:
        raw_id = sim_tag.get("id", "")

        if RE_CAPTION_ID.search(raw_id) or RE_CELL_ID.match(raw_id) or RE_SUB_ELEMENTS.search(raw_id):
            continue

        if sim_tag.name == "figure":
            inner_sim = sim_tag.find(lambda t: t != sim_tag and t.get("id") and RE_STRICT_SIM_ID.search(t.get("id")))
            if inner_sim and is_top_level_sim_container(inner_sim) and not RE_SUB_ELEMENTS.search(inner_sim.get("id", "")):
                continue

        if not is_top_level_sim_container(sim_tag):
            continue

        sim_id = normalize_sim_id(raw_id, cap_num=cap_num)
        element_copy = BeautifulSoup(str(sim_tag), "html.parser").find(True)
        if not element_copy:
            continue

        caption_tag = None
        aria_parent = sim_tag.find_parent(attrs={"aria-describedby": True})
        if aria_parent:
            cap_id = aria_parent.get("aria-describedby")
            caption_tag = soup.find(id=cap_id)

        if not caption_tag:
            figure_parent = sim_tag.find_parent("figure") or (sim_tag if sim_tag.name == "figure" else None)
            if figure_parent:
                caption_tag = figure_parent.find("figcaption")

        if not caption_tag:
            caption_tag = element_copy.find("figcaption") or (sim_tag.parent.find("figcaption") if sim_tag.parent else None)

        full_caption = ""
        if caption_tag:
            full_caption = caption_tag.get_text(" ", strip=True)
            if element_copy.find("figcaption"):
                element_copy.find("figcaption").decompose()

        if full_caption:
            clean_title = re.sub(r'^(?:Figura|Figure)\s*[\d.]+\s*:\s*', '', full_caption, flags=re.I)
            short_title = truncate_text(clean_title, max_chars=80)
        else:
            clean_title = f"Simulador {sim_id}"
            short_title = clean_title

        associated_scripts = []
        for script in page_scripts:
            if script.string and (raw_id in script.string or sim_id in script.string or "sim" in script.string):
                associated_scripts.append(str(script))

        sims.append({
            "sim_id": sim_id,
            "raw_id": raw_id,
            "sim_title": short_title,
            "full_title": clean_title,
            "full_caption": full_caption,
            "element": element_copy,
            "scripts": "\n".join(associated_scripts)
        })

    return sims

def build_sim_html(
    sim: dict, 
    styles: str, 
    head_scripts: str, 
    lang: str,
    prev_entry: dict | None = None,
    next_entry: dict | None = None
) -> str:
    content = str(sim["element"])
    all_scripts = head_scripts + "\n" + sim["scripts"]
    favicon_tag = '<link rel="icon" type="image/x-icon" href="../../../favicon.ico">'

    if sim["full_caption"]:
        caption_html = (
            f'<div class="sim-caption-below">'
            f'  <strong>Descrição:</strong> {sim["full_caption"]}'
            f'</div>'
        )
    else:
        caption_html = ''

    if prev_entry:
        p_id = prev_entry["sim_id"]
        prev_btn = f'<a href="{p_id}.html" class="sim-btn sim-btn-nav">← {p_id}</a>'
    else:
        prev_btn = ''

    if next_entry:
        n_id = next_entry["sim_id"]
        next_btn = f'<a href="{n_id}.html" class="sim-btn sim-btn-nav">{n_id} →</a>'
    else:
        next_btn = ''

    return HTML_TEMPLATE.format(
        lang=lang,
        sim_id=sim["sim_id"],
        sim_title=sim["sim_title"],
        full_title=sim["full_title"].replace('"', '&quot;'),
        favicon=favicon_tag,
        styles=styles,
        scripts=all_scripts,
        content=content,
        caption_html=caption_html,
        prev_btn=prev_btn,
        next_btn=next_btn,
    )

def collect_html_files(input_path: Path) -> list[tuple[Path, Path]]:
    pairs: list[tuple[Path, Path]] = []
    if input_path.is_file() and input_path.suffix == ".html":
        pairs.append((input_path, input_path.parent))
    elif input_path.is_dir():
        cap_files = sorted(list(input_path.rglob("cap*/*.html")) + list(input_path.rglob("cap*.html")))
        cap_files = [f for f in cap_files if "eps" not in f.parts and "simuladores" not in f.parts]
        unique_candidates = list(dict.fromkeys(cap_files))

        for html_file in unique_candidates:
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
        print(f"❌ Nenhum arquivo HTML encontrado em: {input_path}", file=sys.stderr)
        sys.exit(1)

    verbose = not args.quiet
    sample_versao = pairs[0][1].name if pairs[0][1].name != "book" else "default"
    book_root = pairs[0][1].parent if pairs[0][1].name != "book" else pairs[0][1]
    default_out_dir = book_root / "simuladores" / sample_versao

    if not args.dry_run and default_out_dir.exists():
        shutil.rmtree(default_out_dir)

    raw_sim_entries = []

    for html_file, versao_dir in pairs:
        raw = html_file.read_text(encoding="utf-8", errors="replace")
        soup = BeautifulSoup(raw, "html.parser")
        lang = detect_lang(soup)
        styles, head_scripts = extract_head_assets(soup)
        sims = find_sim_blocks(soup, html_file)

        if args.out_dir:
            out_dir = Path(args.out_dir)
        else:
            versao_name = versao_dir.name if versao_dir.name != "book" else "default"
            book_root = versao_dir.parent if versao_dir.name != "book" else versao_dir
            out_dir = book_root / "simuladores" / versao_name

        for sim in sims:
            cap_folder = detect_chapter_folder(html_file, sim["sim_id"])
            sim["cap_folder"] = cap_folder
            raw_sim_entries.append({
                "sim": sim,
                "sim_id": sim["sim_id"],
                "cap_folder": cap_folder,
                "out_dir": out_dir,
                "styles": styles,
                "head_scripts": head_scripts,
                "lang": lang,
                "html_file": html_file
            })

    ep_tokens_by_cap: dict[str, list[set[str]]] = {}
    ep_full_ids_by_cap: dict[str, set[str]] = {}

    for entry in raw_sim_entries:
        c = entry["cap_folder"]
        s_id = entry["sim_id"]
        if "ep" in s_id:
            ep_full_ids_by_cap.setdefault(c, set()).add(s_id)
            tokens = extract_key_tokens(s_id)
            if tokens:
                ep_tokens_by_cap.setdefault(c, []).append(tokens)

    final_sim_entries = []
    seen_keys = set()

    for entry in raw_sim_entries:
        c = entry["cap_folder"]
        s_id = entry["sim_id"]

        if re.match(r'^sim-ep-[a-z0-9-]+$', s_id, re.I):
            short_radical = s_id.replace("sim-ep-", "")
            if any(short_radical in full_ep for full_ep in ep_full_ids_by_cap.get(c, set())):
                continue

        # if not ("ep" in s_id):
        #     gen_tokens = extract_key_tokens(s_id)
        #     if gen_tokens:
        #         has_ep_match = any(
        #             tokens_match_generically(gen_tokens, ep_set)
        #             for ep_set in ep_tokens_by_cap.get(c, [])
        #         )
        #         if has_ep_match:
        #             continue

        key = (c, s_id)
        if key not in seen_keys:
            seen_keys.add(key)
            final_sim_entries.append(entry)

    cap_groups: dict[str, list[dict]] = {}
    for entry in final_sim_entries:
        c = entry["cap_folder"]
        cap_groups.setdefault(c, []).append(entry)

    total_sims: list[str] = []
    chapters_index_html = []

    for cap_folder in sorted(cap_groups.keys()):
        # 📌 ORDENAÇÃO: EPs primeiro (sim-ep...), depois os conceituais unificados
        group_entries = sorted(
            cap_groups[cap_folder], 
            key=lambda x: (0 if x["sim_id"].startswith("sim-ep") else 1, x["sim_id"].lower())
        )

        chapter_items_html = ""
        for i, entry in enumerate(group_entries):
            sim = entry["sim"]
            sim_id = entry["sim_id"]
            
            target_dir = entry["out_dir"] / cap_folder
            out_file = target_dir / f"{sim_id}.html"

            prev_entry = group_entries[i - 1] if i > 0 else None
            next_entry = group_entries[i + 1] if i < len(group_entries) - 1 else None

            if args.dry_run:
                if verbose:
                    print(f"  [✓ Found] {cap_folder}/{sim_id}  →  {out_file}")
            else:
                target_dir.mkdir(parents=True, exist_ok=True)
                html_content = build_sim_html(
                    sim, entry["styles"], entry["head_scripts"], entry["lang"],
                    prev_entry=prev_entry, next_entry=next_entry
                )
                out_file.write_text(html_content, encoding="utf-8")
                size_kb = out_file.stat().st_size / 1024
                if verbose:
                    print(f"  ✓ {cap_folder}/{sim_id}  →  {out_file}  ({size_kb:.1f} KB)")

            total_sims.append(f"{cap_folder}/{sim_id}")
            
            # 🌟 DESTAQUE PARA O NOME DO SIMULADOR EM NEGRITO PRIMEIRO, SEGUIDO DO ID
            chapter_items_html += f'<li><a href="{cap_folder}/{sim_id}.html" title="{sim["sim_title"]}"><strong>{sim["sim_title"]}</strong> <span style="opacity:0.6; font-size:0.9em;">({sim_id})</span></a></li>\n'

        cap_display_name = cap_folder.replace("cap", "Capítulo ").upper()
        chapters_index_html.append(f"""\
        <div class="chapter-card">
          <h2>{cap_display_name}</h2>
          <ul class="sim-list">
            {chapter_items_html}
          </ul>
        </div>
        """)

    # GERA O index.html NA RAIZ DA PASTA DE SIMULADORES PARA RESOLVER O ERRO 404 DO GITHUB PAGES
    if not args.dry_run and total_sims:
        index_file = default_out_dir / "index.html"
        default_out_dir.mkdir(parents=True, exist_ok=True)
        index_content = INDEX_TEMPLATE.format(chapters_html="\n".join(chapters_index_html))
        index_file.write_text(index_content, encoding="utf-8")
        if verbose:
            print(f"📁 Índice gerado: {index_file}")

    action = "encontrados" if args.dry_run else "gerados"
    print(f"\n{'─'*50}")
    print(f"✅ {len(total_sims)} Simuladores {action}: {', '.join(sorted(set(total_sims)))}")

    if not args.dry_run and total_sims and not args.out_dir:
        print(f"📁 Saída raiz: {default_out_dir}/index.html")

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="sim_tools.py",
        description="Extrai simuladores interativos de HTMLs Quarto organizados em subpastas de capítulos.",
    )
    sub = parser.add_subparsers(dest="cmd", metavar="SUBCOMANDO")
    sub.required = True

    p_ext = sub.add_parser(
        "extrair",
        help="Extrai simuladores (*-sim-*) agrupando por cap01, cap02, etc.",
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
        help="Pasta de saída (padrão: gen/book/simuladores/<versao>/)",
    )
    p_ext.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Apenas lista simuladores encontrados sem gravar arquivos",
    )
    p_ext.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suprime saída detalhada",
    )
    p_ext.set_defaults(func=cmd_extrair)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()