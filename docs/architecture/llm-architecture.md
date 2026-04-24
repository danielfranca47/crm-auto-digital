# Arquitetura LLM — Mãe e Filhas

## Visão geral

O sistema usa uma arquitetura de duas camadas de LLM por job processado:
- **LLM Mãe**: decide a rota (qual fase do funil atender)
- **LLM Filha**: gera o texto da resposta para o lead com base na rota da Mãe

Toda a lógica está em `backend-executors/app/services/decision_engine.py`.

---

## Fluxo simplificado

```
whatsapp_worker
  → crm_client.get_whatsapp_execution_context(job_id)
  → decision_engine.decide(context)
      → _build_mother_prompt(...)
      → llm_service.generate_mother_route(mother_prompt)
      → valida MotherDecision
      → escolhe prompt filha por route_to:
          qualification   → _build_child_prompt_qualification
          apresentation   → _build_child_prompt_apresentation
          follow-up       → _build_child_followup_prompt
          closing         → _build_child_prompt (genérica)
      → llm_service.generate_child_result(route_to, child_prompt)
      → valida ChildResult
      → compose_decision_output(...)
          + guardrails de categoria e outcome
          + monta decision_trace
      → retorna DecisionOutput
```

---

## Contratos

### MotherDecision (saída da LLM Mãe)
| Campo | Tipo | Descrição |
|---|---|---|
| `route_to` | `qualification\|apresentation\|follow-up\|closing` | Rota decidida |
| `perceived_category` | mesmos valores + null | Categoria percebida |
| `confidence` | 0..1 | Confiança da decisão |
| `reason` | string | Justificativa textual |

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

### DecisionOutput (saída final do executor)
Combinação de MotherDecision + ChildResult + guardrails, enviado ao CRM via `complete_job`.

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

### Filha Follow-up (`_build_child_followup_prompt`)
- Monta `followup_summary` com `followup_goal`, `outcome`, `operator_note`, `meeting_happened`, `proposal_sent`
- Inclui regras por variant (`sdr_scheduler` vs `hybrid_scheduler`)
- Instrução prioritária: usar `followup_contract_signals` como fonte principal
- Passa `tone_of_voice`, `custom_instructions`, `offer_description`, `goals`, `niche`, `identity_mode`

### Filha Genérica (`_build_child_prompt`)
- Usada para rotas `closing` e como fallback
- Recebe contexto completo mas sem instrução especializada

---

## Guardrails de estágio

Existem duas camadas de guardrails:

**No executor (`decision_engine.py`):**
- `apply_mother_category_guardrails` — avanço/retrocesso/jump de etapas
- `_apply_child_micro_adjustment` — micro avanço sugerido pela filha em qualification
- `_sanitize_category_decision` — valida categoria permitida no contexto

**No CRM (`jobs_service.apply_suggested_category`):**
- Valida categoria contra `LEAD_CATEGORIES_SET`
- Exige sinal inbound para persistir mudança
- Aplica side effect ao entrar em closing (`apply_closing_bot_disable_side_effect`)

---

## Nota sobre "n8n" no código

O nome "n8n" aparece em identificadores (`TYPE_WHATSAPP_INBOUND_N8N = "whatsapp.inbound.n8n"`) como artefato histórico de uma arquitetura descartada. **n8n nunca foi implantado.** O executor real é o `backend-executors`.

Locais onde o nome aparece:
- `backend-crm/services/jobs_service.py` — constante `TYPE_WHATSAPP_INBOUND_N8N`
- `backend-crm/routes/executor.py` — usa a constante
- `backend-crm/services/followup_channel_context.py` — `expand_type_variants`

Renomear a constante Python é seguro. Renomear o **valor string** exige migração de jobs pendentes no banco.

---

## Arquivos críticos

| Arquivo | Responsabilidade |
|---|---|
| `backend-executors/app/services/decision_engine.py` | Motor de decisão, prompts Mãe e Filhas, guardrails, composição |
| `backend-executors/app/services/llm_service.py` | Chamada HTTP ao LLM (Claude/OpenAI format) |
| `backend-executors/app/services/orchestrator_models.py` | Schemas MotherDecision, ChildResult |
| `backend-executors/app/runners/whatsapp.py` | Executa cada job: contexto → decide → envia |
| `backend-executors/app/services/fast_path.py` | Decisões sem LLM (handoff imediato, bot desabilitado) |
| `backend-executors/app/services/handoff_policy.py` | Política de handoff humano |
| `backend-executors/app/services/meeting_scheduler.py` | Agendamento de reuniões pós-decisão |
| `backend-crm/services/jobs_service.py` | Persistência de categoria sugerida, side effects |
