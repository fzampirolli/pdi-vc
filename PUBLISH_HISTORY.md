# Histórico de tempos de publish-parallel

Gerado a partir de `PUBLISH_HISTORY.csv` por `pipeline/publish_history.py`, chamado no final de `make publish-parallel`. Não é a tabela `tbl-00-tempos` do prefácio (`includes/prefacio*.qmd`) — essa é conteúdo do livro e é editada manualmente; esta aqui é só um log operacional.

"—" = combo não incluído nessa execução (ou paralelismo não calculável para execuções antigas, sem timestamps no `.rc`) · "FALHA" = incluído mas terminou com erro (não entra na média).

**Paralelismo médio/pico**: grau real de execução simultânea de combos durante o render, calculado a partir dos timestamps de início/fim de cada combo (sweep-line) — médio é ponderado no tempo, pico é o máximo de combos rodando ao mesmo tempo em algum instante.

| Data | Langs | Locales | py.pt | py.en | py.fr | py.es | py.it | cpp.pt | cpp.en | cpp.fr | cpp.es | cpp.it | Render (parede) | Total (c/ deploy) | Paralel. médio | Paralel. pico | Obs. |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-09-11 15:15 | py,cpp | pt,en,fr,es,it | 7m30s | 47m05s | 47m15s | 47m48s | 47m56s | 25m55s | 33m37s | 38m27s | 37m27s | 33m43s | 73m51s | 76m02s | 4.97x | 8x | publish completo (render all, PDF incl.) pós-fixes de prefácio; primeira entrada do histórico |
| **Média (1 execuções)** |  |  | 7m30s | 47m05s | 47m15s | 47m48s | 47m56s | 25m55s | 33m37s | 38m27s | 37m27s | 33m43s | 73m51s | 76m02s | 4.97x | 8.0x |  |
