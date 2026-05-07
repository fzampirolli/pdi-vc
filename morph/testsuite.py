#!/usr/bin/env python3
# testsuite.py - Baixa casos de teste do GitHub e executa testes locais

import subprocess, sys, os, warnings, urllib.request, re

warnings.filterwarnings("ignore")

# Cores para terminal
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
NC = '\033[0m'

# ================= CONFIGURAÇÃO =================
LOCAL_CASES_DIR = "casos"      # pasta local onde os .cases serão salvos
# =================================================

def normalizar_nome_ep(base):
    """
    Converte EP1_2 para EP01_02, ou mantém EP01_02.
    Retorna (base_normalizada, cap_str, ex_str)
    """
    m = re.match(r'EP(\d+)_(\d+)', base, re.IGNORECASE)
    if not m:
        return None, None, None
    cap = int(m.group(1))
    ex = int(m.group(2))
    base_norm = f"EP{cap:02d}_{ex:02d}"
    return base_norm, f"{cap:02d}", f"{ex:02d}"

def baixar_caso_github(nome_caso, cap_str, ex_str):
    """
    Tenta baixar do GitHub:
    1. Caminho novo: all/cap{cap_str}/casos/{nome_caso} (ex: EP01_02.cases)
    2. Caminho antigo: all/cap{cap_str}/cap1/EP{cap_int}_{ex_int}.cases
    """
    os.makedirs(LOCAL_CASES_DIR, exist_ok=True)
    local_path = os.path.join(LOCAL_CASES_DIR, nome_caso)

    if os.path.exists(local_path):
        print(f"✔️ {nome_caso} já existe em {LOCAL_CASES_DIR}/")
        return True

    # 1. Tentativa: caminho novo (casos + nome padronizado)
    url_novo = (f"https://raw.githubusercontent.com/fzampirolli/pdi-vc/master/all/"
                f"cap{cap_str}/casos/{nome_caso}")
    print(f"📥 Tentando novo caminho: {url_novo}")
    try:
        urllib.request.urlretrieve(url_novo, local_path)
        print(f"   ✅ Baixado (novo padrão)")
        return True
    except Exception:
        pass  # Falhou, tentar antigo

    # 2. Tentativa: caminho antigo (cap1 + nome sem zeros)
    cap_int = int(cap_str)
    ex_int = int(ex_str)
    nome_antigo = f"EP{cap_int}_{ex_int}.cases"
    url_antigo = (f"https://raw.githubusercontent.com/fzampirolli/pdi-vc/master/all/"
                  f"cap{cap_str}/cap1/{nome_antigo}")
    print(f"📥 Tentando caminho antigo: {url_antigo}")
    try:
        urllib.request.urlretrieve(url_antigo, local_path)
        print(f"   ✅ Baixado (estrutura antiga, renomeado para {nome_caso})")
        return True
    except Exception as e:
        print(f"❌ Falha também no caminho antigo: {e}")
        return False

def carregar_casos(caminho):
    """Carrega casos de teste do arquivo .cases (mesmo formato original)"""
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            conteudo = f.read().strip()
    except:
        return None

    if "case=" not in conteudo:
        return []

    casos = []
    blocos = conteudo.split("case=")[1:]

    for bloco in blocos:
        linhas = bloco.strip().splitlines()
        if not linhas:
            continue
        nome = linhas[0].strip()
        entrada = []
        saida_opcoes = []
        saida_atual = []
        modo = None

        for linha in linhas[1:]:
            linha = linha.replace('\\n', '\n')
            if linha.startswith("input="):
                if modo == "output" and saida_atual:
                    saida_opcoes.append("\n".join(saida_atual))
                    saida_atual = []
                entrada.append(linha[6:])
                modo = "input"
            elif linha.startswith("output="):
                if modo == "output" and saida_atual:
                    saida_opcoes.append("\n".join(saida_atual))
                    saida_atual = []
                saida_atual.append(linha[7:])
                modo = "output"
            else:
                if modo == "input":
                    entrada.append(linha)
                elif modo == "output":
                    saida_atual.append(linha)

        if saida_atual:
            saida_opcoes.append("\n".join(saida_atual))

        entrada_str = "\n".join(entrada)
        # Limpa aspas envolvendo cada opção de saída
        saida_opcoes_limpas = []
        for op in saida_opcoes:
            if len(op) >= 2 and op[0] == op[-1] and op[0] in "\"'":
                op = op[1:-1]
            saida_opcoes_limpas.append(op)
        saida_final = "\n<OU>\n".join(saida_opcoes_limpas)

        casos.append((nome, entrada_str, saida_final))

    print(f"📋 {len(casos)} caso(s) carregado(s) de {caminho}")
    return casos

def extrair_numeros(texto):
    """Extrai números de uma string (vírgula como separador decimal)"""
    texto = texto.replace(',', '.')
    nums = []
    for token in texto.split():
        token_limpo = "".join(c for c in token if c.isdigit() or c in '.-')
        if token_limpo:
            try:
                nums.append(float(token_limpo))
            except:
                pass
    return nums

def comparar_saidas(saida_aluno, gabarito_raw):
    """
    Compara saída do aluno com gabarito (numérico com tolerância ou textual exato)
    """
    opcoes = gabarito_raw.split("\n<OU>\n")
    nums_aluno = extrair_numeros(saida_aluno)

    # Modo numérico (se houver números na saída do aluno)
    if nums_aluno:
        for opcao in opcoes:
            nums_gab = extrair_numeros(opcao)
            if len(nums_aluno) == len(nums_gab):
                if all(abs(a - b) <= 0.011 for a, b in zip(nums_aluno, nums_gab)):
                    return True

    # Fallback: comparação exata de string (ignorando espaços e quebras)
    saida_norm = saida_aluno.strip().replace('\r\n', '\n')
    for opcao in opcoes:
        opcao_norm = opcao.strip().replace('\r\n', '\n')
        if saida_norm == opcao_norm:
            return True

    return False

def testar(linguagem, comando, arquivo, casos, compilar=None):
    """Executa os casos de teste para um dado arquivo fonte"""
    print(f"\n🔍 Testando {linguagem}: {arquivo}")

    if compilar:
        try:
            subprocess.run(compilar, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            print(f"{RED}💥 Erro de compilação:{NC}")
            if e.stderr:
                print(e.stderr.decode())
            return

    acertos = 0
    total = len(casos)

    for nome, entrada, esperado_raw in casos:
        try:
            proc = subprocess.run(comando, input=entrada,
                                  capture_output=True, text=True, timeout=5)
            saida = proc.stdout.strip()

            if comparar_saidas(saida, esperado_raw):
                print(f"{GREEN}✔️ {nome}: OK{NC}")
                acertos += 1
            else:
                print(f"{RED}❌ {nome}: FALHOU{NC}")
                # Mostra primeiro gabarito para depuração
                primeiro_gabarito = esperado_raw.split("<OU>")[0].strip()
                print(f"   📥 Entrada:\n{entrada}")
                print(f"   🎯 Esperado (primeira opção):\n{primeiro_gabarito}")
                print(f"   📤 Obtido:\n{saida}")

        except subprocess.TimeoutExpired:
            print(f"{RED}⏱️ {nome}: Tempo limite excedido (5s){NC}")
        except Exception as e:
            print(f"{RED}💥 {nome}: Erro - {e}{NC}")

    porcentagem = (acertos / total * 100) if total > 0 else 0
    print(f"\n📊 Resultado: {acertos}/{total} ({porcentagem:.1f}%)")
    if acertos == total:
        print(f"{GREEN}🎉 Parabéns! Todos os testes passaram.{NC}")

def main():
    if len(sys.argv) < 2:
        print("Uso: python testsuite.py EP01_02[.ext]")
        return

    entrada = sys.argv[1]
    base, ext_fornecida = os.path.splitext(entrada)
    if ext_fornecida:
        ext_fornecida = ext_fornecida.lower()
    base_sem_ext = base
    base_original = base_sem_ext

    # Normaliza o nome do EP (EP1_2 -> EP01_02)
    base_norm, cap_str, ex_str = normalizar_nome_ep(base_sem_ext)
    if not base_norm:
        print("❌ Nome inválido. Use EP01_02 ou EP1_2")
        return

    nome_caso = f"{base_norm}.cases"
    if not baixar_caso_github(nome_caso, cap_str, ex_str):
        print("❌ Abortando devido a falha no download.")
        return

    caminho_casos = os.path.join(LOCAL_CASES_DIR, nome_caso)
    casos = carregar_casos(caminho_casos)
    if not casos:
        return

    # Mapeamento de extensões
    linguagens = {
        ".py": ("Python", ["python3", f"{base_norm}.py"], None),
        ".java": ("Java", ["java", base_norm], ["javac", f"{base_norm}.java"]),
        ".c":   ("C",   [f"./{base_norm}"], ["gcc", f"{base_norm}.c", "-o", base_norm, "-lm"]),
        ".cpp": ("C++", [f"./{base_norm}"], ["g++", f"{base_norm}.cpp", "-o", base_norm]),
        ".js":  ("Node.js", ["node", f"{base_norm}.js"], None),
        ".r":   ("R", ["Rscript", "--slave", f"{base_norm}.r"], None),
    }

    # Lista de arquivos a testar
    alvos = []
    if ext_fornecida and ext_fornecida in linguagens:
        # Usuário especificou uma extensão: testa apenas ela (tenta primeiro normalizada)
        candidato = f"{base_norm}{ext_fornecida}"
        if os.path.exists(candidato):
            alvos.append((candidato, ext_fornecida))
        else:
            # Fallback para nome não normalizado (ex: EP1_2.c)
            candidato_original = f"{base_sem_ext}{ext_fornecida}"
            if os.path.exists(candidato_original):
                alvos.append((candidato_original, ext_fornecida))
            else:
                print(f"💥 Arquivo {candidato} não encontrado.")
                return
    else:
        # Nenhuma extensão fornecida: testa todas que existirem
        for ext in linguagens:
            if os.path.exists(f"{base_norm}{ext}"):
                alvos.append((f"{base_norm}{ext}", ext))
            elif os.path.exists(f"{base_sem_ext}{ext}"):
                alvos.append((f"{base_sem_ext}{ext}", ext))

    if not alvos:
        print(f"💥 Nenhum arquivo fonte encontrado para {base_norm}.")
        return

    for arq, ext in alvos:
        lang, cmd, comp = linguagens[ext]
        testar(lang, cmd, arq, casos, comp)

if __name__ == "__main__":
    main()