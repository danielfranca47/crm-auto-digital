# DIAGNÓSTICO — COMPORTAMENTO DE GUARDRAILS E PRIORIDADE DE QUALIFICAÇÃO

> Reflexo atualizado do código. Cada resposta aponta arquivo, função e linha aproximada com trecho real.

---

## 1. BLOQUEIO DE RESPOSTA AO USUÁRIO

Existe em algum lugar do sistema uma lógica que impede ou ignora a resposta ao usuário quando existem campos faltantes de qualificação (`missing_fields`)?

**Arquivos:**
- `backend-executors/app/services/decision_engine.py` (função `_apply_mode_guardrails`, linha ~731)
- `backend-crm/services/qualification_guardrails.py` (função `can_advance_from_qualification`, linha ~69)

**Funções:**
- `_apply_mode_guardrails` — no executor, impede avanço de categoria para `closing` se `missing_fields` estiver preenchido (modos agenda e direto)
- `can_advance_from_qualification` — no CRM, bloqueia promoção de categoria Kanban; agora verifica dois critérios: campos obrigatórios em falta **e** score mínimo abaixo do threshold

**Trecho de código:**

```python
# decision_engine.py ~752 — guardrail modo agenda
if mode == "agenda" and ("availability_window" in missing_fields or "location_preference" in missing_fields):
    if mother_decision.route_to == "closing" or decision.suggested_category == "closing":
        decision.suggested_category = "qualification"
        decision.reason = f"{decision.reason}|guardrail_agenda_missing_booking"

# qualification_guardrails.py ~116 — verificação 1: campos
missing_fields = compute_missing_fields(mode, extracted, required_fields_override=required_fields_override)
if missing_fields:
    return False, missing_fields

# qualification_guardrails.py ~126 — verificação 2: score
if required_fields_override is not None and len(required_fields_override) == 0:
    return True, []  # lista vazia explícita = avança sempre
if total_score < threshold_int:
    return False, [f"score_{total_score}_of_12_below_threshold_{threshold_int}"]
```

**Comportamento:**
Existem dois bloqueios independentes:
1. No executor (`_apply_mode_guardrails`): se `missing_fields` não estiver vazio (modos agenda/direto), reverte `suggested_category` para `"qualification"`.
2. No CRM (`can_advance_from_qualification`): bloqueia movimentação Kanban. Verifica (a) campos obrigatórios em falta e (b) `qualification_total_score` abaixo do `qualification_score_threshold` do AI Profile (default: 6 de 12).

---

## 2. FORÇAMENTO DE PERGUNTA DE QUALIFICAÇÃO

Existe alguma lógica que força o sistema a fazer uma pergunta ao invés de responder o usuário quando há campos faltantes?

**Arquivo:**
- `backend-executors/app/services/decision_engine.py` (`_build_mother_prompt`, linha ~963)

**Função:**
- `_build_mother_prompt` — injeta regras de prioridade no prompt da LLM mãe

**Trecho:**

```python
# _build_mother_prompt ~1043 — PRIORIDADE 1 no prompt
"PRIORIDADE 1 (obrigatória — sistema sobrescreve mesmo se você retornar outra):\n"
"- PRIORIDADE 1A: missing_fields NÃO vazio + mensagem SEM pergunta direta → route_to = \"qualification\"\n"
"- PRIORIDADE 1B: missing_fields NÃO vazio + mensagem COM pergunta direta (serviços, preço, como\n"
"  funciona, horários, etc.) → route_to = \"qualification\", next_action_hint = \"reply\"\n"
"  (filha responde à pergunta antes de qualificar — NUNCA ignore uma pergunta direta do lead)\n"
"  EXCEÇÃO FECHO (agent_mode=agenda/sdr_scheduler): se a mensagem contiver sinal EXPLÍCITO de\n"
"  confirmação/booking → route_to = \"apresentation\" mesmo com missing_fields.\n"
```

**Condição que ativa:**
`missing_fields` não vazio (calculado por `_build_mode_contract_context`). A regra é textual no prompt da mãe. Há duas sub-prioridades:
- **1A** — sem pergunta direta: filha qualification gera pergunta (`should_ask=true`)
- **1B** — com pergunta direta: mãe retorna `next_action_hint="reply"` → filha responde primeiro, qualifica depois

---

## 3. PRIORIDADE ENTRE "RESPONDER" VS "PERGUNTAR"

Onde é decidido se o agente deve responder o usuário ou fazer uma pergunta de qualificação?

**Arquivo:**
- `backend-executors/app/services/decision_engine.py`
  - `_build_mother_prompt` (linha ~927) — decide `route_to` e `next_action_hint`
  - `_build_child_prompt_qualification` (linha ~1192) — decide `should_ask` e conteúdo da resposta

**Trecho:**

```python
# _build_child_prompt_qualification ~1248 — default de response_style é agora "passive"
response_style = (ai_profile.get("response_style") or "passive").strip().lower()

# escopo para passive:
_escopo_line = (
    "Responder perguntas directas do cliente PRIMEIRO, usando offer_description e custom_instructions. "
    "Depois qualificar de forma natural. ..."
    if response_style == "passive"
    else (
        # escopo para active — também responde primeiro, depois qualifica
        "Responde SEMPRE à mensagem do cliente antes de qualificar. Se o cliente fez uma pergunta, "
        "responde usando offer_description e custom_instructions. Depois, se houver campos obrigatórios "
        "em falta, adicione UMA pergunta de qualificação natural ao final. ..."
    )
)

# _passive_reply_now: modo passivo + mãe sinalizou "reply"
_passive_reply_now = response_style == "passive" and _mother_hint == "reply"
```

**Critério de decisão:**
1. `response_style == "passive"` (default atual) + mãe retornou `next_action_hint="reply"`: filha entra em "MODO PASSIVO ACTIVADO — RESPOSTA IMEDIATA OBRIGATÓRIA" (`should_ask=false`, sem pergunta neste turno).
2. `response_style == "passive"` sem hint `reply`: filha responde primeiro se houver pergunta direta, depois qualifica de forma natural.
3. `response_style == "active"`: filha também responde antes de qualificar, mas pode adicionar uma pergunta de qualificação ao final do mesmo turno.

> **Mudança importante:** o default de `response_style` passou de `"active"` para `"passive"`.

---

## 4. USO DE `compute_missing_fields`

Onde a função `compute_missing_fields` é chamada e como o resultado é utilizado?

**Arquivos:**
- `backend-executors/app/contracts/qualification_contract.py` — definição da função (linha ~94)
- `backend-crm/services/qualification_guardrails.py` — segunda definição paralela (linha ~18); usada em `can_advance_from_qualification`
- `backend-executors/app/services/decision_engine.py` — chamada em `_build_mode_contract_context` (linha ~715)

**Funções:**
- `compute_missing_fields` (executor) — retorna lista de campos faltantes com base em `required_fields_override`
- `_build_mode_contract_context` — chama `compute_missing_fields` e embute resultado em `mode_contract`
- `can_advance_from_qualification` (CRM) — chama versão local e bloqueia avanço se lista não vazia ou score insuficiente

**Trecho:**

```python
# qualification_contract.py ~94 (executor)
def compute_missing_fields(agent_mode_normalized, extracted, required_fields_override=None):
    if required_fields_override is not None:
        required = required_fields_override
    else:
        required = []  # Sem configuração no AI Profile = sem campos obrigatórios
    ...
    return missing

# decision_engine.py ~715 — uso no executor (fallback heurístico)
extracted = infer_extracted_fields(context)
missing_fields = compute_missing_fields(mode, extracted, required_fields_override=override)

# qualification_guardrails.py ~116 — uso no CRM
missing_fields = compute_missing_fields(mode, extracted, required_fields_override=required_fields_override)
if missing_fields:
    return False, missing_fields
```

**O que acontece quando existem campos faltantes:**
- No **executor**: `mode_contract["missing_fields"]` não vazio → prompt da mãe instrui `route_to="qualification"` → filha qualification gera pergunta (`should_ask=true`), ou responde primeiro se `next_action_hint="reply"`.
- No **CRM**: `can_advance_from_qualification` retorna `(False, missing_fields)` → endpoint de mudança de categoria rejeita a operação.

---

## 5. DEFINIÇÃO DE CAMPOS OBRIGATÓRIOS

Onde são definidos os campos obrigatórios de qualificação?

**Arquivos:**
- `backend-executors/app/contracts/qualification_contract.py` — função `required_fields_for_mode` (linha ~115)
- `backend-crm/services/qualification_guardrails.py` — função `required_fields_for_mode` (linha ~9)

**Comportamento atual:**

```python
# qualification_contract.py ~115 (executor)
def required_fields_for_mode(agent_mode_normalized, required_fields_override=None):
    if required_fields_override is not None:
        return list(required_fields_override)
    return []  # Sem configuração no AI Profile = sem campos obrigatórios

# qualification_guardrails.py ~9 (CRM) — idêntico
def required_fields_for_mode(agent_mode_normalized, required_fields_override=None):
    if required_fields_override is not None:
        return list(required_fields_override)
    return []  # Sem configuração no AI Profile = sem campos obrigatórios
```

> **Mudança importante:** as constantes `MIN_REQUIRED_FIELDS` e `_MIN_REQUIRED_FIELDS` (com campos hardcoded por modo) foram removidas. Sem `required_fields_override` configurado no AI Profile, **nenhum campo é obrigatório por padrão**.

**Fonte dos campos:**
- Exclusivamente via `qualification_required_fields` (lista de strings no AI Profile) — lida por `_get_required_fields_override` no executor e por `_fetch_ai_profile` no CRM.
- Ou via `qualification_fields` (lista de objetos com `key`, `label`, `question`, `passive_hint`, `mode`) — processada por `_build_qualification_context` no orchestrator (backward compat: se não existir, usa `qualification_required_fields`).

---

## 6. EXISTÊNCIA DE GUARDRAILS HARDCODED

Existem regras fixas no código que obrigam coleta de dados específicos independentemente do AI Profile?

**Arquivos:**
- `backend-executors/app/services/decision_engine.py` — função `_apply_mode_guardrails` (linha ~731)
- `backend-crm/services/ai_orchestrator/orchestrator.py` — função `apply_mode_overrides` (linha ~136)

**Trecho:**

```python
# orchestrator.py ~149 — modo agenda: must_collect só injetado se AI Profile definiu campos
elif agent_mode_normalized == "agenda":
    merged.update({
        "max_chars": 350,
        "qualification_depth": "medium",
    })
    profile_fields = (ai_profile or {}).get("qualification_required_fields")
    if isinstance(profile_fields, list) and len(profile_fields) > 0:
        merged.update({"must_collect": profile_fields})
    # profile_fields == None → sem override automático
    # profile_fields == [] → modo passivo, sem must_collect

# decision_engine.py ~752 — guardrail agenda hardcoded (ainda existe)
if mode == "agenda" and ("availability_window" in missing_fields or "location_preference" in missing_fields):
    if mother_decision.route_to == "closing" or decision.suggested_category == "closing":
        decision.suggested_category = "qualification"

# decision_engine.py ~760 — guardrail direto hardcoded (ainda existe)
if mode == "direto":
    signals = _sanitize_signals_structured(mother_decision.signals)
    price_ok = signals.get("price_acceptance") in {"yes", True}
    intent_ok = signals.get("intent_level") in {"medium", "high"}
    if not (price_ok and intent_ok) and (...closing...):
        decision.suggested_category = "qualification"

# decision_engine.py ~741 — guardrail consultivo: bloqueia outcome=won e força handoff em closing
if mode == "consultivo" and decision.outcome == "won":
    decision.outcome = None
if mode == "consultivo" and mother_decision.route_to == "closing":
    decision.decision_trace["next_action_hint"] = "handoff"
```

**Guardrails fixos por modo:**
| Regra | Modo | Arquivo |
|---|---|---|
| `availability_window` ou `location_preference` em falta → revert to qualification | agenda | `_apply_mode_guardrails` |
| `price_acceptance` não "yes" ou `intent_level` não medium/high → revert to qualification | direto | `_apply_mode_guardrails` |
| `outcome=won` bloqueado | consultivo | `_apply_mode_guardrails` |
| `route_to=closing` → força handoff | consultivo | `_apply_mode_guardrails` |

> **Mudança importante:** `apply_mode_overrides` no orchestrator **não injeta mais `must_collect` hardcoded** para modo agenda. O bloco agora só injeta se o AI Profile tiver `qualification_required_fields` configurado explicitamente.

---

## 7. USO DO AI PROFILE NA QUALIFICAÇÃO

Onde o AI Profile é utilizado para definir campos de qualificação?

**Arquivos:**
- `backend-executors/app/services/decision_engine.py` — `_get_required_fields_override` (linha ~598), `_build_mode_contract_context` (linha ~677)
- `backend-crm/services/qualification_guardrails.py` — `_fetch_ai_profile` (linha ~51), `can_advance_from_qualification` (linha ~69)
- `backend-crm/services/ai_orchestrator/orchestrator.py` — `_build_qualification_context` (linha ~88), `apply_mode_overrides` (linha ~136)

**Funções:**
- `_get_required_fields_override` — lê `ai_profile.qualification_required_fields` (lista de keys)
- `can_advance_from_qualification` — lê `ai_profile.qualification_required_fields` e `qualification_score_threshold`
- `_build_qualification_context` — processa `qualification_fields` (formato rico: `key`, `label`, `question`, `passive_hint`, `mode`); backward compat com `qualification_required_fields`

**Trecho:**

```python
# decision_engine.py ~598
def _get_required_fields_override(context):
    ai_profile = context.get("ai_profile") or {}
    override = ai_profile.get("qualification_required_fields")
    if isinstance(override, list):
        return [str(f) for f in override if isinstance(f, str)]
    return None

# qualification_guardrails.py ~109
override = ai_profile.get("qualification_required_fields")
required_fields_override = [str(f) for f in override if isinstance(f, str)] if isinstance(override, list) else None

# orchestrator.py ~88 — formato rico
def _build_qualification_context(ai_profile):
    qual_fields = profile.get("qualification_fields")
    if not isinstance(qual_fields, list) or len(qual_fields) == 0:
        # fallback para lista simples
        required_keys = profile.get("qualification_required_fields")
        ...
    must_collect_with_questions = [f for f in qual_fields if f.get("mode") == "required"]
    nice_to_collect = [f for f in qual_fields if f.get("mode") == "optional"]
```

**Como os campos são carregados:**
1. `qualification_fields` (lista de objetos com `key`, `label`, `question`, `passive_hint`, `mode`) — formato rico, gerado na UI de configuração.
2. `qualification_required_fields` (lista de strings) — formato legado, ainda suportado via backward compat.
3. `qualification_score_threshold` — threshold de score mínimo (4Ps, default 6 de 12) para `can_advance_from_qualification`.
4. `response_style` — controla se a filha responde primeiro ou qualifica diretamente.
5. `tone_of_voice`, `niche`, `custom_instructions`, `offer_description` — injetados no prompt textual da filha.

---

## 8. CONFLITO ENTRE AI PROFILE E GUARDRAILS

Existe algum ponto onde dados do AI Profile são ignorados ou substituídos por lógica fixa?

**Arquivos:**
- `backend-executors/app/services/decision_engine.py` — `_apply_mode_guardrails` (linha ~731)
- `backend-crm/services/ai_orchestrator/orchestrator.py` — `apply_mode_overrides` (linha ~136)

**Trecho:**

```python
# decision_engine.py ~752 — guardrail agenda sobrescreve decisão da LLM
if mode == "agenda" and ("availability_window" in missing_fields or "location_preference" in missing_fields):
    if ...:
        decision.suggested_category = "qualification"  # sobrescreve mesmo que LLM retorne closing

# orchestrator.py ~154 — must_collect só injetado se AI Profile configurou (não há mais sobreposição automática)
profile_fields = (ai_profile or {}).get("qualification_required_fields")
if isinstance(profile_fields, list) and len(profile_fields) > 0:
    merged.update({"must_collect": profile_fields})
```

**Comportamento atual:**
1. Se o AI Profile definir `qualification_required_fields=[]` (lista vazia), `can_advance_from_qualification` retorna `True` (avança sempre) e `compute_missing_fields` retorna `[]` (sem campos obrigatórios). Os guardrails de campos respeitam completamente o AI Profile.
2. Se o AI Profile **não** definir `qualification_required_fields` (None), `required_fields` fica `[]` e **nenhum campo é exigido**. O sistema age como se todos os campos já estivessem preenchidos — exceto os guardrails hardcoded de `_apply_mode_guardrails` (agenda: `availability_window`/`location_preference`; direto: `price_acceptance`/`intent_level`).
3. `apply_mode_overrides` (orchestrator) **não sobrepõe mais** `must_collect` para modo agenda sem configuração explícita. O conflito descrito anteriormente foi eliminado.

---

## 9. PROMPTS DAS LLMS (MÃE E FILHAS)

Nos prompts das LLMs, existe instrução que força coleta de dados antes de responder?

**Arquivo:**
- `backend-executors/app/services/decision_engine.py`
  - Prompt mãe: `_build_mother_prompt` (linha ~927)
  - Prompt filha qualification: `_build_child_prompt_qualification` (linha ~1192)

**Trechos relevantes:**

```
# Prompt mãe (~972) — instrução de qualificação
"1. O lead tem missing_fields? Se sim → qualification (obrigatório)"

# Prompt mãe (~1043) — PRIORIDADE 1A/1B
"PRIORIDADE 1 (obrigatória — sistema sobrescreve mesmo se você retornar outra):\n"
"- PRIORIDADE 1A: missing_fields NÃO vazio + mensagem SEM pergunta direta → route_to = \"qualification\"\n"
"- PRIORIDADE 1B: missing_fields NÃO vazio + mensagem COM pergunta direta → route_to = \"qualification\",
  next_action_hint = \"reply\""
"  EXCEÇÃO FECHO (agent_mode=agenda): sinal explícito de confirmação/booking → route_to = \"apresentation\""

# Prompt filha qualification (~1305) — campo por vez
"PAPEL: Coletar campos de qualificação do lead, um por vez, através de perguntas naturais e contextuais."
"FRAMEWORK: ... Campos obrigatórios: {required_fields}. Campo atual: {current_field}."

# Prompt filha qualification (~1327) — regra should_ask
"- Quando should_ask=true, field deve ser EXATAMENTE o current_field."
"- Quando should_ask=true, question_text não pode ser vazio."

# Prompt filha qualification — escopo active (responde sempre primeiro)
"Responde SEMPRE à mensagem do cliente antes de qualificar. Se o cliente fez uma pergunta,
responde usando offer_description e custom_instructions. Depois, se houver campos obrigatórios
em falta, adicione UMA pergunta de qualificação natural ao final."
```

**Comportamento induzido:**
- A mãe é instruída a retornar `route_to="qualification"` enquanto `missing_fields` não estiver vazio, mas com distinção entre pergunta direta (1B, responde primeiro) e não-direta (1A, qualifica direto).
- A filha qualification pergunta exatamente `current_field` (`should_ask=true`), um campo por turno.
- Em ambos os `response_style` (`passive` e `active`), a filha responde primeiro se houver pergunta direta — a diferença é que no `active` pode adicionar uma pergunta de qualificação ao final do mesmo turno.

---

## 10. DEFINIÇÃO DE MODO ATIVO vs PASSIVO

Existe no sistema alguma lógica que diferencia comportamento ativo (pergunta) de passivo (não pergunta)?

**Arquivo:**
- `backend-executors/app/services/decision_engine.py`
  - `_build_mother_prompt` (linha ~1102) — bloco passivo na mãe
  - `_build_child_prompt_qualification` (linha ~1248) — controle passivo/ativo na filha

**Trecho:**

```python
# _build_child_prompt_qualification ~1248
response_style = (ai_profile.get("response_style") or "passive").strip().lower()  # default: passive

# escopo passive
_escopo_line = "Responder perguntas directas do cliente PRIMEIRO. Depois qualificar de forma natural. ..."

# escopo active (também responde primeiro, mas pode adicionar pergunta ao final)
_escopo_line = "Responde SEMPRE à mensagem do cliente antes de qualificar. ... Depois, se houver campos
obrigatórios em falta, adicione UMA pergunta de qualificação natural ao final."

_passive_reply_now = response_style == "passive" and _mother_hint == "reply"
# → "MODO PASSIVO ACTIVADO — RESPOSTA IMEDIATA OBRIGATÓRIA. should_ask=false. NÃO perguntes nada neste turno."

# _build_mother_prompt ~1102 — bloco passivo injetado somente quando response_style=passive
"\nMODO PASSIVO (response_style=passive): "
"Se a mensagem do cliente for uma pergunta directa ... "
"E missing_fields NÃO ESTIVER VAZIO, "
"usa next_action_hint='reply' para sinalizar à filha que deve responder a pergunta primeiro.\n"
```

**Como a decisão é feita:**
1. `response_style == "passive"` (default) + `next_action_hint="reply"` da mãe → filha responde sem perguntar neste turno (`should_ask=false`).
2. `response_style == "passive"` sem hint `reply` → filha responde primeiro a perguntas diretas, depois qualifica naturalmente.
3. `response_style == "active"` → filha responde à mensagem e pode adicionar uma pergunta de qualificação ao final do mesmo turno.

> **Mudança importante:** o default mudou de `"active"` para `"passive"`.

---

## 11. EXTRAÇÃO DE RESPOSTAS IMPLÍCITAS

Existe alguma lógica que extrai informações da mensagem do usuário e preenche automaticamente campos de qualificação?

**Arquivos:**
- `backend-executors/app/contracts/qualification_contract.py` — função `infer_extracted_fields` (linha ~51)
- `backend-executors/app/services/field_extractor.py` — função `extract_fields_llm` (linha ~44) — via LLM

**Funções:**
- `infer_extracted_fields` — extração heurística (regex + keywords) sem LLM; usada como fallback em `_build_mode_contract_context`
- `extract_fields_llm` — extração via LLM com schema de campos; chamada pelo runner após cada turno e persiste em `lead_qualification_state` no CRM
- `_build_mode_contract_context` — usa `infer_extracted_fields` como fallback quando `qualification_state` do banco não está disponível

**Trecho:**

```python
# qualification_contract.py ~51
def infer_extracted_fields(context):
    text = _text_from_context(context).lower()
    extracted = {}
    if any(k in text for k in ["quero", "interesse", "serviço", "procedimento", "produto"]):
        extracted["service_interest"] = True
    if _DAY_OR_TIME_RE.search(text):
        extracted["availability_window"] = True
    if any(k in text for k in ["bairro", "cidade", "presencial", "online", "local"]):
        extracted["location_preference"] = True
    price_yes_terms = ["aceito", "ok o preço", ...]
    price_no_terms = ["caro", "muito caro", ...]
    ...
    return extracted
```

**Campos suportados:**
| Campo | Método de extração |
|---|---|
| `service_interest` | keywords: "quero", "interesse", "serviço", "procedimento", "produto" |
| `availability_window` | regex de dias/horários (`_DAY_OR_TIME_RE`) |
| `location_preference` | keywords: "bairro", "cidade", "presencial", "online", "local" |
| `price_acceptance` | keywords positivas/negativas + "unsure" |
| `budget_or_price_acceptance` | co-extraído com `price_acceptance` |
| `decision_role` | keywords: "eu decido", "decisor", "meu sócio", "aprovação" |
| `urgency` | keywords: "urgente", "hoje", "amanhã", "quanto antes" |
| `constraints` | keywords: "só de manhã", "não posso", "restrição" |
| `next_step` | keywords: "me chama", "próximo passo", "pode me ligar" |
| `next_step_with_time` | `next_step` + regex de dia/hora |

Esta extração heurística é usada como **fallback** quando o `qualification_state` do banco não existe. A extração principal usa LLM via `field_extractor.extract_fields_llm`, chamada pelo runner após cada turno e persistida em `lead_qualification_state` no CRM.

---

## 12. FLUXO COMPLETO DE DECISÃO

Fluxo completo desde entrada da mensagem até decisão final do agente:

```
1. [CRM] POST /webhooks/whatsapp/inbound
   └─ handle_inbound()                              [inbound_handler.py]
       ├─ normaliza telefone, idempotência, cria/encontra lead
       ├─ save_inbound_message()
       ├─ stop_followup_on_inbound_reply()          [followup_state.py]
       ├─ build_context_bundle_from_inbound()       [orchestrator.py]
       │   ├─ fetch_core_ai_profile_resolve()       [core_client.py]
       │   ├─ _normalize_agent_mode_for_bundle()
       │   ├─ _resolve_presentation_contract()
       │   ├─ apply_mode_overrides()                ← injeta must_collect só se AI Profile configurou
       │   └─ get_recent_history()                  [history.py]
       └─ create_job(type=whatsapp.inbound.n8n)     [jobs_service.py]

2. [Executor] whatsapp_worker.py — polling da fila
   └─ execute_job()                                 [runners/whatsapp.py]
       └─ decision_engine                           [services/decision_engine.py]
           ├─ fast_path.try_fast_handoff()          [fast_path.py]  ← sai cedo se handoff keyword
           ├─ _build_mode_contract_context()
           │   ├─ _qualification_state_from_context()  [lê lead_qualification_state do CRM]
           │   ├─ required_fields_for_mode()        [qualification_contract.py]
           │   ├─ compute_missing_fields()          [qualification_contract.py]
           │   └─ infer_extracted_fields() (fallback heurístico)
           ├─ _build_mother_prompt()
           │   └─ injeta missing_fields, PRIORIDADE 1A/1B, modo passivo
           ├─ LLM (mãe) → MotherDecision
           │   └─ retorna route_to + next_action_hint
           ├─ seleciona prompt filha por route_to:
           │   ├─ route_to=qualification → _build_child_prompt_qualification()
           │   ├─ route_to=apresentation → _build_child_prompt_apresentation()
           │   └─ route_to=follow-up/closing → _build_child_prompt()
           ├─ LLM (filha) → ChildResult
           │   └─ retorna message_text, should_ask, field, signals_structured
           ├─ _apply_mode_guardrails()              ← guardrails pós-LLM
           ├─ _sanitize_category_decision()
           └─ envia mensagem via UazAPI + persiste qualification_state no CRM
```

**Arquivos envolvidos:**
- `backend-crm/services/whatsapp_inbound/inbound_handler.py`
- `backend-crm/services/ai_orchestrator/orchestrator.py`
- `backend-crm/services/jobs_service.py`
- `backend-executors/app/runners/whatsapp.py`
- `backend-executors/app/services/decision_engine.py`
- `backend-executors/app/services/fast_path.py`
- `backend-executors/app/contracts/qualification_contract.py`
- `backend-executors/app/services/field_extractor.py`
- `backend-executors/app/services/llm_service.py`
- `backend-crm/services/qualification_guardrails.py` (apenas para movimentação Kanban via API)

**Ponto onde decide responder:**
- `route_to` da mãe ≠ `"qualification"` → filha não-qualification → `message_text` com resposta
- OU `_passive_reply_now=True` (`response_style=passive` + `next_action_hint=reply`) → filha qualification responde sem perguntar (`should_ask=false`)

**Ponto onde decide perguntar:**
- `missing_fields` não vazio + mãe retorna `route_to="qualification"` sem `next_action_hint="reply"` → filha qualification retorna `should_ask=true` com `question_text` para o `current_field`
