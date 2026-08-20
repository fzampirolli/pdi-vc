#!/usr/bin/env bash
#
# setup.sh
#
# Configuração completa do ambiente para este projeto de livro em Quarto:
#   1. Pacotes do TinyTeX necessários para `quarto render --to pdf`
#      (lang: pt, pdf-engine: lualatex, docclass: book)
#   2. Ambiente virtual Python com o requirements.txt fixado
#
# Uso:
#   chmod +x setup.sh
#   ./setup.sh            # esquema completo do TeX Live (recomendado, vários GB)
#   ./setup.sh --minimal  # instala só os pacotes especificamente necessários
#
# Rode este script uma vez após clonar o projeto, ou sempre que o
# `quarto render` falhar com "File `X.sty` not found".

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TLMGR="$HOME/.TinyTeX/bin/x86_64-linux/tlmgr"
KPSEWHICH="$HOME/.TinyTeX/bin/x86_64-linux/kpsewhich"

# ---------------------------------------------------------------------------
# 1. Pacotes TinyTeX / LaTeX
# ---------------------------------------------------------------------------
if [ ! -x "$TLMGR" ]; then
    echo "ERRO: tlmgr não encontrado em $TLMGR"
    echo "Instale o TinyTeX primeiro, ex.: quarto install tinytex"
    exit 1
fi

echo ">>> [1/2] Configuração do TinyTeX"
echo ">>> Definindo repositório do TeX Live..."
"$TLMGR" option repository https://tlnet.yihui.org/

echo ">>> Atualizando o próprio tlmgr..."
"$TLMGR" update --self

if [ "${1:-}" = "--minimal" ]; then
    echo ">>> Instalando pacotes mínimos necessários..."
    "$TLMGR" install \
        luatexbase \
        ctablestack \
        babel-portuges \
        selnolig \
        fvextra \
        emoji \
        babel \
        biber \
        biblatex \
        fancyvrb \
        fontspec \
        l3kernel \
        latex-bin \
        pgf \
        texlive-scripts \
        unicode-data \
        xetex
else
    echo ">>> Instalando o esquema completo do TeX Live (isso pode demorar)..."
    "$TLMGR" install scheme-full
fi

echo ">>> Atualizando todos os pacotes TeX instalados..."
"$TLMGR" update --all

echo ">>> Regenerando banco de dados de nomes de arquivos..."
mktexlsr 2>/dev/null || "$HOME/.TinyTeX/bin/x86_64-linux/mktexlsr"

echo ">>> Verificando se os arquivos-chave agora são encontrados..."
for f in luatexbase.sty portuguese.ldf selnolig.sty fvextra.sty emoji.sty; do
    path=$("$KPSEWHICH" "$f" 2>/dev/null || true)
    if [ -n "$path" ]; then
        echo "  OK        $f -> $path"
    else
        echo "  FALTANDO  $f"
    fi
done

# ---------------------------------------------------------------------------
# 2. Ambiente virtual Python
# ---------------------------------------------------------------------------
echo ""
echo ">>> [2/2] Configuração do ambiente virtual Python"

VENV_DIR="$SCRIPT_DIR/.venv"
REQ_FILE="$SCRIPT_DIR/requirements.txt"

if [ ! -f "$REQ_FILE" ]; then
    echo "ERRO: requirements.txt não encontrado em $REQ_FILE"
    exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
    echo ">>> Criando ambiente virtual em $VENV_DIR ..."
    python3 -m venv "$VENV_DIR"
fi

echo ">>> Instalando dependências Python..."
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install -r "$REQ_FILE"
deactivate

echo ""
echo ">>> Concluído."
echo ">>> Ative o ambiente virtual com:  source .venv/bin/activate"
echo ">>> Depois renderize com:         quarto render --to pdf"
