#!/bin/bash

# Buscar palavra
# grep -rn --include="*.ipynb" "rodar" all/cap*/
#

# Texto a ser substituído
ORIGINAL="""píxeis"""
DESTINO="""pixels"""

# Procura apenas nos notebooks dos capítulos usando Process Substitution
while IFS= read -r -d '' ARQ; do

    # Buscamos as ocorrências e jogamos o resultado em uma variável ou loop seguro
    # Usamos </dev/tty para garantir que o 'read' da pergunta leia o teclado, não o grep
    while IFS=: read -r LINHA CONTEUDO; do

        echo
        echo "Arquivo : $ARQ"
        echo "Linha   : $LINHA"
        echo "Texto   : $CONTEUDO"
        echo

        # Mudança aqui: </dev/tty força o Bash a ouvir o seu teclado físico
        read -p "Substituir esta ocorrência? [s/N] " RESP </dev/tty

        case "$RESP" in
            [sS]|[sS][iI][mM])
                # Ajuste no sed: aspas duplas e proteção de barras se necessário
                sed -i "${LINHA}s|${ORIGINAL}|${DESTINO}|g" "$ARQ"
                echo "✓ Alterado"
                ;;
            *)
                echo "✗ Mantido"
                ;;
        esac

    # Aqui alimentamos o loop interno sem fechar o stdin do terminal
    done < <(grep -n -F "$ORIGINAL" "$ARQ")

done < <(find all -type f -path "*/cap0*/*.ipynb" -print0)

echo
echo "Processo concluído."