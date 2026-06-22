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
- `bot_disabled = 1` → ignora (`{"status": "ignored"/"skipped", "reason": "bot_disabled"}`, nenhum job criado) — **exceto** quando `bot_disabled_reason = "meeting_scheduled"` e o AI Profile tem `meeting_management_enabled = True` (padrão): nesse caso o job é criado normalmente, e `decision_engine.decide()` usa um caminho dedicado de gestão pós-confirmação em vez do bloqueio padrão. Ver "Toggle de Bot por Lead" em [`agents.md`](agents.md).
- Lead em categoria não-atendível → ignora
- Promoção inicial de inbound: `to-prospect`/`in-progress` → `qualification`

O flag `bot_disabled` é gerido por lead individual. Fontes de desactivação: manual (UI), `media_fallback="pausar"`, entrada em `closing` com `agent_mode=agenda`, confirmação de reunião (`agent_mode=agenda`).

---

## Tratamento de Mensagens de Áudio e Mídia

**Arquivo:** `backend-crm/services/whatsapp_inbound/inbound_handler.py`

### Normalização de messageType

A UazAPI envia diferentes valores em `messageType` dependendo da versão/instância:

| `messageType` recebido | Tipo normalizado | Tratamento |
|---|---|---|
| `"ptt"`, `"AudioMessage"`, `"audio"` | `audio` | Transcrição ou `media_fallback` |
| `"media"` com `mediaType="ptt"` | `audio` | Idem |
| `"VideoMessage"`, `"video"`, `"videomessage"` | `video` | `media_fallback` |
| `"ImageMessage"`, `"image"`, `"imagemessage"` | `image` | `media_fallback` |
| `"StickerMessage"`, `"sticker"` | `sticker` | `media_fallback` |
| `"reaction"` | `reaction` | `media_fallback` |
| `"text"`, `"chat"` | `text` | Fluxo normal |
| `"media"` com `mediaType="text"` | `text` | Fluxo normal |

> Quando `messageType = "media"`, o handler usa `message.mediaType` para determinar o tipo real.

### Filtro de mensagem sem texto

Mensagens com `message_text = ""` são descartadas, **excepto** para tipos de mídia que não exigem texto:

```python
_MEDIA_NO_TEXT_TYPES = {"audio", "video", "image", "sticker", "reaction", "document"}
```

Tipos fora deste conjunto sem `message_text` retornam `{"status": "ignored", "reason": "missing_text"}`.

### Pipeline de áudio (`audio_transcription_enabled = True`)

```
PTT/AudioMessage recebido
  → resolve instance_token via GET /whatsapp-connections/resolve-token
  → POST {UAZAPI_BASE_URL}/message/download {id: message_id, return_link: true}
      ← URL pública do áudio (mmg.whatsapp.net requer auth de sessão WhatsApp;
         UazAPI fornece URL temporária através da sessão activa)
  → transcribe_audio_from_url(url) via OpenAI Whisper
      ← message_text = "[Áudio]: {transcrição}"
  → continua fluxo normal (job criado, LLM responde ao conteúdo transcrito)
```

**Variáveis de ambiente necessárias:**
- `OPENAI_API_KEY` — chamadas ao Whisper
- `UAZAPI_BASE_URL` — endpoint da UazAPI (ex.: `https://free.uazapi.com`)

### Comportamento de media_fallback

Aplicado quando: `audio_transcription_enabled = False` com áudio, ou mensagem de mídia inválida (vídeo, imagem, sticker, etc.).

Controlado pelo campo `offer_pack.media_fallback` no AI Profile do utilizador:

| `media_fallback` | Comportamento |
|---|---|
| `"ignorar"` (padrão) | Descarte silencioso — nenhuma mensagem ao lead, nenhum job criado |
| `"continuar"` | Envia `offer_pack.media_fallback_msg` via `send_whatsapp_direct()`. Bot continua ativo. |
| `"pausar"` | Envia `offer_pack.media_fallback_msg`. Define `bot_disabled=1` para este lead. |

> **Envio directo:** `_apply_media_fallback()` usa `send_whatsapp_direct()` (chamada síncrona ao core-api, não via fila de jobs) para evitar que um job `whatsapp.send.local` fique pendente sem ser processado pelo executor.

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

## Multi-message buffer

Configurado em `offer_pack.multi_message_buffer_seconds` (ou `multi_message_buffer_seconds`) no AI Profile.

Quando `> 0`, o primeiro job inbound é criado com `scheduled_at = agora + buffer_seconds`. Mensagens subsequentes que chegam antes de `scheduled_at` são absorvidas e concatenadas no payload do mesmo job (a mensagem anterior é actualizada). O resultado é que o LLM recebe o contexto combinado de todas as mensagens do "lote real" de uma só vez.

---

## Webhook de Pagamento

**Rota:** `POST /webhooks/payment/{gateway}`
**Arquivo:** `backend-crm/routes/webhooks.py`

Recebe eventos de pagamento confirmado de gateways externos (ex.: Hotmart, Stripe). Cada utilizador tem a sua própria URL com token único — ver secção "Webhook de Pagamento" em [`agents.md`](agents.md).

**Autenticação:** token em `X-Webhook-Secret` (header) ou `?token=` (query string), comparado com `payment_webhook_secret` do AI Profile.

**Ao confirmar pagamento:**
1. Identifica o lead por email ou telefone no payload
2. Move lead para `"client-list"`
3. Para cart recovery activo
4. Enfileira mensagem de boas-vindas via job `whatsapp.send.local`

Se nenhum lead for encontrado, regista log `payment_webhook unmatched` e retorna 200 (não expõe informação ao gateway externo).

---

## Arquivos críticos

| Arquivo | Responsabilidade |
|---|---|
| `backend-crm/routes/webhooks.py` | Endpoint `/webhooks/whatsapp/uazapi` e filtro de grupo |
| `backend-crm/services/whatsapp_inbound/inbound_handler.py` | Recebe evento, normaliza tipo, áudio, media_fallback, enfileira job |
| `backend-crm/services/whatsapp_inbound/guardrail.py` | Decide se deve processar (bot_disabled, categoria, etc.) |
| `backend-crm/services/audio_transcription.py` | Transcrição via Whisper (`transcribe_audio_from_url`) |
| `backend-crm/core_client.py` | `fetch_core_whatsapp_token()`, `send_whatsapp_direct()` |
| `backend-crm/services/ai_orchestrator/orchestrator.py` | Monta e enriquece ContextBundle |
| `backend-crm/services/jobs_service.py` | Cria job `whatsapp.inbound.n8n` na fila |
