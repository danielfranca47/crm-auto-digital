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
  "trigger": "manual_crm_transition",
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

**`trigger`:** `"manual_crm_transition"` (gesto manual, Kanban → modal) ou `"auto_inactivity"` (disparo automático — ver "Disparo Automático por Inatividade" e "Check-in Automático de Cliente Inativo" abaixo). A Central de Follow-ups (`FollowUpCenter.tsx`) e o detalhe (`FollowUpEdit.tsx`) exibem badge "AUTO"/"Origem: Automático (inatividade)" quando `trigger === "auto_inactivity"`.

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

A cada ciclo, o loop chama em sequência: `reconcile_due_followups()` (ticks de contratos
já activos — abaixo), `scan_inactive_leads_for_auto_followup()` e
`scan_inactive_clients_for_checkin()` (criação automática de novos contratos por
inatividade — ver "Disparo Automático por Inatividade" e "Check-in Automático de
Cliente Inativo" mais abaixo).

`reconcile_due_followups()`:
1. Busca leads com `followup_status='active'`, `next_followup_at <= agora` e
   `category IN ('follow-up', 'client-list')` — `client-list` cobre o check-in
   automático de cliente inactivo, que não move a categoria
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
| `client_checkin` | +3 dias | — (max=2) | — |

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

**Nota — `client_checkin`:** ao fechar por qualquer `stop_reason` exceto `inbound_reply`/
`handoff_human`, `_maybe_redisable_bot_after_checkin_close()` desactiva o bot de novo
(`bot_disabled_reason="category_checkin_closed"`) se o lead ainda estiver em
`client-list` — ver "Check-in Automático de Cliente Inativo" abaixo.

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

## Disparo Automático por Inatividade (Agent 1/3)

Além do gesto manual (Kanban → modal), um lead silencioso em `apresentation` ou
`agendamento` pode iniciar um `followup_contract` por conta própria, sem ação do
operador. `pre-agendamento` fica fora — já tem recuperação dedicada via
`_schedule_preagendamento_checkin()` (`backend-crm/routes/executor.py`), disparada por
um sinal estruturado do LLM filho.

**Configuração no AI Profile** (ver [`agents.md`](agents.md)):
| Campo | Default | Descrição |
|---|---|---|
| `followup_auto_trigger_enabled` | `false` | Liga o disparo automático |
| `followup_auto_trigger_inactivity_days` | `3` | Dias de inatividade para disparar |

**Função:** `scan_inactive_leads_for_auto_followup()` (`followup_reconciler.py`), chamada a cada ciclo do `_reconciler_loop()`.

**Elegibilidade:**
- `category IN ('apresentation', 'agendamento')`, `bot_disabled = 0`, `is_playground = 0`
- Sem contrato de follow-up `active`/`scheduled`
- `agent_type` elegível: `agent_1 → sdr_scheduler`, `agent_3 → hybrid_scheduler` (`resolve_auto_inactivity_variant()`)
- Sinal de inatividade = `MAX(última mensagem inbound, leads.lastMovement)` ≥ `followup_auto_trigger_inactivity_days`
- Qualificação completa (mesmo guardrail do `start-followup` manual, `can_advance_from_qualification()`)
- Fora do cooldown: `leads.followup_auto_trigger_last_fired_at` (DATETIME) — evita re-disparo repetido sobre o mesmo lead

**`start_followup_for_inactivity()`** (`followup_state.py`): cria o contrato com
`trigger="auto_inactivity"` e defaults neutros (`meeting_or_session_happened=None`,
`outcome=None`, `proposal_sent=False`); `followup_goal` por variante: `"reengage"`
(`sdr_scheduler`), `"reengage_conversation"` (`hybrid_scheduler`); `max_attempts` por
variante: `4` (`sdr_scheduler`), `3` (`hybrid_scheduler`); offset do primeiro envio: 30
min. Move `category` para `follow-up` e reativa o bot, igual ao fluxo manual.

**Ordem commit → create_job:** o *scan* chama `create_job()` (fila `pregenerate`) sempre
depois do `conn.commit()` da própria transação — `create_job()` abre a sua própria
conexão SQLite, e chamá-lo antes do commit causa `database is locked`.

---

## Check-in Automático de Cliente Inativo (`client_checkin`)

Cliente já convertido (`category='client-list'`) sem sessão/contacto há N dias recebe
um check-in automático de relacionamento pós-venda — sem pressão de venda, sem reabrir
qualificação. Restrito a `agent_1`/`agent_3`; Agent 2 (`closer_agressivo`) fica fora —
seu bot não passa pelo mesmo side-effect de desactivação ao entrar em `closing`/
`client-list` (ver [`agents.md`](agents.md), "Toggle de Bot por Lead").

**Configuração no AI Profile** (ver [`agents.md`](agents.md)):
| Campo | Default | Descrição |
|---|---|---|
| `followup_checkin_auto_trigger_enabled` | `false` | Liga o check-in automático |
| `followup_checkin_inactivity_days` | `30` | Dias de inatividade para disparar |
| `followup_checkin_instructions` | `null` | Texto livre injectado no prompt da variante `client_checkin` |

**Função:** `scan_inactive_clients_for_checkin()` (`followup_reconciler.py`), chamada a cada ciclo do `_reconciler_loop()`.

**Elegibilidade:**
- `category = 'client-list'`, `is_playground = 0`, `agent_type IN ('agent_1', 'agent_3')`
- Sem contrato de follow-up `active`/`scheduled`
- Sinal de inatividade = `MAX(última appointment.start_at não cancelada, última mensagem inbound, leads.lastMovement)` ≥ `followup_checkin_inactivity_days`
- Fora do cooldown: mesma coluna `leads.followup_auto_trigger_last_fired_at` do disparo
  acima (`client-list` e `apresentation`/`agendamento` são mutuamente exclusivos para o
  mesmo lead, sem conflito de uso)
- **Sem** filtro de `bot_disabled` (cliente em `client-list` normalmente já está
  desligado) e **sem** guardrail de qualificação (o cliente já comprou)

**`start_client_checkin_followup()`** (`followup_state.py`): cria o contrato com
`followup_variant="client_checkin"`, `followup_goal="checkin"`, `max_attempts=2`,
`trigger="auto_inactivity"`, offset do primeiro envio 30 min. **Não** move `category`
(permanece `client-list` — evita confundir o Kanban de vendas com um cliente já
convertido "voltando"). Reativa o bot (`bot_disabled=0`, `bot_disabled_reason=NULL`)
porque o repouso normal de `client-list` é bot desligado.

**Re-desativação ao encerrar:** `_maybe_redisable_bot_after_checkin_close()` devolve o
bot a `bot_disabled=1`/`bot_disabled_reason="category_checkin_closed"` quando o
contrato fecha sem conversa activa e o lead ainda está em `client-list`. Chamado em
`stop_followup()` (para todo `stop_reason` exceto `inbound_reply`/`handoff_human`), no
branch `max_attempts_reached` de `progress_followup_after_auto_send()`, e em
`cancel_followup_manually()`.

**Personalização do prompt:** branch dedicado `client_checkin` em
`_build_child_prompt_follow_up()` (`decision_engine.py`) — ver "Personalização das
Mensagens de Follow-Up" abaixo.

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

## Personalização das Mensagens de Follow-Up

O prompt da Filha Follow-up (`_build_child_prompt_follow_up()` em `decision_engine.py`) tem 3 camadas de personalização por variante, em ordem de prioridade crescente:

```
[ABERTURA OBRIGATÓRIA — saudação calorosa e contextual]   ← hardcoded, default
[instrução hardcoded da variante]
[_goal_rule — por followup_goal, se configurado]           ← AI Profile
[_variant_operator_block — texto livre do operador]        ← AI Profile
[regras gerais de modo]
...
[custom_instructions — global]                             ← AI Profile
```

### Abertura calorosa (default para todos os agentes)

Todos os `variant_rule` têm instrução `ABERTURA OBRIGATÓRIA` que força uma saudação contextual antes de qualquer conteúdo comercial. `sdr_scheduler` e `hybrid_scheduler` sempre abrem com saudação; `cart_recovery` tentativa 1 abre com saudação, tentativas 2 e 3 são directas (urgência justifica).

### Campos configuráveis do AI Profile por variante

| Campo | Variante | O que faz |
|---|---|---|
| `followup_sdr_instructions` | `sdr_scheduler` | Texto livre injectado após a instrução hardcoded da variante |
| `followup_recovery_instructions` | `cart_recovery` | Texto livre injectado após a instrução hardcoded da variante |
| `followup_postsession_instructions` | `hybrid_scheduler` | Texto livre injectado após a instrução hardcoded da variante |
| `followup_goal_instructions` | `sdr_scheduler` | Dict por `followup_goal` — instrução específica para o goal activo |
| `cart_recovery_attempt_instructions` | `cart_recovery` | Lista de 3 strings — sobrescreve instrução hardcoded da tentativa correspondente |
| `followup_outcome_instructions` | `hybrid_scheduler` | Dict por `outcome` — sobrescreve instrução hardcoded do outcome correspondente |
| `followup_checkin_instructions` | `client_checkin` | Texto livre injectado após a instrução hardcoded da variante |

**Fallback:** quando o campo não está configurado ou a chave não existe, o comportamento hardcoded é mantido inalterado.

### Instruções hardcoded por variante (defaults)

**`sdr_scheduler`:** follow-up consultivo pós-reunião — reforçar valor, síntese do contexto, próximo passo.

**`cart_recovery` por tentativa:**
- T1: lembrete neutro — pedido reservado, sem pressão
- T2: benefício + objeção mais comum do nicho
- T3: urgência máxima — oferta expira, CTA directo

**`hybrid_scheduler` por outcome:**
- `interested_not_closed`: retomar contexto, remover objeção, propor nova data
- `reschedule_needed`: oferecer 2-3 horários, pergunta fechada
- `converted`: onboarding/boas-vindas, confirmar próximo passo

**`client_checkin`:** check-in de relacionamento pós-venda — abertura calorosa de quem
já é cliente, sem pressão de venda; objetivo único é perguntar como está e propor
agendar a próxima sessão (2-3 horários directos na mensagem, sem mudar de categoria);
nunca reabre qualificação antiga nem trata como lead novo.

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
| `backend-crm/services/followup_state.py` | Máquina de estado: start, stop, pause, resume, cancel, progress, cart_recovery, auto_inactivity, client_checkin |
| `backend-crm/services/followup_reconciler.py` | Detecta vencimentos, guard de idempotência, circuit breaker, janela de horário, disparo automático de novos contratos (inatividade/check-in) |
| `backend-crm/app.py` | `_reconciler_loop()` — loop asyncio no lifespan |
| `backend-crm/services/followup_channel_context.py` | Resolve instance_id/phone para o tick |
| `backend-crm/services/agent_type.py` | Mapeamento template_key → agent_type |
| `backend-crm/services/lead_category_policy.py` | Side-effects de categoria (inclui parar follow-up) |
| `backend-crm/services/whatsapp_inbound/inbound_handler.py` | Para follow-up quando lead responde |
| `backend-executors/app/workers/whatsapp_worker.py` | Worker polling |
| `backend-executors/app/runners/whatsapp.py` | Executa job: contexto → LLM → WhatsApp |
| `backend-executors/app/services/decision_engine.py` | Motor de decisão + prompt de follow-up |
