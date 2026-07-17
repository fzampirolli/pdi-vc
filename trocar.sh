#!/bin/bash

# Texto a ser substituído
ORIGINAL="aluno"
DESTINO="estudante"

# Procura apenas nos notebooks dos capítulos
find all -type f -path "*/cap0*/*.ipynb" -print0 |
while IFS= read -r -d '' ARQ; do

    # Obtém linhas que contêm o texto
    grep -n -F "$ORIGINAL" "$ARQ" | while IFS=: read -r LINHA CONTEUDO; do

        echo
        echo "Arquivo : $ARQ"
        echo "Linha   : $LINHA"
        echo "Texto   : $CONTEUDO"
        echo

        read -p "Substituir esta ocorrência? [s/N] " RESP

        case "$RESP" in
            [sS]|[sS][iI][mM])
                sed -i "${LINHA}s|${ORIGINAL}|${DESTINO}|g" "$ARQ"
                echo "✓ Alterado"
                ;;
            *)
                echo "✗ Mantido"
                ;;
        esac
    done
done

echo
echo "Processo concluído."