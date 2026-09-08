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


def _pkgconfig_opencv(*args: str) -> list[str]:
    try:
        out = subprocess.run(['pkg-config', *args, 'opencv4'],
                             capture_output=True, text=True, timeout=5)
        return out.stdout.split() if out.returncode == 0 else []
    except Exception:
        return []


def _opencv_cxxflags() -> list[str]:
    """`pkg-config --cflags --libs opencv4` como lista; [] se indisponível.
    OK para `g++ ... fonte.cpp ... <estas flags>` (fonte ANTES das -l)."""
    return _pkgconfig_opencv('--cflags', '--libs')


def _opencv_cflags() -> list[str]:
    """Só `--cflags` (-I/-D): vão ANTES do arquivo-fonte no comando g++."""
    return _pkgconfig_opencv('--cflags')


def _opencv_libs() -> list[str]:
    """Só `--libs` (-L/-l): vão DEPOIS do arquivo-fonte (ordem do linker
    GNU: quem precisa do símbolo vem antes da -l que o provê)."""
    return _pkgconfig_opencv('--libs')


def _opencv_libs_min() -> list[str]:
    """Subconjunto mínimo p/ CPP_MM_OPENCV_CHAPTERS (cap04): mm::dil/ero →
    cv::dilate/erode, cv::createCLAHE, connectedComponents, findContours,
    putText/rectangle/circle/cvtColor, cv::RNG — tudo em core + imgproc.
    Linkar os ~45 .so do `pkg-config --libs opencv4` cheio custa ~60 s por
    célula e estoura o timeout do Quarto; aqui são 2-3. Mantém o `-L` do
    pkg-config (diretório das libs) e troca a lista de `-l`."""
    dirs = [f for f in _pkgconfig_opencv('--libs-only-L') if f.startswith('-L')]
    return dirs + ['-lopencv_imgproc', '-lopencv_imgcodecs', '-lopencv_core']

# Extensão de arquivo por linguagem-alvo suportada aqui (só as que têm etapa
# de compilação real — .py/.js/.r não passam por este módulo).
_EXT_BY_LANG = {'cpp': '.cpp', 'java': '.java', 'c': '.c'}


def compile_check(lang: str, source: str, name: str = 'snippet',
                   timeout: int = 15, opencv: bool = False,
                   run: bool = False, stub_state=None) -> tuple[bool, str]:
    """
    Escreve `source` num diretório temporário e tenta compilar via o comando
    de `compile_run_table`. Devolve (ok, stderr).

    `run=True`: além de compilar, EXECUTA o binário (com PNGs sintéticos em
    tmp/state/ para cada (var, idx) de `stub_state`) e exige exit 0 — pega
    tradução que compila mas crasha em runtime.

    `opencv=True` (capítulos em CPP_OPENCV_CHAPTERS): compila com
    `-DMM_USE_OPENCV` + flags do `pkg-config opencv4`, dando à célula acesso
    à API `cv::` do C++. Linkar OpenCV é lento — o timeout sobe.

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
            if opencv:
                flags = _opencv_cxxflags()
                if not flags:
                    return False, 'pkg-config opencv4 indisponível (libopencv-dev não instalado)'
                cmd += ['-DMM_USE_OPENCV', *flags]
                timeout = max(timeout, 60)

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

        if not run:
            return True, ''

        # ── Run-check: compilar não basta pros capítulos cv:: — a tradução do
        # LLM pode compilar e crashar em runtime (tipos cv::Mat misturados em
        # arithm_op, índice fora do range, etc.). Roda o binário com PNGs de
        # estado sintéticos e exige exit 0.
        (tmp_path / 'tmp' / 'state').mkdir(parents=True, exist_ok=True)
        for var, idx in (stub_state or []):
            _write_stub_png(tmp_path / 'tmp' / 'state' / f'{var}_{idx}.png')
        # Assets do capítulo lidos por caminho relativo (mm::read/cv::imread
        # "imagens/..."): o run-check roda num tmp isolado sem a pasta imagens/
        # do capítulo — cria stubs sintéticos para não reprovar por isso.
        for rel in set(re.findall(r'["\'](imagens/[^"\']+?\.(?:png|jpe?g))["\']',
                                  source, re.IGNORECASE)):
            dst = tmp_path / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            _write_stub_png(dst)
        run_cmd = compile_run_table(name)[ext][1]
        try:
            rr = subprocess.run(run_cmd, cwd=tmp_path, capture_output=True,
                                timeout=timeout, text=True)
        except subprocess.TimeoutExpired:
            return False, f'timeout ({timeout}s) ao EXECUTAR o binário'
        if rr.returncode != 0:
            return False, (rr.stderr or rr.stdout or
                           f'binário saiu com código {rr.returncode}')[-2000:]
        # exit 0 não basta: se a célula declara MM_OUT, o PNG TEM que sair —
        # senão a célula-cola `mm.read("tmp/fig_x.png")` dá FileNotFound e
        # derruba o render (ex.: binário que lê uma imagem que não existe e
        # segue com Mat vazio sem crashar).
        m = re.search(r'#define\s+MM_OUT\s+"([^"]+)"', source)
        if m and not (tmp_path / m.group(1)).exists():
            return False, f'binário rodou (exit 0) mas nao produziu {m.group(1)}'
        return True, ''


def _write_stub_png(path: Path):
    """PNG grayscale 64x64 — só pra o binário do run-check ter o que ler em
    state/. Conteúdo não importa, só existir com dimensões/canais válidos."""
    from PIL import Image as _PILImage
    _PILImage.new('L', (64, 64), color=128).save(str(path))


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


def strip_assumed_var_decls(cpp_src: str, var_names) -> str:
    """
    Remove linhas em que o LLM declarou/atribuiu uma variável que o prompt
    mandou tratar como JÁ disponível (ver `external_vars`/`persisted_vars`
    em translate()). Sem isso, a injeção mecânica de
    `mm::Image <var> = ...` logo depois colide com a do LLM
    (`redeclaration of 'mm::Image <var>'`) e derruba a tradução inteira pra
    referência. Casa a linha inteira: `mm::Image v;`, `mm::Image v = ...;`,
    `auto v = ...;` (com comentário opcional no fim).
    """
    names = [re.escape(v) for v in var_names]
    if not names:
        return cpp_src
    pat = re.compile(
        r'^[ \t]*(?:const\s+)?(?:mm::Image|auto)\s*&?\s*'
        r'(?:' + '|'.join(names) + r')\s*(?:=[^;]*)?;[ \t]*(?://[^\n]*)?\n',
        re.MULTILINE,
    )
    return pat.sub('', cpp_src)


def inject_consumer_reads(cpp_src: str, records: list):
    """
    Insere, logo após `int main() {`, um
    `mm::Image <var> = mm::read("state/<var>_<producer_idx>.png");` por
    registro consumido (cada um um dict com 'var_name'/'producer_idx',
    ver `notebook_processor._detect_cross_cell_mm_vars`). Devolve None se
    `main` não for localizado.
    """
    cpp_src = strip_assumed_var_decls(cpp_src, [r['var_name'] for r in records])
    span = find_main_body_span(cpp_src)
    if span is None:
        return None
    body_start, _ = span

    lines = [STATE_IO_BEGIN]
    for record in sorted(records, key=lambda r: r['var_name']):
        var = record['var_name']
        producer_idx = record['producer_idx']
        # _read_state preserva o nº de canais real do PNG (grayscale volta
        # 1-canal); mm::read forçaria 3, e a morfologia do cap04 lança em
        # imagem != 1 canal.
        lines.append(f'mm::Image {var} = mm::_read_state("{STATE_DIR}/{var}_{producer_idx}.png");')
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


# ── Ponte de estado no lado PYTHON ──────────────────────────────────────────
# Espelho de inject_consumer_reads/inject_producer_writes para células que a
# trilha C++ mantém como passthrough Python (figura matplotlib/pywt, simulador
# HTML) mas que dependem de / alimentam uma imagem produzida por outra célula
# (que virou programa C++ e gravou state/<var>_<idx>.png). Sem isto, a célula
# passthrough dá NameError na variável que "veio de outra célula".
STATE_IO_BEGIN_PY = '# [pdi:state-io] auto-gerado — não editar à mão'
STATE_IO_END_PY = '# [pdi:state-io:end]'


def _split_quarto_options(py_src: str):
    """Devolve (linhas de opção `#|` no topo, resto) — a injeção Python precisa
    entrar DEPOIS do bloco `#| label:/fig-cap:/...`, senão o Quarto não o
    reconhece como opções da célula."""
    lines = py_src.split('\n')
    i = 0
    while i < len(lines) and lines[i].lstrip().startswith('#|'):
        i += 1
    return lines[:i], lines[i:]


def inject_consumer_reads_py(py_src: str, records: list) -> str:
    """Prepende `<var> = mm.read("state/<var>_<producer_idx>.png")` (mm.read do
    Python já preserva grayscale → 2D), logo após as opções `#|` da célula."""
    opts, body = _split_quarto_options(py_src)
    reads = [STATE_IO_BEGIN_PY]
    for r in sorted(records, key=lambda r: r['var_name']):
        reads.append(f'{r["var_name"]} = mm.read('
                     f'"{STATE_DIR}/{r["var_name"]}_{r["producer_idx"]}.png")')
    reads.append(STATE_IO_END_PY)
    return '\n'.join(opts + reads + body)


def inject_producer_writes_py(py_src: str, var_names: list, producer_idx: int) -> str:
    """Anexa `mm.write(<var>, "state/<var>_<producer_idx>.png")` no fim da
    célula, criando o diretório."""
    tail = [STATE_IO_BEGIN_PY,
            f'import os as _pdi_os; _pdi_os.makedirs("{STATE_DIR}", exist_ok=True)']
    for v in sorted(var_names):
        tail.append(f'mm.write({v}, "{STATE_DIR}/{v}_{producer_idx}.png")')
    tail.append(STATE_IO_END_PY)
    return py_src.rstrip('\n') + '\n' + '\n'.join(tail) + '\n'


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
    cpp_src = strip_assumed_var_decls(cpp_src, var_names)
    span = find_main_body_span(cpp_src)
    if span is None:
        return None
    body_start, _ = span
    lines = [f'mm::Image {v};' for v in sorted(var_names)]
    block = '\n' + '\n'.join(lines) + '\n'
    return cpp_src[:body_start] + block + cpp_src[body_start:]
