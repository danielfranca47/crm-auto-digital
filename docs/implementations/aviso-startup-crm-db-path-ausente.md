# Aviso no arranque se CRM_DB_PATH estiver ausente em produção

**Branch:** `main`
**Status:** Em andamento

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`docs/implementations/persistencia-banco-dados-producao.md` (feature já
graduada — ver [`docs/architecture/_mapa-sistema.md`](../architecture/_mapa-sistema.md#persistência-em-produção-railway)).

O `backend-crm` corrigiu a perda de dados em produção ao passar a ler
`CRM_DB_PATH` do ambiente (com fallback para um caminho relativo local,
efémero em produção). O código está correto e a env var está configurada em
produção, mas **nada avisa se essa configuração for removida ou esquecida no
futuro** (ex.: apagada por engano no Railway, ou um novo ambiente/serviço
clonado sem copiar as variáveis) — o sistema simplesmente volta a usar o
caminho efémero em silêncio, exatamente a mesma classe de bug que já causou
perda real de leads em produção, sem nenhum sinal nos logs até alguém notar
dados a desaparecer.

Utilizador validou como item urgente (não-backlog) após a correção do bug
original, para fechar essa lacuna enquanto o contexto ainda está fresco.

---

## Problemas Identificados (estado anterior)

1. **Sem sinal no arranque:** `backend-crm/database.py` — se `CRM_DB_PATH`
   não estiver definida, o código cai silenciosamente no caminho relativo
   local, sem log de aviso, mesmo quando a aplicação está a correr num
   ambiente de produção (Railway injeta `RAILWAY_ENVIRONMENT` — sinal
   disponível para detectar o cenário).

---

## Abordagem

Utilizador optou, quando questionado directamente sobre o trade-off, pela
opção mais protetora: **recusar o arranque** (não só logar) se
`CRM_DB_PATH` faltar em produção — aceitando que um ambiente Railway
legitimamente sem persistência também falharia ao subir nessas condições,
a menos que `CRM_DB_PATH` seja definida explicitamente para ele também.

Checagem a nível de módulo em `backend-crm/database.py`, logo após
`DB_PATH`/`DB_DIR` (mesmo bloco do comentário de aviso já adicionado nesta
sessão) — corre uma única vez, no import, equivalente a "no arranque do
processo":

```python
if os.environ.get("RAILWAY_ENVIRONMENT") and not os.environ.get("CRM_DB_PATH"):
    raise RuntimeError(
        "CRM_DB_PATH não está definida em produção "
        f"(RAILWAY_ENVIRONMENT={os.environ.get('RAILWAY_ENVIRONMENT')!r}). "
        "O banco de dados dos leads NÃO persiste entre deploys/restarts sem "
        "isso — defina CRM_DB_PATH apontando para o volume persistente do "
        "serviço (ex.: /data/crm.db). Ver docs/architecture/_mapa-sistema.md, "
        "secção 'Persistência em produção'."
    )
```

`RAILWAY_ENVIRONMENT` confirmado como o sinal correto (visto directamente
via `railway variable list --service backend-crm` nesta sessão:
`RAILWAY_ENVIRONMENT=production`). Localmente essa variável não existe,
então o dev local fica inalterado. `app.py` importa `from database import
init_db` logo no arranque — se o `raise` disparar, a importação falha, o
`uvicorn` não sobe, e a Railway marca o deploy como falhado com esta
mensagem nos logs.

**Fora do escopo desta fase:** aplicar o mesmo raciocínio ao `backend-core`
(`DATABASE_URL`) — já está configurado corretamente hoje (verificado nesta
sessão), então não é urgente; fica como possível próximo item, não faz
parte desta fase para manter o escopo focado no que já está mapeado.

---

## Plano de Implementação

### Fase 1 — Recusar arranque se CRM_DB_PATH faltar em produção

**Objetivo:** impedir que a mesma classe de bug (perda silenciosa de dados)
se repita sem nenhum sinal.

| Arquivo | O que muda |
|---|---|
| `backend-crm/database.py` | Nova checagem a nível de módulo, logo após `DB_PATH`/`DB_DIR`: `raise RuntimeError(...)` se `RAILWAY_ENVIRONMENT` estiver definida e `CRM_DB_PATH` não estiver |
