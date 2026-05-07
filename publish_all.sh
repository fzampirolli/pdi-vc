#!/usr/bin/env bash
# publish_all.sh — Pipeline completo: gerar → render → index → deploy para docs/
# Uso: ./publish_all.sh [--langs py,cpp] [--locales pt,en] [--dry-run] [--skip-git]

set -e
cd "$(dirname "${BASH_SOURCE[0]}")"

# Valores padrão
LANGS="py"
LOCALES="pt"
DRY_RUN=""
SKIP_GIT=""

# Processa argumentos
while [[ $# -gt 0 ]]; do
  case $1 in
    --langs|--langs=*)
      if [[ "$1" == "--langs" ]]; then
        LANGS="$2"
        shift 2
      else
        LANGS="${1#*=}"
        shift
      fi
      ;;
    --locales|--locales=*)
      if [[ "$1" == "--locales" ]]; then
        LOCALES="$2"
        shift 2
      else
        LOCALES="${1#*=}"
        shift
      fi
      ;;
    --dry-run)
      DRY_RUN="--dry-run"
      shift
      ;;
    --skip-git)
      SKIP_GIT="true"
      shift
      ;;
    *)
      echo "Opção desconhecida: $1"
      shift
      ;;
  esac
done

echo "=================================================="
echo "  PDI+VC Livro — Pipeline de Publicação"
echo "  Langs: $LANGS | Locales: $LOCALES"
echo "  $(date)"
echo "=================================================="

# Criar diretórios necessários
mkdir -p gen
mkdir -p docs

# ===================================================================
# Passo 1: Gerar notebooks traduzidos
# ===================================================================
echo ""
echo "[1/5] Gerando notebooks traduzidos..."
if [ -n "$DRY_RUN" ]; then
  echo "      Modo DRY-RUN (sem chamadas à API)"
fi
python dev.py --once --langs "$LANGS" --locales "$LOCALES" $DRY_RUN
echo "      ✓ Notebooks em gen/"

# ===================================================================
# Passo 2: Renderizar HTML com Quarto
# ===================================================================
echo ""
echo "[2/5] Renderizando com Quarto..."
IFS=',' read -ra LANG_LIST <<< "$LANGS"
IFS=',' read -ra LOCALE_LIST <<< "$LOCALES"

for lang in "${LANG_LIST[@]}"; do
  for locale in "${LOCALE_LIST[@]}"; do
    combo="${lang}.${locale}"
    qdir="gen/quarto/${combo}"
    
    if [ -d "$qdir" ]; then
      echo "      📖 Processando: $combo"
      
      # Limpa cache do Quarto para forçar re-render
      rm -rf "$qdir/_freeze"
      
      echo "        → HTML..."
      (cd "$qdir" && quarto render --to html 2>&1) && echo "          ✓ HTML" || echo "          ⚠ Falha"
    fi
  done
done

# ===================================================================
# Passo 2b: Gerar notebooks para alunos
# ===================================================================
echo ""
echo "[2b/5] Gerando notebooks para alunos..."
python gerar_notebooks_alunos.py --batch references.bib --out-dir notebooks_alunos
echo "      ✓ notebooks_alunos/"

echo "        → PDF..."
(cd "$qdir" && quarto render --to pdf 2>&1) && echo "          ✓ PDF" || echo "          ⚠ Falha PDF"

# ===================================================================
# Passo 3: Gerar página principal (índice) dentro de gen/book/
# ===================================================================
echo ""
echo "[3/5] Gerando página principal..."
if python -m pipeline.index_builder 2>/dev/null; then
  echo "      ✓ gen/book/index.html gerado"
else
  echo "      ⚠ Falha ao gerar índice"
fi

# ===================================================================
# Passo 4: Preparar docs/ para GitHub Pages
# ===================================================================
echo ""
echo "[4/5] Preparando docs/..."
rm -rf docs
mkdir -p docs
cp -rL gen/book/. docs/
touch docs/.nojekyll
echo "      ✓ docs/ pronta"

# ===================================================================
# Passo 5: Git commit e push
# ===================================================================
echo ""
echo "[5/5] Git push principal..."
if [ -z "$SKIP_GIT" ]; then
  TIMESTAMP=$(date +"%Y-%m-%d %H:%M")
  git add docs/ gen/ notebooks_alunos/
  if git commit -m "publish: $TIMESTAMP (langs: $LANGS, locales: $LOCALES)"; then
    git push origin master 2>/dev/null || git push origin main 2>/dev/null
    echo "      ✓ Push realizado"
  else
    echo "      ℹ Nada novo para commitar"
  fi
fi

# ===================================================================
# Sumário final
# ===================================================================
echo ""
echo "=================================================="
echo "  ✅ Pipeline concluído!"
echo ""
echo "  📁 Saídas disponíveis:"
echo "    📄 gen/book/index.html (portal principal)"
for lang in "${LANG_LIST[@]}"; do
  for locale in "${LOCALE_LIST[@]}"; do
    combo="${lang}.${locale}"
    if [ -d "gen/book/${combo}" ]; then
      echo "    📖 gen/book/${combo}/ (HTML + PDF)"
    fi
  done
done
echo ""
echo "  🌐 GitHub Pages (docs/):"
echo "    https://fzampirolli.github.io/pdi-vc/"
echo ""
echo "  📂 Local:"
echo "    open docs/index.html"
echo "=================================================="

# Mostrar estatísticas finais
echo ""
echo "  📊 Estatísticas:"
echo "    $(find gen -name "*.ipynb" 2>/dev/null | wc -l) notebooks traduzidos"
echo "    $(find docs -name "*.html" 2>/dev/null | wc -l) arquivos HTML em docs/"
echo "    $(find docs -name "*.pdf" 2>/dev/null | wc -l) arquivos PDF em docs/"
echo "=================================================="