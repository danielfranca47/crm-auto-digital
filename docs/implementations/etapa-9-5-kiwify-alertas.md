# Kiwify Webhook + Alertas de Consumo

**Branch:** `etapa-9-planos-limites`
**Status:** Em andamento

---

## Motivação

O ciclo de cobrança está incompleto — quando um cliente paga no Kiwify, a subscription tem de ser activada manualmente pelo admin. Adicionalmente, utilizadores não recebem qualquer aviso quando o consumo de conversas IA se aproxima ou atinge o limite do plano.

---

## Informações de Integração Kiwify

| Campo | Valor |
|---|---|
| Token de validação | `qbq3qqs60ag` |
| Produto ID | `2e138970-e434-11f0-92a7-49ac9b9afca8` |
| Oferta Start (`crm_start`) | `gOjcexD` |
| Oferta Growth (`crm_growth`) | `To8qV99` |
| URL do webhook | `https://api.danielfranca.pt/webhooks/kiwify` |

---

## Problemas Identificados (estado anterior)

1. **Sem webhook Kiwify (`backend-core`):** activação de planos é 100% manual.
2. **`max_ia_conversas_monthly` ausente do `GET /api/usage` (`backend-crm/routes/usage.py`):** sem forma de o frontend saber quantas conversas foram usadas no mês.
3. **Sem alerta de consumo no frontend-crm:** utilizador não sabe quando está a aproximar-se do limite.

---

## Abordagem

```
Cliente paga no Kiwify
  → POST /webhooks/kiwify (backend-core)
  → valida token no payload
  → identifica oferta → mapeia para plan_code
  → encontra utilizador pelo email
  → desactiva subscription activa existente
  → cria nova Subscription (30 dias ou 365 dias para anual)

Utilizador usa conversas IA
  → frontend chama GET /api/usage
  → retorna ia_monthly: { used, limit, pct }
  → se pct >= 80: banner amarelo "80% das conversas usadas"
  → se pct >= 100: banner vermelho + link de checkout Kiwify
```

---

## Plano de Implementação

### Fase 1 — Webhook Kiwify (backend-core)

| Arquivo | O que muda |
|---|---|
| `backend-core/app/config.py` | `KIWIFY_WEBHOOK_SECRET`, `KIWIFY_PRODUCT_ID`, `KIWIFY_OFFER_MAP` |
| `backend-core/app/api/webhooks_kiwify.py` | Novo router. `POST /webhooks/kiwify` |
| `backend-core/app/main.py` | Incluir router |

**Eventos tratados:**
- `order_approved` / `order.approved` → activa subscription
- `subscription_renewed` / `subscription.renewed` → renova por +30 dias
- `order_refunded` / `subscription_cancelled` → cancela subscription

### Fase 2 — IA usage no endpoint + alerta frontend

| Arquivo | O que muda |
|---|---|
| `backend-crm/routes/usage.py` | Adicionar `ia_monthly` ao payload com `used`, `limit`, `pct` |
| `frontend-crm/src/components/UsageAlertBanner.tsx` | Novo. Banner amarelo (80%) ou vermelho (100%) com links de checkout |
| `frontend-crm/src/components/AppSidebar.tsx` ou layout | Renderizar banner quando alerta activo |

---

## Checks de Validação

### Cenário K1 — Webhook activa subscription
- [ ] Enviar payload de teste simulando compra do Start → utilizador recebe `crm_start`
- [ ] Enviar payload do Growth → utilizador recebe `crm_growth`
- [ ] Token inválido → 401

### Cenário K2 — Renovação e cancelamento
- [ ] `subscription_renewed` → `current_period_end` estende +30 dias
- [ ] `subscription_cancelled` → subscription passa a `cancelled`

### Cenário K3 — Alerta 80%
- [ ] Utilizador com 200/250 conversas usadas → banner amarelo visível no CRM

### Cenário K4 — Alerta 100%
- [ ] Utilizador com 250/250 → banner vermelho + link de checkout Kiwify Start

---

## Ajustes Possíveis Pós-Implementação

- Email automático "Compra confirmada — bem-vindo ao plano Start" após activação
- Email automático 3 dias antes da expiração da subscription
- Webhook de teste no painel Kiwify para validar antes de pagamento real
