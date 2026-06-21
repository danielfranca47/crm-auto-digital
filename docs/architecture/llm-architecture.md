# Arquitetura LLM — Mãe e Filhas

## Visão geral

O sistema usa uma arquitetura de duas camadas de LLM por job processado:
- **LLM Mãe**: decide a rota (qual fase do funil atender)
- **LLM Filha**: gera o texto da resposta para o lead com base na rota da Mãe

Toda a lógica está em `backend-executors/app/services/decision_engine.py`.

---

## Fluxo simplificado

> **Camada 7 (Fluxo de Venda):** `_evaluate_sales_flow_phases()` corre dentro de `decide()` após a decisão da LLM Mãe e antes do prompt filho. Produz `prompt_injections` (orientações injectadas no prompt), `pre_send_media` e `system_actions` que são compostos no `DecisionOutput`. Ver [`sales-flow.md`](sales-flow.md).

```
whatsapp_worker
  → crm_client.get_whatsapp_execution_context(job_id)
  → decision_engine.decide(context)
      → _build_mother_prompt(...)
      → llm_service.generate_mother_route(mother_prompt)
      → valida MotherDecision
      → _evaluate_sales_flow_phases(context, route_to, message_text)
          → avalia blocos da fase correspondente
          → retorna {prompt_injections, pre_send_media, system_actions}
      → escolhe prompt filha por route_to (+ injeta prompt_injections):
          recepcao         → _build_child_prompt_recepcao
          qualification    → _build_child_prompt_qualification
          apresentation    → _build_child_prompt_apresentation
          pre-agendamento  → _build_child_prompt_pre_agendamento
          agendamento      → _build_child_prompt_agendamento
          follow-up        → _build_child_followup_prompt
          closing          → _build_child_prompt (genérica)
      → llm_service.generate_child_result(route_to, child_prompt)
      → valida ChildResult
      → compose_decision_output(...)
          + guardrails de categoria e outcome
          + monta decision_trace
          + inclui pre_send_media e system_actions do Fluxo de Venda
      → retorna DecisionOutput
```

---

## Contratos

### MotherDecision (saída da LLM Mãe)

**Campos obrigatórios:**

| Campo | Tipo | Descrição |
|---|---|---|
| `route_to` | `recepcao\|qualification\|apresentation\|pre-agendamento\|agendamento\|follow-up\|closing` | Rota decidida. `pre-agendamento`/`agendamento` só fazem sentido para templates de agendamento (`_SCHEDULING_AGENT_TEMPLATES` — ver [`pipeline-phases.md`](pipeline-phases.md)). Campo obrigatório, sem tolerância de enum — valor fora da lista levanta `ValidationError` e cai no fallback/retry existente. |
| `perceived_category` | mesmos valores + null | Categoria percebida |
| `confidence` | 0..1 | Confiança da decisão |
| `reason` | string | Justificativa textual |
| `detected_intents` | `list[str]` | Intenções detectadas na mensagem do lead. Presente apenas quando a fase activa tem blocos `intent_trigger`; caso contrário `[]`. Usado por `_evaluate_sales_flow_phases()` para avaliar `intent_trigger`. |

**Campos opcionais (backward compatible):**

| Campo | Tipo | Descrição |
|---|---|---|
| `signals` | dict\|null | Sinais estruturados: `meeting_scheduled` (bool), `intent_level` (`low\|medium\|high`), `urgency_level` (`low\|medium\|high`), `price_acceptance` (`no\|unsure\|yes`) |
| `next_action_hint` | `reply\|ask_qualification\|handoff\|ignore\|greet\|null` | Sugestão de próxima ação ao pipeline |
| `objective` | string\|null | Objetivo da resposta atual (informativo) |
| `compound_follow_through` | mesmos valores de `route_to` + null | Quando `route_to="recepcao"` mas a mensagem combina saudação com pedido comercial (ex.: "Oi, gostaria de agendar para amanhã às 16h"), indica a rota real da parte comercial. Mãe instruída (prompt, secção SAUDAÇÃO COMPOSTA) a aplicar um checklist dia+hora: ambos presentes → `agendamento` directamente; só um ou nenhum → `pre-agendamento`/`qualification`/etc. conforme o caso. Decisão de uma LLM — não-determinística; quando erra para `pre-agendamento` em vez de `agendamento`, a homologação de categoria (ver [`pipeline-phases.md`](pipeline-phases.md)) absorve o caso no mesmo ou próximo turno. |

**Tolerância de enum (campos opcionais):** valores fora do enum em `next_action_hint`, `agent_mode`, `compound_follow_through` e `perceived_category` são silenciosamente convertidos para `None` por um `field_validator(mode="before")` em `MotherDecision` (`orchestrator_models.py`), em vez de levantar `ValidationError` e derrubar a decisão inteira do turno. Log: `event=mother_decision_invalid_enum_coerced field=<campo> value=<valor>`. `route_to` (obrigatório) fica fora desta tolerância.

### Saudação composta — recepção responde antes da filha comercial

Quando `route_to="recepcao"` e existe `compound_follow_through` (ou, em sua ausência, `perceived_category` difere da categoria actual do lead), `decide()` faz uma **segunda chamada LLM** dedicada — `_build_child_prompt_recepcao()` + `generate_child_result("recepcao", ...)` — só para gerar o cumprimento. O texto resultante é guardado em `context["_compound_greeting_text"]` e prefixado à resposta da filha comercial (`"{saudação}\n\n{texto comercial}"`); a divisão em bolhas distintas no WhatsApp é feita pelo mecanismo de humanização já existente (ver [`humanization.md`](humanization.md)).

Custo: 1 chamada LLM extra, só neste turno específico (primeira mensagem composta de um lead) — não afecta turnos normais. Chamada best-effort (`try/except`): se falhar, a resposta segue sem a bolha de saudação separada.

### ChildResult (saída da LLM Filha)
| Campo | Tipo | Descrição |
|---|---|---|
| `message_text` | string | Mensagem para enviar ao lead via WhatsApp |
| `did_complete_phase` | bool | Se a fase foi concluída |
| `recommended_next_category` | string\|null | Sugestão de próxima categoria |
| `outcome` | `won\|lost\|null` | Outcome se aplicável |
| `kanban_highlight` | `green\|orange\|null` | Destaque visual no Kanban |
| `signals` | list[string] | Sinais detectados |
| `signals_structured` | dict\|null | Sinais estruturados (meeting_proposed, checkout_sent, etc.) |
| `media_keys_to_send` | list[string]\|null | Chaves de `knowledge_media` cujas mídias a filha decidiu anexar neste turno. Só populado na filha de apresentação. Fallback estrito: `null`/`[]` → nenhuma mídia anexada. |
| `confidence` | 0..1 | Confiança da resposta |

### Normalização de agent_mode

O executor normaliza o `agent_mode` do AI Profile para um valor canônico antes de qualquer decisão:

| Valor recebido | Normalizado (`agent_mode_normalized`) |
|---|---|
| `consultivo` | `consultivo` |
| `agenda` | `agenda` |
| `direto` | `direto` |
| `closer` | `direto` |
| `sdr_scheduler` | `agenda` |

### Dual-read de meeting_scheduled

Para compatibilidade com o contrato legado, o executor segue esta ordem:
1. Lê `mother_decision.signals.meeting_scheduled` (bool estruturado — novo)
2. Se ausente: fallback para substring `"meeting_scheduled"` em `mother_decision.reason` (legado)

Resultado publicado em `decision_trace.meeting_scheduled`.

### decision_trace — campos de observabilidade

Campos adicionados ao `decision_trace` que acompanham o `DecisionOutput`:

| Campo | Descrição |
|---|---|
| `agent_mode_normalized` | Modo normalizado final (`consultivo`, `agenda`, `direto`) |
| `next_action_hint` | Valor retornado pela Mãe, se presente |
| `mother_signals` | Resumo de `signals` da Mãe (intent_level, urgency_level, price_acceptance, etc.) |
| `meeting_scheduled` | Resultado do dual-read |

### DecisionOutput (saída final do executor)
Combinação de MotherDecision + ChildResult + guardrails + Fluxo de Venda, enviado ao CRM via `complete_job`.

Campos adicionados pelo Fluxo de Venda (Camada 7):

| Campo | Tipo | Descrição |
|---|---|---|
| `pre_send_media` | `list[dict]\|null` | Mídias de `media_keys_to_send` da filha de apresentação. Blocos `midia` do Fluxo de Venda vão para `system_actions` (não para este campo). |
| `system_actions` | `list[dict]\|null` | Ações do Fluxo de Venda: `send_message`, `send_media`, `advance_phase`, `mark_phase_triggered`, `mark_trigger_fired` |
| `suppress_llm_response` | `bool` | `True` quando um trigger com o flag disparou. Força `next_action="ignore"` e `message_text=""`. Ações automáticas são executadas normalmente. |

---

## LLMs Filhas implementadas

### Filha Qualification (`_build_child_prompt_qualification`)
- Instrução: gerar 1–2 perguntas objetivas de qualificação
- Não agendar reunião (só na rota `apresentation`)
- Respeitar `max_chars` do playbook
- `recommended_next_category`: null ou `apresentation`

### Filha Presentation (`_build_child_prompt_apresentation`)
- Instrução: lidar com agendamento (pedir dia/horário, confirmar, reagendar, enviar link)
- SDR: confirma horário e indica envio de link
- Closer: mantém postura comercial ao tratar agendamento
- **Seleção contextual de mídia** (`media_keys_to_send`): o prompt lista as categorias de `knowledge_media` disponíveis e a filha declara quais devem ser anexadas neste turno. Regra: mídia só entra quando o lead pediu explicitamente (preço, pagamento, objeção, etc.). O `decision_engine` usa essa lista para filtrar as mídias enviadas — fallback estrito: se a filha omitir o campo, nenhuma mídia é anexada.

### Filha Recepção (`_build_child_prompt_recepcao`)
- Instrução restrita: só o cumprimento inicial, sem tratar pedido comercial
- Usada tanto na saudação pura quanto, numa 2ª chamada dedicada, na saudação composta (ver acima)

### Filha Pré-agendamento (`_build_child_prompt_pre_agendamento`)
- Só para templates de agendamento (`sdr_padrao`, `hybrid_scheduler`)
- Detecta intenção tentativa de agendar ("vou ver", "semana que vem") vs. firme (dia+hora específicos)
- Quando dia+hora específicos: pula o fluxo de negociação tentativa e usa `recommended_next_category="agendamento"` para homologar o avanço de fase no mesmo turno (ver [`pipeline-phases.md`](pipeline-phases.md))
- Recebe `tabela_de_dias` (lookup de hoje + 14 dias com nome do dia da semana já calculado) em vez de só a data de hoje — evita a LLM ter de calcular aritmética de calendário

### Filha Agendamento (`_build_child_prompt_agendamento`)
- Confirma o horário pedido contra `calendar_busy_slots`/disponibilidade do AI Profile
- Devolve `signals_structured.meeting_datetime_candidate` (data/hora exacta combinada, ISO) — consumido por `meeting_scheduler.py` antes de cair no fallback heurístico de extracção por texto (`extract_start_at`, impreciso). Mesmo mecanismo já usado pela filha de Presentation.
- Recebe `tabela_de_dias` (mesmo lookup acima) e `ai_profile.timezone`

### Filha Follow-up (`_build_child_followup_prompt`)
- Monta `followup_summary` com `followup_goal`, `outcome`, `operator_note`, `meeting_happened`, `proposal_sent`
- Inclui regras por variant (`sdr_scheduler` vs `hybrid_scheduler`)
- Instrução prioritária: usar `followup_contract_signals` como fonte principal
- Passa `tone_of_voice`, `custom_instructions`, `offer_description`, `goals`, `niche`, `identity_mode`

### Filha Closing (`_build_child_prompt_closing`)
- Instrução: confirmar decisão de compra, nunca enviar links antes de confirmar interesse
- Postura ajustada por `agent_mode_normalized` (direto vs consultivo)
- Recebe `offer_pack_summary`, `anchor_price`, `guarantee_text` se disponíveis

### Filha Genérica (`_build_child_prompt`)
- Fallback para rotas não cobertas pelas filhas especializadas
- Recebe contexto completo mas sem instrução especializada de fase

---

## Estrutura de prompt das Filhas

Todos os prompts de Filha seguem a mesma ordem de blocos no final:

```
...contexto de fase (regras, histórico, qualificação, playbook)...
_build_training_examples_block(phase)   ← few-shot por fase (qualification/apresentation/followup/closing)
_build_custom_instructions_block()      ← custom_instructions do operador (último = maior peso)
_build_validation_block(max_chars)      ← formato de saída JSON + limite de caracteres
```

**Regra de posicionamento:** LLMs priorizam início e fim do prompt. `custom_instructions` fica no final para garantir que as instruções do operador sobreponham os defaults do playbook. Os few-shot examples ficam imediatamente antes para servir de referência próxima ao output.

**`_build_training_examples_block(phase)`** — lê `context.training_examples[phase]` (populado pelo AI Profile). Se não configurado, o bloco é omitido. Fases cobertas: `qualification`, `apresentation`, `followup`, `closing`.

## Guardrails de estágio

Existem duas camadas de guardrails:

**No executor (`decision_engine.py`):**
- `apply_mother_category_guardrails` — avanço/retrocesso/jump de etapas
- `_apply_child_micro_adjustment` — micro avanço sugerido pela filha em qualification
- `_sanitize_category_decision` — valida categoria permitida no contexto
- Guardrails anti-loop de qualification (Regra 1/2/3) e homologação de categoria entre fases (`pre-agendamento→agendamento`, `apresentation→agendamento`) — ver [`pipeline-phases.md`](pipeline-phases.md)

**No CRM (`jobs_service.apply_suggested_category`):**
- Valida categoria contra `LEAD_CATEGORIES_SET`
- Exige sinal inbound para persistir mudança
- Aplica side effect ao entrar em closing (`apply_closing_bot_disable_side_effect`)

### Gate de confirmação de agendamento (M3) — `is_phase_entry`

`compose_decision_output()` expõe `decision_trace["is_phase_entry"]` (já calculado para outros fins) ao `DecisionOutput`. `meeting_scheduler._extract_meeting_signal()` lê esse campo para `MeetingSignal.is_phase_entry`; em `handle_meeting_scheduled()`, quando `is_phase_entry=True`, o appointment **não é criado** e o bot **não é desabilitado** neste turno — a resposta normal da filha (proposta/negociação) segue ao lead, e a confirmação real só pode criar o appointment num turno em que o lead já estava antes na fase actual. Evita que uma 1ª mensagem interpretada erradamente pela Mãe como confirmação (`meeting_scheduled=true`) crie um compromisso fantasma. Log: `event=meeting_scheduled_deferred_phase_entry`.

Trade-off aceite: se o lead confirma um horário na MESMA mensagem em que a Mãe avança a categoria para a fase de agendamento, a criação real fica diferida para o turno seguinte.

---

## Regras de automação do meeting scheduler por agent_mode

| `agent_mode_normalized` | Comportamento |
|---|---|
| `consultivo` | Não dispara criação automática de appointment — fluxo com human-in-loop ou handoff |
| `agenda` | Dispara automação quando `decision_trace.meeting_scheduled=true` |
| `direto` | Não participa da automação de agendamento |

---

## Nota sobre "n8n" no código

O nome "n8n" aparece em identificadores (`TYPE_WHATSAPP_INBOUND_N8N = "whatsapp.inbound.n8n"`) como artefato histórico de uma arquitetura descartada. **n8n nunca foi implantado.** O executor real é o `backend-executors`.

Locais onde o nome aparece:
- `backend-crm/services/jobs_service.py` — constante `TYPE_WHATSAPP_INBOUND_N8N`
- `backend-crm/routes/executor.py` — usa a constante
- `backend-crm/services/followup_channel_context.py` — `expand_type_variants`

Renomear a constante Python é seguro. Renomear o **valor string** exige migração de jobs pendentes no banco.

---

## Retry com backoff nas chamadas à LLM

`backend-executors/app/services/llm_service.py` — helper partilhado `_post_with_retry()`,
usado pelas quatro funções públicas (`generate_mother_route`, `generate_decision_text`,
`generate_child_result`, `generate_conflict_message`): até 2 tentativas, com 1s de backoff entre elas, antes de
propagar a excepção final. Cobre falhas transitórias de rede (`httpx.RequestError`) e
status HTTP retryable (429/500/502/503/504). Aplica-se tanto ao fluxo real (WhatsApp,
via fila de jobs) quanto ao Playground (chamada síncrona, sem fila) — antes desta
camada, o Playground não tinha nenhum retry e qualquer falha transitória caía
directo no fallback `reason="llm_failure"` (`message_text=""`).

Não interfere com o retry de job da fila (`app/runners/whatsapp.py`, backoff
60s/180s) — são camadas independentes: o retry de `llm_service.py` é interno a uma
única chamada HTTP; o retry de job é externo, reagenda o job inteiro quando
`llm_failure` persiste mesmo após as tentativas internas.

---

## Arquivos críticos

| Arquivo | Responsabilidade |
|---|---|
| `backend-executors/app/services/decision_engine.py` | Motor de decisão, prompts Mãe e Filhas, guardrails, composição |
| `backend-executors/app/services/llm_service.py` | Chamada HTTP ao LLM (Claude/OpenAI format), retry com backoff |
| `backend-executors/app/services/orchestrator_models.py` | Schemas MotherDecision, ChildResult |
| `backend-executors/app/runners/whatsapp.py` | Executa cada job: contexto → decide → envia |
| `backend-executors/app/services/fast_path.py` | Decisões sem LLM (handoff imediato, bot desabilitado) |
| `backend-executors/app/services/handoff_policy.py` | Política de handoff humano |
| `backend-executors/app/services/meeting_scheduler.py` | Agendamento de reuniões pós-decisão |
| `backend-crm/services/jobs_service.py` | Persistência de categoria sugerida, side effects |
