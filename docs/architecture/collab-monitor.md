# Monitoramento de WhatsApp de Colaborador

Base para os planos Scale/Enterprise (ver
[`docs/plans/scale-enterprise-roadmap.md`](../plans/scale-enterprise-roadmap.md)):
permite conectar o WhatsApp comercial de um colaborador da equipe apenas para
**observação** — alimenta o CRM com os leads/conversas desse colaborador, sem
que o agente de IA responda por ele. Via UazAPI (mesmo provider das instâncias
de agente), nunca a API oficial da Meta.

Diferente do **Agente Espião** (`routes/spy_agent.py` +
`services/spy_agent/*`): aquele é uma janela de observação **temporária** (14
dias) para sugerir ajustes de **configuração do AI Profile**, 1 instância por
conta, nunca cria leads. Este é **permanente**, multi-instância (uma por
colaborador), e cria leads reais no Kanban.

---

## `role` na conexão WhatsApp (backend-core)

`WhatsappConnection.role` (`backend-core/app/models/whatsapp_connection.py`) —
`"agent"` (default) ou `"monitor"`. É o que garante que uma conta pode ter
várias instâncias WhatsApp sem que o agente principal seja afetado:

- `whatsapp_connections.get_connection_for_user()` filtra `role == "agent"` —
  usado por `GET /whatsapp-connections/resolve-by-user` (consumido pelo
  executor real para saber de qual instância o agente deve enviar). Uma
  instância `role="monitor"` nunca é candidata a esse resolve.
- `upsert_connection()`/`upsert_connection_optional_token()` resolvem a linha
  existente por **`instance_id`** (não por `user_id`) — pré-requisito para
  multi-instância: antes, conectar uma 2ª instância para a mesma conta
  sobrescrevia a linha da 1ª. Ver [`whatsapp-connection.md`](whatsapp-connection.md)
  para o fluxo de conexão em si (QR/pareamento).
- `POST /whatsapp-instances/init` e `/connect` aceitam `role` opcional no
  payload (default `"agent"`, mantém compatibilidade).

**Defesa em profundidade contra envio:** `backend-core/app/api/whatsapp_send.py`
(`/whatsapp/send` e `/whatsapp/send-media`) rejeitam com `403
instance_not_allowed_to_send` qualquer tentativa de envio por uma instância
cujo `role != "agent"` — independente do que aconteça no roteamento do
webhook (camada abaixo), esta é a garantia final de que uma instância monitor
nunca envia mensagem.

---

## Cadastro de instância de colaborador (backend-crm)

**Tabela:** `collab_monitor_instances` (`user_id`, `instance_id`,
`collaborator_name`, `status`, `created_at`, `updated_at`) — N linhas por
conta, uma por colaborador.

**Rotas:** `backend-crm/routes/collab_monitor.py`, prefixo `/api/collab-monitor`:

| Rota | Descrição |
|---|---|
| `POST /instances` | Cadastra colaborador + inicia conexão (QR ou código de pareamento, se `phone` informado) — cria a instância no core com `role="monitor"` |
| `GET /instances` | Lista instâncias da conta, enriquecidas com `phone_e164`/`connection_status` ao vivo |
| `DELETE /instances/{id}` | Remove o cadastro (não desconecta a instância no core) |
| `POST /instances/{id}/reconnect` | Reconecta via QR ou código de pareamento, preserva o cadastro |
| `GET /conversations` | Agrega leads `category='monitoring'` por colaborador — base da tela de leitura (ver abaixo). Filtro opcional `?instance_id=` |

Reaproveita os mesmos helpers genéricos de conexão do core
(`connect_core_whatsapp_instance`/`init_core_whatsapp_instance`) que o Agente
Espião já usa — mesmo padrão de QR/pareamento de
[`whatsapp-connection.md`](whatsapp-connection.md).

---

## Roteamento do webhook e ingestão (backend-crm)

`backend-crm/routes/webhooks.py` (`POST /webhooks/whatsapp/uazapi`) — a
checagem `is_monitor_instance(instance_id)` fica na mesma posição do
`is_spy_instance` do Agente Espião: **antes do filtro `from_me`**, porque as
mensagens que o colaborador envia (não só as que recebe) também precisam ser
capturadas.

```
event="messages" → is_monitor_instance(instance_id)?
  → services/collab_monitor/monitor_inbound_handler.py::handle_monitor_inbound()
      → find_or_create_monitor_lead()  — chave (user_id, phone, instance_id)
      → grava mensagem em `messages` (channel='whatsapp')
      → NUNCA chama guardrail / orchestrator / LLM
      → NUNCA enfileira job whatsapp.inbound.n8n ou whatsapp.send.local
```

`services/collab_monitor/monitor_inbound_handler.py`:

- `is_monitor_instance(instance_id)` / `get_monitor_info(instance_id)` —
  resolvem contra `collab_monitor_instances`.
- `find_or_create_monitor_lead()` — a chave de dedup inclui `instance_id`:
  o mesmo telefone falando com dois colaboradores monitorados diferentes
  gera **dois leads**, um por colaborador, nunca o mesmo card. Lead nasce
  com `category='monitoring'`, `collab_monitor_instance_id=<instance_id>`,
  `bot_disabled=1` e `bot_disabled_reason='collab_monitor'` (segunda camada
  de segurança independente do roteamento do webhook).
- Mensagens gravadas em `messages` (mesma tabela do fluxo real, para
  aparecerem no histórico do card): `model='inbound'` para a mensagem do
  lead, `model='human_agent'` para a mensagem que o próprio colaborador
  envia (`fromMe`) — nunca confundido com resposta de IA (`model=<llm
  model>` no fluxo real).
- Mensagens de mídia (áudio/imagem/vídeo/figurinha/documento/reação) — ver
  seção "Tratamento de mídia" abaixo.

---

## Unicidade de telefone por lead (`leads`)

`leads.collab_monitor_instance_id` (nullable) tagueia o lead ao colaborador
que o originou. A regra "1 lead por telefone por conta" (antes um único
índice `UNIQUE(user_id, phone)`) foi dividida em dois índices parciais —
`ensure_leads_phone_uniqueness()` (`backend-crm/database.py`):

```sql
CREATE UNIQUE INDEX ux_leads_user_phone
  ON leads(user_id, phone) WHERE collab_monitor_instance_id IS NULL;

CREATE UNIQUE INDEX ux_leads_user_phone_collab
  ON leads(user_id, phone, collab_monitor_instance_id) WHERE collab_monitor_instance_id IS NOT NULL;
```

Leads normais (`collab_monitor_instance_id IS NULL` — todo lead que já
existia antes desta coluna nascer) mantêm exatamente a regra antiga: 1 por
telefone por conta. Leads de monitoramento passam a ser únicos por (conta,
telefone, colaborador) — o mesmo telefone pode ter um lead por colaborador
que efetivamente contatou.

Ver [`leads-schema.md`](leads-schema.md) para a tabela geral de pontos de
criação de lead (este é mais um ponto: origem `whatsapp_inbound`, `companyName`
sempre `NULL`, `contactName` = `wa_display_name` ou o telefone).

---

## Kanban — coluna "Monitorado"

`frontend-crm/src/data/mockData.ts` (`KANBAN_COLUMNS`) e
`src/types/crm.ts` (`LeadStatus`) — categoria `monitoring`, coluna dedicada
("Monitorado"), separada do pipeline normal do agente. Lead nasce aqui, mas
sai automaticamente assim que a classificação de estágio (abaixo) identificar
sinal claro de avanço.

`frontend-crm/src/components/ManageCollaboratorsDialog.tsx` — dialog de
cadastro/gerenciamento (botão "Gerenciar colaboradores" na própria página
`/monitoramento`, ver "Tela de leitura estilo WhatsApp Web" abaixo): nome do
colaborador, QR/pareamento, lista de instâncias com status,
reconectar/remover.

`frontend-crm/src/components/LeadCard.tsx` exibe uma badge "Monitorado"
sempre que `lead.collabMonitorInstanceId` não for nulo — mantém o card
identificável como conduzido por humano mesmo depois de sair da coluna
"Monitorado" e passar a compartilhar coluna com leads do bot.

---

## Classificação de estágio do lead monitorado (IA read-only)

A cada mensagem inbound do lead monitorado (nunca do colaborador/`from_me`),
`handle_monitor_inbound()` enfileira um job `collab_monitor.classify.local`
(`services/jobs_service.py`) — mesmo padrão de job interno usado por
`spy.media.process` (lease via CAS, retry/backoff), processado por um loop
próprio registrado no `lifespan` de `app.py`
(`_collab_monitor_classify_worker_loop`, `services/collab_monitor/classify_worker.py`).

**`services/collab_monitor/classifier.py`** — 1 chamada LLM (`gpt-4o-mini`)
read-only: lê o histórico do lead (`services/ai_orchestrator/history.py::get_recent_history()`)
e retorna `{"suggested_category": str|null, "category_reason": str|null}`.
Enum restrito às categorias do Kanban aplicáveis a uma conversa já em
andamento: `qualification`, `apresentation`, `follow-up`, `closing`,
`client-list`, `prospect-refused`, `disqualified`. Postura conservadora
(mesma técnica de prompt já validada em `suggested_category` do
`decision_engine.py` — a LLM mãe do pipeline real): `null` sempre que não
houver sinal explícito na conversa; nunca decide categoria "por suposição".

**`services/collab_monitor/classify_worker.py::process_pending_collab_monitor_classify_jobs()`**
aplica dois guardrails antes de tocar em `leads.category`:
- `suggested_category is None` → não faz nada.
- Guardrail de não-retrocesso (`_is_valid_forward_move`): ordem do funil
  `monitoring(0) < qualification(1) < apresentation(2) < follow-up(3) <
  closing(4) < client-list(5)`; `prospect-refused`/`disqualified` são saídas,
  aplicáveis a partir de qualquer estágio não-terminal. Uma vez em
  `prospect-refused`/`disqualified`, o lead fica terminal — só reativação
  manual pelo Kanban (mesmo comportamento unidirecional de
  `services/lead_category_policy.py` para `closing`/`disqualified`/
  `prospect-refused` no pipeline real).

Quando aplica a mudança: `UPDATE leads.category` direto via
`sqlite3.Connection` (não pela rota `PATCH /api/leads/{id}` — aquela rota
bloqueia avanço `qualification → apresentation/follow-up/closing` via
`can_advance_from_qualification()`, checagem baseada em `qualification_state`
que só existe porque o bot real pergunta/extrai campos turno a turno; leads
monitorados não têm esse estado, pois quem conversa é um humano) + log de
auditoria em `prospection_logs` (`action='collab_monitor_category_changed'`,
`notes` com `old_category`/`new_category`/`category_reason`).

Continua **completamente isolado** do pipeline de IA real: nunca chama
`orchestrator`/`decision_engine`/guardrail de resposta, nunca envia mensagem.

---

## Tratamento de mídia (áudio/imagem/vídeo/figurinha/documento/reação)

`handle_monitor_inbound()` nunca descarta uma mensagem por falta de texto —
áudio e imagem passam por IA (transcrição/descrição); vídeo, figurinha,
documento e reação não (mesmo comportamento do pipeline real de bot — ver
`inbound_handler.py::_apply_media_fallback`), mas deixam um placeholder no
histórico em vez de sumir (`[Vídeo]`, `[Figurinha]`, `[Documento]`,
`[Reação]`).

```
mensagem sem texto
  ├─ áudio/imagem com media_url resolvido?
  │    → salva placeholder "(processando…)" + enfileira job
  │      collab_monitor.media.process
  │    → classify.local só é enfileirado DEPOIS do processamento
  │      (media_worker.py), nunca na hora — só existe texto real após
  │      transcrição/descrição
  └─ vídeo/figurinha/documento/reação, ou áudio/imagem sem media_url →
       salva placeholder fixo na hora; classify.local enfileirado
       imediatamente (se não for from_me), igual ao caminho de texto normal
```

**`services/collab_monitor/media_worker.py::process_pending_collab_monitor_media_jobs()`**
(mesmo padrão CAS/retry/loop-no-lifespan de `spy.media.process` e
`collab_monitor.classify.local`):
- **Áudio:** gate por `ai_profile.audio_transcription_enabled` (mesmo toggle
  de conta do pipeline real) — se desligado, salva placeholder explicando o
  motivo, sem chamar Whisper. Se ligado, resolve a URL pública via UazAPI
  (`fetch_core_whatsapp_token` + `services/audio_transcription.py::download_audio_url_from_uazapi()`
  — a URL crua do webhook costuma exigir autenticação da sessão) e transcreve
  com `transcribe_audio_from_url()` — mesmas funções já usadas pelo pipeline
  real de bot, zero duplicação. `messages.media_url` é atualizado com a URL
  resolvida (mais confiável para uso futuro, ex.: tocar o áudio numa tela
  dedicada), mas **pode expirar com o tempo** — ver
  [`monitoramento-colaborador-midia-url-expiracao.md`](../implementations/monitoramento-colaborador-midia-url-expiracao.md).
- **Imagem:** `services/image_description.py::describe_image_from_url()`
  (GPT-4o-mini visão) — extraído de `spy_agent/media_processor.py` (mesmo
  precedente de `audio_transcription.py`) para reuso entre Agente Espião e
  monitoramento de colaborador sem duplicar a chamada à API.
- Ambos os casos: `UPDATE messages SET body=..., media_url=...` e, se
  `from_me=False`, enfileira `collab_monitor.classify.local` — só agora
  existe texto real para o classificador ler.

`messages.media_url` (nullable, `ensure_column`) — nova coluna, guarda a URL
bruta/resolvida da mídia (além de `message_type`, já existente). Usado tanto
pela classificação de estágio (via `body`) quanto por uma futura tela de
mídia (via `media_url`).

Continua **completamente isolado** do pipeline de IA real: nenhum destes
caminhos chama orchestrator/decision_engine/guardrail de resposta.

---

## Tela de leitura estilo WhatsApp Web (frontend-crm)

`frontend-crm/src/pages/CollabMonitorInbox.tsx`, rota `/monitoramento`
(grupo autenticado com sidebar, item "Monitoramento" em Automação) — tela
dedicada para ler as conversas monitoradas, separada do Kanban:

- **Coluna esquerda:** lista de conversas via `GET /api/collab-monitor/conversations`
  (`api.crm.collabMonitorConversations`), com filtro por colaborador/instância
  (`Select`), ordenada pela mensagem mais recente. Cada item mostra avatar
  (iniciais), nome do contato, preview e contagem de mensagens, e o nome do
  colaborador que originou a conversa.
- **Coluna direita:** ao selecionar uma conversa, busca o histórico via
  `GET /api/assistente-ia/messages/{lead_id}?latest=false`
  (`api.assistenteIA.mensagens`, já existente e reaproveitado sem mudanças) e
  renderiza em bolhas de chat — `model='inbound'` (lead) à esquerda,
  `model='human_agent'` (colaborador) à direita.
- Renderiza só texto (`body`) — como o tratamento de mídia (acima) já
  converte áudio/imagem em texto (transcrição/descrição) antes de chegar
  aqui, a bolha de chat mostra esse conteúdo automaticamente, sem mudança
  nenhuma nesta tela. O que ainda falta é exibir a mídia **bruta** (tocar o
  áudio, ver a imagem em si) — ver "Fora do escopo", abaixo.
- **Nota de implementação:** as colunas peroláveis usam `overflow-y-auto`
  simples, não o componente `ScrollArea` (Radix/shadcn) — o wrapper interno
  do Radix usa `display: table`, que não respeita a largura do contêiner
  pai e deixa conteúdo vazar para fora da coluna.
- **Botão "Gerenciar colaboradores"** no header abre o
  `ManageCollaboratorsDialog` (cadastro/QR/reconectar/remover — ver "Kanban
  — coluna Monitorado" acima). Ao fechar o dialog após qualquer
  criação/reconexão/remoção, a query `["collab-monitor-conversations"]` é
  invalidada para a lista à esquerda refletir sem reload manual.
- `WhatsappDisconnectBanner.tsx` (banner global de "WhatsApp desconectado",
  renderizado pelo `AppShell` em toda página autenticada) é suprimido
  explicitamente nesta rota (`pathname.startsWith("/monitoramento")`) — ele
  é sobre a conexão do agente principal (`role="agent"`), sem relação com as
  instâncias de colaborador monitoradas.

---

## Fora do escopo desta base (planejado para depois)

- Exibir mídia bruta na tela de leitura (tocar áudio, ver imagem em si) —
  hoje só o texto (transcrição/descrição) aparece na bolha de chat. Ver
  "Tela de leitura estilo WhatsApp Web", acima.
- Paginação/scroll infinito na tela de leitura (lista de conversas e
  histórico de mensagens), caso o volume cresça. Ver
  [`monitoramento-colaborador-paginacao.md`](../implementations/monitoramento-colaborador-paginacao.md).
- Re-resolução de URL de mídia expirada (a URL persistida em `media_url` não
  é permanente) — ver
  [`monitoramento-colaborador-midia-url-expiracao.md`](../implementations/monitoramento-colaborador-midia-url-expiracao.md).
- Débito/custo da classificação de estágio (1 chamada LLM por mensagem
  inbound, sem debounce nem contabilização contra a franquia de "conversas
  IA" do plano) — ver nota em
  [`plans-subscriptions.md`](../plans/plans-subscriptions.md), seção "Fontes
  de custo de LLM ainda não medidas".
- Gate comercial de planos (`max_instances`, seed `crm_scale`/`crm_enterprise`)
  — já mapeado em [`scale-enterprise-roadmap.md`](../plans/scale-enterprise-roadmap.md),
  ortogonal a este trabalho técnico.
