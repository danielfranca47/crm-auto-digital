# Upgrade de Plano: Checkout e Webhook de Activação

**Branch:** `etapa-9-planos-limites`
**Status:** Todos os checks validados localmente — pendente de deploy para produção

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

### Fase 5 — Backend-core: criar conta e enviar credenciais para novos compradores

**Gap identificado em 03/06/2026:** o endpoint `/internal/subscriptions/kiwify-event` retorna `skipped: user_not_found` quando o email do comprador não existe no sistema. Para novos clientes (primeira compra), nunca é criada conta nem enviado email — o comprador paga mas não consegue aceder.

**Comportamento esperado:**
```
order_approved → email desconhecido
  → criar User com password aleatória (12+ chars, segura)
  → enviar email "Bem-vindo ao Lara AI" com:
      - password temporária
      - link de login directo
      - primeiros passos
  → activar subscription
  → retornar {"action": "created_and_activated"}

order_approved → email já existente (upgrade)
  → fluxo actual: activar subscription normalmente
  → retornar {"action": "activated"}
```

| Arquivo | O que muda |
|---|---|
| `backend-core/app/api/subscriptions.py` | `kiwify_subscription_event`: se `user_not_found` → criar `User` com password aleatória segura → activar subscription → enviar email |
| `backend-core/app/services/email_service.py` | Novo template `render_kiwify_new_customer_email(name, email, temp_password, login_url)` com credenciais e primeiros passos |

**Geração de password segura:**
```python
import secrets, string
alphabet = string.ascii_letters + string.digits + "!@#$%"
temp_password = ''.join(secrets.choice(alphabet) for _ in range(14))
```

O utilizador deve ser forçado a alterar a senha no primeiro login (ou pelo menos incentivado pelo email).

### Commits Fase 5

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | — | — |

---

## Pendente de configuração (pré-deploy)

| Item | Estado |
|---|---|
| `KIWIFY_WEBHOOK_SECRET` no `.env` de **produção do backend-crm** | ⏳ ao fazer deploy |
| URL de redirect pós-compra no painel Kiwify | ⏳ decisão pendente — ver nota |

**Nota sobre redirect pós-compra:** `/assinatura?upgraded=1` é adequado para upgrades de utilizadores existentes. Para **novos compradores** (primeira compra), faz mais sentido uma página de boas-vindas (`/welcome`) com instruções de login. A definir antes do primeiro cliente real.

**Nota sobre `backend-core/.env`:** o ficheiro `backend-core/app/api/webhooks_kiwify.py` é código morto (o endpoint `/webhooks/kiwify` agora está no backend-crm). Pode ser removido numa limpeza futura junto com o `KIWIFY_WEBHOOK_SECRET` do `.env` do core.

---

## Checks de Validação

### U1 — Botões de checkout activos
- [x] Utilizador com plano activo: `/assinatura` → aviso de renovação com data visível
- [x] Botão "Selecionar plano" nos cards está activo
- [⏭️] Clicar → confirmar URL em nova aba (requer sessão activa; validar após deploy)
- **Validado em:** 03/06/2026 — accessibility tree confirmou banner e botões activos

### U2 — Webhook activa subscrição (`order_approved`)
- [x] Payload `order_approved` com `plan.name: "Plano Growth"` e email existente → `{"ok": true, "action": "activated"}`
- [x] `GET /me/entitlements` → `follow_up_enabled: true`, `playground_monthly_limit: null`, `crm_start` cancelado automaticamente
- **Validado em:** 03/06/2026 — curl directo com HMAC-SHA1 calculado localmente

### U3 — Rejeição de signature inválida
- [x] Signature errada → HTTP 401
- [x] Sem signature → HTTP 401
- **Validado em:** 03/06/2026

### U4 — Webhook de cancelamento
- [x] `subscription_canceled` → `{"ok": true, "action": "cancelled"}`
- [x] `GET /me/entitlements` → `subscription_status: inactive`, plano `cancelled`
- **Validado em:** 03/06/2026 — curl directo

### U5 — Banner pós-compra
- [x] `/assinatura?upgraded=1` → Alert "Plano activado com sucesso!" visível
- **Validado em:** 03/06/2026 — accessibility tree confirmou `heading "Plano activado com sucesso!"`

### U6 — Endpoint interno (smoke test)
- [x] `POST localhost:8001/internal/subscriptions/kiwify-event` com token correcto → `{"ok": true, "action": "activated"}`
- [x] Com token errado → 401
- **Validado em:** 03/06/2026

### U7 — Novo comprador: conta criada automaticamente (Fase 5)
- [ ] Webhook `order_approved` com email **não existente** → `{"ok": true, "action": "created_and_activated"}`
- [ ] Utilizador criado no DB (`users` table) com o email da Kiwify
- [ ] Email enviado com password temporária e link de login
- [ ] Subscrição activada para o novo utilizador

### U8 — Login com credenciais recebidas por email (Fase 5)
- [ ] Fazer `POST /auth/login` com email e password temporária recebida → token JWT válido
- [ ] `GET /me/entitlements` → plano correcto activo

### U9 — Comprador existente (upgrade) não recebe email de boas-vindas (Fase 5)
- [ ] Webhook `order_approved` com email **já existente** → `{"ok": true, "action": "activated"}` (sem criação de conta, sem email de credenciais)
