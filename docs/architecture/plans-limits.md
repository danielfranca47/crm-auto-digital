# Feature Gates e Limites por Plano

Documenta o sistema de controlo de acesso a funcionalidades baseado no plano de subscrição do utilizador.

---

## Visão geral

Cada plano (`crm_start`, `crm_growth`, `crm_internal`, etc.) tem uma linha em `plan_limits` no backend-core. O backend-crm consume os entitlements via `require_crm_access` e aplica gates nas rotas antes de processar a lógica de negócio.

---

## Campos de limite relevantes em `plan_limits`

| Campo | Tipo | `crm_start` | `crm_growth` / legado |
|---|---|---|---|
| `follow_up_enabled` | `INTEGER (0/1)` | `0` | `1` |
| `playground_monthly_limit` | `INTEGER` ou `NULL` | `5` | `NULL` (ilimitado) |
| `knowledge_ingest_weekly_limit` | `INTEGER` ou `NULL` | `3` | `10` (`crm_growth`) / `NULL` (`crm_internal`, ilimitado) |

Estes campos são expostos via `GET /me/entitlements` (backend-core) na estrutura `limits`:

```json
{
  "limits": {
    "follow_up_enabled": false,
    "playground_monthly_limit": 5,
    "knowledge_ingest_weekly_limit": 3
  }
}
```

**Comportamento para utilizadores legados (planos sem o campo ou sem subscrição):** `_calculate_limits` retorna `follow_up_enabled: True` e `playground_monthly_limit: None` por defeito — sem bloqueio.

---

## Serviço de gates — `backend-crm/services/plan_gates.py`

### `check_follow_up_enabled(entitlements)`

Verifica se o plano inclui follow-up automático.

- Lê `entitlements["limits"]["follow_up_enabled"]`
- Default `True` se campo ausente (compatibilidade com planos legados)
- Lança `HTTP 403` com `{ "error": "follow_up_not_included" }` se `False`

**Chamado em:** `routes/leads.py` → `start_followup_transition()`

### `check_playground_limit(user_id, entitlements, conn)`

Verifica e incrementa a quota mensal do Playground.

- Lê `entitlements["limits"]["playground_monthly_limit"]`
- `None` → ilimitado, retorna imediatamente
- Garante existência de `playground_usage_monthly` (CREATE IF NOT EXISTS)
- Compara `count >= limit` → 403 antes de qualquer processamento
- Se permitido: faz `INSERT ... ON CONFLICT DO UPDATE SET count = count + 1`

**Chamado em:** `routes/playground.py` → endpoint `POST /api/playground/chat`

**Erro 403 ao exceder:**
```json
{
  "error": "playground_limit_reached",
  "message": "...",
  "used": 3,
  "limit": 5
}
```

---

## Limites por contagem de jobs — `backend-crm/services/rate_limit_service.py`

Padrão usado para limites cuja unidade é "1 job criado", sem tabela de uso dedicada — a contagem
é feita direto na tabela `jobs`, filtrando por `type` + `user_id` + janela de tempo.

### Limite diário — `LIMIT_KEYS_BY_TYPE`

```python
LIMIT_KEYS_BY_TYPE = {
    TYPE_WHATSAPP_SEND: "max_whatsapp_send_daily",
    TYPE_EMAIL_SEND_COLD: "max_email_send_daily",
    TYPE_MAPS_SEARCH: "max_maps_search_daily",
    TYPE_MAPS_ENRICH: "max_maps_enrich_daily",
}
```

`build_rate_limit_state()` / `ensure_daily_limit(job_type, user_id, entitlements)` contam jobs
desse tipo criados hoje (`_count_jobs_for_today`, `DATE(created_at,'utc') = DATE('now','utc')`) e
levantam `HTTP 429` se o próximo job excederia o limite.

**Nota — divergência conhecida:** `routes/usage.py::build_usage_payload()` tem uma lista
`daily_keys` que inclui essas mesmas chaves (`max_whatsapp_send_daily`, `max_maps_search_daily`,
etc.) e as lê via `_get_daily_usage()` — mas essa função lê da tabela `limit_usage`, que só é
escrita para `max_prospects_daily` (via `consume_daily_units`/`reserve_daily_units` em
`automations/search/proposals/site/runner.py`). Para os outros keys da lista, o gate real (na
criação do job) e o número exibido em `/api/usage` vêm de fontes diferentes — o `/api/usage`
mostraria `used: 0` sempre para eles. Pré-existente, fora do escopo de qualquer feature que só
precise do gate funcionando; ao adicionar um novo limite por contagem de job, prefira ler o
"usado" também da tabela `jobs` (ver exemplo do limite semanal abaixo), não de `limit_usage`.

### Limite semanal — `LIMIT_KEYS_BY_TYPE_WEEKLY`

```python
LIMIT_KEYS_BY_TYPE_WEEKLY = {
    TYPE_KNOWLEDGE_INGEST: "knowledge_ingest_weekly_limit",
}
```

Mesmo padrão do diário, mas com janela da semana corrente (segunda-feira UTC até agora):
`_count_jobs_for_week()` usa `DATE(created_at,'utc') >= DATE('now','utc','-6 days','weekday 1')`
(idioma SQLite para "a segunda-feira mais recente", não é ISO-8601 estrito em bordas de ano —
mesmo nível de precisão já aceito para `month_utc` no restante do arquivo).

- `ensure_weekly_job_limit(job_type, user_id, entitlements, label=None)` — gate, levanta `429`
- `get_weekly_job_usage(job_type, user_id, conn=None)` — leitura sem gate, usada por `/api/usage`

**Chamado em:** `routes/knowledge_ingest.py` → `create_ingest_batch()` (antes de salvar arquivos
em disco e antes do check de job ativo/409) · `routes/usage.py` → bloco `knowledge_ingest_weekly`
(lê direto de `jobs`, evitando a divergência descrita acima).

---

## Tabela `playground_usage_monthly` (CRM DB)

```sql
CREATE TABLE IF NOT EXISTS playground_usage_monthly (
    user_id INTEGER NOT NULL,
    month   TEXT    NOT NULL,   -- formato YYYY-MM (UTC)
    count   INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, month)
);
```

- Criada lazily na primeira chamada ao gate (idempotente)
- O contador não é decrementado mesmo que a chamada ao LLM falhe após o gate

---

## Campo `playground_monthly` em `/usage`

`GET /api/usage` (backend-crm) retorna na chave `usage`:

```json
{
  "playground_monthly": {
    "used": 2,
    "limit": 5,
    "remaining": 3
  },
  "knowledge_ingest_weekly": {
    "used": 1,
    "limit": 3,
    "remaining": 2
  }
}
```

- `limit: null` e `remaining: null` para planos ilimitados
- Calculado em `build_usage_payload()` em `routes/usage.py`

---

## Padrão de UX no frontend

### Toast de bloqueio com CTA de upgrade

Quando a API retorna 403 com um erro de gate, o frontend fecha o modal/ação e exibe um toast com botão "Ver planos" apontando para `/assinatura`.

| Erro 403 | Componente | Título do toast |
|---|---|---|
| `follow_up_not_included` | `FollowUpTransitionModal.tsx` | "Follow-up não incluído no seu plano" |
| `playground_limit_reached` | `Playground.tsx` | "Limite de testes atingido" |

Implementação: handler no `catch` verifica `error?.data?.detail?.error`, se reconhecido mostra toast com `ToastAction` e retorna — sem executar o toast genérico de erro.

**Exceção — `KnowledgeIngestPanel.tsx`:** o gate de `knowledge_ingest_weekly_limit` retorna `429`
com `detail` como string simples (não `{error, message}`), e o painel não segue o padrão de
toast/CTA — mostra a mensagem do backend inline no próprio painel de erro do componente
(`startProcessing()` checa `err instanceof ApiError && err.status === 429`). Escolha consciente
para manter consistência com o painel de erro inline já existente no componente, não um gap a
corrigir.

### Badge de quota no Playground

`Playground.tsx` usa `useUsage()` para ler `usage.playground_monthly` e exibe badge na barra superior da sessão:

- Plano com limite: `"X / Y usos este mês"` (vermelho quando `remaining === 0`)
- Plano ilimitado: `"N usos este mês"`

---

## Página de Assinatura — `frontend-crm/src/pages/Assinatura.tsx`

Ponto de acesso do utilizador para upgrade e visualização do plano actual.

**Checkout de upgrade** (`PLAN_CHECKOUT_URLS`, `buildCheckoutUrl(planCode)`): aponta para o
endpoint de checkout sob demanda da Efí (`{VITE_CRM_BASE_URL}/checkout/efi/{start|growth}`, com
`VITE_UPGRADE_CHECKOUT_URL` como fallback) — detalhes completos do fluxo em
[`billing-efi.md`](billing-efi.md).

**Data de renovação:** lida de `entitlements.products[0].current_period_end`. Exibida no card do plano actual como "Renovação: DD/MM/AAAA".

**Aviso de sobreposição:** ao selecionar um plano diferente do actual, exibe alerta explicando que a troca de plano não é automática — o utilizador deve subscrever o novo plano e contactar o suporte para cancelar a assinatura actual.

**Banner pós-compra:** se `?upgraded=1` estiver na URL, mostra Alert "Plano activado com sucesso!" (parâmetro reservado para um futuro redirect pós-pagamento; o checkout hospedado da Efí ainda não envia este parâmetro automaticamente).

---

## CORS — `backend-core/app/main.py`

As origens `http://127.0.0.1:5173` e `http://127.0.0.1:5174` foram adicionadas à lista `origins` para permitir acesso do frontend em ambiente local (Chrome resolve `localhost` para `::1` mas os backends escutam em `127.0.0.1`).
