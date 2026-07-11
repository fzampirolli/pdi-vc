#!/usr/bin/env bash

# Uso:
#   ./mermaid2png.sh fig-07-mapa-conceitual.mmd

set -e

if [ $# -ne 1 ]; then
    echo "Uso: $0 arquivo.mmd"
    exit 1
fi

IN="$1"
BASE="${IN%.*}"

TMP="$(mktemp)"

# Remove a sintaxe do Quarto
sed \
    -e '/^```{mermaid}/d' \
    -e '/^```$/d' \
    -e '/^%%|/d' \
    "$IN" > "$TMP"

echo "Gerando SVG..."
mmdc \
    -i "$TMP" \
    -o "${BASE}.svg"

echo "Gerando PNG (alta resolução)..."
mmdc \
    -i "$TMP" \
    -o "${BASE}.png" \
    -w 2200 \
    -H 3000 \
    -s 3

rm "$TMP"

echo
echo "Arquivos gerados:"
echo "  ${BASE}.svg"
echo "  ${BASE}.png"
