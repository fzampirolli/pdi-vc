#!/bin/bash
# run.sh — limpa cache e renderiza PDF

QDIR="gen/quarto/py.pt"
GENDIR="gen/py.pt"

# Limpa artefatos LaTeX
rm -rf "$QDIR"/.quarto
rm -f  "$QDIR"/*.aux "$QDIR"/*.log "$QDIR"/*.tex
rm -f  "$QDIR"/*.toc "$QDIR"/*.bcf "$QDIR"/*.bbl

# Limpa cache de execução dos notebooks
rm -rf "$GENDIR"/cap*/.quarto

make pdf