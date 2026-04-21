# Webhook WhatsApp Inbound

## Pipeline completo (inbound)

```
WhatsApp → UazAPI → POST /webhooks/whatsapp/inbound (backend-crm)
  → services/whatsapp_inbound/inbound_handler.py
  → services/whatsapp_inbound/guardrail.py       # verifica se deve responder
  → services/ai_orchestrator/orchestrator.py      # monta ContextBundle
  → job enfileirado (whatsapp.inbound.n8n)
  → backend-executors (worker polling)
  → decision_engine.decide()
  → LLM (Mãe + Filha)
  → core_client.send_whatsapp_message()
  → UazAPI → WhatsApp
```

**Nota:** o tipo de job `whatsapp.inbound.n8n` usa "n8n" por razão histórica — ver [llm-architecture.md](llm-architecture.md).

---

## Endpoint de webhook

**Rota:** `POST /webhooks/whatsapp/uazapi`
**Arquivo:** `backend-crm/routes/webhooks.py`

O endpoint aceita eventos da UazAPI e os roteia para `inbound_handler`.

---

## Filtro de mensagens de grupo

Antes de chamar `handle_inbound`, o endpoint verifica se a mensagem vem de um grupo. Se sim, retorna imediatamente:

```json
{"status": "ignored", "reason": "group_message"}
```

Sem criar: `inbound_events`, lead, mensagem inbound, jobs.

### Campos de detecção de grupo

- `payload.chat.isGroup == true`
- `payload.data.isGroup == true` ou `payload.data.groupId` presente
- `payload.message.isGroup == true` ou `payload.message.groupId` presente
- Qualquer campo `remoteJid`, `chatId` ou `id` com sufixo `@g.us`

Há também defesa em profundidade no `handle_inbound`: se receber `is_group=true`, retorna `ignored` imediatamente.

**Observabilidade:** log emitido no ignore:
```
uazapi webhook ignored group_message instance=%s sender=%s message_id=%s
```

---

## Guardrail (inbound_handler)

**Arquivo:** `backend-crm/services/whatsapp_inbound/guardrail.py`

Verifica se o sistema deve processar a mensagem:
- `bot_disabled = 1` → ignora
- Lead em categoria não-atendível → ignora
- Promoção inicial de inbound: `to-prospect`/`in-progress` → `qualification`

---

## ContextBundle (orchestrator)

**Arquivo:** `backend-crm/services/ai_orchestrator/orchestrator.py`

O orchestrator constrói o `ContextBundle` com:
- `ai_profile` — perfil de IA do usuário
- `lead` — dados do lead
- `history` — histórico de mensagens
- `playbook` — playbook do template_key
- `qualification_state` — estado de qualificação do lead

Para garantir paridade com o Playground, todo campo novo que afeta o LLM deve ser adicionado via `enrich_context_bundle()`. Ver [playground-parity.md](playground-parity.md).

---

## Arquivos críticos

| Arquivo | Responsabilidade |
|---|---|
| `backend-crm/routes/webhooks.py` | Endpoint `/webhooks/whatsapp/uazapi` e filtro de grupo |
| `backend-crm/services/whatsapp_inbound/inbound_handler.py` | Recebe evento, monta bundle base, enfileira job |
| `backend-crm/services/whatsapp_inbound/guardrail.py` | Decide se deve processar a mensagem |
| `backend-crm/services/ai_orchestrator/orchestrator.py` | Monta e enriquece ContextBundle |
| `backend-crm/services/jobs_service.py` | Cria job `whatsapp.inbound.n8n` na fila |
