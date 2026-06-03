# Upgrade de Plano: Checkout e Webhook de Activação

**Branch:** `etapa-9-planos-limites`
**Status:** Em andamento — código implementado, pendente de deploy e validação em produção

---

## Motivação

A página `/assinatura` existia mas os botões de upgrade estavam inactivos. Após pagamento na Kiwify, a subscrição não era activada automaticamente — requeria intervenção manual do admin. Utilizadores bloqueados pelos gates (follow-up, playground) chegavam à página de planos sem conseguir agir.

---

## Dados Kiwify (recolhidos em 03/06/2026)

### Produto
- **Nome:** Lara AI - Digital Pro  
- **ID:** `2e138970-e434-11f0-92a7-49ac9b9afca8`

### Links de checkout por plano

| Plano | URL Kiwify | Preço | `plan_code` (nosso) |
|---|---|---|---|
| Plano Start | `https://pay.kiwify.com.br/gOjcexD` | R$ 97/mês | `crm_start` |
| Plano Growth | `https://pay.kiwify.com.br/To8qV99` | R$ 197/mês | `crm_growth` |
| Plano Scale | `https://pay.kiwify.com.br/2mtd25x` | R$ 997/mês | `crm_scale` (não existe no DB ainda) |
| Sales Page | `https://kiwify.app/lr5CF3L` | — | — |

### Webhook configurado na Kiwify
- **URL:** `https://api.danielfranca.pt/webhooks/kiwify`
- **Secret:** variável `KIWIFY_WEBHOOK_SECRET` no `.env` do backend-crm
- **Eventos activos:** Compra aprovada ✅, Assinatura cancelada ✅, Assinatura renovada ✅
- **Validação:** HMAC-SHA1 enviado como query param `?signature=<valor>`

### Comportamento de upgrade (confirmado por pesquisa — 03/06/2026)
A Kiwify **não tem upgrade automático com proration**. Comprar um plano superior cria uma nova subscrição independente. O fluxo recomendado ao utilizador:
1. Subscrever o novo plano próximo da data de renovação do actual
2. Cancelar o plano antigo pelo link no email da Kiwify
3. O nosso sistema activa o novo plano e cancela o anterior internamente ao receber `order_approved`

### Fluxo do webhook
```
Kiwify → POST api.danielfranca.pt/webhooks/kiwify?signature=<hmac>
  → backend-crm: valida HMAC-SHA1, mapeia Subscription.plan.name → plan_code
  → POST localhost:8001/internal/subscriptions/kiwify-event (x-service-token)
  → backend-core: activa / cancela / renova subscription no DB
```

---

## Implementação

### Fase 1 — Frontend: botões de checkout activos + aviso de renovação

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/pages/Assinatura.tsx` | `PLAN_CHECKOUT_URLS` por plano; data de renovação do plano actual; aviso de sobreposição; banner `?upgraded=1` |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `8cfad99` | `PLAN_CHECKOUT_URLS` + `buildCheckoutUrl` por plano + banner `?upgraded=1` |
| 2 | `df910ef` | `current_period_end` em entitlements + data de renovação + aviso de sobreposição |

---

### Fase 2 — Backend-crm: endpoint público `POST /webhooks/kiwify`

| Arquivo | O que muda |
|---|---|
| `backend-crm/routes/webhooks.py` | Valida HMAC-SHA1 via `?signature=`; mapeia `plan.name` → `plan_code`; chama core via httpx |
| `backend-crm/.env` | `KIWIFY_WEBHOOK_SECRET=<token do painel Kiwify>` |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `731bd1b` | `POST /webhooks/kiwify` no backend-crm |

---

### Fase 3 — Backend-core: endpoint interno `POST /internal/subscriptions/kiwify-event`

| Arquivo | O que muda |
|---|---|
| `backend-core/app/api/subscriptions.py` | Endpoint interno protegido por `x-service-token`; activa/cancela/renova subscription; expõe `current_period_end` em entitlements |

### Commits Fase 3

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `731bd1b` | `/internal/subscriptions/kiwify-event` no backend-core |
| 2 | `df910ef` | `current_period_end` em `ProductEntitlement` |

---

## Pendente de configuração (pré-deploy)

| Item | Estado | Responsável |
|---|---|---|
| `KIWIFY_WEBHOOK_SECRET` no `.env` de produção (backend-crm) | ⏳ | Deploy |
| `KIWIFY_WEBHOOK_SECRET` no `.env` de produção (backend-core) | ⏳ | Deploy (já existia localmente) |
| URL de redirect pós-compra no painel Kiwify | ⏳ | A definir — ver nota abaixo |

**Nota sobre redirect pós-compra:** o redirect `/assinatura?upgraded=1` é adequado para utilizadores existentes que fazem upgrade. Para **novos compradores** (primeira compra), o ideal seria uma página de boas-vindas (`/welcome` ou similar) com instruções de acesso. A definir se a mesma URL serve ambos os casos ou se se criam duas.

---

## Checks de Validação

### U1 — Botões de checkout activos
- [ ] Utilizador com plano activo: `/assinatura` → aviso de renovação com data visível
- [ ] Botão "Selecionar plano" no card Growth está activo
- [ ] Clicar → abre `https://pay.kiwify.com.br/To8qV99` em nova aba com email pré-preenchido

### U2 — Webhook activa subscrição (`order_approved`)
- [x] Payload `order_approved` com `plan.name: "Plano Growth"` e email existente → `{"ok": true, "action": "activated"}`
- [x] `GET /me/entitlements` → `follow_up_enabled: true`, `playground_monthly_limit: null`, `crm_start` cancelado automaticamente
- **Validado em:** 03/06/2026 — curl directo com HMAC-SHA1 calculado localmente

### U3 — Rejeição de signature inválida
- [x] Signature errada → HTTP 401
- [x] Sem signature → HTTP 401
- **Validado em:** 03/06/2026

### U4 — Webhook de cancelamento
- [ ] Enviar `webhook_event_type: "subscription_canceled"` → subscrição fica `cancelled` no DB
- [ ] Entitlements reflectem plano sem acesso

### U5 — Banner pós-compra
- [ ] Navegar para `/assinatura?upgraded=1` → Alert verde "Plano activado!" visível

### U6 — Endpoint interno (smoke test)
- [x] `POST localhost:8001/internal/subscriptions/kiwify-event` com token correcto → `{"ok": true, "action": "activated"}`
- [x] Com token errado → 401
- **Validado em:** 03/06/2026
