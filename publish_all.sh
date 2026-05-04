#!/usr/bin/env bash
# publish_all.sh — Pipeline completo: gerar → render → index → push
# Uso: ./publish_all.sh [--langs py,cpp] [--locales pt,en] [--dry-run] [--skip-git] [--deploy]

#!/usr/bin/env bash
# publish_all.sh — Pipeline completo
# ./publish_all.sh --langs py --locales pt       
set -e
cd "$(dirname "${BASH_SOURCE[0]}")"

# Valores padrão
LANGS="py"
LOCALES="pt"
DRY_RUN=""
SKIP_GIT=""

# Processa argumentos de forma mais robusta
while [[ $# -gt 0 ]]; do
  case $1 in
    --langs)
      LANGS="$2"
      shift 2
      ;;
    --langs=*)
      LANGS="${1#*=}"
      shift
      ;;
    --locales)
      LOCALES="$2"
      shift 2
      ;;
    --locales=*)
      LOCALES="${1#*=}"
      shift
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

# Criar diretório gen/ se não existir
mkdir -p gen

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
# Passo 2: Copiar assets estáticos (se existirem)
# ===================================================================
echo ""
echo "[2/5] Copiando assets estáticos..."
if [ -d "assets" ]; then
  cp -r assets/* gen/ 2>/dev/null || true
  echo "      ✓ Assets copiados"
else
  echo "      ℹ Nenhum asset encontrado"
fi

# ===================================================================
# Passo 3: Renderizar HTML e PDF com Quarto
# ===================================================================
echo ""
echo "[3/5] Renderizando com Quarto..."
IFS=',' read -ra LANG_LIST <<< "$LANGS"
IFS=',' read -ra LOCALE_LIST <<< "$LOCALES"

RENDER_SUCCESS=0
RENDER_FAILED=0

for lang in "${LANG_LIST[@]}"; do
  for locale in "${LOCALE_LIST[@]}"; do
    combo="${lang}.${locale}"
    qdir="gen/quarto/${combo}"
    
    if [ -d "$qdir" ]; then
      echo ""
      echo "      📖 Processando: $combo"
      
      # HTML
      echo "        → HTML..."
      if (cd "$qdir" && quarto render --to html > /dev/null 2>&1); then
        echo "          ✓ HTML gerado"
      else
        echo "          ⚠ Falha no HTML"
        ((RENDER_FAILED++))
      fi
      
      # PDF
      echo "        → PDF..."
      if (cd "$qdir" && quarto render --to pdf > /dev/null 2>&1); then
        echo "          ✓ PDF gerado"
        ((RENDER_SUCCESS++))
      else
        echo "          ⚠ Falha no PDF (pode ser problema de LaTeX)"
        ((RENDER_FAILED++))
      fi
    else
      echo "      ⚠ $qdir não encontrado (pulando)"
    fi
  done
done

echo ""
echo "      Renderização: $RENDER_SUCCESS sucessos, $RENDER_FAILED falhas"

# ===================================================================
# Passo 4: Gerar página principal (índice)
# ===================================================================
echo ""
echo "[4/5] Gerando página principal..."
if python -m pipeline.index_builder 2>/dev/null; then
  echo "      ✓ gen/index.html"
else
  echo "      ⚠ Falha ao gerar índice (index_builder pode não existir)"
  # Criar índice mínimo
  cat > gen/index.html << 'EOF'
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>PDI+VC - Livro</title></head>
<body>
<h1>📖 Processamento Digital de Imagens e Visão Computacional</h1>
<p>Pipeline em execução... aguarde a conclusão.</p>
</body>
</html>
EOF
  echo "      ✓ Índice mínimo criado"
fi

# ===================================================================
# Passo 5: Git e Deploy
# ===================================================================
echo ""
echo "[5/5] Publicação..."

# Git commit
if [ -z "$SKIP_GIT" ]; then
  TIMESTAMP=$(date +"%Y-%m-%d %H:%M")
  echo "      📦 Git commit..."
  git add .
  if git commit -m "publish: $TIMESTAMP (langs: $LANGS, locales: $LOCALES)" 2>/dev/null; then
    echo "        ✓ Commit realizado"
    echo "      🚀 Git push..."
    if git push origin main 2>/dev/null; then
      echo "        ✓ Push realizado"
    else
      echo "        ⚠ Push falhou (branch ou remote?)"
    fi
  else
    echo "        ℹ Nada novo para commitar"
  fi
else
  echo "      ⚠ Git skipado (--skip-git)"
fi

# Deploy (copiar para outra pasta)
if [ -n "$DEPLOY" ]; then
  echo "      📂 Deploy para: $DEPLOY_PATH"
  mkdir -p "$DEPLOY_PATH"
  rsync -av --delete gen/ "$DEPLOY_PATH/" --exclude='.git*' 2>/dev/null
  echo "        ✓ Deploy realizado"
fi

# ===================================================================
# Sumário final
# ===================================================================
echo ""
echo "=================================================="
echo "  ✅ Pipeline concluído!"
echo ""
echo "  📁 Saídas disponíveis:"
echo "    📄 gen/index.html (portal principal)"
for lang in "${LANG_LIST[@]}"; do
  for locale in "${LOCALE_LIST[@]}"; do
    combo="${lang}.${locale}"
    if [ -d "gen/book/${combo}" ]; then
      echo "    📖 gen/book/${combo}/ (HTML + PDF)"
    fi
  done
done
echo ""
echo "  🌐 Abrir localmente:"
echo "    open gen/index.html"
echo ""
if [ -n "$DEPLOY" ]; then
  echo "  🌍 Publicado em: $DEPLOY_PATH"
fi
echo "=================================================="

# Mostrar estatísticas finais
echo ""
echo "  📊 Estatísticas:"
echo "    $(find gen -name "*.ipynb" 2>/dev/null | wc -l) notebooks traduzidos"
echo "    $(find gen -name "*.html" 2>/dev/null | wc -l) arquivos HTML"
echo "    $(find gen -name "*.pdf" 2>/dev/null | wc -l) arquivos PDF"
echo "=================================================="