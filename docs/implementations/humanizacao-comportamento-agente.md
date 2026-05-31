# Humanização Comportamental do Agente

**Branch:** múltiplos commits em branch de feature (ver hashes abaixo)
**Status:** Todos os cenários validados — graduado em 31/05/2026

---

## Motivação

O agente respondia de forma instantânea e determinística: a mensagem gerada pela LLM ia diretamente para a UazAPI sem nenhum delay, sem indicador de digitação e sem quebra em partes. O comportamento era visivelmente robótico. O objetivo era simular o ritmo humano de conversação — delay antes de responder, "Digitando…" proporcional ao tamanho da resposta, mensagens chegando em bolhas separadas por pontuação, janela de horário de trabalho e suporte a áudio de voz estático.

---

## Problemas Identificados (estado anterior)

1. **Sem delay de resposta:** `inbound_handler.py` criava jobs com `scheduled_at = None` — o worker executava imediatamente.
2. **Sem typing indicator:** `uazapi_client.py` não passava o campo `delay` no payload da UazAPI.
3. **Mensagens chegam em bloco único:** `whatsapp.py` (executor) enviava o texto inteiro em uma mensagem, mesmo com múltiplas frases.
4. **Campos `followup_allowed_hours` e `availability_schedule` existiam no AI Profile mas nunca eram lidos** no momento de agendar jobs.
5. **Áudio como arquivo comum:** o tipo `myaudio` (mensagem de voz) não estava mapeado em `uazapi_client.py`; arquivos de áudio na base de conhecimento eram tratados como `audio` (player de arquivo, não bolha de voz).
6. **Playground sem preview temporal:** a resposta do playground não expunha delay, typing ou quebra de partes — o usuário não conseguia prever o comportamento real no WhatsApp.

---

## Abordagem

```
inbound_handler.py
  → compute_scheduled_at(ai_profile, is_first_message)   ← humanization.py
      ├─ compute_reply_delay()    # sorteia delay entre min/max
      └─ next_available_at()      # desloca para janela de horário se fora dela
  → create_job(scheduled_at=...)  # worker só executa quando scheduled_at <= now

executor (whatsapp.py)
  → _split_message_by_punctuation(text)   # quebra em partes por . ! ? …
  → para cada parte:
      delay_ms = compute_typing_ms(parte)
      core_client.send_whatsapp_message(text=parte, delay_ms=delay_ms)
           → UazAPI campo "delay": exibe "Digitando…" durante delay_ms

playground.py
  → PlaygroundChatResponse inclui:
      simulated_delay_seconds, typing_seconds, message_parts, audio_previews
```

---

## Plano de Implementação

### Fase 1 — Delay de resposta

**Objetivo:** agendar jobs no futuro com delay configurável por lead novo vs. conversa em andamento.

| Arquivo | O que mudou |
|---|---|
| `backend-core/app/models/ai_profile.py` | 4 campos: `first_reply_delay_min/max_seconds`, `reply_delay_min/max_seconds` |
| `backend-core/app/db.py` | `ensure_ai_profile_columns()` com migrations idempotentes |
| `backend-crm/services/humanization.py` | Novo módulo: `compute_reply_delay()`, `scheduled_at_from_delay()` |
| `backend-crm/services/whatsapp_inbound/inbound_handler.py` | Conta mensagens do lead, detecta primeira mensagem, passa `scheduled_at` ao `create_job()` |
| `backend-crm/routes/playground.py` | Campo `simulated_delay_seconds: int` na resposta |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `5853a0a` | Delay de resposta: campos AI Profile + humanization.py + inbound_handler + playground |

---

### Fase 2 — Typing indicator

**Objetivo:** exibir "Digitando…" no WhatsApp proporcional ao tamanho da resposta.

| Arquivo | O que mudou |
|---|---|
| `backend-crm/services/humanization.py` | `compute_typing_ms()`: 40ms/char, mínimo 1s, máximo 8s |
| `backend-core/app/providers/uazapi_client.py` | `delay_ms` em `send_text()` e `send_media()`; injetado no payload quando > 0 |
| `backend-core/app/api/whatsapp_send.py` | Campo `delay_ms: int = 0` nos dois request bodies; repassado ao client |
| `backend-executors/app/runners/whatsapp.py` | Calcula `delay_ms = min(max(len(text) * 40, 1000), 8000)` antes do envio |
| `backend-crm/routes/playground.py` | Campo `typing_seconds: float` na resposta |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `1fb7fe5` | Typing indicator: compute_typing_ms + delay_ms na UazAPI + playground |

---

### Fase 3 — Quebra de mensagem por pontuação

**Objetivo:** cada frase chega ao lead como uma bolha separada, com "Digitando…" proporcional entre elas.

| Arquivo | O que mudou |
|---|---|
| `backend-crm/services/humanization.py` | `split_by_punctuation()`: divide em partes por `. ! ? …`; frases curtas < 15 chars fundidas com a próxima |
| `backend-executors/app/runners/whatsapp.py` | `_split_message_by_punctuation()`: envia partes sequencialmente com `time.sleep` + `delay_ms` em cada |
| `backend-crm/routes/playground.py` | Campo `message_parts: List[str]` na resposta |

### Commits Fase 3

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `97497f4` | Quebra por pontuação: split_by_punctuation + executor + playground |

---

### Fase 4 — Paridade playground (campos visuais)

**Objetivo:** playground exibe preview fiel do comportamento temporal do agente real.

| Arquivo | O que mudou |
|---|---|
| `frontend-crm/src/services/api.ts` | 3 campos em `PlaygroundChatResponse`: `simulated_delay_seconds`, `typing_seconds`, `message_parts` |
| `frontend-crm/src/components/playground/MessageBubble.tsx` | `humanizationPreview` em `ChatMessage`; badges "Clock delay / Keyboard digitando / Layers N bolhas" |
| `frontend-crm/src/pages/Playground.tsx` | `buildBotMessage` + `revealExtraParts`: bolhas reveladas sequencialmente com loading proporcional ao tamanho |

### Commits Fase 4

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `353530e` | Frontend playground: preview de humanização com bolhas sequenciais |

---

### Fase 5 — Delay UI no AI Profile + Janela de horário

**Objetivo:** expor configurações de delay e disponibilidade na tela do AI Profile.

| Arquivo | O que mudou |
|---|---|
| `backend-core/app/api/ai_profiles.py` | 4 campos de delay em `AIProfileBase` e `AIProfileUpdate` |
| `frontend-crm/src/types/agente.ts` | 4 campos na `AgentConfig` + defaults em `DEFAULT_AGENT_CONFIG` |
| `frontend-crm/src/services/api.ts` | Leitura em `getConfig` e escrita em `saveConfig` |
| `frontend-crm/src/components/agente/CamadaPipeline.tsx` | `DrawerDelayResposta` com presets Imediato/Rápido/Normal/Lento/Personalizado |
| `backend-core/app/models/ai_profile.py` | Campo `availability_mode` (default `"24h"`) |
| `backend-core/app/db.py` | Migration idempotente para `availability_mode` |
| `backend-core/app/api/ai_profiles.py` | `availability_mode` exposto em `AIProfileBase` e `AIProfileUpdate` |
| `backend-crm/services/humanization.py` | `next_available_at()`: calcula próxima abertura da janela; `compute_scheduled_at()`: combina delay + janela |
| `backend-crm/services/whatsapp_inbound/inbound_handler.py` | `compute_scheduled_at()` unificado em vez de chamadas separadas |
| `frontend-crm/src/components/agente/CamadaPipeline.tsx` | `DrawerHorarioTrabalho`: modos 24h / Horário comercial / Personalizado com grade de dias e horas |

### Commits Fase 5

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `816a7bf` | Delay UI: campos + CamadaPipeline DrawerDelayResposta |
| 2 | `3afdc57` | Janela de horário: availability_mode + next_available_at + compute_scheduled_at + UI |

---

### Fase 6 — Áudio estático como mensagem de voz (myaudio/ptt)

**Objetivo:** uploads de áudio (mp3/ogg/opus) na base de conhecimento chegam ao WhatsApp como bolha de voz, não como arquivo.

| Arquivo | O que mudou |
|---|---|
| `backend-core/app/providers/uazapi_client.py` | `myaudio → send/myaudio` e `ptt → send/ptt` em `_MEDIA_TYPE_TO_ENDPOINT` |
| `backend-crm/database.py` | `ensure_knowledge_item_media_myaudio_type()`: recria tabela `knowledge_item_media` com `myaudio`/`ptt` no CHECK constraint |
| `backend-crm/routes/knowledge.py` | `_ext_to_media_type()`: retorna `"myaudio"` para mp3/ogg/opus |
| `backend-executors/app/runners/whatsapp.py` | `pre_send_media` do tipo `myaudio`/`ptt`: passa `delay_ms=3000` para exibir "Gravando áudio…" |
| `backend-crm/routes/playground.py` | Campo `audio_previews: List[str]` com URLs dos myaudio que seriam enviados |
| `frontend-crm/src/components/agente/CamadaConhecimento.tsx` | Ícone 🎙️ para myaudio/ptt; hint "áudio → mensagem de voz" no upload |
| `frontend-crm/src/components/playground/MessageBubble.tsx` | Ícone Mic e label "Mensagem de voz" para myaudio/ptt |
| `frontend-crm/src/services/api.ts` | `myaudio`/`ptt` no union type de `PlaygroundPreSendMediaItem.media_type`; campo `audio_previews` em `PlaygroundChatResponse` |

### Commits Fase 6

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `8dfa179` | Áudio estático myaudio/ptt: uazapi_client + knowledge + executor + playground + frontend |

---

## Checks de Validação

### Cenário P1 — Delay visível no playground
- [x] Configurar AI Profile com `first_reply_delay_min_seconds = 5`, `max = 15`
- [x] Enviar mensagem no playground
- [x] Confirmar: campo `simulated_delay_seconds` presente e entre 5–15

### Cenário P2 — Typing seconds proporcional ao texto
- [x] Gerar resposta curta (~20 chars) e longa (~200 chars)
- [x] Confirmar: `typing_seconds` maior para a resposta longa

### Cenário P3 — message_parts quebra por pontuação
- [x] Gerar resposta com múltiplas frases
- [x] Confirmar: `message_parts` lista cada frase como entrada separada

### Cenário P4 — Playground revela bolhas sequencialmente
- [x] Enviar mensagem no Playground.tsx
- [x] Confirmar: bolhas aparecem uma a uma com loading intermediário

### Cenário P5 — Audio preview no playground
- [x] Upload de mp3 na base de conhecimento
- [x] Confirmar: `audio_previews` retorna URL e ícone de microfone aparece na bolha

### Cenário C1 — Delay real no WhatsApp
- [x] Enviar mensagem de lead com delay configurado
- [x] Confirmar: job criado com `scheduled_at > now`; mensagem chega após o delay configurado

### Cenário C2 — Typing indicator no WhatsApp ("Digitando…")
- [x] Enviar resposta do agente
- [x] Confirmar: WhatsApp do lead exibe "Digitando…" por duração proporcional ao texto antes da mensagem chegar

### Cenário C3 — Quebra de mensagem em bolhas
- [x] Gerar resposta com 3+ frases
- [x] Confirmar: mensagens chegam em 3+ bolhas separadas, cada uma precedida de "Digitando…"

### Cenário C4 — Janela de horário bloqueia envio fora do horário
- [x] Configurar `availability_mode = "business_hours"` (Seg–Sex 09h–18h)
- [x] Enviar mensagem fora do horário
- [x] Confirmar: job agendado para o próximo horário disponível

### Cenário C5 — Áudio de voz no WhatsApp
- [x] Upload de mp3 na base de conhecimento
- [x] Confirmar: lead recebe bolha de voz (não arquivo de áudio) com "Gravando áudio…" antes
