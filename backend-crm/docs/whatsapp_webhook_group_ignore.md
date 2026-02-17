# WhatsApp webhook (Uazapi): ignore de mensagens de grupo

## Objetivo

Evitar side-effects no CRM para mensagens de grupos vindas da Uazapi.

Quando detectado grupo, o endpoint retorna:

```json
{"status": "ignored", "reason": "group_message"}
```

Sem chamar `handle_inbound`, portanto sem criar:

- `inbound_events`
- lead (`find_or_create_lead_by_phone`)
- mensagem inbound (`messages`/`prospection_logs`)
- jobs (`create_job`)

## Campos de detecção de grupo

A detecção no endpoint `/webhooks/whatsapp/uazapi` considera:

- `payload.chat.isGroup == true`
- `payload.data.isGroup == true` ou `payload.data.groupId` presente
- `payload.message.isGroup == true` ou `payload.message.groupId` presente
- Qualquer campo `remoteJid` / `chatId` / `id` com sufixo `@g.us`

Também existe defesa em profundidade no `handle_inbound`: se receber `is_group=true`, retorna `ignored` imediatamente.

## Exemplo de payload de grupo

```json
{
  "event": "message",
  "instance": "inst-1",
  "chat": {"phone": "+5511999999999"},
  "data": {
    "messageId": "m-123",
    "text": "olá grupo",
    "messageType": "text",
    "remoteJid": "123456789-123@g.us"
  }
}
```

## Observabilidade

No ignore, é emitido log:

- `uazapi webhook ignored group_message instance=%s sender=%s message_id=%s`

## Como reverter

1. Remover o bloco de detecção/retorno no endpoint `routes/webhooks.py`.
2. Remover/ajustar a defesa por `is_group` no `handle_inbound`.
3. Atualizar/remover os testes `tests/test_whatsapp_group_ignore.py`.
