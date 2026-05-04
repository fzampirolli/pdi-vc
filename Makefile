# Makefile — PDI+VC  (atalhos de desenvolvimento)
# ─────────────────────────────────────────────────
# make          → watch py+pt, sem render (só notebooks)
# make html     → watch py+pt, renderiza HTML ao salvar
# make pdf      → watch py+pt, renderiza PDF ao salvar
# make build    → build único py+pt + HTML
# make all-langs→ build único todas as linguagens × pt, HTML
# make clean    → apaga gen/ e cache

# Makefile — PDI+VC (corrigido)

LANGS   ?= py
LOCALES ?= pt
RENDER  ?=
DRY     ?=

PY      = python dev.py

# ── Watch + render ────────────────────────────────────────────────────────────
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

.PHONY: build-pdf
build-pdf:
	$(PY) --once --langs $(LANGS) --locales $(LOCALES) --render pdf

.PHONY: build-all
build-all:
	$(PY) --once --langs $(LANGS) --locales $(LOCALES) --render all

# ── Combinações especiais ──────────────────────────────────────────────────────
.PHONY: full
full:
	$(PY) --once --langs py,cpp,java,c --locales pt,en,fr,es,it --render all


# Adicione ou corrija estes targets no Makefile

.PHONY: index
index:
	python -m pipeline.index_builder

.PHONY: open
open:
	open gen/index.html

# Corrigir o build para gerar índice
build:
	$(PY) --once --langs $(LANGS) --locales $(LOCALES) --render html
	$(MAKE) index

build-pdf:
	$(PY) --once --langs $(LANGS) --locales $(LOCALES) --render pdf
	$(MAKE) index

build-all:
	$(PY) --once --langs $(LANGS) --locales $(LOCALES) --render all
	$(MAKE) index

# ── Ajuda ─────────────────────────────────────────────────────────────────────
.PHONY: help
help:
	@echo ""
	@echo "  📚 Geração de conteúdo:"
	@echo "  make build       → py×pt + HTML"
	@echo "  make build-pdf   → py×pt + PDF"
	@echo "  make build-all   → py×pt + HTML + PDF"
	@echo "  make full        → todas linguagens×idiomas + HTML+PDF"
	@echo ""
	@echo "  👀 Modo watch (auto-rebuild ao salvar):"
	@echo "  make html        → watch + HTML"
	@echo "  make pdf         → watch + PDF"
	@echo "  make all-formats → watch + HTML+PDF"
	@echo ""
	@echo "  💡 Overrides: make build-pdf LANGS=cpp LOCALES=en"
	@echo ""