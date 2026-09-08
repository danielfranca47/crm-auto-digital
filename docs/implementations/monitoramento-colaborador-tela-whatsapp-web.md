# Tela estilo WhatsApp Web para monitoramento de colaborador

**Branch:** `feat/monitoramento-colaborador-tela-whatsapp-web-2`
**Status:** Todos os cenários validados (08/09/2026) — pendente: graduação

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`monitoramento-colaborador-whatsapp.md` (base do monitoramento de WhatsApp de
colaborador — ver [`docs/architecture/collab-monitor.md`](../architecture/collab-monitor.md)).

Hoje a única forma de ver as conversas monitoradas é abrindo cada lead
individualmente no Kanban (coluna "Monitorado"). O utilizador quer uma tela
nova, dedicada, que simule a experiência do WhatsApp Web: navegar pelos
telefones/colaboradores, entrar em cada conversa, ler mensagens — com filtro
por colaborador, por instância, ou exibindo todas de uma vez.

---

## Diagnóstico (Plan Mode)

### Já existe?

Não. Confirmado por leitura de código:

- `frontend-crm/src/components/agente/MonitoramentoColaboradores.tsx` só
  cadastra/conecta instâncias (renderizado dentro de `AiProfile.tsx`, aba
  "Monitoramento") — não lista leads nem mensagens.
- `GET /api/leads` (`backend-crm/routes/leads.py:359`, `listar_leads`) retorna
  todos os leads do `user_id` sem filtro de `category` nem paginação —
  filtragem hoje é 100% client-side.
- `backend-crm/routes/collab_monitor.py` só tem CRUD de instâncias
  (`POST/GET /instances`, `DELETE /instances/{id}`,
  `POST /instances/{id}/reconnect`). Não existe endpoint que agregue
  "colaborador → leads → mensagens".
- **Reaproveitável sem mudanças:**
  `GET /api/assistente-ia/messages/{lead_id}?latest=false`
  (`backend-crm/routes/assistente_ia.py:134`) já retorna o histórico completo
  de mensagens de um lead (`SELECT id, channel, subject, body, model,
  createdAt FROM messages WHERE lead_id = ?`), já valida ownership via
  `_require_lead_for_user`. Esta rota é a fonte de mensagens da nova tela —
  não recriar.

### O que precisa ser construído

**backend-crm:**
- Novo endpoint `GET /api/collab-monitor/conversations` em
  `routes/collab_monitor.py` — agrega leads `category='monitoring'` do
  `user_id`, opcionalmente filtrado por `?instance_id=`, com preview da
  última mensagem e nome do colaborador (JOIN com `collab_monitor_instances`).

**frontend-crm:**
- Página nova `src/pages/CollabMonitorInbox.tsx` — lista de conversas
  (esquerda) + painel de mensagens com bolhas (direita).
- Novo método `api.crm.collabMonitorConversations()` em `src/services/api.ts`.
- Rota nova em `App.tsx` + item de navegação em `AppSidebar.tsx`.

Sem impacto em banco de dados nesta iteração (sem migração de schema).

### Riscos e dependências

**Mídia (imagem/áudio) fica fora de escopo desta implementação.**
`handle_monitor_inbound`
(`backend-crm/services/collab_monitor/monitor_inbound_handler.py:137-140`)
descarta qualquer mensagem sem `message_text` (`{"status": "ignored",
"reason": "missing_text"}`) — toda mídia recebida por instância de
monitoramento hoje nem chega a ser gravada. Além disso, `routes/webhooks.py`
não extrai `media_url` no bloco que monta o payload do monitor (diferente do
bloco vizinho do Agente Espião, que já faz isso). Resolver isso implicaria:
nova coluna em `messages` (tabela de alto tráfego, compartilhada com o
pipeline real de IA), mudança em área sensível do webhook, e um pipeline de
download/persistência que hoje só existe, isolado, em `spy_agent_messages` +
`spy_media_worker.py` (Agente Espião). É esforço substancial com decisões de
produto em aberto (custo/retenção de mídia baixada) — decisão: fica registrado
em "Ajustes Possíveis Pós-Implementação", não implementado agora. A tela
entrega texto, que já cobre a demanda central (navegar/filtrar conversas por
colaborador).

Nenhum outro risco relevante — a mudança é aditiva (rota nova + página nova),
sem tocar em pipeline de IA, guardrails ou fluxo de envio.

### Proposta de fases

Fase 1 — Endpoint de agregação — expor via API os leads de monitoramento
agrupados/filtráveis por colaborador ou instância.
Fase 2 — Tela dedicada (texto) — navegação estilo WhatsApp Web ponta a ponta,
usando dados já existentes.

---

## Problemas Identificados (estado anterior)

1. **Sem navegação dedicada:** a única forma de ler uma conversa monitorada é
   abrir o lead individualmente no Kanban (coluna "Monitorado") — não há
   visão agregada por colaborador/instância.
2. **Sem endpoint de agregação:** `GET /api/leads` não filtra por `category`
   nem junta dados de `collab_monitor_instances` — qualquer agregação hoje
   teria que acontecer no cliente.

---

## Abordagem

```
Frontend: CollabMonitorInbox.tsx
  → GET /api/collab-monitor/conversations[?instance_id=]
      → lista leads (category='monitoring') + colaborador + preview
  → usuário seleciona uma conversa
      → GET /api/assistente-ia/messages/{lead_id}?latest=false (já existe)
          → bolhas de mensagem: model='inbound' (lead) | model='human_agent' (colaborador)
```

---

## Plano de Implementação

### Fase 1 — Endpoint de agregação (backend-crm)

**Objetivo:** expor via API os leads de monitoramento agrupados/filtráveis
por colaborador ou instância, com preview da última mensagem.

| Arquivo | O que muda |
|---|---|
| `backend-crm/routes/collab_monitor.py` | Novo `GET /conversations` (montado como `/api/collab-monitor/conversations`) |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `5636f57` | backend: `GET /api/collab-monitor/conversations` |

**Detalhes do commit:**
- `backend-crm/routes/collab_monitor.py` — novo modelo `CollabMonitorConversationOut`
  e rota `GET /conversations`: agrega `leads` (`category='monitoring'`) com
  `collab_monitor_instances` (nome do colaborador) e uma subquery com
  `ROW_NUMBER()` para trazer a última mensagem (`body`/`createdAt`) e a
  contagem total por lead, seguindo o mesmo padrão de agregação já usado em
  `listar_leads` (`routes/leads.py`). Aceita `?instance_id=` opcional.

### Relatório da Fase 1 — o que mudou na prática

**Antes:** não existia nenhuma forma de listar, via API, as conversas de
monitoramento agrupadas por colaborador — só dava para abrir lead por lead no
Kanban.
**Agora:** existe um endpoint (`GET /api/collab-monitor/conversations`) que
retorna todas as conversas monitoradas da conta, com nome do colaborador,
quantidade de mensagens e um preview da última mensagem — já ordenado da
conversa mais recente para a mais antiga. Aceita filtrar por uma instância
específica (`?instance_id=`).
**Para validar:** Cenário P1, abaixo — já testado nesta sessão com dados
sintéticos (ver validação abaixo); ainda pendente testar com uma conta real
que tenha colaboradores monitorados de verdade.

### Fase 2 — Tela dedicada (frontend-crm, texto apenas)

**Objetivo:** navegação estilo WhatsApp Web ponta a ponta — lista de
conversas + painel de mensagens com bolhas — usando dados já existentes.

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/services/api.ts` | Novo tipo `CollabMonitorConversation` + `api.crm.collabMonitorConversations(instanceId?)` |
| `frontend-crm/src/pages/CollabMonitorInbox.tsx` | Página nova — lista de conversas (esquerda) + painel com bolhas de mensagem (direita) |
| `frontend-crm/src/App.tsx` | Nova rota `/monitoramento` (grupo autenticado com sidebar) |
| `frontend-crm/src/components/AppSidebar.tsx` | Novo item "Monitoramento" no grupo "Automação" |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `45c44e5` | frontend: tela de monitoramento estilo WhatsApp Web |

**Detalhes do commit:**
- `frontend-crm/src/pages/CollabMonitorInbox.tsx` — página nova: coluna
  esquerda com filtro por colaborador (`Select`) e lista de conversas
  (avatar com iniciais, nome, preview da última mensagem, contagem, badge
  "via `<colaborador>`"); coluna direita com bolhas de mensagem
  (`model='inbound'` à esquerda, `model='human_agent'` à direita),
  reaproveitando `api.assistenteIA.mensagens(leadId, false)` já existente.
- `frontend-crm/src/services/api.ts` — tipo `CollabMonitorConversation` e
  método `collabMonitorConversations`.
- `frontend-crm/src/App.tsx` / `AppSidebar.tsx` — rota `/monitoramento` e
  item de navegação.

**Nota técnica (achado durante o teste ao vivo):** a lista de conversas
inicialmente usava o componente `ScrollArea` (Radix/shadcn). O wrapper
interno do Radix usa `display: table`, que não respeita a largura do
contêiner pai — o item da lista crescia além dos 320px da coluna e vazava
sob o painel da direita, cortando o timestamp visualmente (sem ellipsis,
parecia um bug de truncamento mas era sobreposição de camadas). Troquei por
`overflow-y-auto` simples nas duas colunas peroláveis (lista de conversas e
histórico de mensagens) — resolve e evita a mesma armadilha no futuro.

### Relatório da Fase 2 — o que mudou na prática

**Antes:** para ler uma conversa monitorada era preciso abrir o lead
individualmente no Kanban, coluna "Monitorado", um de cada vez.
**Agora:** existe uma tela dedicada ("Monitoramento", no menu lateral, grupo
Automação) que lista todas as conversas monitoradas com nome do colaborador,
prévia da última mensagem e contagem — filtrável por colaborador — e ao
clicar numa conversa mostra o histórico completo em formato de chat (bolhas
à esquerda para o cliente, à direita para o colaborador).
**Para validar:** Cenário P2, abaixo — já testado nesta sessão via browser
(Chrome DevTools MCP) com dados sintéticos: lista, seleção de conversa,
histórico em ordem cronológica correta e filtro por colaborador, todos
funcionando.

---

## Checks de Validação

### Cenário P1 — Endpoint retorna conversas corretas
- [x] Chamar `GET /api/collab-monitor/conversations` autenticado
- [x] Confirmar: retorna só leads `category='monitoring'` do usuário, com nome
  do colaborador e preview da última mensagem
- [x] Chamar com `?instance_id=` e confirmar filtro aplicado
- **Validado em:** 08/09/2026 — testado localmente (backend-core :8001 +
  backend-crm :8000) com 2 instâncias/colaboradores e 2 leads sintéticos
  (inseridos e removidos só na cópia local de `crm.db` desta worktree, não
  afeta a conta de teste real). Confirmado: ordenação por última mensagem
  (`last_message_at` desc), `msg_count` correto (2 e 1), `last_message_preview`
  trazendo a mensagem mais recente (não a mais antiga), `collaborator_name`
  correto via JOIN, e filtro `?instance_id=` isolando só a conversa certa.

### Cenário P2 — Tela lista e exibe conversas
- [x] Abrir a tela nova
- [x] Confirmar: lista de conversas aparece, agrupável/filtrável por
  colaborador ou instância
- [x] Selecionar uma conversa → confirmar histórico de texto real aparece,
  com bolhas diferenciando lead x colaborador
- **Validado em:** 08/09/2026 — testado ao vivo via Chrome DevTools MCP
  (frontend-crm local na porta 8081, backend-crm :8000, backend-core :8001)
  com 2 instâncias/colaboradores e 2 leads sintéticos (inseridos e removidos
  só na cópia local de `crm.db` desta worktree). Confirmado: lista ordenada
  pela última mensagem, avatar com iniciais, preview e contagem corretos,
  seleção de conversa carrega histórico em ordem cronológica (mais antiga no
  topo), bolhas do lead à esquerda e do colaborador à direita, filtro por
  colaborador (`Select`) restringe a lista corretamente e limpa a seleção
  quando a conversa selecionada sai do filtro.

---

## Ajustes Possíveis Pós-Implementação

- Captura e exibição de mídia (imagem/áudio) nas conversas monitoradas —
  depende de decisão de produto sobre custo/retenção de mídia baixada e de
  replicar o pipeline do Agente Espião (`spy_agent/media_processor.py` +
  `spy_media_worker.py`) para o monitoramento.
- Paginação/scroll infinito na lista de conversas e no histórico, caso o
  volume cresça.
