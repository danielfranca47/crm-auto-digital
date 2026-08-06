# Ingestão de conhecimento — limite de lotes por semana/plano

**Branch:** `feat/ajuste-configuracao-ai-profile`
**Status:** Em andamento

---

## Motivação

O único limite em `POST /api/knowledge/ingest` (`backend-crm/routes/knowledge_ingest.py`) é
estrutural — 6 fontes por lote, 1 job ativo por utilizador por vez (409 se já houver um em
andamento) — não há limite de **quantos lotes por semana** um utilizador pode disparar. Cada
lote pode envolver várias chamadas a `gpt-4o-mini` (vision por imagem + classificação), custando
dinheiro sem controle por plano.

Decisão tomada no planeamento: o limite é **semanal**, não diário/mensal — ingestão de
conhecimento é uma tarefa de configuração pontual, não uso intenso do dia a dia. Esse conceito
de "semana" ainda não existe no sistema (só há padrões diário e mensal em
`services/rate_limit_service.py`) e precisou ser introduzido.

---

## Problemas Identificados (estado anterior)

1. **Sem gate de plano:** `routes/knowledge_ingest.py:create_ingest_batch()` não chama nenhuma
   função de gate antes de criar o job.
2. **Sem campo de limite nos planos:** `entitlements["limits"]` não tem uma entrada equivalente a
   `knowledge_ingest_weekly_limit`.
3. **Sem conceito de "semana" em `rate_limit_service.py`:** só existem helpers para janela diária
   (`_count_jobs_for_today`, `_get_daily_usage`) e mensal (`_get_monthly_usage`).

---

## Abordagem

Reaproveitar o padrão já existente de contagem de jobs por tipo (usado por
`max_maps_search_daily`, `max_whatsapp_send_daily` etc. via `LIMIT_KEYS_BY_TYPE` +
`_count_jobs_for_today`), mas com janela semanal (segunda a hoje, UTC) em vez de diária —
contando direto na tabela `jobs`, sem tabela de uso nova, já que cada lote de ingestão grava um
job em `TYPE_KNOWLEDGE_INGEST`.

```
POST /api/knowledge/ingest
  → valida MAX_SOURCES_PER_BATCH
  → ensure_weekly_job_limit(knowledge.ingest.internal)   [NOVO — antes de salvar arquivos]
      ├─ limite None (ilimitado/legado) → segue
      ├─ uso da semana + 1 > limite → 429 "Limite semanal atingido..."
      └─ ok → segue
  → check job ativo (409)
  → salva arquivos + cria job
```

`GET /api/usage` passa a expor `usage.knowledge_ingest_weekly.{used,limit,remaining}`, contando
da mesma fonte (`jobs`), para não repetir a divergência já existente entre os `daily_keys` de
`usage.py` (leem de `limit_usage`) e o gate real de criação de job (lê de `jobs`) — ver nota em
`docs/architecture/plans-limits.md`.

---

## Plano de Implementação

### Fase 1 — backend-core: campo de limite semanal nos planos

**Objetivo:** expor `knowledge_ingest_weekly_limit` em `GET /me/entitlements`, com valores
seedados por plano.

| Arquivo | O que muda |
|---|---|
| `backend-core/app/models/plan_limits.py` | novo `Column("knowledge_ingest_weekly_limit", Integer, nullable=True)` + incluir em `as_dict()` |
| `backend-core/app/db.py` | `ensure_plan_limits_columns()`: adicionar coluna à migração idempotente |
| `backend-core/app/api/subscriptions.py` | `UserLimits` + `_calculate_limits()`: somar `knowledge_ingest_weekly_limit` entre subscrições ativas (mesmo tratamento dos `*_daily`) |
| `backend-core/app/seed.py` | `crm_start: 3`, `crm_growth: 10`, `crm_internal: None` (ilimitado); demais planos: `None` |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `3598ff0` | Campo `knowledge_ingest_weekly_limit` em `plan_limits`, entitlements e seed |

**Detalhes do commit `3598ff0`:**
- `plan_limits.py` — nova coluna `knowledge_ingest_weekly_limit` (Integer, nullable) + incluída em `as_dict()` (nota: essa inclusão também corrige, só para o campo novo, um `KeyError` latente que já existia para `max_email_send_daily`, ausente de `as_dict()` mas presente no dict `totals` de `_calculate_limits()` — bug pré-existente, fora do escopo desta tarefa, não corrigido para os outros campos)
- `db.py` — coluna adicionada a `ensure_plan_limits_columns()` (migração idempotente via `ALTER TABLE`)
- `subscriptions.py` — `UserLimits.knowledge_ingest_weekly_limit` + soma no dict `totals` de `_calculate_limits()`
- `seed.py` — `crm_start: 3`, `crm_growth: 10`, `crm_internal: None` (ilimitado)

### Relatório da Fase 1 — o que mudou na prática

**Antes:** os planos (Start, Growth, Interno) não tinham nenhum campo relacionado a limite de
ingestão de conhecimento — `GET /me/entitlements` não retornava essa informação.
**Agora:** cada plano tem um limite semanal configurado (Start: 3, Growth: 10, Interno:
ilimitado), exposto em `entitlements.limits.knowledge_ingest_weekly_limit`. Isso ainda não
bloqueia nada — é só a base de dados/config; o bloqueio real entra na Fase 2.
**Para validar:** nenhum Cenário desta secção cobre só a Fase 1 isoladamente (o comportamento
observável só aparece com a Fase 2 aplicada). Pode-se opcionalmente confirmar manualmente que
`GET /me/entitlements` (backend-core, porta 8001) retorna o campo novo com o valor correto por
plano de teste, mas os Cenários C1/C2/P1 só ficam testáveis depois da Fase 2.

**Nota:** ainda não perguntei sobre teste automatizado porque esta fase isolada não tem
comportamento observável via browser — vou seguir direto para a Fase 2 e oferecer o teste ao
final dela, quando o gate estiver realmente bloqueando/permitindo lotes.

### Fase 2 — backend-crm: conceito de semana + gate

**Objetivo:** bloquear criação de lote além do limite semanal, e expor uso em `/api/usage`.

| Arquivo | O que muda |
|---|---|
| `backend-crm/services/rate_limit_service.py` | `LIMIT_KEYS_BY_TYPE_WEEKLY`, `_count_jobs_for_week()`, `ensure_weekly_job_limit()`, `get_weekly_job_usage()` |
| `backend-crm/routes/knowledge_ingest.py` | chamar `ensure_weekly_job_limit(...)` em `create_ingest_batch()`, antes de salvar arquivos e antes do check 409 |
| `backend-crm/routes/usage.py` | bloco `knowledge_ingest_weekly` em `build_usage_payload()` |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `5882765` | Gate semanal de ingestão de conhecimento + exposição em `/api/usage` |

**Detalhes do commit `5882765`:**
- `rate_limit_service.py` — `LIMIT_KEYS_BY_TYPE_WEEKLY`, `_count_jobs_for_week()` (mirror de `_count_jobs_for_today()` com janela `DATE('now','utc','-6 days','weekday 1')`), `ensure_weekly_job_limit()` (levanta 429 se `uso + 1 > limite`) e `get_weekly_job_usage()` (leitura sem gate)
- `knowledge_ingest.py` — `create_ingest_batch()` chama o gate logo após validar `MAX_SOURCES_PER_BATCH`, antes de qualquer `dest.write_bytes()` e antes do check 409 de job ativo
- `usage.py` — novo bloco `knowledge_ingest_weekly` no payload de `/api/usage`, contando direto da tabela `jobs` (mesma fonte do gate)

### Relatório da Fase 2 — o que mudou na prática

**Antes:** um utilizador podia disparar quantos lotes de ingestão de conhecimento quisesse, sem
nenhum limite de uso — cada lote gera custo de IA (vision + classificação) sem controle por plano.
**Agora:** cada plano tem uma cota semanal (Start: 3, Growth: 10, Interno: ilimitado). Ao tentar
criar um lote além da cota, a API responde `429` com a mensagem "Limite semanal atingido para
ingestão de conhecimento. Atualize seu plano." — antes de qualquer arquivo ser salvo em disco.
`GET /api/usage` agora mostra quantos lotes já foram usados essa semana e quantos restam.
**Para validar:** Cenários C1 e C2, abaixo.

Quer que eu rode os Cenários C1 e C2 agora via browser (MCP chrome-devtools), com você
acompanhando? Isso exige um utilizador de teste com plano `crm_start` (limite 3/semana) para
forçar o 429 no Cenário C1.

Se preferir fazer depois (aqui ou numa conversa nova), pode colar:

> Lê `docs/implementations/knowledge-ingest-limite-lotes-semanal.md`, secção "Fase 2", e executa
> os testes dos Cenários C1 e C2.

### Fase 3 — frontend-crm: tratamento do 429 no painel de ingestão

**Objetivo:** exibir a mensagem real do limite semanal em vez do fallback genérico.

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/components/agente/KnowledgeIngestPanel.tsx` | `catch` de `startProcessing()`: checar `err instanceof ApiError && err.status === 429`, mostrar `err.message` |

### Commits Fase 3

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `1a77387` | Painel de ingestão mostra a mensagem real do limite semanal em vez do fallback genérico |

**Detalhes do commit `1a77387`:**
- `KnowledgeIngestPanel.tsx` — `startProcessing()`: novo branch no `catch` para `err instanceof ApiError && err.status === 429`, exibindo `err.message` (a mensagem do backend, ex.: "Limite semanal atingido para ingestão de conhecimento. Atualize seu plano.") no painel de erro inline já existente do componente

### Relatório da Fase 3 — o que mudou na prática

**Antes:** ao atingir o limite semanal, o utilizador via a mensagem genérica "Não foi possível
iniciar o processamento. Tente novamente." — sem explicar o motivo real.
**Agora:** a mesma tela mostra a mensagem real do backend, deixando claro que é um limite
semanal do plano e sugerindo upgrade.
**Para validar:** Cenário P1, abaixo.

Quer que eu rode o Cenário P1 agora via browser (MCP chrome-devtools), com você acompanhando?
Isso exige um utilizador de teste com plano `crm_start` (limite 3/semana) já no limite.

Se preferir fazer depois (aqui ou numa conversa nova), pode colar:

> Lê `docs/implementations/knowledge-ingest-limite-lotes-semanal.md`, secção "Fase 3", e executa
> o teste do Cenário P1.

### Fase 4 — docs de arquitetura

**Objetivo:** `docs/architecture/plans-limits.md` reflete o novo campo e o novo conceito de
limite semanal.

### Commits Fase 4

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `ba6bf90` | `docs/architecture/plans-limits.md` documenta o campo, o padrão `LIMIT_KEYS_BY_TYPE_WEEKLY` e a divergência pré-existente `daily_keys`/`limit_usage` |

Fase só de documentação — sem relatório separado (nenhum comportamento novo, só reflete o que já
foi implementado e reportado nas Fases 1–3).

---

## Checks de Validação

### Cenário C1 — Limite semanal bloqueia novo lote
- [ ] Setup: utilizador de teste com plano cujo `knowledge_ingest_weekly_limit` é baixo (ex.: 1)
- [ ] Ação: disparar lotes de ingestão até exceder o limite da semana
- [ ] Confirmar: lote extra recebe `429` com mensagem "Limite semanal atingido..."; `GET /api/usage` mostra `knowledge_ingest_weekly.used == limit`

### Cenário C2 — Plano ilimitado não é bloqueado
- [ ] Setup: utilizador com plano `crm_internal` (ou legado sem o campo)
- [ ] Ação: disparar vários lotes na mesma semana
- [ ] Confirmar: nenhum 429; `knowledge_ingest_weekly.limit` é `null`

### Cenário P1 — Frontend exibe mensagem do limite semanal
- [ ] Setup: forçar 429 (limite baixo no plano de teste)
- [ ] Ação: tentar iniciar processamento no `KnowledgeIngestPanel`
- [ ] Confirmar: mensagem exibida menciona limite semanal, não o fallback genérico

---

## Ajustes Possíveis Pós-Implementação

- A janela semanal usa `DATE('now','utc','-6 days','weekday 1')` (segunda-feira UTC mais
  recente) — não é ISO-8601 estrito em casos de borda de ano, mesmo nível de precisão já aceito
  para `month_utc` no resto do código.
- Nenhum toast/modal dedicado no frontend (mantém o padrão de erro inline já usado pelo
  componente) — se no futuro quiser paridade visual com o modal genérico de rate limit
  (`RateLimitModalContext`), seria um ajuste de UX separado.
