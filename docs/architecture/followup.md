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

**Agent 2 (closer_agressivo)** não usa o fluxo assistido (modal de transição), mas tem **cart recovery automático** — iniciado pelo próprio bot ao enviar link de pagamento. Ver secção "Cart Recovery".

---

## Fluxo completo

### 1. Gatilho no Kanban

**Arquivo:** `frontend-crm/src/components/KanbanBoard.tsx`

Quando o usuário arrasta um card de `apresentation → follow-up`:
1. Frontend chama `api.core.getAiProfileMe()` para resolver o `agent_type`
2. Mapeamento `template_key → agent_type`: `hybrid_scheduler` → `agent_3`; `closer*` → `agent_2`; demais → `agent_1`
3. Se `agent_1` ou `agent_3`: abre `FollowUpTransitionModal`
4. Se `agent_2`: move o card diretamente sem popup

Se a qualificação estiver incompleta (backend retorna 409), o `LeadsContext` exibe toast actionable: *"Abra o card do lead e preencha os Critérios de Qualificação antes de avançar."* O operador pode ver e preencher os campos directamente no `LeadCardDialog` (secção Critérios de Qualificação).

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

**Configuração via AI Profile** (substitui hardcodes quando presente):
- `followup_max_attempts` — sobrescreve o default por variante
- `followup_first_offset` — offset em minutos para o primeiro envio
- `followup_cadence` — lista de inteiros (minutos) entre tentativas

**Defaults hardcoded** (usados quando AI Profile não sobrescreve):

`max_attempts`: `sdr_scheduler=4`, `hybrid_scheduler=3`

**Offset do primeiro follow-up:**
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

Após `start-followup`, é criado um job `whatsapp.followup.pregenerate` para pré-aquecer a primeira mensagem.

---

### 4. Reconciliador — asyncio loop

**Arquivo:** `backend-crm/services/followup_reconciler.py`
**Iniciado em:** `backend-crm/app.py` — `_reconciler_loop()` como asyncio task no lifespan

O loop executa `reconcile_due_followups()` periodicamente:
1. Busca leads com `followup_status='active'` e `next_followup_at <= agora`
2. Para cada lead vencido, verifica `followup_reconcile_guard` (idempotência por `(lead_id, due_at)`)
3. Cria job do tipo `whatsapp.followup.tick`
4. Registra guard para evitar duplicação

**Janela de horário:** se o AI Profile do utilizador definir `followup_allowed_hours` (`HH:MM-HH:MM`), o reconciliador adia `next_followup_at` para o início da próxima janela em vez de enfileirar o job.

**Circuit breaker (falhas non-retryable):**
Quando o guard aponta para um job `failed`, o reconciliador lê `j.error.details.retryable`:
- `retryable: true` ou ausente → deleta guard e re-enfileira normalmente
- `retryable: false` → deleta guard, avança `next_followup_at` em 24h, regista `followup_circuit_breaker` em `prospection_logs`, não cria novo job

Previne loops infinitos quando a causa de falha é definitiva (ex.: conexão WhatsApp inativa). Após 24h o lead volta à janela elegível — se a causa persistir, novo cooldown de 24h é aplicado automaticamente.

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

**`progress_followup_after_auto_send`:** incrementa `attempts`, recalcula `next_followup_at` (via `followup_cadence` do AI Profile ou defaults hardcoded abaixo), e cria job `whatsapp.followup.pregenerate` para a próxima mensagem.

**Intervalos entre tentativas (defaults hardcoded em `followup_state.py`, substituíveis por `followup_cadence`):**

| Variant | Tentativa 1→2 | Tentativa 2→3 | Tentativa 3→4 |
|---|---|---|---|
| `sdr_scheduler` | +24h | +3 dias | +7 dias |
| `hybrid_scheduler` | +24h | +48h | — (max=3) |
| `cart_recovery` | +24h | +48h | — (max=3) |

---

### 6. Parada do follow-up

**Arquivo:** `backend-crm/services/followup_state.py`

| Razão | Gatilho | Status final |
|---|---|---|
| `inbound_reply` | Lead respondeu via WhatsApp | `paused` |
| `handoff_human` | `bot_disabled = 1` | `paused` |
| `deal_closed` | Lead movido para `client-list` | `closed` |
| `explicit_rejection` | Lead movido para `prospect-refused` / `disqualified` | `closed` |
| `max_attempts_reached` | Tentativas atingiram `max_attempts` | `closed` |
| `manual_cancel` | Operador cancelou via UI | `closed` |

---

## Cart Recovery (Agent 2)

**Função:** `start_cart_recovery_followup()` em `followup_state.py`

Iniciado automaticamente quando o bot envia link de pagamento (Agent 2 — closer_agressivo). Não requer intervenção do operador.

- Variante: `cart_recovery`
- Cadência: 2h (1ª tentativa), 24h (2ª), 48h (3ª)
- `max_attempts`: 3
- `followup_goal`: `cart_recovery`
- Não inicia se já existe contrato com `status=active`

---

## Controlo Manual (Pause / Resume / Cancel)

**Rotas** em `backend-crm/routes/leads.py`:

| Rota | Status resultante | Notas |
|---|---|---|
| `POST /api/leads/{id}/followup/pause` | `manually_paused` | Cancela jobs pendentes; preserva `attempts` e posição na cadência |
| `POST /api/leads/{id}/followup/resume` | `active` | Recalcula `next_followup_at = now + cadence[attempts]` |
| `POST /api/leads/{id}/followup/cancel` | `closed` | Cancela jobs pendentes; `stop_reason = manual_cancel`; irreversível |

**Distinção de status:**
- `paused` — auto-pausado por resposta inbound (lead voltou a falar)
- `manually_paused` — pausado pelo operador; pode ser retomado via `/resume`

---

## Job type de pré-geração

`whatsapp.followup.pregenerate` — criado em dois momentos:
1. No `start-followup`, para pré-aquecer a primeira mensagem
2. Após cada tick enviado (`progress_followup_after_auto_send`), para a próxima tentativa

Processado pelo executor em `backend-crm/routes/executor.py` juntamente com `whatsapp.followup.tick`.

---

## Central de Follow-up (UI)

**`FollowUpCenter.tsx`** (`frontend-crm/src/pages/FollowUpCenter.tsx`):
- Lista todos os leads com `category=follow-up` e `followup_status != closed`
- Stats bar: `total_active`, `hot_active` (outcome=hot), `urgent_count` (envio em < 2h), `replied_today` (paused hoje)
- Temperatura por lead: `hot`, `warm`, `cold`, `cart_recovery`, `lost`
- AttemptDots: visualização `attempts/max_attempts`
- Notificação para leads com `status=paused` (responderam — requer acção humana)
- Acções por lead: pausar / retomar / cancelar

**`FollowUpEdit.tsx`** (`frontend-crm/src/pages/FollowUpEdit.tsx`):
- Countdown ao vivo (actualizado ao segundo) até ao próximo envio
- Mapa visual da sequência: tentativas concluídas / actual / futuras com labels descritivos
- Variante da cadência visível

**Endpoints de suporte:**
- `GET /api/leads/followups/active` — lista paginada para a Central
- `GET /api/leads/followups/stats` — métricas do stats bar

---

## Qualificação no card (guardrail de transição)

**Arquivo:** `frontend-crm/src/components/LeadCardDialog.tsx`

Secção Critérios de Qualificação — carrega campos do AI Profile e valores já capturados pelo agente:
- Badge **"X pendentes"** / **"Completo"**
- Edição inline com Salvar próprio
- O operador pode preencher campos em falta directamente no card, antes de iniciar o follow-up

O guardrail está no backend em ambos os pontos de entrada (`start-followup` e Kanban drag). Se a qualificação estiver incompleta, o `LeadsContext` exibe toast actionable apontando para esta secção.

---

## Arquivos críticos

| Arquivo | Responsabilidade |
|---|---|
| `frontend-crm/src/components/KanbanBoard.tsx` | Gatilho do popup na mudança de coluna |
| `frontend-crm/src/components/FollowUpTransitionModal.tsx` | Modal com campos dinâmicos por agent_type |
| `frontend-crm/src/components/LeadCardDialog.tsx` | Secção Critérios de Qualificação |
| `frontend-crm/src/pages/FollowUpCenter.tsx` | Central de Follow-up: lista, stats, acções |
| `frontend-crm/src/pages/FollowUpEdit.tsx` | Detalhe por lead: countdown, mapa de sequência |
| `backend-crm/routes/leads.py` | Endpoints: `start-followup`, pause, resume, cancel, active, stats, qualification-fields |
| `backend-crm/services/followup_state.py` | Máquina de estado: start, stop, pause, resume, cancel, progress, cart_recovery |
| `backend-crm/services/followup_reconciler.py` | Detecta vencimentos, guard de idempotência, circuit breaker, janela de horário |
| `backend-crm/app.py` | `_reconciler_loop()` — loop asyncio no lifespan |
| `backend-crm/services/followup_channel_context.py` | Resolve instance_id/phone para o tick |
| `backend-crm/services/agent_type.py` | Mapeamento template_key → agent_type |
| `backend-crm/services/lead_category_policy.py` | Side-effects de categoria (inclui parar follow-up) |
| `backend-crm/services/whatsapp_inbound/inbound_handler.py` | Para follow-up quando lead responde |
| `backend-executors/app/workers/whatsapp_worker.py` | Worker polling |
| `backend-executors/app/runners/whatsapp.py` | Executa job: contexto → LLM → WhatsApp |
| `backend-executors/app/services/decision_engine.py` | Motor de decisão + prompt de follow-up |
