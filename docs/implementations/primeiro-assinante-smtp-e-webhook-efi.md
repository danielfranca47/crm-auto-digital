# Primeiro assinante real — SMTP de produção + correções do webhook Efí

**Branch:** `main`
**Status:** Em andamento — Fase 1 (SMTP) implementada e validada por logs (falta recepção visual,
S2); Fase 2 (correção de dado) executada e validada; Fase 3 (idempotência) aguardando Plan Mode

---

## Contexto

Em 12/08/2026 o sistema recebeu o **primeiro assinante pagante real**: Gabriel Smith Soares
(`gabrielsmith.original@gmail.com`), oferta Growth Fundador (R$147), cartão de crédito, cobrança
única confirmada `paid` na Efí (charge `1048544670`, produção). Ao validar o Cenário C1 pendente
de `email-drip-expiracao-fundador.md` (pagamento real ponta a ponta, nunca antes observado),
foram descobertos 3 problemas — este arquivo documenta a correção dos três.

**O que o pagamento real validou com sucesso** (alimenta o C1 do `email-drip-expiracao-fundador.md`):
- Efí notificou `POST /webhooks/efi` em produção ✅
- `payment_event` criou o User (id=3) e ativou a subscription (plano Growth) ✅
- `custom_id` chegou como `crm_growth__growth_fundador` (separador `__` do hotfix da Fase 3
  daquele arquivo funcionando em produção) ✅

---

## Problemas Identificados (estado anterior)

1. **Nenhum email de produção jamais foi entregue — Railway bloqueia egress SMTP na porta 587:**
   `backend-core` usava `SMTP_PORT=587` (`smtp.resend.com`). A Railway bloqueia as portas SMTP
   padrão (25/465/587) — toda chamada a `send_email()` falhava com `[Errno 110] Connection timed
   out` após ~2 min, engolida pelos `try/except` não-bloqueantes. Consequência concreta: o email
   de boas-vindas com a **senha temporária** do primeiro assinante nunca saiu — cliente pagou e
   ficou sem acesso. Como o padrão é não-bloqueante por design (`auth-email.md`), a falha era
   invisível: `HTTP 200` em tudo, erro só no log.

2. **`current_period_end` inflado 5× por reentregas do webhook:** a subscription do assinante
   ficou com `current_period_end=2027-01-09` (150 dias = exatos 5×30) em vez de ~2026-09-11.
   Causa: a Efí reentregou a notificação da mesma cobrança várias vezes (os logs do backend-crm
   mostram 3 `POST /webhooks/efi` no período, coincidindo com os redeploys da manhã; um deles
   logou `efi_webhook: erro ao chamar core:` — timeout que provavelmente gerou retry da Efí).
   Cada reentrega vira `action=renew` e soma +30 dias em `payment_event`
   (`backend-core/app/api/subscriptions.py`, ramo `renew`). **Não houve cobrança duplicada** —
   confirmado na API da Efí: 1 única charge, `paid_value=14700`.

3. **Sem idempotência por `charge_id` no fluxo webhook → payment_event:** causa estrutural do
   item 2. `efi_webhook` (`backend-crm/routes/webhooks.py`) repassa toda notificação `paid` como
   `renew`, e `payment_event` estende o período incondicionalmente — nada verifica se aquela
   cobrança específica já foi processada, embora o `charge_id` já trafegue no payload e seja
   gravado em `Subscription.efi_charge_id`. Qualquer reentrega futura da Efí (que é comportamento
   normal e esperado de webhook) repetirá o problema com os próximos clientes.

---

## Fase 1 — SMTP de produção: porta 2587 (executada 12/08/2026)

**Objetivo:** emails de produção passam a ser entregues de facto.

**Correção (somente configuração — nenhuma mudança de código):**

| Onde | O que mudou |
|---|---|
| Railway → backend-core → Variables | `SMTP_PORT`: `587` → `2587` (porta alternativa oficial do Resend para ambientes que bloqueiam a 587; executado pelo utilizador via `railway variable set`, redeploy automático 15:48) |
| `backend-core/.env` (local, gitignored) | Alinhado para `2587` — paridade com produção |
| `docs/architecture/auth-email.md` | Tabela de config SMTP atualizada com a exigência da 2587 e o porquê |

**Recuperação do acesso do assinante:** como a senha temporária do email de boas-vindas perdido
não é recuperável (só o hash é guardado), o acesso foi restabelecido via
`POST /auth/forgot-password` — email "Recuperação de senha" com link de reset (validade 2h)
enviado com sucesso após o fix.

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `2f5514e` | docs: SMTP_PORT 2587 obrigatório em produção (Railway bloqueia 587) |

### Checks de Validação — Fase 1

#### Cenário S1 — Envio real de email após o fix
- [x] `POST /auth/forgot-password` para a conta de teste (`autodigital157@gmail.com`) —
      resposta em 1,9s (antes: 2+ min de timeout) e log de produção **sem** a linha
      `Erro ao enviar email de reset`
- [x] `POST /auth/forgot-password` para o assinante real — mesmo padrão, sem erro no log
- **Validado em:** 12/08/2026 — logs Railway do backend-core

#### Cenário S2 — Recepção visual do email
- [ ] Confirmar na caixa de `autodigital157@gmail.com` que o email "Recuperação de senha —
      Digital Pro" chegou (inbox, não spam) e o link funciona
- [ ] Confirmar que o assinante recebeu, redefiniu a senha e conseguiu fazer login
- **Pendente** — depende de verificação humana da caixa de entrada / contacto com o cliente

---

## Fase 2 — Corrigir `current_period_end` do assinante (aguardando execução)

**Objetivo:** a subscription do user id=3 reflete o período realmente pago (30 dias).

**Abordagem aprovada em conceito:** correção de dado direto no SQLite do backend-core
(volume Railway), via `railway ssh` — sem redeploy, sem downtime. Antes do UPDATE, conferir o
`id` exato da subscription e o valor atual; depois do UPDATE, confirmar via
`GET /internal/subscriptions/by-email`.

```sql
UPDATE subscriptions
SET current_period_end = '2026-09-11 11:18:00.652753'  -- 30 dias após a ativação real
WHERE user_id = 3 AND status = 'active';
```

### Checks de Validação — Fase 2

#### Cenário D1 — Período corrigido
- [x] `SELECT` antes: 1 única subscription (id=8) ativa do user 3, end `2027-01-09 11:18:00`
- [x] `UPDATE` executado (guardado por `user_id=3 AND status='active' AND end LIKE '2027-01-09%'`)
      — `updated rows: 1`; `SELECT` depois confirma `2026-09-11 11:18:00`
- [x] `GET /internal/subscriptions/by-email/gabrielsmith.original@gmail.com` devolve
      `current_period_end: 2026-09-11T11:18:00` — a API lê o valor corrigido
- [x] `origin_offer='growth_fundador'` e `efi_charge_id=1048544670` confirmados na linha do DB
      (valida o check correspondente do C1 do `email-drip-expiracao-fundador.md`)
- **Validado em:** 12/08/2026 — UPDATE executado pelo utilizador via `railway ssh` (DB
  `/data/core.db`), verificação HTTP pelo Claude

---

## Fase 3 — Idempotência por `charge_id` no webhook Efí (aguardando Plan Mode)

**Objetivo:** reentregas da mesma notificação/cobrança não somam períodos extra.

**Rascunho de abordagem (a confirmar em Plan Mode — não substitui o diagnóstico obrigatório):**
no ramo `renew` de `payment_event` (`backend-core/app/api/subscriptions.py`), se
`payload.charge_id` for igual ao `efi_charge_id` já gravado na subscription ativa, tratar como
reentrega: não estender o período (retornar `{"action": "skipped", "reason": "duplicate_charge"}`).
A verificação natural fica no backend-core porque é lá que o estado (`efi_charge_id`) vive;
o `efi_webhook` do backend-crm continua stateless.

**Pontos a validar em Plan Mode:**
- Cobrança sem `charge_id` (payload antigo/cancel) não pode ser bloqueada por engano
- Renovação legítima mensal chega com `charge_id` **novo** — não pode ser confundida com reentrega
- O que fazer quando não há subscription ativa (1ª ativação) — caminho atual já cobre

---

## Ajustes Possíveis Pós-Implementação

### Investigações preventivas a abrir (1 por item — para garantir que não ocorram de novo)

- **Investigação 1 (derivada do problema SMTP): auditoria de falhas silenciosas e dependências
  externas em produção.** O SMTP falhou 100% das vezes durante semanas sem nenhum sinal além de
  uma linha de log que ninguém lia. Mapear: (a) todos os pontos com padrão `try/except` que
  engolem falha de serviço externo (SMTP, UazAPI, Efí, LLM) e definir alerta/notificação admin
  quando a taxa de falha for anómala; (b) que outras portas/egress a Railway restringe que o
  sistema assume abertas; (c) validar entrega real (não só "sem erro no log") de cada tipo de
  email de produção.

- **Investigação 2 (derivada do período inflado): auditoria de efeitos de reentrega em todos os
  handlers de webhook.** A Efí reentrega notificações por design — mapear todos os webhooks do
  sistema (`/webhooks/efi`, `/webhooks/payment/{gateway}`, `/webhooks/whatsapp/*`) e verificar,
  para cada um, o que acontece se o mesmo evento chegar 2–5×: que estado é duplicado/inflado,
  que jobs são re-enfileirados, que emails são reenviados. Documentar a garantia (ou falta dela)
  por endpoint.

- **Investigação 3 (derivada da falta de idempotência): política de idempotência padrão para
  eventos externos.** Além do fix pontual da Fase 3, definir uma convenção única do projeto para
  processar eventos externos exatamente-uma-vez (chave de dedup por evento — ex.: `charge_id`,
  `message_id` — e onde ela é persistida), a aplicar em qualquer webhook/integração futura, para
  o problema não renascer a cada endpoint novo.

### Outros ajustes

- **Migrar para a API HTTP do Resend** (porta 443, imune a bloqueio de egress SMTP) — a chave já
  está no ambiente (`SMTP_PASS`). Alternativa mais robusta que depender da 2587.
- **Reprocessamento dos emails perdidos:** qualquer email de produção anterior a 12/08 nunca
  chegou (boas-vindas, avisos de expiração). Hoje só há 3 users (2 internos + o assinante, já
  tratado) — nada mais a reenviar. Registado apenas como contexto histórico.
