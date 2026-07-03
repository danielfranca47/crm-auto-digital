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

Estes campos são expostos via `GET /me/entitlements` (backend-core) na estrutura `limits`:

```json
{
  "limits": {
    "follow_up_enabled": false,
    "playground_monthly_limit": 5
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
