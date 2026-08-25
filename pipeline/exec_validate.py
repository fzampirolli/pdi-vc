"""
pipeline/exec_validate.py
==========================
Validação de execução em tempo de build.

Compila (nunca executa) um trecho de código traduzido por LLM antes de
aceitar a tradução — sem isso, uma tradução C++ quebrada seria cacheada e só
apareceria como erro no dia do render, ou pior, silenciosamente (o kernel
Python do Quarto não entende sintaxe C++, então uma célula quebrada nunca
gera um traceback óbvio).

Reaproveita a mesma tabela de comandos que já roda os EPs em 6 linguagens
(morph.testsuite.compile_run_table) — fonte única, não reinventa comando de
compilar por linguagem aqui.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from morph.testsuite import compile_run_table

REPO_ROOT = Path(__file__).resolve().parent.parent
MORPH_CPP_INCLUDE = REPO_ROOT / 'morph' / 'cpp'

# Extensão de arquivo por linguagem-alvo suportada aqui (só as que têm etapa
# de compilação real — .py/.js/.r não passam por este módulo).
_EXT_BY_LANG = {'cpp': '.cpp', 'java': '.java', 'c': '.c'}


def compile_check(lang: str, source: str, name: str = 'snippet',
                   timeout: int = 15) -> tuple[bool, str]:
    """
    Escreve `source` num diretório temporário e tenta compilar (nunca
    executar) via o comando de `compile_run_table`. Devolve (ok, stderr).

    Linguagens sem etapa de compilação registrada aqui (ainda não têm um
    tradutor real usando este gate) devolvem ok=True sem fazer nada.
    """
    ext = _EXT_BY_LANG.get(lang)
    if ext is None:
        return True, ''

    _, _, compile_cmd = compile_run_table(name)[ext]
    if compile_cmd is None:
        return True, ''

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        (tmp_path / f'{name}{ext}').write_text(source, encoding='utf-8')

        cmd = list(compile_cmd)
        if lang == 'cpp':
            # -I pro morph.hpp (Fase 4) — inofensivo se o snippet não incluir
            # nada de lá, ou se o header ainda não existir.
            cmd = [cmd[0], f'-I{MORPH_CPP_INCLUDE}', *cmd[1:]]

        try:
            result = subprocess.run(
                cmd, cwd=tmp_path, capture_output=True, timeout=timeout, text=True
            )
        except subprocess.TimeoutExpired:
            return False, f'timeout ({timeout}s) ao compilar'
        except FileNotFoundError as exc:
            return False, str(exc)

        if result.returncode != 0:
            return False, result.stderr
        return True, ''
