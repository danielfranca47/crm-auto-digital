# Reembolso — botão no painel admin (MVP)

**Branch:** `main`
**Status:** Fase 1 implementada e testada ao vivo (browser + sandbox real) — falta apenas
confirmar um reembolso realmente bem-sucedido, o que só é observável com uma cobrança `paid` em
produção (ver nota no Cenário P1)

---

## Motivação

A landing (`CRMLandingV2.tsx`) promete garantia de reembolso ("30 dias, sem perguntas"), mas não
existe nenhum processo de reembolso implementado — nem chamada à API da Efí, nem ação no painel
admin. O utilizador pediu, por ordem de prioridade:

1. **Agora:** uma área no painel admin com um botão para estornar (reembolsar + cancelar acesso).
2. **Futuro (fora do escopo desta implementação):** automatizar o reembolso dos 7 dias via um
   agente que lê emails de pedido de reembolso e confirma dados do cliente quando não for
   possível identificar automaticamente.
3. **Futuro (fora do escopo desta implementação):** para os 30 dias, um "chamado" visível por
   email e no painel admin para a equipa contactar o cliente e também poder acionar o reembolso
   a partir daí.

Este documento cobre só o item 1.

---

## Pesquisa — API de reembolso da Efí

- **Endpoint:** `POST /v1/charge/card/:id/refund` (mesma base já usada por `efi_client.py`)
- **Body:** `{"amount": <centavos>}` opcional — omitido = reembolso total
- **Restrições:**
  - Cobrança tem de estar com status `paid` (não `approved`)
  - Só um pedido de reembolso simultâneo por cobrança
  - Só um reembolso parcial por dia por cobrança
  - Reembolso parcial: até 90 dias após confirmação do pagamento
  - Reembolso total: até 360 dias após confirmação do pagamento
  - Só para cartão de crédito, não disponível para vendas em marketplace
- Reembolsa a **cobrança** (`charge_id`), não a assinatura em si — cancelar a recorrência futura
  é uma ação separada (`payment_event`, `action=cancel`), já existente.
- Fonte: `dev.efipay.com.br/en/docs/api-cobrancas/cartao/` + comunidade Efí.

**Lacuna encontrada:** não guardávamos `charge_id` de nenhuma assinatura — o webhook já recebe
esse dado mas descartava-o. Sem isso, um admin teria de procurar manualmente o `charge_id` no
painel da Efí antes de conseguir reembolsar.

---

## Abordagem

```
Admin clica "Reembolsar" (AdminUsers.tsx)
  → POST /admin/billing/refund {email}         (backend-crm, JWT admin)
      → GET /internal/subscriptions/by-email/{email}   (backend-core, service token)
          → devolve efi_charge_id da subscrição activa
      → efi_client.refund_charge(efi_charge_id)         → POST /v1/charge/card/:id/refund
      → POST /internal/subscriptions/payment-event (action=cancel)   (backend-core)
      → retorna {ok, refunded, plan_code}
```

---

## Plano de Implementação

### Fase 1 — charge_id persistido + endpoint de reembolso + botão admin

| Arquivo | O que muda |
|---|---|
| `backend-crm/routes/webhooks.py` | extrai `charge_id` da notificação e propaga no POST ao core |
| `backend-core/app/models/subscription.py` | coluna `efi_charge_id` (Integer, nullable) |
| `backend-core/app/db.py` | migração idempotente |
| `backend-core/app/api/subscriptions.py` | `PaymentEventRequest.charge_id`; grava/actualiza; novo `GET /internal/subscriptions/by-email/{email}` |
| `backend-crm/services/efi_client.py` | nova `refund_charge()` |
| `backend-crm/routes/admin_billing.py` *(novo)* | `POST /admin/billing/refund` |
| `backend-crm/app.py` | regista o novo router |
| `frontend-admin/src/services/api.ts` | `crmPost` + `refundUser` |
| `frontend-admin/src/pages/AdminUsers.tsx` | botão + diálogo de confirmação |
| `docs/architecture/billing-efi.md` | nova secção "Reembolso" |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `729b711` | charge_id persistido + endpoint de reembolso + botão admin |

---

## Checks de Validação

### Cenário P1 — `refund_charge` funciona contra a Efí real
- [x] Chamada real a `POST /v1/charge/card/:id/refund` (sandbox) com um `charge_id` real de uma
      subscrição de teste criada nesta sessão
- **Validado em:** 04/07/2026 — Efí respondeu `{"error":"invalid_data","error_description":
  "Apenas transações com status [paid] podem ser reembolsadas."}`. Rejeição **esperada** — o
  sandbox da Efí nunca chega a `paid` (só simula `approved`, confirmado em teste anterior desta
  migração). Confirma que a chamada, autenticação e construção do request estão correctas; o
  reembolso de facto só é observável com uma cobrança real em produção.

### Cenário P2 — `charge_id` propagado pelo webhook
- [x] Lógica de extracção (`entry.identifiers.charge_id`, `None` em `cancel`) testada
      isoladamente com 4 casos — todos correctos
- **Validado em:** 04/07/2026 — script Python isolado

### Cenário P3 — Endpoint `by-email` devolve os dados certos
- [x] Revisão de código de `get_subscription_by_email` — query simples (User por email →
      Subscription activa mais recente → Plan), mesmo padrão já usado em `list_my_subscriptions`
- **Validado em:** 04/07/2026 — revisão de código

### Cenário P4 — Fluxo completo local (testado ao vivo via browser)
- [x] Criado utilizador de teste real via `payment_event` (email/plan/charge_id conhecido)
- [x] `GET /internal/subscriptions/by-email` confirmado a devolver o `efi_charge_id` correcto
- [x] Clique real em "Reembolsar" no painel admin (localhost:5174) → `POST /admin/billing/refund`
      → `by-email` → `efi_client.refund_charge` → Efí recusa (`invalid_data`, status ≠ `paid`,
      mesma limitação do sandbox do Cenário P1) → erro repassado, `502`
- [x] Confirmado por `GET /internal/subscriptions/by-email` **depois** da tentativa: a subscrição
      continua `status: "active"` — **não cancelou**, porque o reembolso na Efí falhou. Confirma
      a proteção mais importante do fluxo: só cancela o acesso se o reembolso realmente suceder.
- **Validado em:** 04/07/2026 — teste ao vivo via browser (chrome-devtools MCP), backend-core
  (8001) + backend-crm (8000) + frontend-admin (5174) locais, sandbox real da Efí

### Cenário P5 — UI (testado ao vivo via browser)
- [x] `npx tsc --noEmit` sem erros após as mudanças em `api.ts`/`AdminUsers.tsx`
- [x] Login no painel admin, botão "Reembolsar" aparece na lista de utilizadores
- [x] Clique abre o diálogo de confirmação com o texto de aviso correcto (nome do utilizador,
      aviso "não pode ser desfeito")
- [x] Clique em "Reembolsar e cancelar" → botão muda para "Reembolsando…" → toast de erro aparece
      no canto inferior direito com a mensagem real da Efí — modal permanece aberto (correcto,
      permite tentar de novo ou cancelar)
- **Validado em:** 04/07/2026 — teste ao vivo via browser (chrome-devtools MCP), screenshot
  conferido

---

## Fase 2 — Email de confirmação de cancelamento + correção de doc

### Problema identificado

O utilizador perguntou o que acontece depois de um reembolso bem-sucedido. Ao verificar o código,
`payment_event(action=cancel)` só actualizava a base de dados — **nenhum email era enviado** ao
cliente confirmando o cancelamento. Além disso, `docs/architecture/auth-email.md` já afirmava
(incorretamente, herdado da doc original da Kiwify) que `render_subscription_cancelled_email` era
disparado em `action=cancel` — a função existia em `email_service.py` mas nunca era chamada.
A própria copy do template também estava desatualizada: dizia "o acesso ficará limitado no final
do período actual", mas o cancelamento é sempre imediato (não há período de carência no código).

### Correção

| Arquivo | Mudança |
|---|---|
| `backend-core/app/services/email_service.py` | copy de `render_subscription_cancelled_email` corrigida para "acesso encerrado imediatamente" |
| `backend-core/app/api/subscriptions.py` | `payment_event`, ramo `cancel`: chama `render_subscription_cancelled_email` + `send_email` após o commit (mesmo padrão try/except do email de boas-vindas) |
| `docs/architecture/billing-efi.md`, `auth-email.md` | documentado que `action=cancel` (webhook Efí **ou** reembolso admin) agora envia o email |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `118c519` | email de cancelamento + correção de copy + docs |

### Validação

- [x] Email renderizado localmente — copy confirma "encerrado imediatamente" (antes: "no final do
      período actual", incorreto)
- [x] `action=cancel` testado ao vivo contra backend-core local (mesmo utilizador de teste da
      Fase 1) — resposta `{"ok":true,"action":"cancelled"}`; `GET by-email` confirmou a subscrição
      deixou de estar `active` (cancelamento efectivo)
- **Nota:** o envio de email em si não foi confirmado visualmente (SMTP real do Resend, sem forma
  de inspeccionar a caixa de entrada nesta sessão) — mas o código segue exactamente o padrão já
  comprovado do email de boas-vindas (mesmo `send_email()`, mesmo try/except)
- **Validado em:** 04/07/2026

---

## Fora do Escopo — Futuro

- **Reembolso automático dos 7 dias:** agente que lê emails de pedido de reembolso, tenta
  identificar o cliente automaticamente (por email remetente/dados mencionados), e se não
  conseguir, confirma com o cliente antes de acionar. Depende de um agente de leitura/triagem de
  email ainda não existente no sistema.
- **Fluxo de "chamado" dos 30 dias:** pedidos de reembolso fora da janela incondicional geram um
  chamado visível por email e no painel admin, para a equipa contactar o cliente antes de decidir
  — o botão desta fase poderia ser reaproveitado como a ação final desse fluxo.
- **Reembolso parcial pela UI:** `efi_client.refund_charge` já aceita `amount_cents`, mas o botão
  do MVP só expõe reembolso total.
- **Inconsistência "7 dias" (H1) vs "30 dias" (termos formais) na landing:** identificada numa
  conversa anterior, ainda sem decisão do utilizador sobre qual copy está correta.
