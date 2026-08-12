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

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `fe9662c` | backend: checagem de arranque — recusa subir sem `CRM_DB_PATH` em produção |

**Detalhes do commit `fe9662c`:**
- `backend-crm/database.py` — `raise RuntimeError(...)` a nível de módulo, logo após `DB_PATH`/`DB_DIR`, se `RAILWAY_ENVIRONMENT` estiver definida e `CRM_DB_PATH` não

### Relatório da Fase 1 — o que mudou na prática

**Antes:** se a variável `CRM_DB_PATH` fosse removida ou esquecida em
produção, o sistema simplesmente voltava a guardar os dados num lugar
temporário, sem avisar nada — o mesmo problema que já causou perda real de
leads podia acontecer de novo, em silêncio.

**Agora:** nessas condições, o `backend-crm` **recusa-se a ligar** — o
deploy falha de forma clara e visível nos registos do Railway, explicando
exatamente o que está errado e como corrigir. Não há mais como isso
acontecer sem ninguém notar.

**Para validar:** Cenários P1, P2 e P3, na seção "Checks de Validação"
abaixo — já executados por mim nesta sessão.

---

## Checks de Validação

### Cenário P1 — Comportamento local inalterado (regressão)
- [x] (2026-08-12) Sem `RAILWAY_ENVIRONMENT` nem `CRM_DB_PATH` definidas: `import database` funciona normalmente, `DB_PATH` resolve para o caminho padrão local (igual a antes)

### Cenário P2 — Recusa de arranque em produção sem CRM_DB_PATH (novo comportamento)
- [x] (2026-08-12) Com `RAILWAY_ENVIRONMENT=test` e sem `CRM_DB_PATH`: `import database` levanta `RuntimeError` imediatamente, com mensagem clara explicando o problema e a correção

### Cenário P3 — Não interfere quando CRM_DB_PATH está definida (regressão)
- [x] (2026-08-12) Com `RAILWAY_ENVIRONMENT=test` e `CRM_DB_PATH` definida: `import database` funciona normalmente, `DB_PATH` resolve para o caminho indicado
- [x] (2026-08-12) Suite de testes existente (`test_leads_company_or_contact_migration`, `test_meeting_management_gate`, `test_inbound_orchestrator_flag`) — mesmos resultados de antes (2 erros pré-existentes de limpeza de pasta temporária no Windows, já confirmados não relacionados a esta mudança)

> Não é preciso testar em produção diretamente: a variável `CRM_DB_PATH` já
> está definida lá (confirmado nesta sessão), então o próximo deploy com
> este commit simplesmente não deve disparar o `RuntimeError` — o deploy
> subir normalmente já é a confirmação de que não há falso positivo.
