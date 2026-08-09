#!/usr/bin/env bash
# find_label_mismatches.sh
#
# Varre all/cap*/*.ipynb procurando células com:
#   #| label: fig-XX-sim-...
#   <div id="sim-...">
#
# Mostra APENAS os casos em que o label não corresponde ao padrão
# fig-<cap>-<id-da-div>, junto com a linha atual e a linha sugerida.
#
# Uso:
#   ./find_label_mismatches.sh                 # usa ./all/cap*/*.ipynb
#   ./find_label_mismatches.sh /caminho/all    # usa <caminho>/cap*/*.ipynb

set -euo pipefail

BASE_DIR="${1:-all}"

python3 - "$BASE_DIR" <<'PYEOF'
import json
import re
import sys
import glob
import os

base_dir = sys.argv[1]
pattern = os.path.join(base_dir, "cap*", "*.ipynb")
files = sorted(glob.glob(pattern))

if not files:
    print(f"⚠ Nenhum arquivo encontrado em: {pattern}", file=sys.stderr)
    sys.exit(1)

RE_LABEL = re.compile(r'^\s*#\|\s*label:\s*(fig-(\d+)-(sim-[a-z0-9-]+))\s*$', re.IGNORECASE | re.MULTILINE)
RE_DIV_ID = re.compile(r'<div\s+id=["\'](sim-[a-z0-9-]+)["\']', re.IGNORECASE)

total_mismatches = 0

for nb_path in files:
    try:
        with open(nb_path, "r", encoding="utf-8") as f:
            nb = json.load(f)
    except Exception as e:
        print(f"⚠ Erro ao ler {nb_path}: {e}", file=sys.stderr)
        continue

    for cell_idx, cell in enumerate(nb.get("cells", [])):
        if cell.get("cell_type") != "code":
            continue

        source = cell.get("source", [])
        src_text = "".join(source) if isinstance(source, list) else source

        label_match = RE_LABEL.search(src_text)
        if not label_match:
            continue

        full_label = label_match.group(1)   # fig-01-sim-map
        cap_num = label_match.group(2)       # 01
        label_sim_name = label_match.group(3)  # sim-map

        div_match = RE_DIV_ID.search(src_text)
        if not div_match:
            # tem label de simulador mas nao achou div id -- sinaliza tambem
            print(f"\n{nb_path}  [cell {cell_idx}]")
            print(f"  ⚠ label='{full_label}' mas nenhuma <div id=\"sim-...\"> encontrada na célula")
            continue

        div_id = div_match.group(1)          # sim-ep0103-map

        expected_label = f"fig-{cap_num}-{div_id}"

        if full_label != expected_label:
            total_mismatches += 1
            print(f"\n{nb_path}  [cell {cell_idx}]")
            print(f"  OLD: #| label: {full_label}")
            print(f"  NEW: #| label: {expected_label}")

print(f"\n{'─'*60}")
print(f"Total de divergências encontradas: {total_mismatches}")
PYEOF
