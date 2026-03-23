# Diagnóstico: Sistema de Follow-Up de Leads

**Data:** 2026-03-23
**Branch atual:** `feature/etapa-8-n8n-orion`

> **Nota:** o nome "n8n" aparece em alguns tipos de job (`whatsapp.inbound.n8n`) e comentários, mas é apenas um artefato histórico. Toda a execução real é feita pelo `backend-executors`. Ver [info_n8n.md](info_n8n.md) para detalhes.

---

## 1. Visão Geral da Arquitetura

O follow-up automático é composto por **4 camadas**:

```
[Frontend React]          Gatilho Kanban → Modal
       ↓
[Backend CRM]             POST /leads/start-followup → cria contrato
       ↓
[Reconciliador]           POST /internal/followup/reconcile ← ⚠️ NINGUÉM CHAMA (ver seção 4.1)
       ↓
[backend-executors]       Worker polling → decision engine → LLM → WhatsApp
```

---

## 2. Fluxo Completo — Passo a Passo

### 2.1 Gatilho no Kanban (Frontend)

**Arquivo:** `frontend-crm/src/components/KanbanBoard.tsx`

Quando o usuário arrasta um card de **apresentation → follow-up**:

1. O frontend chama `api.core.getAiProfileMe()` para resolver o `agent_type` do usuário.
2. Mapeamento de `template_key` para `agent_type`:
   - `hybrid_scheduler` → `agent_3`
   - `closer*` → `agent_2`
   - qualquer outro → `agent_1`
3. **Se `agent_type` for `agent_1` ou `agent_3`**: abre o modal `FollowUpTransitionModal`.
4. **Se `agent_type` for `agent_2`**: move o card direto, **sem popup**, sem contrato de follow-up.

> **Nota:** `agent_2` é intencionalmente excluído do fluxo de follow-up. O closer agressivo não recebe follow-up automático — é uma decisão de design, não um bug.

---

### 2.2 Modal FollowUpTransitionModal

**Arquivo:** `frontend-crm/src/components/FollowUpTransitionModal.tsx`

O modal exibe campos **dinâmicos por tipo de agente**:

#### Campos comuns (todos os agentes)
| Campo | Tipo | Obrigatoriedade |
|-------|------|-----------------|
| "A reunião/sessão aconteceu?" | select | Obrigatório |
| Observação do operador | textarea | Opcional |

#### Agent 1 — Reunião aconteceu (`yes`)
| Campo | Opções |
|-------|--------|
| "Como esse lead saiu da reunião?" | `hot`, `warm`, `cold`, `lost` |
| "Você enviou proposta?" | `yes`, `no` |
| "Qual o objetivo do follow-up?" | `advance_closing`, `nurture`, `reschedule_conversation`, `register_only` |

#### Agent 1 — Reunião NÃO aconteceu
| Campo | Opções |
|-------|--------|
| "O que você quer que o bot faça?" | `recover_and_reschedule`, `reengage`, `register_only` |

#### Agent 3 — Reunião aconteceu (`yes`)
| Campo | Opções / Condição |
|-------|------------------|
| "Como terminou a sessão?" | `interested_not_closed`, `reschedule_needed`, `lost`, `converted` |
| "O que o bot deve fazer?" | `nurture_interest`, `prompt_reply`, `prepare_next_conversation` — só se outcome = `interested_not_closed` |
| "O bot deve tentar remarcar?" | `yes`, `no` — só se outcome = `reschedule_needed` |

#### Agent 3 — Reunião NÃO aconteceu
| Campo | Opções |
|-------|--------|
| "O que o bot deve tentar fazer agora?" | `recover_and_reschedule`, `reengage_conversation`, `register_only` |

**Conclusão sobre coerência dos popups com os agentes:**
✅ Os popups estão corretamente diferenciados por `agent_type`. Agent 1 e Agent 3 recebem campos distintos. Agent 2 não recebe popup algum (intencional).

---

### 2.3 POST /leads/start-followup (Backend CRM)

**Arquivo:** `backend-crm/routes/leads.py` (aprox. linhas 409–544)

Ao submeter o modal:

1. **Validações:**
   - Lead existe e pertence ao usuário
   - Lead está em `apresentation` (única origem permitida)
   - `agent_type` no payload bate com o do banco
   - `agent_type` é `agent_1` ou `agent_3`
   - Qualificação está completa (via `qualification_guardrails.py`)

2. **Criação do Followup Contract** (JSON salvo em `leads.followup_contract`):

```json
{
  "phase": "follow-up",
  "version": 1,
  "followup_variant": "sdr_scheduler",      // agent_1 → sdr_scheduler / agent_3 → hybrid_scheduler
  "trigger": "manual_crm_transition",
  "status": "active",
  "attempts": 0,
  "max_attempts": 4,                         // sdr_scheduler=4, hybrid_scheduler=3 (hardcoded)
  "next_followup_at": "<agora + offset>",    // ver tabela abaixo
  "last_followup_at": null,
  "stop_reason": null,
  "meeting_happened": true,                  // ⚠️ redundante (derivado de meeting_or_session_happened)
  "meeting_or_session_happened": "yes",
  "outcome": "hot",
  "temperature": "hot",                      // ⚠️ duplicado de outcome
  "proposal_sent": true,
  "followup_goal": "advance_closing",
  "operator_note": "...",
  "created_at": "<timestamp>"
}
```

3. **Atualização do lead:**
   - `category = follow-up`
   - `bot_disabled = 0` (bot é reativado)
   - `followup_status = active`
   - `next_followup_at = agora + offset`

**Offset do primeiro follow-up (hardcoded em `routes/leads.py`):**

| Variant | Condição | Offset |
|---------|----------|--------|
| `sdr_scheduler` (agent_1) | qualquer | 30 min |
| `hybrid_scheduler` (agent_3) | reunião = `yes` | 120 min (2h) |
| `hybrid_scheduler` (agent_3) | `no_show`, `canceled`, `needs_reschedule` | 30 min |

---

### 2.4 Reconciliador — Criação dos Jobs

**Arquivo:** `backend-crm/services/followup_reconciler.py`
**Endpoint:** `POST /internal/followup/reconcile` (protegido por service token)

**Responsabilidade:** varrer leads com follow-up vencido e criar os jobs para o worker processar.

**O que faz:**
1. Busca leads com `followup_status='active'` e `next_followup_at <= agora`
2. Para cada lead vencido, verifica a tabela `followup_reconcile_guard` (idempotência por `(lead_id, due_at)`)
3. Cria job do tipo `whatsapp.followup.tick` na fila de jobs
4. Registra guard para evitar duplicação

> ⚠️ **Problema crítico:** ver seção 4.1

---

### 2.5 Execução do Follow-Up (backend-executors)

**Arquivos:**
- `backend-executors/app/workers/whatsapp_worker.py` — polling loop
- `backend-executors/app/runners/whatsapp.py` — executor do job
- `backend-executors/app/services/decision_engine.py` — motor de decisão + prompt LLM

#### 2.5.1 Worker (polling)

O `whatsapp_worker.py` roda como processo contínuo (não como API HTTP). Ele:
- Chama `crm_client.get_next_job(types)` a cada 0.5–30s (backoff progressivo quando não há jobs)
- Tipos consumidos: `whatsapp.inbound.n8n` e `whatsapp.followup.tick`
- Ao encontrar job: chama `execute_job(job_id)`

#### 2.5.2 Execução do Job

O `execute_job()` no `runners/whatsapp.py`:

1. **Claim do job** — lease de 300s (`executors:local`)
2. **Busca contexto** — `crm_client.get_whatsapp_execution_context(job_id)` → retorna lead, history, ai_profile, playbook, qualification_state
3. **Injeta followup_contract** — `_inject_followup_contract_context()` extrai do `lead.followup_contract` os sinais:
   ```python
   followup_signals = {
     "followup_goal": ...,
     "followup_outcome": ...,
     "followup_variant": ...,
     "followup_attempts": ...,
     "followup_meeting_or_session_happened": ...,
     "followup_proposal_sent": ...,
     "followup_operator_note": ...,
   }
   metadata["followup_context"] = followup_signals
   ```
4. **Decision engine** — `decision_engine.decide(context)` → monta prompt + chama LLM
5. **Guardrails pós-decisão** — checkout link, handoff policy
6. **Envia mensagem** — via `core_client.send_whatsapp_message()` (UazAPI via backend-core)
7. **Confirma envio** — `crm_client.complete_job()` → aciona `progress_followup_after_auto_send()`

#### 2.5.3 Como followup_goal e outcome chegam ao LLM

O `decision_engine.py` possui um builder específico para follow-up (`_build_child_followup_prompt`), que:
- Monta `followup_summary` com `followup_goal`, `outcome`, `operator_note`, `meeting_happened`, `proposal_sent`
- Inclui regras de variant (`sdr_scheduler` vs `hybrid_scheduler`)
- Injeta instrução prioritária: *"use followup_contract_signals como fonte principal da resposta"*
- Passa `tone_of_voice`, `custom_instructions`, `offer_description`, `goals`, `niche`, `identity_mode` do AI Profile

✅ Os dados do popup e do AI Profile **chegam ao prompt do LLM** via backend-executors.

**Intervalo entre tentativas subsequentes (hardcoded em `followup_state.py`):**

| Variant | Tentativa 1 enviada → próxima | Tentativa 2 enviada → próxima | Tentativa 3 enviada → próxima |
|---------|-------------------------------|-------------------------------|-------------------------------|
| `sdr_scheduler` (agent_1) | +24h | +3 dias | +7 dias |
| `hybrid_scheduler` (agent_3) | +24h | +48h | — (max_attempts=3) |

---

### 2.6 Parada do Follow-Up

**Arquivo:** `backend-crm/services/followup_state.py`

| Razão | Gatilho | Status final |
|-------|---------|-------------|
| `STOP_INBOUND_REPLY` | Lead respondeu via WhatsApp | `paused` |
| `STOP_HANDOFF_HUMAN` | `bot_disabled = 1` | `paused` |
| `STOP_DEAL_CLOSED` | Lead movido para `client-list` | `closed` |
| `STOP_EXPLICIT_REJECTION` | Lead movido para `prospect-refused` / `disqualified` | `closed` |
| `STOP_MAX_ATTEMPTS_REACHED` | Tentativas atingiram `max_attempts` | `closed` |

---

## 3. Arquivos-Chave Envolvidos

| Arquivo | Responsabilidade |
|---------|-----------------|
| `frontend-crm/src/components/KanbanBoard.tsx` | Gatilho do popup na mudança de coluna |
| `frontend-crm/src/components/FollowUpTransitionModal.tsx` | Modal com campos dinâmicos por agent_type |
| `frontend-crm/src/services/api.ts` | Chamada POST /leads/start-followup |
| `backend-crm/routes/leads.py` | Endpoint start_followup_transition (validação + criação do contrato) |
| `backend-crm/services/followup_state.py` | Máquina de estado (start, stop, progress, pausa) |
| `backend-crm/services/followup_reconciler.py` | Detecta vencimentos e cria jobs |
| `backend-crm/services/followup_channel_context.py` | Resolve instance_id/phone para o tick |
| `backend-crm/routes/executor.py` | Endpoint execution-context + confirmação de envio |
| `backend-crm/services/ai_orchestrator/orchestrator.py` | Monta context bundle entregue ao executor |
| `backend-crm/services/ai_playbooks/__init__.py` | Playbooks de resposta por template_key |
| `backend-crm/services/agent_type.py` | Mapeamento template_key → agent_type |
| `backend-crm/services/lead_category_policy.py` | Side-effects de mudança de categoria (inclui parar follow-up) |
| `backend-crm/services/whatsapp_inbound/inbound_handler.py` | Para o follow-up quando lead responde |
| `backend-core/app/models/ai_profile.py` | Model do AI Profile (colunas disponíveis) |
| `backend-executors/app/workers/whatsapp_worker.py` | Worker polling — consome fila de jobs |
| `backend-executors/app/runners/whatsapp.py` | Executa job: contexto → LLM → WhatsApp |
| `backend-executors/app/services/decision_engine.py` | Motor de decisão + builder de prompt para o LLM |

---

## 4. Problemas Detectados

### 4.1 Reconciliador sem acionamento — ⚠️ CRÍTICO

**Situação:** O endpoint `POST /internal/followup/reconcile` é o mecanismo que cria os jobs `whatsapp.followup.tick`. Sem ele ser chamado, o worker do `backend-executors` nunca recebe esses jobs, portanto **nenhum follow-up automático é disparado**.

**O que existe:**
- ✅ O worker (`whatsapp_worker.py`) está pronto para processar `whatsapp.followup.tick`
- ✅ O reconciliador (`followup_reconciler.py`) está implementado e correto
- ❌ **Nada chama `POST /internal/followup/reconcile` periodicamente**

Não há:
- Scheduler interno (APScheduler, Celery beat) no `backend-crm`
- Background task no startup do `backend-crm` (`app.py`)
- Chamada periódica no `backend-executors` (o worker só processa jobs existentes)
- Nenhuma plataforma externa (n8n, cron do servidor, etc.)

**Consequência:** os contratos de follow-up são criados corretamente no banco, `next_followup_at` avança, mas nenhum job é gerado e nenhuma mensagem é enviada.

**Solução recomendada:** implementar um scheduler interno no `backend-crm` (ex: lifespan task com `asyncio` ou `APScheduler`) que chame `reconcile_due_followups()` a cada 1–5 minutos. Alternativamente, o `backend-executors` pode adicionar uma rotina de reconciliação própria chamando `POST /internal/followup/reconcile` no início de cada ciclo de polling.

---

### 4.2 Playbook específico para agent_3 ausente

**Arquivo:** `backend-crm/services/ai_playbooks/__init__.py`

Apenas 3 playbooks existem: `sdr_padrao`, `consultor_especialista`, `closer_agressivo`.

O `template_key = hybrid_scheduler` (agent_3) cai no fallback `sdr_padrao`. Não há playbook específico para o agente 3 com regras de agendamento, remarcação ou sessões.

---

### 4.3 Primeiro offset não é configurável pelo usuário

Os delays do primeiro follow-up (30 min / 2h) estão hardcoded em `routes/leads.py`. O usuário não pode configurar via popup nem via AI Profile.

---

### 4.4 Max attempts não é configurável pelo usuário

Hardcoded: `sdr_scheduler=4`, `hybrid_scheduler=3`. Não exposto como configuração.

---

### 4.5 Campo `temperature` duplica `outcome` (minor)

```python
"outcome": payload.outcome,
"temperature": payload.outcome,  # mesmo valor, sempre
```

Redundante. Risco de divergência em versões futuras.

---

### 4.6 Campo `meeting_happened` redundante (minor)

```python
"meeting_happened": payload.meeting_or_session_happened == "yes",
"meeting_or_session_happened": payload.meeting_or_session_happened,
```

`meeting_happened` é sempre derivado do outro campo.

---

## 5. Campos do AI Profile — Usados vs. Disponíveis no Follow-Up

**Arquivo:** `backend-core/app/models/ai_profile.py`
**Referência:** `backend-executors/app/services/decision_engine.py` (`_build_prompt`, `_build_child_followup_prompt`)

| Campo AI Profile | Disponível | Chegam ao LLM? | Observação |
|-----------------|-----------|----------------|------------|
| `template_key` | ✅ | ✅ | Define agent_type + seleciona playbook |
| `agent_mode` | ✅ | ✅ | `apply_mode_overrides` + incluído no ai_summary do prompt |
| `brand_name` | ✅ | ✅ | Incluído no ai_summary |
| `tone_of_voice` | ✅ | ✅ | Incluído no ai_summary do prompt |
| `niche` | ✅ | ✅ | Incluído no ai_summary do prompt |
| `target_audience` | ✅ | ✅ | Incluído no ai_summary do prompt |
| `offer_description` | ✅ | ✅ | Incluído no ai_summary do prompt |
| `goals` | ✅ | ✅ | Incluído no ai_summary do prompt |
| `custom_instructions` | ✅ | ✅ | Incluído no ai_summary do prompt |
| `identity_mode` | ✅ | ✅ | Incluído no ai_summary do prompt |
| `presentation_variant` | ✅ | ✅ | Resolve variant → passado no playbook |
| `hybrid_flow_style` | ✅ | ✅ | Passado no playbook |
| `offer_pack` | ✅ | ✅ | Passado no playbook + guardrail de checkout link |
| `handoff_policy` | ✅ | ✅ Parcial | Usado em handoff_policy service, não no prompt direto |
| `handoff_custom_text` | ✅ | ✅ Parcial | Incluído no ai_summary |
| `requires_handoff` | ✅ | ❌ | Flag, não lida pelo decision engine |
| `human_in_loop` | ✅ | ❌ | Flag, não lida pelo decision engine |

✅ A maioria dos campos do AI Profile é corretamente passada ao LLM pelo `backend-executors`.

---

## 6. Mapa Visual Resumido

```
┌─────────────────────────────────────────────────────────────────────┐
│ KANBAN (frontend)                                                   │
│ Lead: apresentation → follow-up                                     │
│   ↓ se agent_1 ou agent_3                                          │
│ FollowUpTransitionModal (campos dinâmicos por agent_type)           │
│   ↓ submit                                                          │
└─────────────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────────┐
│ POST /leads/start-followup  (backend-crm)                           │
│ • valida qualificação                                               │
│ • cria followup_contract (JSON com followup_goal, outcome, etc.)    │
│ • SET bot_disabled=0, followup_status=active                        │
│ • SET next_followup_at = agora + offset (30min ou 2h)               │
└─────────────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────────┐
│ POST /internal/followup/reconcile  ← ⚠️ NÃO É CHAMADO POR NINGUÉM │
│ • query: followup_status=active AND next_followup_at <= agora       │
│ • cria job: whatsapp.followup.tick                                  │
│ • guard de idempotência em followup_reconcile_guard                 │
└─────────────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────────┐
│ backend-executors  (whatsapp_worker — polling loop)                 │
│ • GET next_job → encontra whatsapp.followup.tick                    │
│ • GET /whatsapp/execution-context?job_id=X                          │
│   → lead (com followup_contract), ai_profile, playbook, history     │
│ • _inject_followup_contract_context()                               │
│   → followup_goal, outcome, operator_note → metadata.followup_ctx  │
│ • decision_engine.decide() → LLM (com prompt de follow-up)         │
│ • send via core_client → UazAPI → WhatsApp                         │
└─────────────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────────┐
│ complete_job → backend-crm                                          │
│ • progress_followup_after_auto_send()                               │
│ • incrementa attempts                                               │
│ • calcula next_followup_at (+24h, +3d, +7d / +24h, +48h)           │
│ • se max_attempts: status=closed                                    │
└─────────────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────────┐
│ Lead responde (inbound webhook → backend-crm)                       │
│ • stop_followup_on_inbound_reply()                                  │
│ • followup_status=paused, next_followup_at=NULL                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 7. Checklist de Verificação

- [ ] **CRÍTICO:** Implementar chamada periódica ao reconciliador (`reconcile_due_followups()`) — scheduler interno no `backend-crm` ou rotina no `backend-executors`
- [ ] Criar playbook específico para `hybrid_scheduler` (agent_3) em `ai_playbooks/__init__.py`
- [ ] Remover campo `temperature` duplicado do followup_contract
- [ ] Remover campo `meeting_happened` redundante do followup_contract
- [ ] Avaliar expor `max_attempts` e offsets como configurações no AI Profile
