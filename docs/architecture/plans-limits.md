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

`get_daily_job_usage(job_type, user_id, conn=None)` — leitura sem gate, mesma fonte (`jobs`),
usada por `/api/usage`. `JOB_TYPE_BY_LIMIT_KEY` (inverso de `LIMIT_KEYS_BY_TYPE`) deixa
`routes/usage.py::build_usage_payload()` decidir, por chave, se lê de `jobs` (chaves com job
type mapeado) ou de `limit_usage` via `_get_daily_usage()` (demais chaves, ex.:
`max_prospects_daily`, escrita por `consume_daily_units`/`reserve_daily_units` em
`automations/search/proposals/site/runner.py`) — mesmo padrão já usado pelo limite semanal
abaixo, sem tabela de uso duplicada para os tipos contados por job.

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

### Conta sem plano activo — `SubscriptionGate`

Sem assinatura `active` do produto `crm`, `require_crm_access` responde `403 Assinatura do produto
CRM ausente ou inativa` a todas as rotas privadas do backend-crm. O login (backend-core) continua a
funcionar, por isso o frontend trata o caso à entrada em vez de deixar o utilizador bater no erro:

```
login OK → Protected (valida sessão em /users/me)
  → SubscriptionGate → useSubscriptionStatus() → GET /me/entitlements (core)
      ├─ active   → app normal
      ├─ unknown  → app normal (core indisponível ou sem token — fail-open; quem decide é o backend-crm)
      └─ expired / cancelled / none
           → qualquer rota redireciona para /assinatura
           → AppShell troca para LockedShell (sem sidebar nem banners, só "Sair")
           → LeadsContext não arranca o polling de leads/pausa do bot
```

- `frontend-crm/src/lib/subscription.ts` — `pickCrmSubscription(entitlements)`: a assinatura activa
  ganha sempre; sem activa, vale a de `current_period_end` mais recente. Estados: `active`,
  `expired`, `cancelled` (qualquer outro status não-activo), `none` (nunca teve assinatura do CRM).
- `frontend-crm/src/hooks/useSubscriptionStatus.ts` — React Query, chave `["entitlements"]`
  (`ENTITLEMENTS_QUERY_KEY`), partilhada por gate, shell, `LeadsContext` e página de Assinatura.
  Só consulta com token guardado e fora das rotas públicas (`isPublicPath`, em
  `src/lib/public-routes.ts`).
- `frontend-crm/src/components/SubscriptionGate.tsx` e `LockedShell.tsx`.

**Quando a consulta falha (fail-open):** o `isLoading` do hook significa "ainda não houve nenhuma
resposta" (`enabled && !query.isFetched`), não o `isLoading` do React Query — este volta a `true` a
cada nova tentativa de uma consulta em erro sem dados, e o gate, que esconde a app enquanto
carrega, entraria em ciclo de montar/desmontar. Pelo mesmo motivo a consulta usa
`retryOnMount: false`: em erro, não é refeita só porque outro componente que usa o hook montou.
Repete uma vez em falha de rede/5xx (nunca em 401/403) e recupera sozinha quando a janela volta
a ter foco ou quando um 403 invalida a chave. Enquanto estiver em erro o estado é `unknown` e a
app funciona normalmente.

**401 vs 403 no handler global** (`useApiErrorHandler`): só `401` significa sessão expirada (toast +
`/login`). `403` nunca redireciona para o login: invalida `["entitlements"]` — se o plano caducou a
meio do uso, o gate leva a `/assinatura` — e mostra o toast "Sem acesso" com a mensagem do backend
(`detail` em texto, ou `detail.message` quando o gate devolve objecto). O polling de leads do
`LeadsContext` passa os seus 403 pelo handler em modo silencioso, só para disparar essa revalidação.
O handler não apaga o token: quem o apaga é quem confirmou no core que a sessão acabou — ver
"Guarda no LeadsContext" em [`auth-email.md`](auth-email.md).

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

**Catálogo "Planos disponíveis":** só os planos à venda — `SELLABLE_PLAN_CODES`, que são as chaves
de `PLAN_CHECKOUT_URLS` (`crm_start`, `crm_growth`), nessa ordem. `GET /plans?product_code=crm`
devolve todos os planos com `is_active` (incluindo os legados `crm_free`/`crm_basic`/`crm_pro` e o
`crm_internal`), porque o painel admin precisa deles; o filtro é feito na página. Um plano novo só
aparece ao cliente depois de ter entrada em `PLAN_CHECKOUT_URLS`. Os cartões mostram nome,
faturamento ("Mensal") e "Valor apresentado no checkout" — o preço não está no frontend.

**Assinatura exibida:** vem de `useSubscriptionStatus()` (ver "Conta sem plano activo" acima), não
da primeira linha de `entitlements.products` — o core devolve uma linha por assinatura que o
utilizador já teve. O cartão "Plano atual" mostra o nome do plano (mesmo que não esteja à venda,
ex.: "Interno"). O plano só é marcado "Plano atual" no catálogo (e o botão desabilitado) quando o
estado é `active`; um plano expirado/cancelado continua seleccionável.

**Data de fim de período:** `current_period_end` da assinatura escolhida. No card do plano actual:
"Activo até DD/MM/AAAA" (activa), "Expirou em" (expirada) ou "Período terminou em" (cancelada).

**Cartão de plano inactivo:** quando o estado é `expired`, `cancelled` ou `none`, aparece no topo um
Alert com o que aconteceu, a garantia de que os dados estão guardados e os botões:
- **Renovar agora / Reativar plano** → `renewal_checkout_url` da assinatura (fallback
  `buildCheckoutUrl(plan_code)`, e scroll aos planos se não houver link) — ver
  [`billing-efi.md`](billing-efi.md) para a regra do preço de Fundador
- **Escolher plano** (estado `none`) → scroll para a lista de planos
- **Já paguei — atualizar** → refaz a consulta de entitlements; a consulta também se revalida
  sozinha quando o utilizador volta ao separador depois de pagar
- **Falar com suporte** → `buildWhatsAppUrl`, só se `VITE_WHATSAPP_UPGRADE_NUMBER` estiver definido

Os atalhos "Ver limites"/"Ver uso" ficam escondidos nesse estado (dependem do backend-crm).

**Aviso de sobreposição:** ao selecionar um plano diferente do actual, exibe alerta explicando que a troca de plano não é automática — o utilizador deve subscrever o novo plano e contactar o suporte para cancelar a assinatura actual.

**Banner pós-compra:** se `?upgraded=1` estiver na URL, mostra Alert "Plano activado com sucesso!" (parâmetro reservado para um futuro redirect pós-pagamento; o checkout hospedado da Efí ainda não envia este parâmetro automaticamente).

---

## CORS — `backend-core/app/main.py`

As origens `http://127.0.0.1:5173` e `http://127.0.0.1:5174` foram adicionadas à lista `origins` para permitir acesso do frontend em ambiente local (Chrome resolve `localhost` para `::1` mas os backends escutam em `127.0.0.1`).
