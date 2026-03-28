# Agente 3 — Híbrido (Hybrid Scheduler)

> **Template:** `hybrid_scheduler` / `hybrid_scheduler_followup`
> **Agent mode normalizado:** `agenda`
> **Presentation variant:** `scheduler` (sempre)
> **Perfil típico:** Coaches, terapeutas, consultores solo, profissionais liberais

---

## 1. Variáveis cadastradas pelo usuário (onboarding)

Todas as variáveis abaixo são persistidas no modelo `AIProfile` do `backend-core`.

### Obrigatórias

| Variável | Descrição |
|---|---|
| `template_key` | `"hybrid_scheduler"` |
| `name` | Nome do bot/perfil |
| `brand_name` | Nome da empresa/marca ou nome do profissional |
| `tone_of_voice` | Tom de voz (ex: `"pessoal e próximo"`) |
| `niche` | Nicho de atuação (ex: `"coaching executivo"`) |
| `target_audience` | Descrição do público-alvo ideal |
| `offer_description` | Descrição textual da oferta/serviço |
| `goals` | Objetivos de negócio |

### Opcionais relevantes para o Agente 3

| Variável | Tipo | Descrição |
|---|---|---|
| `agent_mode` | `"sdr_scheduler" \| "agenda"` | Modo do agente (normalizado para `agenda`) |
| `presentation_variant` | `"scheduler"` | Sempre scheduler — não alterar |
| `hybrid_flow_style` | `"offer_then_schedule" \| "schedule_then_offer"` | Ordem: oferta antes do agendamento ou ao contrário |
| `warming_social_proof` | string | Prova social customizada usada no estágio de aquecimento |
| `warming_session_preview` | string | Prévia da sessão customizada usada no estágio de aquecimento |
| `offer_pack` | JSON | Pacote de oferta estruturada (se quiser enviar link/preço após a sessão) |
| `origin_inbound_opener` | string | Saudação customizada para leads inbound |
| `origin_outbound_opener` | string | Saudação customizada para leads outbound |
| `identity_mode` | `"human_agent" \| "virtual_assistant" \| "user_clone"` | Como o bot se apresenta |
| `handoff_policy` | `"disable_bot" \| "keep_active_notify" \| "ignore"` | O que fazer após handoff |
| `custom_instructions` | string | Instruções extras injetadas no prompt |
| `objection_common` | string | Objeção mais comum do nicho |
| `qualification_score_threshold` | int | Score mínimo 4P para avançar (padrão: `6/12`) |
| `nurture_vs_discard_rule` | `"discard" \| "nurture"` | O que fazer com leads de baixo score |
| `followup_cadence` | lista de minutos | Override da cadência padrão (padrão: `[1440, 2880]` = 24h, 48h) |
| `followup_max_attempts` | int | Limite de tentativas de follow-up |
| `followup_allowed_hours` | objeto | Janela horária permitida para envio de follow-ups |
| `appointment_reminder_offsets` | lista de minutos | Quando enviar lembretes antes da sessão |
| `briefing_enabled` | bool | Envia briefing antes da sessão para o operador |
| `briefing_lead_time` | int | Minutos antes da sessão para enviar briefing (padrão: `120`) |
| `briefing_channel` | string | Canal de envio do briefing |
| `operator_whatsapp` | string | WhatsApp do profissional para receber briefings |
| `calendar_integration` | `"none" \| "google" \| "hubspot"` | Integração de calendário |
| `timezone` | string | Fuso horário para ISO datetime do agendamento |

### Defaults de aquecimento (quando não customizados pelo usuário)

```python
DEFAULT_SOCIAL_PROOF = (
    "Um profissional com o seu perfil já utilizou essa abordagem e conseguiu resultados expressivos. "
    "Posso te contar mais detalhes na nossa conversa."
)
DEFAULT_SESSION_PREVIEW = (
    "Na sessão de aproximadamente 1h, vamos mapear sua situação atual, identificar os principais pontos de melhoria "
    "e sair com um plano de ação claro para você."
)
```

---

## 2. Fluxo por fase da pipeline

```
WhatsApp → UazAPI → POST /webhooks/whatsapp/inbound
  → inbound_handler.py
    → guardrail.py  (cria/promove lead, categoria inicial: "qualification")
    → build_context_bundle()
    → [EXECUTOR] decision_engine.py
        → Prompt Mãe  (rota: qualification | apresentation | follow-up | closing)
        → Prompt Filho (específico da rota, com estágio de warming para Agent 3)
        → apply_decision_engine()  (guardrails, sinais, categoria)
    → job enfileirado → backend-executors → UazAPI → WhatsApp

[Após sessão acontecer]
    → followup_state.py (variante: hybrid_scheduler)
        → Jobs "whatsapp.followup.tick" (24h → 48h)
        → Outcome: interested_not_closed | reschedule_needed | converted
```

---

### Fase 1 — Qualificação

**Objetivo:** Coletar os campos mínimos necessários para propor agendamento de sessão.

**Campos obrigatórios (modo `agenda` para hybrid_scheduler):**
```
service_interest | availability_window | location_preference | price_acceptance
```

**Regras e filtros:**
- A Mãe é forçada a rotear para `qualification` enquanto existirem `missing_fields`.
- A Filha só pode fazer **1 pergunta por turno** (`current_field`).
- Evita repetir perguntas já feitas para o mesmo campo (histórico `asked_questions_json`).
- Tom: `"pessoal e próximo, como assistente do próprio profissional — nunca SDR agressivo"`.
- `max_chars=400` — respostas um pouco mais ricas que o SDR padrão.

**Score 4P (calculado em `qualification_state.py`):**
| Dimensão | Campo | Critério máx (3 pts) |
|---|---|---|
| Power | `decision_role` | Não obrigatório neste modo |
| Priority | `urgency` | Não obrigatório neste modo |
| Price | `price_acceptance` | "sim", "ok", "topei" = 3 pts |
| Timing | `availability_window` | Dia/hora específico = 3 pts |

**Recursos utilizados:**
- `backend-crm/services/qualification_state.py`
- `backend-crm/services/qualification_guardrails.py`
- `backend-executors/app/services/decision_engine.py` — `_build_child_prompt_qualification()`

---

### Fase 2 — Aquecimento (Warming Stage) ← exclusivo do Agente 3

**Objetivo:** Construir confiança e valor imediatamente após a qualificação ser aprovada, antes de propor o agendamento.

**Trigger:**
- `template_key == "hybrid_scheduler"` AND
- `mother_decision.route_to == "qualification"` AND
- `missing_fields` está vazio (qualificação recém-aprovada)

**Execução — 2 passos em 1 única mensagem:**

1. **Prova Social** (`warming_social_proof` ou default):
   > _"Um profissional com o seu perfil já utilizou essa abordagem e conseguiu resultados expressivos."_

2. **Prévia da Sessão** (`warming_session_preview` ou default):
   > _"Na sessão de ~1h, vamos mapear sua situação atual, identificar os principais pontos de melhoria e sair com um plano de ação claro para você."_

3. Ao final da mensagem: propor o agendamento da sessão.

**Regras:**
- Os 2 passos devem ser combinados de forma **fluida e natural** — nunca mencionar os termos `"prova social"` ou `"prévia da sessão"` explicitamente.
- É 1 mensagem completa (não 2 separadas).
- O warming é injetado como instrução adicional no prompt filho `apresentation` via `warming_injection`.

**Recursos utilizados:**
- `backend-crm/services/ai_playbooks/__init__.py` — `DEFAULT_SOCIAL_PROOF`, `DEFAULT_SESSION_PREVIEW`, playbook `"hybrid_scheduler"`
- `backend-executors/app/services/decision_engine.py` — `_build_child_prompt_apresentation()` com `warming_injection`

---

### Fase 3 — Apresentação (Agendamento de Sessão)

**Objetivo:** Propor, confirmar e gerenciar o agendamento da sessão/reunião.

**Presentation variant:** `scheduler`

**Hybrid Flow Style (configurável pelo usuário):**
| Estilo | Comportamento |
|---|---|
| `offer_then_schedule` | Apresenta detalhes do serviço/precificação primeiro; depois solicita agendamento |
| `schedule_then_offer` | Agenda a sessão primeiro; a oferta/fechamento acontece dentro da sessão |

**Regras e filtros:**
- A Filha SEMPRE preenche `signals_structured.meeting_proposed` e `signals_structured.meeting_datetime_candidate`.
- Se proposta/confirmação com horário: `meeting_proposed=true` + `meeting_datetime_candidate` (ISO datetime).
- Se pedindo disponibilidade sem horário: `meeting_proposed=true` + `meeting_datetime_candidate=null`.
- Respeita `ai_profile.timezone` para formato ISO (ex: `2026-03-10T17:00:00`).
- Na confirmação final: inclui `"meeting_scheduled"` em `signals`.
- O bot pode ser desabilitado automaticamente ao entrar em `closing` com `meeting_scheduled=true`.

**Briefing (se `briefing_enabled=true`):**
- Enviado `briefing_lead_time` minutos antes da sessão (padrão: 120min).
- Enviado para `operator_whatsapp` com detalhes da sessão.

**Recursos utilizados:**
- `backend-executors/app/services/decision_engine.py` — `_build_child_prompt_apresentation()`
- `backend-crm/services/meeting_scheduler.py` — criação de agendamento
- `backend-core/app/routes/appointments.py` — persistência do appointment
- `backend-crm/services/lead_category_policy.py` — side-effect de desabilitar bot

---

### Fase 4 — Follow-Up Pós-Sessão

**Objetivo:** Retomar contato após a sessão realizada, com base no outcome específico.

**Playbook:** `hybrid_scheduler_followup`
**Variante de follow-up:** `hybrid_scheduler`

**Cadência padrão:**
| Tentativa | Offset |
|---|---|
| 1 | 24 horas após a sessão/auto-envio |
| 2 | 48 horas após tentativa 1 |

**3 ramificações por outcome:**

#### `interested_not_closed` — Lead teve a sessão mas não fechou
**Instrução injetada no prompt:**
> _"Tom de continuidade: retome o contexto da sessão anterior, remova a objeção específica que foi levantada e ofereça uma nova data concreta para avançar."_

#### `reschedule_needed` — Lead não compareceu ou pediu remarcação
**Instrução injetada no prompt:**
> _"Tom leve e sem pressão: o lead não compareceu ou pediu remarcação. Ofereça 2-3 horários diretamente e encerre com uma pergunta fechada."_

#### `converted` — Lead fechou / comprou
**Instrução injetada no prompt:**
> _"Tom de onboarding e boas-vindas: parabenize, confirme o próximo passo, envie link de pagamento ou instrução de acesso. Não reabra vendas."_

**Regras gerais:**
- Tom sempre pessoal e próximo — nunca SDR agressivo.
- Em ticks automáticos: `missing_fields` da qualificação é read-only — não reabrir perguntas antigas.
- `stop_followup_on_inbound_reply()` — follow-up pausado imediatamente quando o lead responde.
- Follow-up de `converted` nunca reabre o processo de vendas.

**Recursos utilizados:**
- `backend-crm/services/followup_state.py` — `progress_followup_after_auto_send()`, `stop_followup_on_inbound_reply()`
- `backend-executors/app/services/decision_engine.py` — `_build_child_prompt_follow_up()` com variante `hybrid_scheduler`
- Jobs do tipo `whatsapp.followup.tick`

---

### Fase 5 — Closing

**Objetivo:** Confirmar fechamento após a sessão ou diretamente (se `offer_then_schedule`).

**Modo `agenda`:** Fechamento operacional — confirmar próximos passos, pagamento e acesso.

**Guardrails de fechamento:**
- Não pode avançar para `closing` se `availability_window` ou `location_preference` estiverem ausentes — retorna para `qualification` (`guardrail_agenda_missing_booking`).
- `kanban_highlight` e `outcome` só são válidos quando `lead.category == "closing"`.
- Bot desabilitado automaticamente ao entrar em `closing`.

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
  "reason": "qualificação concluída, pronto para agendar",
  "agent_mode": null,
  "signals": {
    "meeting_scheduled": true,
    "intent_level": "medium",
    "urgency_level": "medium",
    "price_acceptance": "yes"
  },
  "objective": "agendar sessão",
  "next_action_hint": "reply"
}
```

**Regras específicas para o Híbrido injetadas no prompt:**
- `meeting_scheduled=true` é válido quando confirmação de horário ocorre.
- Política `agenda`: foco em vender até booking e confirmar presença.
- `route_to=apresentation` inclui: agendar, confirmar horário, reagendar, pedir link.
- `follow-up` somente após evidência de apresentação/sessão realizada.

**Contexto injetado no prompt:**
```
lead: {id, name, segment, status, category}
ai_profile: {id, name, template_key: "hybrid_scheduler", tone_of_voice, niche, target_audience, agent_mode}
history: [últimas 10 mensagens]
agent_mode_normalized: "agenda"
required_fields: ["service_interest", "availability_window", "location_preference", "price_acceptance"]
missing_fields: [...campos ainda não coletados...]
inbound_message_text: "..."
```

---

### 3.2 Prompt Filho — Qualificação

**Função:** `_build_child_prompt_qualification()` em `decision_engine.py`

**Saída esperada (JSON):**
```json
{
  "question_text": "string — pergunta pessoal e próxima",
  "field": "service_interest|availability_window|location_preference|price_acceptance|null",
  "should_ask": true,
  "message_text": "string",
  "did_complete_phase": false,
  "recommended_next_category": "apresentation|null",
  "outcome": null,
  "kanban_highlight": null,
  "signals": ["..."],
  "confidence": 0.0
}
```

**Tom diferencial vs Agente 1:** Pessoal e próximo — como um assistente do próprio profissional, não como SDR.

---

### 3.3 Prompt Filho — Apresentação com Warming

**Função:** `_build_child_prompt_apresentation()` em `decision_engine.py`

**Instrução de warming injetada (quando `warming_stage_active=true`):**
```
ESTÁGIO WARMING (pós-qualificação aprovada para hybrid_scheduler):
O lead acabou de concluir a qualificação. Antes de propor o agendamento, execute os 2 passos de aquecimento em UMA mensagem natural:
  1. PROVA SOCIAL: [warming_social_proof ou DEFAULT_SOCIAL_PROOF]
  2. PRÉVIA DA SESSÃO: [warming_session_preview ou DEFAULT_SESSION_PREVIEW]
Combine os 2 passos de forma fluida e, ao final, proponha o agendamento da sessão.
Não mencione os termos 'prova social' ou 'prévia da sessão' explicitamente — use linguagem natural.
```

**Saída esperada — Turno de Warming + Agendamento:**
```json
{
  "message_text": "Um profissional com o seu perfil já conseguiu resultados expressivos com essa abordagem — posso te contar mais detalhes na nossa conversa. Na sessão de ~1h, vamos mapear sua situação atual e sair com um plano claro. Qual o melhor horário para você esta semana?",
  "did_complete_phase": false,
  "recommended_next_category": null,
  "outcome": null,
  "kanban_highlight": null,
  "signals": [],
  "signals_structured": {
    "meeting_proposed": true,
    "meeting_datetime_candidate": null,
    "offer_presented": false,
    "checkout_sent": false,
    "presentation_variant": "scheduler"
  },
  "confidence": 0.8
}
```

**Saída esperada — Confirmação de horário:**
```json
{
  "message_text": "Perfeito! Confirmo sua sessão para terça às 17h. Vou te enviar o link em breve.",
  "signals": ["meeting_scheduled"],
  "signals_structured": {
    "meeting_proposed": true,
    "meeting_datetime_candidate": "2026-04-01T17:00:00",
    "presentation_variant": "scheduler"
  },
  "confidence": 0.9
}
```

**Contexto adicional injetado:**
```
presentation_variant: "scheduler"
hybrid_flow_style: "offer_then_schedule" | "schedule_then_offer" | ""
warming_stage_active: true | false
offer_pack_summary: {available: ..., items: [...], ...}
ai_profile.timezone: "America/Sao_Paulo"
```

---

### 3.4 Prompt Filho — Follow-Up (Hybrid Scheduler)

**Função:** `_build_child_prompt_follow_up()` com variante `hybrid_scheduler` em `decision_engine.py`

**Instrução dinâmica por outcome injetada no prompt:**

```
Variante hybrid_scheduler (coaches/terapeutas/consultores solo):
tom pessoal e próximo, como assistente do próprio profissional — nunca SDR agressivo.
Regra por outcome ([interested_not_closed|reschedule_needed|converted]):
  [instrução específica do outcome]
```

**Saída esperada para `interested_not_closed`:**
```json
{
  "message_text": "Oi [nome], que bom te ter na sessão! Percebo que ficou com dúvida sobre [objeção]. Que tal agendarmos um novo momento para resolver isso juntos? Tenho terça e quinta disponíveis.",
  "recommended_next_category": "follow-up",
  "outcome": null,
  "confidence": 0.8
}
```

**Saída esperada para `reschedule_needed`:**
```json
{
  "message_text": "Oi [nome]! Notei que não nos encontramos na sessão de hoje. Tudo bem por aí? Tenho estes horários disponíveis: terça às 10h, quarta às 15h ou quinta às 17h. Qual funciona melhor?",
  "recommended_next_category": "follow-up",
  "outcome": null,
  "confidence": 0.75
}
```

**Saída esperada para `converted`:**
```json
{
  "message_text": "Parabéns pela sua decisão! Aqui está o link para formalizar: https://pay.exemplo.com/sessao. Após a confirmação, te envio os próximos passos.",
  "recommended_next_category": "closing",
  "outcome": null,
  "confidence": 0.9
}
```

**Contexto adicional (`followup_contract_signals`):**
```json
{
  "followup_goal": "standard",
  "outcome": "interested_not_closed",
  "followup_variant": "hybrid_scheduler",
  "attempts": 1,
  "max_attempts": 2,
  "meeting_or_session_happened": true,
  "proposal_sent": false,
  "operator_note": "Lead levantou objeção de preço na sessão"
}
```

**Regras específicas do tick automático (`is_followup_tick=true`):**
```
CONTEXTO PRIORITÁRIO (follow-up tick):
- use followup_contract_signals como fonte principal da resposta
- qualification_state e missing_fields são SOMENTE memória auxiliar (read-only)
- É proibido usar missing_fields de qualification como alvo de coleta/pergunta
- O histórico é memória contextual; não é backlog de perguntas pendentes
- Só retome algo do histórico se estiver diretamente necessário para o objetivo do follow-up atual
```

---

### 3.5 Prompt Filho — Closing

**Função:** `_build_child_prompt_closing()` em `decision_engine.py`

**Regra por modo (`agenda`):**
> _"Fechamento operacional — confirmar horário, políticas e pagamento quando aplicável."_

**Saída esperada (JSON):**
```json
{
  "message_text": "Ótimo! Após a confirmação do pagamento, te envio os materiais e acesso para nossa próxima sessão.",
  "did_complete_phase": true,
  "recommended_next_category": "closing",
  "outcome": "won",
  "kanban_highlight": "green",
  "signals": ["payment_confirmed"],
  "confidence": 0.9
}
```

---

## 4. Guardrails e filtros transversais

| Guardrail | Regra |
|---|---|
| **missing_fields → qualification** | Enquanto `missing_fields` não vazio, `route_to` é forçado para `qualification` |
| **agenda sem booking** | Se `availability_window` ou `location_preference` faltam ao tentar avançar para `closing`, retorna para `qualification` (`guardrail_agenda_missing_booking`) |
| **warming só no hybrid_scheduler** | A injeção de warming só acontece quando `template_key == "hybrid_scheduler"` E `missing_fields` vazio |
| **follow-up somente após evidência** | `follow-up` exige evidência textual de sessão realizada ou `lead.category` já sendo `follow-up/closing` |
| **tick read-only** | Em `whatsapp.followup.tick`, `missing_fields` é read-only — proibido reabrir qualificação |
| **converted não reativa vendas** | Outcome `converted` jamais reabre processo de vendas |
| **bot_disabled no closing** | Desabilitado automaticamente ao entrar em `closing` |
| **kanban_highlight/outcome** | Só emitidos quando `lead.category == "closing"` |
| **follow-up pausado por resposta** | `stop_followup_on_inbound_reply()` para a cadência quando o lead responde |
| **meeting_scheduled signal** | Incluído em `signals` na confirmação final do agendamento para compatibilidade |

---

## 5. Resumo do fluxo completo

```
1. Lead entra via WhatsApp (inbound)
   └─ Categoria inicial: "qualification"

2. Qualificação (4 campos: service_interest, availability_window, location_preference, price_acceptance)
   ├─ Mãe rota para "qualification"
   ├─ Filha pergunta 1 campo por turno (tom pessoal e próximo)
   └─ Score ≥ threshold → libera avanço

3. Aquecimento (Warming Stage — exclusivo do Agente 3)
   ├─ Trigger: qualificação recém-aprovada (missing_fields vazio)
   ├─ Filha recebe instrução de warming no prompt de apresentation
   ├─ 1 mensagem: Prova Social + Prévia da Sessão + Proposta de Agendamento
   └─ Linguagem natural — sem mencionar "prova social" ou "prévia da sessão"

4. Apresentação (Agendamento)
   ├─ Mãe rota para "apresentation"
   ├─ Filha propõe horário (meeting_proposed=true)
   ├─ Lead confirma → meeting_datetime_candidate preenchido
   ├─ Sinal "meeting_scheduled" emitido
   └─ Briefing enviado ao operador se briefing_enabled=true

5. Sessão acontece (operador realiza a sessão)
   └─ Operador registra outcome: interested_not_closed | reschedule_needed | converted

6. Follow-up Pós-Sessão (hybrid_scheduler)
   ├─ Tentativa 1 (+24h): mensagem personalizada por outcome
   └─ Tentativa 2 (+48h): follow-up adicional se necessário

7. Closing
   ├─ Lead confirma → outcome="won"
   ├─ Bot desabilitado imediatamente
   └─ Onboarding: link de pagamento ou instrução de acesso
```

---

## 6. Diferenças-chave vs Agentes 1 e 2

| Dimensão | Agente 1 (SDR) | Agente 2 (Closer) | Agente 3 (Híbrido) |
|---|---|---|---|
| **Template** | `sdr_padrao` | `closer_agressivo` | `hybrid_scheduler` |
| **Campos de qualificação** | 4 (agenda) / 6 (consultivo) | 3 | 4 |
| **Tom** | Profissional e equilibrado | Direto e objetivo | Pessoal e próximo |
| **Warming Stage** | Não | Não | Sim (prova social + prévia) |
| **Presentation variant** | Scheduler | Sales (2 turnos) | Scheduler |
| **Follow-up variante** | `sdr_scheduler` (até 7 dias) | `cart_recovery` (até 48h) | `hybrid_scheduler` (24h + 48h) |
| **Outcomes de follow-up** | Padrão | Neutro / Benefício / Urgência | interested_not_closed / reschedule_needed / converted |
| **Closing autônomo** | Condicional (agenda) / Handoff (consultivo) | Direto | Condicional (agenda) |
| **max_chars** | 350 | 350 (recovery: 280) | 400 |
