# Diagnóstico Uazapi inbound x mensagens de grupo

## 1) Endpoint webhook e parsing atual

- **Rota recebida no CRM:** `POST /webhooks/whatsapp/uazapi` (registrada em `routes/webhooks.py`).
- **Router registrado na app:** `app.include_router(webhooks.router)` em `app.py`, então o endpoint fica público sob `/webhooks/...`.

### Campos usados no parsing

No endpoint Uazapi, os campos usados para resolver remetente/chat/evento são:

- `event`: `payload.event` ou `payload.EventType` ou `payload.type`.
- `instance_id`: `payload.instance` ou `payload.instanceName`.
- `data`: `payload.data` (dict).
- `message`: `payload.message` (dict).
- `sender`:
  - primeiro `payload.chat.phone`
  - fallback para `data.sender` ou `message.sender_pn`
  - todos passam por normalização para E.164.
- `message_id`: `data.messageId` ou `data.id` ou `message.messageid` ou `message.id`.
- `message_type`: `data.messageType` ou `message.type` ou `message.messageType`.
- `message_text`: `data.text` ou `message.text` ou `message.content`.
- `from_me`: `data.fromMe is True` ou `message.fromMe is True`.

### Filtros que já existem

Hoje o endpoint ignora:

- evento diferente de `messages/message`;
- mensagens `fromMe`;
- mensagens não-texto;
- mensagens sem texto.

### Detecção de grupo no webhook Uazapi

**Não há detecção explícita de grupo.**

Não existe checagem de:

- `isGroup`, `chat.isGroup`, `groupId`;
- `remoteJid` terminando em `@g.us`;
- qualquer campo equivalente no payload Uazapi.

Também não há validação por header/flag para grupo.

---

## 2) Pipeline inbound (o que acontece após receber mensagem)

### Sequência atual

1. Endpoint `/webhooks/whatsapp/uazapi` monta `inbound_payload` e chama `handle_inbound(...)`.
2. `handle_inbound` valida texto, `message_id/event_id`, normaliza telefone e resolve conexão.
3. Tenta inserir `inbound_events` para idempotência (`UNIQUE(provider, instance_id, external_event_id)`).
4. Registra/atualiza conversa mensal Orion.
5. Chama `find_or_create_lead_by_phone(...)`.
6. Salva mensagem inbound em `messages` + log em `prospection_logs`.
7. Monta payload e cria job `TYPE_WHATSAPP_INBOUND_N8N` via `create_job(...)`.

### Respostas objetivas

- **Cria job sempre?**
  - **Quase sempre para payload válido**: cria ao final do `handle_inbound`.
  - **Não cria** em casos rejeitados antes (erro de validação/403) ou duplicado (`status=duplicate`).
- **Cria inbound_event?**
  - Sim, tenta sempre no início do fluxo transacional; duplicado retorna sem seguir.
- **Chama inbound_handler que faz find_or_create_lead_by_phone?**
  - Sim. O endpoint Uazapi sempre delega para `handle_inbound`, que chama `find_or_create_lead_by_phone` antes da criação do job.

### Melhor ponto para bloquear grupo

**Mais correto: bloquear no endpoint `/webhooks/whatsapp/uazapi`, antes de chamar `handle_inbound`.**

Motivo:

- evita tocar em `inbound_events`, `orion_conversations`, `messages`, `prospection_logs`, criação/atualização de lead e criação de job;
- mantém `handle_inbound` focado no domínio “mensagem 1:1 já validada”.

Como fallback de defesa em profundidade, pode-se adicionar segunda verificação no início de `handle_inbound` (caso outro provedor/endpoint reutilize o handler futuramente).

---

## 3) Config Uazapi: headers/flags para grupo

- O código atual só valida segredo (`X-Webhook-Secret` ou query `secret`) para autenticar webhook.
- Não existe “validador de grupo” por header/flag de configuração.

### Campos do payload que **podem** ser usados para detectar grupo

Com base no parsing atual e sem quebrar compatibilidade, os pontos naturais seriam:

- `payload.chat` (já lido para `chat.phone`) — se vier algo como `chat.isGroup`.
- `payload.data` (já lido para `sender`, `messageId`, etc.) — se vier `remoteJid`, `isGroup`, `groupId`.
- `payload.message` (já lido para texto e tipo) — se vier `remoteJid`/`isGroup`.

No estado atual, nenhum desses campos é inspecionado com regra de grupo.

---

## 4) Tabela PASS/FAIL

| Item | Status | Evidência resumida |
|---|---|---|
| Detecção de grupo existe | **FAIL** | Não há checagem `isGroup/chat.isGroup/remoteJid@g.us/groupId`; apenas filtros de evento, fromMe, tipo e texto. |
| Bloqueio de grupo existe | **FAIL** | Não existe `if grupo -> ignore` no endpoint nem no handler. |
| Ponto de criação de job | **PASS** | `create_job(TYPE_WHATSAPP_INBOUND_N8N, ...)` no final de `handle_inbound`. |
| Ponto de criação de lead | **PASS** | `find_or_create_lead_by_phone(...)` dentro de `handle_inbound` antes do job. |

---

## Opções de implementação (sem aplicar agora)

1. **Mínima (rápida):**
   - No endpoint `/webhooks/whatsapp/uazapi`, adicionar função `is_group(payload)` com regra simples (`remoteJid.endswith('@g.us')` OU `isGroup==True` onde existir).
   - Se grupo, retornar `{status: "ignored", reason: "group_message"}` antes de `handle_inbound`.

2. **Intermediária (defesa em profundidade):**
   - Implementar o bloqueio do item 1 no endpoint.
   - E adicionar campo opcional `is_group` no `inbound_payload` para `handle_inbound`, que também ignora quando verdadeiro.

3. **Robusta (observabilidade + evolução):**
   - Centralizar parser Uazapi (extração de event/sender/chat/message/group) em função utilitária tipada.
   - Registrar métrica/log estruturado para motivos de ignore (incluindo grupo).
   - Cobrir com testes unitários de payloads variantes (`chat.isGroup`, `data.remoteJid`, `message.remoteJid`, etc.).
