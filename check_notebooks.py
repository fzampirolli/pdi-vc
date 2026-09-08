#!/usr/bin/env python3
"""
check_notebooks.py — preflight de execução das fontes.

Executa cada `all/capNN/*.ipynb` (por padrão, menos os capítulos em SKIP_CAPS)
numa CÓPIA TEMPORÁRIA, com `morph.py` / `morph.hpp` / `stb_image*.h` da árvore
de trabalho, e falha (exit != 0) se qualquer célula quebrar.

Motivação: o build de 6 combos demora; um "esqueci de rodar uma célula" ou uma
`morph.*` local defasada só aparece lá na frente. Aqui o kernel é o mesmo que
o Francisco usa ao abrir o notebook no Jupyter (Python, cwd = pasta do
capítulo), então pega exatamente essa classe de erro — rápido e antes do build.

NÃO escreve outputs de volta nas fontes (roda sobre a cópia, que é descartada).
Os `%%writefile EPxx_yy.py` e downloads de células caem na cópia temporária.

Uso:
    python check_notebooks.py                     # cap01..cap08, .ipynb + .EPs
    python check_notebooks.py --chapters cap02,cap03
    python check_notebooks.py --no-eps            # só capNN.ipynb
    python check_notebooks.py --timeout 240       # segundos por célula
"""
from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import time
from pathlib import Path

import nbformat
from jupyter_client.manager import KernelManager
from nbclient import NotebookClient
from nbclient.exceptions import CellExecutionError

# Kernel = ESTE interpretador (não o kernelspec "python3", que resolve `python`
# pelo PATH e pode cair no Python do sistema em vez do .venv — morph.py usa
# sintaxe 3.11+). Rode com o python do .venv e o notebook roda nele também.
_KERNEL_ARGV = [sys.executable, '-m', 'ipykernel_launcher', '-f', '{connection_file}']

ROOT = Path(__file__).resolve().parent
ALL = ROOT / 'all'

# cap09 fica de fora por padrão (trilha não portada / dependências pesadas).
SKIP_CAPS = {'cap09'}

# Copiados da árvore de trabalho para a cópia temporária, sobrepondo o que o
# `config.setup` teria baixado do GitHub master.
_MORPH_PY = [ROOT / 'morph' / 'morph.py']
_MORPH_CPP = ['morph.hpp', 'stb_image.h', 'stb_image_write.h']

_IGNORE = shutil.ignore_patterns('tmp', 'state', '.ipynb_checkpoints', '__pycache__')


def _overlay_morph(cap_dir: Path, work: Path) -> None:
    for s in _MORPH_PY:
        if s.exists():
            shutil.copy2(s, work / s.name)
    for name in _MORPH_CPP:
        s = ROOT / 'morph' / 'cpp' / name
        if s.exists() and (cap_dir / name).exists():
            shutil.copy2(s, work / name)


def _run_one(nb_path: Path, timeout: int) -> str | None:
    """Retorna None se OK, senão uma string de erro (1 linha) buscável."""
    cap_dir = nb_path.parent
    rel = nb_path.relative_to(ROOT)
    with tempfile.TemporaryDirectory(prefix=f'nbcheck_{cap_dir.name}_') as td:
        work = Path(td) / cap_dir.name
        shutil.copytree(cap_dir, work, ignore=_IGNORE)
        _overlay_morph(cap_dir, work)

        nb = nbformat.read(work / nb_path.name, as_version=4)
        km = KernelManager(kernel_name='python3')
        km.kernel_spec.argv = list(_KERNEL_ARGV)
        client = NotebookClient(
            nb, km=km, timeout=timeout, allow_errors=False,
            resources={'metadata': {'path': str(work)}},
        )
        try:
            client.execute()
        except CellExecutionError as e:
            first = (e.evalue or '').strip().splitlines()
            return f'{rel}: {e.ename}: {first[0] if first else ""}'
        except Exception as e:                       # timeout, kernel morto, etc.
            return f'{rel}: {type(e).__name__}: {str(e).splitlines()[0] if str(e) else ""}'
    return None


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--chapters', default=None,
                    help='ex.: cap02,cap03 (padrão: todos menos %s)' % sorted(SKIP_CAPS))
    ap.add_argument('--no-eps', action='store_true', help='pula os *.EPs.ipynb')
    ap.add_argument('--timeout', type=int, default=240, help='segundos por célula')
    args = ap.parse_args()

    if args.chapters:
        caps = args.chapters.split(',')
    else:
        caps = sorted(p.name for p in ALL.glob('cap*')
                      if p.is_dir() and p.name not in SKIP_CAPS
                      and not p.name.startswith('_'))

    notebooks: list[Path] = []
    for cap in caps:
        d = ALL / cap
        main_nb = d / f'{cap}.ipynb'
        eps_nb = d / f'{cap}.EPs.ipynb'
        if main_nb.exists():
            notebooks.append(main_nb)
        if eps_nb.exists() and not args.no_eps:
            notebooks.append(eps_nb)

    if not notebooks:
        print('check_notebooks: nada a executar', file=sys.stderr)
        return 0

    print(f'=== check_notebooks — executando {len(notebooks)} notebook(s), '
          f'timeout {args.timeout}s/célula ===')
    failures: list[str] = []
    for nb_path in notebooks:
        t0 = time.time()
        err = _run_one(nb_path, args.timeout)
        dt = time.time() - t0
        if err is None:
            print(f'  \033[32m✓\033[0m {nb_path.relative_to(ROOT)}  ({dt:.0f}s)')
        else:
            print(f'  \033[31m✗ FAIL\033[0m {err}  ({dt:.0f}s)')
            failures.append(err)

    print()
    if failures:
        print(f'\033[31m{len(failures)} notebook(s) com célula quebrada\033[0m')
        for f in failures:
            print(f'  - {f}')
        return 1
    print(f'\033[32mOK\033[0m — {len(notebooks)} notebook(s) executaram sem erro')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
