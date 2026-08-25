#!/usr/bin/env bash
# publish_all.sh — Pipeline completo: gerar → render → index → deploy para docs/
# Uso: ./publish_all.sh [--langs py,cpp] [--locales pt,en] [--dry-run] [--skip-git] [--skip-render]

set -e
cd "$(dirname "${BASH_SOURCE[0]}")"

# Valores padrão
LANGS="py"
LOCALES="pt"
DRY_RUN=""
SKIP_GIT=""
SKIP_RENDER=""

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
    --skip-render)
      SKIP_RENDER="true"
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
# Passo 1 e 2: Geração e Renderização (ignorados se --skip-render)
# ===================================================================
if [ -z "$SKIP_RENDER" ]; then
  echo ""
  echo "[1/6] Gerando notebooks traduzidos..."
  if [ -n "$DRY_RUN" ]; then
    echo "      Modo DRY-RUN (sem chamadas à API)"
  fi
  python dev.py --once --langs "$LANGS" --locales "$LOCALES" $DRY_RUN
  echo "      ✓ Notebooks em gen/"

  echo ""
  echo "[2/6] Renderizando HTML + PDF via dev.py..."
  python dev.py --once --langs "$LANGS" --locales "$LOCALES" --render all $DRY_RUN
  echo "      ✓ HTML e PDF em gen/book/"
else
  echo ""
  echo "[1/6 e 2/6] Pulando geração e renderização (--skip-render ativo)..."
  echo "            Usando arquivos existentes em gen/book/"
fi

# ===================================================================
# Passo 2b: Gerar notebooks para alunos
# ===================================================================
echo ""
echo "[2b/6] Gerando notebooks para alunos..."
python gerar_notebooks_alunos.py --batch references.bib --out-dir notebooks_alunos
echo "      ✓ notebooks_alunos/"

# ===================================================================
# Passo 2c: Extrair EPs e gerar fragmentos Moodle
# ===================================================================
echo ""
echo "[2c/6] Extraindo EPs e gerando fragmentos Moodle..."
IFS=',' read -ra LANG_LIST  <<< "$LANGS"
IFS=',' read -ra LOCALE_LIST <<< "$LOCALES"
for lang in "${LANG_LIST[@]}"; do
  for locale in "${LOCALE_LIST[@]}"; do
    versao="${lang}.${locale}"
    src="gen/book/${versao}"
    eps_dir="gen/book/eps/${versao}"
    moodle_dir="gen/book/eps/${versao}_moodle"
    if [ -d "$src" ]; then
      echo "      → extraindo EPs de ${versao}..."
      python ep_tools.py extrair --input "$src" --out-dir "$eps_dir" --quiet
      echo "      → gerando fragmentos Moodle para ${versao}..."
      python ep_tools.py limpar "$eps_dir" "$moodle_dir" \
        --base-url "https://fzampirolli.github.io/pdi-vc/eps/${versao}"
      ep_count=$(find "$moodle_dir" -name "EP*.html" 2>/dev/null | wc -l)
      echo "      ✓ ${ep_count} EPs Moodle em ${moodle_dir}/"
    fi
  done
done

# ===================================================================
# Passo 2d: Extrair Simuladores Interativos
# ===================================================================
echo ""
echo "[2d/6] Extraindo Simuladores Interativos..."
for lang in "${LANG_LIST[@]}"; do
  for locale in "${LOCALE_LIST[@]}"; do
    versao="${lang}.${locale}"
    src="gen/book/${versao}"
    if [ -d "$src" ]; then
      echo "      → extraindo simuladores de ${versao}..."
      python sim_tools.py extrair --input "$src" --quiet
    fi
  done
done

# ===================================================================
# Passo 3: Gerar página principal (índice) dentro de gen/book/
# ===================================================================
echo ""
echo "[3/6] Gerando página principal..."
if python -m pipeline.index_builder 2>/dev/null; then
  echo "      ✓ gen/book/index.html gerado"
else
  echo "      ⚠ Falha ao gerar índice"
fi

# ===================================================================
# Passo 4: Preparar docs/ para GitHub Pages
# ===================================================================
echo ""
echo "[4/6] Preparando docs/..."
rm -rf docs
mkdir -p docs
cp -rL gen/book/. docs/
touch docs/.nojekyll

# Rede de segurança: impede recrawl de conteúdo retirado de circulação
# (ex.: apendice_f, cujo resultado já está no artigo em revisão duplo-cego).
# NOTA: por ser um projeto no GitHub Pages (fzampirolli.github.io/pdi-vc/),
# este arquivo não é servido na raiz do domínio, então motores de busca que
# só respeitam robots.txt de raiz (ex. Google) podem ignorá-lo. Mantido
# como camada extra; a proteção real é o conteúdo nunca ser gerado.
cat > docs/robots.txt <<'EOF'
User-agent: *
Disallow: */apendice_f*
Disallow: */apendice-f*
EOF

# Copiar as duas versões de EP para docs/eps/
#
#   docs/eps/<versao>/          → HTML completo Quarto (MathJax perfeito, link para aluno)
#   docs/eps/<versao>_moodle/   → fragmento sem CSS externo (colar no editor VPL)
#
# URLs públicas:
#   https://fzampirolli.github.io/pdi-vc/eps/py.pt/EP01_01.html        (versão completa)
#   https://fzampirolli.github.io/pdi-vc/eps/py.pt_moodle/EP01_01.html (versão Moodle)
for lang in "${LANG_LIST[@]}"; do
  for locale in "${LOCALE_LIST[@]}"; do
    versao="${lang}.${locale}"
    eps_dir="gen/book/eps/${versao}"
    moodle_dir="gen/book/eps/${versao}_moodle"

    # Versão completa Quarto (fórmulas MathJax, para link público ao aluno)
    if [ -d "$eps_dir" ]; then
      mkdir -p "docs/eps/${versao}"
      cp "$eps_dir"/EP*.html "docs/eps/${versao}/" 2>/dev/null || true
      ep_count=$(find "docs/eps/${versao}" -name "EP*.html" 2>/dev/null | wc -l)
      echo "      ✓ ${ep_count} EPs (versão completa) → docs/eps/${versao}/"
    fi

    # Versão Moodle (fragmento sem CSS externo, para colar no editor VPL)
    if [ -d "$moodle_dir" ]; then
      mkdir -p "docs/eps/${versao}_moodle"
      cp "$moodle_dir"/EP*.html "docs/eps/${versao}_moodle/" 2>/dev/null || true
      ep_count=$(find "docs/eps/${versao}_moodle" -name "EP*.html" 2>/dev/null | wc -l)
      echo "      ✓ ${ep_count} EPs Moodle    → docs/eps/${versao}_moodle/"
    fi
  done
done

# Copiar Simuladores para docs/simuladores/
for lang in "${LANG_LIST[@]}"; do
  for locale in "${LOCALE_LIST[@]}"; do
    versao="${lang}.${locale}"
    sims_dir="gen/book/simuladores/${versao}"
    if [ -d "$sims_dir" ]; then
      mkdir -p "docs/simuladores/${versao}"
      cp -r "$sims_dir"/* "docs/simuladores/${versao}/" 2>/dev/null || true
      sim_count=$(find "docs/simuladores/${versao}" -name "*.html" ! -name "index.html" 2>/dev/null | wc -l)
      echo "      ✓ ${sim_count} Simuladores → docs/simuladores/${versao}/"
    fi
  done
done

# Comprime PDFs grandes (>50MB) com Ghostscript
find docs -name "*.pdf" | while read pdf; do
  size=$(du -m "$pdf" | cut -f1)
  if [ "$size" -gt 50 ]; then
    echo "      ⚙ Comprimindo $pdf (${size}MB)..."
    tmp="${pdf%.pdf}_tmp.pdf"
    if gs -dBATCH -dNOPAUSE -q -sDEVICE=pdfwrite \
          -dPDFSETTINGS=/ebook \
          -dCompatibilityLevel=1.5 \
          -sOutputFile="$tmp" "$pdf" 2>/dev/null; then
      mv "$tmp" "$pdf"
      new_size=$(du -m "$pdf" | cut -f1)
      echo "      ✓ Comprimido: ${size}MB → ${new_size}MB"
    else
      rm -f "$tmp"
      echo "      ⚠ Falha ao comprimir, mantendo original"
    fi
  fi
done
echo "      ✓ docs/ pronta"

# ===================================================================
# Passo 5: Git commit e push
# ===================================================================
echo ""
echo "[5/6] Git push principal..."
if [ -z "$SKIP_GIT" ]; then
  TIMESTAMP=$(date +"%Y-%m-%d %H:%M")
  git add -A docs/ notebooks_alunos/
  if git commit -m "publish: $TIMESTAMP (langs: $LANGS, locales: $LOCALES)"; then
    git push origin master || git push origin main
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
echo "  🎓 EPs — duas versões publicadas:"
for lang in "${LANG_LIST[@]}"; do
  for locale in "${LOCALE_LIST[@]}"; do
    versao="${lang}.${locale}"
    echo ""
    echo "    📖 Versão completa (MathJax — link para o aluno):"
    echo "       https://fzampirolli.github.io/pdi-vc/eps/${versao}/"
    echo "    📋 Versão Moodle   (HTML puro — colar no editor VPL):"
    echo "       https://fzampirolli.github.io/pdi-vc/eps/${versao}_moodle/"
    if [ -d "docs/eps/${versao}" ]; then
      for ep in $(find "docs/eps/${versao}" -name "EP*.html" | sort); do
        ep_name=$(basename "$ep" .html)
        echo "      · ${ep_name}"
        echo "          completo : https://fzampirolli.github.io/pdi-vc/eps/${versao}/${ep_name}.html"
        echo "          moodle   : https://fzampirolli.github.io/pdi-vc/eps/${versao}_moodle/${ep_name}.html"
      done
    fi
  done
done
echo ""
echo "  📂 Local:"
echo "    open docs/index.html"
echo "=================================================="

# Mostrar estatísticas finais
echo ""
echo "  📊 Estatísticas:"
echo "    $(find gen -name "*.ipynb" 2>/dev/null | wc -l) notebooks traduzidos"
echo "    $(find docs -name "*.html" 2>/dev/null | wc -l) arquivos HTML em docs/"
echo "    $(find docs -name "*.pdf"  2>/dev/null | wc -l) arquivos PDF em docs/"
echo "    $(find docs/eps -name "EP*.html" 2>/dev/null | wc -l) EPs publicados em docs/eps/ (completo + moodle)"
echo "=================================================="
