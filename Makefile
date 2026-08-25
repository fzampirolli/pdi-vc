# Makefile — PDI+VC  (atalhos de desenvolvimento)
# ─────────────────────────────────────────────────
# make build    → build único py+pt + HTML + índice + eps + moodle + sims
# make build-pdf→ build único py+pt + PDF + índice
# make build-all→ build único py+pt + HTML+PDF + índice
# make html     → watch py+pt, renderiza HTML ao salvar
# make pdf      → watch py+pt, renderiza PDF ao salvar
# make publish  → build + docs/ + git push
# make clean    → apaga gen/, docs/ e cache

LANGS   ?= py
LOCALES ?= pt

PY      = python dev.py

# TinyTeX na frente do PATH para garantir lualatex correto
TINYTEX = $(HOME)/.TinyTeX/bin/x86_64-linux
export PATH := $(TINYTEX):$(PATH)

# ── Watch (modo desenvolvimento) ──────────────────────────────────────────────
.PHONY: html
html:
	$(PY) --once --langs $(LANGS) --locales $(LOCALES) --render html
	$(MAKE) index

.PHONY: pdf
pdf:
	$(PY) --once --langs $(LANGS) --locales $(LOCALES) --render pdf

.PHONY: all-formats
all-formats:
	$(PY) --langs $(LANGS) --locales $(LOCALES) --render all

# ── Build único ───────────────────────────────────────────────────────────────
.PHONY: build
build:
	$(PY) --once --langs $(LANGS) --locales $(LOCALES) --render html
	$(MAKE) index
	$(MAKE) eps-all
	$(MAKE) moodle-all
	$(MAKE) sims-all

.PHONY: build-index
build-index:
	$(MAKE) index
	
.PHONY: build-pdf
build-pdf:
	$(PY) --once --langs $(LANGS) --locales $(LOCALES) --render pdf
	$(MAKE) index

.PHONY: build-all
build-all:
	$(PY) --once --langs $(LANGS) --locales $(LOCALES) --render all
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
full:
	$(PY) --once --langs py,cpp,java,c --locales pt,en,fr,es,it --render all
	$(MAKE) index

# ── Publicação GitHub Pages ───────────────────────────────────────────────────
.PHONY: publish
publish:
	./publish_all.sh --langs $(LANGS) --locales $(LOCALES)

.PHONY: publish-fast
publish-fast:
	./publish_all.sh --langs $(LANGS) --locales $(LOCALES) --skip-render


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

BASE_URL ?= https://fzampirolli.github.io/pdi-vc/eps/py.$(LOCALES)

.PHONY: eps
eps:
	python ep_tools.py extrair --input gen/book/$(LOCALES:%=py.%) 2>/dev/null || \
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
		gen/book/eps/py.$(LOCALES) \
		gen/book/eps/py.$(LOCALES)_moodle \
		--base-url "$(BASE_URL)"

.PHONY: moodle-all
moodle-all:
	@for locale in $$(echo "$(LOCALES)" | tr ',' ' '); do \
		python ep_tools.py limpar \
			gen/book/eps/py.$$locale \
			gen/book/eps/py.$${locale}_moodle \
			--base-url "https://fzampirolli.github.io/pdi-vc/eps/py.$$locale"; \
	done

# ── Extração de Simuladores ──────────────────────────────────────────────────

.PHONY: sims
sims:
	python sim_tools.py extrair --input gen/book/py.$(LOCALES)

.PHONY: sims-all
sims-all:
	python sim_tools.py extrair --input gen/book

.PHONY: sims-dry
sims-dry:
	python sim_tools.py extrair --input gen/book --dry-run

    
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
	@echo ""
	@echo "  👀 Watch (Ctrl+C para sair):"
	@echo "  make html          → watch + HTML"
	@echo "  make pdf           → watch + PDF"
	@echo "  make all-formats   → watch + HTML+PDF"
	@echo ""
	@echo "  🌐 Publicação:"
	@echo "  make publish       → build + docs/ + git push"
	@echo "  make publish-fast  → deploy para docs/ + git push (sem recompilar HTML/PDF)"
	@echo "  make index         → só regenera o índice"
	@echo "  make open          → abre gen/book/index.html"
	@echo ""
	@echo "  make render-single FILE=all/cap01/cap01.ipynb  → renderiza HTML sem publicar"
	@echo "  make publish-single FILE=all/cap01/cap01.ipynb → HTML + git push do arquivo"
	@echo "  make render-single FILE=all/apendices/apendice_f/apendice_f.ipynb → idem, para apêndice"
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
