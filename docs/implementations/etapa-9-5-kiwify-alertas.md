# Kiwify Webhook + Alertas de Consumo

**Branch:** `etapa-9-planos-limites`
**Status:** Em andamento — lógica validada; K1/K2 end-to-end pendentes de webhook real Kiwify

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

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `4dbbaef` | webhooks_kiwify.py + config KIWIFY_WEBHOOK_SECRET + KIWIFY_PRODUCT_ID |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `35f4cb8` | ia_monthly no usage endpoint + UsageAlertBanner + AppShell |

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
- [x] `_resolve_plan_code(payload com ucode gOjcexD)` → `crm_start`
- [x] `_resolve_plan_code(payload com ucode To8qV99)` → `crm_growth`
- [x] Fallback por string no payload → `crm_start`
- [x] `_extract_field(payload, "token")` → `qbq3qqs60ag`
- [⏭️] End-to-end com webhook real Kiwify — pendente de primeiro pagamento/teste real
- **Validado em:** 02/06/2026 — teste directo de lógica via Python

### Cenário K2 — Renovação e cancelamento
- [⏭️] `subscription_renewed` → lógica implementada, pendente de webhook real
- [⏭️] `subscription_cancelled` → idem
- **Nota:** lógica em `_renew_subscription` e `_cancel_subscription` é directa e coerente com o padrão existente

### Cenário K3 — Alerta 80%
- [x] `GET /api/usage` retorna `ia_monthly: {used, limit, pct}` e `checkout_links`
- [x] `UsageAlertBanner` renderizado no AppShell (entre header e main)
- [⏭️] Visual com 200/250 usadas — pendente de utilizador com uso real
- **Validado em:** 02/06/2026 — curl ao /api/usage: ia_monthly.limit=250, pct=0

### Cenário K4 — Alerta 100%
- [⏭️] Visual com 250/250 — pendente de utilizador no limite
- **Nota:** lógica no banner: `pct >= 100` → fundo vermelho + "Comprar mais"

---

## Ajustes Possíveis Pós-Implementação

- Email automático "Compra confirmada — bem-vindo ao plano Start" após activação
- Email automático 3 dias antes da expiração da subscription
- Webhook de teste no painel Kiwify para validar antes de pagamento real
