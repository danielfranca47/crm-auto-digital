# Monitoramento: exibir estágio da IA + alerta de conversa parada

**Branch:** `worktree-feat+monitoramento-estagio-conversa`
**Status:** Em andamento

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

### Fase 2 — Frontend: chip de estágio + alerta de conversa parada

**Objetivo:** o supervisor vê o estágio de cada conversa (lista e chat) e
identifica na hora quem está sem resposta do colaborador há mais de 3h.

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/services/api.ts` | `CollabMonitorConversation`: novos campos `category` e `last_message_from` |
| `frontend-crm/src/pages/CollabMonitorInbox.tsx` | `ConversationListItem`: chip de estágio (reaproveita label/cor de `KANBAN_COLUMNS`/`ARCHIVED_COLUMNS`) + chip de risco "Sem resposta há Xh"; cabeçalho do chat: banner de estágio da conversa selecionada |

---

## Checks de Validação

### Cenário P1 — Conversa não some após avançar de estágio
- [ ] Abrir uma conversa monitorada nova (`category='monitoring'`) na tela `/monitoramento`
- [ ] Forçar avanço de categoria (ex.: mover o card no Kanban ou aguardar a classificação automática)
- [ ] Confirmar: a conversa continua listada em `/monitoramento`, agora com o chip do novo estágio

### Cenário P2 — Chip de estágio bate com o Kanban
- [ ] Selecionar conversas em pelo menos 3 estágios diferentes
- [ ] Confirmar: label e cor do chip (lista e banner do chat) batem com a coluna correspondente no Kanban (`Index.tsx`)

### Cenário P3 — Alerta de conversa parada
- [ ] Abrir uma conversa cuja última mensagem seja do lead há mais de 3h
- [ ] Confirmar: chip "Sem resposta há Xh" aparece na lista e/ou no chat
- [ ] Responder como colaborador (mensagem `model='human_agent'`) e confirmar que o chip some

---

## Ajustes Possíveis Pós-Implementação

- Limiar de "conversa parada" (3h) está fixo no frontend, não configurável por conta/plano.
- Sem filtro por "só ativas" vs "todo o histórico" — a lista agora mostra qualquer estágio, ordenada por mensagem mais recente; se o volume crescer muito, pode valer um toggle no futuro.
