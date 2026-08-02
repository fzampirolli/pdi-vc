#!/usr/bin/env bash
set -e

# ./run.sh                    # roda todos os notebooks + build completo
# ./run.sh 03                 # roda só o capítulo 3 + build completo
# ./run.sh --no-exec          # pula execução dos notebooks, só rebuilda o PDF
# ./run.sh 03 --no-exec       # equivalente a --no-exec (CAP é ignorado nesse caso)


cd /home/fz/fz/VSCode/pdi-vc
source .venv/bin/activate

CAP=""
SKIP_EXEC=false

# ── Parse de argumentos (ordem livre) ─────────────────────────────
for arg in "$@"; do
  case "$arg" in
    --no-exec|--skip-exec)
      SKIP_EXEC=true
      ;;
    *)
      CAP="$arg"
      ;;
  esac
done

# ── Execução dos notebooks (opcional) ─────────────────────────────
if [ "$SKIP_EXEC" = true ]; then
  echo "⏭️  Pulando execução dos notebooks (--no-exec)"
else
  if [ -z "$CAP" ]; then
    NOTEBOOKS=(all/cap*/cap*.ipynb)
  else
    NOTEBOOKS=(all/cap${CAP}/cap${CAP}.ipynb)
  fi

  # remove imagens de simulação para forçar reexecução dos notebooks
  rm -f all/cap*/imagens/fig-*-sim-*.png

  echo "📓 Executando notebooks..."
  for nb in "${NOTEBOOKS[@]}"; do
    echo "▶ $nb"
    jupyter nbconvert --to notebook --execute --inplace \
      --ExecutePreprocessor.timeout=600 \
      "$nb" || echo "❌ Falhou: $nb"
  done

  echo "🧹 Limpando arquivos temporários dos notebooks..."
  rm -f all/cap*/*.py
  rm -f all/cap*/*.png
  rm -f all/cap*/*.pgm
  rm -f all/cap*/*.txt
  rm -f all/cap*/*.csv
fi

# ── Limpeza de cache e build antigo ────────────────────────────────
echo "🗑️ Limpando cache e build antigo..."
make clean
rm -rf gen

QDIR="gen/quarto/py.pt"
GENDIR="gen/py.pt"

rm -rf "$QDIR"/.quarto
rm -f  "$QDIR"/*.aux "$QDIR"/*.log "$QDIR"/*.tex
rm -f  "$QDIR"/*.toc "$QDIR"/*.bcf "$QDIR"/*.bbl
rm -rf "$GENDIR"/cap*/.quarto

# ── Renderização ────────────────────────────────────────────────────
echo "📄 Renderizando PDF..."
make build-pdf

echo "✅ Concluído."