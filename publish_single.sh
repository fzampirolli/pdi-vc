#!/usr/bin/env bash
# publish_single.sh — Renderiza e publica um único notebook (capítulo ou apêndice)
# Uso: ./publish_single.sh <notebook.ipynb> [--lang py] [--locale pt] [--skip-git]
#
# Exemplos:
#   ./publish_single.sh all/cap01/cap01.ipynb
#   ./publish_single.sh all/apendices/apendice_f/apendice_f.ipynb
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
  echo "  ex.: $0 all/cap01/cap01.ipynb"
  echo "  ex.: $0 all/apendices/apendice_f/apendice_f.ipynb"
  exit 1
fi

COMBO="${LANG}.${LOCALE}"
BASENAME=$(basename "$FILE" .ipynb)
SUBDIR=$(basename "$(dirname "$FILE")")   # ex: cap01, ou apendice_f

echo "▶ Renderizando $FILE..."
python dev.py --once --langs "$LANG" --locales "$LOCALE" --render html "$FILE"

# O Quarto coloca o HTML em gen/book/<combo>/<subdir>/<basename>[.<combo>].html
#
# Capítulos (capXX) passam pelo pipeline de tradução e ganham o sufixo
# ".<combo>" no nome do arquivo (ex.: cap01.py.pt.ipynb → cap01.py.pt.html).
#
# Apêndices-notebook (ex.: apendice_f) ainda podem estar no modo "fallback
# cru" do quarto_builder.py — sem passar pela tradução por combo — nesse
# caso o Quarto gera o HTML sem sufixo (ex.: apendice_f.html). Por isso
# tentamos os dois padrões de nome abaixo, nessa ordem.
HTML_SRC="gen/book/${COMBO}/${SUBDIR}/${BASENAME}.${COMBO}.html"
if [[ ! -f "$HTML_SRC" ]]; then
  HTML_SRC_SEM_SUFIXO="gen/book/${COMBO}/${SUBDIR}/${BASENAME}.html"
  if [[ -f "$HTML_SRC_SEM_SUFIXO" ]]; then
    HTML_SRC="$HTML_SRC_SEM_SUFIXO"
  fi
fi

if [[ ! -f "$HTML_SRC" ]]; then
  echo "❌ HTML não encontrado. Tentei:"
  echo "   gen/book/${COMBO}/${SUBDIR}/${BASENAME}.${COMBO}.html"
  echo "   gen/book/${COMBO}/${SUBDIR}/${BASENAME}.html"
  echo "   Arquivos disponíveis em gen/book/${COMBO}/${SUBDIR}/:"
  find "gen/book/${COMBO}/${SUBDIR}" -name "*.html" 2>/dev/null || echo "   (nenhum)"
  exit 1
fi

HTML_NAME=$(basename "$HTML_SRC")

echo "▶ Copiando para docs/..."
mkdir -p "docs/${COMBO}/${SUBDIR}"

# Copia o HTML (preservando o nome real gerado, com ou sem sufixo de combo)
cp "$HTML_SRC" "docs/${COMBO}/${SUBDIR}/${HTML_NAME}"

# Copia todos os assets da pasta (imagens, CSS local, JS)
rsync -a --exclude="*.ipynb" --exclude="*.qmd" \
"gen/book/${COMBO}/${SUBDIR}/" \
"docs/${COMBO}/${SUBDIR}/"

if [[ -z "$SKIP_GIT" ]]; then
    TIMESTAMP=$(date +"%Y-%m-%d %H:%M")
    git add "docs/${COMBO}/${SUBDIR}/${HTML_NAME}"
if git commit -m "publish: ${SUBDIR}/${BASENAME} ($TIMESTAMP)"; then
        git push origin master 2>/dev/null || git push origin main 2>/dev/null
        echo "✅ Publicado: https://fzampirolli.github.io/pdi-vc/${COMBO}/${SUBDIR}/${HTML_NAME}"
else
        echo "ℹ Nada novo para commitar"
fi
fi
