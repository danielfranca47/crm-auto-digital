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

| `offer_key` | `plan_id` (env) | `plan_code` | Valor | Uso |
|---|---|---|---|---|
| `start` | `EFI_PLAN_ID_START` | `crm_start` | R$97,00 | checkout Start |
| `growth` | `EFI_PLAN_ID_GROWTH` | `crm_growth` | R$297,00 | preço tabelado normal — upgrade dentro do CRM, venda directa |
| `growth_founder_renewal` | `EFI_PLAN_ID_GROWTH` (mesmo plan_id do `growth`) | `crm_growth` | R$197,00 | condição travada, exclusiva do email de renovação do Fundador |
| `growth_fundador` | `EFI_PLAN_ID_GROWTH_FUNDADOR` | `crm_growth` | R$147,00 (12x) | campanha, landing pública |

**Nota importante:** o `plan_id` da Efí só define a recorrência (intervalo + nº de repetições) —
**não** o valor cobrado. Por isso `growth` e `growth_founder_renewal` reaproveitam o mesmo
`plan_id` (ambos mensais, ilimitados); o preço vem de `value_cents`, definido por oferta em
`_offers()`. Não é preciso criar um plano novo na Efí para cada preço.

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

**`custom_id` — plan_code + origem da oferta:** `create_subscription_link` recebe
`custom_id=f"{plan_code}__{offer_key}"` (ex.: `"crm_growth__growth_fundador"`, `"crm_growth__growth"`).
Separador `__`, não `:` — a Efí valida `custom_id` contra `^[a-zA-Z0-9_-\s]+$` e rejeita `:` com
`500 validation_error` (descoberto em produção: os 4 checkouts pararam de funcionar até a
correcção). É o único campo comprovado a ida-e-volta pela Efí (`get_charge`/`get_subscription`
devolvem-no tal qual). O webhook decompõe isto (`_split_custom_id` em `webhooks.py`) para obter
`plan_code` e `origin_offer` separadamente — `origin_offer` é gravado na `Subscription` e usado
para escolher a copy do email de aviso de expiração (ver "Ciclo de vida de avisos" abaixo). Formato
antigo (sem `__`, de assinaturas criadas antes desta convenção) é tratado como `origin_offer=None`.

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
`plan_code`/`origin_offer`/email (via `_split_custom_id`, ver acima) — tenta primeiro `charge_id`
(`get_charge`), cai para `subscription_id` (`get_subscription` + procura nas cobranças do
histórico) quando não há `charge_id` directo (caso típico de cancelamento). `origin_offer` é
incluído no `POST /internal/subscriptions/payment-event`. Em `activate`/`renew`, o `charge_id` da
própria notificação (`entry.identifiers.charge_id`) também é incluído no payload — é gravado na
`Subscription` para permitir reembolso futuro (ver "Reembolso" abaixo). Em `cancel` não há
cobrança nova, por isso não é enviado.

## Activação — `backend-core/app/api/subscriptions.py`

`POST /internal/subscriptions/payment-event` (`x-service-token`), `payment_event()` — payload
`{email, plan_code, action, origin_offer}` (`origin_offer` opcional):

- Email existente + `activate`/`renew` → cancela sub activa do produto, cria nova (`status=active`, `+30 dias`, `origin_offer=payload.origin_offer`), retorna `{"action": "activated"}`
- Email **desconhecido** + `activate`/`renew` → cria `User` (senha aleatória 14 chars `ascii+!@#$%`), activa subscription, envia `render_welcome_email`, retorna `{"action": "created_and_activated"}`
- Email desconhecido + `cancel` → `{"action": "skipped", "reason": "user_not_found"}` (não cria conta à toa)
- Email existente + `cancel` → cancela a sub activa do plano, envia `render_subscription_cancelled_email` ao cliente, retorna `{"action": "cancelled"}`
- `plan_code` inexistente → `{"action": "skipped", "reason": "plan_not_found"}`
- Renovação de sub já activa: se `sub.origin_offer` ainda não estiver definido, faz backfill com
  `payload.origin_offer` (cobre assinaturas activas antes desta convenção existir)
- `charge_id` (opcional) é gravado/actualizado em `Subscription.efi_charge_id` — sempre a cobrança
  mais recente, tanto na criação quanto em cada renovação
- **Idempotência por `charge_id` (ramo `renew`):** se `payload.charge_id` for igual ao
  `efi_charge_id` já gravado na sub activa, a chamada é tratada como **reentrega** da mesma
  notificação (a Efí reenvia webhooks por design) e devolve
  `{"action": "skipped", "reason": "duplicate_charge"}` **sem estender o período**. Sem
  `charge_id` no payload (ou sub pré-feature sem `efi_charge_id`) não há base para dedup e o
  comportamento é o normal. Limitação aceite: só a cobrança mais recente é guardada — uma
  reentrega antiga que chegue *depois* de uma cobrança nova legítima não é detectada (janela
  desprezível: reentregas ocorrem em minutos/horas, renovações são mensais)

---

## Reembolso

**Endpoint Efí:** `POST /v1/charge/card/{charge_id}/refund` (`backend-crm/services/efi_client.py`,
`refund_charge(charge_id, amount_cents=None)`). `amount_cents=None` → reembolso total.

**Restrições da Efí** (rejeitam com erro se violadas):
- Cobrança tem de estar com status `paid` (não `approved` — ver nota de status acima)
- Só um pedido de reembolso simultâneo por cobrança; só um reembolso parcial por dia por cobrança
- Reembolso parcial: até 90 dias após pagamento; reembolso total: até 360 dias
- Só cartão de crédito, não disponível para vendas em marketplace

**Fluxo (MVP, reembolso total via painel admin):**
```
Admin clica "Reembolsar" (frontend-admin, AdminUsers.tsx)
  → POST /admin/billing/refund {email}              (backend-crm, routes/admin_billing.py, JWT admin via require_crm_admin)
      → GET /internal/subscriptions/by-email/{email}      (backend-core) → efi_charge_id
      → efi_client.refund_charge(efi_charge_id)           → POST /v1/charge/card/:id/refund
      → POST /internal/subscriptions/payment-event (action=cancel)   (backend-core) — cancela o
        acesso imediatamente e envia render_subscription_cancelled_email ao cliente
      → devolve {ok, refunded, plan_code}
```

Sem `efi_charge_id` gravado (assinatura anterior a esta funcionalidade) → `422`, mensagem indica
reembolso manual no painel da Efí. Erro da Efí (fora da janela, já reembolsado, status inválido)
→ `502` com a mensagem de erro dela repassada directamente (não uma mensagem genérica) — nesse
caso `action=cancel` nunca é chamado, a subscrição permanece activa.

**Fora do escopo actual** (ver `docs/implementations/refund-admin-mvp.md`): automação do
reembolso dos 7 dias via agente de email, fluxo de "chamado" dos 30 dias, reembolso parcial pela
UI (a função já suporta, só não é exposta no botão).

---

## Ciclo de vida de avisos de expiração — `backend-core/app/jobs/subscription_jobs.py`

Job diário (ver `auth-email.md` para o agendamento) manda um aviso em cada um destes pontos antes
de `current_period_end`, do menos ao mais urgente: **30, 15, 7, 3, 2, 1, 0 dias**.

- `Subscription.expiry_warning_stage` (Integer, nullable) guarda o estágio mais urgente já
  enviado no período actual — impede reenvio do mesmo estágio ou de um menos urgente.
- **Reposto a `None` a cada renovação bem-sucedida** (`payment_event`, ramo `renew`) — o ciclo de
  avisos recomeça no novo período.
- Copy do email (`render_subscription_expiring_email`, `email_service.py`) varia por:
  - **Tom** (`days_remaining`): calmo (30/15) · atenção (7/3/2) · último aviso (1/0)
  - **Origem** (`origin_offer == "growth_fundador"`): copy de transição de preço ("trava o teu
    preço de fundador em R$197/mês para sempre — novos clientes pagam R$297/mês") vs. copy
    informativa genérica ("a tua Lara renova em breve", pensada como rede de segurança para
    assinaturas normais que já renovam automaticamente via Efí)
- **Link de checkout correcto por origem:** `_get_checkout_url(plan_code, origin_offer)` — quando
  `plan_code == "crm_growth"` e `origin_offer == "growth_fundador"`, usa o offer
  `growth_founder_renewal` (R$197, condição travada); qualquer outro caso usa `growth` (R$297,
  preço normal). Aplica-se tanto ao aviso antecipado quanto ao email final de "expirado" — um
  Fundador que reactive a qualquer momento pelo link do email mantém o preço travado; só voltando
  a assinar do zero pelo checkout público (sem esse contexto) é que pagaria R$297.

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
