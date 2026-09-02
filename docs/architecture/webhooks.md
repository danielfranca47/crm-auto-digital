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

### Registo do webhook na UazAPI

Feito em `backend-crm/routes/whatsapp_connect.py` (`_set_whatsapp_webhook`), disparado a cada `/api/whatsapp/connect` e `/api/whatsapp/qr/refresh` (o fluxo de conexão em si — QR code e código de pareamento — está documentado em [`whatsapp-connection.md`](whatsapp-connection.md)). A URL registada é sempre construída a partir de `CRM_PUBLIC_BASE_URL` (nunca `localhost`), pois a UazAPI precisa de conseguir entregar o POST a um endereço publicamente roteável:

```
{CRM_PUBLIC_BASE_URL}/webhooks/whatsapp/uazapi?secret={CRM_WEBHOOK_SECRET}
```

**Testar o fluxo inbound em ambiente local:** como `localhost` não é alcançável pela UazAPI, é preciso expor o `backend-crm` via túnel público (ex.: ngrok), apontar `CRM_PUBLIC_BASE_URL` temporariamente para a URL do túnel, reiniciar o `backend-crm`, e reconfigurar o webhook (`POST {UAZAPI_BASE_URL}/webhook` com header `token: {instance_token}`, ou via `/api/whatsapp/connect`/`/qr/refresh` que já reconfigura automaticamente). Reverter tudo (URL de produção + webhook) ao final do teste.

---

## Evento de conexão (`event="connection"`) — status real + alerta de desconexão

A UazAPI envia dois tipos de evento para o mesmo webhook: `"messages"` (tratado
no resto deste documento) e `"connection"`, disparado sempre que a sessão da
instância muda de estado (ex.: cai por logout forçado do WhatsApp). É o único
caminho automático que existe hoje para saber que uma sessão caiu de verdade —
sem ele, `WhatsappConnection.status` (backend-core) fica congelado no último
valor conhecido, porque a única outra escrita é sob demanda
(`GET /whatsapp-instances/status`, só chamado enquanto a tela de Conexão está
aberta com QR pendente).

```
UazAPI → POST /webhooks/whatsapp/uazapi (event="connection")
  → backend-crm (routes/webhooks.py): resolve instance_id, loga payload bruto
      → core_client.report_whatsapp_connection_event(instance_id, raw_payload)
          → backend-core: POST /whatsapp-instances/connection-event (X-Service-Token)
              → uazapi_admin.extract_connection_meta(raw) → status_value
              → grava o novo status sempre (corrige o congelamento)
              → SE a transição foi active → inactive:
                  busca o User da connection e envia email
                  (render_whatsapp_disconnected_email) pedindo para reconectar
  ← sempre 200 para a UazAPI, mesmo se o repasse ao core falhar (best-effort)
```

**Formato do payload é diferente do evento `messages` nesse ponto:** para
`messages`, `payload["instance"]` é a *string* com o instance_id. Para
`connection`, a UazAPI aninha o **objeto inteiro** da instância ali
(`{"name", "status", "lastDisconnect", "lastDisconnectReason"}`) — ex.:
`lastDisconnectReason: "401: logged out from another device"`. O handler
resolve isso separadamente (`connection_instance_field.get("name")` quando é
dict) sem tocar na resolução usada por `messages`.

**Email de alerta:** dispara só na transição `active → inactive` (não repete
em eventos "disconnected" seguidos, já que o segundo já vê o status local como
inactive). Reconexões (`inactive → active`) só atualizam o status, sem email
de confirmação.

**Limitação conhecida:** este mecanismo depende inteiramente do webhook ser
entregue. Não existe hoje nenhuma verificação periódica em segundo plano que
confirme o status real junto à UazAPI de forma independente — se a entrega do
webhook falhar, o status volta a ficar congelado sem aviso.

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
- `bot_global_pause_state.is_paused = 1` para o usuário → ignora incondicionalmente (`{"status": "skipped", "reason": "global_pause"}`, nenhum job criado), **antes** do gate de `bot_disabled` por lead — cobre inclusive leads novos criados durante a pausa. Ver [`bot-global-pause.md`](bot-global-pause.md).
- `bot_disabled = 1` → ignora (`{"status": "ignored"/"skipped", "reason": "bot_disabled"}`, nenhum job criado) — **exceto** quando `bot_disabled_reason = "meeting_scheduled"` e o AI Profile tem `meeting_management_enabled = True` (padrão): nesse caso o job é criado normalmente, e `decision_engine.decide()` usa um caminho dedicado de gestão pós-confirmação em vez do bloqueio padrão. Ver "Toggle de Bot por Lead" em [`agents.md`](agents.md).
- Lead em categoria não-atendível → ignora
- Promoção inicial de inbound: `to-prospect`/`in-progress` → `qualification`

O flag `bot_disabled` é gerido por lead individual. Fontes de desactivação: manual (UI), `media_fallback="pausar"`, entrada em `closing` com `agent_mode=agenda`, confirmação de reunião (`agent_mode=agenda`), fechamento do check-in automático de cliente inativo (`category_checkin_closed`, ver [`followup.md`](followup.md)), pausa geral pelo header do Kanban (`global_pause`, ver [`bot-global-pause.md`](bot-global-pause.md)).

### Criação automática de lead (primeiro contacto)

`find_or_create_lead_by_phone()` (mesmo arquivo) cria o lead quando não existe nenhum com o telefone do remetente. `routes/webhooks.py::_resolve_wa_display_name()` extrai o nome de perfil do WhatsApp (pushName) do payload bruto da UazAPI, com prioridade `message.senderName` → `chat.wa_name` (nome de perfil do remetente, existe para qualquer remetente) → `chat.wa_contactName` → `chat.name` (nome salvo na agenda de contatos do telefone do bot — só existe se o operador salvou aquele número manualmente; usado apenas como último recurso). `contactName` nasce como esse nome quando disponível; só cai para `<telefone>` como placeholder quando nenhum nome é resolvido do payload. `companyName = NULL`. O valor também é persistido à parte em `leads.wa_display_name` — campo nunca sobrescreve uma edição manual de `contactName` feita pelo operador em turnos seguintes. Ver regra completa de nome em [`leads-schema.md`](leads-schema.md).

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
- `UAZAPI_BASE_URL` — endpoint da UazAPI (definido em `backend-core/.env` **e** `backend-crm/.env` — as duas cópias precisam apontar para o mesmo servidor)

### Comportamento de media_fallback

Aplicado quando: `audio_transcription_enabled = False` com áudio, ou mensagem de mídia inválida (vídeo, imagem, sticker, etc.).

Controlado pelo campo `offer_pack.media_fallback` no AI Profile do utilizador:

| `media_fallback` | Comportamento |
|---|---|
| `"ignorar"` (padrão) | Descarte silencioso — nenhuma mensagem ao lead, nenhum job criado |
| `"continuar"` | Envia `offer_pack.media_fallback_msg` via `send_whatsapp_direct()`. Bot continua ativo. |
| `"pausar"` | Envia `offer_pack.media_fallback_msg`. Define `bot_disabled=1` para este lead. |

> **Envio directo:** `_apply_media_fallback()` usa `send_whatsapp_direct()` (chamada síncrona ao core-api, não via fila de jobs) para evitar que um job `whatsapp.send.local` fique pendente sem ser processado pelo executor.

**Guard de pausa:** antes de enviar (comportamentos `"continuar"`/`"pausar"`), `_apply_media_fallback()` verifica `bot_global_pause_state.is_paused` e `leads.bot_disabled` para o par `(user_id, phone)` — se qualquer um estiver ativo, retorna `{"status": "skipped", "reason": "global_pause"|"bot_disabled"}` sem enviar nada. Isso mantém o fallback de mídia consistente com o gate de pausa já aplicado ao fluxo de texto (ver "Guardrail" acima) — pausar o bot não deve deixar passar uma resposta automática só porque o lead mandou uma imagem/vídeo em vez de texto.

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
| `backend-crm/routes/webhooks.py` | Endpoint `/webhooks/whatsapp/uazapi`, filtro de grupo, tratamento do evento `connection` |
| `backend-core/app/api/whatsapp_instances.py` | Rota `POST /whatsapp-instances/connection-event` — atualiza status real, dispara email na transição active→inactive |
| `backend-core/app/services/email_service.py` | `render_whatsapp_disconnected_email()` |
| `backend-crm/services/whatsapp_inbound/inbound_handler.py` | Recebe evento, normaliza tipo, áudio, media_fallback, enfileira job |
| `backend-crm/services/whatsapp_inbound/guardrail.py` | Decide se deve processar (bot_disabled, categoria, etc.) |
| `backend-crm/services/audio_transcription.py` | Transcrição via Whisper (`transcribe_audio_from_url`) |
| `backend-crm/core_client.py` | `fetch_core_whatsapp_token()`, `send_whatsapp_direct()` |
| `backend-crm/services/ai_orchestrator/orchestrator.py` | Monta e enriquece ContextBundle |
| `backend-crm/services/jobs_service.py` | Cria job `whatsapp.inbound.n8n` na fila |
