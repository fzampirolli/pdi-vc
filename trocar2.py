#!/usr/bin/env python3
"""
remover_separador.py — Remove interativamente o trecho

    (linha em branco)
    ---
    (linha em branco)

de dentro do "source" de células MARKDOWN de notebooks .ipynb.

Por que não usar sed/grep como no script original?
----------------------------------------------------
O .ipynb é JSON. O trecho a remover é multi-linha (3 linhas dentro da
lista `source` da célula), então um `sed -i "<linha>s|...|...|g"` de
linha única não dá conta — e mexer no texto bruto do JSON à mão é
arriscado (pode quebrar aspas/escapes e corromper o notebook). Este
script abre o notebook com o módulo `json`, only mexe no array
`source` das células markdown, e regrava o arquivo no final.

Uso:
    python3 remover_separador.py                # varre all/cap0*/*.ipynb
    python3 remover_separador.py --base outra_pasta
    python3 remover_separador.py --dry-run       # só mostra, não pergunta nem grava
"""

import argparse
import json
import re
import sys
from pathlib import Path


def is_blank(line: str) -> bool:
    return line.strip() == ""


def is_hr(line: str) -> bool:
    """True se a linha, ignorando espaços, for só traços (--- ou mais)."""
    s = line.strip()
    return len(s) >= 3 and set(s) == {"-"}


def normalize_source(source) -> tuple[list[str], bool]:
    """Retorna (lista_de_linhas, era_lista_originalmente)."""
    if isinstance(source, str):
        return source.splitlines(keepends=True), False
    return list(source), True


def find_matches(lines: list[str]) -> list[set[int]]:
    """
    Localiza cada ocorrência de '---' cercado de linha(s) em branco.
    Retorna uma lista de conjuntos de índices (os índices que seriam
    removidos para aquela ocorrência: a linha '---' + as linhas em
    branco adjacentes que existirem).
    """
    matches: list[set[int]] = []
    for i, line in enumerate(lines):
        if not is_hr(line):
            continue
        prev_ok = (i == 0) or is_blank(lines[i - 1])
        next_ok = (i == len(lines) - 1) or is_blank(lines[i + 1])
        if not (prev_ok and next_ok):
            continue
        idxs = {i}
        if i > 0 and is_blank(lines[i - 1]):
            idxs.add(i - 1)
        if i < len(lines) - 1 and is_blank(lines[i + 1]):
            idxs.add(i + 1)
        matches.append(idxs)
    return matches


def print_context(lines: list[str], idxs: set[int]) -> None:
    lo = max(0, min(idxs) - 2)
    hi = min(len(lines), max(idxs) + 3)
    for i in range(lo, hi):
        marker = ">>" if i in idxs else "  "
        texto = lines[i].rstrip("\n")
        print(f"    {marker} [{i}] {texto!r}")


def process_notebook(path: Path, dry_run: bool) -> tuple[bool, bool]:
    """Retorna (changed, quit_requested)."""
    try:
        raw = path.read_text(encoding="utf-8")
        nb = json.loads(raw)
    except (OSError, json.JSONDecodeError) as e:
        print(f"⚠️  Não consegui ler/parsear {path}: {e}", file=sys.stderr)
        return False, False

    changed = False
    quit_requested = False

    for cell_idx, cell in enumerate(nb.get("cells", [])):
        if quit_requested:
            break
        if cell.get("cell_type") != "markdown":
            continue

        source = cell.get("source", [])
        if not source:
            continue

        lines, was_list = normalize_source(source)
        matches = find_matches(lines)
        if not matches:
            continue

        set_blank: set[int] = set()   # índices que viram uma única linha em branco
        remove_idx: set[int] = set()  # índices removidos de fato

        for idxs in matches:
            # Sobreposição com ocorrência já tratada nesta célula? pula.
            if idxs & (set_blank | remove_idx):
                continue

            print()
            print(f"Arquivo : {path}")
            print(f"Célula  : #{cell_idx} (markdown)")
            print("Contexto:")
            print_context(lines, idxs)
            print()

            if dry_run:
                print("  (dry-run — não remove nem pergunta)")
                continue

            resp = input("Remover esta ocorrência? [s/N/q] ").strip().lower()
            if resp in ("q", "sair"):
                print("⏹  Saindo... (progresso já confirmado até aqui será salvo)")
                quit_requested = True
                break
            elif resp in ("s", "sim"):
                keep_idx = min(idxs)          # essa linha vira a linha em branco
                remove_idx |= (idxs - {keep_idx})
                set_blank.add(keep_idx)
                print("✓ Marcado: '---' removido, 1 linha em branco mantida")
            else:
                print("✗ Mantido")

        if (set_blank or remove_idx) and not dry_run:
            new_lines = []
            for i, ln in enumerate(lines):
                if i in remove_idx:
                    continue
                if i in set_blank:
                    new_lines.append("\n")
                else:
                    new_lines.append(ln)
            cell["source"] = new_lines if was_list else "".join(new_lines)
            changed = True

    if changed and not dry_run:
        with path.open("w", encoding="utf-8") as f:
            json.dump(nb, f, indent=1, ensure_ascii=False)
            f.write("\n")
        print(f"\n💾 Salvo: {path}")

    return changed, quit_requested


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="all", help="pasta raiz (padrão: all)")
    ap.add_argument(
        "--pattern", default="cap0*/*.ipynb",
        help="glob relativo à pasta base (padrão: cap0*/*.ipynb)",
    )
    ap.add_argument("--dry-run", "-n", action="store_true", help="só mostra ocorrências, não pergunta nem grava")
    args = ap.parse_args()

    base = Path(args.base)
    if not base.is_dir():
        print(f"❌ Pasta não encontrada: {base}", file=sys.stderr)
        sys.exit(1)

    files = sorted(base.glob(args.pattern))
    if not files:
        print(f"❌ Nenhum .ipynb encontrado em {base}/{args.pattern}", file=sys.stderr)
        sys.exit(1)

    total_changed = 0
    interrupted = False
    for f in files:
        changed, quit_requested = process_notebook(f, args.dry_run)
        if changed:
            total_changed += 1
        if quit_requested:
            interrupted = True
            break

    print()
    print("─" * 50)
    status = "interrompido pelo usuário" if interrupted else "concluído"
    print(f"✅ Processo {status}. {total_changed} notebook(s) alterado(s).")


if __name__ == "__main__":
    main()