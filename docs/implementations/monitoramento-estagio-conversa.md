# Monitoramento: exibir estágio da IA + alerta de conversa parada

**Branch:** `worktree-feat+monitoramento-estagio-conversa`
**Status:** Todos os cenários validados (12/09/2026)

---

## Motivação

Ao montar um mock/demo da tela `/monitoramento` para mostrar a clientes, surgiu
a pergunta se a tela real já mostra o estágio que a IA classifica para cada
conversa monitorada, e se há algum alerta de conversa parada. Não mostra.

A investigação revelou algo mais importante que uma simples falta de UI:
**hoje, assim que a IA classifica uma conversa monitorada para além de
`monitoring`, ela desaparece por completo da tela de Monitoramento** — o
supervisor só volta a achar essa conversa procurando o card no Kanban. Esta
implementação resolve as duas coisas juntas: mostra o estágio (resolvendo o
"sumiço") e sinaliza quando uma conversa está sem resposta do colaborador.

---

## Problemas Identificados (estado anterior)

1. **Conversa desaparece da tela após avançar de estágio:**
   `backend-crm/routes/collab_monitor.py:427-428` — `GET /api/collab-monitor/conversations`
   filtra rigidamente `l.category = 'monitoring'`. Assim que
   `services/collab_monitor/classify_worker.py` avança a categoria do lead
   (ex.: para `qualification` ou `closing`), a linha some do resultado desta
   rota, mesmo que a conversa continua ativa e monitorada — só aparece de
   novo procurando o card no Kanban.

2. **Nenhum indicador de estágio na UI:** `frontend-crm/src/pages/CollabMonitorInbox.tsx`
   e o tipo `CollabMonitorConversation` (`frontend-crm/src/services/api.ts:455-464`)
   não carregam `category`. Não há chip nem banner de estágio na lista nem no
   chat.

3. **Nenhum alerta de conversa parada:** a última mensagem não expõe de quem
   foi (`lead` ou `colaborador`), então não dá para saber, direto na tela, se
   uma conversa está esperando resposta humana há muito tempo.

---

## Abordagem

```
GET /api/collab-monitor/conversations
  → ANTES: WHERE l.category = 'monitoring'  (conversa some ao avançar)
  → AGORA: WHERE l.collab_monitor_instance_id IS NOT NULL  (mostra em qualquer estágio)
  → SELECT adicional: l.category, last_msg.model (direção da última mensagem)

Frontend (CollabMonitorInbox.tsx)
  ├─ lista: chip de estágio (label/cor reaproveitados de KANBAN_COLUMNS/ARCHIVED_COLUMNS)
  │         + chip "Sem resposta há Xh" quando last_message_from='inbound' e >3h
  └─ chat:  banner de estágio no topo, mesmo mapeamento de label/cor
```

---

## Plano de Implementação

### Fase 1 — Backend: expor `category` e direção da última mensagem

**Objetivo:** a conversa nunca mais some da tela ao avançar de estágio, e a
API passa a informar em que estágio está e quem mandou a última mensagem.

| Arquivo | O que muda |
|---|---|
| `backend-crm/routes/collab_monitor.py` | `list_collab_monitor_conversations`: troca o filtro `category='monitoring'` por `collab_monitor_instance_id IS NOT NULL`; adiciona `l.category` e `last_msg.model` ao SELECT; novos campos `category`/`last_message_from` em `CollabMonitorConversationOut` |

```python
# ANTES
WHERE l.user_id = ?
  AND l.category = 'monitoring'

# DEPOIS
WHERE l.user_id = ?
  AND l.collab_monitor_instance_id IS NOT NULL
```

```python
# last_msg agora também traz a coluna model (direção da mensagem)
SELECT lead_id, body, createdAt, model
FROM (
    SELECT lead_id, body, createdAt, model,
           ROW_NUMBER() OVER (...) AS rn
    FROM messages
)
WHERE rn = 1
```

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `e748ba4` | backend: filtro ampliado + `category`/`last_message_from` expostos |

**Detalhes do commit `e748ba4`:**
- `backend-crm/routes/collab_monitor.py` — `list_collab_monitor_conversations`: troca `WHERE l.category = 'monitoring'` por `WHERE l.collab_monitor_instance_id IS NOT NULL`; adiciona `l.category` e `last_msg.model` (aliado como `last_message_from`) ao SELECT e ao `CollabMonitorConversationOut`

### Relatório da Fase 1 — o que mudou na prática

**Antes:** assim que a IA classificava uma conversa monitorada para além do
estágio inicial, ela sumia da tela de Monitoramento — só reaparecia
procurando o card no Kanban.
**Agora:** a API que alimenta essa tela devolve a conversa em qualquer
estágio, junto com o estágio atual e a informação de quem mandou a última
mensagem (lead ou colaborador). Ainda não há nada visível na tela — isso é a
Fase 2.
**Para validar:** os Cenários P1, P2 e P3 (seção "Checks de Validação")
dependem também da Fase 2 (frontend), que ainda não foi implementada — não há
teste isolado só de backend nesta fase.

### Fase 2 — Frontend: chip de estágio + alerta de conversa parada

**Objetivo:** o supervisor vê o estágio de cada conversa (lista e chat) e
identifica na hora quem está sem resposta do colaborador há mais de 3h.

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/services/api.ts` | `CollabMonitorConversation`: novos campos `category` e `last_message_from` |
| `frontend-crm/src/pages/CollabMonitorInbox.tsx` | `ConversationListItem`: chip de estágio (reaproveita label/cor de `KANBAN_COLUMNS`/`ARCHIVED_COLUMNS`) + chip de risco "Sem resposta há Xh"; cabeçalho do chat: banner de estágio da conversa selecionada |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `dfb5159` | frontend: chips de estágio/risco na lista + banner de estágio no chat |

**Detalhes:**
- `frontend-crm/src/services/api.ts` — `CollabMonitorConversation` ganha `category` e `last_message_from`
- `frontend-crm/src/pages/CollabMonitorInbox.tsx` — novo `STAGE_LOOKUP` (reaproveita `KANBAN_COLUMNS`/`ARCHIVED_COLUMNS` de `src/data/mockData.ts`), `isAwaitingResponse()`/`hoursSince()` (limiar de 3h), componentes `StageChip`/`StaleChip` na lista, banner de estágio no cabeçalho do chat

### Relatório da Fase 2 — o que mudou na prática

**Antes:** a tela de Monitoramento não mostrava em que fase da venda cada
conversa estava, nem se um lead estava esperando resposta do colaborador.
**Agora:** cada conversa na lista mostra um selo com o estágio atual (mesma
cor/nome usada no Kanban) e, quando o lead mandou a última mensagem há mais
de 3h sem resposta do colaborador, um selo vermelho "Sem resposta há Xh". A
mesma informação aparece de forma mais visível no topo do chat ao abrir a
conversa.
**Para validar:** Cenários P1, P2 e P3 (seção "Checks de Validação").

---

## Checks de Validação

### Cenário P1 — Conversa não some após avançar de estágio
- [x] Abrir uma conversa monitorada nova (`category='monitoring'`) na tela `/monitoramento`
- [x] Forçar avanço de categoria (seed direto no banco de teste da worktree: leads em `qualification` e `closing`, via `collab_monitor_instances`/`leads`/`messages`)
- [x] Confirmar: a conversa continua listada em `/monitoramento`, agora com o chip do novo estágio
- **Validado em:** 12/09/2026 — `GET /api/collab-monitor/conversations` retornou os 3 leads de teste (`monitoring`, `qualification`, `closing`) na mesma resposta, todos com `category` preenchido; antes da mudança, os dois últimos teriam sido excluídos pelo filtro antigo

### Cenário P2 — Chip de estágio bate com o Kanban
- [x] Selecionar conversas em pelo menos 3 estágios diferentes
- [x] Confirmar: label e cor do chip (lista e banner do chat) batem com a coluna correspondente no Kanban (`Index.tsx`, via `KANBAN_COLUMNS`)
- **Validado em:** 12/09/2026 — "Monitorado" (cinza), "Qualificação" (azul), "Fechamento" (laranja) renderizados corretamente na lista e no banner do chat, cores idênticas às de `KANBAN_COLUMNS`

### Cenário P3 — Alerta de conversa parada
- [x] Abrir uma conversa cuja última mensagem seja do lead há mais de 3h
- [x] Confirmar: chip "Sem resposta há Xh" aparece na lista e/ou no chat
- [x] Responder como colaborador (mensagem `model='human_agent'`) e confirmar que o chip some
- **Validado em:** 12/09/2026 — lead com última mensagem do lead há ~5h mostrou "⚠ Sem resposta há 5h" na lista e no banner do chat; após inserir mensagem `human_agent` mais recente e recarregar, o chip desapareceu e a conversa reordenou para o topo (mais recente)

---

## Ajustes Possíveis Pós-Implementação

- Limiar de "conversa parada" (3h) está fixo no frontend, não configurável por conta/plano.
- Sem filtro por "só ativas" vs "todo o histórico" — a lista agora mostra qualquer estágio, ordenada por mensagem mais recente; se o volume crescer muito, pode valer um toggle no futuro.
