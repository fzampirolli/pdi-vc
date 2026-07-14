#!/usr/bin/env python3
"""
Verifica ocorrencias de uma string em arquivos .ipynb e pergunta,
uma a uma, se deseja substituir.

Uso:
    python3 check_and_replace.py "all/cap06/*.ipynb"   # testar num capitulo
    python3 check_and_replace.py "all/*/*.ipynb"        # rodar em tudo
    python3 check_and_replace.py                        # usa 'all/*/*.ipynb' por padrao

Comandos durante a revisao:
    s = substituir esta ocorrencia
    n / enter = pular esta ocorrencia
    a = pular TODAS as ocorrencias restantes deste arquivo
    q = encerrar o programa agora (salva o que ja foi confirmado)
"""

import sys
import glob

# Em arquivos .ipynb (JSON), as aspas do HTML normalmente aparecem
# escapadas como \" dentro do texto bruto do arquivo. Tratamos os dois
# formatos possiveis (aspas normais e aspas escapadas).
PATTERNS = [
    (
        '<div style=\\"padding:20px;background:white;\\">',
        '<div style=\\"padding:20px;background:white;overflow:auto\\">',
    ),
    (
        '<div style="padding:20px;background:white;">',
        '<div style="padding:20px;background:white;overflow:auto">',
    ),
]

CONTEXT_LINES = 20


def process_file(path):
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    total_in_file = sum(
        line.count(old) for line in lines for old, _new in PATTERNS
    )
    if total_in_file == 0:
        return 0, 0

    print(f"\n########## {path} ##########")
    print(f"Ocorrencias encontradas neste arquivo: {total_in_file}")

    changed = 0
    reviewed = 0
    skip_rest_of_file = False
    stop_everything = False

    def find_next(text, start_pos):
        """Retorna (idx, old, new) da ocorrencia mais proxima entre todos
        os padroes, a partir de start_pos, ou None se nao houver mais."""
        best = None
        for old, new in PATTERNS:
            idx = text.find(old, start_pos)
            if idx != -1 and (best is None or idx < best[0]):
                best = (idx, old, new)
        return best

    for i, line in enumerate(lines):
        if skip_rest_of_file or stop_everything:
            break
        if not any(old in line for old, _new in PATTERNS):
            continue

        pos = 0
        new_line = line
        while True:
            found = find_next(new_line, pos)
            if found is None:
                break
            idx, old, new = found

            reviewed += 1
            start = max(0, i - CONTEXT_LINES)
            print("\n------------------------------------------------------")
            print(f"Arquivo: {path}")
            print(f"Linha: {i + 1}  (ocorrencia #{reviewed} deste arquivo)")
            print("Contexto (ate 20 linhas antes):")
            print("".join(lines[start:i]).rstrip("\n"))
            print(">>> linha com a ocorrencia:")
            print(new_line.rstrip("\n"))
            print("------------------------------------------------------")

            resp = input("Substituir por overflow:auto? [s/N/a/q] ").strip().lower()

            if resp == "s":
                new_line = new_line[:idx] + new + new_line[idx + len(old):]
                pos = idx + len(new)
                changed += 1
                print(">> marcado para substituicao.")
            elif resp == "a":
                print(">> pulando as demais ocorrencias deste arquivo.")
                skip_rest_of_file = True
                break
            elif resp == "q":
                print(">> encerrando o programa.")
                stop_everything = True
                break
            else:
                pos = idx + len(old)
                print(">> mantido sem alteracao.")

        lines[i] = new_line

    if changed > 0:
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        print(f">> Arquivo salvo com {changed} substituicao(oes).")
    else:
        print(">> Nenhuma alteracao salva neste arquivo.")

    return changed, stop_everything


def main():
    pattern = sys.argv[1] if len(sys.argv) > 1 else "all/*/*.ipynb"
    files = sorted(glob.glob(pattern))

    if not files:
        print(f"Nenhum arquivo encontrado para o padrao: {pattern}")
        sys.exit(1)

    print(f"Padrao: {pattern}")
    print(f"Arquivos encontrados: {len(files)}")
    for f in files:
        print(f"  - {f}")

    total_changed = 0
    for path in files:
        changed, stop = process_file(path)
        total_changed += changed
        if stop:
            break

    print(f"\n==================================================")
    print(f"Total de ocorrencias substituidas: {total_changed}")
    print(f"==================================================")


if __name__ == "__main__":
    main()
