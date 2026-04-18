# Agente 2 — Closer Agressivo

> **Template:** `closer_agressivo` / `closer_agressivo_cart_recovery`
> **Agent mode normalizado:** `direto`
> **Presentation variant:** `sales`

---

## 1. Variáveis cadastradas pelo usuário (onboarding)

Todas as variáveis abaixo são persistidas no modelo `AIProfile` do `backend-core`.

### Obrigatórias

| Variável | Descrição |
|---|---|
| `template_key` | `"closer_agressivo"` |
| `name` | Nome do bot/perfil |
| `brand_name` | Nome da empresa/marca |
| `tone_of_voice` | Tom de voz (ex: `"direto e objetivo"`) |
| `niche` | Nicho de atuação |
| `target_audience` | Descrição do público-alvo ideal |
| `offer_description` | Descrição textual da oferta (fallback quando não há `offer_pack`) |
| `goals` | Objetivos de negócio do usuário |

### Opcionais relevantes para o Agente 2

| Variável | Tipo | Descrição |
|---|---|---|
| `agent_mode` | `"closer" \| "direto"` | Modo do closer (normalizado para `direto`) |
| `presentation_variant` | `"sales"` | Tipo de apresentação (sempre `sales` no closer) |
| `offer_pack` | JSON | Pacote de oferta estruturada (obrigatório para envio de link) |
| `origin_inbound_opener` | string | Saudação customizada para leads inbound |
| `origin_outbound_opener` | string | Saudação customizada para leads outbound |
| `identity_mode` | `"human_agent" \| "virtual_assistant" \| "user_clone"` | Como o bot se apresenta |
| `handoff_policy` | `"disable_bot" \| "keep_active_notify" \| "ignore"` | O que fazer após handoff |
| `custom_instructions` | string | Instruções extras injetadas no prompt |
| `objection_common` | string | Objeção mais comum do nicho para antecipar |
| `buying_signal_keywords` | lista | Keywords de alto interesse para detecção de intenção |
| `qualification_score_threshold` | int | Score mínimo 4P para avançar da qualificação (padrão: `6/12`) |
| `nurture_vs_discard_rule` | `"discard" \| "nurture"` | O que fazer com leads de baixo score |
| `payment_gateway` | `"stripe" \| "whatsapp_pay"` | Gateway de pagamento integrado |
| `timezone` | string | Fuso horário do negócio |

### Estrutura do `offer_pack` (JSON)

Campo central do Closer — define o produto a ser vendido diretamente no WhatsApp:

```json
{
  "items": [
    {
      "name": "Plano Pro",
      "price": "R$997",
      "description": "Acesso completo à plataforma por 12 meses",
      "bullets": ["Suporte 24h", "Treinamento incluso", "Sem fidelidade"],
      "proof": ["200 clientes ativos", "NPS 9.2"],
      "faq": ["Posso cancelar? Sim, a qualquer momento."],
      "checkout_link": "https://pay.exemplo.com/plano-pro"
    }
  ],
  "cta_text": "Garanta agora com desconto",
  "disclaimers": ["Oferta válida até hoje"],
  "media_url": "https://cdn.exemplo.com/oferta.jpg",
  "media_type": "image",
  "anchor_price": "R$1.497",
  "guarantee_text": "7 dias de garantia incondicional",
  "upsell_message": "Adicione o módulo avançado por mais R$197"
}
```

**Obs.:** Máximo de 3 itens. A mídia (`media_url`) é enviada automaticamente antes do texto pelo executor — não mencionar "veja a imagem" no message_text.

---

## 2. Fluxo por fase da pipeline

```
WhatsApp → UazAPI → POST /webhooks/whatsapp/inbound
  → inbound_handler.py
    → guardrail.py  (cria/promove lead, categoria inicial: "qualification")
    → build_context_bundle()
    → [EXECUTOR] decision_engine.py
        → Prompt Mãe  (rota: qualification | apresentation | closing)
        → Prompt Filho (específico da rota)
        → apply_decision_engine()  (guardrails, sinais, categoria)
    → job enfileirado → backend-executors → UazAPI → WhatsApp

[Se oferta enviada e sem fechamento]
    → start_cart_recovery_followup()
        → Jobs "whatsapp.followup.tick" (2h → 24h → 48h)
```

### Fase 1 — Qualificação (Mínima)

**Objetivo:** Coletar apenas os campos mínimos para avançar ao pitch — sem perguntas desnecessárias.

**Campos obrigatórios (modo `direto`):**
```
service_interest | availability_window | price_acceptance
```

**Regras e filtros:**
- A Mãe é forçada a rotear para `qualification` enquanto existirem `missing_fields`.
- A Filha pergunta 1 campo por turno.
- Com apenas 3 campos, o closer qualifica mais rápido que os outros agentes.
- Guardrail de fechamento: `price_acceptance="yes"` E `intent_level="medium|high"` são obrigatórios para avançar para `closing` — se ausentes, retorna para `qualification`.
- O playbook `closer_agressivo` usa tom `"direct"` com `max_chars=350`.

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

### Fase 2 — Apresentação (Pitch Direto / Venda)

**Objetivo:** Apresentar a oferta e levar o lead ao pagamento em no máximo 2 turnos.

**Presentation variant:** `sales`

**Regras de 2 turnos (UM TURNO = UMA AÇÃO):**

**Turno 1 — CONFIRMAR (sem link):**
- Descreve a oferta (nome, preço, benefícios principais).
- Pergunta confirmação: `"quer seguir?"` ou similar.
- `signals_structured.checkout_sent = false`.
- **Proibido:** incluir URL real ou placeholder de link neste turno.
- Se `anchor_price` estiver preenchido: usar preço âncora (`"De R$1.497 por apenas R$997"`).
- Se `guarantee_text` estiver preenchido: incluir na mensagem.

**Turno 2 — ENVIAR LINK (com link):**
- Oferta curta + link real de checkout + próximo passo (`"conclua e me confirme"`).
- `signals_structured.checkout_sent = true`.
- **Proibido:** pedir permissão para enviar o link neste turno (não usar `"posso enviar o link?"` junto com checkout_sent=true).

**Guardrail de consistência obrigatória:**
- Se houver pergunta de confirmação no turno → `checkout_sent=false`, sem link.
- Se `checkout_sent=true` → link incluído, sem pedido de permissão.

**Fluxo pós-link:**
- Se o lead fechar → `outcome="won"`, lead vai para `closing`, bot desabilitado.
- Se o lead não responder → após 2h inicia `cart_recovery` (ver Fase 3).

**Recursos utilizados:**
- `backend-executors/app/services/decision_engine.py` — `_build_child_prompt_apresentation()`
- `backend-crm/services/lead_category_policy.py` — desabilita bot ao entrar em closing
- `backend-crm/services/followup_state.py` — `start_cart_recovery_followup()`

---

### Fase 3 — Cart Recovery (Follow-Up Pós-Oferta)

**Objetivo:** Recuperar o pagamento de quem recebeu o link mas não converteu.

**Playbook:** `closer_agressivo_cart_recovery`
**Variante de follow-up:** `cart_recovery`

**Cadência:**
| Tentativa | Offset | Tom |
|---|---|---|
| 1 | 2 horas após envio do link | `neutral_reminder` |
| 2 | 24 horas após tentativa 1 | `benefit_objection` |
| 3 | 48 horas após tentativa 2 | `urgency` |

**Instrução por tentativa (injetada no prompt filho):**

**Tentativa 1 — `neutral_reminder`:**
> _"Lembrete neutro: o pedido está reservado e o link ainda está disponível. Sem pressão — apenas informa e pergunta se há alguma dúvida que impeça o pagamento."_

**Tentativa 2 — `benefit_objection`:**
> _"Reforce o benefício principal do produto/serviço e antecipe a objeção mais comum do nicho. Tom amigável, resolva a dúvida que está impedindo o pagamento."_

**Tentativa 3 — `urgency`:**
> _"Urgência máxima: a oferta expira hoje. CTA direto para o link de pagamento. Não reabra qualificação."_

**Regras:**
- Mensagens curtas: `max_chars=280`.
- `stop_followup_on_inbound_reply()` — interrompido imediatamente se o lead responder.
- Após 3 tentativas sem resposta: `stop_reason="max_attempts_reached"`.
- Não há follow-up multi-semana no Closer — ou converte na recovery ou descarta.

**Recursos utilizados:**
- `backend-crm/services/followup_state.py` — `start_cart_recovery_followup()`, `progress_followup_after_auto_send()`
- `backend-executors/app/services/decision_engine.py` — `_build_child_prompt_follow_up()` com variante `cart_recovery`
- Jobs do tipo `whatsapp.followup.tick`

---

### Fase 4 — Closing

**Objetivo:** Confirmar fechamento, coletar confirmação de pagamento.

**Modo `direto`:** Conduz fechamento e confirmação de pagamento com objetividade.

**Guardrails de fechamento:**
- Para avançar para `closing`, o sistema verifica: `price_acceptance="yes"` E `intent_level="medium|high"` nos signals da Mãe.
- Se qualquer um estiver ausente → `route_to` é revertido para `qualification` (`guardrail_direto_pullback`).
- `kanban_highlight="green"` e `outcome="won"` só são válidos quando `lead.category == "closing"`.
- Bot desabilitado automaticamente ao entrar em `closing`.

**Recursos utilizados:**
- `backend-executors/app/services/decision_engine.py` — `_build_child_prompt_closing()`
- `backend-crm/services/lead_category_policy.py`

---

## 3. Estrutura dos prompts LLM

### 3.1 Prompt Mãe — Roteador

**Função:** `_build_mother_prompt()` em `decision_engine.py`

**Saída esperada (JSON):**
```json
{
  "route_to": "qualification|apresentation|closing",
  "perceived_category": "qualification|apresentation|closing|null",
  "confidence": 0.9,
  "reason": "intenção de fechamento",
  "agent_mode": null,
  "signals": {
    "meeting_scheduled": false,
    "intent_level": "high",
    "urgency_level": "high",
    "price_acceptance": "yes"
  },
  "objective": "fechar venda direto",
  "next_action_hint": "reply"
}
```

**Regras específicas para o Closer injetadas no prompt:**
- `meeting_scheduled` deve ficar `false` para o closer — agendamento não é objetivo final.
- Se inbound for claramente de fechamento (`"posso assinar"`, `"manda contrato"`, `"quero fechar"`): `route_to="closing"`.
- `price_acceptance` SEMPRE como string: `"no"` | `"unsure"` | `"yes"`.
- `agent_mode`: `null` — vem do perfil do sistema (normalizado para `"direto"`).

**Contexto injetado no prompt:**
```
lead: {id, name, segment, status, category}
ai_profile: {id, name, template_key, tone_of_voice, niche, target_audience, agent_mode}
history: [últimas 10 mensagens]
agent_mode_normalized: "direto"
required_fields: ["service_interest", "availability_window", "price_acceptance"]
missing_fields: [...campos ainda não coletados...]
inbound_message_text: "..."
```

**Exemplos injetados (ultracurtos):**
```
CLOSER: inbound="Posso assinar hoje?"
→ {"route_to":"closing","confidence":0.9,"reason":"intenção de fechamento"}

CLOSER: inbound="Manda contrato"
→ {"route_to":"closing","confidence":0.85,"reason":"pedido de contrato"}

CLOSER (negativo): inbound="Fechou amanhã 17h"
→ {"route_to":"apresentation","confidence":0.8,"reason":"confirmou horário (no closer, sem meeting_scheduled)"}
```

---

### 3.2 Prompt Filho — Qualificação

**Função:** `_build_child_prompt_qualification()` em `decision_engine.py`

**Saída esperada (JSON):**
```json
{
  "question_text": "string — pergunta direta e objetiva",
  "field": "service_interest|availability_window|price_acceptance|null",
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

**Diferença do Closer:** Apenas 3 campos — a filha avança para `apresentation` mais rápido que no Agente 1.

---

### 3.3 Prompt Filho — Apresentação (Sales)

**Função:** `_build_child_prompt_apresentation()` em `decision_engine.py`

**Saída esperada Turno 1 (CONFIRMAR):**
```json
{
  "message_text": "Plano Pro por R$997 com suporte 24h e 7 dias de garantia. Quer seguir com a contratação?",
  "did_complete_phase": false,
  "recommended_next_category": null,
  "outcome": null,
  "kanban_highlight": null,
  "signals": [],
  "signals_structured": {
    "offer_presented": true,
    "checkout_sent": false,
    "presentation_variant": "sales",
    "offer_item_name": "Plano Pro"
  },
  "confidence": 0.85
}
```

**Saída esperada Turno 2 (ENVIAR LINK):**
```json
{
  "message_text": "Perfeito! Aqui está seu link: https://pay.exemplo.com/plano-pro\nConclua e me confirme por aqui.",
  "did_complete_phase": false,
  "recommended_next_category": null,
  "outcome": null,
  "kanban_highlight": null,
  "signals": [],
  "signals_structured": {
    "offer_presented": true,
    "checkout_sent": true,
    "presentation_variant": "sales",
    "offer_item_name": "Plano Pro"
  },
  "confidence": 0.9
}
```

**Contexto adicional injetado:**
```
presentation_variant: "sales"
offer_pack_summary: {available: true, items: [...], anchor_price: "R$1.497", guarantee_text: "7 dias...", media_url: "..."}
```

---

### 3.4 Prompt Filho — Follow-Up (Cart Recovery)

**Função:** `_build_child_prompt_follow_up()` com variante `cart_recovery` em `decision_engine.py`

**Instrução dinâmica por tentativa injetada no prompt:**
```
Variante cart_recovery (carrinho abandonado, Agent 2): recuperar pagamento pendente após link enviado.
Mensagens curtas (máx 280 chars).
Instrução para tentativa 2/3: Reforce o benefício principal e antecipe a objeção mais comum do nicho.
Tom amigável, resolva a dúvida que está impedindo o pagamento.
```

**Saída esperada (JSON):**
```json
{
  "message_text": "string — curta (máx 280 chars)",
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
  "followup_goal": "cart_recovery",
  "followup_variant": "cart_recovery",
  "attempts": 1,
  "max_attempts": 3,
  "proposal_sent": true,
  "meeting_or_session_happened": false
}
```

---

### 3.5 Prompt Filho — Closing

**Função:** `_build_child_prompt_closing()` em `decision_engine.py`

**Regra por modo (`direto`):**
> _"Conduzir fechamento e confirmação de pagamento com objetividade."_

**Saída esperada (JSON):**
```json
{
  "message_text": "Ótimo! Confirma o pagamento e em seguida libero seu acesso.",
  "did_complete_phase": true,
  "recommended_next_category": "closing",
  "outcome": "won",
  "kanban_highlight": "green",
  "signals": ["payment_confirmed"],
  "confidence": 0.95
}
```

---

## 4. Guardrails e filtros transversais

| Guardrail | Regra |
|---|---|
| **missing_fields → qualification** | Enquanto `missing_fields` não estiver vazio, `route_to` é forçado para `qualification` |
| **direto sem price+intent** | Para avançar para `closing`: `price_acceptance="yes"` E `intent_level="medium\|high"` obrigatórios; senão retorna para `qualification` (`guardrail_direto_pullback`) |
| **meeting_scheduled=false** | Closer não usa sinal de reunião agendada |
| **cart_recovery inicia após link** | Após `checkout_sent=true` e sem resposta do lead, `start_cart_recovery_followup()` é chamado |
| **max 3 tentativas de recovery** | Após 3 tentativas sem fechamento: `stop_reason="max_attempts_reached"` |
| **bot_disabled no closing** | Desabilitado automaticamente ao entrar em `closing` |
| **kanban_highlight/outcome** | Só emitidos quando `lead.category == "closing"` |
| **follow-up pausado por resposta** | `stop_followup_on_inbound_reply()` interrompe a cadência quando o lead responde |

---

## 5. Resumo do fluxo completo

```
1. Lead entra via WhatsApp (inbound) ou é criado (outbound)
   └─ Categoria inicial: "qualification"

2. Qualificação (apenas 3 campos: service_interest, availability_window, price_acceptance)
   ├─ Mãe rota para "qualification"
   ├─ Filha pergunta 1 campo por turno
   └─ Score ≥ threshold → avança para apresentation

3. Apresentação — Pitch Direto (2 turnos)
   ├─ Turno 1: Descreve oferta, pergunta "quer seguir?" (sem link)
   └─ Turno 2: Envia link de checkout + "conclua e me confirme"

4. Cart Recovery (se link enviado sem fechamento)
   ├─ Tentativa 1 (+2h): Lembrete neutro
   ├─ Tentativa 2 (+24h): Benefício + objeção
   └─ Tentativa 3 (+48h): Urgência (oferta expira hoje)

5. Closing
   ├─ Lead confirma pagamento → outcome="won"
   ├─ Bot desabilitado imediatamente
   └─ Operador humano assume se necessário
```
