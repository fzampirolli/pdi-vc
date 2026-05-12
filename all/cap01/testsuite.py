#!/usr/bin/env python3
# testsuite.py - Baixa casos de teste do GitHub e executa testes locais
import subprocess, sys, os, warnings, urllib.request, re

__version__ = "1.1.0"

warnings.filterwarnings("ignore")

RED    = '\033[0;31m'
GREEN  = '\033[0;32m'
YELLOW = '\033[1;33m'
NC     = '\033[0m'

GITHUB_BASE     = "https://raw.githubusercontent.com/fzampirolli/pdi-vc/master/all"
LOCAL_CASES_DIR = "casos"


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
            raise ValueError(f"Nome inválido: '{ep}'. Use EP01_02 ou EP1_2.")

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
            self._p(f"✔️ {nome_caso} já existe em {LOCAL_CASES_DIR}/")
            return True
        cap_int = int(self.cap_str)
        ex_int  = int(self.ex_str)
        for url in [
            f"{GITHUB_BASE}/cap{self.cap_str}/casos/{nome_caso}",
            f"{GITHUB_BASE}/cap{self.cap_str}/cap{cap_int}/EP{cap_int}_{ex_int}.cases",
        ]:
            self._p(f"📥 Tentando: {url}")
            try:
                urllib.request.urlretrieve(url, caminho_local)
                self._p("   ✅ Baixado com sucesso")
                return True
            except Exception:
                pass
        self._p(f"❌ Não foi possível baixar {nome_caso}")
        return False

    def _carregar(self, caminho):
        try:
            conteudo = open(caminho, encoding="utf-8").read().strip()
        except Exception:
            return None
        
        if "case=" not in conteudo:
            return []
            
        casos = []
        # Divide pelos blocos de caso
        blocos = re.split(r'case=', conteudo)
        
        for bloco in blocos:
            if not bloco.strip():
                continue
            
            linhas = bloco.strip().splitlines()
            nome = linhas[0].strip()
            entrada_acumulada = []
            saida_acumulada = []
            modo = None
            
            for linha in linhas[1:]:
                # Limpeza de resíduos de comentários ou separadores do arquivo de cases
                if linha.startswith("####") or linha.strip() == "":
                    continue
                
                if linha.startswith("input="):
                    entrada_acumulada.append(linha[6:].replace('\\n', '\n'))
                    modo = "input"
                elif linha.startswith("output="):
                    saida_acumulada.append(linha[7:].replace('\\n', '\n'))
                    modo = "output"
                else:
                    # Se não tem prefixo, pertence ao modo atual
                    if modo == "input":
                        entrada_acumulada.append(linha.replace('\\n', '\n'))
                    elif modo == "output":
                        saida_acumulada.append(linha.replace('\\n', '\n'))
            
            if entrada_acumulada and saida_acumulada:
                entrada_final = "\n".join(entrada_acumulada).strip()
                # Remove marcações de strings (aspas) se existirem no arquivo de casos
                saida_final = "\n".join(saida_acumulada).strip()
                if len(saida_final) >= 2 and saida_final[0] == saida_final[-1] and saida_final[0] in "\"'":
                    saida_final = saida_final[1:-1]
                
                casos.append((nome, entrada_final, saida_final))
        
        self._p(f"📋 {len(casos)} caso(s) carregado(s) de {caminho}")
        return casos

    def _linguagens(self):
        n = self.base_norm
        return {
            ".py":   ("Python",   ["python3", f"{n}.py"],                    None),
            ".java": ("Java",     ["java", n],              ["javac", f"{n}.java"]),
            ".c":    ("C",        [f"./{n}"],                ["gcc",  f"{n}.c",   "-o", n, "-lm"]),
            ".cpp":  ("C++",      [f"./{n}"],                ["g++",  f"{n}.cpp", "-o", n]),
            ".js":   ("Node.js",  ["node", f"{n}.js"],                        None),
            ".r":    ("R",        ["Rscript", "--slave", f"{n}.r"],            None),
        }

    def _alvos(self):
        linguagens = self._linguagens()
        if self.ext and self.ext in linguagens:
            for candidato in [f"{self.base_norm}{self.ext}"]:
                if os.path.exists(candidato):
                    return [(candidato, self.ext)]
            self._p(f"💥 Arquivo {self.base_norm}{self.ext} não encontrado.")
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
        self._p(f"\n🔍 Testando {linguagem}: {arquivo}")

        # ⬇️ NOVO: verifica se o arquivo tem pelo menos 3 linhas
        try:
            with open(arquivo, 'r', encoding='utf-8') as f:
                num_linhas = sum(1 for _ in f)
            if num_linhas < 3:
                self._p(f"{YELLOW}⚠️ {arquivo}: Arquivo sem conteúdo (menos de 3 linhas). Testes ignorados.{NC}")
                return
        except Exception as e:
            self._p(f"{YELLOW}⚠️ Não foi possível ler {arquivo}: {e}. Testes ignorados.{NC}")
            return
        # ⬆️ fim da verificação

        if compilar:
            try:
                subprocess.run(compilar, check=True, capture_output=True)
            except subprocess.CalledProcessError as e:
                self._p(f"{RED}💥 Erro de compilação:{NC}")
                if e.stderr: self._p(e.stderr.decode())
                return
            
        acertos = 0
        for nome, entrada, gabarito_raw in casos:
            try:
                proc  = subprocess.run(comando, input=entrada, capture_output=True, text=True, timeout=5)
                saida = proc.stdout.strip()
                if self._comparar(saida, gabarito_raw):
                    self._p(f"{GREEN}✔️ {nome}: OK{NC}")
                    acertos += 1
                else:
                    self._p(f"{RED}❌ {nome}: FALHOU{NC}")
                    self._p(f"   📥 Entrada:\n{entrada}")
                    self._p(f"   🎯 Esperado:\n{gabarito_raw.split('<OU>')[0].strip()}")
                    self._p(f"   📤 Obtido:\n{saida}")
            except subprocess.TimeoutExpired:
                self._p(f"{RED}⏱️ {nome}: Tempo limite excedido (5s){NC}")
            except Exception as e:
                self._p(f"{RED}💥 {nome}: Erro - {e}{NC}")
        pct = acertos / len(casos) * 100 if casos else 0
        self._p(f"\n📊 Resultado: {acertos}/{len(casos)} ({pct:.1f}%)")
        if acertos == len(casos):
            self._p(f"{GREEN}🎉 Parabéns! Todos os testes passaram.{NC}")


# ------------------------------------------------------------------ #
#  Uso via linha de comando: python3 testsuite.py EP01_01.py          #
# ------------------------------------------------------------------ #
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python3 testsuite.py EP01_02[.ext]")
        sys.exit(1)
    TestSuite(sys.argv[1]).run()