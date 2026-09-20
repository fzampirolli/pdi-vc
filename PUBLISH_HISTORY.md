# Histórico de tempos de publish-parallel

Gerado a partir de `PUBLISH_HISTORY.csv` por `pipeline/publish_history.py`, chamado no final de `make publish-parallel`. Não é a tabela `tbl-00-tempos` do prefácio (`includes/prefacio*.qmd`) — essa é conteúdo do livro e é editada manualmente; esta aqui é só um log operacional.

"—" = combo não incluído nessa execução (ou paralelismo não calculável para execuções antigas, sem timestamps no `.rc`) · "FALHA" = incluído mas terminou com erro (não entra na média).

**Paralelismo médio/pico**: grau real de execução simultânea de combos durante o render, calculado a partir dos timestamps de início/fim de cada combo (sweep-line) — médio é ponderado no tempo, pico é o máximo de combos rodando ao mesmo tempo em algum instante.

**Soma dos combos (serial)**: soma do tempo de cada combo individualmente — quanto levaria rodando um de cada vez, sem paralelismo. É bem maior que "Render (parede)" porque a máquina roda vários combos ao mesmo tempo (ver CPU usada no README, § "Tempos de build").

| Data | Langs | Locales | py.pt | py.en | py.fr | py.es | py.it | cpp.pt | cpp.en | cpp.fr | cpp.es | cpp.it | Render (parede) | Total (c/ deploy) | Soma dos combos (serial) | Paralel. médio | Paralel. pico | Obs. |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-09-11 15:15 | py,cpp | pt,en,fr,es,it | 7m30s | 47m05s | 47m15s | 47m48s | 47m56s | 25m55s | 33m37s | 38m27s | 37m27s | 33m43s | 73m51s | 76m02s | 366m43s | 4.97x | 8x | publish completo (render all, PDF incl.) pós-fixes de prefácio; primeira entrada do histórico |
| 2026-09-20 18:03 | py,cpp | pt,en,fr,es,it | 7m28s | 31m06s | 31m08s | 31m20s | 31m20s | 25m54s | 34m12s | 37m51s | 37m27s | 34m35s | 63m45s | 71m31s | 302m21s | 4.74x | 8x |  |
| 2026-09-20 19:36 | py,cpp | pt,en,fr,es,it | 7m29s | 49m02s | 49m21s | 50m21s | 50m18s | 25m57s | 34m53s | 39m27s | 38m52s | 35m35s | 76m18s | 89m43s | 381m15s | 5.00x | 8x |  |
| **Média (3 execuções)** |  |  | 7m29s | 42m24s | 42m35s | 43m10s | 43m11s | 25m55s | 34m14s | 38m35s | 37m55s | 34m38s | 71m18s | 79m05s | 350m06s | 4.90x | 8.0x |  |
