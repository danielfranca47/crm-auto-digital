# Prompts LLM — Referência Oficial

> **Atualizado em:** 2026-04-16
> **Escopo:** Todos os prompts enviados a LLMs no sistema
> **Arquivos cobertos:**
> - [`backend-executors/app/services/decision_engine.py`](../backend-executors/app/services/decision_engine.py) — Motor de decisão (WhatsApp inbound)
> - [`backend-executors/app/services/field_extractor.py`](../backend-executors/app/services/field_extractor.py) — Extração de campos
> - [`backend-crm/automations/assistente_ia/llm.py`](../backend-crm/automations/assistente_ia/llm.py) — Geração de outreach

---

## Índice rápido para avaliadores

| Seção | Prompt | Agente(s) | Output | Tem exemplos? |
|---|---|---|---|---|
| 1.1 | `_build_prompt()` | Todos (fallback) | JSON DecisionOutput | Não |
| 1.2 | `_build_mother_prompt()` | Todos | JSON MotherDecision | Sim (11 casos) |
| 1.3 | `_build_child_prompt_qualification()` | Todos | JSON ChildResult | Não (usa training_examples) |
| 1.4 | `_build_child_prompt_apresentation()` | Todos | JSON ChildResult | Sim (2 casos sales) |
| 1.5 | `_build_child_prompt_follow_up()` | Todos | JSON ChildResult | Não |
| 1.6 | `_build_child_prompt_closing()` | Todos | JSON ChildResult | Não |
| 1.7 | `_build_child_prompt()` | Todos (fallback) | JSON ChildResult | Não |
| 2 | `field_extractor.py` | Todos | JSON extração | Não |
| 3 | `llm.py` (outreach) | Agent Local | Texto/JSON por canal | Não |

---

## Visão geral da arquitetura de prompts

O sistema usa **três tipos de LLM** com propósitos distintos:

| Tipo | Arquivo | Papel |
|---|---|---|
| **Decisão / Execução** | `decision_engine.py` | Processa inbound WhatsApp; roteia o lead pelo funil (Mãe) e gera a resposta comercial (Filha) |
| **Extração** | `field_extractor.py` | Extrai campos de qualificação estruturados da conversa |
| **Outreach** | `llm.py` | Gera cold outreach (e-mail, WhatsApp, Instagram, roteiro de ligação) para prospecção |

**Regra absoluta de output:** todos os prompts de `decision_engine.py` e `field_extractor.py` retornam **SOMENTE JSON válido** — sem texto livre, sem markdown. A LLM em `llm.py` retorna texto ou JSON dependendo do canal.

---

## Contexto que chega a todos os prompts do `decision_engine`

Antes de entrar em cada prompt individualmente, é importante entender o **ContextBundle** — o objeto que o `backend-crm` monta e envia ao executor. Todos os prompts extraem dados deste bundle.

```
ContextBundle {
  lead             — dados do lead (id, nome, categoria, segmento, status)
  ai_profile       — perfil de IA configurado pelo usuário (vem do backend-core)
  playbook         — template/playbook do agente
  metadata         — inbound_message_text, instance_id, provider, lead_origin,
                     lead_origin_label, followup_context, allowed_lead_categories,
                     force_presentation_variant
  history          — histórico da conversa (últimas N mensagens, [{model, body}])
  qualification_state — estado atual de qualificação do lead (data_json, attempts_json,
                        asked_questions_json, last_question_text)
  knowledge_items  — base de conhecimento do usuário (dict por categoria)
  knowledge_media  — chaves das categorias que têm mídia (set)
  training_examples — exemplos classificados pelo operador no Playground (bom/ruim por fase)
  generated_prompt_parts — blocos gerados pelo meta-prompter (few-shot por fase,
                           tone_rules, qualification_phrasing, objection_rewrites,
                           outreach_scenarios)
}
```

---

## 1. Motor de Decisão — `decision_engine.py`

### Por que a arquitetura Mãe + Filha?

A LLM Mãe e as LLMs Filhas são **duas chamadas separadas ao modelo**. Esta divisão existe por motivos funcionais e de qualidade:

1. **Separação de responsabilidade:** a Mãe apenas roteia (sem texto para o lead); as Filhas apenas geram resposta (sem ter que roteiar). Prompts mais curtos e com menor risco de conflito de instrução.
2. **Especialização por fase:** cada Filha tem um contexto, tom e regras otimizadas para sua fase (qualificação vs. fechamento são tarefas muito diferentes).
3. **Auditabilidade:** o raciocínio de roteamento fica separado da resposta comercial — é possível inspecionar por que o lead foi enviado para uma fase sem misturar com o output.
4. **Guardrails isolados:** os guardrails de modo (`_apply_mode_guardrails`) atuam sobre a saída da Mãe antes de escolher a Filha, sem contaminar o prompt da Filha.

```
Inbound WhatsApp
    ↓
_build_mother_prompt()   ← LLM Mãe: decide a fase (route_to)
    ↓                       retorna MotherDecision (JSON)
[guardrails de modo]     ← código Python valida/corrige o route_to
    ↓
_build_child_prompt_qualification()   ← route_to == "qualification"
_build_child_prompt_apresentation()   ← route_to == "apresentation"
_build_child_prompt_follow_up()       ← route_to == "follow-up"
_build_child_prompt_closing()         ← route_to == "closing"
_build_child_prompt()                 ← fallback (sem fase especializada)
```

Há também `_build_prompt()` como caminho legado/fallback sem Mãe — usada quando o executor decide não usar a arquitetura bifurcada.

---

### 1.1 `_build_prompt()` — Motor de decisão geral (fallback)

> **Arquivo:** `decision_engine.py` — função `_build_prompt()`
> **Usado por:** todos os agentes como caminho de fallback (sem bifurcação Mãe/Filha)
> **Agentes:** qualquer `agent_mode` / `template_key`

**Papel da LLM:**
> "Você é um motor de decisão de um CRM (WhatsApp)."

A LLM age como sistema de roteamento e geração em uma única chamada. Decide a ação (`reply`, `ask_qualification`, `handoff`, `ignore`) e redige a resposta se necessário.

**Output esperado:**
```json
{
  "next_action": "reply|ask_qualification|handoff|ignore",
  "message_text": "string",
  "questions": ["..."],
  "reason": "curto",
  "suggested_category": "ou null",
  "category_reason": "ou null"
}
```

**Variáveis injetadas no prompt — de onde vêm:**

| Variável | Origem no bundle | Conteúdo |
|---|---|---|
| `lead_summary` | `context["lead"]` | id, nome, telefone, segmento, status, categoria |
| `ai_summary` | `context["ai_profile"]` | template_key, agent_mode, brand_name, tone_of_voice, niche, target_audience, offer_description, goals, custom_instructions, identity_mode, handoff_policy, handoff_custom_text |
| `playbook_summary` | `context["playbook"]` | template_key / name |
| `metadata_summary` | `context["metadata"]` | provider, instance_id |
| `allowed_categories` | `context["metadata"]["allowed_lead_categories"]` | lista de categorias Kanban permitidas (ou DEFAULT_ALLOWED_LEAD_CATEGORIES) |
| `history_text` | `context["history"]` | últimas 10 mensagens formatadas como `role: body` |
| `last_bot_message` | derivado do `history` | última mensagem `model=outbound` — só injetado se `_is_short_reply()` retornar True |
| `short_reply_hint` | lógica interna | hint `"message_text é resposta direta"` — só injetado se reply curto detectado |
| `agent_mode_normalized` | `_compute_system_agent_mode()` | modo normalizado (consultivo, agenda, direto) |
| `required_fields` | `_build_mode_contract_context()` | campos obrigatórios do modo ativo |
| `missing_fields` | `qualification_state.data_json` vs `required_fields` | campos ainda não coletados |
| `current_field` | `_select_current_field()` | próximo campo a coletar (primeiro dos missing) |
| `asked_questions_for_current_field` | `qualification_state.asked_questions_json` | últimas 2 perguntas feitas para o campo atual |
| `last_question_text` | `qualification_state.last_question_text` | última pergunta enviada |
| `lead_origin_label` | `context["metadata"]["lead_origin_label"]` | ex.: `"INBOUND"` ou `"OUTBOUND"` |
| `origin_opener` | `ai_profile.origin_inbound_opener` ou `origin_outbound_opener` | texto de abertura configurado pelo operador |
| `message_text` | `context["metadata"]["inbound_message_text"]` | mensagem atual do lead |

**Regras críticas embutidas:**
- `suggested_category` deve ser um estágio do funil (`ALLOWED_LEAD_CATEGORIES`), nunca um nicho/tema
- Se inbound for genérico ("oi"), pergunta UMA coisa — não sugere categoria
- `handoff` só em pedido explícito de humano
- `short_reply_hint`: se presente, responde ao contexto anterior sem iniciar assunto novo

---

### 1.2 `_build_mother_prompt()` — Roteador Mãe

> **Arquivo:** `decision_engine.py` — função `_build_mother_prompt()`
> **Usado por:** todos os agentes (antes de qualquer Filha especializada)
> **Agentes:** qualquer `agent_mode` / `template_key`

**Papel da LLM:**
> "Você é o ROTEADOR MÃE de um CRM de vendas WhatsApp."

A LLM não responde ao lead. Apenas decide o `route_to` e emite sinais para a Filha usar.

**Output esperado:**
```json
{
  "route_to": "qualification|apresentation|follow-up|closing",
  "perceived_category": "qualification|apresentation|follow-up|closing|null",
  "confidence": 0.0,
  "reason": "curto",
  "agent_mode": null,
  "signals": {
    "meeting_scheduled": true,
    "intent_level": "low|medium|high",
    "urgency_level": "low|medium|high",
    "price_acceptance": "no|unsure|yes"
  },
  "objective": "string curta",
  "next_action_hint": "reply|ask_qualification|handoff|ignore|greet|null"
}
```

**Variáveis injetadas:** subconjunto do `_build_prompt()` — mesmos campos de `lead_summary`, `ai_summary`, `playbook_summary`, `metadata_summary`, `history_text`, `agent_mode_normalized`, `required_fields`, `missing_fields`, `lead_origin_label`, `origin_opener`, `message_text`.

**Bloco condicional adicional — modo passivo:**
Injetado **somente** quando `ai_profile.response_style == "passive"`:
```
MODO PASSIVO (response_style=passive): se a mensagem for pergunta directa E missing_fields NÃO VAZIO
→ usar next_action_hint='reply' para sinalizar à filha que deve responder a pergunta primeiro.
OU se for saudação social pura E histórico vazio/1 msg → usar next_action_hint='greet'.
```

**Regras de roteamento (prioridade decrescente):**

| Prioridade | Condição | Rota |
|---|---|---|
| 1A | `missing_fields` não vazio + mensagem sem pergunta direta | `qualification` |
| 1B | `missing_fields` não vazio + mensagem com pergunta direta | `qualification` + `next_action_hint=reply` |
| EXCEÇÃO FECHO | `agent_mode=agenda` + sinal explícito de booking (mesmo com missing_fields) | `apresentation` |
| 2 | Lead confirmou data/horário | `apresentation` |
| 2 | Lead disse "quero comprar/fechar" com `intent_level=high` | `closing` |
| 2 | Lead mencionou sessão passada + objeção | `follow-up` |
| 3 | Interesse sem confirmação | `apresentation` (confidence < 0.7) |
| 4 | Mensagem genérica | manter rota atual |
| SAUDAÇÃO | Saudação pura + histórico vazio | `qualification` + `next_action_hint=greet` |

**Exemplos fornecidos no prompt (11 casos — few-shot in-context):**

| # | Inbound | Rota esperada |
|---|---|---|
| 1 | "Amanhã 17h tá confirmado" | `apresentation` + `meeting_scheduled=true` |
| 2 | "Pode reagendar pra sexta?" | `apresentation` |
| 3 | "Vou pensar" (pós-apresentação) | `follow-up` |
| 4 | "Vou pensar" (sem apresentação) | ❌ não usar follow-up |
| 5 | "Qual o preço?" | ❌ não usar closing |
| 6 | SDR "Fechou amanhã 17h, manda o link" | `apresentation` + `meeting_scheduled` |
| 7 | SDR "Pode confirmar a reunião?" | `apresentation` |
| 8 | CLOSER "Posso assinar hoje?" | `closing` |
| 9 | CLOSER "Manda contrato" | `closing` |
| 10 | CLOSER "Fechou amanhã 17h" | `apresentation` (sem meeting_scheduled) |
| 11 | AGENDA "Perfeito, fica combinado" | `apresentation` + sinal de fecho override |

> **Por que 11 exemplos?** Para cobrir os 3 `agent_mode` distintos (consultivo, agenda, direto/closer) em variações de saudação, fechamento e roteamento negativo. O modelo tende a confundir `follow-up` e `closing` sem exemplos negativos explícitos.

---

### 1.3 `_build_child_prompt_qualification()` — Filha Qualificação

> **Arquivo:** `decision_engine.py` — função `_build_child_prompt_qualification()`
> **Usado por:** todos os agentes quando `route_to == "qualification"`
> **Agentes:** qualquer `agent_mode` / `template_key`

**Papel da LLM:**
> "Você é a FILHA QUALIFICATION de um CRM de vendas WhatsApp."

Opera em dois modos controlados por `response_style`. Coleta campos de qualificação um por vez.

**Output esperado:**
```json
{
  "question_text": "string",
  "field": "service_interest|urgency|decision_role|constraints|availability_window|budget_or_price_acceptance|location_preference|price_acceptance|custom_*|null",
  "should_ask": true,
  "message_text": "string",
  "did_complete_phase": false,
  "recommended_next_category": "apresentation|null",
  "outcome": null,
  "kanban_highlight": null,
  "signals": ["..."],
  "signals_structured": {"missing_fields": ["..."], "handoff_requested": false},
  "confidence": 0.0
}
```

**Variáveis adicionais (além do core do ContextBundle):**

| Variável | Origem | Conteúdo |
|---|---|---|
| `response_style` | `ai_profile.response_style` (default `"passive"`) | `"active"` ou `"passive"` — muda radicalmente o comportamento |
| `current_field` | `_select_current_field(missing, filled)` | próximo campo a coletar |
| `asked_for_current` | `qualification_state.asked_questions_json` | últimas 2 perguntas já feitas para este campo — a LLM DEVE reformular |
| `last_question_text` | `qualification_state.last_question_text` | última pergunta enviada |
| `lead_origin_label` / `origin_opener` | `ai_profile` + `metadata` | abertura de primeiro contato |
| `tone_block` | `_build_tone_block(ai_profile, playbook)` | regras de tom WhatsApp (veja seção 1.3.1) |
| `qualification_fields_block` | `_build_qualification_fields_block(ai_profile, response_style)` | campos configurados + instruções de uso (veja seção 1.3.2) |
| `custom_instructions_block` | `_build_custom_instructions_block(ai_profile)` | instruções livres do operador (prioridade máxima) |
| `training_examples_block` | `_build_training_examples_block(context, "qualification")` | exemplos bom/ruim classificados pelo operador no Playground |
| `generated_prompt_parts` | `context["generated_prompt_parts"]` | injetado via `_inject_generated_parts()` pós-construção (veja seção 1.8) |
| `knowledge_media` | `context["knowledge_media"]` | chaves de categorias com mídia — ativa nota de supressão de texto |

**Blocos condicionais injetados no cabeçalho do prompt:**

| Bloco | Condição de ativação | Descrição |
|---|---|---|
| `_first_contact_opener_header` | `is_first_contact=True` + `origin_opener` preenchido + sem saudação | Força uso do texto de abertura configurado no AI Profile |
| `_greeting_header` | `next_action_hint == "greet"` | Modo saudação: cumprimenta ANTES de qualificar, origin_opener opcional |
| `_passive_header` (modo reply) | `response_style == "passive"` + `next_action_hint == "reply"` | Resposta imediata proibindo qualquer pergunta neste turno |
| `_passive_header` (modo padrão) | `response_style == "passive"` (sem hint especial) | Zero perguntas abertas; inferência silenciosa obrigatória |
| `_media_intro_note` | `context["knowledge_media"]` não vazio | Instrui LLM a escrever apenas introdução curta (mídia enviada automaticamente) |

**Regras de copy — modo `active`:**
```
Responde SEMPRE à mensagem do cliente antes de qualificar.
Se o cliente fez uma pergunta, responde usando offer_description e custom_instructions.
Depois, se houver campos obrigatórios em falta, adicione UMA pergunta de qualificação
natural ao final. Nunca respondas APENAS com uma pergunta de qualificação.
```
- Máximo 1 pergunta por turno
- `field` deve ser EXATAMENTE o `current_field` quando `should_ask=true`
- Proibido agendar reunião aqui

**Regras de copy — modo `passive`:**
```
NUNCA faças perguntas abertas de qualificação.
ZERO perguntas de qualificação. should_ask=false na esmagadora maioria dos casos.
Qualificação por INFERÊNCIA SILENCIOSA — lê o que o lead diz e preenche internamente.
ÚNICA EXCEÇÃO: closing_question binária configurada (ex: "às 15h ou 17h?").
```

**Proibições (7 regras críticas embutidas no prompt):**
1. Nunca invente informações fora do contexto
2. Nunca prometa condições não presentes em offer_pack / knowledge_items
3. Nunca dê conselhos médicos, jurídicos ou financeiros
4. Nunca mencione concorrentes (exceto se em knowledge_items)
5. Nunca use urgência artificial
6. Nunca responda fora do nicho
7. Se não souber, diga que vai verificar (→ handoff)

Plus `_ESCAPE_HATCH_BLOCK` (o que fazer quando não sabe responder) e `_build_validation_block` (checklist pré-retorno).

#### 1.3.1 `_build_tone_block()` — Bloco de tom WhatsApp

Gerado em tempo de execução para cada prompt de Filha. Contém:
- Tom de voz configurado (`ai_profile.tone_of_voice`)
- Limite de caracteres (`playbook.max_chars`)
- Regras de formato WhatsApp (sem bullet points, sem markdown, 1-2 parágrafos)
- Proibições de estilo (emojis excessivos, CAPS, exclamações consecutivas)
- **Condicional `hybrid_scheduler`:** se `template_key == "hybrid_scheduler"` e `brand_name` preenchido, adiciona regra de persona como assistente pessoal do profissional (ex: "fale como o assistente da Dra. Maria").

#### 1.3.2 `_build_qualification_fields_block()` — Campos de qualificação por modo

Gerado a partir de `ai_profile.qualification_fields` (array `QualificationField[]`).

**Modo `active`** — expõe:
- `required` com `question` e `passive_hint`: "OBRIGATÓRIOS — usar a question configurada ao perguntar"
- `optional` com `question` e `passive_hint`: "DESEJÁVEIS — capturar se surgir oportunidade"

Exemplo injetado:
```
CAMPOS DE QUALIFICAÇÃO CONFIGURADOS:
OBRIGATÓRIOS — usar a question configurada ao perguntar:
- Disponibilidade (key: availability_window): pergunta → "Qual horário funciona?" | inferir: "se lead mencionar horário"
- Nome do pet (key: custom_nome_do_pet): pergunta → "Qual o nome do seu pet?"
DESEJÁVEIS — capturar se surgir oportunidade natural:
- Serviço de interesse (key: service_interest): pergunta → "O que você busca?" | inferir: "pelo contexto"
```

**Modo `passive`** — expõe:
- `passive_hint` por campo: "Registrar internamente se o lead mencionar (NÃO perguntar)"
- `closing_question` por campo (se `allow_closing_question=true`): únicas perguntas permitidas

**Não gera bloco** se `qualification_fields` for null/vazio.

---

### 1.4 `_build_child_prompt_apresentation()` — Filha Apresentação

> **Arquivo:** `decision_engine.py` — função `_build_child_prompt_apresentation()`
> **Usado por:** todos os agentes quando `route_to == "apresentation"`
> **Agentes:** qualquer `agent_mode` / `template_key`

**Papel da LLM:**
> "Você é a FILHA APRESENTATION de um CRM de vendas WhatsApp."

É o prompt mais complexo do sistema. Comportamento controlado por `presentation_variant`.

**Output esperado:**
```json
{
  "message_text": "string",
  "did_complete_phase": false,
  "recommended_next_category": null,
  "outcome": null,
  "kanban_highlight": null,
  "signals": ["..."],
  "signals_structured": {
    "missing_fields": ["..."],
    "handoff_requested": false,
    "meeting_proposed": false,
    "meeting_datetime_candidate": null,
    "offer_presented": false,
    "checkout_sent": false,
    "presentation_variant": "sales|scheduler",
    "offer_item_name": "string"
  },
  "confidence": 0.0
}
```

**Variáveis adicionais:**

| Variável | Origem | Como é resolvida |
|---|---|---|
| `presentation_variant` | `_resolve_presentation_variant()` | 1º `metadata.force_presentation_variant`; 2º `ai_profile.presentation_variant`; 3º derivado de `agent_mode` (direto→sales, agenda→scheduler) |
| `hybrid_flow_style` | `_resolve_hybrid_flow_style()` | `ai_profile.hybrid_flow_style` ou `metadata.hybrid_flow_style` |
| `offer_pack_summary` | `_build_offer_pack_summary()` | `ai_profile.offer_pack` (JSON) ou fallback de `offer_description` |
| `appointment_mode` | `ai_profile.appointment_mode` | `"exploratory"` (padrão) ou `"commercial"` — só relevante para `hybrid_scheduler` |
| `knowledge_items` | `context["knowledge_items"]` | dict com categorias: social_proof, pitch_script, product_details, objections_faq, service_faq, guarantee_policy |
| `knowledge_media` | `context["knowledge_media"]` | chaves com mídia — suprime texto descritivo |
| `warming_social_proof` | `ai_profile.warming_social_proof` | texto de prova social (agent 3 exploratory) |
| `warming_session_preview` | `ai_profile.warming_session_preview` | preview da sessão (agent 3 exploratory) |
| `extracted_fields` | `qualification_state.data_json` | campos já coletados — usados no recibo de reserva |

**Blocos condicionais:**

| Bloco | Condição | Descrição |
|---|---|---|
| `_apres_first_contact_opener` | `is_first_contact=True` + `origin_opener` preenchido | Abertura de primeiro contato |
| `_passive_apres_header` | `response_style=passive` + qualificação concluída neste turno + pergunta no inbound | Instrui responder pergunta do lead antes de propor agendamento |
| `warming_injection` (exploratory) | `template_key=hybrid_scheduler` + qualificação recém-aprovada + `appointment_mode=exploratory` | Aquecimento: prova social + preview da sessão antes de propor agendamento (veja 1.4.1) |
| `warming_injection` (scheduler) | `template_key=hybrid_scheduler` + qualificação recém-aprovada + `presentation_variant=scheduler` | Pós-qualificação para serviços presenciais: confirmar disponibilidade e valor |
| `commercial_injection` | `template_key=hybrid_scheduler` + qualificação recém-aprovada + `appointment_mode=commercial` | Modo comercial: apresentar serviços, tratar objeções, fechar compromisso ANTES de agendar (veja 1.4.2) |
| `_booking_confirmation_block` | `meeting_scheduled=True` + `presentation_variant=scheduler` | "Modo recibo": emite resumo estruturado da reserva usando `extracted_fields` |
| `standard_knowledge_block` | quando NÃO há `commercial_injection` + knowledge não vazio | Injeção dos itens de knowledge com instruções de uso por categoria |
| `_media_intro_note_apres` | `knowledge_media` não vazio | Suprime descrição — mídia enviada automaticamente |

**Regras do modo `sales`:**
- **UM TURNO = UMA AÇÃO**: confirmar (sem link) OU enviar link — nunca os dois
- `checkout_sent=false` + proibido URL/placeholder quando confirma
- `checkout_sent=true` + deve incluir URL real quando envia link
- Usar `anchor_price` se disponível: "De R$X por apenas R$Y"
- Usar `guarantee_text` se disponível
- Se `media_url` presente em offer_pack: mídia já foi enviada — NÃO mencionar "veja a imagem/vídeo"

**Regras do modo `scheduler`:**
- Sempre preencher `meeting_proposed` e `meeting_datetime_candidate`
- ISO naive no timezone de `ai_profile.timezone`
- Confirmação final inclui `meeting_scheduled` nos signals

**Exemplos fornecidos no prompt:**
```
EXEMPLO CONFIRMAR: message_text='Plano Starter por R$X. Quer seguir?'
  signals_structured={offer_presented:true, checkout_sent:false, ...}
EXEMPLO ENVIAR LINK: message_text='Aqui está seu link: https://...\nConclua e confirme.'
  signals_structured={offer_presented:true, checkout_sent:true, ...}
```

#### 1.4.1 Injeção WARMING — modo `exploratory` (hybrid_scheduler)

**Quando ativa:** `template_key == "hybrid_scheduler"` + qualificação recém-aprovada + `appointment_mode == "exploratory"`

**Texto injetado:**
```
ESTÁGIO WARMING (pós-qualificação aprovada para hybrid_scheduler):
O lead acabou de concluir a qualificação. Execute os 2 passos em UMA mensagem natural:
1. PROVA SOCIAL: {warming_social_proof ou fallback}
2. PRÉVIA DA SESSÃO: {warming_session_preview ou fallback}
Combine de forma fluida e, ao final, proponha o agendamento.
Não mencione 'prova social' ou 'prévia da sessão' explicitamente.
```

Fallback de prova social (quando não configurado): `"Tenho ajudado muitas pessoas a transformarem [área] com resultados concretos. Posso te contar mais na nossa conversa."`

Fallback de preview (quando não configurado): `"Na sessão de aproximadamente 1h, vamos mapear sua situação atual e sair com um plano de ação claro."`

#### 1.4.1b Injeção WARMING — modo `scheduler` (serviço presencial)

**Quando ativa:** `template_key == "hybrid_scheduler"` + qualificação recém-aprovada + `presentation_variant == "scheduler"` (e NÃO commercial)

**Texto injetado:**
```
ESTÁGIO PÓS-QUALIFICAÇÃO (scheduler — serviço presencial):
1. Confirmar (ou verificar) disponibilidade para o horário mencionado
2. Informar o valor do serviço solicitado (se ainda não mencionado)
3. Propor confirmação da reserva de forma acolhedora
REGRA CRÍTICA: usa linguagem de spa/serviço — 'agendar sessão', 'reservar'.
NUNCA 'mapear situação', 'plano de ação', 'diagnóstico'.
```

#### 1.4.2 Injeção COMMERCIAL — modo `commercial` (hybrid_scheduler)

**Quando ativa:** `template_key == "hybrid_scheduler"` + qualificação recém-aprovada + `appointment_mode == "commercial"`

Lê as categorias de `knowledge_items` específicas do modo comercial:

| Campo knowledge | Fallback quando vazio |
|---|---|
| `social_proof` ou `ai_profile.warming_social_proof` | "use tom acolhedor e destaque o diferencial" |
| `service_pricing_table` | "pergunte o interesse antes de citar valores" |
| `commercial_objections` | "use empatia e reformule o valor entregue" |
| `service_differentials` | campo omitido do prompt |
| `active_promotion` | campo omitido do prompt |
| `payment_policy` | campo omitido do prompt |
| `pre_commitment_faq` | campo omitido do prompt |

Regra crítica embutida: "pagamento é SEMPRE presencial — NUNCA envie link de checkout."

#### 1.4.3 `standard_knowledge_block` — Knowledge Base (fora do commercial)

Injetado quando NÃO há `commercial_injection` e `knowledge_items` não está vazio. Cada categoria tem instrução de uso diferente:

| Categoria | Instrução de uso | Comportamento com mídia |
|---|---|---|
| `social_proof` | Integrar na fase de warming ou quando lead hesitar. Nunca dizer "temos uma prova social" | — |
| `pitch_script` | Usar como guia estrutural, não copiar literalmente | Se tiver mídia: omite texto, só introdução curta |
| `product_details` | Usar dados presentes; nunca inventar features | Se tiver mídia: omite texto, só introdução curta |
| `objections_faq` | Usar apenas quando lead levantar objeção; adaptar tom | — |
| `service_faq` | Usar apenas quando lead fizer pergunta coberta; handoff se não coberta | Se tiver mídia: omite texto, só introdução curta |
| `guarantee_policy` | Citar apenas quando lead demonstrar hesitação sobre risco | — |

---

### 1.5 `_build_child_prompt_follow_up()` — Filha Follow-up

> **Arquivo:** `decision_engine.py` — função `_build_child_prompt_follow_up()`
> **Usado por:** todos os agentes quando `route_to == "follow-up"`
> **Agentes:** qualquer `agent_mode`; comportamento varia muito por `followup_variant`

**Papel da LLM:**
> "Você é a FILHA FOLLOW-UP de um CRM de vendas WhatsApp."

**Output esperado:**
```json
{
  "message_text": "string",
  "did_complete_phase": false,
  "recommended_next_category": "follow-up|closing|null",
  "outcome": null,
  "kanban_highlight": null,
  "signals": ["..."],
  "signals_structured": {"missing_fields": ["..."], "handoff_requested": false},
  "confidence": 0.0
}
```

**Variáveis adicionais:**

| Variável | Origem | Conteúdo |
|---|---|---|
| `followup_ctx` | `context["metadata"]["followup_context"]` (dict) | contrato de follow-up do lead |
| `followup_summary` | derivado de `followup_ctx` | goal, outcome, variant, attempts, max_attempts, meeting_happened, meeting_or_session_happened, proposal_sent, operator_note, status, next_followup_at |
| `followup_variant` | `followup_ctx.followup_variant` | `sdr_scheduler`, `cart_recovery` ou `hybrid_scheduler` |
| `is_followup_tick` | `_is_followup_tick_context(context)` | `True` = disparo automático (`job_type=whatsapp.followup.tick`); `False` = resposta a inbound |
| `qualification_context_block` | read-only quando `is_followup_tick=True` | só memória auxiliar — proibido coletar campos |

**`variant_rule` — instrução por variante (injetada no corpo do prompt):**

**`sdr_scheduler`:**
```
Variante sdr_scheduler: follow-up consultivo pós-reunião;
reforçar valor, síntese do contexto e próximo passo comercial.
```

**`cart_recovery`** (Agent 2 — low ticket):
```
Variante cart_recovery: recuperar pagamento pendente. Mensagens curtas (máx 280 chars).
Instrução para tentativa N/3: [baseada em attempts_done+1]
```
- Tentativa 1: lembrete neutro
- Tentativa 2: benefício + objeção
- Tentativa 3: urgência máxima + CTA direto

**`hybrid_scheduler`** (Agent 3 — coaches/terapeutas/consultores):
```
Variante hybrid_scheduler: tom pessoal e próximo, como assistente do próprio profissional
— nunca SDR agressivo.
Regra por outcome (XXXX): [instrução específica]
```

Por `outcome`:
| Outcome | Instrução injetada |
|---|---|
| `interested_not_closed` | Retome contexto, remova objeção específica, ofereça nova data |
| `reschedule_needed` | Tom leve, 2-3 horários diretos, encerre com pergunta fechada |
| `converted` | Tom de onboarding; parabenize, confirme próximo passo, link/acesso |
| outros | Recuperação de no-show, confirmação de presença, reengajamento |

**`followup_priority_rule` — regra condicional ao `is_followup_tick`:**

Quando `is_followup_tick=True`:
```
CONTEXTO PRIORITÁRIO (follow-up tick): use followup_contract_signals como fonte principal.
Histórico é memória contextual — não é backlog de perguntas pendentes.
missing_fields de qualification são SOMENTE memória auxiliar (read-only).
É proibido usar missing_fields como alvo de coleta/pergunta.
```

Quando `is_followup_tick=False`:
```
Faça no máximo 1 pergunta por mensagem e priorize o próximo missing_field.
```

**Knowledge Base (follow-up):** injetado via `followup_knowledge_block` com categorias: `social_proof`, `objections_faq`, `service_faq` (com mesmas instruções de uso da apresentação).

---

### 1.6 `_build_child_prompt_closing()` — Filha Closing

> **Arquivo:** `decision_engine.py` — função `_build_child_prompt_closing()`
> **Usado por:** todos os agentes quando `route_to == "closing"`
> **Agentes:** comportamento central controlado por `agent_mode_normalized`

**Papel da LLM:**
> "Você é a FILHA CLOSING de um CRM de vendas WhatsApp."

**Output esperado:**
```json
{
  "message_text": "string",
  "did_complete_phase": false,
  "recommended_next_category": "closing|null",
  "outcome": "won|lost|null",
  "kanban_highlight": "green|orange|null",
  "signals": ["..."],
  "signals_structured": {"missing_fields": ["..."], "handoff_requested": false},
  "confidence": 0.0
}
```

**Nota:** `outcome` e `kanban_highlight` só têm efeito visual no Kanban se `lead.category == "closing"` (guardrail `apply_outcome_guardrails` em código Python).

**Regras por `agent_mode_normalized`:**

| Modo | Comportamento |
|---|---|
| `consultivo` | Não fecha sozinho; responde curto e encaminha para humano |
| `agenda` | Fechamento operacional — confirma horário, políticas, pagamento quando aplicável |
| `direto` | Conduz fechamento e confirmação de pagamento com objetividade |

**Diferença em relação às outras Filhas:**
- Sem chamada a `_inject_generated_parts()` — o `closing` não tem `few_shot_closing` no meta-prompter (e `tone_rules` já vêm via `_build_tone_block`, evitando duplicação).

---

### 1.7 `_build_child_prompt()` — Filha genérica (fallback)

> **Arquivo:** `decision_engine.py` — função `_build_child_prompt()`
> **Usado por:** quando nenhuma Filha especializada é selecionada (rota não reconhecida)

**Papel da LLM:**
> "Você é uma LLM FILHA de um CRM de vendas WhatsApp."

Sem persona, sem instruções de modo específicas. Output: mesmo schema ChildResult.

---

### 1.8 Injeção do Meta-prompter — `_inject_generated_parts()`

> **Arquivo:** `decision_engine.py` — função `_inject_generated_parts()`
> **Ativação:** quando `context["generated_prompt_parts"]` não está vazio (Tarefa 4 — aditivo)

Esta função é chamada **após** a construção do prompt de cada Filha. Injeta blocos gerados pelo meta-prompter do nicho, sem sobrescrever nada — apenas adiciona ao final.

**Estrutura de `generated_prompt_parts`:**

| Chave | Fases que usa | Descrição |
|---|---|---|
| `few_shot_qualification` | `qualification` | Exemplos lead+resposta esperada para o nicho |
| `few_shot_apresentation` | `apresentation` | Exemplos de pitch/agendamento do nicho |
| `few_shot_followup` | `followup` | Exemplos de reengajamento do nicho |
| `tone_rules` | todas (qualif, apres, followup) | Regras de tom específicas do nicho (lista de strings) |
| `qualification_phrasing` | `qualification` | Formas naturais de perguntar um campo naquele nicho |
| `objection_rewrites` | `apresentation`, `followup` | Objeções no formato LAER (causa, reconhecer, explorar, responder, próximo passo) |
| `outreach_scenarios` | `llm.py` (outreach) | Cenários dinâmicos para cold outreach (substitui cenários fixos no_site/weak_site) |

**Formato de injeção dos few-shot:**
```
EXEMPLOS DE REFERÊNCIA PARA ESTE NICHO (adapte ao contexto atual, não copie):
Cenário: [scenario]
Lead: "[inbound]"
Resposta esperada: {expected_output JSON}
```

**Formato de injeção das objeções (LAER):**
```
OBJEÇÕES REFORMULADAS (formato LAER — usar quando o lead levantar objeção):
Objeção: "é caro"
  Causa real: lead compara com concorrente
  Reconhecer: "Entendo, é um investimento..."
  Explorar: "O que seria ideal para você?"
  Responder: "Incluímos X e Y que evitam..."
  Próximo passo: "Se fizer sentido, proponho..."
```

---

### 1.9 `_build_training_examples_block()` — Exemplos do Playground

> **Arquivo:** `decision_engine.py` — função `_build_training_examples_block()`
> **Ativação:** quando `context["training_examples"]` não está vazio

Injetado ao final dos prompts de qualificação, apresentação e follow-up. Fonte: classificações reais do operador feitas no Playground (aprovar/rejeitar respostas do bot).

**Estrutura de `training_examples`:**
```json
{
  "qualification": {
    "good": [{"lead_message": "...", "bot_message": "..."}],
    "bad": [{"lead_message": "...", "bot_message": "...", "comment": "..."}]
  },
  "apresentation": { ... },
  "followup": { ... }
}
```

**Formato injetado:**
```
EXEMPLOS DE TREINO DO OPERADOR (baseados em classificações reais):

✅ RESPOSTA APROVADA:
Lead: "quanto custa?"
Bot: "O plano Starter começa em R$X. Quer que eu te explique o que inclui?"

❌ RESPOSTA REJEITADA:
Lead: "quanto custa?"
Bot: "Posso te enviar uma proposta detalhada. Qual é a tua empresa?"
Motivo do operador: "respondeu com pergunta em vez de responder o preço"
```

---

## 2. Extrator de Campos — `field_extractor.py`

> **Arquivo:** `backend-executors/app/services/field_extractor.py`
> **Função principal:** `extract_fields_llm(context, fields_schema)`
> **Usado por:** todos os agentes após cada inbound, para atualizar `qualification_state`

**Papel da LLM:**
> "Você é um extractor de campos de qualificação."

**Prompt:**
```
Você é um extractor de campos de qualificação. Retorne SOMENTE JSON válido:
{
  "extracted": {"field": "value"},
  "confidence": {"field": 0.0},
  "evidence": {"field": "trecho curto"}
}
Regras:
- Extraia APENAS com base no texto disponível.
- Se não houver evidência, não invente campo.
- confidence entre 0 e 1 por campo.
- schema: {fields_schema}
- inbound_message_text: {mensagem atual}
- history: {últimas 6 mensagens}
```

**Variáveis injetadas:**

| Variável | Origem | Conteúdo |
|---|---|---|
| `fields_schema` | `ai_profile.qualification_fields` (todos os campos) | Schema JSON com campos do sistema + campos `custom_*`. Para `custom_*`, o `passive_hint` configurado é incluído como instrução de extração. |
| `inbound_message_text` | `context["metadata"]["inbound_message_text"]` | Mensagem atual do lead |
| `history` | `context["history"][-6:]` | Últimas 6 mensagens formatadas como `[bot/lead]: texto` |

**Por que não tem exemplos:** o extrator opera sobre dados factuais do texto — exemplo prévio não ajuda e pode enviesar a extração.

---

## 3. Geração de Outreach — `llm.py`

> **Arquivo:** `backend-crm/automations/assistente_ia/llm.py`
> **Classe:** `LLMClient`
> **Modelo:** OpenAI (default `gpt-3.5-turbo`, configurável)
> **Usado por:** Agent Local de prospecção (não é usado no fluxo WhatsApp inbound)

### System prompts fixos

| Método | System Prompt | Uso |
|---|---|---|
| `_chat_text()` | `"Você é um assistente de prospecção objetivo e cordial."` | Texto livre (scripts de ligação, WhatsApp, Instagram) |
| `_chat_json()` | `"Você escreve e-mails comerciais objetivos e cordiais."` | JSON estruturado (e-mail) |

### `generate_for_lead()` — prompts por canal

**Parâmetros:**
```python
generate_for_lead(lead, channels, tone, language, context, sender, ai_profile)
```

**Bloco de contexto comum** (injetado em todos os canais):
```
Empresa do prospect: {lead.companyName}
{scenario_context}  ← cenários dinâmicos OU legado (veja abaixo)
Remetente: Nome=X; Empresa=Y; Email=Z; Telefone=W
NUNCA use placeholders como [Seu Nome]; use os dados do Remetente fornecidos.
Se contactName estiver vazio, cumprimente pela empresa.
```

**Variáveis globais:**

| Variável | Origem | Conteúdo |
|---|---|---|
| `lead.companyName` | banco CRM | nome da empresa prospectada |
| `lead.contactName` | banco CRM | nome do contato (pode ser vazio) |
| `scenario_context` | `_format_outreach_scenarios()` ou `_format_legacy_scenario()` | veja abaixo |
| `tone` | parâmetro da chamada | tom de voz escolhido pelo usuário |
| `language` | parâmetro da chamada | idioma do output (`pt-PT`, `pt-BR`, `en`, etc.) |
| `sender.*` | perfil do usuário logado | name, company, email, phone, signature |

**Cenários dinâmicos vs. legado:**

| Modo | Condição | Variável injetada |
|---|---|---|
| **Dinâmico** (Tarefa 4.3) | `ai_profile.generated_prompt_parts.outreach_scenarios` não vazio | Lista de cenários com `scenario_key`, `description`, `whatsapp_angle`, `cta` — instruindo LLM a escolher o ângulo mais relevante |
| **Legado** | cenários dinâmicos ausentes | `scenario = no_site|weak_site|decent_site` derivado de `context` (ssl, mobile, issues) |

**Variáveis template pós-processadas** (não pela LLM — substituídas depois no processador):
- `{{prospect.company}}` → nome da empresa
- `{{sender.signature}}` → assinatura do remetente

**Prompts por canal:**

| Canal | Regras principais | Output |
|---|---|---|
| `email` | assunto ≤ 60 chars; corpo 120-180 palavras; sem links; CTA "posso enviar 2 ideias?"; comportamento por cenário legado se dinâmico ausente | JSON `{subject, body}` |
| `whatsapp` | 4-6 linhas; sem links; CTA de permissão para enviar ideias; assinar como `{{sender.name}}, {{sender.company}}` | texto |
| `instagram` | 2-4 linhas; amigável; sem spam; CTA de ideias | texto |
| `call` | bullets: abertura 10-15s; 2-3 perguntas; pitch 20s; CTA próximo passo | texto |

**Comportamento por cenário legado (quando `outreach_scenarios` ausente):**

| Cenário | Instrução ao LLM |
|---|---|
| `no_site` | Propor criação de site com CTA + WhatsApp |
| `weak_site` | 2-3 melhorias rápidas (mobile, HTTPS, SEO) + convite call 15 min |
| `decent_site` | Focar em automações de captação (form→WhatsApp, agendador, chat) + teste-piloto |

---

## 4. Variáveis de identidade e copy do `ai_profile`

Estas variáveis são injetadas nos prompts do `decision_engine` e controlam o tom e persona:

| Campo | Chave `ai_profile` | Onde é usado |
|---|---|---|
| Nome do agente/marca | `brand_name` | `_build_tone_block()` (persona hybrid_scheduler), todos os ai_summary |
| Tom de voz | `tone_of_voice` | Todos os prompts de Filha |
| Nicho | `niche` | ai_summary em todos os prompts |
| Público-alvo | `target_audience` | ai_summary em prompts de Mãe e fallback |
| Oferta | `offer_description` | Disponível como fallback do offer_pack; qualificação (responder perguntas do lead) |
| Objetivos | `goals` | ai_summary no fallback geral |
| Instruções customizadas | `custom_instructions` | `_build_custom_instructions_block()` — prioridade máxima |
| Modo de identidade | `identity_mode` | ai_summary no fallback geral |
| Política de handoff | `handoff_policy` | ai_summary no fallback geral |
| Texto de handoff | `handoff_custom_text` | ai_summary no fallback geral |
| Prova social warming | `warming_social_proof` | `_build_child_prompt_apresentation()` modo exploratory |
| Preview da sessão | `warming_session_preview` | `_build_child_prompt_apresentation()` modo exploratory |
| Modo de compromisso | `appointment_mode` | Apresentação: `exploratory` (default) ou `commercial` (hybrid_scheduler) |
| Estilo de resposta | `response_style` | `"active"` (pergunta) ou `"passive"` (infere). Default `"passive"` quando null |
| Opener inbound | `origin_inbound_opener` | Abertura de primeiro contato para leads inbound |
| Opener outbound | `origin_outbound_opener` | Abertura de primeiro contato para leads outbound |
| Campos de qualificação | `qualification_fields` | `QualificationField[]` — source of truth para prompts, extração e guardrails |
| Campos obrigatórios | `qualification_required_fields` | Derivado de `qualification_fields[mode=required].map(key)` ao salvar no core |
| Timezone | `timezone` | Usado na Filha Apresentação para formato ISO de `meeting_datetime_candidate` |
| Template key | `template_key` | Seleciona comportamentos condicionais (hybrid_scheduler, sdr_padrao, closer_agressivo) |
| Offer pack | `offer_pack` | JSON com itens, preços, bullets, provas, checkout_link, media_url, anchor_price, guarantee_text |

---

## 5. Mapa de injeções condicionais

Blocos que só aparecem no prompt quando certas condições são atendidas:

| Bloco | Condição de ativação | Prompts afetados |
|---|---|---|
| `_first_contact_opener_header` | `is_first_contact=True` + `origin_opener` preenchido + sem saudação | qualification, apresentation |
| `_greeting_header` | `next_action_hint == "greet"` | qualification |
| `_passive_header` (reply now) | `response_style=passive` + `next_action_hint=reply` | qualification |
| `_passive_header` (default) | `response_style=passive` (sem hint especial) | qualification |
| `_passive_apres_header` | `response_style=passive` + qualif concluída neste turno + pergunta no inbound | apresentation |
| `must_collect_with_questions` | `response_style=active` + `qualification_fields` com `mode=required` | qualification |
| `passive_hints` | `response_style=passive` + `passive_hint` preenchido em algum campo | qualification |
| `closing_questions` | `response_style=passive` + `allow_closing_question=True` + `closing_question` preenchida | qualification |
| `WARMING exploratory` | `template_key=hybrid_scheduler` + qualif recém-aprovada + `appointment_mode=exploratory` | apresentation |
| `WARMING scheduler` | `template_key=hybrid_scheduler` + qualif recém-aprovada + `presentation_variant=scheduler` | apresentation |
| `COMMERCIAL INJECTION` | `template_key=hybrid_scheduler` + qualif recém-aprovada + `appointment_mode=commercial` | apresentation |
| `_booking_confirmation_block` | `meeting_scheduled=True` + `presentation_variant=scheduler` | apresentation |
| `standard_knowledge_block` | `not commercial_injection` + `knowledge_items` não vazio | apresentation |
| `followup_knowledge_block` | `knowledge_items` com social_proof/objections_faq/service_faq | followup |
| `VARIANT_RULE cart_recovery` | `followup_variant=cart_recovery` | followup |
| `VARIANT_RULE hybrid_scheduler` | `followup_variant=hybrid_scheduler` | followup |
| `FOLLOWUP_PRIORITY_RULE` (tick) | `is_followup_tick=True` | followup |
| `qualification_context_block` (read-only) | `is_followup_tick=True` | followup |
| `offer_pack media_url` | `offer_pack_summary.media_url` preenchido | apresentation |
| `anchor_price` no pitch | `offer_pack_summary.anchor_price` preenchido | apresentation |
| `guarantee_text` no pitch | `offer_pack_summary.guarantee_text` preenchido | apresentation |
| `_media_intro_note` | `context["knowledge_media"]` não vazio | qualification, apresentation |
| `media_suppressed (category)` | chave da categoria presente em `knowledge_media` | apresentation, followup |
| `MODO PASSIVO` no mother | `ai_profile.response_style == "passive"` | mother |
| `custom_instructions_block` | `ai_profile.custom_instructions` preenchido | qualification, apresentation |
| `training_examples_block` | `context["training_examples"]` não vazio | qualification, apresentation, followup |
| `generated_prompt_parts` | `context["generated_prompt_parts"]` não vazio | qualification, apresentation, followup |
| `tone_rules` (meta) | `generated_prompt_parts.tone_rules` preenchido | qualification, apresentation, followup |
| `few_shot_{phase}` (meta) | `generated_prompt_parts.few_shot_{phase}` preenchido | qualification, apresentation, followup |
| `qualification_phrasing` (meta) | `generated_prompt_parts.qualification_phrasing[current_field]` | qualification |
| `objection_rewrites` (meta) | `generated_prompt_parts.objection_rewrites` preenchido | apresentation, followup |
| `outreach_scenarios` (meta) | `ai_profile.generated_prompt_parts.outreach_scenarios` | llm.py outreach |

---

## 6. Referências no código

| Arquivo | Relevância |
|---|---|
| [backend-executors/app/services/decision_engine.py](../backend-executors/app/services/decision_engine.py) | Todos os prompts do funil WhatsApp (Mãe + Filhas + helpers de bloco) |
| [backend-executors/app/services/field_extractor.py](../backend-executors/app/services/field_extractor.py) | Extração estruturada de campos — inclui custom_* |
| [backend-executors/app/contracts/qualification_contract.py](../backend-executors/app/contracts/qualification_contract.py) | Contrato de qualificação: campos por modo, SIGNALS_SCHEMA, compute_missing_fields |
| [backend-executors/app/services/orchestrator_models.py](../backend-executors/app/services/orchestrator_models.py) | Modelos Pydantic: MotherDecision, ChildResult |
| [backend-crm/automations/assistente_ia/llm.py](../backend-crm/automations/assistente_ia/llm.py) | Geração de outreach multicanal (prospecção local) |
| [backend-crm/routes/executor.py](../backend-crm/routes/executor.py) | Monta o ContextBundle + injeta knowledge_items + training_examples antes de enviar ao decision_engine |
| [backend-crm/services/ai_orchestrator/orchestrator.py](../backend-crm/services/ai_orchestrator/orchestrator.py) | Orquestra fluxo inbound; constrói qualification context antes do executor |
| [backend-crm/services/qualification_guardrails.py](../backend-crm/services/qualification_guardrails.py) | Guardrail do Kanban — lê qualification_required_fields; chamado nas rotas manuais de leads |
| [backend-core/app/models/ai_profile.py](../backend-core/app/models/ai_profile.py) | Modelo SQLAlchemy — inclui qualification_fields (JSON nullable), response_style, appointment_mode, origin_openers |
| [backend-core/app/api/ai_profiles.py](../backend-core/app/api/ai_profiles.py) | API de AI Profile; deriva qualification_required_fields de qualification_fields ao salvar |
| [frontend-crm/src/types/agente.ts](../frontend-crm/src/types/agente.ts) | Tipos TypeScript — interface QualificationField, AgentConfig |
