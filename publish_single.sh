#!/usr/bin/env bash
# publish_single.sh — Renderiza e publica um único notebook
# Uso: ./publish_single.sh <notebook.ipynb> [--lang py] [--locale pt] [--skip-git]
set -e
cd "$(dirname "${BASH_SOURCE[0]}")"

FILE=""
LANG="py"
LOCALE="pt"
SKIP_GIT=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --lang)     LANG="$2";   shift 2 ;;
    --locale)   LOCALE="$2"; shift 2 ;;
    --skip-git) SKIP_GIT=true; shift ;;
    *)
      if [[ -z "$FILE" ]]; then FILE="$1"; fi
      shift ;;
  esac
done

if [[ -z "$FILE" ]]; then
  echo "Uso: $0 <notebook.ipynb> [--lang py] [--locale pt] [--skip-git]"
  exit 1
fi

COMBO="${LANG}.${LOCALE}"
BASENAME=$(basename "$FILE" .ipynb)
CAPDIR=$(basename "$(dirname "$FILE")")   # ex: cap01

echo "▶ Renderizando $FILE..."
python dev.py --once --langs "$LANG" --locales "$LOCALE" --render html "$FILE"

# O Quarto coloca o HTML em gen/book/<combo>/<capdir>/<basename>.html
HTML_SRC="gen/book/${COMBO}/${CAPDIR}/${BASENAME}.${COMBO}.html"

if [[ ! -f "$HTML_SRC" ]]; then
  echo "❌ HTML não encontrado: $HTML_SRC"
  echo "   Arquivos disponíveis em gen/book/${COMBO}/:"
  find "gen/book/${COMBO}" -name "*.html" 2>/dev/null || echo "   (nenhum)"
  exit 1
fi

echo "▶ Copiando para docs/..."
mkdir -p "docs/${COMBO}/${CAPDIR}"

# Copia o HTML
cp "$HTML_SRC" "docs/${COMBO}/${CAPDIR}/${BASENAME}.${COMBO}.html"

# Copia todos os assets do capítulo (imagens, CSS local, JS)
rsync -a --exclude="*.ipynb" --exclude="*.qmd" \
    "gen/book/${COMBO}/${CAPDIR}/" \
    "docs/${COMBO}/${CAPDIR}/"

if [[ -z "$SKIP_GIT" ]]; then
    TIMESTAMP=$(date +"%Y-%m-%d %H:%M")
    git add "docs/${COMBO}/${CAPDIR}/${BASENAME}.${COMBO}.html"
    if git commit -m "publish: ${CAPDIR}/${BASENAME} ($TIMESTAMP)"; then
        git push origin master 2>/dev/null || git push origin main 2>/dev/null
        echo "✅ Publicado: https://fzampirolli.github.io/pdi-vc/${COMBO}/${CAPDIR}/${BASENAME}.${COMBO}.html"
    else
        echo "ℹ Nada novo para commitar"
  fi
fi