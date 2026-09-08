# Tratamento de mídia (áudio/imagem) no monitoramento de colaborador

**Branch:** `feat/monitoramento-colaborador-midia`
**Status:** Em andamento

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`monitoramento-colaborador-classificacao-ia.md` (classificação de estágio do
lead monitorado via IA — ver
[`docs/architecture/collab-monitor.md`](../architecture/collab-monitor.md)).

Hoje `services/collab_monitor/monitor_inbound_handler.py::handle_monitor_inbound()`
ignora mensagens sem texto (`message_text` vazio) — imagem, áudio, vídeo,
figurinha, documento. A mensagem nem é salva no histórico do lead. Isso tem
dois efeitos ruins:
1. O histórico do lead monitorado fica incompleto.
2. A classificação de estágio via IA (`classifier.py`) não enxerga nada do
   que foi comunicado por áudio/imagem — pode perder sinais claros de avanço
   do funil (ex.: lead manda print do comprovante de pagamento, ou áudio
   confirmando fechamento).

**Decisões de produto validadas com o utilizador:**
- **Imagem:** descrever com IA (reaproveitar visão do GPT-4o-mini, já usada
  pelo Agente Espião) — a descrição vira texto no histórico e alimenta o
  classificador.
- **Áudio:** transcrever reaproveitando o MESMO toggle de conta
  `ai_profile.audio_transcription_enabled` já usado pelo pipeline real.
- **Vídeo/figurinha/documento/reação:** sem IA (igual ao pipeline real —
  nunca descritos nem lá), mas passam a salvar um placeholder no histórico
  (ex.: `[Vídeo]`) em vez de sumir por completo.

---

## Problemas Identificados (estado anterior)

1. **Mensagens de mídia descartadas:** `handle_monitor_inbound()` (linhas
   ~137-140) retorna `{"status": "ignored", "reason": "missing_text"}` para
   qualquer mensagem sem `message_text` — não salva nada, não cria lead se
   for a primeira mensagem.
2. **Webhook não repassa `media_url` pro monitor:** `routes/webhooks.py`,
   bloco `is_monitor_instance` (~linhas 338-356), monta `monitor_payload`
   sem `media_url` — diferente do bloco irmão do Espião (linhas 296-330),
   que já extrai `media_url` de `fileURL`/`mediaUrl`/`_content_obj.URL`.

---

## Abordagem

### Por que não copiar direto o padrão do Agente Espião

O Espião transcreve áudio com uma versão simplificada
(`media_processor.py::_transcribe_audio`) que baixa `media_url` direto — mas
o pipeline REAL de produção (`services/whatsapp_inbound/inbound_handler.py`,
linhas ~309-359) usa um caminho mais confiável: PTT do WhatsApp frequentemente
vem com uma URL que exige autenticação da sessão (`mmg.whatsapp.net`), então
o inbound real **sempre** resolve a URL pública via UazAPI
(`POST {uazapi}/message/download`, usando o token da instância) antes de
transcrever — `services/audio_transcription.py::download_audio_url_from_uazapi()`
+ `transcribe_audio_from_url()`, com fallback pro `media_url` direto só se a
resolução falhar. Reaproveitar este caminho já-testado é mais seguro para o
monitoramento (que quer histórico completo e confiável).

Já para **imagem**, o pipeline real nunca descreve (só
video/imagem/figurinha/documento → `_apply_media_fallback`, resposta padrão
configurável ou ignorar). O único lugar que já descreve imagem é o Espião
(`media_processor.py::_describe_image`, GPT-4o-mini visão, sem download
prévio). Extraída para um módulo compartilhado `services/image_description.py`
(mesmo precedente já usado por `audio_transcription.py`) — evita duplicar a
chamada à API de visão; `media_processor.py` do Espião passa a chamar a
função extraída (comportamento do Espião não muda).

### Onde persistir a URL/descrição

`messages` já tem `message_type` (default `'text'`, não usado ainda por
`_save_message`), mas não tem coluna para a URL bruta da mídia. Nova coluna
`messages.media_url` (nullable, via `ensure_column()`) — além desta feature,
a implementação pendente `monitoramento-colaborador-tela-whatsapp-web.md`
("navegação de mídia") vai precisar da URL real da mídia. `body` continua
guardando texto (transcrição/descrição/placeholder).

### Fluxo resultante

```
handle_monitor_inbound(payload)
  ├─ tem message_text? → salva normal (sem mudança)
  ├─ sem texto, áudio ou imagem (media_url resolvido)?
  │    → salva mensagem já (body placeholder "processando…", message_type,
  │      media_url) → cria job collab_monitor.media.process
  ├─ sem texto, vídeo/figurinha/documento/reação → salva placeholder direto
  │    (ex. "[Vídeo]"), sem job; se from_me=False, já enfileira
  │    collab_monitor.classify.local
  └─ sem texto e sem media_url resolvível → mesmo caminho de placeholder
     direto (fallback defensivo)

Worker collab_monitor.media.process (novo loop em app.py)
  ├─ audio_transcription_enabled desligado? → placeholder "desativado"
  ├─ áudio: download_audio_url_from_uazapi + transcribe_audio_from_url →
  │    body = "[Áudio]: <texto>"
  ├─ imagem: image_description.describe_image_from_url → body = "[Imagem]: <descrição>"
  └─ se from_me=False → cria job collab_monitor.classify.local agora
```

Continua completamente isolado do pipeline de IA real: nenhum destes
caminhos chama orchestrator/decision_engine/guardrail de resposta.

---

## Plano de Implementação

### Fase 1 — Backend

**Objetivo:** mensagens de mídia deixam de ser descartadas; áudio/imagem
viram texto (transcrição/descrição) no histórico e alimentam o classificador.

| Arquivo | O que muda |
|---|---|
| `backend-crm/database.py` (`init_db()`) | `ensure_column(conn, "messages", "media_url", "media_url TEXT")` |
| `backend-crm/routes/webhooks.py` | Bloco `is_monitor_instance`: adiciona extração de `media_url` ao `monitor_payload` |
| `backend-crm/services/image_description.py` (novo) | `describe_image_from_url()` — extraído de `spy_agent/media_processor.py` |
| `backend-crm/services/spy_agent/media_processor.py` | Passa a chamar `image_description.describe_image_from_url()` (mesmo comportamento) |
| `backend-crm/services/collab_monitor/monitor_inbound_handler.py` | `_save_message()` aceita `message_type`/`media_url`; `handle_monitor_inbound()` trata áudio/imagem/vídeo/figurinha/documento/reação em vez de ignorar |
| `backend-crm/services/jobs_service.py` | Nova constante `TYPE_COLLAB_MONITOR_MEDIA = "collab_monitor.media.process"` |
| `backend-crm/services/collab_monitor/media_worker.py` (novo) | `process_pending_collab_monitor_media_jobs()` + `process_collab_monitor_media_job()` |
| `backend-crm/app.py` | Novo `_collab_monitor_media_worker_loop()` registrado no `lifespan` |
| `backend-crm/scripts/test_collab_monitor_media_flow.py` (novo) | Script de validação ponta a ponta (Cenários C1-C4) |
| `backend-crm/scripts/test_collab_monitor_classify_flow.py` | Schema de teste atualizado com a nova coluna `media_url` (senão o `INSERT` de `_save_message` falha) |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `f8425fd` | Tratamento de áudio/imagem/vídeo/figurinha/documento no monitoramento de colaborador |

### Relatório da Fase 1 — o que mudou na prática

**Antes:** qualquer mensagem sem texto (áudio, imagem, vídeo, figurinha,
documento) enviada num WhatsApp monitorado era descartada — nem aparecia no
histórico do lead.

**Agora:** áudio é transcrito (Whisper) e imagem é descrita (visão do
GPT-4o-mini) automaticamente, virando texto no histórico — a mesma IA que
classifica o estágio do lead passa a enxergar esse conteúdo. Vídeo,
figurinha, documento e reação continuam sem IA (igual ao pipeline real do
bot), mas deixam pelo menos um aviso no histórico (ex.: "[Vídeo]") em vez de
sumir. A transcrição de áudio respeita a mesma preferência de conta
(`audio_transcription_enabled`) já usada pelo bot real.

**Para validar:** Cenários C1-C4, abaixo — já rodados com o script
`scripts/test_collab_monitor_media_flow.py` (chamadas de IA/UazAPI
mockadas, valida o mecanismo). O resultado real do Whisper/visão sobre
áudio/imagem de verdade fica para um teste manual/ao vivo.

---

## Checks de Validação

### Cenário C1 — Áudio transcrito
- [x] Simular payload inbound `message_type="audio"` sem texto
- [x] Rodar `process_pending_collab_monitor_media_jobs()`
- [x] Confirmar `messages.body` com transcrição e job de classificação criado
- **Validado em:** 08/09/2026 — `scripts/test_collab_monitor_media_flow.py`, chamadas mockadas (determinístico): placeholder de processamento salvo na hora, job de classify só criado depois da transcrição.

### Cenário C2 — Imagem descrita
- [x] Simular payload inbound `message_type="image"` sem texto
- [x] Rodar o worker de mídia
- [x] Confirmar `messages.body` com descrição e job de classificação criado
- **Validado em:** 08/09/2026 — mesmo script.

### Cenário C3 — Vídeo/figurinha/documento (placeholder direto)
- [x] Simular payload inbound `message_type="video"` sem texto
- [x] Confirmar `messages.body = "[Vídeo]"` salvo imediatamente, sem job de mídia, com job de classificação criado
- **Validado em:** 08/09/2026 — mesmo script.

### Cenário C4 — Toggle de transcrição desligado
- [x] Simular `audio_transcription_enabled=False` no AI Profile
- [x] Confirmar placeholder de "transcrição desativada", sem chamada real ao Whisper
- **Validado em:** 08/09/2026 — mesmo script; `transcribe_audio_from_url` mockado e nunca chamado (`assert_not_called`).

---

## Ajustes Possíveis Pós-Implementação

- **URL de mídia pode expirar:** `media_worker.py` já persiste a URL
  resolvida via UazAPI (`/message/download`) para áudio, mais confiável que
  a URL crua do webhook — mas essa URL pode ainda assim expirar com o
  tempo (não é permanente). Se uma futura tela de mídia
  (`monitoramento-colaborador-tela-whatsapp-web.md`) precisar tocar áudio
  muito tempo depois do recebimento, pode precisar re-resolver a URL on
  demand em vez de confiar na persistida.
