# Alerta de desconexão do WhatsApp

**Branch:** `fix/alerta-desconexao-whatsapp`
**Status:** Em andamento

---

## Motivação

Dois usuários em produção (gabrielsmith.original@gmail.com,
aydebarbaraqod@gmail.com) reportaram que o agente para de responder no dia
seguinte à conexão via QR code, mesmo com o aparelho ainda listado como
"conectado" no WhatsApp do telemóvel do cliente.

Causa raiz identificada: a UazAPI já é instruída a avisar sobre dois tipos de
evento — `"messages"` e `"connection"` — sempre que um cliente
conecta/reconecta (`backend-crm/routes/whatsapp_connect.py:198`). Ou seja, a
UazAPI já envia um evento `connection` quando a sessão cai — só que o endpoint
que recebe o webhook descartava qualquer evento fora de
`{"messages", "message"}` (`backend-crm/routes/webhooks.py:248`):

```python
if event not in {"messages", "message"}:
    return {"status": "ignored", "reason": "event_not_messages"}
```

Consequência dupla: (1) `WhatsappConnection.status` (backend-core) nunca era
atualizado quando a sessão caía de verdade — ficava congelado em
"conectado"/"active" indefinidamente, porque o único outro caminho de escrita
é sob demanda (`GET /whatsapp-instances/status`, chamado só enquanto a tela de
Conexão está aberta com QR pendente); (2) ninguém era avisado — nem o cliente,
nem o admin. Quando o envio de mensagem falhava por causa disso, o executor
tentava de novo até 3x e desistia silenciosamente (só log técnico,
`backend-executors/app/runners/whatsapp.py:1086-1094`).

**Nota operacional (fora do código):** esta correção é só para daqui para a
frente — não reenvia sozinha um evento `connection` para conexões que já
caíram no passado (a UazAPI não reenvia webhooks antigos). Para os dois
usuários já afetados, o passo prático é pedir para eles reconectarem agora.

---

## Problemas Identificados (estado anterior)

1. **Evento `connection` descartado:** `backend-crm/routes/webhooks.py:248` —
   qualquer evento fora de `{"messages","message"}` retorna `ignored` sem
   nenhuma ação, incluindo o evento `connection` que a própria UazAPI já
   envia.
2. **Status da conexão nunca atualizado em segundo plano:**
   `backend-core/app/models/whatsapp_connection.py` — `status` só é escrito em
   `init`/`connect` (na resposta da UazAPI) ou sob demanda em
   `GET /whatsapp-instances/status`. Sem processo em segundo plano, fica
   "congelado".
3. **Nenhum alerta ao usuário:** falhas de envio por conexão inativa
   (`backend-executors/app/runners/whatsapp.py:1077-1094`) só geram log
   técnico — o cliente não é avisado para reconectar.

---

## Abordagem

```
UazAPI → POST /webhooks/whatsapp/uazapi   (event="connection")
  → backend-crm (routes/webhooks.py):
      loga payload bruto (formato do evento connection não documentado hoje)
      → core_client.report_whatsapp_connection_event(instance_id, raw_payload)
          → backend-core: POST /whatsapp-instances/connection-event (novo,
            protegido por X-Service-Token)
              → uazapi_admin.extract_connection_meta(raw) → status_value
              → connections_service.get_connection_by_instance(instance_id)
              → compara normalize_connection_status_for_crm(status ANTES)
                vs (status DEPOIS)
              → grava o novo status sempre (corrige o "congelamento")
              → SE a transição foi active → inactive:
                  busca User pelo user_id da connection
                  renderiza + envia email (best-effort, try/except)
  ← sempre 200 para a UazAPI (mesmo se o core estiver fora, best-effort)
```

Email dispara só na transição active→inactive (não em todo evento
"disconnected" repetido) — o segundo evento já vê o status local como
"inactive" e não repete o envio. Reconexões (inactive→active) só atualizam o
status, sem email de confirmação.

---

## Plano de Implementação

### Fase 1 — Processar evento connection + alertar por email

**Objetivo:** parar de descartar o evento `connection` da UazAPI, manter o
status real da conexão atualizado, e avisar o dono da conta por email quando
a sessão cai.

| Arquivo | O que muda |
|---|---|
| `backend-crm/routes/webhooks.py` | Trata `event == "connection"` antes do filtro que descarta eventos não-`messages`: loga payload, chama `core_client.report_whatsapp_connection_event`, sempre responde 200 |
| `backend-crm/core_client.py` | Nova função `report_whatsapp_connection_event(instance_id, raw_payload)` |
| `backend-core/app/api/whatsapp_instances.py` | Nova rota `POST /whatsapp-instances/connection-event` (service-token) |
| `backend-core/app/services/email_service.py` | Nova `render_whatsapp_disconnected_email(name, login_url)` |

---

## Checks de Validação

### Cenário C1 — Evento connection com sessão caída atualiza status e envia email
- [ ] Com uma connection existente no banco do backend-core com `status="active"`
- [ ] Simular `POST /webhooks/whatsapp/uazapi?secret=...` com `event="connection"`
      e payload indicando desconectado
- [ ] Confirmar: `WhatsappConnection.status` deixou de normalizar como "active"
- [ ] Confirmar: tentativa de envio de email ocorreu (log), sem quebrar a resposta 200

### Cenário C2 — Evento repetido não duplica o email
- [ ] Repetir o mesmo evento "disconnected" duas vezes seguidas
- [ ] Confirmar: o disparo de email só ocorre na primeira vez

### Cenário C3 — Produção (payload real)
- [ ] Observar nos logs de produção o payload bruto real de um evento
      `connection` da UazAPI, confirmando que `extract_connection_meta`
      extrai `status_value` corretamente

---

## Ajustes Possíveis Pós-Implementação

- **Verificação periódica de status (health-check)** — rede de segurança para
  o caso de o webhook não ser entregue. Prioridade urgente — ver
  `docs/implementations/whatsapp-status-healthcheck.md`.
- Notificação de "reconectado com sucesso" (inactive→active) — silencioso por
  agora.
- UI in-app (sino/notificação no CRM) — o sistema de notificações hoje é
  100% lead-cêntrico; construir uma superfície de notificação de conta é
  escopo maior, fora desta iteração.
- Cooldown/rate-limit de email além do que a lógica de transição já garante
  naturalmente.
