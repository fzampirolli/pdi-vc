#!/usr/bin/env bash
set -e; cd "$(dirname "${BASH_SOURCE[0]}")"

echo "🧹 Iniciando limpeza profunda..."

# Tenta o comando nativo, mas não para se falhar (versões antigas)
quarto clean 2>/dev/null || echo "⚠️ Quarto clean não suportado, seguindo com limpeza manual..."

# Limpeza manual robusta
echo "🗑️ Removendo pastas de build e caches..."
# Adicionei 'gen' e 'docs' que são seus alvos de publicação
rm -rf .quarto _freeze __pycache__ .jupyter_cache gen/ docs/

# Limpeza de arquivos temporários
echo "📄 Limpando arquivos temporários..."
find . -type f \( \
    -name "*.aux" -o -name "*.log" -o -name "*.toc" -o -name "*.out" \
    -name "*.bbl" -o -name "*.blg" -o -name ".DS_Store" -o -name "*.synctex.gz" \
\) -delete 2>/dev/null || true

echo "✓ Ambiente limpo."