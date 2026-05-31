# Pipeline de Fases por Tipo de Agente

## Visão geral

O pipeline de vendas tem três fases: **Qualification → Presentation → Closing**. A transição entre fases é controlada por guardrails no `backend-executors` e persistida via `backend-crm`. O comportamento do LLM em cada fase vem de uma "LLM Filha" especializada.

---

## Campos do AI Profile que chegam ao LLM

Prompt construído em `backend-executors/app/services/decision_engine.py`:

| Campo | Status | Observação |
|-------|:---:|---|
| `brand_name` | ✅ | Sempre |
| `tone_of_voice` | ✅ | Sempre |
| `niche` | ✅ | Sempre |
| `target_audience` | ✅ | Sempre |
| `offer_description` | ✅ | Sempre |
| `goals` | ✅ | Sempre |
| `custom_instructions` | ✅ | Sempre |
| `agent_mode` (normalizado) | ✅ | consultivo/agenda/direto |
| `offer_pack` (resumo) | ✅ | Via `_build_offer_pack_summary()` |
| `identity_mode` | ✅ | Sempre |
| `handoff_policy` | ✅ | Sempre |
| `handoff_custom_text` | ✅ | Sempre |
| `presentation_variant` | ✅ | Resolvido no orchestrator |
| `followup_cadence` | ⚠️ | Usado no followup_state, não no prompt de qualificação/apresentação |
| `hybrid_flow_style` | ⚠️ | Campo existe, execução parcial no decision_engine |
| `qualification_questions` | ❌ | Não existe — hardcoded em `ai_playbooks/__init__.py` |

---

## Qualification

### Implementado (comum a todos os agentes)

- Campos obrigatórios por `agent_mode` — `backend-crm/services/qualification_guardrails.py`:
  - `consultivo`: 6 campos | `agenda`: 4 campos | `direto`: 3 campos
- Bloqueio de avanço: HTTP 409 se campos faltantes — `backend-crm/routes/leads.py`
- Extração heurística de campos por regex/keywords — `backend-executors/app/contracts/qualification_contract.py`
- Persistência em `lead_qualification_state` com histórico de perguntas (max 3/campo)
- Evitar repetição de perguntas via SequenceMatcher

### Guardrails anti-loop

**Regra 1 — `missing_fields == [] → nunca ask_qualification`**
- Cobertura: parcial. Quando `route_to=qualification` e `missing_fields` vazio e `lead_current_category=qualification`, há auto-promoção para `apresentation`.
- Gap: se a categoria atual já estiver fora de qualification, a trava não dispara.

**Regra 2 — campo já preenchido não é reperguntado**
- Cobertura: boa. `missing_fields` = `required_fields - filled_fields`; o campo `current_field` aponta para `missing[0]`, então campos preenchidos saem da fila.
- Gap: sem sanitizer rígido que bloqueie se o LLM "desobedecer" a instrução.

**Regra 3 — após promoção, não volta para qualification**
- Cobertura: parcial. `decision_trace.qualification_auto_promoted` existe mas não é persistência cross-job.
- Gap: não há trava explícita no início de `decide()` baseada em categoria atual.

**Localização:** `backend-executors/app/services/decision_engine.py` — funções `compose_decision_output` e `decide`.

### LLM Filha de Qualification

- Prompt: `_build_child_prompt_qualification` em `decision_engine.py`
- Instrução: gerar 1 pergunta por turno; não agendar reunião; usar `tone_of_voice`, `brand_name`, `niche`
- **Perguntas configuráveis via `qualification_fields`** — quando presentes no AI Profile, substituem os defaults hardcoded. Cada campo tem `question` (pergunta direta), `passive_hint` (captura silenciosa), `qualify_if` e `disqualify_if` (critérios opcionais de qualificação/desqualificação)
- **Abertura de qualificação (`qual_opener`):** bloco especial de tipo `orientacao` com flag `qual_opener: true` na fase p1 do `sales_flow`. Quando presente e `asked_questions_json` está vazio, injeta instrução de abertura antes da primeira pergunta (ex: "Posso te fazer algumas perguntas rápidas?"). Condição de activação: `qualification_fields` com pelo menos 1 campo ativo + `response_style="active"` + primeira mensagem da fase
- **Reação contextual (`_natural_reaction_block`):** instrução injectada quando `response_style="active"` e há `qualification_fields` activos — orienta o LLM a comentar brevemente sobre a resposta do lead antes de avançar para a próxima pergunta, usando `qualify_if`/`disqualify_if` para calibrar o tom (conexão vs. compreensão breve)

### Edição manual da qualificação

A secção "Critérios de Qualificação" no `LeadCardDialog` permite editar manualmente os campos de qualificação capturados pela IA:
- **Fonte:** `GET /api/leads/{lead_id}/qualification-fields` — lê `lead_qualification_state.data_json`
- **Edição:** `PATCH /api/leads/{lead_id}/qualification-fields` — atualiza campos individualmente
- Badge "X pendentes" (vermelho) indica `required_fields` sem valor; badge "Completo" (verde) quando todos preenchidos
- A secção renderiza apenas quando o AI Profile tem `qualification_fields` configurados

---

## Presentation

### Implementado (comum a todos os agentes)

- Variantes `"sales"` e `"scheduler"` resolvidas no orchestrator
- `offer_pack` injetado no prompt via `_build_offer_pack_summary()`
- Guardrail de reversão: modo agenda sem horário volta para qualification
- `hybrid_flow_style` definido no AI Profile (`offer_then_schedule` / `schedule_then_offer`) — campo existe, branches no decision_engine parcialmente implementados

### LLM Filha de Presentation

- Prompt: `_build_child_prompt_apresentation` em `decision_engine.py`
- Instrução: lidar com agendamento (pedir dia/horário, confirmar, reagendar, enviar link)
- Para SDR: confirma horário e indica que enviará link; para closer: mantém postura de avanço comercial

---

## Closing

### Implementado (comum a todos os agentes)

- Bot desabilitado ao entrar em closing para agentes de agenda (Agent 1, 3)
- Bot permanece ativo para Agent 2 (`presentation_variant = "sales"`)
- Parada de follow-up ao mover para `"client-list"`, `"prospect-refused"`, `"disqualified"`
- Appointments com outcomes (`completed`, `no_show`, `rescheduled`)
- Registro de temperatura pós-reunião via `FollowUpTransitionModal`

### LLM Filha de Closing

- Prompt: `_build_child_prompt` genérica (não há filha especializada de closing ainda)
- Recebe: `route_to`, `reason`, `lead_summary`, `ai_summary`, `playbook_summary`, `history`

---

## Mapeamento de tipos de agente para fases

| `template_key` | Tipo de agente | Agente lógico |
|---|---|---|
| `sdr_padrao`, `consultor_especialista` | SDR/Scheduler | `agent_1` |
| `closer_agressivo` | Closer | `agent_2` |
| `hybrid_scheduler` | Híbrido agendador | `agent_3` |

### Agent 2 (closer_agressivo)
- Não entra no fluxo de follow-up automático (intencional)
- Bot permanece ativo em closing

### Agent 3 (hybrid_scheduler)
- Playbook específico ausente: cai no fallback `sdr_padrao` em `ai_playbooks/__init__.py`

---

## Camada 7 — Fluxo de Venda

O Fluxo de Venda permite configurar comportamentos determinísticos por fase via blocos tipados. Corre **antes da construção do prompt filho** em cada job processado.

**Função:** `_evaluate_sales_flow_phases(context, effective_route_to, message_text)` em `decision_engine.py`

Três efeitos produzidos:
1. **`prompt_injections`** — blocos `orientacao` são injectados como instrução adicional no prompt filho da fase
2. **`pre_send_media`** — blocos `midia` geram itens enviados antes da mensagem de texto
3. **`system_actions`** — blocos `mensagem` e `avancar_fase` geram ações executadas pelo executor do CRM

`avancar_fase` → mapeado via `_PHASE_ID_TO_CATEGORY` → chama `apply_suggested_category()` para mover o lead no Kanban.

Ver [`docs/architecture/sales-flow.md`](sales-flow.md) para detalhes completos sobre fases, tipos de bloco e fluxo de execução.

---

## Hardcodes identificados (comportamentos não configuráveis pelo usuário)

| Hardcode | Localização |
|---|---|
| Perguntas de qualificação (fallback sem `qualification_fields`) | `backend-crm/services/ai_playbooks/__init__.py` |
| Overrides de comportamento por `agent_mode` (`max_chars`, `qualification_depth`) | `backend-crm/services/ai_orchestrator/orchestrator.py` |
| Estratégia de cart recovery (Agent 2) | `backend-crm/services/ai_playbooks/__init__.py` |
| Estratégia de follow-up pós-sessão por outcome (Agent 3) | `backend-crm/services/ai_playbooks/__init__.py` |

---

## Arquivos críticos

| Arquivo | Responsabilidade |
|---|---|
| `backend-crm/services/qualification_guardrails.py` | Campos obrigatórios por modo |
| `backend-crm/services/ai_playbooks/__init__.py` | Playbooks e hardcodes por template |
| `backend-crm/services/ai_orchestrator/orchestrator.py` | Monta ContextBundle, aplica overrides por mode |
| `backend-executors/app/services/decision_engine.py` | Motor de decisão, prompts das filhas, guardrails anti-loop |
| `backend-crm/routes/leads.py` | Guardrail HTTP 400/409 por qualificação incompleta; `GET /{lead_id}/qualification-fields` e `PATCH /{lead_id}/qualification-fields` |
| `backend-crm/services/lead_category_policy.py` | Side-effects de mudança de categoria |
