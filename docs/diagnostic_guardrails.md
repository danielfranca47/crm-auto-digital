# DIAGNÓSTICO — COMPORTAMENTO DE GUARDRAILS E PRIORIDADE DE QUALIFICAÇÃO

## INSTRUÇÕES

Para cada pergunta abaixo:

- Responda diretamente no arquivo
- Aponte:
  - arquivo(s)
  - função(ões)
  - linha(s) aproximadas
- Inclua trecho de código relevante
- Não faça suposições
- Se não encontrar, escreva: NÃO ENCONTRADO

---

## 1. BLOQUEIO DE RESPOSTA AO USUÁRIO

Existe em algum lugar do sistema uma lógica que:

- impede ou ignora a resposta ao usuário
- quando existem campos faltantes de qualificação (`missing_fields` ou equivalente)

### Procurar por:

- condicionais baseadas em:
  - missing_fields
  - required_fields
  - qualification incomplete

### Resposta:

- **Arquivo(s):**
  - `backend-executors/app/services/decision_engine.py` (função `_apply_mode_guardrails`, linha ~682)
  - `backend-crm/services/qualification_guardrails.py` (função `can_advance_from_qualification`, linha ~92)

- **Função(ões):**
  - `_apply_mode_guardrails` — no executor, impede avanço de categoria se missing_fields estiver preenchido
  - `can_advance_from_qualification` — no CRM, bloqueia promoção de categoria Kanban

- **Trecho de código:**

```python
# decision_engine.py ~682 — guardrail modo agenda
if mode == "agenda" and ("availability_window" in missing_fields or "location_preference" in missing_fields):
    if mother_decision.route_to == "closing" or decision.suggested_category == "closing":
        decision.suggested_category = "qualification"
        decision.reason = f"{decision.reason}|guardrail_agenda_missing_booking"

# qualification_guardrails.py ~139
missing_fields = compute_missing_fields(mode, extracted, required_fields_override=required_fields_override)
if missing_fields:
    return False, missing_fields
```

- **Descrição objetiva do comportamento:**
  Existem **dois bloqueios independentes**:
  1. No executor (`_apply_mode_guardrails`): se `missing_fields` não estiver vazio, reverte `suggested_category` para `"qualification"` e bloqueia avanço para `closing` (modo agenda/direto).
  2. No CRM (`can_advance_from_qualification`): bloqueia movimentação Kanban para fora de `qualification` via API (`/api/leads`). Chamado na rota de mudança de categoria.

---

## 2. FORÇAMENTO DE PERGUNTA DE QUALIFICAÇÃO

Existe alguma lógica que:

- força o sistema a fazer uma pergunta
- ao invés de responder o usuário
- quando há campos faltantes

### Procurar por:

- next_action = ask_qualification
- route_to = qualification
- qualquer lógica que priorize pergunta

### Resposta:

- **Arquivo(s):**
  - `backend-executors/app/services/decision_engine.py` (`_build_mother_prompt`, linha ~929 e ~968)

- **Função(ões):**
  - `_build_mother_prompt` — injeta regra obrigatória no prompt da LLM mãe

- **Trecho de código:**

```python
# _build_mother_prompt ~929 — regra injetada diretamente no prompt da LLM mãe
"- REGRA OBRIGATÓRIA DE QUALIFICAÇÃO: se missing_fields não estiver vazio, route_to DEVE ser \"qualification\".\n"
"  EXCEÇÃO FECHO: sinal explícito de confirmação/booking em agent_mode=agenda/sdr_scheduler permite\n"
"  route_to=\"apresentation\" — ver PRIORIDADE 1 EXCEÇÃO FECHO abaixo.\n"

# ~968 — prioridade 1 no prompt
"PRIORIDADE 1 (obrigatória — sistema sobrescreve mesmo se você retornar outra):\n"
"- missing_fields NÃO vazio → route_to = \"qualification\"\n"
```

- **Condição que ativa esse comportamento:**
  `missing_fields` não vazio (calculado por `_build_mode_contract_context` antes de construir o prompt). A regra é textual no prompt da mãe, não código Python — a LLM mãe é instruída a retornar `route_to="qualification"`, o que depois leva a filha qualification a gerar uma pergunta (`should_ask=true`).

---

## 3. PRIORIDADE ENTRE "RESPONDER" VS "PERGUNTAR"

Onde no sistema é decidido:

- se o agente deve responder o usuário
- ou fazer uma pergunta de qualificação

### Procurar por:

- funções de decisão
- orquestração
- decision engine
- lógica de next_action

### Resposta:

- **Arquivo(s):**
  - `backend-executors/app/services/decision_engine.py`
    - Funções `_build_mother_prompt` (linha ~857), `_build_child_prompt_qualification` (linha ~1114)
    - Bloco de modo passivo (`response_style == "passive"`)

- **Função(ões):**
  - `_build_mother_prompt` — define `route_to` (mãe); se `missing_fields` não vazio → `qualification`
  - `_build_child_prompt_qualification` — define se a filha pergunta (`should_ask=true`) ou responde (`should_ask=false`)
  - Variável `_passive_reply_now` — controla se filha responde primeiro quando `response_style=passive` + `next_action_hint=reply`

- **Trecho de código:**

```python
# _build_child_prompt_qualification ~1170
response_style = (ai_profile.get("response_style") or "active").strip().lower()

_escopo_line = (
    "Responder perguntas directas do cliente PRIMEIRO, usando offer_description e custom_instructions. "
    "Depois qualificar de forma natural. ..."
    if response_style == "passive"
    else "Você APENAS faz perguntas de qualificação. ..."
)

_passive_reply_now = response_style == "passive" and _mother_hint == "reply"
_passive_header = (
    "MODO PASSIVO ACTIVADO — RESPOSTA IMEDIATA OBRIGATÓRIA.\n"
    "A mãe sinalizou next_action_hint='reply': ..."
    "INSTRUÇÃO CRÍTICA: coloca TODA a resposta em message_text. NÃO perguntes nada neste turno.\n"
    if _passive_reply_now
    else ...
)
```

- **Critério de decisão identificado:**
  1. Se `response_style == "active"` (padrão): filha qualification **sempre pergunta** quando `missing_fields` não vazio.
  2. Se `response_style == "passive"` e mãe retornou `next_action_hint="reply"`: filha **responde primeiro**, pergunta depois.
  3. Se `response_style == "passive"` sem hint `reply`: filha responde primeiro se houver pergunta direta, depois qualifica.

---

## 4. USO DE `compute_missing_fields`

Onde a função `compute_missing_fields` (ou equivalente):

- é chamada
- e como o resultado dela (`missing`) é utilizado

### Resposta:

- **Arquivo(s):**
  - `backend-executors/app/contracts/qualification_contract.py` — **definição** da função (`compute_missing_fields`, linha ~115)
  - `backend-crm/services/qualification_guardrails.py` — **segunda definição** paralela (linha ~41); usada em `can_advance_from_qualification`
  - `backend-executors/app/services/decision_engine.py` — chamada em `_build_mode_contract_context` (linha ~645)

- **Função(ões):**
  - `compute_missing_fields` (em `qualification_contract.py`) — retorna lista de campos faltantes
  - `_build_mode_contract_context` — chama `compute_missing_fields` e embute resultado em `mode_contract`
  - `can_advance_from_qualification` (CRM) — chama versão local e bloqueia avanço se lista não vazia

- **Trecho de código:**

```python
# qualification_contract.py ~115 (executor)
def compute_missing_fields(agent_mode_normalized, extracted, required_fields_override=None):
    ...
    missing.append(field)
    return missing

# decision_engine.py ~644 — uso no executor
extracted = infer_extracted_fields(context)
missing_fields = compute_missing_fields(mode, extracted, required_fields_override=override)

# qualification_guardrails.py ~139 — uso no CRM
missing_fields = compute_missing_fields(mode, extracted, required_fields_override=required_fields_override)
if missing_fields:
    return False, missing_fields
```

- **O que acontece quando existem campos faltantes:**
  - No **executor**: `mode_contract["missing_fields"]` não vazio → prompt da mãe instrui `route_to="qualification"` → filha qualification pede pergunta (`should_ask=true`).
  - No **CRM**: `can_advance_from_qualification` retorna `(False, missing_fields)` → endpoint de mudança de categoria rejeita a operação.

---

## 5. DEFINIÇÃO DE CAMPOS OBRIGATÓRIOS

Onde são definidos os campos obrigatórios de qualificação:

- required_fields_for_mode
- ou qualquer outra fonte de definição

### Resposta:

- **Arquivo(s):**
  - `backend-executors/app/contracts/qualification_contract.py` — constante `MIN_REQUIRED_FIELDS` (linha ~31)
  - `backend-crm/services/qualification_guardrails.py` — constante `_MIN_REQUIRED_FIELDS` (linha ~10)

- **Função(ões):**
  - `required_fields_for_mode` — existe nas duas cópias; retorna lista para o modo dado, ou o override do AI Profile

- **Estrutura dos campos:**

```python
# qualification_contract.py (executor) — MIN_REQUIRED_FIELDS
"consultivo": ["service_interest", "urgency", "decision_role", "constraints", "availability_window", "budget_or_price_acceptance"]
"agenda":     ["service_interest", "availability_window", "price_acceptance"]
"direto":     ["service_interest", "availability_window", "price_acceptance"]

# qualification_guardrails.py (CRM) — _MIN_REQUIRED_FIELDS
"consultivo": ["service_interest", "urgency", "decision_role", "constraints", "availability_window", "budget_or_price_acceptance"]
"agenda":     ["service_interest", "availability_window", "price_acceptance"]
"direto":     ["service_interest", "availability_window", "price_acceptance"]
```

- **Origem:** **Hardcoded** em dois ficheiros separados (executor e CRM). O AI Profile pode sobrescrever via `qualification_required_fields` (lista enviada no perfil), que é lida por `_get_required_fields_override` no executor e por `_fetch_ai_profile` no CRM.

---

## 6. EXISTÊNCIA DE GUARDRAILS HARDCODED

Existem regras fixas no código que:

- obrigam coleta de dados específicos
- independentemente do AI Profile

### Resposta:

- **Arquivo(s):**
  - `backend-executors/app/services/decision_engine.py` — função `_apply_mode_guardrails` (linha ~661)
  - `backend-executors/app/contracts/qualification_contract.py` — constante `MIN_REQUIRED_FIELDS` (linha ~31)
  - `backend-crm/services/qualification_guardrails.py` — constante `_MIN_REQUIRED_FIELDS` (linha ~10)
  - `backend-crm/services/ai_orchestrator/orchestrator.py` — função `apply_mode_overrides` (linha ~88)

- **Função(ões):**
  - `_apply_mode_guardrails` — regras fixas por modo (agenda, direto, consultivo)
  - `apply_mode_overrides` — injeta `must_collect` fixo para modo agenda

- **Trecho de código:**

```python
# orchestrator.py ~101 — must_collect hardcoded para modo agenda
elif agent_mode_normalized == "agenda":
    merged.update({
        "max_chars": 350,
        "qualification_depth": "medium",
        "must_collect": ["service_interest", "availability_window", "location_preference", "price_acceptance"],
    })

# decision_engine.py ~682 — guardrail agenda hardcoded
if mode == "agenda" and ("availability_window" in missing_fields or "location_preference" in missing_fields):
    if mother_decision.route_to == "closing" or decision.suggested_category == "closing":
        decision.suggested_category = "qualification"

# decision_engine.py ~690 — guardrail direto hardcoded
if mode == "direto":
    signals = _sanitize_signals_structured(mother_decision.signals)
    price_ok = signals.get("price_acceptance") in {"yes", True}
    intent_ok = signals.get("intent_level") in {"medium", "high"}
    if not (price_ok and intent_ok) and (...closing...):
        decision.suggested_category = "qualification"
```

- **Lista de campos hardcoded encontrados:**
  | Campo | Modo | Onde |
  |---|---|---|
  | `availability_window` | agenda, consultivo, direto | `MIN_REQUIRED_FIELDS` (ambos ficheiros) |
  | `price_acceptance` | agenda, direto | `MIN_REQUIRED_FIELDS` (ambos ficheiros) |
  | `service_interest` | todos | `MIN_REQUIRED_FIELDS` (ambos ficheiros) |
  | `urgency` | consultivo | `MIN_REQUIRED_FIELDS` (ambos ficheiros) |
  | `decision_role` | consultivo | `MIN_REQUIRED_FIELDS` (ambos ficheiros) |
  | `constraints` | consultivo | `MIN_REQUIRED_FIELDS` (ambos ficheiros) |
  | `budget_or_price_acceptance` | consultivo | `MIN_REQUIRED_FIELDS` (ambos ficheiros) |
  | `location_preference` | agenda | `apply_mode_overrides` (orchestrator) + guardrail executor |

---

## 7. USO DO AI PROFILE NA QUALIFICAÇÃO

Onde o AI Profile é utilizado para:

- definir perguntas
- definir campos de qualificação

### Resposta:

- **Arquivo(s):**
  - `backend-executors/app/services/decision_engine.py` — `_get_required_fields_override` (linha ~598), `_build_mode_contract_context` (linha ~607)
  - `backend-crm/services/qualification_guardrails.py` — `_fetch_ai_profile` (linha ~74), `can_advance_from_qualification` (linha ~132)
  - `backend-executors/app/services/decision_engine.py` — `_build_child_prompt_qualification` (linha ~1114) usa `ai_profile.tone_of_voice`, `niche`, `agent_mode`, `response_style`, `custom_instructions`

- **Função(ões):**
  - `_get_required_fields_override` — lê `ai_profile.qualification_required_fields` (lista de override)
  - `can_advance_from_qualification` — lê `ai_profile.qualification_required_fields` para override de campos obrigatórios
  - `_build_child_prompt_qualification` — injeta `tone_of_voice`, `niche`, `agent_mode`, `response_style`, `custom_instructions`, `offer_description` do AI Profile no prompt da filha

- **Trecho de código:**

```python
# decision_engine.py ~598
def _get_required_fields_override(context):
    ai_profile = context.get("ai_profile") or {}
    override = ai_profile.get("qualification_required_fields")
    if isinstance(override, list):
        return [str(f) for f in override if isinstance(f, str)]
    return None

# qualification_guardrails.py ~132
ai_profile = _fetch_ai_profile(user_id)
override = ai_profile.get("qualification_required_fields")
required_fields_override = [str(f) for f in override if isinstance(f, str)]
    if isinstance(override, list) else None
```

- **Como os campos/perguntas são carregados:**
  1. `qualification_required_fields` (lista no AI Profile) sobrescreve os campos hardcoded quando presente.
  2. `response_style` (AI Profile) controla se a filha pergunta primeiro ou responde primeiro.
  3. `tone_of_voice`, `niche`, `custom_instructions`, `offer_description` são injetados no prompt textual da filha qualification.
  4. O AI Profile **não define perguntas concretas** — apenas define tom, campos obrigatórios (via override) e estilo de resposta; as perguntas em si são geradas pela LLM filha.

---

## 8. CONFLITO ENTRE AI PROFILE E GUARDRAILS

Existe algum ponto onde:

- dados do AI Profile são ignorados
- ou substituídos por lógica fixa (guardrails)

### Resposta:

- **Arquivo(s):**
  - `backend-executors/app/services/decision_engine.py` — `_apply_mode_guardrails` (linha ~661)
  - `backend-crm/services/ai_orchestrator/orchestrator.py` — `apply_mode_overrides` (linha ~88)

- **Função(ões):**
  - `_apply_mode_guardrails` — sobrescreve `suggested_category` mesmo que o AI Profile configure campos diferentes
  - `apply_mode_overrides` — injeta `must_collect` fixo no playbook, ignorando o que o AI Profile possa ter configurado via template

- **Trecho de código:**

```python
# orchestrator.py ~101 — força must_collect independentemente do AI Profile
elif agent_mode_normalized == "agenda":
    merged.update({
        "must_collect": ["service_interest", "availability_window", "location_preference", "price_acceptance"],
    })

# decision_engine.py ~682 — guardrail reverte category mesmo que a LLM (influenciada pelo AI Profile) tivesse decidido avançar
if mode == "agenda" and ("availability_window" in missing_fields or "location_preference" in missing_fields):
    if mother_decision.route_to == "closing" or decision.suggested_category == "closing":
        decision.suggested_category = "qualification"  # sobrescreve decisão da LLM
```

- **Descrição do conflito:**
  1. Se o AI Profile definir `qualification_required_fields=[]` (lista vazia), `can_advance_from_qualification` no CRM avança (`return True, []`). Mas no executor, `_build_mode_contract_context` também lê o override — se for lista vazia, `missing_fields` fica vazio e o guardrail não activa. **Neste caso os guardrails respeitam o AI Profile.**
  2. Se o AI Profile **não** definir `qualification_required_fields` (None), os campos hardcoded de `MIN_REQUIRED_FIELDS` são usados. O AI Profile não tem forma de remover campos individuais hardcoded, apenas substituir a lista inteira.
  3. `apply_mode_overrides` (orchestrator.py) injeta `must_collect` fixo para modo `agenda` **sem verificar** se o AI Profile configurou campos diferentes — é uma sobreposição unilateral no playbook.

---

## 9. PROMPTS DAS LLMS (MÃE E FILHAS)

Nos prompts das LLMs, existe alguma instrução que:

- força a coleta de todos os dados antes de responder
- prioriza perguntas de qualificação sobre respostas

### Procurar por frases como:

- "ask until all information is collected"
- "do not proceed without"
- "always collect"

### Resposta:

- **Arquivo(s):**
  - `backend-executors/app/services/decision_engine.py`

- **Prompt(s):**
  - Prompt da **mãe** (`_build_mother_prompt`, linha ~857)
  - Prompt da **filha qualification** (`_build_child_prompt_qualification`, linha ~1114)

- **Trecho relevante:**

```
# Prompt mãe (~929) — instrução obrigatória de qualificação
"- REGRA OBRIGATÓRIA DE QUALIFICAÇÃO: se missing_fields não estiver vazio, route_to DEVE ser 'qualification'."
"  Enquanto houver missing_fields E sem sinal de fecho, NÃO sugerir avanço para apresentation, follow-up ou closing."

# Prompt mãe (~968) — prioridade 1
"PRIORIDADE 1 (obrigatória — sistema sobrescreve mesmo se você retornar outra):\n"
"- missing_fields NÃO vazio → route_to = 'qualification'"

# Prompt filha qualification (~1217) — instrução de coleta campo por campo
"PAPEL: Coletar campos de qualificação do lead, um por vez, através de perguntas naturais e contextuais."
"Campos obrigatórios: {required_fields}. Campo atual: {current_field}."

# Prompt filha qualification (~1232) — schema de retorno com should_ask
'"should_ask": true'  # instrui a LLM a sinalizar se deve perguntar

# Prompt filha qualification (~1239) — NÃO agendar sem qualificação
"- NÃO agendar reunião aqui (só na rota apresentation, salvo pedido explícito do inbound)."
```

- **Comportamento induzido:**
  - A LLM mãe é instruída a retornar `route_to="qualification"` enquanto `missing_fields` não estiver vazio. Isso é declarado como "obrigatório" e "sistema sobrescreve".
  - A LLM filha qualification é instruída a perguntar exatamente `current_field` (`should_ask=true`), um campo por turno.
  - Não existe instrução explícita "ask until all information is collected" em texto, mas a combinação de `REGRA OBRIGATÓRIA` + `Campos obrigatórios: {required_fields}` + `should_ask=true` produz esse comportamento iterativo.

---

## 10. DEFINIÇÃO DE MODO ATIVO vs PASSIVO

Existe no sistema alguma lógica que:

- diferencia comportamento ativo (pergunta)
- de comportamento passivo (não pergunta)

### Resposta:

- **Arquivo(s):**
  - `backend-executors/app/services/decision_engine.py`
    - `_build_mother_prompt` (linha ~1025) — bloco passivo na mãe
    - `_build_child_prompt_qualification` (linha ~1170) — controle passivo na filha

- **Função(ões):**
  - `_build_child_prompt_qualification` — lê `ai_profile.response_style` e altera o comportamento da filha
  - `_build_mother_prompt` — se `response_style == "passive"`, injeta instrução para mãe retornar `next_action_hint="reply"` quando há pergunta direta

- **Trecho de código:**

```python
# _build_child_prompt_qualification ~1170
response_style = (ai_profile.get("response_style") or "active").strip().lower()

_escopo_line = (
    "Responder perguntas directas do cliente PRIMEIRO, ... Depois qualificar de forma natural."
    if response_style == "passive"
    else "Você APENAS faz perguntas de qualificação. ..."
)

_passive_reply_now = response_style == "passive" and _mother_hint == "reply"

# _build_mother_prompt ~1025 (bloco injetado apenas quando passive)
"\nMODO PASSIVO (response_style=passive): "
"Se a mensagem do cliente for uma pergunta directa ... "
"E missing_fields NÃO ESTIVER VAZIO, "
"usa next_action_hint='reply' para sinalizar à filha que deve responder a pergunta primeiro."
```

- **Como essa decisão é feita:**
  1. `ai_profile.response_style` é lido pelo executor no momento de construir o prompt.
  2. Se `"active"` (padrão): filha qualification pede campo de qualificação sem olhar para o conteúdo da pergunta do lead.
  3. Se `"passive"`: mãe pode sinalizar `next_action_hint="reply"` quando detecta pergunta direta → filha entra em "MODO PASSIVO ACTIVADO — RESPOSTA IMEDIATA OBRIGATÓRIA" e não pergunta naquele turno.

---

## 11. EXTRAÇÃO DE RESPOSTAS IMPLÍCITAS

Existe alguma lógica que:

- extrai informações da mensagem do usuário
- e preenche automaticamente campos de qualificação

### Resposta:

- **Arquivo(s):**
  - `backend-executors/app/contracts/qualification_contract.py` — função `infer_extracted_fields` (linha ~72)
  - `backend-executors/app/services/field_extractor.py` — função `extract_fields_llm` (linha ~44) — via LLM

- **Função(ões):**
  - `infer_extracted_fields` — extração heurística (regex + keywords) sem LLM
  - `extract_fields_llm` — extração via LLM com schema de campos
  - `_build_mode_contract_context` — usa `infer_extracted_fields` como fallback quando `qualification_state` está ausente

- **Trecho de código:**

```python
# qualification_contract.py ~72
def infer_extracted_fields(context):
    text = _text_from_context(context).lower()
    extracted = {}
    if any(k in text for k in ["quero", "interesse", "serviço", ...]):
        extracted["service_interest"] = True
    if _DAY_OR_TIME_RE.search(text):
        extracted["availability_window"] = True
    if any(k in text for k in ["bairro", "cidade", "presencial", "online", ...]):
        extracted["location_preference"] = True
    price_yes_terms = ["aceito", "ok o preço", ...]
    price_no_terms = ["caro", "muito caro", ...]
    ...
    return extracted
```

- **Campos suportados:**
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

  Esta extração heurística é usada como **fallback** quando o `qualification_state` do banco não existe. A extração principal usa LLM via `field_extractor.extract_fields_llm`, que é chamada pelo runner do executor após cada turno e persiste os campos em `lead_qualification_state` no CRM.

---

## 12. FLUXO COMPLETO DE DECISÃO

Mapear o fluxo completo desde:

entrada da mensagem do usuário → até decisão final do agente

### Resposta:

- **Sequência de funções chamadas:**

```
1. [CRM] POST /webhooks/whatsapp/inbound
   └─ handle_inbound()                              [inbound_handler.py]
       ├─ normaliza telefone, idempotência, cria/encontra lead
       ├─ save_inbound_message()                    [inbound_handler.py]
       ├─ stop_followup_on_inbound_reply()          [followup_state.py]
       ├─ build_context_bundle_from_inbound()       [orchestrator.py]
       │   ├─ fetch_core_ai_profile_resolve()       [core_client.py]
       │   ├─ _normalize_agent_mode_for_bundle()    [orchestrator.py]
       │   ├─ _resolve_presentation_contract()      [orchestrator.py]
       │   └─ get_recent_history()                  [history.py]
       └─ create_job(type=whatsapp.inbound.n8n)     [jobs_service.py]
          → job entra na fila

2. [Executor] whatsapp_worker.py — polling da fila
   └─ execute_job()                                 [runners/whatsapp.py]
       └─ decision_engine (via LLM)                 [services/decision_engine.py]
           ├─ fast_path.try_fast_handoff()          [fast_path.py]  ← sai cedo se handoff keyword
           ├─ _build_mode_contract_context()        [decision_engine.py]
           │   ├─ _qualification_state_from_context()  [lê qualification_state do CRM]
           │   ├─ compute_missing_fields()          [qualification_contract.py]
           │   └─ infer_extracted_fields() (fallback) [qualification_contract.py]
           ├─ _build_mother_prompt()                [decision_engine.py]
           │   └─ injeta missing_fields, regra obrigatória, modo passivo
           ├─ LLM chamada (mãe) → MotherDecision    [llm_service.py]
           │   └─ retorna route_to (qualification|apresentation|follow-up|closing)
           ├─ seleciona prompt filha por route_to:
           │   ├─ route_to=qualification → _build_child_prompt_qualification()
           │   ├─ route_to=apresentation → _build_child_prompt_apresentation()
           │   └─ route_to=follow-up/closing → _build_child_prompt()
           ├─ LLM chamada (filha) → ChildResult     [llm_service.py]
           │   └─ retorna message_text, should_ask, field, signals_structured
           ├─ _apply_mode_guardrails()              [decision_engine.py]  ← guardrails pós-LLM
           ├─ _sanitize_category_decision()         [decision_engine.py]
           └─ envia mensagem via UazAPI + persiste qualification_state no CRM
```

- **Arquivos envolvidos:**
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

- **Ponto onde decide responder:**
  - `route_to` da mãe ≠ `"qualification"` → filha não-qualification → `message_text` com resposta
  - OU `response_style=passive` + `next_action_hint=reply` → filha qualification responde sem perguntar (`should_ask=false`)

- **Ponto onde decide perguntar:**
  - `missing_fields` não vazio + `response_style=active` → mãe retorna `route_to="qualification"` → filha qualification retorna `should_ask=true` com `question_text` para o campo `current_field`

---
