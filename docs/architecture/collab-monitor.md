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
- Mensagens sem texto (mídia) ainda não têm tratamento dedicado — ver
  "Ajustes futuros" no final.

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
("Monitorado"), separada do pipeline normal do agente. Leads monitorados
aparecem aqui **sem classificação de estágio** — isso é trabalho futuro (IA
mãe lendo a conversa), não implementado nesta base.

`frontend-crm/src/components/agente/MonitoramentoColaboradores.tsx` — tela
de cadastro (aba "Monitoramento" em `AiProfile.tsx`): nome do colaborador,
QR/pareamento, lista de instâncias com status, reconectar/remover.

---

## Fora do escopo desta base (planejado para depois)

- IA mãe classificar automaticamente o estágio do lead monitorado e mover
  entre colunas do Kanban.
- Tela estilo WhatsApp Web (multi-telefone, filtro por colaborador/instância,
  navegação de mídia).
- Tratamento de mensagens de mídia (imagem/áudio) no monitoramento — hoje
  `handle_monitor_inbound` ignora mensagens sem texto.
- Gate comercial de planos (`max_instances`, seed `crm_scale`/`crm_enterprise`)
  — já mapeado em [`scale-enterprise-roadmap.md`](../plans/scale-enterprise-roadmap.md),
  ortogonal a este trabalho técnico.
