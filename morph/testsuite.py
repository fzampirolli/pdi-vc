#!/usr/bin/env python3
# testsuite.py - Baixa casos de teste do GitHub e executa testes locais
import subprocess, sys, os, warnings, urllib.request, re

__version__ = "1.1.2"

warnings.filterwarnings("ignore")

RED    = '\033[0;31m'
GREEN  = '\033[0;32m'
YELLOW = '\033[1;33m'
NC     = '\033[0m'

GITHUB_BASE     = "https://raw.githubusercontent.com/fzampirolli/pdi-vc/master/all"
LOCAL_CASES_DIR = "casos"

# Idioma das mensagens impressas por este módulo — mesmo mecanismo do
# morph/config.py: lido de PDI_VC_LOCALE (definido pelo pipeline de build
# por combo), com "pt" como padrão fora do pipeline (Colab, uso avulso).
LOCALE = os.environ.get("PDI_VC_LOCALE", "pt")

_MESSAGES = {
    "pt": {
        "given_directly":    "📋 {n} caso(s) fornecido(s) diretamente",
        "testing_inline":    "\n🔍 Testando Python (inline)",
        "cases_exist":       "✔️ {nome_caso} já existe em {dir}/",
        "trying_url":        "📥 Tentando: {url}",
        "downloaded_ok":     "   ✅ Baixado com sucesso",
        "download_failed":   "❌ Não foi possível baixar {nome_caso}",
        "cases_loaded":      "📋 {n} caso(s) carregado(s) de {caminho}",
        "file_not_found":    "💥 Arquivo {arq} não encontrado.",
        "testing_lang_file": "\n🔍 Testando {linguagem}: {arquivo}",
        "file_too_short":    "⚠️ {arquivo}: Arquivo sem conteúdo (menos de 3 linhas). Testes ignorados.",
        "file_read_error":   "⚠️ Não foi possível ler {arquivo}: {erro}. Testes ignorados.",
        "compile_error":     "💥 Erro de compilação:",
        "runtime_error":     "💥 {nome}: Erro durante a execução",
        "case_ok":           "✔️ {nome}: OK",
        "case_failed":       "❌ {nome}: FALHOU",
        "input_label":       "   📥 Entrada:\n{entrada}",
        "expected_label":    "   🎯 Esperado:\n{esperado}",
        "obtained_label":    "   📤 Obtido:\n{obtido}",
        "timeout":           "⏱️ {nome}: Tempo limite excedido (5s)",
        "result_summary":    "\n📊 Resultado: {acertos}/{total} ({pct:.1f}%)",
        "all_passed":        "🎉 Parabéns! Todos os testes passaram.",
        "cli_usage":         "Uso: python3 testsuite.py EP01_02[.ext]",
        "invalid_name":      "Nome inválido: '{ep}'. Use EP01_02 ou EP1_2.",
    },
    "en": {
        "given_directly":    "📋 {n} case(s) provided directly",
        "testing_inline":    "\n🔍 Testing Python (inline)",
        "cases_exist":       "✔️ {nome_caso} already exists in {dir}/",
        "trying_url":        "📥 Trying: {url}",
        "downloaded_ok":     "   ✅ Downloaded successfully",
        "download_failed":   "❌ Could not download {nome_caso}",
        "cases_loaded":      "📋 {n} case(s) loaded from {caminho}",
        "file_not_found":    "💥 File {arq} not found.",
        "testing_lang_file": "\n🔍 Testing {linguagem}: {arquivo}",
        "file_too_short":    "⚠️ {arquivo}: Empty file (fewer than 3 lines). Tests skipped.",
        "file_read_error":   "⚠️ Could not read {arquivo}: {erro}. Tests skipped.",
        "compile_error":     "💥 Compilation error:",
        "runtime_error":     "💥 {nome}: Error during execution",
        "case_ok":           "✔️ {nome}: OK",
        "case_failed":       "❌ {nome}: FAILED",
        "input_label":       "   📥 Input:\n{entrada}",
        "expected_label":    "   🎯 Expected:\n{esperado}",
        "obtained_label":    "   📤 Output:\n{obtido}",
        "timeout":           "⏱️ {nome}: Timeout exceeded (5s)",
        "result_summary":    "\n📊 Result: {acertos}/{total} ({pct:.1f}%)",
        "all_passed":        "🎉 Congratulations! All tests passed.",
        "cli_usage":         "Usage: python3 testsuite.py EP01_02[.ext]",
        "invalid_name":      "Invalid name: '{ep}'. Use EP01_02 or EP1_2.",
    },
    "fr": {
        "given_directly":    "📋 {n} cas fourni(s) directement",
        "testing_inline":    "\n🔍 Test de Python (en ligne)",
        "cases_exist":       "✔️ {nome_caso} existe déjà dans {dir}/",
        "trying_url":        "📥 Tentative : {url}",
        "downloaded_ok":     "   ✅ Téléchargement réussi",
        "download_failed":   "❌ Impossible de télécharger {nome_caso}",
        "cases_loaded":      "📋 {n} cas chargé(s) depuis {caminho}",
        "file_not_found":    "💥 Fichier {arq} introuvable.",
        "testing_lang_file": "\n🔍 Test de {linguagem} : {arquivo}",
        "file_too_short":    "⚠️ {arquivo} : fichier vide (moins de 3 lignes). Tests ignorés.",
        "file_read_error":   "⚠️ Impossible de lire {arquivo} : {erro}. Tests ignorés.",
        "compile_error":     "💥 Erreur de compilation :",
        "runtime_error":     "💥 {nome} : erreur pendant l'exécution",
        "case_ok":           "✔️ {nome} : OK",
        "case_failed":       "❌ {nome} : ÉCHEC",
        "input_label":       "   📥 Entrée :\n{entrada}",
        "expected_label":    "   🎯 Attendu :\n{esperado}",
        "obtained_label":    "   📤 Obtenu :\n{obtido}",
        "timeout":           "⏱️ {nome} : délai dépassé (5 s)",
        "result_summary":    "\n📊 Résultat : {acertos}/{total} ({pct:.1f} %)",
        "all_passed":        "🎉 Félicitations ! Tous les tests ont réussi.",
        "cli_usage":         "Utilisation : python3 testsuite.py EP01_02[.ext]",
        "invalid_name":      "Nom invalide : '{ep}'. Utilisez EP01_02 ou EP1_2.",
    },
    "es": {
        "given_directly":    "📋 {n} caso(s) proporcionado(s) directamente",
        "testing_inline":    "\n🔍 Probando Python (en línea)",
        "cases_exist":       "✔️ {nome_caso} ya existe en {dir}/",
        "trying_url":        "📥 Intentando: {url}",
        "downloaded_ok":     "   ✅ Descargado con éxito",
        "download_failed":   "❌ No fue posible descargar {nome_caso}",
        "cases_loaded":      "📋 {n} caso(s) cargado(s) de {caminho}",
        "file_not_found":    "💥 Archivo {arq} no encontrado.",
        "testing_lang_file": "\n🔍 Probando {linguagem}: {arquivo}",
        "file_too_short":    "⚠️ {arquivo}: archivo vacío (menos de 3 líneas). Pruebas omitidas.",
        "file_read_error":   "⚠️ No fue posible leer {arquivo}: {erro}. Pruebas omitidas.",
        "compile_error":     "💥 Error de compilación:",
        "runtime_error":     "💥 {nome}: Error durante la ejecución",
        "case_ok":           "✔️ {nome}: OK",
        "case_failed":       "❌ {nome}: FALLÓ",
        "input_label":       "   📥 Entrada:\n{entrada}",
        "expected_label":    "   🎯 Esperado:\n{esperado}",
        "obtained_label":    "   📤 Obtenido:\n{obtido}",
        "timeout":           "⏱️ {nome}: Tiempo límite excedido (5s)",
        "result_summary":    "\n📊 Resultado: {acertos}/{total} ({pct:.1f}%)",
        "all_passed":        "🎉 ¡Felicidades! Todas las pruebas pasaron.",
        "cli_usage":         "Uso: python3 testsuite.py EP01_02[.ext]",
        "invalid_name":      "Nombre inválido: '{ep}'. Use EP01_02 o EP1_2.",
    },
    "it": {
        "given_directly":    "📋 {n} caso/i fornito/i direttamente",
        "testing_inline":    "\n🔍 Test di Python (inline)",
        "cases_exist":       "✔️ {nome_caso} esiste già in {dir}/",
        "trying_url":        "📥 Tentativo: {url}",
        "downloaded_ok":     "   ✅ Scaricato con successo",
        "download_failed":   "❌ Impossibile scaricare {nome_caso}",
        "cases_loaded":      "📋 {n} caso/i caricato/i da {caminho}",
        "file_not_found":    "💥 File {arq} non trovato.",
        "testing_lang_file": "\n🔍 Test di {linguagem}: {arquivo}",
        "file_too_short":    "⚠️ {arquivo}: file vuoto (meno di 3 righe). Test saltati.",
        "file_read_error":   "⚠️ Impossibile leggere {arquivo}: {erro}. Test saltati.",
        "compile_error":     "💥 Errore di compilazione:",
        "runtime_error":     "💥 {nome}: Errore durante l'esecuzione",
        "case_ok":           "✔️ {nome}: OK",
        "case_failed":       "❌ {nome}: FALLITO",
        "input_label":       "   📥 Input:\n{entrada}",
        "expected_label":    "   🎯 Atteso:\n{esperado}",
        "obtained_label":    "   📤 Ottenuto:\n{obtido}",
        "timeout":           "⏱️ {nome}: Timeout superato (5s)",
        "result_summary":    "\n📊 Risultato: {acertos}/{total} ({pct:.1f}%)",
        "all_passed":        "🎉 Complimenti! Tutti i test sono stati superati.",
        "cli_usage":         "Uso: python3 testsuite.py EP01_02[.ext]",
        "invalid_name":      "Nome non valido: '{ep}'. Usa EP01_02 o EP1_2.",
    },
}


def _msg(key, **kwargs):
    table = _MESSAGES.get(LOCALE, _MESSAGES["pt"])
    template = table.get(key, _MESSAGES["pt"][key])
    return template.format(**kwargs)


def compile_run_table(name: str) -> dict:
    """
    Comando de compilar (quando houver) e rodar cada linguagem suportada,
    para o nome-base `name` (ex.: "EP01_01"). Fonte única, usada por
    TestSuite._linguagens() e pelo pipeline de build (que não pode
    reimportar TestSuite sem puxar toda a lógica de download/comparação).
    """
    n = name
    return {
        ".py":   ("Python",   ["python3", f"{n}.py"],                    None),
        ".java": ("Java",     ["java", n],              ["javac", f"{n}.java"]),
        ".c":    ("C",        [f"./{n}"],                ["gcc",  f"{n}.c",   "-o", n, "-lm"]),
        ".cpp":  ("C++",      [f"./{n}"],                ["g++",  f"{n}.cpp", "-o", n]),
        ".js":   ("Node.js",  ["node", f"{n}.js"],                        None),
        ".r":    ("R",        ["Rscript", "--slave", f"{n}.r"],            None),
    }


class TestSuite:
    """Baixa casos de teste do GitHub e valida soluções locais."""

    def __init__(self, ep: str):
        """
        Parâmetro
        ---------
        ep : str
            Nome do EP com ou sem extensão. Ex: "EP01_01", "EP01_01.py", "EP1_1.c"
        """
        self._buf = []
        base, ext = os.path.splitext(ep)
        self.ext        = ext.lower() if ext else None
        self.base_norm, self.cap_str, self.ex_str = self._normalizar(base)
        if not self.base_norm:
            raise ValueError(_msg("invalid_name", ep=ep))

    # ------------------------------------------------------------------ #
    #  API pública                                                         #
    # ------------------------------------------------------------------ #

    def run(self):
        """Baixa os casos e executa os testes. Chamada principal."""
        nome_caso     = f"{self.base_norm}.cases"
        caminho_casos = os.path.join(LOCAL_CASES_DIR, nome_caso)

        if not self._baixar(nome_caso, caminho_casos):
            self._flush(); return

        casos = self._carregar(caminho_casos)
        if not casos:
            self._flush(); return

        for arq, ext in self._alvos():
            self._testar(self._linguagens()[ext], arq, casos)

        self._flush()


    def run_code(self, codigo: str, casos_dict: dict = None):
        """
        Executa código Python diretamente (sem salvar permanentemente o arquivo).
        O código é gravado em um arquivo temporário e executado pelo mesmo
        mecanismo utilizado por run(), garantindo comportamento idêntico.
        """
        import tempfile, os

        if casos_dict:
            casos = [(nome, v["input"], v["output"]) for nome, v in casos_dict.items()]
            self._p(_msg("given_directly", n=len(casos)))
        else:
            nome_caso = f"{self.base_norm}.cases"
            caminho_casos = os.path.join(LOCAL_CASES_DIR, nome_caso)
            if not self._baixar(nome_caso, caminho_casos):
                self._flush()
                return
            casos = self._carregar(caminho_casos)
            if not casos:
                self._flush()
                return

        self._p(_msg("testing_inline"))

        with tempfile.TemporaryDirectory() as tmp:
            nome = f"{self.base_norm}.py"
            arq = os.path.join(tmp, nome)
            with open(arq,"w",encoding="utf-8") as f:
                f.write(codigo)

            atual=os.getcwd()
            os.chdir(tmp)
            try:
                self._testar(self._linguagens()[".py"], nome, casos)
            finally:
                os.chdir(atual)

        self._flush()

    # ------------------------------------------------------------------ #
    #  Internos                                                            #
    # ------------------------------------------------------------------ #

    def _p(self, linha=""):
        self._buf.append(str(linha))

    def _flush(self):
        saida = "\n".join(self._buf)
        try:
            from IPython.display import display, HTML
            s = re.sub(r'\033\[0;32m(.*?)\033\[0m', r'<span style="color:#27ae60;font-weight:500">\1</span>', saida)
            s = re.sub(r'\033\[0;31m(.*?)\033\[0m', r'<span style="color:#e74c3c;font-weight:500">\1</span>', s)
            s = re.sub(r'\033\[1;33m(.*?)\033\[0m', r'<span style="color:#f39c12;font-weight:500">\1</span>', s)
            display(HTML(f'<pre style="font-family:monospace;font-size:13px;line-height:1.5;margin:0">{s}</pre>'))
        except Exception:
            print(saida)
        self._buf.clear()

    @staticmethod
    def _normalizar(base):
        m = re.match(r'EP(\d+)_(\d+)', base, re.IGNORECASE)
        if not m:
            return None, None, None
        cap, ex = int(m.group(1)), int(m.group(2))
        return f"EP{cap:02d}_{ex:02d}", f"{cap:02d}", f"{ex:02d}"

    def _baixar(self, nome_caso, caminho_local):
        os.makedirs(LOCAL_CASES_DIR, exist_ok=True)
        if os.path.exists(caminho_local):
            self._p(_msg("cases_exist", nome_caso=nome_caso, dir=LOCAL_CASES_DIR))
            return True
        cap_int = int(self.cap_str)
        ex_int  = int(self.ex_str)
        for url in [
            f"{GITHUB_BASE}/cap{self.cap_str}/casos/{nome_caso}",
            f"{GITHUB_BASE}/cap{self.cap_str}/cap{cap_int}/EP{cap_int}_{ex_int}.cases",
        ]:
            self._p(_msg("trying_url", url=url))
            try:
                urllib.request.urlretrieve(url, caminho_local)
                self._p(_msg("downloaded_ok"))
                return True
            except Exception:
                pass
        self._p(_msg("download_failed", nome_caso=nome_caso))
        return False

    def _carregar(self, caminho):
        try:
            conteudo = open(caminho, encoding="utf-8").read().strip()
        except Exception:
            return None
        if "case=" not in conteudo:
            return []
        casos = []
        for bloco in conteudo.split("case=")[1:]:
            linhas = bloco.strip().splitlines()
            if not linhas:
                continue
            nome, entrada, saida_opcoes, saida_atual, modo = linhas[0].strip(), [], [], [], None
            for linha in linhas[1:]:
                linha = linha.replace('\\n', '\n')
                if linha.startswith("input="):
                    if modo == "output" and saida_atual:
                        saida_opcoes.append("\n".join(saida_atual)); saida_atual = []
                    entrada.append(linha[6:]); modo = "input"
                elif linha.startswith("output="):
                    if modo == "output" and saida_atual:
                        saida_opcoes.append("\n".join(saida_atual)); saida_atual = []
                    saida_atual.append(linha[7:]); modo = "output"
                else:
                    (entrada if modo == "input" else saida_atual).append(linha)
            if saida_atual:
                saida_opcoes.append("\n".join(saida_atual))
            opcoes_limpas = [op[1:-1] if len(op) >= 2 and op[0] == op[-1] and op[0] in "\"'" else op
                             for op in saida_opcoes]
            casos.append((nome, "\n".join(entrada), "\n<OU>\n".join(opcoes_limpas)))
        self._p(_msg("cases_loaded", n=len(casos), caminho=caminho))
        return casos

    def _linguagens(self):
        return compile_run_table(self.base_norm)

    def _alvos(self):
        linguagens = self._linguagens()
        if self.ext and self.ext in linguagens:
            for candidato in [f"{self.base_norm}{self.ext}"]:
                if os.path.exists(candidato):
                    return [(candidato, self.ext)]
            self._p(_msg("file_not_found", arq=f"{self.base_norm}{self.ext}"))
            return []
        return [(f"{self.base_norm}{ext}", ext)
                for ext in linguagens if os.path.exists(f"{self.base_norm}{ext}")]

    @staticmethod
    def _extrair_numeros(texto):
        texto = texto.replace(',', '.')
        nums  = []
        for token in texto.split():
            t = "".join(c for c in token if c.isdigit() or c in '.-')
            try:
                if t: nums.append(float(t))
            except Exception:
                pass
        return nums

    def _comparar(self, obtido, gabarito_raw):
        opcoes     = gabarito_raw.split("\n<OU>\n")
        nums_aluno = self._extrair_numeros(obtido)
        if nums_aluno:
            for op in opcoes:
                nums_gab = self._extrair_numeros(op)
                if len(nums_aluno) == len(nums_gab) and all(abs(a-b) <= 0.011 for a,b in zip(nums_aluno, nums_gab)):
                    return True
        obtido_norm = obtido.strip().replace('\r\n', '\n')
        return any(obtido_norm == op.strip().replace('\r\n', '\n') for op in opcoes)

    def _testar(self, lang_info, arquivo, casos):
        linguagem, comando, compilar = lang_info
        self._p(_msg("testing_lang_file", linguagem=linguagem, arquivo=arquivo))

        # ⬇️ NOVO: verifica se o arquivo tem pelo menos 3 linhas
        try:
            with open(arquivo, 'r', encoding='utf-8') as f:
                num_linhas = sum(1 for _ in f)
            if num_linhas < 3:
                self._p(f"{YELLOW}{_msg('file_too_short', arquivo=arquivo)}{NC}")
                return
        except Exception as e:
            self._p(f"{YELLOW}{_msg('file_read_error', arquivo=arquivo, erro=e)}{NC}")
            return
        # ⬆️ fim da verificação

        if compilar:
            try:
                subprocess.run(compilar, check=True, capture_output=True)
            except subprocess.CalledProcessError as e:
                self._p(f"{RED}{_msg('compile_error')}{NC}")
                if e.stderr: self._p(e.stderr.decode())
                return

        acertos = 0
        for nome, entrada, gabarito_raw in casos:
            try:
                proc = subprocess.run(comando, input=entrada, capture_output=True, text=True, timeout=5)

                if proc.returncode != 0:
                    self._p(f"{RED}{_msg('runtime_error', nome=nome)}{NC}")
                    if proc.stderr.strip():
                        self._p(proc.stderr.strip())
                    continue

                saida = proc.stdout.strip()
                if self._comparar(saida, gabarito_raw):
                    self._p(f"{GREEN}{_msg('case_ok', nome=nome)}{NC}")
                    acertos += 1
                else:
                    self._p(f"{RED}{_msg('case_failed', nome=nome)}{NC}")
                    self._p(_msg("input_label", entrada=entrada))
                    self._p(_msg("expected_label", esperado=gabarito_raw.split('<OU>')[0].strip()))
                    self._p(_msg("obtained_label", obtido=saida))
            except subprocess.TimeoutExpired:
                self._p(f"{RED}{_msg('timeout', nome=nome)}{NC}")
            except Exception:
                self._p(f"{RED}{_msg('runtime_error', nome=nome)}{NC}")
                self._p(traceback.format_exc())
        pct = acertos / len(casos) * 100 if casos else 0
        self._p(_msg("result_summary", acertos=acertos, total=len(casos), pct=pct))
        if acertos == len(casos):
            self._p(f"{GREEN}{_msg('all_passed')}{NC}")


# ------------------------------------------------------------------ #
#  Uso via linha de comando: python3 testsuite.py EP01_01.py          #
# ------------------------------------------------------------------ #
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(_msg("cli_usage"))
        sys.exit(1)
    TestSuite(sys.argv[1]).run()
