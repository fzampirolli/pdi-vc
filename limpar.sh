#!/usr/bin/env bash
set -e; cd "$(dirname "${BASH_SOURCE[0]}")"
echo "Limpando caches..."
find . -name ".quarto" -o -name "_freeze" -o -name "__pycache__" \
       -o -name ".jupyter_cache" | xargs rm -rf 2>/dev/null || true
find . \( -name "*.aux" -o -name "*.log" -o -name "*.toc" -o -name "*.out" \
       -o -name "*.bbl" -o -name "*.blg" -o -name ".DS_Store" \) \
       -delete 2>/dev/null || true
echo "✓ Limpeza concluída."
