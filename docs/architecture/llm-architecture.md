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

**Tolerância de enum (campos opcionais):** valores fora do enum em `next_action_hint`, `agent_mode` e `perceived_category` são silenciosamente convertidos para `None` por um `field_validator(mode="before")` em `MotherDecision` (`orchestrator_models.py`), em vez de levantar `ValidationError` e derrubar a decisão inteira do turno. Log: `event=mother_decision_invalid_enum_coerced field=<campo> value=<valor>`. `route_to` (obrigatório) fica fora desta tolerância genérica — não tem default seguro para degradar a `None`.

**Alias de `route_to`:** em vez de tolerância genérica, um segundo `field_validator(mode="before")` corrige apenas aliases pontuais conhecidos antes da validação do `Literal` — hoje só `"presentation"` → `"apresentation"` (typo recorrente da LLM, falta o "a-" do enum em PT). Valores fora dos aliases conhecidos continuam a levantar `ValidationError` e caem no fallback normal (`llm_orchestrator_error` → handoff). Log: `event=mother_decision_route_to_alias_coerced value=<valor> normalized=<valor_corrigido>`.

### Saudação composta — pedido comercial pendente é reenfileirado, não tratado no mesmo turno

Quando a 1ª mensagem do lead mistura saudação com pedido comercial (ex.: "Oi, gostaria de agendar para amanhã às 16h", ou um burst de mensagens rápidas concatenadas pelo buffer de debounce — ver [`webhooks.md`](webhooks.md)), `_enforce_greeting_first()` continua a forçar `route_to="recepcao"` nesse turno. Em vez de a Mãe tentar classificar e o código promover `route_for_child` no mesmo turno (mecanismo antigo, removido), a própria **Filha Recepção** — que já lê a mensagem crua no prompt (`_build_child_prompt_recepcao()`) — extrai literalmente qualquer trecho que não seja saudação/social para `ChildResult.pending_commercial_text`.

Se esse campo vier preenchido, `compose_decision_output()` anexa um `system_action` ao `DecisionOutput`:

```json
{"type": "requeue_pending_message", "message_text": "<trecho extraído>"}
```

O consumo é responsabilidade de quem chama o executor, não do `decide()` (que continua puro):
- **WhatsApp real** (`backend-crm/routes/executor.py`, `_dispatch_system_actions`): cria um novo job `whatsapp.inbound.n8n` com o texto pendente, reaproveitando `instance_id`/`provider`/`phone` do job original — percorre o pipeline normal no ciclo seguinte do worker.
- **Playground** (`backend-crm/routes/playground.py`): dispara uma 2ª chamada síncrona a `_call_executors_decide()` dentro da mesma request HTTP, e anexa o resultado como 2ª bolha — replica o comportamento do WhatsApp real sem depender de fila/worker.

Em ambos os casos, o turno seguinte roda a Mãe **sem overrides** — `outbound_count>0` nesse ponto (a saudação já foi enviada), então `_enforce_greeting_first` não força mais `recepcao`, e a rota comercial é decidida normalmente pelas prioridades já existentes no prompt da Mãe.

**Por que o mecanismo antigo foi removido (não mantido como fallback):** dependia de uma decisão de LLM (`compound_follow_through`/divergência de `perceived_category`) competindo com ~7 prioridades no mesmo prompt — não-determinístico, e comprovadamente falho em testes reais (a Mãe não sinalizava, a rota ficava `recepcao` pura, e a Filha Recepção chegava a improvisar promessas vazias como "vou verificar" sem nenhum estado de pendência registrado). O gate cego a `route_for_child` promovido (que motivou o "caso irmão corrigido" em 2026-06-28, no bloco "MODO COMERCIAL" da filha de apresentação — ver [`pipeline-phases.md`](pipeline-phases.md#estágio-de-aquecimento-e-appointment_mode-só-hybrid_scheduler)) deixa de existir como classe de bug, não só a instância corrigida.

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
| `pending_commercial_text` | string\|null | Só populado pela Filha Recepção — trecho literal do pedido comercial embutido na saudação, se houver. Ver "Saudação composta" acima. |
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
| `system_actions` | `list[dict]\|null` | Ações do Fluxo de Venda: `send_message`, `send_media`, `advance_phase`, `mark_phase_triggered`, `mark_trigger_fired`. Mais `requeue_pending_message` (fora do Fluxo de Venda, ver "Saudação composta" acima). |
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
- Extrai qualquer pedido comercial embutido na mensagem para `pending_commercial_text`, sem tentar respondê-lo (ver "Saudação composta" acima)

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

## Gestão pós-confirmação de reunião — atalho dedicado (bypassa a Mãe)

Quando `metadata.bot_disabled_reason == "meeting_scheduled"` (lead já confirmou uma reunião — ver "Toggle de Bot por Lead" em [`agents.md`](agents.md)), `decide()` não entra na pipeline Mãe/Filha normal. Em vez disso, antes de qualquer outra lógica:

```python
def decide(context, logger=None):
    metadata = context.get("metadata") or {}
    if metadata.get("bot_disabled"):
        if metadata.get("bot_disabled_reason") == "meeting_scheduled":
            return _decide_post_meeting_management(context, logger=logger)
        return BOT_DISABLED_DECISION   # next_action="ignore"
```

`_decide_post_meeting_management()` (`decision_engine.py`) é um caminho dedicado e mínimo, mesmo padrão de `fast_path.py` — não toca em guardrails de categoria/qualificação nem na máquina de fases. Faz **uma única chamada LLM** via `_build_child_prompt_meeting_management()`, que decide entre três resultados:

- **Cancelamento** — `signals_structured.meeting_cancel_requested = true`
- **Reagendamento** — `signals_structured.meeting_reschedule_requested = true` + `meeting_datetime_candidate` (data/hora candidata, ISO, mesmo mecanismo de extração da Filha Agendamento)
- **Nenhum dos dois** — resposta mínima e cordial, sem reabrir negociação de venda. Nunca define `suggested_category` (não move o Kanban).

A prompt cobre dois padrões de reagendamento, ambos committando `meeting_reschedule_requested=true` no mesmo turno — evita uma resposta hesitante ("vou confirmar") que exigiria outro turno:
- **Novo dia explícito** — dia e horário informados juntos (ex.: "pode ser domingo às 11h?") — usa a data literal informada pelo lead.
- **Reagendamento implícito, só horário** — a mensagem propõe apenas um horário diferente do já confirmado, sem mencionar um novo dia (ex.: "pode ser às 16h em vez de 14h?") — assume o **mesmo dia** da reunião já confirmada, combinando essa data (do bloco "REUNIÃO/SESSÃO JÁ CONFIRMADA" injectado no prompt) com o novo horário mencionado.

**Consumo do sinal:** `meeting_scheduler._extract_cancel_reschedule_signal()` lê `decision_trace.child_signals_structured` (paralelo a `_extract_meeting_signal()`) e `handle_meeting_cancel_or_reschedule()` aplica a ação real no appointment — ver [`agenda.md`](agenda.md).

**Limite conhecido:** este caminho não escala para atendimento humano — um pedido explícito de handoff dentro desta janela cai no balde "nenhum dos dois" (resposta mínima), não chama `handoff_policy`/`fast_path`. Ver `docs/plans/cancelamento-reagendamento-melhorias-futuras.md`.

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
usado pelas seis funções públicas (`generate_mother_route`, `generate_decision_text`,
`generate_child_result`, `generate_conflict_message`, `generate_appointment_reminder_message`,
`generate_appointment_title_message`): até 2 tentativas, com 1s de backoff entre elas, antes de
propagar a excepção final. Cobre falhas transitórias de rede (`httpx.RequestError`) e
status HTTP retryable (429/500/502/503/504). Aplica-se tanto ao fluxo real (WhatsApp,
via fila de jobs) quanto ao Playground (chamada síncrona, sem fila) — antes desta
camada, o Playground não tinha nenhum retry e qualquer falha transitória caía
directo no fallback `reason="llm_failure"` (`message_text=""`).

As últimas quatro (`generate_conflict_message`, `generate_appointment_reminder_message`,
`generate_appointment_title_message`) devolvem texto puro (sem `text.format=json_object`)
— usadas para gerar uma única mensagem de WhatsApp, não uma decisão estruturada. Cada
uma tem uma função-irmã em `meeting_scheduler.py` (`_generate_conflict_message`,
`generate_appointment_reminder_message`, `generate_appointment_title`) que monta o
prompt e nunca propaga excepção — qualquer falha (sem `LLM_API_KEY`, erro de rede,
timeout, resposta vazia) devolve `None` e o caller cai num fallback fixo.

Não interfere com o retry de job da fila (`app/runners/whatsapp.py`, backoff
global 60s/180s) — são camadas independentes: o retry de `llm_service.py` é interno a uma
única chamada HTTP; o retry de job é externo, reagenda o job inteiro quando
`llm_failure` persiste mesmo após as tentativas internas. O job
`whatsapp.appointment.reminder` tem um override deste backoff global — ver
[`agenda.md`](agenda.md#lembrete-de-reunião-gerado-por-ia).

### Fallback final: falha da LLM Mãe sempre vira handoff

Se a chamada à LLM Mãe (ou o parsing/validação do payload) falhar mesmo após o retry de
`llm_service.py`, o `except Exception` de `decide()` cai sempre em
`handoff_policy.apply(context, FALLBACK_DECISION, logger=logger)` — independente de quantos
turnos a conversa já teve. `handoff_policy.apply()` lê `ai_profile.handoff_custom_text` (ou o
template padrão por `identity_mode`, ver [`agents.md`](agents.md)) e envia essa mensagem ao
lead, seguindo a política configurada (`keep_active_notify` notifica o time; `disable_bot`
pausa o bot para aquele lead). Não existe caminho de falha da Mãe que devolva resposta vazia
sem handoff — nem mesmo nos primeiros turnos de uma conversa nova.

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
