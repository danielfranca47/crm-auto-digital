# Re-resolução de URL de mídia expirada no monitoramento de colaborador

**Branch:** `feat/monitoramento-colaborador-midia-url-expiracao`
**Status:** Todos os cenários validados (09/09/2026)

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

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `60a7a6f` | Nova coluna `messages.external_message_id` + gravação em `_save_message()`/`handle_monitor_inbound()` + docs de arquitetura atualizados |

**Detalhes do commit `60a7a6f`:**
- `backend-crm/database.py` — `ensure_column(conn, "messages", "external_message_id", "external_message_id TEXT")`
- `backend-crm/services/collab_monitor/monitor_inbound_handler.py` — `_save_message()` ganha o parâmetro `external_message_id`; `handle_monitor_inbound()` passa a variável já extraída do payload do webhook
- `docs/architecture/collab-monitor.md` — documenta a nova coluna em "Tratamento de mídia" e atualiza a entrada de "Fora do escopo" sobre re-resolução de URL

### Relatório da Fase 1 — o que mudou na prática

**Antes:** quando uma mensagem de áudio ou imagem chegava de um colaborador
monitorado, o sistema sabia o id original dela no WhatsApp só durante o
processamento inicial (transcrição/descrição) — depois disso, esse id era
perdido para sempre.

**Agora:** esse id fica guardado junto com a mensagem no banco. Isso não
muda nada visível hoje (nenhuma tela usa esse dado ainda), mas destrava a
possibilidade de, no futuro, reabrir o áudio ou a imagem de uma conversa
antiga mesmo que o link original já tenha expirado.

**Para validar:** Cenário C1 e C2, abaixo — exigem enviar uma mensagem real
de áudio/imagem para uma instância de colaborador monitorada já conectada e
conferir a coluna no banco.

---

## Checks de Validação

Sem UI para testar via browser (mudança é só de persistência de dado, sem
consumidor). Não havia nenhuma instância de colaborador conectada localmente
(banco local nunca teve esse fluxo testado) — decisão tomada com o
utilizador: em vez de montar o setup completo (3 backends + túnel público +
QR real) só para validar a gravação de uma coluna, os cenários chamam
`handle_monitor_inbound()` diretamente com payloads no mesmo formato que a
UazAPI envia, contra um banco SQLite isolado — exercita o código real de
produção sem precisar de WhatsApp de verdade.

### Cenário C1 — Áudio (payload real simulado)
- [x] Registrar instância de colaborador de teste + chamar
  `handle_monitor_inbound()` com `message_type="audio"`,
  `message_id="WAMID_TEST_AUDIO_001"`, `media_url` de teste
- [x] Confirmar via query no banco que `messages.external_message_id` foi
  preenchida com o id da mensagem
- [x] Confirmar que `body` (placeholder `"[Áudio] (processando…)"`) e
  `media_url` continuam sendo preenchidos normalmente (comportamento
  existente, sem regressão)
- **Validado em:** 09/09/2026 — script `test_external_message_id.py`
  (scratchpad), resultado `PASS`: linha da mensagem com
  `external_message_id='WAMID_TEST_AUDIO_001'`, `media_url` e `body`
  corretos

### Cenário C2 — Imagem (payload real simulado)
- [x] Mesma verificação do C1, com `message_type="image"`,
  `message_id="WAMID_TEST_IMAGE_002"`
- **Validado em:** 09/09/2026 — mesmo script, resultado `PASS`: linha da
  mensagem com `external_message_id='WAMID_TEST_IMAGE_002'`, `media_url` e
  `body` (`"[Imagem] (processando…)"`) corretos

---

## Fase 2 — Diagnóstico + Correção: colunas de `leads` perdidas em banco fresco (09/09/2026)

### Problema identificado

Descoberto ao rodar o teste isolado da Fase 1 contra um banco SQLite
totalmente fresco (nunca inicializado antes): `init_db()` falhava porque
`leads` não tinha a coluna `wa_display_name`.

Causa raiz: `_migrate_leads_company_or_contact()`
(`backend-crm/database.py`) recria a tabela `leads` do zero (`CREATE TABLE
leads_new` + `INSERT ... SELECT` com uma lista explícita de colunas). Cinco
colunas adicionadas via `ensure_column()` antes dessa migração
(`branches_selected`, `sales_flow_wait`, `knowledge_categories_shown`,
`wa_display_name`, `acquisition_channel`) não constam nessa lista — a
migração as apaga ao recriar a tabela. `collab_monitor_instance_id` já era
re-adicionada logo após a recriação (dentro da própria função), por isso
nunca foi afetada.

Nunca se manifestou em ambiente real porque a migração tem guarda de
idempotência (`if company_col and company_col["notnull"] == 0: return`) —
todo banco existente já passou por ela antes dessas 5 colunas terem sido
criadas, então ela nunca mais roda de fato nesses bancos. Só aparece ao
inicializar um banco do zero (ex.: ambiente de teste limpo).

### Correção

Reordenado `init_db()`: as 5 colunas que a migração não preserva agora são
re-adicionadas via `ensure_column()` **depois** dela (chamada idempotente,
sem efeito em bancos já migrados). As 5 colunas que a migração já preservava
(`checkout_token`, `is_playground`, `detected_language`, `phases_triggered`,
`triggers_fired`) continuam sendo adicionadas **antes**, porque o `SELECT`
da migração as lê da tabela antiga por nome.

| Arquivo | Mudança |
|---|---|
| `backend-crm/database.py` | `init_db()`: `ensure_column()` de `branches_selected`/`sales_flow_wait`/`knowledge_categories_shown`/`wa_display_name`/`acquisition_channel`/`collab_monitor_instance_id` movidos para depois de `_migrate_leads_company_or_contact(conn)` |

Validado com dois scripts isolados (mesmo padrão do teste da Fase 1, banco
SQLite fresco):
- Confirmado: as 6 colunas existem em `leads` após `init_db()` num banco
  novo — `PASS`.
- `init_db()` chamado duas vezes seguidas (simula reinício do backend) —
  sem erro, idempotente.

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `<preencher após commit>` | Fix: reordenar `ensure_column()` das colunas de `leads` perdidas em banco fresco |

---

## Ajustes Possíveis Pós-Implementação

- Endpoint de re-resolução sob demanda (ex.: `GET
  /api/collab-monitor/messages/{id}/media-url`) — construir junto da tela de
  mídia bruta, quando essa implementação nascer (é a consumidora natural do
  dado persistido aqui). Já documentado em `docs/architecture/collab-monitor.md`,
  seção "Fora do escopo" — não precisa de arquivo próprio agora.
