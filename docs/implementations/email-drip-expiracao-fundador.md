# Email de expiração multi-estágio + copy de transição Fundador

**Branch:** `main`
**Status:** Todos os cenários validados

---

## Motivação

O job diário de subscriptions manda um único email de aviso, 3 dias antes de expirar, com copy
genérica ("o teu plano expira, renova agora"). Isso não serve bem o caso da campanha "Growth
Fundador" (12 cobranças a R$147/mês, depois o cliente precisa de subscrever o Growth normal a
R$197/mês, sem prazo) — o cliente recebe um aviso de expiração comum, sem entender que é uma
transição de preço esperada, não uma falha.

O utilizador pediu para (1) ajustar a copy para deixar isso claro e (2) esticar o fluxo de avisos
para vários pontos no tempo: 30, 15, 7, 3, 2, 1 dias antes, e um no próprio dia.

---

## Problemas Identificados (estado anterior)

1. **Sem forma de identificar a origem Fundador:** `Subscription.plan_code` é o mesmo
   (`crm_growth`) para o Growth normal e para o Growth Fundador — o sistema não tinha como saber
   qual copy mandar.
2. **`expiry_warning_sent` nunca é reposto a `False`** (`backend-core/app/models/subscription.py:20`,
   usado em `backend-core/app/jobs/subscription_jobs.py:96`) — um cliente que renove várias vezes
   só recebe o aviso de expiração uma única vez em toda a vida da conta. Bug latente, nunca
   reportado porque a maioria das assinaturas ainda não completou vários ciclos.
3. **Um único ponto de aviso (3 dias antes)** — não dá antecedência suficiente para o cliente
   Fundador decidir se quer continuar ao preço normal.

---

## Abordagem

```
Checkout (offer_key: start | growth | growth_fundador)
  → custom_id enviado à Efí passa a "{plan_code}:{offer_key}" (ex.: "crm_growth:growth_fundador")

Webhook Efí → _resolve_efi_plan_and_email decompõe custom_id em (plan_code, origin_offer)
  → POST /internal/subscriptions/payment-event inclui origin_offer

payment_event grava origin_offer na Subscription (na criação, ou por backfill na renovação)

Job diário, por assinatura activa:
  days_remaining = (current_period_end - hoje).dias
  estágio_aplicável = menor threshold em [0,1,2,3,7,15,30] >= days_remaining
  se estágio_aplicável < último_estágio_enviado (ou nunca enviado):
      manda email (tom por days_remaining, copy por origin_offer == "growth_fundador")
      grava expiry_warning_stage = estágio_aplicável

Renovação bem-sucedida (payment_event, action=renew):
  repõe expiry_warning_stage = None (corrige o bug do item 2 acima)
```

---

## Plano de Implementação

### Fase 1 — origin_offer, colunas novas, drip multi-estágio, copy

**Objetivo:** o sistema sabe distinguir Fundador de Growth normal, manda avisos em vários pontos
no tempo, e a copy explica a transição de preço quando aplicável.

| Arquivo | O que muda |
|---|---|
| `backend-crm/routes/checkout.py` | `custom_id` passa a `"{plan_code}:{offer_key}"` |
| `backend-crm/routes/webhooks.py` | `_resolve_efi_plan_and_email` devolve `(plan_code, origin_offer, email)`; `efi_webhook` propaga `origin_offer` no POST ao core |
| `backend-core/app/api/subscriptions.py` | `PaymentEventRequest.origin_offer`; grava na criação, faz backfill na renovação; reset de `expiry_warning_stage` ao estender `current_period_end` |
| `backend-core/app/models/subscription.py` | colunas `origin_offer` (String, nullable) e `expiry_warning_stage` (Integer, nullable) |
| `backend-core/app/db.py` | `ensure_subscription_columns()` — `ALTER TABLE` idempotente para as 2 colunas |
| `backend-core/app/services/email_service.py` | `render_subscription_expiring_email` ganha `days_remaining` e `is_founder_transition`; 3 tons (calmo/atenção/último aviso) × 2 variantes de copy |
| `backend-core/app/jobs/subscription_jobs.py` | loop de thresholds `[0,1,2,3,7,15,30]` substitui o booleano único |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `28426a4` | origin_offer + drip multi-estágio + copy Fundador/Normal |

---

## Checks de Validação

### Cenário P1 — Threshold aplicável calculado corretamente
- [x] Simulação isolada da lógica de threshold com `days_remaining` em
      35/30/29/15/7/3/2/1/0/-1/5 e diferentes `last_stage` — todos os 11 casos bateram com o
      esperado (30 disparado uma vez, ignorado no dia seguinte até baixar de estágio, -1 ignorado
      por já cair na Parte 1, 5 dias cai corretamente no estágio 7)
- **Validado em:** 04/07/2026 — script Python isolado (`.venv` do backend-core)

### Cenário P2 — Reset de `expiry_warning_stage` na renovação
- [x] Revisão de código: no ramo `renew` de `payment_event`, `sub.expiry_warning_stage = None` é
      atribuído incondicionalmente sempre que uma sub activa é encontrada e o período é
      estendido — antes de `db.commit()`
- **Validado em:** 04/07/2026 — revisão de código (mudança de uma linha, comportamento óbvio)

### Cenário P3 — `origin_offer` propagado ponta a ponta
- [x] `_split_custom_id` testado isoladamente: `"crm_growth:growth_fundador"` →
      `("crm_growth", "growth_fundador")`; formato antigo sem `:` → `origin_offer=None`
      (retrocompatível); `None`/`""` → `(None, None)`
- [x] `routes/checkout.py` gera `custom_id=f'{plan_code}:{offer_key}'` — confirmado por leitura
      directa do código editado
- **Validado em:** 04/07/2026 — script Python isolado + revisão de código

### Cenário P4 — Copy revisada
- [x] Renderizados os 6 templates (3 tons × 2 origens) com `render_subscription_expiring_email` —
      texto lido integralmente
- [x] Fundador explica a transição de preço (R$147 fundador → R$197 normal); Normal usa tom
      informativo, sem alarmar ("a tua Lara renova em breve" em vez de "vai parar")
- **Validado em:** 04/07/2026 — script Python isolado, saída revista integralmente

---

## Fase 2 — Correcção de preço: R$297 normal vs. R$197 travado do Fundador

### Problema identificado

A landing (`CRMLandingV2.tsx`) promete R$147/mês nos primeiros 12 meses e depois **R$197/mês
para sempre, preço travado, exclusivo do Fundador** — novos clientes pagam **R$297/mês** (preço
tabelado normal do Growth). A Fase 1 desta feature usava R$197 tanto para a renovação do Fundador
quanto para qualquer upgrade normal dentro do CRM (`Assinatura.tsx`, `UsageAlertBanner.tsx`) —
ou seja, qualquer cliente Start que fizesse upgrade para Growth pagaria R$197 em vez de R$297. A
copy do email também chamava R$197 de "valor normal", quando é a condição especial travada.

**Achado durante a implementação:** o `plan_id` da Efí só define a recorrência (intervalo +
repetições) — o valor cobrado é definido por `value_cents` na hora de gerar o link de checkout,
não no plano. Não foi preciso criar nenhum plano novo na Efí — bastou reaproveitar o `plan_id` do
"growth" já existente para os dois preços.

### Correcção

| Arquivo | Mudança |
|---|---|
| `backend-crm/routes/checkout.py` | oferta `growth` passa a R$297; nova oferta `growth_founder_renewal` (mesmo `plan_id`) a R$197 |
| `backend-core/app/jobs/subscription_jobs.py` | `_get_checkout_url` ganha `origin_offer`; Fundador → `growth_founder_renewal`, resto → `growth` |
| `backend-core/app/services/email_service.py` | copy Fundador corrigida: R$197 é "preço travado para sempre", R$297 é o preço de novos clientes |
| `docs/architecture/billing-efi.md` | tabela de ofertas actualizada + nota sobre plan_id vs. valor |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | *(a registar após o commit)* | correção de preço R$297/R$197 + copy + doc |

---

## Ajustes Possíveis Pós-Implementação

- Nenhuma mudança no fluxo de cobrança em si nem no email de "expirado" — apenas nos avisos
  antecipados e no link de checkout usado.
- Se no futuro existirem mais campanhas com preço promocional temporário, o mesmo mecanismo de
  `origin_offer` serve — só é preciso adicionar a nova copy correspondente.
