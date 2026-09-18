# Verificação periódica de saúde das conexões WhatsApp (a cada 6h)

---

**Branch:** `feat/whatsapp-connection-health-check`
**Status:** Em andamento

---

## Motivação

O backend-core só descobre que uma sessão WhatsApp morreu do lado da UazAPI
quando o webhook `connection` avisa. Essa limitação já estava documentada em
`docs/architecture/whatsapp-connection.md` ("Deteção de queda de sessão"):
*"depender da entrega do webhook, sem verificação periódica independente
ainda"*.

Isso causou um incidente real: a instância `crm-2-b089460e`
(`autodigital157@gmail.com`) morreu na UazAPI (401 em qualquer chamada) sem
nenhum webhook avisar — o banco continuou achando que estava tudo bem até o
usuário tentar reconectar manualmente e esbarrar num bug separado (fora
desta implementação). Pedido do usuário: um job que rode a cada 6 horas,
pergunte pra UazAPI se cada conexão marcada como ativa no nosso banco ainda
está viva de verdade, e corrija o status quando não estiver.

---

## Problemas Identificados (estado anterior)

1. **Sem verificação periódica:** `backend-core/app/main.py:67-81` — o único
   job agendado no sistema é o de expiração de assinaturas
   (`run_daily_subscription_jobs`). Nada verifica proativamente se as
   conexões WhatsApp continuam vivas na UazAPI.

2. **Lógica de email presa no webhook:** `backend-core/app/api/whatsapp_instances.py:356-463`
   (`connection_event`) — a detecção de transição ativo↔inativo, o cooldown
   de 30min e o disparo dos emails de desconexão/reconexão estão embutidos
   direto no handler da rota de webhook, sem forma de reaproveitar a partir
   de um contexto diferente (como um job agendado) sem duplicar ~70 linhas.

---

## Abordagem

```
APScheduler (a cada 6h, UTC 00/06/12/18)
  → run_whatsapp_connection_check()  [novo: app/jobs/whatsapp_connection_check_jobs.py]
      → busca todas as WhatsappConnection com status normalizado = "active"
      → para cada uma (com pausa de 0.3s entre chamadas):
          → decrypt_secret(instance_token_encrypted)
          → uazapi_admin.get_status(...)
              ├─ 401 (token morto)         → apply_connection_status_change(db, conn, "disconnected")
              ├─ status extraído da UazAPI → apply_connection_status_change(db, conn, status)
              └─ outro erro (timeout/5xx/429 esgotado) → loga e pula, tenta no próximo ciclo
      → retorna sumário {checked, marked_dead, errors, ran_at}

apply_connection_status_change(db, connection, new_status)  [novo, extraído do webhook]
  → em app/services/whatsapp_connections.py
  → detecta transição ativo↔inativo (normalize_connection_status_for_crm, já existe)
  → grava novo status, dispara email de desconexão/reconexão com o mesmo
    cooldown de 30min que já existe hoje
  → usado tanto pelo webhook (connection_event) quanto pelo job novo
```

---

## Plano de Implementação

### Fase 1 — Extrair lógica de status/email para função reutilizável

**Objetivo:** refactor puro, sem mudança de comportamento — pré-requisito para a Fase 2.

| Arquivo | O que muda |
|---|---|
| `backend-core/app/services/whatsapp_connections.py` | Nova função `apply_connection_status_change(db, connection, new_status)` — move a lógica de `whatsapp_instances.py:380-461` (transição, cooldown, os dois emails, updates de `disconnect_alert_sent_at`/`last_disconnect_email_at`) quase verbatim |
| `backend-core/app/api/whatsapp_instances.py` | `connection_event()` passa a só extrair `status_value` e chamar `connections_service.apply_connection_status_change(db, connection, status_value)` — remove ~70 linhas duplicadas |

### Fase 2 — Job periódico + registro no scheduler + trigger manual

**Objetivo:** rodar a verificação a cada 6h e permitir disparo manual para validar

| Arquivo | O que muda |
|---|---|
| `backend-core/app/jobs/whatsapp_connection_check_jobs.py` (novo) | `run_whatsapp_connection_check() -> dict` — mesmo padrão de `run_daily_subscription_jobs`; roda `asyncio.run(...)` por dentro; erro tratado por conexão, não aborta o lote |
| `backend-core/app/main.py` | Registra `run_whatsapp_connection_check` no `_scheduler` já existente, `CronTrigger(hour="0,6,12,18", minute=0, timezone="UTC")` — sem chamada síncrona no startup |
| `backend-core/app/api/cron.py` | Nova rota `POST /admin/cron/whatsapp-connection-check` (mesmo padrão de `/admin/cron/daily`) para validar sem esperar 6h |

---

## Checks de Validação

### Cenário P1 — Webhook continua funcionando após o refactor da Fase 1
- [ ] Desconectar e reconectar uma instância de teste
- [ ] Confirmar: os dois emails (queda e retorno) continuam disparando, com o cooldown de 30min intacto

### Cenário C1 — Job não mexe em conexão saudável
- [ ] Chamar `POST /admin/cron/whatsapp-connection-check` com uma conexão real e saudável no banco
- [ ] Confirmar: sumário mostra `marked_dead: 0`, nenhum email disparado, status inalterado

### Cenário C2 — Job detecta conexão morta e dispara alerta
- [ ] Chamar o trigger manual com uma conexão cujo token a UazAPI não reconhece mais
- [ ] Confirmar: sumário mostra `marked_dead: 1`, status vira `disconnected` no banco, email de desconexão chega, banner aparece no frontend-crm

### Cenário C3 — Agendamento automático funciona
- [ ] Confirmar nos logs do Railway (`backend-core`) que o job roda sozinho nos horários 00:00/06:00/12:00/18:00 UTC

---

## Ajustes Possíveis Pós-Implementação

- Hoje o job só detecta conexões que estavam "ativas" no banco e morreram — não tenta redescobrir conexões marcadas como `disconnected` que voltaram a ficar vivas sem passar pelo webhook. Se isso virar um problema real, dá pra estender o escopo da query.
