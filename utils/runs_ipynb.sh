FALHAS=()
mkdir -p logs
for nb in all/cap0*/cap0*.ipynb; do
  echo "▶ Executando: $nb"
  log="logs/$(basename "${nb%.ipynb}").log"
  if ! jupyter nbconvert --to notebook --execute --inplace \
        --ExecutePreprocessor.timeout=1200 "$nb" > "$log" 2>&1; then
    FALHAS+=("$nb")
    echo "   ❌ falhou — ver $log"
  fi
done

echo ""
if [ ${#FALHAS[@]} -eq 0 ]; then
  echo "✅ Todos os notebooks executaram sem erro."
else
  echo "❌ Notebooks com falha:"
  printf '   %s\n' "${FALHAS[@]}"
fi