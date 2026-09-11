# Histórico de tempos de publish-parallel

Gerado a partir de `PUBLISH_HISTORY.csv` por `pipeline/publish_history.py`, chamado no final de `make publish-parallel`. Não é a tabela `tbl-00-tempos` do prefácio (`includes/prefacio*.qmd`) — essa é conteúdo do livro e é editada manualmente; esta aqui é só um log operacional.

"—" = combo não incluído nessa execução · "FALHA" = incluído mas terminou com erro (não entra na média).

| Data | Langs | Locales | py.pt | py.en | py.fr | py.es | py.it | cpp.pt | cpp.en | cpp.fr | cpp.es | cpp.it | Render (parede) | Total (c/ deploy) | Obs. |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-09-11 13:03 | py,cpp | pt,en,fr,es,it | 7m30s | 47m05s | 47m15s | 47m48s | 47m56s | 25m55s | 33m37s | 38m27s | 37m27s | 33m43s | 73m51s | 76m02s | publish completo (render all, PDF incl.) pós-fixes de prefácio; primeira entrada do histórico |
| **Média (1 execuções)** |  |  | 7m30s | 47m05s | 47m15s | 47m48s | 47m56s | 25m55s | 33m37s | 38m27s | 37m27s | 33m43s | 73m51s | 76m02s |  |
