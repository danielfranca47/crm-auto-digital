# Upgrade de Plano: Checkout e Webhook de Activação

**Branch:** `etapa-9-planos-limites`
**Status:** Todos os cenários pendentes de teste em produção — código implementado

---

## Motivação

A página `/assinatura` existe e mostra os planos disponíveis, mas o botão "Selecionar plano" está desabilitado porque `VITE_UPGRADE_CHECKOUT_URL` e `VITE_WHATSAPP_UPGRADE_NUMBER` não estão configurados. Mesmo que o utilizador consiga aceder ao checkout externo (Kiwify), a troca de plano é um processo manual — não há webhook que actualize a subscrição automaticamente após o pagamento.

O utilizador no plano Start que clica em "Ver planos" (vindo de um toast de gate) chega a uma página com botões inactivos.

---

## Dados Kiwify (recolhidos em 03/06/2026)

### Produto
- **Nome:** Lara AI - Digital Pro
- **ID:** `2e138970-e434-11f0-92a7-49ac9b9afca8`

### Links de checkout por plano

| Plano | URL | Preço | `plan_id` interno (nosso) |
|---|---|---|---|
| Plano Start | `https://pay.kiwify.com.br/gOjcexD` | R$ 97/mês | 8 (`crm_start`) |
| Plano Growth | `https://pay.kiwify.com.br/To8qV99` | R$ 197/mês | 9 (`crm_growth`) |
| Plano Scale | `https://pay.kiwify.com.br/2mtd25x` | R$ 997/mês | — (não mapeado ainda) |
| Sales Page | `https://kiwify.app/lr5CF3L` | — | — |

### Webhook já configurado
- **URL:** `https://api.danielfranca.pt/webhooks/kiwify`
- **Token (secret):** `<ver .env do backend-core — KIWIFY_WEBHOOK_TOKEN>`
- **Eventos activos:** Compra aprovada ✅, Assinatura cancelada ✅, Assinatura renovada ✅

### Formato do payload (Kiwify → nosso endpoint)

```json
{
  "webhook_event_type": "order_approved",
  "order_status": "paid",
  "Customer": {
    "email": "cliente@exemplo.com",
    "full_name": "Nome Completo"
  },
  "Product": {
    "product_id": "2e138970-e434-11f0-92a7-49ac9b9afca8",
    "product_name": "Lara AI - Digital Pro"
  },
  "Subscription": {
    "status": "active",
    "start_date": "2026-06-03T...",
    "next_payment": "2026-07-03T...",
    "plan": {
      "id": "<uuid-kiwify-interno>",
      "name": "Plano Start",
      "frequency": "monthly"
    }
  }
}
```

### Validação de assinatura
- A Kiwify envia a assinatura como **query param** na URL: `?signature=<valor>`
- Algoritmo: `HMAC-SHA1(JSON.stringify(body), token)`
- Token = valor de `KIWIFY_WEBHOOK_TOKEN` no `.env` do backend-core
- Comparar o valor recebido em `?signature=` com o calculado localmente

### Mapeamento plano Kiwify → nosso sistema
Identificar pelo `Subscription.plan.name`:

| `plan.name` (Kiwify) | `plan_id` (nosso DB) | `plan_code` |
|---|---|---|
| `"Plano Start"` | 8 | `crm_start` |
| `"Plano Growth"` | 9 | `crm_growth` |
| `"Plano Scale"` | — | `crm_scale` (não existe ainda) |

---

## Abordagem

```
Fase 1 — Frontend: mapeamento directo por plano (sem URL base genérica)
  Assinatura.tsx: buildCheckoutUrl usa mapeamento planCode → URL fixa Kiwify
  Botões "Selecionar plano" ficam activos para Start, Growth e Scale

Fase 2 — Backend-core: endpoint de webhook
  POST /webhooks/kiwify?signature=<hmac>
    → valida HMAC-SHA1(body, KIWIFY_WEBHOOK_TOKEN)
    → identifica user por Customer.email
    → webhook_event_type == "order_approved" → activa/actualiza subscrição
    → webhook_event_type == "subscription_canceled" → status = inactive
    → webhook_event_type == "subscription_renewed" → actualiza next_payment
    → retorna 200 {"status": "ok"}

Fase 3 — Frontend: banner pós-compra
  /assinatura?upgraded=1 → banner "Plano activado!"
  Kiwify redirect URL configurada para https://crmapp.danielfranca.pt/assinatura?upgraded=1
```

---

## Plano de Implementação

### Fase 1 — Frontend: activar botões de checkout

**Objetivo:** botões "Selecionar plano" abrem directamente a URL correta da Kiwify por plano.

**Decisão:** a `buildCheckoutUrl()` actual constrói a URL com query string — não funciona com a Kiwify (cada plano tem URL própria). Requer ajuste na `Assinatura.tsx`.

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/pages/Assinatura.tsx` | `buildCheckoutUrl()` substituída por mapeamento `planCode → URL` usando as URLs fixas da Kiwify |
| `frontend-crm/.env` | Adicionar as 3 URLs: `VITE_CHECKOUT_URL_CRM_START`, `VITE_CHECKOUT_URL_CRM_GROWTH`, `VITE_CHECKOUT_URL_CRM_SCALE` |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `8cfad99` | PLAN_CHECKOUT_URLS + buildCheckoutUrl por plano + banner ?upgraded=1 |

---

### Fase 2 — Backend-core: endpoint webhook Kiwify

**Objetivo:** processar automaticamente compras, cancelamentos e renovações.

| Arquivo | O que muda |
|---|---|
| `backend-core/app/api/webhooks_kiwify.py` | Novo. `POST /webhooks/kiwify`; validação HMAC-SHA1; upsert em `subscriptions` |
| `backend-core/app/api/__init__.py` | Registar novo router (sem prefixo de auth) |
| `backend-core/.env` | `KIWIFY_WEBHOOK_TOKEN=<token do painel Kiwify Apps → Webhooks>` |

**Lógica do handler:**
```python
import hmac, hashlib, json

def verify_signature(body_bytes: bytes, token: str, received_sig: str) -> bool:
    expected = hmac.new(token.encode(), body_bytes, hashlib.sha1).hexdigest()
    return hmac.compare_digest(expected, received_sig)

# Mapeamento plan.name → plan_id local
PLAN_NAME_MAP = {
    "Plano Start":  8,
    "Plano Growth": 9,
}

# Evento order_approved → upsert subscription
# Evento subscription_canceled → status = "inactive"
# Evento subscription_renewed → actualizar current_period_end
```

**Resposta mínima:** `{"status": "ok"}` com HTTP 200 (a Kiwify reenvía até 5x se não receber 2xx).

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | (pré-existente) | `webhooks_kiwify.py` + `KIWIFY_WEBHOOK_SECRET` em settings/env — já estava implementado |

---

### Fase 3 — Frontend: banner pós-compra

**Objetivo:** utilizador que volta do checkout vê confirmação do upgrade.

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/pages/Assinatura.tsx` | Detectar `?upgraded=1` na URL → mostrar Alert de boas-vindas; refetch entitlements |

> Configurar no painel Kiwify o URL de redirect após compra: `https://crmapp.danielfranca.pt/assinatura?upgraded=1`

### Commits Fase 3

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `8cfad99` | Banner `?upgraded=1` em `Assinatura.tsx` (mesmo commit da Fase 1) |

---

## Checks de Validação

### Cenário U1 — Botões de checkout activos
- [ ] Plano Start: `/assinatura` → botão "Selecionar plano" no card Growth está activo
- [ ] Clicar → abre `https://pay.kiwify.com.br/To8qV99` em nova aba

### Cenário U2 — Webhook activa subscrição (`order_approved`)
- [ ] Enviar payload simulado com `webhook_event_type: "order_approved"`, `plan.name: "Plano Growth"`, `Customer.email: <email existente>` e assinatura HMAC válida → 200
- [ ] `GET /me/entitlements` → `follow_up_enabled: true`, `playground_monthly_limit: null`

### Cenário U3 — Rejeição de assinatura inválida
- [ ] Enviar payload com `?signature=errado` → 401

### Cenário U4 — Webhook de cancelamento
- [ ] Enviar `webhook_event_type: "subscription_canceled"` → subscrição fica `inactive`
- [ ] Entitlements reflectem plano sem acesso

### Cenário U5 — Banner pós-compra
- [ ] Navegar para `/assinatura?upgraded=1` → Alert "Plano activado!" visível
- [ ] Entitlements actualizados sem reload manual
