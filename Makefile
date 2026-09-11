# Makefile — PDI+VC  (atalhos de desenvolvimento)
# ─────────────────────────────────────────────────
# make build    → build único py+pt + HTML + índice + eps + moodle + sims
# make build-pdf→ build único py+pt + PDF + índice
# make build-all→ build único py+pt + HTML+PDF + índice
# make html     → watch py+pt, renderiza HTML ao salvar
# make pdf      → watch py+pt, renderiza PDF ao salvar
# make publish  → build + docs/ + git push
# make publish-parallel → render de TODOS os combos em paralelo + docs/ + git push
# make clean    → apaga gen/, docs/ e cache

LANGS   ?= py
LOCALES ?= pt

# ── Atalho de combo "lang.locale" (ex.: make build cpp.pt) ────────────────────
# Qualquer argumento extra no formato lang.locale (contém um ".") vira LANGS/
# LOCALES automaticamente, valendo pra qualquer target abaixo — equivalente a
# escrever LANGS=cpp LOCALES=pt na mão. Múltiplos combos (ex.: "cpp.pt py.en")
# combinam em produto cartesiano de LANGS×LOCALES (mesmo comportamento de
# LANGS=cpp,py LOCALES=pt,en — não são pares exatos); um único combo não tem
# essa ambiguidade.
empty :=
SPACE := $(empty) $(empty)
COMMA := ,
COMBO_GOALS := $(strip $(foreach g,$(MAKECMDGOALS),$(if $(findstring .,$(g)),$(g))))
ifneq ($(COMBO_GOALS),)
LANGS   := $(subst $(SPACE),$(COMMA),$(sort $(foreach c,$(COMBO_GOALS),$(firstword $(subst ., ,$(c))))))
LOCALES := $(subst $(SPACE),$(COMMA),$(sort $(foreach c,$(COMBO_GOALS),$(word 2,$(subst ., ,$(c))))))
$(COMBO_GOALS):
	@:
endif

PY      = python dev.py

# INC=1 → passa --incremental ao dev.py: capítulos cujo gen/ já está mais novo
# que a fonte + .EPs + morph.*/cache/pipeline (mtime) não são reprocessados.
# Combina com o `freeze: auto` do Quarto (só re-executa o que foi regenerado).
INCREMENTAL := $(if $(filter 1,$(INC)),--incremental,)

# TinyTeX na frente do PATH para garantir lualatex correto
TINYTEX = $(HOME)/.TinyTeX/bin/x86_64-linux
export PATH := $(TINYTEX):$(PATH)

# ── Watch (modo desenvolvimento) ──────────────────────────────────────────────
.PHONY: html
html: sync-morph
	$(PY) --once $(INCREMENTAL) --langs $(LANGS) --locales $(LOCALES) --render html
	$(MAKE) index

.PHONY: pdf
pdf: sync-morph
	$(PY) --once $(INCREMENTAL) --langs $(LANGS) --locales $(LOCALES) --render pdf

.PHONY: all-formats
all-formats: sync-morph
	$(PY) --langs $(LANGS) --locales $(LOCALES) --render all

# ── Build rápido de 1 capítulo ────────────────────────────────────────────────
# HTML do capítulo pedido (+ EPs dele, se existir) + notebook do aluno — sem
# tocar all/ (nenhum rename de pasta), sem apêndices e sem eps-all/moodle-all/
# sims-all/index (que varrem TODOS os capítulos de TODOS os combos já gerados
# em gen/book/, não só este). Uso:
#   make cap01 cpp.pt
#   make cap03            (usa LANGS/LOCALES default ou já setados)
cap%: sync-morph
	$(PY) --once $(INCREMENTAL) --langs $(LANGS) --locales $(LOCALES) --render html --no-apendices \
		all/cap$*/cap$*.ipynb \
		$(wildcard all/cap$*/cap$*.EPs.ipynb)
ifneq ($(FAST),1)
	python gerar_notebooks_alunos.py --batch references.bib --out-dir notebooks_alunos \
		--lang $(LANGS) --locale $(LOCALES) --cap cap$*
endif

# ── Build único ───────────────────────────────────────────────────────────────
.PHONY: build
build: sync-morph
	$(PY) --once $(INCREMENTAL) --langs $(LANGS) --locales $(LOCALES) --render html
	$(MAKE) index
	$(MAKE) eps-all
	$(MAKE) moodle-all
	$(MAKE) sims-all

.PHONY: build-index
build-index:
	$(MAKE) index
	
.PHONY: build-pdf
build-pdf: sync-morph
	$(PY) --once $(INCREMENTAL) --langs $(LANGS) --locales $(LOCALES) --render pdf
	$(MAKE) index

.PHONY: build-all
build-all: sync-morph
	$(PY) --once $(INCREMENTAL) --langs $(LANGS) --locales $(LOCALES) --render all
	$(MAKE) index

# ── Índice e abertura local ────────────────────────────────────────────────────
.PHONY: index
index:
	python -m pipeline.index_builder

.PHONY: open
open:
	open gen/book/index.html

# ── Combinações especiais ──────────────────────────────────────────────────────
.PHONY: full
full: sync-morph
	$(PY) --once --langs py,cpp,java,c --locales pt,en,fr,es,it --render all
	$(MAKE) index

# ── Publicação GitHub Pages ───────────────────────────────────────────────────
.PHONY: publish
publish:
	./publish_all.sh --langs $(LANGS) --locales $(LOCALES)

.PHONY: publish-fast
publish-fast:
	./publish_all.sh --langs $(LANGS) --locales $(LOCALES) --skip-render

# ── Publicação com render PARALELO de todos os combos ─────────────────────────
# Renderiza em 2 ONDAS: 1ª os combos .pt (aquecem o cache de tradução, que é
# locale-independente p/ código C++), 2ª os demais locales em paralelo. Evita a
# race de cache que quebra cpp.en/cpp.fr. Tempo ≈ (pior .pt) + (pior não-.pt).
#
#   make publish-parallel                 # padrão: py,cpp × pt,en,fr (livro inteiro)
#   make publish-parallel PUB_LANGS=cpp PUB_LOCALES=pt     # subconjunto
#   make publish-parallel cpp.pt py.en    # atalho lang.locale (produto cartesiano)
#   make publish-parallel JOBS=3          # no máx. 3 combos por vez (poupa RAM)
#   make publish-parallel NP=1            # gera gen/book/ + docs/ mas NÃO faz git push
#   make publish-parallel INC=1           # incremental (só re-renderiza o que mudou)
#
# Escopo por trilha (herdado do dev.py): py = cap01-09, cpp = só CPP_CHAPTERS
# (cap01-05 hoje) — em ambos com apêndices e PDF. Logs em gen/_publog/<combo>.log.
PUB_LANGS   ?= py,cpp
PUB_LOCALES ?= pt,en,fr
_PUB_LANGS   := $(if $(COMBO_GOALS),$(LANGS),$(PUB_LANGS))
_PUB_LOCALES := $(if $(COMBO_GOALS),$(LOCALES),$(PUB_LOCALES))

.PHONY: publish-parallel
publish-parallel: sync-morph
	@set -e; mkdir -p gen/_publog; T0=$$(date +%s); \
	all=$$(for L in $(subst $(COMMA),$(SPACE),$(_PUB_LANGS)); do \
	         for O in $(subst $(COMMA),$(SPACE),$(_PUB_LOCALES)); do echo $$L.$$O; done; \
	       done); \
	RUN1='c="{}"; L=$${c%.*}; O=$${c#*.}; s=$$(date +%s); \
	  python dev.py --once $(INCREMENTAL) --langs $$L --locales $$O --render all \
	    > gen/_publog/$$c.log 2>&1; \
	  rc=$$?; e=$$(date +%s); echo "$$rc $$((e-s)) $$s $$e" > gen/_publog/$$c.rc; \
	  [ $$rc = 0 ] && echo "  ✓ [$$(date +%H:%M:%S)] $$c ($$((e-s))s)" \
	              || echo "  ✗ [$$(date +%H:%M:%S)] $$c rc=$$rc ($$((e-s))s) gen/_publog/$$c.log"'; \
	w1=$$(printf '%s\n' $$all | grep -E "\.pt$$"  || true); \
	w2=$$(printf '%s\n' $$all | grep -Ev "\.pt$$" || true); \
	if [ -n "$$w1" ]; then echo ">> [$$(date +%H:%M:%S)] onda 1 (base .pt, aquece cache):" $$w1; \
	  printf '%s\n' $$w1 | xargs -P $(or $(JOBS),0) -I{} sh -c "$$RUN1"; fi; \
	if [ -n "$$w2" ]; then echo ">> [$$(date +%H:%M:%S)] onda 2 (demais locales):" $$w2; \
	  printf '%s\n' $$w2 | xargs -P $(or $(JOBS),0) -I{} sh -c "$$RUN1"; fi; \
	fail=0; echo ">> tempos por combo:"; \
	for c in $$all; do \
	  read rc dt s0 e0 < gen/_publog/$$c.rc 2>/dev/null || { rc=1; dt=0; }; \
	  printf '   %-8s %s  %ss\n' "$$c" "$$([ $$rc = 0 ] && echo OK || echo FALHA)" "$$dt"; \
	  [ "$$rc" = 0 ] || fail=1; done; \
	TR=$$(($$(date +%s)-T0)); echo ">> render total (parede): $$((TR/60))m$$((TR%60))s"; \
	if [ $$fail != 0 ]; then \
	  echo "!! combo(s) falharam — deploy abortado (logs em gen/_publog/)"; exit 1; fi; \
	echo ">> [$$(date +%H:%M:%S)] todos os combos OK — índice + deploy"; \
	./publish_all.sh --langs $(_PUB_LANGS) --locales $(_PUB_LOCALES) --skip-render \
	  $(if $(filter 1,$(NP)),--skip-git,); \
	TT=$$(($$(date +%s)-T0)); echo ">> [$$(date +%H:%M:%S)] publish-parallel completo: $$((TT/60))m$$((TT%60))s"; \
	python -m pipeline.publish_history --publog-dir gen/_publog \
	  --render-seconds $$TR --total-seconds $$TT \
	  --pub-langs "$(_PUB_LANGS)" --pub-locales "$(_PUB_LOCALES)"


# ── Publicação de notebook único ──────────────────────────────────────────────
.PHONY: render-single
render-single:
ifndef FILE
	$(error Use: make render-single FILE=meu_notebook.ipynb)
endif
	./publish_single.sh $(FILE) --lang $(LANGS) --locale $(LOCALES) --skip-git

.PHONY: publish-single
publish-single:
ifndef FILE
	$(error Use: make publish-single FILE=meu_notebook.ipynb)
endif
	./publish_single.sh $(FILE) --lang $(LANGS) --locale $(LOCALES)

# ── Limpeza ───────────────────────────────────────────────────────────────────
.PHONY: clean
clean:
	rm -rf gen/ docs/ .cache/

.PHONY: clean-cache
clean-cache:
	rm -f .cache/translations.json

.PHONY: clean-gen
clean-gen:
	rm -rf gen/ docs/

# ── Notebooks para alunos ─────────────────────────────────────────────────────
.PHONY: alunos
alunos:
	python gerar_notebooks_alunos.py --batch references.bib --out-dir notebooks_alunos

.PHONY: alunos-no-numbering
alunos-no-numbering:
	python gerar_notebooks_alunos.py --batch references.bib --out-dir notebooks_alunos --no-numbering

.PHONY: epub
epub:
	python gerar_notebooks_alunos.py --epub references.bib --out-dir notebooks_epub


# ── Extração de EPs ───────────────────────────────────────────────────────────

BASE_URL ?= https://fzampirolli.github.io/pdi-vc/eps/$(LANGS).$(LOCALES)

.PHONY: eps
eps:
	python ep_tools.py extrair --input gen/book/$(LOCALES:%=$(LANGS).%) 2>/dev/null || \
	python ep_tools.py extrair --input gen/book

.PHONY: eps-all
eps-all:
	python ep_tools.py extrair --input gen/book

.PHONY: eps-dry
eps-dry:
	python ep_tools.py extrair --input gen/book --dry-run

# ── Conversão para Moodle ─────────────────────────────────────────────────────

.PHONY: moodle
moodle:
	python ep_tools.py limpar \
		gen/book/eps/$(LANGS).$(LOCALES) \
		gen/book/eps/$(LANGS).$(LOCALES)_moodle \
		--base-url "$(BASE_URL)"

.PHONY: moodle-all
moodle-all:
	@for lang in $$(echo "$(LANGS)" | tr ',' ' '); do \
		for locale in $$(echo "$(LOCALES)" | tr ',' ' '); do \
			in_dir="gen/book/eps/$$lang.$$locale"; \
			if [ ! -d "$$in_dir" ]; then \
				echo "⏭  moodle-all: pulando $$in_dir (não existe)"; \
				continue; \
			fi; \
			python ep_tools.py limpar \
				"$$in_dir" \
				"gen/book/eps/$$lang.$${locale}_moodle" \
				--base-url "https://fzampirolli.github.io/pdi-vc/eps/$$lang.$$locale"; \
		done; \
	done

# ── Extração de Simuladores ──────────────────────────────────────────────────

.PHONY: sims
sims:
	python sim_tools.py extrair --input gen/book/$(LANGS).$(LOCALES)

.PHONY: sims-all
sims-all:
	python sim_tools.py extrair --input gen/book

.PHONY: sims-dry
sims-dry:
	python sim_tools.py extrair --input gen/book --dry-run


# ── Checks de consistência entre combos ──────────────────────────────────────
# check-combos        → os dois checks (usa CPP_CHAPTERS por padrão)
# check-combos-locale → só estrutura pt vs en vs fr (mesma linguagem)
# check-combos-parity → só py vs cpp (mesmo idioma, pt): labels e refs
# Falha (exit != 0) se alguma inconsistência estrutural for encontrada.
# Ex.: make check-combos CHAPTERS=cap01,cap02   LOCALE=pt

CHAPTERS ?=
LOCALE   ?= pt

# ── Sincroniza morph.py / morph.hpp / stb_image*.h da árvore de trabalho ──────
# para as CÓPIAS LOCAIS ao lado das fontes (all/capNN/). Essas cópias são
# gitignoradas e o `config.setup` só as baixa do GitHub master `if not exists`,
# nunca as atualiza — então, ao editar morph/* e rodar um notebook de all/
# direto no Jupyter (ou compilar um %%writefile .cpp na mão), usa-se a versão
# defasada. O build do pipeline (make html) não sofre disso: ele faz symlink
# da morph/* viva. Rode isto após mexer em morph/*, e reinicie o kernel.
.PHONY: sync-morph
sync-morph:
	@python -c "import shutil, pathlib; \
from pipeline.config import CPP_CHAPTERS; \
root = pathlib.Path('.'); \
caps = sorted(p.name for p in (root/'all').glob('cap*') if p.is_dir()); \
[shutil.copy2(root/'morph'/'morph.py', root/'all'/c/'morph.py') for c in caps]; \
[shutil.copy2(root/'morph'/'cpp'/f, root/'all'/c/f) \
   for c in caps if c in CPP_CHAPTERS \
   for f in ('morph.hpp','stb_image.h','stb_image_write.h') \
   if (root/'morph'/'cpp'/f).exists()]; \
print('sync-morph: morph.py ->', caps); \
print('sync-morph: morph.hpp+stb ->', [c for c in caps if c in CPP_CHAPTERS])"

.PHONY: check-combos
check-combos: sync-morph
	python check_combos.py $(if $(CHAPTERS),--chapters $(CHAPTERS),) --locale $(LOCALE)

.PHONY: check-combos-locale
check-combos-locale: sync-morph
	python check_combos.py --locale-consistency $(if $(CHAPTERS),--chapters $(CHAPTERS),)

.PHONY: check-combos-parity
check-combos-parity: sync-morph
	python check_combos.py --lang-parity --locale $(LOCALE) $(if $(CHAPTERS),--chapters $(CHAPTERS),)

# ── Preflight OPCIONAL: executa as fontes all/capNN/*.ipynb (menos cap09) ──────
# numa cópia temporária, com morph* da árvore de trabalho, e falha se alguma
# célula quebrar — pega o "esqueci de rodar uma célula". NÃO é pré-requisito de
# build (é pesado: executa cap01..cap08); rode sob demanda antes de publicar,
# de preferência filtrando: `make check-notebooks CHAPTERS=cap02`.
# Não escreve outputs de volta. Rode DENTRO do .venv (morph.py é 3.11+).
.PHONY: check-notebooks
check-notebooks: sync-morph
	python check_notebooks.py $(if $(CHAPTERS),--chapters $(CHAPTERS),) $(NBCHECK_ARGS)


# ── Ajuda ─────────────────────────────────────────────────────────────────────
.PHONY: help
help:
	@echo ""
	@echo "  📚 Build:"
	@echo "  make build         → py×pt + HTML + índice + eps + moodle + sims"
	@echo "  make build-index   → py×pt + índice"
	@echo "  make build-pdf     → py×pt + PDF + índice"
	@echo "  make build-all     → py×pt + HTML+PDF + índice"
	@echo "  make full          → todas linguagens×idiomas + HTML+PDF"
	@echo "  INC=1 make build …  → pula capítulos cujo gen/ já está atualizado (mtime); casa com o freeze do Quarto"
	@echo ""
	@echo "  👀 Watch (Ctrl+C para sair):"
	@echo "  make html          → watch + HTML"
	@echo "  make pdf           → watch + PDF"
	@echo "  make all-formats   → watch + HTML+PDF"
	@echo ""
	@echo "  🌐 Publicação:"
	@echo "  make publish       → build + docs/ + git push"
	@echo "  make publish-fast  → deploy para docs/ + git push (sem recompilar HTML/PDF)"
	@echo "  make publish-parallel → render de TODOS os combos EM PARALELO (py,cpp × pt,en,fr) + HTML+PDF + índice + docs/ + git push"
	@echo "     opções: PUB_LANGS=cpp PUB_LOCALES=pt (subconjunto) · JOBS=3 (limita combos simultâneos) · NP=1 (sem git push) · INC=1 (incremental)"
	@echo "     escopo: py = cap01-09 · cpp = só CPP_CHAPTERS (cap01-05) · logs em gen/_publog/<combo>.log"
	@echo "  make index         → só regenera o índice"
	@echo "  make open          → abre gen/book/index.html"
	@echo ""
	@echo "  make render-single FILE=all/cap01/cap01.ipynb  → renderiza HTML sem publicar"
	@echo "  make publish-single FILE=all/cap01/cap01.ipynb → HTML + git push do arquivo"
	@echo "  make render-single FILE=all/apendices/apendice_f/apendice_f.ipynb → idem, para apêndice"
	@echo ""
	@echo "  ✅ Checks (exit != 0 se inconsistente):"
	@echo "  make check-combos          → estrutura pt/en/fr + paridade py/cpp"
	@echo "  make check-combos-locale   → só estrutura pt vs en vs fr (mesma linguagem)"
	@echo "  make check-combos-parity   → só py vs cpp (labels, refs, xrefs)"
	@echo "  make check-notebooks CHAPTERS=cap02 → (opcional, pesado) executa as fontes e falha se célula quebrar"
	@echo "  make sync-morph            → copia morph.py/hpp da árvore de trabalho p/ all/cap*/ (roda antes de build/html/checks)"
	@echo "     opções: CHAPTERS=cap01,cap02  LOCALE=pt"
	@echo ""
	@echo "  🧹 Limpeza:"
	@echo "  make clean         → apaga gen/, docs/ e .cache/"
	@echo "  make clean-cache   → apaga só .cache/"
	@echo "  make clean-gen     → apaga gen/ e docs/"
	@echo ""
	@echo "  🎓 EPs e Moodle:"
	@echo "  make eps           → extrai EPs do locale atual (gen/book/eps/py.pt/)"
	@echo "  make eps-all       → extrai EPs de todos os locales"
	@echo "  make eps-dry       → lista EPs sem gravar"
	@echo "  make moodle        → converte EPs para Moodle + banner de link"
	@echo "  make moodle-all    → converte todos os locales para Moodle"
	@echo ""
	@echo "  🎮 Simuladores:"
	@echo "  make sims          → extrai simuladores do locale atual (gen/book/simuladores/py.pt/)"
	@echo "  make sims-all      → extrai simuladores de todos os locales"
	@echo "  make sims-dry      → lista simuladores encontrados sem gravar"
	@echo ""
	@echo "  💡 Overrides: make build LANGS=cpp LOCALES=en"
	@echo "                make moodle BASE_URL=https://meusite.com/eps/py.en"
	@echo "  💡 Atalho:    make build cpp.pt   (== LANGS=cpp LOCALES=pt)"
	@echo "                make html cpp.pt"
	@echo ""
	@echo "  ⚡ Build de 1 capítulo (rápido, sem eps/moodle/sims/index):"
	@echo "  make cap01 cpp.pt        → só HTML do cap01 (+ EPs + caderno do aluno)"
	@echo "  FAST=1 make cap01 cpp.pt → idem, pulando o caderno do aluno (iteração)"
	@echo "  (freeze: auto — capítulos não alterados restauram do gen/quarto/<combo>/_freeze/;"
	@echo "   PDI_VC_NO_FREEZE=1 desliga; mexer em morph.* invalida o _freeze automaticamente)"
