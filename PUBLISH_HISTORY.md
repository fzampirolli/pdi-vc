# Histórico de tempos de publish-parallel

Gerado a partir de `PUBLISH_HISTORY.csv` por `pipeline/publish_history.py`, chamado no final de `make publish-parallel`. Não é a tabela `tbl-00-tempos` do prefácio (`includes/prefacio*.qmd`) — essa é conteúdo do livro e é editada manualmente; esta aqui é só um log operacional.

"—" = combo não incluído nessa execução (ou paralelismo não calculável para execuções antigas, sem timestamps no `.rc`) · "FALHA" = incluído mas terminou com erro (não entra na média).

**Paralelismo médio/pico**: grau real de execução simultânea de combos durante o render, calculado a partir dos timestamps de início/fim de cada combo (sweep-line) — médio é ponderado no tempo, pico é o máximo de combos rodando ao mesmo tempo em algum instante.

**Soma dos combos (serial)**: soma do tempo de cada combo individualmente — quanto levaria rodando um de cada vez, sem paralelismo. É bem maior que "Render (parede)" porque a máquina roda vários combos ao mesmo tempo (ver CPU usada no README, § "Tempos de build").

| Data | Langs | Locales | py.pt | py.en | py.fr | py.es | py.it | cpp.pt | cpp.en | cpp.fr | cpp.es | cpp.it | Render (parede) | Total (c/ deploy) | Soma dos combos (serial) | Paralel. médio | Paralel. pico | Obs. |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-09-11 15:15 | py,cpp | pt,en,fr,es,it | 7m30s | 47m05s | 47m15s | 47m48s | 47m56s | 25m55s | 33m37s | 38m27s | 37m27s | 33m43s | 73m51s | 76m02s | 366m43s | 4.97x | 8x | publish completo (render all, PDF incl.) pós-fixes de prefácio; primeira entrada do histórico |
| 2026-09-20 18:03 | py,cpp | pt,en,fr,es,it | 7m28s | 31m06s | 31m08s | 31m20s | 31m20s | 25m54s | 34m12s | 37m51s | 37m27s | 34m35s | 63m45s | 71m31s | 302m21s | 4.74x | 8x |  |
| **Média (2 execuções)** |  |  | 7m29s | 39m06s | 39m12s | 39m34s | 39m38s | 25m54s | 33m54s | 38m09s | 37m27s | 34m09s | 68m48s | 73m46s | 334m32s | 4.86x | 8.0x |  |
