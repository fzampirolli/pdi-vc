# Makefile — PDI+VC  (atalhos de desenvolvimento)
# ─────────────────────────────────────────────────
# make build    → build único py+pt + HTML + índice
# make build-pdf→ build único py+pt + PDF + índice
# make build-all→ build único py+pt + HTML+PDF + índice
# make html     → watch py+pt, renderiza HTML ao salvar
# make pdf      → watch py+pt, renderiza PDF ao salvar
# make publish  → build + docs/ + git push
# make clean    → apaga gen/, docs/ e cache

LANGS   ?= py
LOCALES ?= pt

PY      = python dev.py

# ── Watch (modo desenvolvimento) ──────────────────────────────────────────────
.PHONY: html
html:
	$(PY) --langs $(LANGS) --locales $(LOCALES) --render html

.PHONY: pdf
pdf:
	$(PY) --langs $(LANGS) --locales $(LOCALES) --render pdf

.PHONY: all-formats
all-formats:
	$(PY) --langs $(LANGS) --locales $(LOCALES) --render all

# ── Build único ───────────────────────────────────────────────────────────────
.PHONY: build
build:
	$(PY) --once --langs $(LANGS) --locales $(LOCALES) --render html
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

.PHONY: epub
epub:
	python gerar_notebooks_alunos.py --epub references.bib --out-dir notebooks_epub

# ── Ajuda ─────────────────────────────────────────────────────────────────────
.PHONY: help
help:
	@echo ""
	@echo "  📚 Build:"
	@echo "  make build         → py×pt + HTML + índice"
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
	@echo "  make index         → só regenera o índice"
	@echo "  make open          → abre gen/book/index.html"
	@echo ""
	@echo "  🧹 Limpeza:"
	@echo "  make clean         → apaga gen/, docs/ e .cache/"
	@echo "  make clean-cache   → apaga só .cache/"
	@echo "  make clean-gen     → apaga gen/ e docs/"
	@echo ""
	@echo "  💡 Overrides: make build LANGS=cpp LOCALES=en"
	@echo ""