# Diagnóstico: Sistema de Follow-Up de Leads

**Data:** 2026-03-23
**Branch atual:** `feature/etapa-8-n8n-orion`

---

## 1. Visão Geral da Arquitetura

O follow-up automático é composto por **4 camadas**:

```
[Frontend React]          Gatilho Kanban → Modal
       ↓
[Backend CRM]             POST /leads/start-followup → cria contrato
       ↓
[Reconciliador]           POST /internal/followup/reconcile (chamado externamente, ex. n8n)
       ↓
[Executor / n8n]          Processa job → chama LLM → envia mensagem WhatsApp
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

> **Nota crítica:** `agent_2` é intencionalmente excluído do fluxo de follow-up. O closer agressivo não recebe follow-up automático — é uma decisão de design, não um bug.

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
✅ Os popups estão corretamente diferenciados por `agent_type`. Agent 1 e Agent 3 recebem campos distintos. Agent 2 não recebe popup algum.

---

### 2.3 POST /leads/start-followup (Backend)

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
  "max_attempts": 4,                         // sdr_scheduler=4, hybrid_scheduler=3
  "next_followup_at": "<agora + offset>",    // ver tabela abaixo
  "last_followup_at": null,
  "stop_reason": null,
  "meeting_happened": true,
  "meeting_or_session_happened": "yes",
  "outcome": "hot",
  "temperature": "hot",                      // ⚠️ DUPLICADO de outcome (ver seção 5)
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

**Offset do primeiro follow-up (hardcoded):**

| Variant | Condição | Offset |
|---------|----------|--------|
| `sdr_scheduler` (agent_1) | qualquer | 30 min |
| `hybrid_scheduler` (agent_3) | reunião = `yes` | 120 min (2h) |
| `hybrid_scheduler` (agent_3) | `no_show`, `canceled`, `needs_reschedule` | 30 min |

---

### 2.4 Reconciliador (Agendamento de Jobs)

**Arquivo:** `backend-crm/services/followup_reconciler.py`

**Acionamento:** Via chamada externa — `POST /internal/followup/reconcile` (endpoint protegido por service token). **Não há scheduler interno** no Python; a chamada periódica depende de um agente externo (presumivelmente n8n ou cron).

> ⚠️ **Ponto crítico:** Se nenhum sistema externo chamar esse endpoint periodicamente, os follow-ups nunca serão disparados.

**O que faz:**
1. Busca leads com `followup_status='active'` e `next_followup_at <= agora`
2. Para cada lead vencido, verifica a tabela `followup_reconcile_guard` (evita duplicação)
3. Cria job do tipo `whatsapp.followup.tick`
4. Registra guard com `(lead_id, due_at)` — chave única

---

### 2.5 Execução do Follow-Up (n8n / Executor)

**Arquivo:** `backend-crm/routes/executor.py`

O executor (ou n8n) consome o job `whatsapp.followup.tick`:

1. Chama `GET /whatsapp/execution-context?job_id=X`
2. O endpoint retorna o **context bundle** completo:
   - `lead` (com o `followup_contract` completo)
   - `history` (histórico de mensagens recentes)
   - `ai_profile` (perfil de IA do usuário)
   - `playbook` (regras de resposta)
   - `qualification_state` (estado de qualificação)
   - `metadata` (canal, phone, instance_id, etc.)
3. n8n/LLM usa esse contexto para compor a mensagem de follow-up
4. Após o envio, o executor chama `progress_followup_after_auto_send()`

**Intervalo entre tentativas subsequentes (hardcoded):**

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
| `backend-crm/services/followup_reconciler.py` | Detecta vencimentos e enfileira jobs |
| `backend-crm/services/followup_channel_context.py` | Resolve instance_id/phone para o tick |
| `backend-crm/routes/executor.py` | Endpoint execution-context + confirmação de envio |
| `backend-crm/services/ai_orchestrator/orchestrator.py` | Monta context bundle entregue ao n8n/LLM |
| `backend-crm/services/ai_playbooks/__init__.py` | Playbooks de resposta por template_key |
| `backend-crm/services/agent_type.py` | Mapeamento template_key → agent_type |
| `backend-crm/services/lead_category_policy.py` | Side-effects de mudança de categoria (inclui parar follow-up) |
| `backend-crm/services/whatsapp_inbound/inbound_handler.py` | Para o follow-up quando lead responde |
| `backend-core/app/models/ai_profile.py` | Model do AI Profile (colunas disponíveis) |

---

## 4. Problemas Detectados

### 4.1 Reconciliador sem acionamento garantido ⚠️ CRÍTICO

O endpoint `POST /internal/followup/reconcile` precisa ser chamado externamente de forma periódica. Não há evidência no código Python de um scheduler interno (ex. APScheduler, Celery beat). Se o workflow n8n responsável por chamar esse endpoint estiver inativo ou não existir, **nenhum follow-up será disparado**, mesmo que o contrato esteja criado corretamente.

**O que verificar:** existe um workflow n8n com trigger de `cron` ou `interval` que chama `POST /internal/followup/reconcile`?

---

### 4.2 followup_goal e outcome não modulam o prompt Python ⚠️

Os campos `followup_goal`, `outcome`, `proposal_sent` e `operator_note` coletados no popup **são armazenados no contrato** e passados para o n8n via `execution-context`, mas **não há nenhuma lógica Python** que modifique o prompt ou o playbook com base nesses valores.

O behavior atual:
- O `playbook` montado pelo orquestrador usa `agent_mode`, `template_key`, `presentation_variant` — mas **não lê** `followup_goal` ou `outcome`.
- O `conversation_goal` é sempre `"qualify"` ou `"advance"` — nunca `"nurture"`, `"recover"`, etc.

**Consequência:** se n8n não interpretar explicitamente `lead.followup_contract.followup_goal` no prompt, todas as mensagens de follow-up terão o mesmo tom, independente de o usuário ter selecionado "advance_closing", "nurture" ou "recover_and_reschedule".

**O que verificar:** o workflow n8n de follow-up usa `followup_goal` para customizar o system prompt do LLM?

---

### 4.3 Campo `temperature` duplica `outcome` ⚠️

No contrato criado em `routes/leads.py`:
```python
"outcome": payload.outcome,
"temperature": payload.outcome,  # mesmo valor
```

`temperature` é redundante. Pode causar confusão em versões futuras se os dois campos divergirem.

---

### 4.4 Campo `meeting_happened` redundante

```python
"meeting_happened": payload.meeting_or_session_happened == "yes",
"meeting_or_session_happened": payload.meeting_or_session_happened,
```

`meeting_happened` é derivado de `meeting_or_session_happened`. A presença de ambos cria redundância.

---

### 4.5 Playbooks são MVP mínimo

**Arquivo:** `backend-crm/services/ai_playbooks/__init__.py`

Apenas 3 playbooks existem:
- `sdr_padrao`
- `consultor_especialista`
- `closer_agressivo`

O template_key `hybrid_scheduler` (agent_3) cai no fallback `sdr_padrao`. Não há playbook específico para o agente 3.

---

### 4.6 Primeiro offset não é configurável pelo usuário

Os delays de 30 min e 2h estão hardcoded em `routes/leads.py`. O usuário não pode configurar "quero que o primeiro follow-up vá em 1h" — nem via popup, nem via AI Profile.

---

### 4.7 Max attempts não é configurável pelo usuário

Hardcoded em `routes/leads.py`: `sdr_scheduler=4`, `hybrid_scheduler=3`. Não exposto como configuração no AI Profile.

---

## 5. Campos do AI Profile — Usados vs. Disponíveis no Follow-Up

**Arquivo:** `backend-core/app/models/ai_profile.py`

| Campo AI Profile | Disponível | Usado no Follow-Up? | Onde é Usado |
|-----------------|-----------|---------------------|--------------|
| `template_key` | ✅ | ✅ | Define agent_type + seleciona playbook |
| `agent_mode` | ✅ | ✅ Parcial | `apply_mode_overrides` no orchestrator (max_chars, qualification_depth) — mas apenas para inbound, não exclusivamente follow-up |
| `presentation_variant` | ✅ | ✅ Parcial | `_resolve_presentation_contract` → passado no playbook para n8n — mas sem garantia de uso no follow-up específico |
| `hybrid_flow_style` | ✅ | ✅ Parcial | Idem `presentation_variant` |
| `offer_pack` | ✅ | ✅ Parcial | Passado no playbook para n8n |
| `identity_mode` | ✅ | ❌ | Armazenado no AI Profile mas **não lido** pelo orchestrator no context bundle |
| `handoff_policy` | ✅ | ❌ | Afeta handoff (parar bot), não modula mensagem de follow-up |
| `handoff_custom_text` | ✅ | ❌ | Apenas para handoff |
| `requires_handoff` | ✅ | ❌ | Flag de flag, não usado no follow-up |
| `human_in_loop` | ✅ | ❌ | Flag, não usado no follow-up |
| `tone_of_voice` | ✅ | ❌ | Armazenado no AI Profile, **não injetado** no context bundle entregue ao n8n |
| `custom_instructions` | ✅ | ❌ | Idem `tone_of_voice` |
| `offer_description` | ✅ | ❌ | Idem |
| `goals` | ✅ | ❌ | Idem |
| `niche` / `target_audience` | ✅ | ❌ | Idem |

**Campos críticos não sendo passados para o LLM:**
`tone_of_voice`, `custom_instructions`, `offer_description`, `goals`, `niche`, `target_audience`, `identity_mode` ficam **no AI Profile mas não chegam ao LLM** via context bundle atual. Se n8n não buscar essas informações diretamente na API do core, o LLM não os utiliza.

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
│ POST /leads/start-followup                                          │
│ • valida qualificação                                               │
│ • cria followup_contract (JSON)                                     │
│ • SET bot_disabled=0, followup_status=active                        │
│ • SET next_followup_at = agora + offset (30min ou 2h)               │
└─────────────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────────┐
│ POST /internal/followup/reconcile  ← chamado por n8n/cron externo  │
│ • query: followup_status=active AND next_followup_at <= agora       │
│ • cria job: whatsapp.followup.tick                                  │
│ • guard de idempotência em followup_reconcile_guard                 │
└─────────────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────────┐
│ GET /whatsapp/execution-context?job_id=X  ← chamado por n8n        │
│ • retorna: lead (+ followup_contract), ai_profile, playbook,        │
│   history, qualification_state, metadata                            │
│ • followup_goal, outcome, operator_note disponíveis em              │
│   lead.followup_contract — mas NÃO modificam o playbook Python      │
└─────────────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────────┐
│ n8n: compõe prompt + chama LLM + envia WhatsApp                    │
│ (lógica de prompt fora do código Python — risco de desconexão)      │
└─────────────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────────┐
│ POST /whatsapp/outbound/confirm-sent                                │
│ • progress_followup_after_auto_send()                               │
│ • incrementa attempts                                               │
│ • calcula next_followup_at (+24h, +3d, +7d / +24h, +48h)           │
│ • se max_attempts: status=closed                                    │
└─────────────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────────┐
│ Lead responde (inbound webhook)                                     │
│ • stop_followup_on_inbound_reply()                                  │
│ • followup_status=paused, next_followup_at=NULL                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 7. Checklist de Verificação Recomendada

- [ ] **n8n tem workflow com cron** chamando `POST /internal/followup/reconcile` periodicamente?
- [ ] **n8n usa `followup_goal`** do `lead.followup_contract` para customizar o prompt do LLM?
- [ ] **n8n usa `outcome`** (temperatura do lead) para ajustar o tom da mensagem?
- [ ] **n8n usa `operator_note`** como contexto adicional para o LLM?
- [ ] **n8n injeta `tone_of_voice`, `custom_instructions`, `goals`** do AI Profile no prompt?
- [ ] O AI Profile do usuário possui um playbook específico para `hybrid_scheduler` (agent_3)?
- [ ] O campo `temperature` duplicado em `followup_contract` pode ser removido?
- [ ] Os offsets e max_attempts precisam ser configuráveis pelo usuário via AI Profile?
