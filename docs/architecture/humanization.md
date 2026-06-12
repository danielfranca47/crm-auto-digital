# Humanização Comportamental do Agente

O sistema simula o ritmo humano de conversação em três dimensões: **tempo de resposta**, **indicador de digitação** e **quebra de mensagem em bolhas**. O comportamento é controlado por campos do AI Profile e implementado no módulo `backend-crm/services/humanization.py`.

---

## Módulo `humanization.py`

**Localização:** `backend-crm/services/humanization.py`

| Função | Responsabilidade |
|---|---|
| `compute_reply_delay(ai_profile, is_first_message)` | Sorteia delay em segundos entre `min` e `max` do AI Profile; retorna `0` se não configurado |
| `compute_typing_ms(text)` | Retorna duração do "Digitando…" em ms: 40ms/char, mínimo 1000ms, máximo 8000ms |
| `split_by_punctuation(text, min_chars=15)` | Divide texto em partes por `. ! ? …`; parágrafos duplos sempre criam quebra; frases curtas (< 15 chars) são fundidas com a próxima |
| `next_available_at(ai_profile, now_utc)` | Calcula o próximo instante dentro da janela de horário do agente; retorna `None` se já estiver dentro da janela |
| `compute_scheduled_at(ai_profile, is_first_message)` | Ponto de entrada principal: combina delay de humanização + janela de horário em um único `datetime` (ou `None` se imediato) |

---

## Delay de Resposta

### Campos do AI Profile

| Campo | Default | Descrição |
|---|---|---|
| `first_reply_delay_min_seconds` | `0` | Delay mínimo (s) para a **primeira** mensagem de um lead |
| `first_reply_delay_max_seconds` | `0` | Delay máximo (s) para a primeira mensagem |
| `reply_delay_min_seconds` | `0` | Delay mínimo (s) para mensagens subsequentes |
| `reply_delay_max_seconds` | `0` | Delay máximo (s) para mensagens subsequentes |

Quando `min == max == 0`, não há delay (comportamento padrão).

### Fluxo

```
inbound_handler.py
  → conta mensagens do lead para detectar is_first_message
  → compute_scheduled_at(ai_profile, is_first_message)
      ├─ compute_reply_delay()   # sorteia int entre min e max
      └─ next_available_at()     # desloca para fora da janela se necessário
  → create_job(scheduled_at=resultado)
      └─ worker respeita scheduled_at: job só é executado quando scheduled_at <= now
```

---

## Typing Indicator ("Digitando…")

O campo `delay` da UazAPI exibe automaticamente "Digitando…" para mensagens de texto e "Gravando áudio…" para mensagens de voz durante o período configurado.

### Fórmula

```python
delay_ms = min(max(len(text) * 40, 1000), 8000)  # 40ms/char, entre 1s e 8s
```

### Propagação

```
executor (whatsapp.py)
  → calcula delay_ms inline
  → POST /whatsapp/send (backend-core) com delay_ms
       → uazapi_client.send_text(delay_ms=...)
           → UazAPI payload: { "delay": delay_ms }
```

Implementado em dois pontos independentes (serviços separados):
- `backend-crm/services/humanization.py` → `compute_typing_ms()` (usado pelo playground)
- `backend-executors/app/runners/whatsapp.py` → cálculo inline antes do envio

---

## Quebra de Mensagem em Bolhas

O executor divide cada resposta em partes antes do envio. Cada parte chega ao WhatsApp como uma bolha separada, precedida de "Digitando…".

### Regras de split (`split_by_punctuation`)

- Quebra após `. ! ? …` quando a parte resultante tem ≥ 15 chars
- Parágrafos duplos (`\n\n`) sempre criam quebra, independente do tamanho
- Frases curtas (< 15 chars) são fundidas com a próxima para evitar bolhas triviais

### Fluxo no executor

```python
parts = _split_message_by_punctuation(text)
for i, part in enumerate(parts):
    delay_ms = min(max(len(part) * 40, 1000), 8000)
    if i > 0:
        time.sleep(len(parts[i-1]) * 0.05)   # pausa proporcional à parte anterior
    core_client.send_whatsapp_message(text=part, delay_ms=delay_ms)
```

---

## Janela de Horário (Disponibilidade)

### Campo do AI Profile

| Campo | Enum | Default |
|---|---|---|
| `availability_mode` | `"24h"` \| `"business_hours"` \| `"custom"` | `"24h"` |

- **`24h`**: sem restrição de horário
- **`business_hours`**: Seg–Sex, 09h00–18h00 no timezone do AI Profile (`timezone`)
- **`custom`**: grade de dias e horários configurada manualmente na UI

### Comportamento

`next_available_at()` retorna `None` se o momento atual já estiver dentro da janela (sem deslocamento). Se estiver fora, retorna o próximo instante de abertura — combinado com o delay de humanização em `compute_scheduled_at()`.

O campo `followup_allowed_hours` (legado) existe no AI Profile mas não é utilizado pelo `inbound_handler`. O controle de horário é feito via `availability_mode`.

---

## Áudio de Voz (myaudio/ptt)

Arquivos de áudio (mp3, ogg, opus) salvos na base de conhecimento são tratados como **mensagens de voz** (`myaudio`), não como arquivos de áudio comuns.

### Tipos mapeados em `uazapi_client.py`

| Tipo | Endpoint UazAPI | Comportamento no WhatsApp |
|---|---|---|
| `myaudio` | `send/myaudio` | Bolha de voz (alternativa ao PTT) |
| `ptt` | `send/ptt` | Bolha de voz Push-to-Talk |
| `audio` | `send/audio` | Player de arquivo de áudio |

### Fluxo de envio de myaudio

```
executor (whatsapp.py)
  → detecta pre_send_media com type = "myaudio" ou "ptt"
  → passa delay_ms = 3000 (exibe "Gravando áudio…" por 3s)
  → core_client.send_whatsapp_media(type="myaudio", url=..., delay_ms=3000)
```

### Reclassificação no upload

`backend-crm/routes/knowledge.py` → `_ext_to_media_type()`:
- `.mp3`, `.ogg`, `.opus` → `"myaudio"` (mensagem de voz)
- Outros formatos → mapeamento padrão

---

## Paridade Playground

O playground retorna campos de preview que espelham o comportamento temporal do agente real. Ver campos completos em [playground-parity.md](playground-parity.md).

| Campo na resposta | O que simula |
|---|---|
| `simulated_delay_seconds` | Delay antes de responder (sorteado entre min/max) |
| `typing_seconds` | Duração do "Digitando…" que seria exibido |
| `message_parts` | Como a resposta seria dividida em bolhas |
| `audio_previews` | URLs dos myaudio que seriam enviados como voz |

---

## Arquivos Críticos

| Arquivo | Responsabilidade |
|---|---|
| `backend-crm/services/humanization.py` | Módulo central: delay, typing, split, janela de horário |
| `backend-crm/services/whatsapp_inbound/inbound_handler.py` | Aplica `compute_scheduled_at()` ao criar jobs inbound |
| `backend-executors/app/runners/whatsapp.py` | Quebra por pontuação, typing delay no envio real |
| `backend-core/app/providers/uazapi_client.py` | `delay_ms` em `send_text`/`send_media`; endpoints myaudio/ptt |
| `backend-core/app/api/whatsapp_send.py` | Expõe `delay_ms` nos request bodies |
| `backend-crm/routes/playground.py` | Campos de preview na `PlaygroundChatResponse` |
