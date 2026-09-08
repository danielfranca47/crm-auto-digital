# Paginação na tela de monitoramento de colaborador

**Branch:** `feat/monitoramento-colaborador-paginacao`
**Status:** Em andamento

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`monitoramento-colaborador-tela-whatsapp-web.md` (tela de monitoramento
estilo WhatsApp Web — ver [`docs/architecture/collab-monitor.md`](../architecture/collab-monitor.md)).

A tela nova (`GET /api/collab-monitor/conversations` +
`GET /api/assistente-ia/messages/{lead_id}`) carrega hoje a lista completa de
conversas e o histórico completo de mensagens de uma vez, sem paginação nem
scroll infinito. Funciona bem com poucos leads/mensagens, mas não escala se
o volume de conversas monitoradas ou de mensagens por conversa crescer
muito.

**Decisões de produto confirmadas pelo utilizador:**
- Paginação **tradicional** (botões Anterior/Próxima) — não scroll infinito.
- O pedido adicional de filtro por categoria/grupo de colaboradores (grupo
  simples para plano Scale, hierarquia em árvore para Enterprise) fica **fora
  deste trabalho** — vai virar uma implementação própria depois, em
  branch/worktree separada, por mexer em modelo de dados novo e ser ortogonal
  a paginação.

---

## Problemas Identificados (estado anterior)

1. **Lista de conversas sem paginação:** `backend-crm/routes/collab_monitor.py::list_collab_monitor_conversations`
   (`GET /api/collab-monitor/conversations`, linhas 376-443) roda uma query só
   sem `LIMIT`/`OFFSET`, agregando todas as conversas `category='monitoring'`
   do usuário de uma vez.
2. **Histórico de mensagens sem paginação:** `backend-crm/routes/assistente_ia.py::get_messages`
   (`GET /api/assistente-ia/messages/{lead_id}`, linhas 134-159) busca todas
   as mensagens do lead numa query só (`ORDER BY createdAt DESC`), sem
   limite. Esta rota é **compartilhada** com outros consumidores além da tela
   de monitoramento: `LeadCardDialog.tsx:331,344` e
   `ProspectionCardDialog.tsx:219,419` (via `api.assistenteIA.mensagens()`,
   `frontend-crm/src/services/api.ts:941`) — qualquer mudança de contrato
   precisa preservar o comportamento desses outros consumidores.
3. **Frontend sem controle de página:** `frontend-crm/src/pages/CollabMonitorInbox.tsx`
   usa `useQuery` simples para as duas chamadas acima, sempre buscando tudo.

---

## Abordagem

```
Backend (2 rotas) → devolvem página (limit/offset) + has_more
  ├─ /collab-monitor/conversations  → única consumidora é CollabMonitorInbox
  │    → response vira {items, has_more}, muda livremente
  └─ /assistente-ia/messages/{id}   → compartilhada com LeadCardDialog e
       ProspectionCardDialog
       → só pagina quando o chamador manda `limit` explicitamente;
         sem `limit` (ou latest=true) → comportamento idêntico ao atual

Frontend (CollabMonitorInbox.tsx) → 2 pagers independentes
  ├─ lista de conversas   → conversationPage (reset ao trocar filtro de colaborador)
  └─ histórico de mensagens → messagePage (reset ao trocar de conversa selecionada)
```

Sem `COUNT(*)` total: cada query busca `limit + 1` linhas, corta para
`limit`, e `has_more = len(rows) > limit` decide se o botão "Próxima" fica
habilitado. Evita uma segunda query de contagem em cima da agregação de
mensagens. Efeito prático: mostra "Página N" com Anterior/Próxima
habilitados/desabilitados, sem "Página 3 de 7".

Precedente de padrão de query params reaproveitado:
`backend-crm/routes/prospeccao.py::get_history` (linha 378-419) já usa
`limit: int = Query(50, ge=1, le=200)` / `offset: int = Query(0, ge=0)` +
`LIMIT ? OFFSET ?` manual.

Componente de UI reaproveitado: `frontend-crm/src/components/ui/pagination.tsx`
(shadcn, ainda não usado em nenhuma tela) — `Pagination`/`PaginationPrevious`/`PaginationNext`
com `onClick` (não `href`, já que não há roteamento por URL aqui).

**Trade-off consciente:** a query de conversas continua agregando *todas* as
mensagens de todos os leads monitorados antes do `LIMIT` final (o
`GROUP BY`/`ROW_NUMBER()` roda sobre a tabela inteira) — o `LIMIT`/`OFFSET`
reduz o tamanho da resposta e do DOM renderizado, não o custo de CPU/IO da
query em si. Otimizar a query para limitar quais leads entram na agregação
antes de juntar fica fora do escopo desta iteração — ver "Ajustes Possíveis
Pós-Implementação".

---

## Plano de Implementação

### Fase 1 — Backend: paginar os dois endpoints

**Objetivo:** os dois endpoints aceitam `limit`/`offset` e devolvem `has_more`, sem quebrar nenhum consumidor existente.

**Status:** Implementado.

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `edc1a7c` | `GET /collab-monitor/conversations` e `GET /assistente-ia/messages/{lead_id}` paginados (opt-in na segunda), cliente `api.ts` atualizado |

| Arquivo | O que muda |
|---|---|
| `backend-crm/routes/collab_monitor.py` | `list_collab_monitor_conversations`: adiciona `limit: int = Query(20, ge=1, le=100)`, `offset: int = Query(0, ge=0)`; busca `limit+1` linhas, corta para `limit`, calcula `has_more`. Novo response model `CollabMonitorConversationsPage {items, has_more}` no lugar do `List[...]` direto. |
| `backend-crm/routes/assistente_ia.py` | `get_messages`: adiciona `limit: Optional[int] = Query(None, ge=1, le=200)`, `offset: int = Query(0, ge=0)`. Se `limit` for `None` ou `latest=True` → comportamento idêntico ao atual. Se `limit` vier e `latest=False` → `LIMIT ?+1 OFFSET ?`, corta para `limit`, inclui `has_more` na resposta. |
| `frontend-crm/src/services/api.ts` | `collabMonitorConversations(instanceId?, {limit, offset}?)` → retorno vira `{items, has_more}`. `mensagens(leadId, latest?, {limit, offset}?)` → só acrescenta `limit`/`offset` na URL quando informados; retorno ganha `has_more?` opcional. |

```python
# ANTES (collab_monitor.py)
@router.get("/conversations", response_model=List[CollabMonitorConversationOut])
async def list_collab_monitor_conversations(
    instance_id: Optional[str] = None,
    current_user: CurrentUser = Depends(require_crm_access),
) -> List[CollabMonitorConversationOut]:
    ...
    query += " ORDER BY datetime(last_msg.createdAt) DESC"
    rows = conn.execute(query, tuple(params)).fetchall()
    ...
    return [CollabMonitorConversationOut(...) for row in rows]

# DEPOIS
@router.get("/conversations", response_model=CollabMonitorConversationsPage)
async def list_collab_monitor_conversations(
    instance_id: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: CurrentUser = Depends(require_crm_access),
) -> CollabMonitorConversationsPage:
    ...
    query += " ORDER BY datetime(last_msg.createdAt) DESC LIMIT ? OFFSET ?"
    params.extend([limit + 1, offset])
    rows = conn.execute(query, tuple(params)).fetchall()
    has_more = len(rows) > limit
    rows = rows[:limit]
    ...
    return CollabMonitorConversationsPage(
        items=[CollabMonitorConversationOut(...) for row in rows],
        has_more=has_more,
    )
```

### Fase 2 — Frontend: UI de paginação em `CollabMonitorInbox.tsx`

**Objetivo:** dois pagers independentes (conversas e mensagens), sem afetar `LeadCardDialog`/`ProspectionCardDialog`.

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/pages/CollabMonitorInbox.tsx` | `conversationPage` (reset ao trocar `instanceFilter`, tamanho 20) e `messagePage` (reset ao trocar `selectedLeadId`, tamanho 30). `useQuery` keys incluem a página. Barra de paginação no rodapé da coluna esquerda e no topo do painel de mensagens — "Anterior" desabilitado em `page === 0`, "Próxima" desabilitado em `!has_more`. |

**Ajuste feito durante a implementação (não previsto no plano):** a lista de
colaboradores do filtro (`Select` no topo da coluna esquerda) antes era
derivada das próprias conversas carregadas (`conversations` completo, sem
paginação). Com paginação, isso passaria a mostrar só os colaboradores da
página atual — regressão. Corrigido usando `GET /collab-monitor/instances`
(`api.crm.collabMonitorList()`, já existente, usado pelo `ManageCollaboratorsDialog`)
como fonte da lista de colaboradores do filtro, independente da paginação
das conversas.

**Ajuste de componente:** em vez do `Pagination`/`PaginationLink` do shadcn
(baseado em `<a>`, pensado para navegação com `href`), foi criado um
componente `Pager` local com `Button` (`onClick`), mais adequado a paginação
sem roteamento por URL e com foco/teclado corretos por padrão.

**Status:** Implementado.

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 2 | `1e42ab9` | UI de paginação tradicional (conversas + mensagens) em `CollabMonitorInbox.tsx` |

### Relatório da Fase 1 — o que mudou na prática

**Antes:** os dois endpoints por trás da tela de monitoramento (lista de
conversas e histórico de mensagens de uma conversa) sempre devolviam tudo de
uma vez — sem limite.
**Agora:** os dois aceitam parâmetros de página; quando pedidos, devolvem só
um pedaço dos dados por vez, mais um sinalizador dizendo se há mais itens
depois. A rota de mensagens continua devolvendo tudo de uma vez para quem não
pedir paginação (Kanban, prospecção) — nada mudou para essas telas.
**Para validar:** Cenário C3, abaixo (regressão nas outras telas que usam a
mesma rota de mensagens).

### Relatório da Fase 2 — o que mudou na prática

**Antes:** a tela de Monitoramento (`/monitoramento`) carregava de uma vez
todas as conversas monitoradas e, ao abrir uma conversa, todo o histórico de
mensagens — sem nenhum controle de página.
**Agora:** tanto a lista de conversas (à esquerda) quanto o histórico de
mensagens de uma conversa (à direita) mostram um pedaço por vez (20
conversas, 30 mensagens), com botões "Anterior"/"Próxima" no rodapé/topo de
cada lista. Trocar de colaborador no filtro ou de conversa selecionada volta
automaticamente para a primeira página. O filtro de colaborador continua
mostrando todos os colaboradores cadastrados, não só os que aparecem na
página atual de conversas.
**Para validar:** Cenários C1, C2 e C3, abaixo.

---

## Checks de Validação

### Cenário C1 — Paginação da lista de conversas
- [ ] Abrir `/monitoramento` no browser
- [ ] Se a conta de teste tiver poucas conversas monitoradas (≤20), chamar a API diretamente com `?limit=2` para forçar `has_more=true` e validar a lógica sem depender de volume real de dados
- [ ] Confirmar: botão "Próxima" avança a lista, "Anterior" volta, sem duplicar nem pular conversas

### Cenário C2 — Paginação do histórico de mensagens
- [ ] Selecionar uma conversa com várias mensagens (ou forçar `limit` baixo via chamada direta à API)
- [ ] Confirmar: "Próxima" carrega mensagens mais antigas, "Anterior" volta às mais recentes, sem duplicar nem pular mensagens
- [ ] Trocar de conversa selecionada e confirmar que a página de mensagens reseta para a primeira

### Cenário C3 — Regressão: consumidores compartilhados de `get_messages`
- [ ] Abrir um `LeadCardDialog` (Kanban) e confirmar que o preview e o histórico completo de mensagens continuam aparecendo normalmente, sem paginação visível
- [ ] Abrir um `ProspectionCardDialog` e confirmar o mesmo

---

## Ajustes Possíveis Pós-Implementação

- Otimizar a query de `/collab-monitor/conversations` para não agregar
  mensagens de leads fora da página atual (hoje o `GROUP BY`/`ROW_NUMBER()`
  roda sobre toda a tabela `messages` antes do `LIMIT` final) — só vale a
  pena se o volume de mensagens crescer o suficiente para pesar no tempo de
  resposta.
- Mostrar contagem total ("Página N de M") exigiria uma query `COUNT(*)`
  adicional — deixado de fora por simplicidade nesta iteração.
- Filtro por categoria/grupo de colaboradores (grupo simples para Scale,
  hierarquia em árvore para Enterprise) — implementação separada, decidida
  pelo utilizador para ficar fora deste trabalho.
