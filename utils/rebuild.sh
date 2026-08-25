#!/usr/bin/env bash
#
# utils/rebuild.sh
#
# Limpeza + build completo (HTML + PDF) para os combos indicados.
# Equivalente a: ./utils/limpar.sh && make build && make html && make pdf,
# mas com LANGS/LOCALES parametrizáveis.
#
# Não apaga .cache/translations.json — nem utils/limpar.sh nem os alvos do
# Makefile usados aqui tocam nesse arquivo, então traduções já em cache não
# são refeitas (nem custam API de novo).
#
# Uso:
#   ./utils/rebuild.sh                      # LANGS=py   LOCALES=pt,en (padrão)
#   ./utils/rebuild.sh cpp pt,en,fr         # LANGS=cpp  LOCALES=pt,en,fr
#   LANGS=py LOCALES=en ./utils/rebuild.sh  # via variável de ambiente

set -e
cd "$(dirname "${BASH_SOURCE[0]}")/.."

LANGS="${1:-${LANGS:-py}}"
LOCALES="${2:-${LOCALES:-pt,en}}"

echo "🔀 Langs: $LANGS | Locales: $LOCALES"
echo ""

./utils/limpar.sh
make build LANGS="$LANGS" LOCALES="$LOCALES"
make html  LANGS="$LANGS" LOCALES="$LOCALES"
#make pdf   LANGS="$LANGS" LOCALES="$LOCALES"
