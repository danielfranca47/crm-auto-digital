# Botão global de Pausa do Bot (Kanban)

**Branch:** `feat/bot-pause-global`
**Status:** Em andamento

---

## Motivação

Hoje o único jeito de desligar o bot para um lead é individual (`bot_disabled`/`bot_disabled_reason`
por lead, via `POST /api/leads/{id}/bot-disabled`). O usuário quer um interruptor único no topo do
Kanban ("liga/desliga") que pausa a IA para todos os leads ativos de uma vez, e ao retomar, deixa
escolher entre reativar só quem foi pausado por esse botão, ou reativar geral.

Confirmado com o usuário: o botão é um **kill switch real** — enquanto pausado, nenhum lead deve
receber resposta automática, incluindo leads novos que chegarem durante a pausa.

Categorias onde o bot estruturalmente não atua (`client-list`, `prospect-refused`, `disqualified`)
nunca entram nesse fluxo: não são pausadas pelo botão nem reativadas no popup de retomada.

---

## Abordagem

```
Usuário clica "Pausar" no header do Kanban
  → POST /api/bot-pause/pause
    → UPDATE leads SET bot_disabled=1, reason='global_pause'
      WHERE user_id=? AND bot_disabled=0 AND category NOT IN (client-list, prospect-refused, disqualified)
    → bot_global_pause_state.is_paused=1

Enquanto pausado:
  → inbound_handler.py checa bot_global_pause_state ALÉM do bot_disabled do lead
    → lead novo (nunca pausado individualmente) também é bloqueado

Usuário clica "Retomar"
  → popup: reativar só os pausados pela pausa geral | reativar todos
  → POST /api/bot-pause/resume {mode}
    → UPDATE leads SET bot_disabled=0 conforme o modo escolhido
    → bot_global_pause_state.is_paused=0
```

---

## Plano de Implementação

### Fase 1 — Backend: schema + serviço + rotas

| Arquivo | O que muda |
|---|---|
| `backend-crm/database.py` | Nova tabela `bot_global_pause_state` (`user_id` PK, `is_paused`, `paused_at`, `updated_at`) |
| `backend-crm/services/lead_category_policy.py` | Nova constante `BOT_STRUCTURALLY_INACTIVE_CATEGORIES` |
| `backend-crm/services/bot_global_pause.py` (novo) | `get_status`, `pause_all`, `resume_all` |
| `backend-crm/models.py` | `BotResumeModePayload` (`mode: Literal["previously_paused", "all"]`) |
| `backend-crm/routes/bot_pause.py` (novo) | `GET /status`, `POST /pause`, `POST /resume` |
| `backend-crm/app.py` | `include_router(bot_pause.router)` |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `bff0909` | schema + serviço + rotas do backend (testado manualmente com script funcional, ver relato abaixo) |

### Fase 2 — Kill switch no pipeline de inbound

| Arquivo | O que muda |
|---|---|
| `backend-crm/services/whatsapp_inbound/inbound_handler.py` | Checagem adicional de `bot_global_pause_state.is_paused` no bloco de skip (~linha 480-499) |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `4bd1095` | checagem de pausa geral antes do bot_disabled por lead no inbound handler |

### Fase 3 — Frontend: botão + popup de retomada

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/services/api.ts` | `getBotPauseStatus`, `pauseAllBots`, `resumeAllBots` |
| `frontend-crm/src/contexts/LeadsContext.tsx` | Estado `botGlobalPaused`/`botGlobalPausedAt` + ações |
| `frontend-crm/src/components/CrmHeader.tsx` | Botão pause/play ao lado do toggle de tema |
| `frontend-crm/src/components/KanbanBoard.tsx` | Orquestra clique → pausa direta ou abre popup de retomada |
| `frontend-crm/src/components/BotPauseResumeDialog.tsx` (novo) | Popup com as 2 opções de retomada |
| `frontend-crm/src/components/LeadCardDialog.tsx` | Mapeia `bot_disabled_reason="global_pause"` para texto amigável |

### Commits Fase 3

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | (a registrar) | botão no header + popup de retomada + integração com o contexto |

**Nota:** `botGlobalPaused`/`onTogglePause` viraram props opcionais em `CrmHeader` — outras
páginas que reaproveitam o header (`ProspectionBoard.tsx`, `AssistenteIA.tsx`) não passam esses
props e simplesmente não exibem o botão de pausa, sem precisar de mudança nelas.

---

## Fora de escopo (confirmado com o usuário)

- Playground não é afetado (ambiente de teste isolado).
- Não recategoriza nem move leads de coluna — só liga/desliga `bot_disabled`.

---

## Checks de Validação

### Cenário 1 — Pausa geral respeita categorias excluídas
- [ ] Pausar com leads ativos em categorias variadas (incluindo `client-list`)
- [ ] Confirmar: `client-list`/`prospect-refused`/`disqualified` não são tocados

### Cenário 2 — Kill switch bloqueia lead novo durante a pausa
- [ ] Simular inbound de número novo enquanto pausado
- [ ] Confirmar: resposta `{"status": "skipped", "reason": "global_pause"}`, sem job de envio

### Cenário 3 — Retomada "só os pausados pela pausa geral"
- [ ] Ter 1 lead pausado manualmente antes + N pausados pela pausa geral
- [ ] Retomar com essa opção → só os N voltam, o manual continua pausado

### Cenário 4 — Retomada "reativar todos"
- [ ] Mesmo cenário do Cenário 3, retomar com "todos"
- [ ] Confirmar: o lead pausado manualmente também volta

### Cenário 5 — UI (ícone, toasts, popup)
- [ ] Ícone alterna Pause/Play corretamente
- [ ] Toasts mostram contagem de leads afetados
- [ ] Popup de retomada mostra as 2 opções com texto claro
