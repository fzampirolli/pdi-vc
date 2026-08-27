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

import re
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


# ─────────────────────────────────────────────────────────────────────────────
# Injeção mecânica de state/ no C++ traduzido — variáveis mm::Image que
# atravessam células (ver notebook_processor._detect_cross_cell_mm_vars).
#
# Vive aqui (não em notebook_processor.py) por precisar ser importável tanto
# por `translators.py` (que a usa só pra STUBAR variáveis externas antes do
# compile_check interno de LLMCodeTranslator.translate() — sem isso, o
# compile_check reprovaria toda tradução que assume uma variável "já
# disponível", já que ela genuinamente não existe ainda nesse ponto) quanto
# por `notebook_processor.py` (que a usa pra injeção real, com os caminhos
# de state/<var>_<producer_idx>.png de verdade). String-manipulation, não
# parser C++ de verdade — tolerante a variações de formatação do LLM
# (`int main(){`/`int main() {`, com/sem `return` explícito) via casamento
# de chaves ciente de string/char/comentário.
# ─────────────────────────────────────────────────────────────────────────────

_MAIN_SIG_RE = re.compile(r'int\s+main\s*\([^)]*\)\s*\{')
STATE_IO_BEGIN = '// [pdi:state-io] auto-generated — do not edit by hand'
STATE_IO_END = '// [pdi:state-io:end]'

# Diretório dos PNGs de passagem de mm::Image entre células. Fica sob tmp/
# (mesma pasta dos demais artefatos de build — ver
# notebook_processor.TMP_DIR) pra não poluir o diretório do capítulo.
STATE_DIR = 'tmp/state'


def find_main_body_span(cpp_src: str):
    """
    Localiza `int main(...) { ... }` em `cpp_src` e devolve
    (body_start, body_end) — offsets logo após o `{` de abertura e na
    posição do `}` de fechamento correspondente — ou None se `main` não
    for encontrado. Casa chaves ignorando as que aparecem dentro de
    strings/chars/comentários.
    """
    m = _MAIN_SIG_RE.search(cpp_src)
    if m is None:
        return None
    depth = 1
    i = m.end()
    n = len(cpp_src)
    while i < n and depth > 0:
        c = cpp_src[i]
        if c == '/' and i + 1 < n and cpp_src[i + 1] == '/':
            j = cpp_src.find('\n', i)
            i = n if j == -1 else j
            continue
        if c == '/' and i + 1 < n and cpp_src[i + 1] == '*':
            j = cpp_src.find('*/', i + 2)
            i = n if j == -1 else j + 2
            continue
        if c in ('"', "'"):
            quote = c
            j = i + 1
            while j < n and cpp_src[j] != quote:
                j += 2 if cpp_src[j] == '\\' else 1
            i = j + 1
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return (m.end(), i)
        i += 1
    return None


def inject_consumer_reads(cpp_src: str, records: list):
    """
    Insere, logo após `int main() {`, um
    `mm::Image <var> = mm::read("state/<var>_<producer_idx>.png");` por
    registro consumido (cada um um dict com 'var_name'/'producer_idx',
    ver `notebook_processor._detect_cross_cell_mm_vars`). Devolve None se
    `main` não for localizado.
    """
    span = find_main_body_span(cpp_src)
    if span is None:
        return None
    body_start, _ = span

    lines = [STATE_IO_BEGIN]
    for record in sorted(records, key=lambda r: r['var_name']):
        var = record['var_name']
        producer_idx = record['producer_idx']
        lines.append(f'mm::Image {var} = mm::read("{STATE_DIR}/{var}_{producer_idx}.png");')
    lines.append(STATE_IO_END)
    block = '\n' + '\n'.join(lines) + '\n'

    return cpp_src[:body_start] + block + cpp_src[body_start:]


def inject_producer_writes(cpp_src: str, var_names: list, producer_idx: int):
    """
    Insere `std::filesystem::create_directories("state");` + um
    `mm::write(<var>, "state/<var>_<producer_idx>.png");` por variável,
    logo antes do ÚLTIMO `return` do corpo de `main` (ou no fim do corpo,
    se não houver `return`) — nunca "antes de cada return", pra não gravar
    uma imagem antes dela estar de fato calculada num caminho de saída
    antecipada. Garante `#include <filesystem>` (mm::write nunca cria
    diretório sozinho). Devolve None se `main` não for localizado.
    """
    span = find_main_body_span(cpp_src)
    if span is None:
        return None
    body_start, body_end = span
    body = cpp_src[body_start:body_end]

    lines = [STATE_IO_BEGIN,
             f'std::filesystem::create_directories("{STATE_DIR}");']
    for var in sorted(var_names):
        lines.append(f'mm::write({var}, "{STATE_DIR}/{var}_{producer_idx}.png");')
    lines.append(STATE_IO_END)
    block = '\n' + '\n'.join(lines) + '\n'

    returns = list(re.finditer(r'\breturn\b[^;]*;', body))
    if returns:
        last = returns[-1]
        new_body = body[:last.start()] + block + body[last.start():]
    else:
        new_body = body + block

    mutated = cpp_src[:body_start] + new_body + cpp_src[body_end:]
    return _ensure_filesystem_include(mutated)


def _ensure_filesystem_include(cpp_src: str) -> str:
    """Garante `#include <filesystem>` — mm::write nunca cria diretório
    sozinho, e create_directories() precisa do header."""
    if re.search(r'#include\s*<filesystem>', cpp_src):
        return cpp_src
    includes = list(re.finditer(r'^#include\s*[<"][^">]+[>"]', cpp_src, re.MULTILINE))
    insert_at = includes[-1].end() if includes else 0
    return cpp_src[:insert_at] + '\n#include <filesystem>' + cpp_src[insert_at:]


PANEL_IO_BEGIN = '// [pdi:panel-io] auto-generated — do not edit by hand'
PANEL_IO_END = '// [pdi:panel-io:end]'


def inject_panel_writes(cpp_src: str, var_names: list, base: str):
    """
    Insere `mm::write(<var>, "tmp/<base>_<i>.png");` — uma por imagem, NA
    ORDEM da lista (não ordenado) — antes do último `return` de `main`.

    Serve pra célula-glue Python exibir os painéis individualmente com
    títulos/eixos (mm.show([...], titles=[...], axis=...)); o
    `mm::show(imgs, MM_OUT)` do C++ só compõe um grid achatado, sem texto.
    Devolve None se `main` não for localizado.
    """
    span = find_main_body_span(cpp_src)
    if span is None:
        return None
    body_start, body_end = span
    body = cpp_src[body_start:body_end]

    lines = [PANEL_IO_BEGIN, 'std::filesystem::create_directories("tmp");']
    for i, var in enumerate(var_names):
        lines.append(f'mm::write({var}, "tmp/{base}_{i}.png");')
    lines.append(PANEL_IO_END)
    block = '\n' + '\n'.join(lines) + '\n'

    returns = list(re.finditer(r'\breturn\b[^;]*;', body))
    if returns:
        last = returns[-1]
        new_body = body[:last.start()] + block + body[last.start():]
    else:
        new_body = body + block

    mutated = cpp_src[:body_start] + new_body + cpp_src[body_end:]
    return _ensure_filesystem_include(mutated)


def inject_stub_declares(cpp_src: str, var_names: list):
    """
    Insere `mm::Image <var>;` (construtor default) logo após
    `int main() {` — SÓ pra validação de compilação interna de
    `LLMCodeTranslator.translate()` (ver ali), nunca usado na tradução
    final: uma tradução que assume uma variável "já disponível" (ver
    `external_vars` em translate()) genuinamente não a declara em lugar
    nenhum, e sem esse stub o compile_check reprovaria por
    "não declarado" um código que na verdade está correto — a variável
    real só existe depois que `notebook_processor._expand_foreign_code_cell`
    troca este stub por `inject_consumer_reads(...)` de verdade. Devolve
    None se `main` não for localizado.
    """
    span = find_main_body_span(cpp_src)
    if span is None:
        return None
    body_start, _ = span
    lines = [f'mm::Image {v};' for v in sorted(var_names)]
    block = '\n' + '\n'.join(lines) + '\n'
    return cpp_src[:body_start] + block + cpp_src[body_start:]
