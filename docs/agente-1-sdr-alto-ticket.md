# Agente 1 — SDR Alto Ticket

> **Template:** `sdr_padrao`
> **Agent mode normalizado:** `agenda` (padrão) ou `consultivo` (se `human_in_loop` / `requires_handoff` estiver ativo)
> **Presentation variant:** `scheduler`

---

## 1. Variáveis cadastradas pelo usuário (onboarding)

Todas as variáveis abaixo são persistidas no modelo `AIProfile` do `backend-core`.

### Obrigatórias

| Variável | Descrição |
|---|---|
| `template_key` | `"sdr_padrao"` |
| `name` | Nome do bot/perfil |
| `brand_name` | Nome da empresa/marca |
| `tone_of_voice` | Tom de voz (ex: `"profissional e próximo"`) |
| `niche` | Nicho de atuação |
| `target_audience` | Descrição do público-alvo ideal |
| `offer_description` | Descrição textual da oferta (fallback quando não há `offer_pack`) |
| `goals` | Objetivos de negócio do usuário |

### Opcionais relevantes para o Agente 1

| Variável | Tipo | Descrição |
|---|---|---|
| `agent_mode` | `"sdr_scheduler" \| "agenda" \| "consultivo"` | Modo normalizado do agente |
| `presentation_variant` | `"scheduler"` | Tipo de apresentação (sempre scheduler no SDR) |
| `origin_inbound_opener` | string | Saudação customizada para leads inbound |
| `origin_outbound_opener` | string | Saudação customizada para leads outbound |
| `identity_mode` | `"human_agent" \| "virtual_assistant" \| "user_clone"` | Como o bot se apresenta |
| `handoff_policy` | `"disable_bot" \| "keep_active_notify" \| "ignore"` | O que fazer após handoff |
| `requires_handoff` | bool | Se verdadeiro, normaliza agent_mode para `consultivo` |
| `human_in_loop` | bool | Mesma implicação que `requires_handoff` |
| `custom_instructions` | string | Instruções extras injetadas no prompt |
| `objection_common` | string | Objeção mais comum do nicho para antecipar |
| `buying_signal_keywords` | lista | Keywords de alto interesse para detecção de intenção de compra |
| `qualification_score_threshold` | int | Score mínimo 4P para avançar da qualificação (padrão: `6/12`) |
| `nurture_vs_discard_rule` | `"discard" \| "nurture"` | O que fazer com leads de baixo score |
| `followup_cadence` | lista de minutos | Override da cadência padrão (padrão: `[24h, 72h, 168h]`) |
| `followup_max_attempts` | int | Limite máximo de tentativas (padrão: `3`) |
| `followup_allowed_hours` | objeto | Janela horária permitida para envio de follow-ups |
| `appointment_reminder_offsets` | lista de minutos | Quando enviar lembretes antes da reunião |
| `briefing_enabled` | bool | Envia briefing antes da sessão |
| `briefing_lead_time` | int | Minutos antes da reunião para enviar briefing (padrão: `120`) |
| `operator_whatsapp` | string | Número WhatsApp do operador para receber briefings |
| `calendar_integration` | `"none" \| "google" \| "hubspot"` | Integração de calendário |
| `timezone` | string | Fuso horário para ISO datetime do agendamento |

---

## 2. Fluxo por fase da pipeline

```
WhatsApp → UazAPI → POST /webhooks/whatsapp/inbound
  → inbound_handler.py
    → guardrail.py  (cria/promove lead, categoria inicial: "qualification")
    → build_context_bundle()
    → [EXECUTOR] decision_engine.py
        → Prompt Mãe  (rota: qualification | apresentation | follow-up | closing)
        → Prompt Filho (específico da rota)
        → apply_decision_engine()  (guardrails, sinais, categoria)
    → job enfileirado → backend-executors → UazAPI → WhatsApp
```

### Fase 1 — Qualificação

**Objetivo:** Coletar os campos obrigatórios para o modo `agenda`.

**Campos obrigatórios (modo `agenda`):**
```
service_interest | availability_window | location_preference | price_acceptance
```
_(Se `agent_mode` for `consultivo`, acrescentam-se: `urgency`, `decision_role`, `constraints`, `budget_or_price_acceptance` — total de 6 campos)_

**Regras e filtros:**
- A Mãe é forçada a rotear para `qualification` enquanto existirem `missing_fields`.
- A Filha só pode fazer **1 pergunta por turno** (`current_field`).
- A Filha não repete perguntas já feitas para o mesmo campo (histórico `asked_questions_json`, últimas 2 por campo, máx 20 total).
- A Filha nunca agenda reunião dentro da rota de qualificação (exceto se o lead pedir explicitamente).
- O campo `qualification_score_threshold` (padrão `6/12`) controla se o score 4P é suficiente para avançar.

**Score 4P (calculado em `qualification_state.py`):**
| Dimensão | Campo | Critério máx (3 pts) |
|---|---|---|
| Power | `decision_role` | "decisor", "sou eu" = 3 pts |
| Priority | `urgency` | "urgente", "agora" = 3 pts |
| Price | `budget_or_price_acceptance` | "sim", "ok", "topei" = 3 pts |
| Timing | `availability_window` | Dia/hora específico = 3 pts |

**Recursos utilizados:**
- `backend-crm/services/qualification_state.py` — leitura/escrita do estado 4P
- `backend-crm/services/qualification_guardrails.py` — validação para avançar de fase
- `backend-crm/services/field_extractor.py` — extração heurística de campos da conversa
- `backend-executors/app/services/decision_engine.py` — `_build_child_prompt_qualification()`

---

### Fase 2 — Apresentação (Agendamento)

**Objetivo:** Propor e confirmar um horário de reunião/call com o lead.

**Presentation variant:** `scheduler`

**Regras e filtros:**
- A Filha SEMPRE preenche `signals_structured.meeting_proposed` (bool) e `signals_structured.meeting_datetime_candidate` (ISO datetime ou null).
- Se houver proposta com horário definido: `meeting_proposed=true` + `meeting_datetime_candidate` preenchido.
- Se estiver pedindo disponibilidade sem horário fixo: `meeting_proposed=true` + `meeting_datetime_candidate=null`.
- Na confirmação final do agendamento: inclui `"meeting_scheduled"` na lista `signals`.
- Uma ação por turno: propor horário OU confirmar OU reagendar OU enviar link.
- Respeita `ai_profile.timezone` para formatar o datetime (ex: `2026-03-05T17:00:00`).
- O bot pode ser desabilitado automaticamente ao entrar na categoria `closing` se `meeting_scheduled=true` ou `agent_mode=agenda`.

**Recursos utilizados:**
- `backend-executors/app/services/decision_engine.py` — `_build_child_prompt_apresentation()`
- `backend-crm/services/meeting_scheduler.py` — criação de agendamento
- `backend-core/app/routes/appointments.py` — persistência do appointment
- `backend-crm/services/lead_category_policy.py` — side-effect de desabilitar bot

---

### Fase 3 — Follow-Up

**Objetivo:** Reengajar o lead após a apresentação caso não tenha fechado.

**Playbook:** `sdr_padrao`
**Variante de follow-up:** `sdr_scheduler`

**Cadência padrão:**
| Tentativa | Offset |
|---|---|
| 1 | 24 horas após a apresentação |
| 2 | 3 dias (72h) |
| 3 | 7 dias (168h) |

**Regra de entrada:** A Mãe só rota para `follow-up` se houver **evidência textual de apresentação realizada** no histórico (ex: "call de ontem", "como falamos na reunião") OU se `lead.category` já for `follow-up` ou `closing`.

**Tom e objetivo por variante (`sdr_scheduler`):**
> _"Follow-up consultivo pós-reunião; reforçar valor, síntese do contexto e próximo passo comercial."_

**Regras:**
- Máx 1 pergunta por mensagem.
- Em ticks automáticos (`whatsapp.followup.tick`): o histórico é memória contextual apenas — não reabrir campos de qualificação antigos.
- `missing_fields` da qualificação é read-only no tick de follow-up.
- `stop_followup_on_inbound_reply()` — o follow-up é pausado imediatamente quando o lead responde.

**Recursos utilizados:**
- `backend-crm/services/followup_state.py` — máquina de estado, scheduling
- `backend-crm/services/followup_reconciler.py` — reconciliação de estado
- `backend-executors/app/services/decision_engine.py` — `_build_child_prompt_follow_up()`
- Jobs do tipo `whatsapp.followup.tick`

---

### Fase 4 — Closing

**Objetivo:** Confirmar fechamento, coletar confirmação de pagamento ou assinar contrato.

**Modo `agenda`:** Fechamento operacional — confirmar horário, políticas e pagamento quando aplicável.
**Modo `consultivo`:** Não fecha sozinho — aciona guardrail e encaminha para humano.

**Guardrails de fechamento:**
- `consultivo`: `outcome="won"` é removido automaticamente; a mensagem é substituída por encaminhamento humano.
- `agenda`: Não pode avançar para closing se `availability_window` ou `location_preference` estiverem ausentes — retorna para qualificação.
- `kanban_highlight` e `outcome` só são emitidos quando `lead.category == "closing"`.

**Recursos utilizados:**
- `backend-executors/app/services/decision_engine.py` — `_build_child_prompt_closing()`
- `backend-crm/services/lead_category_policy.py` — desabilita bot ao entrar em closing
- `backend-executors/app/services/handoff_policy.py` — política de handoff

---

## 3. Estrutura dos prompts LLM

### 3.1 Prompt Mãe — Roteador

**Função:** `_build_mother_prompt()` em `decision_engine.py`

**Saída esperada (JSON):**
```json
{
  "route_to": "qualification|apresentation|follow-up|closing",
  "perceived_category": "qualification|apresentation|follow-up|closing|null",
  "confidence": 0.85,
  "reason": "curto",
  "agent_mode": null,
  "signals": {
    "meeting_scheduled": true,
    "intent_level": "low|medium|high",
    "urgency_level": "low|medium|high",
    "price_acceptance": "no|unsure|yes"
  },
  "objective": "string curta opcional",
  "next_action_hint": "reply|ask_qualification|handoff|ignore|null"
}
```

**Regras críticas injetadas no prompt:**
- `route_to` obrigatório.
- Se `missing_fields` não estiver vazio → `route_to` DEVE ser `"qualification"` (forçado pelo sistema mesmo se a LLM retornar outro valor).
- `meeting_scheduled=true` é sinal válido para o SDR quando confirmação de horário ocorre.
- `agent_mode` deve sempre ser `null` — o modo vem do perfil do sistema.
- Política SDR: se confirmação de horário/link fechado, `signals.meeting_scheduled=true` e string `"meeting_scheduled"` no `reason`.

**Contexto injetado no prompt:**
```
lead: {id, name, segment, status, category}
ai_profile: {id, name, template_key, tone_of_voice, niche, target_audience, agent_mode}
playbook: {template_key}
history: [últimas 10 mensagens no formato "role: body"]
agent_mode_normalized: "agenda"
required_fields: ["service_interest", "availability_window", "location_preference", "price_acceptance"]
missing_fields: [...campos ainda não coletados...]
lead_origin: "INBOUND (lead veio te procurar)"
origin_opener: "..."
inbound_message_text: "..."
```

---

### 3.2 Prompt Filho — Qualificação

**Função:** `_build_child_prompt_qualification()` em `decision_engine.py`

**Saída esperada (JSON):**
```json
{
  "question_text": "string — pergunta para o WhatsApp",
  "field": "service_interest|availability_window|location_preference|price_acceptance|null",
  "should_ask": true,
  "message_text": "string (retrocompat)",
  "did_complete_phase": false,
  "recommended_next_category": "apresentation|null",
  "outcome": null,
  "kanban_highlight": null,
  "signals": ["..."],
  "signals_structured": {"missing_fields": ["..."], "handoff_requested": false},
  "confidence": 0.0
}
```

**Regras críticas:**
- Só 1 pergunta por turno.
- `field` deve ser EXATAMENTE o `current_field` quando `should_ask=true`.
- Reformular se a pergunta for similar a alguma já feita para esse campo (`asked_questions_for_current_field`).
- NÃO agendar reunião (só na rota `apresentation`).
- `outcome` e `kanban_highlight` são sempre `null`.

**Contexto adicional injetado:**
```
current_field: "service_interest"  ← próximo campo a coletar
asked_questions_for_current_field: [...]  ← últimas 2 perguntas já feitas para esse campo
last_question_text: "..."
```

---

### 3.3 Prompt Filho — Apresentação (Scheduler)

**Função:** `_build_child_prompt_apresentation()` em `decision_engine.py`

**Saída esperada (JSON):**
```json
{
  "message_text": "string",
  "did_complete_phase": false,
  "recommended_next_category": null,
  "outcome": null,
  "kanban_highlight": null,
  "signals": ["meeting_scheduled"],
  "signals_structured": {
    "meeting_proposed": true,
    "meeting_datetime_candidate": "2026-03-10T17:00:00",
    "offer_presented": false,
    "checkout_sent": false,
    "presentation_variant": "scheduler"
  },
  "confidence": 0.85
}
```

**Regras críticas:**
- `presentation_variant=scheduler`: conduzir agendamento (proposta → confirmação → link).
- SEMPRE preencher `meeting_proposed` e `meeting_datetime_candidate`.
- Respeitar `ai_profile.timezone` para formato ISO.
- Incluir `"meeting_scheduled"` em `signals` na confirmação final.

---

### 3.4 Prompt Filho — Follow-Up (`sdr_scheduler`)

**Função:** `_build_child_prompt_follow_up()` em `decision_engine.py`

**Instrução de variante injetada no prompt:**
> _"Variante sdr_scheduler: follow-up consultivo pós-reunião; reforçar valor, síntese do contexto e próximo passo comercial."_

**Saída esperada (JSON):**
```json
{
  "message_text": "string",
  "did_complete_phase": false,
  "recommended_next_category": "follow-up|closing|null",
  "outcome": null,
  "kanban_highlight": null,
  "signals": ["..."],
  "confidence": 0.0
}
```

**Contexto adicional (`followup_contract_signals`):**
```json
{
  "followup_goal": "standard",
  "outcome": null,
  "followup_variant": "sdr_scheduler",
  "attempts": 1,
  "max_attempts": 3,
  "meeting_happened": true,
  "proposal_sent": false,
  "operator_note": "..."
}
```

---

### 3.5 Prompt Filho — Closing

**Função:** `_build_child_prompt_closing()` em `decision_engine.py`

**Regra por modo:**
- `agenda`: Fechamento operacional — confirmar horário, políticas e pagamento.
- `consultivo`: Não fechar sozinho — resposta curta e encaminhamento humano.

**Saída esperada (JSON):**
```json
{
  "message_text": "string",
  "did_complete_phase": false,
  "recommended_next_category": "closing|null",
  "outcome": "won|lost|null",
  "kanban_highlight": "green|orange|null",
  "signals": ["..."],
  "confidence": 0.0
}
```

---

## 4. Guardrails e filtros transversais

| Guardrail | Regra |
|---|---|
| **missing_fields → qualification** | Se `missing_fields` não vazio, `route_to` é forçado para `qualification` pelo sistema |
| **agenda sem booking** | Se `availability_window` ou `location_preference` faltam ao tentar avançar para `closing`, retorna para `qualification` |
| **consultivo sem closing solo** | `outcome="won"` é removido; handoff para humano |
| **kanban_highlight/outcome** | Só emitidos quando `lead.category == "closing"` |
| **bot_disabled** | Desabilitado automaticamente ao entrar em `closing` se `meeting_scheduled=true` ou `agent_mode=agenda` |
| **quota de conversas** | Verificada no `inbound_handler.py` (limite mensal por usuário) |
| **short reply** | Se mensagem ≤12 chars e sem espaço, injeta `short_reply_hint` no prompt para responder em contexto |
| **follow-up tick** | `missing_fields` é read-only; não reabrir qualificação no follow-up automático |

---

## 5. Resumo do fluxo completo

```
1. Lead entra via WhatsApp (inbound) ou é criado (outbound)
   └─ Categoria inicial: "qualification"

2. Qualificação (4 campos para modo agenda)
   ├─ Mãe rota para "qualification"
   ├─ Filha pergunta 1 campo por turno
   ├─ Score 4P calculado a cada resposta
   └─ Score ≥ threshold → libera avanço

3. Apresentação (agendamento)
   ├─ Mãe rota para "apresentation"
   ├─ Filha propõe horário (meeting_proposed=true)
   ├─ Lead confirma → meeting_datetime_candidate preenchido
   └─ Sinal "meeting_scheduled" emitido

4. Follow-up (se lead não fechou após a reunião)
   ├─ Job "whatsapp.followup.tick" dispara em 24h → 72h → 168h
   ├─ Mãe rota para "follow-up"
   └─ Filha reforça valor e propõe próximo passo

5. Closing
   ├─ Mãe rota para "closing"
   ├─ Bot desabilitado (modo agenda / meeting confirmado)
   └─ Operador humano assume ou lead confirma pagamento
```
