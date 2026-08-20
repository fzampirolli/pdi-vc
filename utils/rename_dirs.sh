#!/bin/bash

# Renomeia pastas para versões "ocultas" com prefixo _
# Uso:
#   ./rename_dirs.sh hide
#   ./rename_dirs.sh restore

set -e

hide() {
    # cap0* exceto cap01
    for d in all/cap0*/; do
        [ -d "$d" ] || continue

        base=$(basename "$d")

        if [ "$base" != "cap01" ]; then
            mv "$d" "all/_$base"
        fi
    done

    # apendices
    if [ -d "all/apendices" ]; then
        mv all/apendices all/_apendices
    fi
}

restore() {
    # _cap0* → cap0*
    for d in all/_cap0*/; do
        [ -d "$d" ] || continue

        base=$(basename "$d")
        original="${base#_}"

        mv "$d" "all/$original"
    done

    # _apendices → apendices
    if [ -d "all/_apendices" ]; then
        mv all/_apendices all/apendices
    fi
}

case "$1" in
    hide)
        hide
        ;;
    restore)
        restore
        ;;
    *)
        echo "Uso: $0 {hide|restore}"
        exit 1
        ;;
esac
