# Etapa 8-6: Recebimento de Áudio e Transcrição para o LLM

**Branch:** `etapa-8-6-audio-texto`  
**Status:** Em implementação — Fase 3 (Transcrição visível) em andamento

---

## Motivação

Leads frequentemente enviam mensagens de voz (PTT/áudio) via WhatsApp. O pipeline de inbound atual descartava silenciosamente qualquer mensagem que não fosse texto puro, tornando o agente incapaz de responder a esse formato.

O sistema já possuía OpenAI Whisper integrado no módulo Spy Agent — o objetivo desta etapa é conectar essa infraestrutura ao pipeline normal de inbound, com ativação controlada por flag no AI Profile do usuário.

---

## Problemas Identificados (estado anterior)

1. **Rejeição precoce no webhook:** `webhooks.py` retornava `{"status": "ignored", "reason": "not_text"}` para qualquer `messageType != "text"`, antes mesmo de consultar o AI Profile do usuário.

2. **"Mídia inválida" sem backend:** O AI Profile já tinha os campos `offer_pack.media_fallback` e `offer_pack.media_fallback_msg` configuráveis no frontend (Camada 3, Seção 1), mas o backend nunca os consultava — toda mídia era simplesmente descartada.

3. **Whisper isolado no Spy Agent:** A lógica de transcrição via OpenAI Whisper existia em `services/spy_agent/media_processor.py` mas não estava disponível para o pipeline principal.

---

## Abordagem

### Princípio central
A decisão de aceitar ou rejeitar uma mensagem de mídia deve ser tomada **no `inbound_handler.py`**, onde o AI Profile do usuário já foi resolvido — não no webhook, que é agnóstico ao usuário.

### Fluxo resultante

```
WhatsApp (PTT) → UazAPI → POST /webhooks/whatsapp/inbound
  → webhooks.py: extrai message_type + media_url (sem mais filtrar não-texto)
  → inbound_handler.py: resolve conexão + user
  │
  ├─ message_type in TIPOS_AUDIO?
  │   ├─ audio_transcription_enabled == True
  │   │   → transcribe_audio_from_url(media_url)
  │   │   → message_text = "[Áudio]: {transcrição}"
  │   │   → continua fluxo normal (LLM → resposta)
  │   └─ audio_transcription_enabled == False
  │       → _apply_media_fallback()
  │
  └─ message_type in TIPOS_MIDIA_INVALIDA (vídeo, figurinha, etc.)
      → _apply_media_fallback()

_apply_media_fallback():
  ├─ "ignorar"   → descarta silenciosamente
  ├─ "continuar" → envia media_fallback_msg, bot continua
  └─ "pausar"    → envia media_fallback_msg, bot desabilitado para este lead
```

---

## Implementação

### Novos arquivos

| Arquivo | Descrição |
|---|---|
| `backend-crm/services/audio_transcription.py` | Serviço compartilhado de transcrição via Whisper |

### Arquivos modificados

| Arquivo | O que muda |
|---|---|
| `backend-crm/routes/webhooks.py` | Remove early-return de não-texto; garante `media_url` e `message_type` no payload ao handler |
| `backend-crm/services/whatsapp_inbound/inbound_handler.py` | Adiciona lógica de transcrição e `_apply_media_fallback()` |
| `backend-core/app/models/ai_profile.py` | Novo campo `audio_transcription_enabled` (Boolean, default False) |
| `backend-core/app/schemas/ai_profile.py` | Expor campo em Create/Update/Out |
| `backend-core/app/db.py` | `ensure_column("ai_profiles", "audio_transcription_enabled", "BOOLEAN NOT NULL DEFAULT 0")` |
| `frontend-crm/src/components/ai-profile/CamadaPipeline.tsx` | Toggle "Receber mensagens de áudio" na Seção 1 |

### Detalhes do serviço de transcrição (`audio_transcription.py`)

```python
async def transcribe_audio_from_url(media_url: str, language: str = "pt") -> str | None
```
- Baixa o áudio via `httpx`
- Chama `openai.audio.transcriptions.create(model="whisper-1", language=language)`
- Formatos suportados: `.ogg`, `.mp3`, `.m4a`, `.wav`, `.webm`
- Retorna `None` em caso de falha (download, API error, formato inválido)

### Variáveis de ambiente

Nenhuma nova variável necessária. `OPENAI_API_KEY` já usada pelo Spy Agent deve estar disponível no `backend-crm`.

---

## Configuração pelo usuário

**Localização:** AI Profile → Camada 3 (Pipeline e comportamento) → Seção 1 (Comportamento por evento)

**Toggle:** "Receber mensagens de áudio"
- **Ligado:** o agente transcreve e responde ao áudio
- **Desligado:** o comportamento segue "Mídia inválida" (já configurável pelo usuário)

**Interdependência com "Mídia inválida":**
- Quando toggle ligado → áudio não cai em "Mídia inválida"
- Quando toggle desligado → áudio segue a regra de `media_fallback` configurada
- O campo `media_fallback_msg` é usado como texto de resposta quando `media_fallback != "ignorar"`

---

## Checks de Validação

### ✅ Cenário 1 — Toggle ligado, áudio recebido
- [ ] Enviar PTT via WhatsApp para número conectado
- [ ] Confirmar nos logs: `messageType: "ptt"` detectado no webhook
- [ ] Confirmar: transcrição via Whisper executada (log ou trace)
- [ ] Confirmar: job `whatsapp.inbound` criado com `message_text = "[Áudio]: ..."`
- [ ] Confirmar: bot responde ao lead com contexto da transcrição

### ✅ Cenário 2 — Toggle desligado, media_fallback = "continuar"
- [ ] Desligar o toggle; configurar Mídia inválida como "Responder e continuar"
- [ ] Enviar PTT
- [ ] Confirmar: bot envia `media_fallback_msg`
- [ ] Confirmar: bot NÃO é desabilitado (campo `bot_disabled` = False)

### ✅ Cenário 3 — Toggle desligado, media_fallback = "pausar"
- [ ] Configurar Mídia inválida como "Responder e pausar o bot"
- [ ] Enviar PTT
- [ ] Confirmar: bot envia `media_fallback_msg`
- [ ] Confirmar: bot desabilitado para este lead (`bot_disabled` = True no DB)

### ✅ Cenário 4 — Toggle desligado, media_fallback = "ignorar"
- [ ] Configurar Mídia inválida como "Ignorar silenciosamente"
- [ ] Enviar PTT
- [ ] Confirmar: `{"status": "ignored", "reason": "media_fallback_ignore"}` nos logs
- [ ] Confirmar: nenhuma mensagem enviada ao lead

### ✅ Cenário 5 — Regressão: mensagem de texto
- [ ] Enviar mensagem de texto normal
- [ ] Confirmar: fluxo normal inalterado (sem regressão)

### ✅ Cenário 6 — Falha de transcrição
- [ ] Simular falha na API Whisper (ex.: URL inválida ou sem `OPENAI_API_KEY`)
- [ ] Confirmar: o sistema aplica `media_fallback` em vez de quebrar silenciosamente
- [ ] Confirmar: nenhuma exceção não tratada nos logs

### ✅ Cenário 7 — Mídia não-áudio (vídeo, figurinha)
- [ ] Enviar figurinha ou vídeo com `media_fallback = "continuar"` configurado
- [ ] Confirmar: `media_fallback_msg` enviada ao lead
- [ ] Confirmar: bot NÃO transcreve (comportamento correto — só áudio é transcrito)

### ✅ Cenário 8 — Usuário sem toggle (migração)
- [ ] Verificar usuário existente sem `audio_transcription_enabled` no AI Profile
- [ ] Confirmar: default `False` aplicado (sem impacto em usuários existentes)

---

## Ajustes Possíveis Pós-Implementação

- **Prefixo da transcrição:** O texto `"[Áudio]: "` antecede a transcrição para o LLM saber o contexto. Avaliar se o prompt do agente precisa de instrução explícita sobre como lidar com transcrições.
- **Idioma Whisper:** Padrão `"pt"`. Se o sistema for usado em outros idiomas, avaliar tornar configurável via AI Profile ou detectar automaticamente.
- **Timeout de transcrição:** Áudios longos podem exceder o timeout do webhook. Monitorar p99 de latência após deploy e ajustar se necessário (opção: mover para job assíncrono).
- **Custo OpenAI:** Whisper é cobrado por minuto de áudio. Monitorar usage após ativação em produção.

---

## Fase 2 — Gravação de Áudio no Playground

### Motivação

A Fase 1 implementou o fluxo real WhatsApp → transcrição → LLM. No entanto, testar esta funcionalidade exigia ter um número WhatsApp conectado e enviar um PTT real. O playground — principal ferramenta de testes do operador — não suportava gravação de áudio: o marcador `{áudio}` apenas simulava um card visual sem transcrição real.

O objetivo desta fase é permitir que o operador grave um áudio diretamente no playground, exatamente como um lead faria no WhatsApp, e valide o comportamento do agente em ambos os casos (toggle ligado e desligado).

### Problemas Identificados (antes da Fase 2)

1. **Sem gravação real no playground:** `PlaygroundChat.tsx` só aceitava text markers `{áudio}` — card visual simulado, sem upload nem transcrição.
2. **`PlaygroundChatRequest` sem suporte a áudio:** O endpoint `/api/playground/chat` só processava `message: string`, sem `message_type` ou referência a arquivo de áudio.
3. **`transcribe_audio_from_url()` dependia de URL pública:** Não se aplicava ao playground onde o arquivo existe localmente no servidor.

### Abordagem

```
Operador clica Mic → MediaRecorder grava áudio no browser
→ Para gravação → Blob criado → preview player mostrado
→ Clica "Enviar"
  → POST /api/playground/upload-audio → salva em temp_audio/ → {filename, audio_url}
  → Lead bubble adicionada com <audio> player reproduzível
  → POST /api/playground/chat {message_type:"audio", audio_filename:filename}
    → backend: check audio_transcription_enabled
      ├─ TRUE  → transcribe_audio_from_path() → effective_message="[Áudio]: ..."
      │          → fluxo normal do LLM → bot responde ao conteúdo
      └─ FALSE → simular media_fallback → retorna mensagem configurada no AI Profile
```

### Novos arquivos (Fase 2)

Nenhum novo arquivo — tudo integrado nos existentes.

### Arquivos modificados (Fase 2)

| Arquivo | O que muda |
|---|---|
| `backend-crm/services/audio_transcription.py` | Adiciona `transcribe_audio_from_path(file_path)` — lê do disco, sem HTTP |
| `backend-crm/routes/playground.py` | Endpoints `POST /upload-audio` e `GET /audio/{filename}`; extensão de `PlaygroundChatRequest`; lógica de transcrição/fallback no chat handler |
| `frontend-crm/src/services/api.ts` | Tipos estendidos + `uploadPlaygroundAudio()` |
| `frontend-crm/src/components/playground/PlaygroundChat.tsx` | Botão microfone, MediaRecorder, preview player, props `onSendAudio` e `audioEnabled` |
| `frontend-crm/src/pages/Playground.tsx` | Callback `handleSendAudio` — coordena upload + chat |
| `frontend-crm/src/components/playground/MessageBubble.tsx` | Player `<audio>` na bolha do lead quando `isAudioMessage=true` |

### Detalhes técnicos

**`transcribe_audio_from_path()`**
- Lê bytes do disco diretamente (sem round-trip HTTP)
- Compartilha lógica Whisper com `transcribe_audio_from_url()`
- Usado exclusivamente pelo playground (inbound real usa a versão com URL)

**Armazenamento temporário**
- Arquivos salvos em `backend-crm/temp_audio/` (criado automaticamente na startup)
- Servidos via `GET /api/playground/audio/{filename}` com `FileResponse`
- Sem cleanup automático (MVP) — pode ser adicionado com TTL em versão futura

**Parity com fluxo real**
- Mesma flag `audio_transcription_enabled` consultada
- Mesmo comportamento de `media_fallback` quando toggle desligado
- Mesmo prefixo `"[Áudio]: "` no texto enviado ao LLM

### Checks de Validação — Fase 2

#### ✅ Cenário P1 — Toggle ligado, gravação no playground
- [x] Ligar `audio_transcription_enabled` no AI Profile
- [x] Clicar no botão de microfone no playground
- [x] Falar e clicar parar
- [x] Confirmar: preview player aparece com o áudio gravado
- [x] Clicar "Enviar"
- [x] Confirmar: lead bubble mostra player de áudio reproduzível
- [x] Confirmar: bot responde ao conteúdo do áudio transcrito
- **Validado em:** 27/05/2026 — playground respondendo corretamente ao conteúdo transcrito

#### ✅ Cenário P2 — Toggle desligado, media_fallback = "continuar"
- [ ] Desligar toggle; configurar Mídia inválida como "Responder e continuar"
- [ ] Gravar e enviar áudio no playground
- [ ] Confirmar: bot responde com a `media_fallback_msg` configurada

#### ✅ Cenário P3 — Toggle desligado, media_fallback = "ignorar"
- [ ] Desligar toggle; configurar Mídia inválida como "Ignorar"
- [ ] Gravar e enviar áudio
- [ ] Confirmar: bot responde com mensagem informando que áudio não é aceito

#### ✅ Cenário P4 — Regressão: marcador `{áudio}` ainda funciona
- [ ] Digitar `{áudio}` e enviar
- [ ] Confirmar: card simulado aparece (sem player, sem upload) — sem regressão

#### ✅ Cenário P5 — Modo lote com texto
- [ ] Adicionar mensagens de texto ao modo lote e enviar
- [ ] Confirmar: comportamento inalterado

#### ✅ Cenário P6 — Permissão de microfone negada
- [ ] Bloquear microfone no browser → clicar Mic
- [ ] Confirmar: erro é tratado graciosamente (toast ou mensagem), UI não quebra

---

## Fase 3 — Transcrição Visível na UI e no Export

### Motivação

Ao validar a Fase 2 em playground (27/05/2026), o bot respondia corretamente ao conteúdo transcrito, mas o operador não conseguia ver qual foi o texto transcrito — a bolha do lead mostrava apenas o player de áudio e o texto fixo "Áudio gravado". O export em Markdown também omitia a transcrição, tornando os registos de sessão incompletos para fins de auditoria e fine-tuning.

### Problemas Identificados

1. **Transcrição invisível na UI:** `MessageBubble.tsx` não recebia nem renderizava o texto transcrito.
2. **`PlaygroundChatResponse` não devolvia a transcrição:** O backend transcrevia e usava o texto internamente (`effective_message`), mas não incluía o valor na resposta HTTP.
3. **Export em Markdown incompleto:** A função `exportMarkdown()` em `PlaygroundFeedback.tsx` tratava mensagens de áudio gravado como texto genérico, sem indicar que eram áudio nem incluir transcrição.

### Abordagem

```
Backend: PlaygroundChatResponse.transcription = texto transcrito (ou null)
  ↓
Playground.tsx handleSendAudio: após resposta, atualiza bolha do lead com transcription
  ↓
MessageBubble.tsx: se message.transcription → mostra em itálico abaixo do player
  ↓
PlaygroundFeedback.tsx exportMarkdown: para isAudioMessage → escreve 🎙️ [Áudio gravado]
                                         + se transcription → escreve **Transcrição:** "..."
```

### Arquivos modificados (Fase 3)

| Arquivo | O que muda |
|---|---|
| `backend-crm/routes/playground.py` | `PlaygroundChatResponse` ganha `transcription: Optional[str] = None`; passado no return final quando `_audio_transcription` não é None |
| `frontend-crm/src/services/api.ts` | `PlaygroundChatResponse` ganha `transcription?: string \| null` |
| `frontend-crm/src/components/playground/MessageBubble.tsx` | `ChatMessage` ganha `transcription?: string`; renderiza em itálico abaixo do `<audio>` quando presente |
| `frontend-crm/src/pages/Playground.tsx` | `handleSendAudio` actualiza a bolha do lead via `setMessages` com `transcription` vinda da resposta |
| `frontend-crm/src/components/playground/PlaygroundFeedback.tsx` | `exportMarkdown` distingue `isAudioMessage` dos outros tipos e inclui a transcrição quando disponível |

### Comportamento resultante

- **Toggle ON + transcrição bem-sucedida:** player de áudio + texto transcrito em itálico abaixo; export inclui transcrição
- **Toggle ON + falha de transcrição:** player de áudio sem texto (transcrição = null); export indica áudio sem transcrição
- **Toggle OFF:** bolha só com player (sem transcrição — o bot retorna media_fallback sem transcrever); export indica 🎙️ [Áudio gravado] sem transcrição
- **Marcador `{áudio}` de texto:** inalterado — sem player, sem upload, sem transcrição

### Checks de Validação — Fase 3

#### ✅ Cenário P7 — Transcrição visível na bolha
- [ ] Ligar `audio_transcription_enabled`
- [ ] Gravar e enviar áudio no playground
- [ ] Confirmar: abaixo do player aparece o texto transcrito em itálico
- [ ] Confirmar: bot responde ao conteúdo transcrito

#### ✅ Cenário P8 — Transcrição no export
- [ ] Após sessão com áudio transcrito, exportar Markdown
- [ ] Confirmar: entrada do lead mostra `🎙️ [Áudio gravado]` + `**Transcrição:** "..."`
- [ ] Confirmar: entradas de texto continuam sem alteração (sem regressão)

#### ✅ Cenário P9 — Áudio sem transcrição (toggle OFF)
- [ ] Desligar toggle; gravar e enviar áudio
- [ ] Confirmar: bolha do lead mostra player sem texto transcrito
- [ ] Confirmar: export mostra `🎙️ [Áudio gravado]` sem linha de transcrição
