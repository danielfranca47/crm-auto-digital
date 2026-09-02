# Pausa Geral do Bot (Kanban)

Interruptor único no header do Kanban (`frontend-crm`) que pausa/retoma a IA para
todos os leads de um usuário de uma vez, sem precisar desativar lead a lead.
Complementa o [toggle de bot por lead](agents.md#toggle-de-bot-por-lead) — mesmo
mecanismo (`leads.bot_disabled`), mas com um estado global por usuário e um gate
adicional no pipeline de inbound.

---

## Estado por usuário

Tabela `bot_global_pause_state` (backend-crm, `database.py`):

| Campo | Tipo | Descrição |
|---|---|---|
| `user_id` | `INTEGER` PK | Um registro por usuário |
| `is_paused` | `INTEGER` (0/1) | Se `1`, o kill switch está ativo |
| `paused_at` | `DATETIME` | Quando a pausa foi ativada (preservado entre re-pausas consecutivas) |
| `updated_at` | `DATETIME` | Última alteração de estado |

Serviço: `backend-crm/services/bot_global_pause.py` — `get_status()`, `pause_all()`, `resume_all()`.

---

## Categorias estruturalmente inativas

Leads em `client-list`, `prospect-refused` ou `disqualified` nunca são tocados por
este mecanismo (nem pausados, nem reativados) — constante
`BOT_STRUCTURALLY_INACTIVE_CATEGORIES` em `services/lead_category_policy.py`. Essas
são as fases em que o bot já não atua (ver "Parada de follow-up" em
[`pipeline-phases.md`](pipeline-phases.md)).

---

## Pausar (`POST /api/bot-pause/pause`)

```sql
UPDATE leads SET bot_disabled = 1, bot_disabled_reason = 'global_pause'
 WHERE user_id = ? AND bot_disabled = 0
   AND category NOT IN (client-list, prospect-refused, disqualified)
```

Só afeta leads que estavam **ativos** no momento do clique — um lead já pausado
individualmente (qualquer motivo) não é tocado, e o motivo original não é
sobrescrito. Idempotente: pausar de novo enquanto já pausado não repete a marcação.

Cada lead afetado gera um log `bot_disabled_changed` em `prospection_logs`, igual
ao toggle individual.

---

## Retomar (`POST /api/bot-pause/resume`, body `{mode}`)

O botão de retomar abre um popup (`BotPauseResumeDialog.tsx`) com 2 opções:

| `mode` | Efeito |
|---|---|
| `previously_paused` | Reativa só os leads com `bot_disabled_reason = 'global_pause'` |
| `all` | Reativa todos os leads com `bot_disabled = 1` fora das categorias estruturalmente inativas — inclui leads pausados manualmente ou por regra de negócio (ex.: `category_closing`) |

Em ambos os modos, `bot_global_pause_state.is_paused` volta a `0` ao final.

---

## Kill switch no pipeline de inbound

`is_paused = 1` bloqueia **qualquer** resposta automática do bot para o usuário,
independente do `bot_disabled` do lead individual — inclusive leads novos criados
durante a pausa (que nunca tiveram `bot_disabled` setado).

Verificado em `backend-crm/services/whatsapp_inbound/inbound_handler.py`, antes do
gate de `bot_disabled` por lead: se `bot_global_pause_state.is_paused = 1` para o
`user_id`, retorna `{"status": "skipped", "reason": "global_pause"}` sem criar job,
mesmo que o lead tenha acabado de ser criado por `find_or_create_lead_by_phone`.

Follow-up ticks (`whatsapp.followup.tick`) não precisam de gate adicional: como
`pause_all()` já marca `bot_disabled=1` nos leads ativos no momento da pausa, o
mecanismo existente de `bot_disabled` (ver [`agents.md`](agents.md#toggle-de-bot-por-lead))
já impede o envio para esses leads.

O fallback de mídia (`_apply_media_fallback()`, ver "Comportamento de media_fallback"
em [`webhooks.md`](webhooks.md)) tem o mesmo gate: verifica `is_paused` e
`bot_disabled` antes de enviar a mensagem configurada em
`offer_pack.media_fallback_msg`, para que pausar o bot também impeça a resposta
automática quando o lead envia imagem/vídeo/áudio em vez de texto.

Playground não é afetado — ambiente de teste isolado, não passa pelo webhook real.

---

## Frontend

| Arquivo | Responsabilidade |
|---|---|
| `frontend-crm/src/contexts/LeadsContext.tsx` | Estado `botGlobalPaused`/`botGlobalPausedAt`; `pauseAllBots()`/`resumeAllBots(mode)`; carrega o status junto do polling de leads (30s) |
| `frontend-crm/src/components/CrmHeader.tsx` | Botão pause/play ao lado do toggle de tema. Props `botGlobalPaused`/`onTogglePause` são opcionais — outras páginas que reusam o header (`ProspectionBoard.tsx`, `AssistenteIA.tsx`) simplesmente não passam esses props e não exibem o botão |
| `frontend-crm/src/components/KanbanBoard.tsx` | Clique: se ativo, pausa direto (sem popup); se pausado, abre o popup de retomada |
| `frontend-crm/src/components/BotPauseResumeDialog.tsx` | Popup com as 2 opções de retomada |
| `frontend-crm/src/components/LeadCardDialog.tsx` | Mapeia `bot_disabled_reason="global_pause"` para "Pausado pelo botão geral" no card do lead |

---

## Arquivos críticos

| Arquivo | Responsabilidade |
|---|---|
| `backend-crm/database.py` | Schema de `bot_global_pause_state` |
| `backend-crm/services/bot_global_pause.py` | `get_status`, `pause_all`, `resume_all` |
| `backend-crm/services/lead_category_policy.py` | `BOT_STRUCTURALLY_INACTIVE_CATEGORIES` |
| `backend-crm/routes/bot_pause.py` | `GET /api/bot-pause/status`, `POST /pause`, `POST /resume` |
| `backend-crm/services/whatsapp_inbound/inbound_handler.py` | Gate do kill switch |
