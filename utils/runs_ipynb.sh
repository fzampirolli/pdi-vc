FALHAS=()
for nb in all/cap0*/cap0*.ipynb; do
  echo "▶ Executando: $nb"
  if ! jupyter nbconvert --to notebook --execute --inplace \
        --ExecutePreprocessor.timeout=1200 "$nb"; then
    FALHAS+=("$nb")
  fi
done

echo ""
if [ ${#FALHAS[@]} -eq 0 ]; then
  echo "✅ Todos os notebooks executaram sem erro."
else
  echo "❌ Notebooks com falha:"
  printf '   %s\n' "${FALHAS[@]}"
fi
