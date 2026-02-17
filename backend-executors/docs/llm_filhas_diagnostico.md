# Diagnóstico — LLMs filhas (estado atual)

Escopo analisado: `backend-executors/app/services/decision_engine.py`, `backend-executors/app/services/llm_service.py`, `backend-executors/app/services/orchestrator_models.py`, `backend-executors/app/runners/whatsapp.py`.

## 1) Quantas LLMs filhas existem atualmente?

Existem **3 prompts de filha implementados**:

1. `FILHA QUALIFICATION` (`_build_child_prompt_qualification`)
2. `FILHA APRESENTATION` (`_build_child_prompt_apresentation`)
3. `LLM FILHA` genérica para rotas restantes (`_build_child_prompt`), usada quando `route_to` é `follow-up` ou `closing`.

Em runtime, há **1 chamada de LLM filha por decisão**, com prompt escolhido por rota da mãe.

## 2) Onde elas estão instanciadas?

As funções de prompt filha ficam em:
- `backend-executors/app/services/decision_engine.py`

A chamada real da LLM filha ocorre em `decide()`:
- monta prompt conforme `mother_decision.route_to`
- chama `llm_service.generate_child_result(mother_decision.route_to, child_prompt)`

## 3) Qual arquivo contém o prompt principal delas?

O conteúdo dos prompts está em:
- `backend-executors/app/services/decision_engine.py`

## 4) Conteúdo completo atual do prompt

### 4.1 Prompt da filha genérica (`_build_child_prompt`)

```text
Você é uma LLM FILHA e deve responder SOMENTE JSON válido:
{
  "message_text": "string",
  "did_complete_phase": false,
  "recommended_next_category": "qualification|apresentation|follow-up|closing|null",
  "outcome": "won|lost|null",
  "kanban_highlight": "green|orange|null",
  "signals": ["..."],
  "confidence": 0.0
}
Regras:
- confidence entre 0 e 1.
- recommended_next_category deve ser um estágio do funil ou null.
- message_text é a resposta para o WhatsApp.

ROTA MÃE: {mother_decision.route_to} (confidence={mother_decision.confidence})
Motivo MÃE: {mother_decision.reason}

CONTEXTO:
- lead: {lead_summary}
- ai_profile: {ai_summary}
- playbook: {playbook_summary}
- metadata: {metadata_summary}
- history: {history_text}
- inbound_message_text: {message_text}
```

### 4.2 Prompt da filha qualification (`_build_child_prompt_qualification`)

```text
Você é a FILHA QUALIFICATION e deve responder SOMENTE JSON válido:
{
  "message_text": "string",
  "did_complete_phase": false,
  "recommended_next_category": "apresentation|null",
  "outcome": null,
  "kanban_highlight": null,
  "signals": ["..."],
  "confidence": 0.0
}
Regras:
- message_text é obrigatório e deve conter 1–2 perguntas objetivas de qualificação.
- NÃO agendar reunião aqui (só agendar na rota apresentation, salvo pedido explícito do inbound).
- Use tone_of_voice, brand_name e niche quando disponíveis.
- Respeite playbook.max_chars se existir (senão, resposta curta).
- recommended_next_category pode ser null ou 'apresentation' (micro-ajuste de avanço).
- outcome e kanban_highlight devem ser null.

ROTA MÃE: {mother_decision.route_to} (confidence={mother_decision.confidence})
Motivo MÃE: {mother_decision.reason}

CONTEXTO:
- lead: {lead_summary}
- ai_profile: {ai_summary}
- playbook: {playbook_summary}
- metadata: {metadata_summary}
- history: {history_text}
- inbound_message_text: {message_text}
```

### 4.3 Prompt da filha apresentation (`_build_child_prompt_apresentation`)

```text
Você é a FILHA APRESENTATION e deve responder SOMENTE JSON válido:
{
  "message_text": "string",
  "did_complete_phase": false,
  "recommended_next_category": null,
  "outcome": null,
  "kanban_highlight": null,
  "signals": ["..."],
  "confidence": 0.0
}
Regras:
- message_text é obrigatório e deve lidar com agenda: pedir dia/horário, confirmar, reagendar, enviar link.
- Se agent_mode for sdr_scheduler e mother_decision.reason contiver meeting_scheduled, confirme horário
  e indique que enviará/confirmará o link (sem criar appointment).
- Se agent_mode for closer, mantenha postura de avanço comercial, mas ainda trate o agendamento.
- Use tone_of_voice, brand_name e niche quando disponíveis.
- Respeite playbook.max_chars se existir (senão, resposta curta).
- recommended_next_category deve ser null.
- outcome e kanban_highlight devem ser null.

ROTA MÃE: {mother_decision.route_to} (confidence={mother_decision.confidence})
Motivo MÃE: {mother_decision.reason}

CONTEXTO:
- lead: {lead_summary}
- ai_profile: {ai_summary}
- playbook: {playbook_summary}
- metadata: {metadata_summary}
- history: {history_text}
- inbound_message_text: {message_text}
```

## 5) Elas recebem `route_to`, `perceived_category`, `decision_trace`?

- **`route_to` da mãe:** **sim**. Vai no argumento `route` de `generate_child_result(route, prompt)` e no texto do prompt (`ROTA MÃE: ...`).
- **`perceived_category`:** **não explicitamente** no payload da filha. O prompt da filha recebe `mother_decision.route_to` e `mother_decision.reason`; não há linha com `perceived_category` no texto da filha.
- **`decision_trace`:** **não**. `decision_trace` é montado depois em `compose_decision_output()` para observabilidade.

## 6) Lógica interna de limite/objetivo/checklist/parada

Nos prompts de filha:
- **limite de perguntas:** apenas na qualification (“1–2 perguntas objetivas”).
- **objetivo explícito:** sim, por rota (qualificar sem agendar; apresentar/agendar na apresentation; resposta WhatsApp na genérica).
- **checklist de qualificação formal:** não existe checklist estruturado; existem regras textuais.
- **critério de parada formal:** não há regra explícita de stop/turn limit; há `did_complete_phase` no JSON de saída, mas sem loop interno no orquestrador.

## 7) A LLM filha decide categoria ou apenas conversa?

A filha **não decide categoria final sozinha**. Ela pode sugerir `recommended_next_category`, mas a categoria aplicada passa por guardrails e composição no orquestrador (`apply_mother_category_guardrails`, `_apply_child_micro_adjustment`, `_sanitize_category_decision`).

## 8) O executor passa instrução contextual além do histórico?

Sim. Além de `history`, o prompt da filha inclui:
- `lead` (id, nome, categoria, segmento)
- `ai_profile` (nome, marca, tom, nicho, agent_mode, etc.)
- `playbook` (template_key e `max_chars` em prompts especializados)
- `metadata` (provider, instance_id)
- `inbound_message_text`
- resumo da rota/motivo da mãe

## Fluxo simplificado de chamada (diagrama textual)

```text
whatsapp runner
  -> crm_client.get_whatsapp_execution_context(job_id)
  -> decision_engine.decide(context)
      -> _build_mother_prompt(...)
      -> llm_service.generate_mother_route(mother_prompt)
      -> valida MotherDecision(route_to, perceived_category, ...)
      -> escolhe prompt filha por route_to
          qualification -> _build_child_prompt_qualification
          apresentation -> _build_child_prompt_apresentation
          follow-up/closing -> _build_child_prompt (genérica)
      -> llm_service.generate_child_result(route_to, child_prompt)
      -> valida ChildResult(...)
      -> compose_decision_output(...)
          + guardrails de categoria e outcome
          + monta decision_trace
      -> retorna DecisionOutput
```
