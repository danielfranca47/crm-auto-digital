# Arquitetura de Follow-Up

## Visão geral

O follow-up automático tem 4 camadas:

```
[Frontend React]          Gatilho Kanban → Modal
       ↓
[Backend CRM]             POST /api/leads/start-followup → cria contrato
       ↓
[Reconciliador]           asyncio loop no lifespan do backend-crm (a cada ~60s)
       ↓
[backend-executors]       Worker polling → decision engine → LLM → WhatsApp
```

**Agent 2 (closer_agressivo) não participa do fluxo de follow-up** — é uma decisão de design.

---

## Fluxo completo

### 1. Gatilho no Kanban

**Arquivo:** `frontend-crm/src/components/KanbanBoard.tsx`

Quando o usuário arrasta um card de `apresentation → follow-up`:
1. Frontend chama `api.core.getAiProfileMe()` para resolver o `agent_type`
2. Mapeamento `template_key → agent_type`: `hybrid_scheduler` → `agent_3`; `closer*` → `agent_2`; demais → `agent_1`
3. Se `agent_1` ou `agent_3`: abre `FollowUpTransitionModal`
4. Se `agent_2`: move o card diretamente sem popup

---

### 2. Modal FollowUpTransitionModal

**Arquivo:** `frontend-crm/src/components/FollowUpTransitionModal.tsx`

Campos dinâmicos por tipo de agente:

#### Agent 1 — Reunião aconteceu (`yes`)
| Campo | Opções |
|---|---|
| "Como esse lead saiu da reunião?" | `hot`, `warm`, `cold`, `lost` |
| "Você enviou proposta?" | `yes`, `no` |
| "Objetivo do follow-up?" | `advance_closing`, `nurture`, `reschedule_conversation`, `register_only` |

#### Agent 1 — Reunião NÃO aconteceu
| Campo | Opções |
|---|---|
| "O que o bot deve fazer?" | `recover_and_reschedule`, `reengage`, `register_only` |

#### Agent 3 — Reunião aconteceu (`yes`)
| Campo | Condição |
|---|---|
| "Como terminou a sessão?" | `interested_not_closed`, `reschedule_needed`, `lost`, `converted` |
| "O que o bot deve fazer?" | `nurture_interest`, `prompt_reply`, `prepare_next_conversation` — só se `interested_not_closed` |
| "O bot deve remarcar?" | `yes`, `no` — só se `reschedule_needed` |

#### Agent 3 — Reunião NÃO aconteceu
| Campo | Opções |
|---|---|
| "O que o bot deve tentar?" | `recover_and_reschedule`, `reengage_conversation`, `register_only` |

---

### 3. POST /api/leads/start-followup

**Arquivo:** `backend-crm/routes/leads.py`

Validações:
- Lead existe e pertence ao usuário
- Lead está em `apresentation`
- `agent_type` bate com o do banco (`agent_1` ou `agent_3`)
- Qualificação está completa (via `qualification_guardrails.py`)

**followup_contract salvo em `leads.followup_contract`:**
```json
{
  "phase": "follow-up",
  "version": 1,
  "followup_variant": "sdr_scheduler",
  "status": "active",
  "attempts": 0,
  "max_attempts": 4,
  "next_followup_at": "<agora + offset>",
  "last_followup_at": null,
  "stop_reason": null,
  "meeting_or_session_happened": "yes",
  "outcome": "hot",
  "proposal_sent": true,
  "followup_goal": "advance_closing",
  "operator_note": "..."
}
```

**max_attempts:** `sdr_scheduler=4`, `hybrid_scheduler=3` (hardcoded)

**Offset do primeiro follow-up (hardcoded):**

| Variant | Condição | Offset |
|---|---|---|
| `sdr_scheduler` | qualquer | 30 min |
| `hybrid_scheduler` | reunião = `yes` | 120 min |
| `hybrid_scheduler` | `no_show`, `canceled`, `needs_reschedule` | 30 min |

**Atualização do lead:**
- `category = follow-up`
- `bot_disabled = 0` (reativado)
- `followup_status = active`
- `next_followup_at = agora + offset`

---

### 4. Reconciliador — asyncio loop

**Arquivo:** `backend-crm/services/followup_reconciler.py`
**Iniciado em:** `backend-crm/app.py` — `_reconciler_loop()` como asyncio task no lifespan

O loop executa `reconcile_due_followups()` periodicamente:
1. Busca leads com `followup_status='active'` e `next_followup_at <= agora`
2. Para cada lead vencido, verifica `followup_reconcile_guard` (idempotência por `(lead_id, due_at)`)
3. Cria job do tipo `whatsapp.followup.tick`
4. Registra guard para evitar duplicação

---

### 5. Execução pelo backend-executors

**Arquivos:**
- `backend-executors/app/workers/whatsapp_worker.py` — polling loop
- `backend-executors/app/runners/whatsapp.py` — executor do job

O worker faz polling em `GET /internal/jobs/next` a cada 0.5–30s (backoff progressivo).

Para job `whatsapp.followup.tick`:
1. Claim do job (lease 300s)
2. Busca contexto: `crm_client.get_whatsapp_execution_context(job_id)` → lead, history, ai_profile, playbook, qualification_state
3. `_inject_followup_contract_context()` — extrai sinais do `followup_contract` e injeta em `metadata.followup_context`
4. `decision_engine.decide(context)` → LLM com prompt específico de follow-up
5. Envia via `core_client.send_whatsapp_message()`
6. `complete_job()` → aciona `progress_followup_after_auto_send()`

**Intervalos entre tentativas subsequentes (hardcoded em `followup_state.py`):**

| Variant | Tentativa 1→2 | Tentativa 2→3 | Tentativa 3→4 |
|---|---|---|---|
| `sdr_scheduler` | +24h | +3 dias | +7 dias |
| `hybrid_scheduler` | +24h | +48h | — (max=3) |

---

### 6. Parada do follow-up

**Arquivo:** `backend-crm/services/followup_state.py`

| Razão | Gatilho | Status final |
|---|---|---|
| `STOP_INBOUND_REPLY` | Lead respondeu via WhatsApp | `paused` |
| `STOP_HANDOFF_HUMAN` | `bot_disabled = 1` | `paused` |
| `STOP_DEAL_CLOSED` | Lead movido para `client-list` | `closed` |
| `STOP_EXPLICIT_REJECTION` | Lead movido para `prospect-refused` / `disqualified` | `closed` |
| `STOP_MAX_ATTEMPTS_REACHED` | Tentativas atingiram `max_attempts` | `closed` |

---

## Arquivos críticos

| Arquivo | Responsabilidade |
|---|---|
| `frontend-crm/src/components/KanbanBoard.tsx` | Gatilho do popup na mudança de coluna |
| `frontend-crm/src/components/FollowUpTransitionModal.tsx` | Modal com campos dinâmicos |
| `backend-crm/routes/leads.py` | Endpoint `start_followup_transition` |
| `backend-crm/services/followup_state.py` | Máquina de estado (start, stop, progress, pausa) |
| `backend-crm/services/followup_reconciler.py` | Detecta vencimentos e cria jobs |
| `backend-crm/app.py` | `_reconciler_loop()` — loop asyncio no lifespan |
| `backend-crm/services/followup_channel_context.py` | Resolve instance_id/phone para o tick |
| `backend-crm/services/agent_type.py` | Mapeamento template_key → agent_type |
| `backend-crm/services/lead_category_policy.py` | Side-effects de categoria (inclui parar follow-up) |
| `backend-crm/services/whatsapp_inbound/inbound_handler.py` | Para follow-up quando lead responde |
| `backend-executors/app/workers/whatsapp_worker.py` | Worker polling |
| `backend-executors/app/runners/whatsapp.py` | Executa job: contexto → LLM → WhatsApp |
| `backend-executors/app/services/decision_engine.py` | Motor de decisão + prompt de follow-up |
