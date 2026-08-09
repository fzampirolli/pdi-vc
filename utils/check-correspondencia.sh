#!/usr/bin/env bash
#
# Verifica a correspondência entre:
#   gen/book/simuladores/py.pt/capNN/<base>.html
#   all/capNN/imagens/fig-NN-<base>.png
#
# Uso: rode a partir da raiz do projeto (pdi-vc)
#   ./check-correspondencia.sh

set -uo pipefail

HTML_ROOT="gen/book/simuladores/py.pt"
PNG_ROOT="all"

missing_png=0
missing_html=0

echo "=== HTML sem PNG correspondente ==="
while IFS= read -r -d '' html; do
    # ex: gen/book/simuladores/py.pt/cap01/sim-ep0101-distancia.html
    rel="${html#"$HTML_ROOT"/}"        # cap01/sim-ep0101-distancia.html
    cap="${rel%%/*}"                   # cap01
    capnum="${cap#cap}"                # 01
    base="$(basename "$rel" .html)"    # sim-ep0101-distancia

    expected_png="$PNG_ROOT/$cap/imagens/fig-${capnum}-${base}.png"

    if [[ ! -f "$expected_png" ]]; then
        echo "  HTML: $html"
        echo "    -> esperado: $expected_png (NÃO ENCONTRADO)"
        missing_png=$((missing_png + 1))
    fi
done < <(find "$HTML_ROOT" -mindepth 2 -maxdepth 2 -name '*.html' -print0 | sort -z)

echo
echo "=== PNG sem HTML correspondente ==="
while IFS= read -r -d '' png; do
    # ex: all/cap01/imagens/fig-01-sim-ep0101-distancia.png
    rel="${png#"$PNG_ROOT"/}"          # cap01/imagens/fig-01-sim-ep0101-distancia.png
    cap="${rel%%/*}"                   # cap01
    fname="$(basename "$rel" .png)"    # fig-01-sim-ep0101-distancia

    # remove o prefixo fig-NN- (assume 2 dígitos, mas aceita variações)
    base="$(echo "$fname" | sed -E 's/^fig-[0-9]+-//')"

    expected_html="$HTML_ROOT/$cap/${base}.html"

    if [[ ! -f "$expected_html" ]]; then
        echo "  PNG:  $png"
        echo "    -> esperado: $expected_html (NÃO ENCONTRADO)"
        missing_html=$((missing_html + 1))
    fi
done < <(find "$PNG_ROOT" -mindepth 3 -maxdepth 3 -path '*/imagens/*-sim-*.png' -print0 | sort -z)

echo
echo "=== Resumo ==="
echo "HTML sem PNG: $missing_png"
echo "PNG sem HTML: $missing_html"

if [[ $missing_png -eq 0 && $missing_html -eq 0 ]]; then
    echo "Tudo correspondendo corretamente."
fi
