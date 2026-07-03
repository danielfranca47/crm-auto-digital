# Billing — Gateway de Pagamento Efí Bank

Cobre a cobrança da assinatura SaaS (Start/Growth): geração de checkout sob demanda, webhook de
confirmação de pagamento e activação/renovação/cancelamento de subscriptions. Substituiu a Kiwify
(ver `docs/implementations/migracao-gateway-efi-bank.md` para o histórico da migração, já
graduado e removido).

**Não confundir com:** o campo `payment_gateway` (`hotmart`/`kiwify`/`stripe`/`generico`) do AI
Profile (`agents.md`) — isso é o gateway que o *cliente final* (utilizador da Lara) usa para
vender os próprios produtos dele, feature independente e sem relação com este documento.

---

## Visão geral do fluxo

```
Landing pública / Assinatura.tsx / UsageAlertBanner.tsx / email de aviso
  → GET /checkout/efi/{offer_key}                          (backend-crm)
      → efi_client.create_subscription_link(...)           → POST /v1/plan/:id/subscription/one-step/link
      → 307 redirect → payment_url (página hospedada Efí)
      → cliente preenche nome/CPF/email/telefone/cartão

Efí aprova pagamento
  → POST /webhooks/efi                                     (backend-crm, form-encoded, campo `notification` = token)
      → efi_client.resolve_notification(token)              → GET /v1/notification/:token
      → para cada mudança de status relevante:
          "paid"               → acção "renew"   (cobre 1ª activação e renovações)
          "canceled"/"expired" → acção "cancel"
      → resolve plan_code + email via get_charge/get_subscription (`_resolve_efi_plan_and_email`)
      → POST /internal/subscriptions/payment-event           (backend-core, x-service-token)
          → activa / renova / cancela subscription
          → email desconhecido + activate/renew → cria User + envia email de boas-vindas
```

---

## Checkout sob demanda — `backend-crm/routes/checkout.py`

`GET /checkout/efi/{offer_key}` — não existe link estático reaproveitável; cada acesso gera uma
nova assinatura/link na Efí.

**Ofertas (`_offers()`):**

| `offer_key` | `plan_id` (env) | `plan_code` | Valor |
|---|---|---|---|
| `start` | `EFI_PLAN_ID_START` | `crm_start` | R$97,00 |
| `growth` | `EFI_PLAN_ID_GROWTH` | `crm_growth` | R$197,00 |
| `growth_fundador` | `EFI_PLAN_ID_GROWTH_FUNDADOR` | `crm_growth` | R$147,00 (campanha, landing pública) |

Oferta desconhecida ou sem `plan_id` configurado no ambiente → `404`. Erro ao gerar o link na Efí
→ `502`. Sucesso → `307` para o `payment_url` hospedado da Efí.

`notification_url` enviado à Efí é sempre `{CRM_PUBLIC_BASE_URL}/webhooks/efi` — **depende de
`CRM_PUBLIC_BASE_URL` apontar para um domínio publicamente acessível**, senão a Efí não consegue
notificar o sistema quando o cliente paga.

**Pontos de entrada que usam este endpoint:**
- `website/src/pages/CRMLandingV2.tsx` — CTAs Start/Growth (offer `start`/`growth_fundador`)
- `frontend-crm/src/pages/Assinatura.tsx` — upgrade de plano (offer `start`/`growth`)
- `frontend-crm/src/components/UsageAlertBanner.tsx` — banner de limite atingido (offer `growth`; utilizador já em `crm_growth` é enviado para `/assinatura` em vez de reofertar o mesmo plano)
- `backend-crm/routes/usage.py` — `checkout_links` no payload de `GET /api/usage`
- `backend-core/app/jobs/subscription_jobs.py` — links nos emails de aviso/expiração (`_get_checkout_url`, fallback para `{CRM_FRONTEND_URL}/assinatura` se `CRM_PUBLIC_BASE_URL` não estiver definida)

---

## Cliente Efí — `backend-crm/services/efi_client.py`

Base sandbox `https://cobrancas-h.api.efipay.com.br` / produção `https://cobrancas.api.efipay.com.br`,
selecionada por `EFI_SANDBOX` (default `true`).

**Autenticação:** OAuth2 `client_credentials` via Basic Auth (`EFI_CLIENT_ID`/`EFI_CLIENT_SECRET`)
em `POST /v1/authorize`; `access_token` cacheado em memória (`_token_cache`) até 30s antes de
expirar.

**Funções:**
- `create_plan(name, interval=1, repeats=None)` — `POST /v1/plan`; `repeats=None` = repetições ilimitadas
- `create_subscription_link(plan_id, item_name, value_cents, notification_url, custom_id=None, link_valid_days=30)` — `POST /v1/plan/:id/subscription/one-step/link`; `custom_id` carrega o `plan_code` nos metadados; `settings.request_delivery_address=False`, `settings.expire_at` calculado a partir de `link_valid_days`. Retorna `payment_url`
- `resolve_notification(token)` — `GET /v1/notification/:token`; lista de mudanças de status (charge/subscription)
- `get_charge(charge_id)` — `GET /v1/charge/:id`; inclui `status`, `custom_id` (plan_code) e dados do cliente uma vez paga
- `get_subscription(subscription_id)` — `GET /v1/subscription/:id`; `custom_id` + histórico de cobranças associadas

**Status de cobrança:** `approved` (cartão autorizado, dinheiro ainda não creditado) ≠ `paid`
(liquidação final). O webhook só age em `paid` — recomendação oficial da Efí para liberar acesso.

---

## Webhook — `backend-crm/routes/webhooks.py`

`POST /webhooks/efi` recebe form-encoded com o campo `notification` (token). Resolve as mudanças
via `resolve_notification`, mapeia `status_current` para uma acção (`renew` para `paid`, `cancel`
para `canceled`/`expired`, ignora o resto), e usa `_resolve_efi_plan_and_email(entry)` para obter
`plan_code`/email — tenta primeiro `charge_id` (`get_charge`), cai para `subscription_id`
(`get_subscription` + procura nas cobranças do histórico) quando não há `charge_id` directo (caso
típico de cancelamento).

## Activação — `backend-core/app/api/subscriptions.py`

`POST /internal/subscriptions/payment-event` (`x-service-token`), `payment_event()`:

- Email existente + `activate`/`renew` → cancela sub activa do produto, cria nova (`status=active`, `+30 dias`), retorna `{"action": "activated"}`
- Email **desconhecido** + `activate`/`renew` → cria `User` (senha aleatória 14 chars `ascii+!@#$%`), activa subscription, envia `render_welcome_email`, retorna `{"action": "created_and_activated"}`
- Email desconhecido + `cancel` → `{"action": "skipped", "reason": "user_not_found"}` (não cria conta à toa)
- `plan_code` inexistente → `{"action": "skipped", "reason": "plan_not_found"}`

**Nota de design:** o webhook não distingue com certeza "1ª cobrança" de "renovação" — qualquer
cobrança `paid` gera acção `renew`. `payment_event` já sabia estender uma subscrição activa
existente; foi ensinado a também criar o `User` nesse caminho (antes só em `activate`).

---

## Variáveis de ambiente

| Variável | Onde | Descrição |
|---|---|---|
| `EFI_CLIENT_ID` / `EFI_CLIENT_SECRET` | backend-crm | Credenciais OAuth2 (sandbox ou produção) |
| `EFI_SANDBOX` | backend-crm | `true`/`false` — selecciona a base URL |
| `EFI_PLAN_ID_START` / `EFI_PLAN_ID_GROWTH` / `EFI_PLAN_ID_GROWTH_FUNDADOR` | backend-crm | IDs de plano criados na Efí (`create_plan`); diferem entre sandbox e produção |
| `CRM_PUBLIC_BASE_URL` | backend-crm, backend-core | URL pública do backend-crm — usada para montar `notification_url` (checkout) e os links de checkout nos emails (`subscription_jobs.py`); precisa ser acessível pela internet para a Efí conseguir notificar pagamentos |

---

## Alertas de consumo e checkout no `/api/usage`

`GET /api/usage` (`backend-crm/routes/usage.py`) inclui `checkout_links: { crm_start, crm_growth }`
apontando para `{CRM_PUBLIC_BASE_URL}/checkout/efi/{start|growth}`.
