#!/usr/bin/env bash
set -e

cd "$(dirname "${BASH_SOURCE[0]}")/.."

echo "🧹 Iniciando limpeza profunda..."

# Tenta o comando nativo (Quarto >= 1.5)
if ! quarto clean 2>/dev/null; then
    echo "⚠️  'quarto clean' não suportado, realizando limpeza manual..."
fi

echo "🗑️ Removendo diretórios de cache e build..."

find . \( \
    -name ".quarto" -o \
    -name "_freeze" -o \
    -name "__pycache__" -o \
    -name ".ipynb_checkpoints" -o \
    -name ".jupyter_cache" -o \
    -name "*_files" \
\) -type d -prune -exec rm -rf {} +

rm -rf gen docs

echo "📄 Removendo arquivos temporários..."

find . -type f \( \
    -name "*.aux" -o \
    -name "*.log" -o \
    -name "*.toc" -o \
    -name "*.out" -o \
    -name "*.bbl" -o \
    -name "*.blg" -o \
    -name "*.bcf" -o \
    -name "*.run.xml" -o \
    -name "*.fdb_latexmk" -o \
    -name "*.fls" -o \
    -name "*.synctex.gz" -o \
    -name "*.nav" -o \
    -name "*.snm" -o \
    -name "*.vrb" -o \
    -name ".DS_Store" \
\) -delete

echo "✅ Ambiente limpo."