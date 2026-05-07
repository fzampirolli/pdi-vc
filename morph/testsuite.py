#!/usr/bin/env python3
# testsuite.py - Versão com URLs Diretas e Comparação Numérica Flexível

import subprocess
import sys
import os
import shutil
import glob
import warnings

# ==============================================================================
# 🚩 CONFIGURAÇÃO DE FILTRO
# ==============================================================================
# Defina como True para impedir funções prontas, ou False para permitir tudo.
USE_PEDAGOGIC_FILTER = True

# Suprimir warnings do Python
warnings.filterwarnings("ignore")

# Cores para o terminal
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
MAGENTA = '\033[0;35m'
NC = '\033[0m' # No Color

# ==============================================================================
# CONFIGURAÇÃO CENTRAL - URLs diretas para cada capítulo
# ==============================================================================
CAPITULOS_URLS = {
    '1': '1IBUcrzLE3ZJSqKT1nrqkLD59FlH-wAjV',  # URL pública da pasta cap1
    '2': '12i58IGZo_jfn4rMd2vGDzQRLAlG4skyc',  # URL pública da pasta cap2
    '3': '1jOLV4k1xsnSaO4FgdeAYS95uMmWluOSl',  # URL pública da pasta cap3
    '4': '1pyc0f7zaUF1Eoi-Mv5R65DfjpG5Og0Kr',  # URL pública da pasta cap4
    '5': '1vwg_pSiJLDGLunjOStPeIZDgVKqJ0ej4',  # URL pública da pasta cap5
    '6': '1_7LZX-1dZx1AsyBL1kVivhwQpGtdiapU',  # URL pública da pasta cap6
    '7': '',  # URL pública da pasta cap7
    '8': '',  # URL pública da pasta cap8
}

# Alternativa: Tentar a pasta raiz primeiro (caso funcione)
PASTA_RAIZ_ID = '1Q6SV3xklQahA9QBG83IuSvdR4LnnqOHa'

# ID do arquivo verificar_arquivo.py no Google Drive
VERIFICAR_ARQUIVO_ID = '136UduedgMuSpnPUE7C_p1Qp_SL9KG-st'

# ==============================================================================


import urllib.request
import urllib.error

def baixar_casos_do_github(pasta_destino, numero_cap):
    """
    Baixa todos os arquivos .cases do capítulo 'cap{numero_cap:02d}' do GitHub.
    Retorna True se pelo menos um arquivo .cases for baixado.
    """
    # URL base dos arquivos brutos do GitHub
    base_url = f"https://raw.githubusercontent.com/fzampirolli/pdi-vc/master/all/cap{numero_cap:02d}/"
    
    # Lista de arquivos .cases conhecida (ou podemos tentar baixar dinamicamente)
    # Como não há listagem de diretório via raw, usamos uma lista fixa ou tentamos nomes comuns.
    # A solução mais simples: baixar o arquivo esperado baseado no nome do EP.
    # Mas para manter a generalidade, vamos tentar baixar qualquer .cases referenciado no código.
    # Como isso é complexo, faremos: tentar baixar um arquivo .cases genérico? 
    # Melhor: aceitar que o nome do arquivo .cases é conhecido (ex: EP1_2.cases). Vamos ajustar.
    
    # Na verdade, a função original baixava uma pasta inteira. Vamos simular:
    # Precisamos saber quais arquivos .cases existem no capítulo. Como não temos listagem,
    # vamos baixar o arquivo .cases correspondente ao EP que está sendo testado.
    # Isso é suficiente para o funcionamento do testsuite.py.
    
    # Portanto, essa função será chamada com o nome do arquivo .cases esperado.
    # Vamos modificar a assinatura para receber também o nome do arquivo.
    pass

def baixar_capitulo_direto(numero_capitulo, pasta_capitulo):
    if numero_capitulo not in CAPITULOS_URLS: return False
    url = CAPITULOS_URLS[numero_capitulo]
    if not url or url.startswith('COLE'): return False
    
    print(f"📥 Baixando capítulo {numero_capitulo}...")
    try:
        subprocess.run(["gdown", "--folder", url, "-O", pasta_capitulo, "--quiet"], check=True)
        return bool(glob.glob(os.path.join(pasta_capitulo, "*.cases")))
    except: return False

def baixar_pasta_raiz_seletivo(pasta_capitulo):
    print(f"🔄 Tentando download alternativo...")
    temp_dir = "temp_download_geral"
    try:
        subprocess.run(["gdown", "--folder", PASTA_RAIZ_ID, "-O", temp_dir, "--quiet"], check=True)
        origem = os.path.join(temp_dir, pasta_capitulo)
        if not os.path.exists(origem): return False
        
        os.makedirs(pasta_capitulo, exist_ok=True)
        for f in glob.glob(os.path.join(origem, "*.cases")):
            shutil.copy(f, os.path.join(pasta_capitulo, os.path.basename(f)))
        return True
    except: return False
    finally:
        if os.path.exists(temp_dir): shutil.rmtree(temp_dir)

def baixar_dependencias(num, pasta):
    if glob.glob(f"{pasta}/*.cases"):
        print(f"✔️ Casos de teste para '{pasta}' já existem.")
        return True
    return baixar_capitulo_direto(num, pasta) or baixar_pasta_raiz_seletivo(pasta)

def garantir_verificador():
    """Baixa o script do Prof. Pisani se não existir e o filtro estiver ativo."""
    if USE_PEDAGOGIC_FILTER and not os.path.exists("verificar_arquivo.py"):
        print(f"{BLUE}📥 Baixando verificador de restrições (verificar_arquivo.py)...{NC}")
        try:
            subprocess.run(["gdown", VERIFICAR_ARQUIVO_ID, "-O", "verificar_arquivo.py", "--quiet"], check=True)
            return True
        except:
            print(f"{YELLOW}⚠️ Falha no download do verificador. Prosseguindo sem filtro.{NC}")
            return False
    return USE_PEDAGOGIC_FILTER

def carregar_casos(caminho_arquivo):
    try:
        with open(caminho_arquivo, "r", encoding="utf-8") as f:
            conteudo = f.read().strip()
    except: return None

    if "case=" not in conteudo: return []
    
    casos = []
    blocos = conteudo.split("case=")[1:]
    
    for bloco in blocos:
        linhas = bloco.strip().splitlines()
        if not linhas: continue
        
        nome = linhas[0].strip()
        entrada = []
        saida_opcoes = [] # Lista de possíveis saídas (para casos com output= multiplos)
        saida_atual = []  # Acumula linhas de UMA saída
        
        modo = None
        
        for linha in linhas[1:]:
            linha = linha.replace('\\n', '\n')
            
            if linha.startswith("input="):
                # Se mudou para input e tinha output acumulado, salva o output
                if modo == "output" and saida_atual:
                    saida_opcoes.append("\n".join(saida_atual))
                    saida_atual = []
                entrada.append(linha[6:])
                modo = "input"
                
            elif linha.startswith("output="):
                # Se já tinha um output sendo montado (multilinha), salva ele antes de começar o novo
                if modo == "output" and saida_atual:
                    saida_opcoes.append("\n".join(saida_atual))
                    saida_atual = []
                
                val = linha[7:]
                saida_atual.append(val)
                modo = "output"
                
            else:
                if modo == "input":
                    entrada.append(linha)
                elif modo == "output":
                    saida_atual.append(linha)
        
        # Salva o último output pendente
        if saida_atual:
            saida_opcoes.append("\n".join(saida_atual))
            
        entrada_str = "\n".join(entrada)
        
        # Limpa aspas que envolvem o bloco inteiro de cada opção de saída
        saida_opcoes_limpas = []
        for op in saida_opcoes:
            if len(op) >= 2 and op.startswith('"') and op.endswith('"'):
                op = op[1:-1]
            elif len(op) >= 2 and op.startswith("'") and op.endswith("'"):
                op = op[1:-1]
            saida_opcoes_limpas.append(op)
            
        # Junta tudo com separador especial para processamento posterior
        saida_final_str = "\n<OU>\n".join(saida_opcoes_limpas)
        
        casos.append((nome, entrada_str, saida_final_str))
        
    print(f"📋 {len(casos)} caso(s) carregado(s)")
    return casos

# ==============================================================================
# LÓGICA DE COMPARAÇÃO ROBUSTA (NUMÉRICA E TEXTUAL)
# ==============================================================================

def extrair_numeros(texto):
    """
    Normaliza a string trocando vírgulas por pontos e extrai todos os floats.
    Retorna uma lista de floats encontrados na ordem.
    """
    texto_limpo = texto.replace(',', '.')
    numeros = []
    # Quebra por whitespace (espaço, tab, enter)
    for token in texto_limpo.split():
        try:
            # Tenta limpar caracteres comuns ao redor de números (ex: R$50.00 -> 50.00)
            token_limpo = "".join(c for c in token if c.isdigit() or c == '.' or c == '-')
            if token_limpo:
                numeros.append(float(token_limpo))
        except ValueError:
            continue
    return numeros

def comparar_saidas(saida_aluno, gabarito_raw):
    """
    Compara a saída do aluno com o gabarito.
    1. Tenta extrair números e comparar com tolerância.
    2. Se falhar ou não tiver números, tenta comparação de string exata (stripped).
    """
    opcoes_gabarito = gabarito_raw.split("\n<OU>\n")
    
    numeros_aluno = extrair_numeros(saida_aluno)
    
    # === MODO 1: Comparação Numérica ===
    if numeros_aluno:
        for opcao in opcoes_gabarito:
            numeros_gabarito = extrair_numeros(opcao)
            
            # Se quantidade de números difere, não é essa opção
            if len(numeros_aluno) != len(numeros_gabarito):
                continue
            
            match_numerico = True
            for val_a, val_g in zip(numeros_aluno, numeros_gabarito):
                # Tolerância de 0.011 para cobrir arredondamentos (0.72 vs 0.73)
                if abs(val_a - val_g) > 0.011:
                    match_numerico = False
                    break
            
            if match_numerico:
                return True

    # === MODO 2: Comparação de String (Fallback) ===
    # Se falhou numericamente ou não tem números (ex: "Hello World"), compara texto
    saida_aluno_norm = saida_aluno.strip().replace('\r\n', '\n')
    for opcao in opcoes_gabarito:
        opcao_norm = opcao.strip().replace('\r\n', '\n')
        if saida_aluno_norm == opcao_norm:
            return True
            
    return False

def testar(linguagem, comando, arquivo, casos, compilar=None):
    print(f"\n🔍 Testando {linguagem}: {arquivo}")

    # === FILTRO PEDAGÓGICO (Apenas Python) ===
    if linguagem == "Python" and USE_PEDAGOGIC_FILTER:
        if garantir_verificador():
            try:
                # O script retorna 0 se encontrar funções proibidas
                res = subprocess.run(["python3", "verificar_arquivo.py", arquivo], capture_output=True, text=True)
                if res.returncode == 0:
                    print(f"{RED}🛑 ERRO: Restrição Pedagógica Violada!{NC}")
                    print(f"{MAGENTA}{res.stdout}{NC}")
                    print(f"{YELLOW}Implemente a lógica manualmente conforme as regras do enunciado.{NC}")
                    return # Interrompe o teste
            except Exception as e:
                print(f"⚠️ Erro ao validar restrições: {e}")

    # === COMPILAÇÃO ===
    if compilar:
        try:
            subprocess.run(compilar, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            print(f"{RED}💥 Erro de compilação:{NC}")
            if e.stderr: print(e.stderr.decode('utf-8'))
            return

    # === EXECUÇÃO DOS CASOS ===
    acertos = 0
    total = len(casos)
    for nome, entrada, esperado_raw in casos:
        try:
            proc = subprocess.run(comando, input=entrada, capture_output=True, text=True, timeout=5)
            saida = proc.stdout.strip()
            
            if comparar_saidas(saida, esperado_raw):
                print(f"{GREEN}✔️ {nome}: OK{NC}")
                acertos += 1
            else:
                print(f"{RED}❌ {nome}: FALHOU{NC}")
                gabarito_visual = esperado_raw.split("\n<OU>\n")[0].strip().strip('"').strip("'")
                print(f"   📥 Entrada:\n{entrada}\n   🎯 Esperado:\n{gabarito_visual}\n   📤 Obtido:\n{saida}")
        except Exception as e: print(f"💥 {nome}: Erro - {e}")

    porcentagem = (acertos/total*100) if total > 0 else 0
    print(f"\n📊 Resultado: {acertos}/{total} ({porcentagem:.1f}%)")
    if acertos == total: print(f"{GREEN}🎉 Parabéns!{NC}")

def main():
    if len(sys.argv) < 2: return print("Uso: python testsuite.py EPx_y")
    nome = sys.argv[1]
    base = nome.rsplit('.', 1)[0] if '.' in nome else nome
    try: cap = base.split('_')[0][2:]; pasta = f"cap{cap}"
    except: return print("Nome inválido.")

    print(f"🎯 Testando {nome}...")
    if not baixar_dependencias(cap, pasta): return
    
    caminho = os.path.join(pasta, f"{base}.cases")
    casos = carregar_casos(caminho)
    if not casos: return

    linguagens = {
            ".py": ("Python", ["python3", f"{base}.py"], None),
            ".java":("Java", ["java", base], ["javac", f"{base}.java"]),
            ".js": ("Node", ["node", f"{base}.js"], None),
            ".c": ("C", [f"./{base}"], ["gcc", f"{base}.c", "-o", base, "-lm"]),
            ".cpp": ("C++", [f"./{base}"], ["g++", f"{base}.cpp", "-o", base]),
            ".r": ("R", ["Rscript", "--slave", f"{base}.r"], None)
        }
    
    alvos = [nome] if '.' in nome else [f"{base}{ext}" for ext in linguagens if os.path.exists(f"{base}{ext}")]
    if not alvos: return print(f"💥 Nenhum arquivo encontrado para {base}")

    for arq in alvos:
        ext = "." + arq.split(".")[-1]
        if ext in linguagens:
            l, c, cp = linguagens[ext]
            testar(l, c, arq, casos, cp)

if __name__ == "__main__":
    main()
