# Persistência de dados em produção — melhorias futuras

> Contexto: item deixado de fora da implementação
> `docs/implementations/aviso-startup-crm-db-path-ausente.md` (já graduada —
> ver [`docs/architecture/_mapa-sistema.md`](../architecture/_mapa-sistema.md#persistência-em-produção-railway)).

## M1 — Checagem de arranque também no backend-core (DATABASE_URL)

**Prioridade: BAIXA**

O `backend-crm` passou a recusar o arranque em produção se `CRM_DB_PATH`
não estiver definida (`backend-crm/database.py`), evitando que a mesma
classe de bug (perda silenciosa de dados por falta de persistência) se
repita sem nenhum aviso.

O `backend-core` (`app/config.py`/`app/db.py`, `DATABASE_URL`) sofre do
mesmo risco estrutural — hoje está correto em produção
(`DATABASE_URL=sqlite:////data/core.db`, confirmado directamente via
`railway variable list --service backend-core`), mas se essa variável for
removida ou esquecida no futuro (Railway dashboard, novo ambiente clonado,
etc.), o serviço voltaria a persistir num caminho efémero sem nenhum sinal.

Aplicar o mesmo padrão: checagem no arranque que recusa subir se
`RAILWAY_ENVIRONMENT` estiver definida e `DATABASE_URL` não apontar para
dentro do volume (`backend-core-volume`, montado em `/data`).
