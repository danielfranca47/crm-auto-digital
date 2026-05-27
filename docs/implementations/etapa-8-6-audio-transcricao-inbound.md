# Etapa 8-6: Recebimento de Áudio e Transcrição para o LLM

**Branch:** `etapa-8-6-audio-texto`  
**Status:** Em implementação

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
