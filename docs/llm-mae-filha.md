# LLM Mãe e Filha — Papel, Prompts e Saídas

Documentação técnica da arquitetura de dois níveis de LLM usada no pipeline de automação WhatsApp do CRM.

---

## Visão Geral

O sistema usa um padrão de **orquestração em duas camadas**:

```
Mensagem inbound (WhatsApp)
        ↓
  [ LLM MÃE ]  →  decide qual etapa do funil acessar
        ↓
  [ LLM FILHA ] →  gera a resposta específica para aquela etapa
        ↓
  DecisionOutput →  mensagem WhatsApp + metadados de CRM
```

**Arquivos centrais:**

| Arquivo | Papel |
|---|---|
| `backend-executors/app/services/decision_engine.py` | Motor principal — construtores de prompt, guardrails, composição |
| `backend-executors/app/services/llm_service.py` | Cliente LLM — chamadas HTTP para a API |
| `backend-executors/app/services/orchestrator_models.py` | Schemas Pydantic — `MotherDecision`, `ChildResult` |
| `backend-crm/services/ai_playbooks/__init__.py` | Playbooks — regras por template/modo |

---

## LLM Mãe

### Papel

A LLM Mãe é um **roteador estratégico**. Ela lê o estado do lead, o histórico da conversa e os campos de qualificação em falta para decidir em qual etapa do funil o lead está e qual filha deve atender.

Ela **não gera mensagem para o usuário final** — apenas toma uma decisão estruturada.

### Construção do Prompt

**Função:** `_build_mother_prompt(context, message_text)` em `decision_engine.py`

**System prompt:**
```
Você é um roteador MÃE de um CRM (WhatsApp). Retorne SOMENTE JSON válido.
```

**Contexto injetado no prompt:**

```json
{
  "lead": {
    "id": "...",
    "name": "...",
    "segment": "...",
    "status": "...",
    "category": "..."
  },
  "ai_profile": {
    "agent_mode": "consultivo | agenda | direto",
    "tone_of_voice": "...",
    "niche": "...",
    "target_audience": "..."
  },
  "playbook": { "template_key": "..." },
  "metadata": {
    "lead_origin_label": "OUTBOUND | INBOUND"
  },
  "history": "[histórico formatado da conversa]",
  "required_fields": "[campos obrigatórios derivados de qualification_fields do AI Profile]",
  "missing_fields": "[campos ainda não coletados]",
  "inbound_message_text": "[mensagem recebida agora]"
}
```

**Regras de prioridade aplicadas no prompt:**

| Prioridade | Condição | Resultado |
|---|---|---|
| **1A** | `missing_fields` não vazio + mensagem **sem** pergunta direta | `route_to = "qualification"` |
| **1B** | `missing_fields` não vazio + mensagem **com** pergunta direta (serviços, preço, como funciona, horários) | `route_to = "qualification"` + `next_action_hint = "reply"` — a filha responde primeiro, depois qualifica |
| **2** | Sinais fortes de reunião (pedido de horário, confirmação, reagendamento, envio de link) | `route_to = "apresentation"` |
| **3** | Pós-apresentação com nutrição ("vou pensar", "me chama mês que vem") | `route_to = "follow-up"` |
| **4** | Intenção direta de compra/assinatura | `route_to = "closing"` |

> **Regra crítica:** uma pergunta direta do lead nunca é ignorada. Quando `missing_fields` existe mas o lead fez uma pergunta, o sistema usa `next_action_hint="reply"` para que a filha responda à pergunta antes de qualificar.

Sem evidência de apresentação prévia → bloquear `follow-up`, manter em `qualification`.

### Saída — `MotherDecision`

Schema definido em `orchestrator_models.py`:

```python
class MotherDecision(BaseModel):
    route_to: Literal["qualification", "apresentation", "follow-up", "closing"]
    perceived_category: Optional[Literal["qualification", "apresentation", "follow-up", "closing"]]
    confidence: float           # 0.0 a 1.0
    reason: str                 # explicação curta da decisão
    agent_mode: Optional[Literal["consultivo", "agenda", "direto"]]  # sempre null (vem do sistema)
    signals: Optional[dict]
    objective: Optional[str]
    next_action_hint: Optional[Literal["reply", "ask_qualification", "handoff", "ignore"]]
```

**Exemplo de saída:**
```json
{
  "route_to": "qualification",
  "perceived_category": "qualification",
  "confidence": 0.85,
  "reason": "Lead não informou orçamento nem urgência",
  "agent_mode": null,
  "signals": {
    "intent_level": "medium",
    "urgency_level": "low",
    "missing_fields": ["urgency", "price_acceptance"]
  },
  "next_action_hint": "ask_qualification"
}
```

---

## LLMs Filha

### Papel

Cada LLM Filha é uma **especialista tática** para uma etapa do funil. Ela recebe a decisão da mãe e o contexto completo, e gera a **mensagem real** a ser enviada ao lead pelo WhatsApp, junto com metadados de CRM.

Existem quatro filhas especializadas mais uma genérica de fallback.

### Seleção da Filha

```python
# decision_engine.py
if route_for_child == "qualification":
    child_prompt = _build_child_prompt_qualification(...)
elif route_for_child == "apresentation":
    child_prompt = _build_child_prompt_apresentation(...)
elif route_for_child == "follow-up":
    child_prompt = _build_child_prompt_follow_up(...)
elif route_for_child == "closing":
    child_prompt = _build_child_prompt_closing(...)
else:
    child_prompt = _build_child_prompt(...)  # fallback genérico
```

**Chamada:** `llm_service.generate_child_result(route_to, child_prompt)`

---

### Filha QUALIFICATION

**Função:** `_build_child_prompt_qualification(context, message_text, mother_decision)`

**System prompt:**
```
Você é a FILHA QUALIFICATION e deve responder SOMENTE JSON válido.
```

**Responsabilidade:** Opera em dois modos controlados por `response_style`. Nunca agenda reunião nesta fase.

#### Fontes dos campos de qualificação

Os campos obrigatórios e opcionais vêm exclusivamente do `qualification_fields` do AI Profile — não há lista hardcoded por `agent_mode`. Quando não configurado → nenhum campo obrigatório.

`_build_qualification_fields_block(ai_profile, response_style)` constrói o bloco de contexto injetado no prompt a partir de `qualification_fields`.

#### Contexto adicional injetado

```json
{
  "response_style": "active | passive",
  "must_collect_with_questions": [
    {"key": "availability_window", "label": "Disponibilidade", "question": "Qual horário funciona?", "passive_hint": "se lead mencionar horário"}
  ],
  "nice_to_collect": [
    {"key": "service_interest", "label": "Serviço", "question": "O que você busca?", "passive_hint": "pelo contexto"}
  ],
  "passive_hints": "... apenas em response_style=passive",
  "closing_questions": "... campos com allow_closing_question=true — apenas em response_style=passive",
  "current_field": "campo que deve ser perguntado agora",
  "asked_questions_for_current_field": ["perguntas já feitas para esse campo"],
  "missing_fields": ["campos ainda não coletados"],
  "filled_fields": { "service_interest": "valor já coletado" }
}
```

#### Modo `active`

```
Responde SEMPRE à mensagem do cliente antes de qualificar.
Se o cliente fez uma pergunta, responde usando offer_description e custom_instructions.
Depois, se houver campos obrigatórios em falta, adicione UMA pergunta de qualificação natural
ao final — usando a `question` configurada no campo, ou reformulando se já foi perguntado antes.
Nunca respondas APENAS com uma pergunta de qualificação.
```

- Máximo 1 pergunta de qualificação por turno
- `field` deve ser EXATAMENTE o `current_field` quando `should_ask=true`
- Campos `custom_*`: usar a `question` configurada em `qualification_fields`

#### Modo `passive`

```
NUNCA faças perguntas abertas de qualificação.
Responde de forma persuasiva, guiando para o próximo passo:
  - Use prova social, benefícios concretos e contexto da oferta
  - Conduza para agendamento, proposta ou pagamento sem pressão excessiva
Se o lead mencionar dados relevantes, registre internamente — não peça por eles.
ÚNICA EXCEÇÃO: campos com closing_question configurada (alternativas binárias/confirmações
tipo "às 15h ou 16h?") — nunca perguntas abertas.
```

**Saída:**

```json
{
  "question_text": "Texto da pergunta a enviar (null em modo passive)",
  "field": "nome_do_campo | null",
  "should_ask": true,
  "message_text": "mensagem completa a enviar",
  "did_complete_phase": false,
  "recommended_next_category": "apresentation | null",
  "signals_structured": {
    "missing_fields": ["urgency"],
    "handoff_requested": false
  },
  "confidence": 0.82
}
```

**Guardrails internos:**
- Se o mesmo campo for perguntado ≥2 vezes → acionar handoff automático
- A pergunta gerada é validada por similaridade com o histórico (evitar loop)
- Máximo de 2 tentativas de geração na filha antes de fallback

---

### Filha APRESENTATION

**Função:** `_build_child_prompt_apresentation(context, message_text, mother_decision)`

**System prompt:**
```
Você é a FILHA APRESENTATION e deve responder SOMENTE JSON válido.
```

**Responsabilidade:** Conduzir a fase de apresentação — agendamento ou oferta — conforme a variante do agente.

**Variantes:**

#### `presentation_variant: "scheduler"` (agenda / hybrid_scheduler)

- Propor dias e horários disponíveis
- Confirmar ou reagendar reunião
- Enviar link de reunião quando aplicável

```json
"signals_structured": {
  "meeting_proposed": true,
  "meeting_datetime_candidate": "2026-03-30T15:00:00",
  "offer_presented": false,
  "checkout_sent": false,
  "presentation_variant": "scheduler"
}
```

#### `presentation_variant: "sales"` (direto / Agent 2)

- **Ação 1 — Confirmar:** Descreve oferta e pergunta se quer seguir. `checkout_sent: false`
- **Ação 2 — Enviar link:** Oferta + link de checkout + próximo passo. `checkout_sent: true`

```json
"signals_structured": {
  "offer_presented": true,
  "checkout_sent": true,
  "offer_item_name": "Pacote Premium",
  "presentation_variant": "sales"
}
```

**Warm-up (hybrid_scheduler — pós-qualificação completa):**

Ativado quando `template_key == "hybrid_scheduler"` + `missing_fields` vazio + `appointment_mode == "exploratory"`. O prompt instrui a filha a fazer uma mensagem de aquecimento antes de propor o agendamento:
1. **Prova social** — contexto do perfil do lead com o serviço
2. **Preview da sessão** — o que acontecerá na reunião

**Saída geral:**

```json
{
  "message_text": "Mensagem WhatsApp a enviar",
  "did_complete_phase": false,
  "recommended_next_category": null,
  "outcome": null,
  "kanban_highlight": null,
  "signals": ["meeting_proposed"],
  "signals_structured": { "..." : "..." },
  "confidence": 0.90
}
```

---

### Filha FOLLOW-UP

**Função:** `_build_child_prompt_follow_up(context, message_text, mother_decision)`

**System prompt:**
```
Você é a FILHA FOLLOW-UP e deve responder SOMENTE JSON válido.
```

**Responsabilidade:** Nutrir o lead pós-apresentação, tratar objeções, gerenciar no-shows e reagendamentos.

**Contexto adicional injetado:**

```json
{
  "followup_context": {
    "followup_goal": "...",
    "followup_outcome": "interested_not_closed | reschedule_needed | converted",
    "followup_variant": "sdr_scheduler | cart_recovery | hybrid_scheduler",
    "attempts": 1,
    "meeting_happened": true,
    "proposal_sent": false
  },
  "is_followup_tick": true
}
```

**Variantes de follow-up:**

#### `sdr_scheduler`
Nutrição consultiva pós-reunião: reforça valor, síntese do contexto, próximo passo comercial.

#### `cart_recovery` (Agent 2)

| Tentativa | Abordagem | Limite |
|---|---|---|
| 1 | Lembrete neutro (pedido ainda reservado, link disponível) | 280 chars |
| 2 | Benefício principal + objeção comum | 280 chars |
| 3 | Urgência máxima (oferta expira hoje) | 280 chars |

#### `hybrid_scheduler`

| Outcome | Comportamento |
|---|---|
| `interested_not_closed` | Mantém momentum, remove objeção, oferece nova data concreta |
| `reschedule_needed` | Tom leve, propõe 2–3 opções de horário, pergunta fechada |
| `converted` | Tom de boas-vindas, confirma próximo passo, envia link de pagamento ou acesso |

**Regra para follow-up automático (`is_followup_tick: true`):**
- Usar `followup_contract_signals` como fonte primária
- **Não** reperguntar campos de qualificação — `qualification_state` é memória de leitura
- Só faz nova pergunta se diretamente ligada ao objetivo do follow-up (remarcação, confirmação de presença)

**Saída:**

```json
{
  "message_text": "Mensagem WhatsApp a enviar",
  "did_complete_phase": false,
  "recommended_next_category": "follow-up | closing | null",
  "outcome": null,
  "kanban_highlight": null,
  "signals": ["reschedule_requested"],
  "signals_structured": {
    "missing_fields": [],
    "handoff_requested": false
  },
  "confidence": 0.75
}
```

---

### Filha CLOSING

**Função:** `_build_child_prompt_closing(context, message_text, mother_decision)`

**System prompt:**
```
Você é a FILHA CLOSING e deve responder SOMENTE JSON válido.
```

**Responsabilidade:** Finalizar o fechamento. Comportamento difere por modo de agente.

| Modo | Comportamento |
|---|---|
| `consultivo` | Não fecha sozinho — aciona handoff para humano nos passos finais |
| `agenda` | Fechamento operacional: confirmar horário, políticas, pagamento se aplicável |
| `direto` | Fechamento direto com confirmação de pagamento |

**Saída:**

```json
{
  "message_text": "Mensagem WhatsApp a enviar",
  "did_complete_phase": false,
  "recommended_next_category": "closing | null",
  "outcome": "won | lost | null",
  "kanban_highlight": "green | orange | null",
  "signals": ["payment_confirmed"],
  "signals_structured": {
    "missing_fields": [],
    "handoff_requested": false
  },
  "confidence": 0.95
}
```

---

### Filha Genérica (Fallback)

**Função:** `_build_child_prompt(context, message_text, mother_decision)`

Usada quando nenhuma rota específica é reconhecida. Gera uma resposta genérica com o mesmo schema `ChildResult`. Cobre casos de erro e rotas inesperadas sem quebrar o pipeline.

---

## Schema Compartilhado — `ChildResult`

Todas as filhas retornam o mesmo schema base, definido em `orchestrator_models.py`:

```python
class ChildResult(BaseModel):
    message_text: str = ""
    question_text: Optional[str] = None       # usado pela filha qualification
    field: Optional[str] = None               # campo de qualificação perguntado
    should_ask: Optional[bool] = None
    did_complete_phase: bool = False
    recommended_next_category: Optional[str] = None
    outcome: Optional[Literal["won", "lost"]] = None
    kanban_highlight: Optional[Literal["green", "orange"]] = None
    signals: list[str] = Field(default_factory=list)
    signals_structured: Optional[dict] = None
    confidence: float = Field(ge=0.0, le=1.0)
```

---

## Saída Final — `DecisionOutput`

Após a composição da decisão da mãe com o resultado da filha (incluindo guardrails), o pipeline produz:

```python
class DecisionOutput(BaseModel):
    next_action: Literal["reply", "ask_qualification", "handoff", "ignore"]
    message_text: str = ""
    reason: str
    suggested_category: Optional[str] = None
    outcome: Optional[Literal["won", "lost"]] = None
    kanban_highlight: Optional[Literal["green", "orange"]] = None
    signals: list[str] = Field(default_factory=list)
    signals_structured: Optional[dict] = None
    confidence: float = 0.0
    decision_trace: Optional[dict] = None   # observabilidade completa
    pre_send_media: Optional[dict] = None   # injeção de mídia (Agent 2)
```

---

## Fluxo Completo (Resumo)

```
1. Mensagem chega via webhook WhatsApp
2. decision_engine.decide(context) é chamado
3. [ MÃE ] _build_mother_prompt → llm_service.generate_mother_route → MotherDecision
4. Se rota=qualification → field_extractor extrai campos e atualiza qualification_state
5. [ FILHA ] _build_child_prompt_<rota> → llm_service.generate_child_result → ChildResult
   ↳ response_style (active/passive) e qualification_fields do AI Profile injetados na filha qualification
6. Guardrails aplicados: loop de qualificação, ordem de etapas, modo de agente
7. compose_decision_output monta o DecisionOutput final
8. Mensagem enviada ao WhatsApp + Kanban/CRM atualizado
```

---

## Serviço LLM

**Arquivo:** `backend-executors/app/services/llm_service.py`

**Funções:**

```python
generate_mother_route(prompt: str) -> str
    # Chamada da mãe — JSON com MotherDecision

generate_child_result(route: str, prompt: str) -> str
    # Chamada da filha — JSON com ChildResult

generate_decision_text(prompt: str) -> str
    # Chamada genérica (sem rota)
```

**Formato da requisição:**
```python
{
  "model": settings.llm_model,
  "input": "texto do prompt",
  "text": {"format": {"type": "json_object"}},  # modo JSON
  "metadata": {"route": "qualification"}         # apenas para filha
}
```

**Stubs (sem API configurada):**
```python
# Mãe:  {"route_to": "qualification", "confidence": 0.5, "reason": "stub_no_key"}
# Filha: {"message_text": "Olá!", "did_complete_phase": false, "confidence": 0.5}
```
