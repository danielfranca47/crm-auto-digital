# Re-resolução de URL de mídia expirada no monitoramento de colaborador

**Branch:** `feat/monitoramento-colaborador-midia-url-expiracao`
**Status:** Em andamento

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`monitoramento-colaborador-midia.md` (tratamento de áudio/imagem no
monitoramento de colaborador — ver
[`docs/architecture/collab-monitor.md`](../architecture/collab-monitor.md)).

`messages.media_url` hoje guarda a URL resolvida via UazAPI
(`/message/download`) para áudio, ou a URL crua do webhook (`fileURL`) para
imagem — mais confiável que a URL original do webhook, mas **não é
permanente**: pode expirar com o tempo (prazo exato desconhecido, depende da
política da UazAPI/WhatsApp). Se uma futura tela de mídia precisar tocar
áudio ou exibir imagem de mensagens antigas, a URL persistida pode já não
funcionar.

---

## Diagnóstico (Plan Mode)

### Já existe?

Não. E o gap é mais fundo do que "a URL pode expirar": o dado necessário
para re-resolver a URL mais tarde (`external_message_id`, o id da mensagem
no WhatsApp/UazAPI, exigido por `/message/download`) já chega no payload do
job `collab_monitor.media.process`
(`monitor_inbound_handler.py:221` — `handle_monitor_inbound()`) e é usado
ali mesmo por `media_worker.py::_process_audio()`
(`download_audio_url_from_uazapi(instance_token, external_message_id)`) —
mas **nunca é persistido** em `messages`. Assim que o job completa, o dado
desaparece. Uma re-resolução futura (depois que existir uma tela de mídia
bruta) não teria como funcionar, porque faltaria o id necessário para chamar
`/message/download` de novo.

### Consumidor real

Hoje nada exibe mídia bruta — `CollabMonitorInbox.tsx`
(`frontend-crm/src/pages/CollabMonitorInbox.tsx`) só renderiza texto
(transcrição/descrição já processada pelo `media_worker.py`). Está listado
explicitamente em "Fora do escopo" de `docs/architecture/collab-monitor.md`.
Construir agora o endpoint de re-resolução + UI seria especulativo, sem como
validar ao vivo (nenhum consumidor real para testar contra).

### Decisão de escopo

Implementar **só a base**: persistir `external_message_id` para toda
mensagem de mídia (áudio e imagem). O endpoint de re-resolução sob demanda e
a UI de mídia bruta ficam para quando essa tela for construída — ela é a
consumidora natural do dado persistido aqui. Isso evita trabalho sem
consumidor testável hoje, mas garante que o pré-requisito indispensável já
existe quando a tela nascer.

---

## Problemas Identificados (estado anterior)

1. **`external_message_id` não persiste:** chega no payload do job
   `collab_monitor.media.process` (`monitor_inbound_handler.py:196-225`),
   mas `_save_message()` (`monitor_inbound_handler.py:120-136`) não grava
   esse campo em `messages` — a `INSERT INTO messages` não tem a coluna.
2. **`messages` não tem coluna para o id externo:** schema atual
   (`backend-crm/database.py:1160-1169` + `ensure_column` em
   `database.py:1332-1333`) só tem `message_type` e `media_url`, nenhuma
   coluna para o id da mensagem no WhatsApp/UazAPI.

---

## Abordagem

```
Webhook inbound (áudio/imagem)
  → handle_monitor_inbound() já extrai external_message_id (payload["message_id"])
  → _save_message() grava em messages, agora incluindo external_message_id
  → job collab_monitor.media.process roda normalmente (sem mudança) —
    resolve/transcreve/descreve usando o external_message_id do PAYLOAD do job
  → messages.external_message_id fica disponível para uso futuro, mesmo
    depois do job completar e o payload do job deixar de existir
```

---

## Plano de Implementação

### Fase 1 — Persistir external_message_id em `messages`

**Objetivo:** garantir que toda mensagem de mídia do monitoramento de
colaborador guarda o id original do WhatsApp, pré-requisito para uma futura
re-resolução de URL.

| Arquivo | O que muda |
|---|---|
| `backend-crm/database.py` | `ensure_column(conn, "messages", "external_message_id", "external_message_id TEXT")` — nova coluna nullable, ao lado de `message_type`/`media_url` |
| `backend-crm/services/collab_monitor/monitor_inbound_handler.py` | `_save_message()` ganha parâmetro `external_message_id: Optional[str] = None`, incluído na `INSERT INTO messages`; `handle_monitor_inbound()` passa `external_message_id=external_message_id or None` (variável já extraída na linha 162, só não era usada além do payload do job) |

Sem mudança em `media_worker.py` — ele já recebe `external_message_id` via
payload do job (fluxo síncrono de processamento inicial, que continua
igual); a mudança aqui é só sobre persistência para uso *futuro*.

Sem mudança em `routes/collab_monitor.py` nem no frontend — a coluna nova
não é exposta em nenhuma rota ainda (não há consumidor).

---

## Checks de Validação

Sem UI para testar via browser (mudança é só de persistência de dado, sem
consumidor). Validação via inspeção direta do banco após mensagem real.

### Cenário C1 — Áudio real para instância monitorada
- [ ] Enviar um áudio de teste para o WhatsApp de uma instância monitor já
  conectada (ambiente local ou produção, conforme disponibilidade)
- [ ] Confirmar via query no banco (`SELECT external_message_id FROM
  messages WHERE id = <id da mensagem>`) que a coluna foi preenchida com o
  id da mensagem
- [ ] Confirmar que `body`/`media_url` continuam sendo preenchidos
  normalmente pelo `media_worker.py` (comportamento existente, não deve
  quebrar)

### Cenário C2 — Imagem real para instância monitorada
- [ ] Mesma verificação do C1, mas com imagem

---

## Ajustes Possíveis Pós-Implementação

- Endpoint de re-resolução sob demanda (ex.: `GET
  /api/collab-monitor/messages/{id}/media-url`) — construir junto da tela de
  mídia bruta, quando essa implementação nascer (é a consumidora natural do
  dado persistido aqui).
