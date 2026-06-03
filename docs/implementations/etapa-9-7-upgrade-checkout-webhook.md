# Upgrade de Plano: Checkout e Webhook de Activação

**Branch:** `etapa-9-planos-limites`
**Status:** Em andamento

---

## Motivação

A página `/assinatura` existe e mostra os planos disponíveis, mas o botão "Selecionar plano" está desabilitado porque `VITE_UPGRADE_CHECKOUT_URL` e `VITE_WHATSAPP_UPGRADE_NUMBER` não estão configurados. Mesmo que o utilizador consiga aceder ao checkout externo (Kiwify), a troca de plano é um processo manual — não há webhook que actualize a subscrição automaticamente após o pagamento.

O utilizador no plano Start que clica em "Ver planos" (vindo de um toast de gate) chega a uma página com botões inactivos.

---

## Problemas Identificados (estado anterior)

1. **`VITE_UPGRADE_CHECKOUT_URL` não configurado (`frontend-crm/.env`):** os botões "Selecionar plano" ficam desabilitados; utilizador não consegue fazer upgrade.

2. **Sem webhook de activação (backend-core):** após o pagamento na Kiwify, a subscrição tem de ser actualizada manualmente pelo admin via painel ou API. Não há endpoint `POST /webhooks/kiwify` que receba a confirmação e actualize `subscriptions`.

3. **Links hardcoded no `/usage` (`backend-crm/routes/usage.py:82`):** `checkout_links` com URLs Kiwify hardcoded no payload de usage, sem uso actual no frontend.

---

## Abordagem

```
Fase 1 — Frontend: configurar checkout links no .env e activar botões
  VITE_UPGRADE_CHECKOUT_URL (base) ou links por plano → botões activos
  Ao clicar: abre checkout externo (Kiwify) em nova aba com ?plan=crm_growth&email=X

Fase 2 — Backend-core: webhook Kiwify
  POST /webhooks/kiwify
    → valida assinatura HMAC (header X-Kiwify-Signature)
    → identifica utilizador pelo email do evento
    → actualiza subscriptions (plan_id, status, current_period_end)
    → retorna 200

Fase 3 — Frontend: feedback pós-compra
  Página /assinatura: detectar query param ?upgraded=1 ou polling de entitlements
  → mostrar banner "Plano activado! Bem-vindo ao Growth."
  → remover toasts de gate já exibidos
```

---

## Plano de Implementação

### Fase 1 — Frontend: activar botões de checkout

**Objetivo:** o utilizador consegue clicar em "Selecionar plano" e chega ao checkout correcto.

**Decisão de design:** a `Assinatura.tsx` já suporta `VITE_UPGRADE_CHECKOUT_URL` (URL base com `?plan=` appended) ou `VITE_WHATSAPP_UPGRADE_NUMBER`. Usar a URL base da Kiwify é suficiente para a Fase 1 — não requer código.

| Arquivo | O que muda |
|---|---|
| `frontend-crm/.env` | Adicionar `VITE_UPGRADE_CHECKOUT_URL=https://pay.kiwify.com.br/XXXXX` (URL da página de planos ou de um funil) |

> **Nota:** Se a Kiwify tiver uma URL única por plano (não por parâmetro), será necessário alterar `buildCheckoutUrl()` em `Assinatura.tsx` para um mapeamento `planCode → url` em vez de construir a URL por query string.

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | — | — |

---

### Fase 2 — Backend-core: webhook Kiwify

**Objetivo:** receber confirmação de pagamento da Kiwify e activar a subscrição automaticamente.

| Arquivo | O que muda |
|---|---|
| `backend-core/app/api/webhooks_kiwify.py` | Novo. Endpoint `POST /webhooks/kiwify`; validação HMAC; lookup de user por email; upsert em `subscriptions` |
| `backend-core/app/api/__init__.py` | Registar novo router |
| `backend-core/.env` | Adicionar `KIWIFY_WEBHOOK_SECRET=<segredo>` |

**Mapeamento de eventos Kiwify → plano:**

| Evento Kiwify | Produto/Oferta | `plan_id` |
|---|---|---|
| `order_approved` | Oferta Start | 8 (`crm_start`) |
| `order_approved` | Oferta Growth | 9 (`crm_growth`) |
| `order_refunded` / `subscription_canceled` | qualquer | status = `inactive` |

**Lógica de upsert:**
```python
# Identificar utilizador pelo email do evento
user = db.query(User).filter(User.email == event["customer"]["email"]).first()
if not user:
    return {"status": "ignored", "reason": "user_not_found"}

# Upsert na subscrição do produto CRM
existing = db.query(Subscription).filter(
    Subscription.user_id == user.id,
    Subscription.product_id == 1  # product "crm"
).first()
# ... actualizar ou criar
```

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | — | — |

---

### Fase 3 — Frontend: feedback pós-compra

**Objetivo:** ao regressar do checkout, o utilizador recebe confirmação visual de que o plano foi activado.

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/pages/Assinatura.tsx` | Detectar `?upgraded=1` na URL (redirect do checkout) ou refetch de entitlements após foco na janela; mostrar Alert/banner de boas-vindas |

> A Kiwify permite configurar um URL de redirect após compra — usar `https://<app>/assinatura?upgraded=1`.

### Commits Fase 3

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | — | — |

---

## Checks de Validação

### Cenário U1 — Botão de checkout activo
- [ ] Plano Start: entrar em `/assinatura` → botão "Selecionar plano" no card Growth está activo
- [ ] Clicar → abre Kiwify em nova aba com email pré-preenchido (se configurado)

### Cenário U2 — Webhook activa subscrição
- [ ] Enviar evento Kiwify simulado (curl com payload de `order_approved`) → subscrição actualizada em `subscriptions`
- [ ] Chamar `GET /me/entitlements` após webhook → `follow_up_enabled: true`, `playground_monthly_limit: null`

### Cenário U3 — Rejeição de webhook inválido
- [ ] Enviar evento com assinatura HMAC errada → 401

### Cenário U4 — Banner pós-compra
- [ ] Navegar para `/assinatura?upgraded=1` → banner "Plano activado!" visível
- [ ] Entitlements reflectem novo plano sem reload manual

---

## Questões em aberto (a confirmar antes de implementar)

1. **URL de checkout:** a Kiwify usa uma URL por produto ou há uma página de planos unificada?
2. **Identificação do plano no evento:** o payload Kiwify inclui o `offer_id` ou apenas o produto? É necessário manter um mapeamento `offer_id → plan_id` no backend-core.
3. **Segredo do webhook:** onde é configurado no painel Kiwify e como é enviado (header vs query param)?
4. **Downgrade:** suportado? Kiwify envia evento de cancelamento que pode ser mapeado para `status = inactive`.
