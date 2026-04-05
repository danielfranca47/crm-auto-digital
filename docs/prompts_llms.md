# Prompts LLM — Referência Oficial

> **Atualizado em:** 2026-04-05
> **Escopo:** Todos os prompts enviados a LLMs no sistema
> **Arquivos cobertos:** `backend-executors/app/services/decision_engine.py`, `backend-executors/app/services/field_extractor.py`, `backend-crm/automations/assistente_ia/llm.py`

---

## Visão geral da arquitetura de prompts

O sistema usa **dois tipos de LLM** com propósitos distintos:

| Tipo | Onde | Papel |
|---|---|---|
| **Decisão / Execução** | `decision_engine.py` | Processa inbound WhatsApp, roteia o lead pelo funil e gera a resposta comercial |
| **Geração de outreach** | `llm.py` | Gera cold outreach (e-mail, WhatsApp, Instagram, roteiro de ligação) para prospecção |
| **Extração** | `field_extractor.py` | Extrai campos de qualificação estruturados da conversa |

Todos os prompts de `decision_engine.py` e `field_extractor.py` retornam **SOMENTE JSON válido** — sem texto livre, sem markdown. A LLM em `llm.py` retorna texto ou JSON dependendo do canal.

---

## 1. Motor de Decisão — `decision_engine.py`

Este arquivo implementa uma **arquitetura Mãe + Filha**: a LLM Mãe roteia o lead para a fase correta do funil; a LLM Filha especializada executa a ação naquela fase.

```
Inbound WhatsApp
    ↓
_build_mother_prompt()   ← LLM Mãe: decide em qual fase o lead está
    ↓
_build_child_prompt_qualification()   ← se em qualificação
_build_child_prompt_apresentation()   ← se em apresentação/agendamento
_build_child_prompt_follow_up()       ← se em follow-up
_build_child_prompt_closing()         ← se em fechamento
```

Há também `_build_prompt()` como fallback geral (decisão simples sem fase especializada).

---

### 1.1 `_build_prompt()` — Motor de decisão geral (fallback)

**Papel da LLM no prompt:**
> "Você é um motor de decisão de um CRM (WhatsApp)."

A LLM age como um sistema de roteamento puro — não tem persona, não tem nome, não é o agente comercial. Decide a ação (`reply`, `ask_qualification`, `handoff`, `ignore`) e redige a resposta se necessário.

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

**Variáveis dinâmicas injetadas no prompt:**

| Variável | Origem | Conteúdo |
|---|---|---|
| `lead_summary` | banco CRM | id, nome, telefone, segmento, status, categoria |
| `ai_summary` | `ai_profiles` (core) | template_key, agent_mode, brand_name, tone_of_voice, niche, target_audience, offer_description, goals, custom_instructions, identity_mode, handoff_policy, handoff_custom_text, `appointment_mode` |
| `playbook_summary` | playbook | nome/template do playbook |
| `metadata_summary` | inbound | provider, instance_id |
| `allowed_categories` | sistema | lista de categorias Kanban permitidas |
| `history_text` | banco CRM | histórico formatado da conversa |
| `last_bot_message` | banco CRM | última mensagem enviada pelo bot |
| `short_reply_hint` | sistema | hint se detectado reply curto esperado |
| `agent_mode_normalized` | `ai_profiles` | modo normalizado (consultivo, agenda, direto, etc.) |
| `required_fields` | `qualification_fields` do AI Profile | campos de qualificação com `mode=required` |
| `missing_fields` | `qualification_state` | campos ainda não coletados |
| `current_field` | sistema | próximo campo a ser coletado |
| `asked_questions_for_current_field` | histórico | perguntas já feitas para o campo atual |
| `last_question_text` | histórico | última pergunta enviada |
| `lead_origin_label` | lead | origem do lead (formulário, WhatsApp direto, etc.) |
| `origin_opener` | `ai_profiles` | texto de abertura personalizado por origem |
| `message_text` | inbound | mensagem atual do lead |

**Regras de copy/comportamento embutidas no texto:**
- Nunca usa categorias fora de `ALLOWED_LEAD_CATEGORIES`
- Se inbound for genérico ("oi"), pergunta UMA coisa — não sugere categoria
- `handoff` só em pedido explícito de humano
- `short_reply_hint`: se presente, responde ao contexto anterior sem iniciar assunto novo

---

### 1.2 `_build_mother_prompt()` — Roteador Mãe

**Papel da LLM no prompt:**
> "Você é um roteador MÃE de um CRM (WhatsApp)."

A LLM não responde ao lead — apenas decide para qual fase do funil rotear: `qualification`, `apresentation`, `follow-up` ou `closing`. É uma LLM de roteamento puro.

**Output esperado:**
```json
{
  "route_to": "qualification|apresentation|follow-up|closing",
  "perceived_category": "...|null",
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
  "next_action_hint": "reply|ask_qualification|handoff|ignore|null"
}
```

**Variáveis dinâmicas injetadas:** mesmas de `_build_prompt()`.

**Regras de copy/comportamento embutidas no texto:**

| Regra | Descrição |
|---|---|
| **PRIORIDADE 1** | Responder SEMPRE à mensagem do cliente — nunca bloquear resposta por qualificação pendente |
| **PRIORIDADE 2** | Se a mensagem não contém pergunta direta E há campos pendentes → preferir `route_to="qualification"` |
| Proibição de bloqueio | `route_to="qualification"` nunca pode ser a ÚNICA resposta se o cliente fez uma pergunta direta |
| Definição de APRESENTATION | Agendar reunião, confirmar horário, reagendar, enviar link, confirmar presença |
| Definição de FOLLOW-UP | Só pós-apresentação realizada com evidência textual — nunca por mera intenção de compra |
| Modo `sdr_scheduler` | Qualquer confirmação de horário → `apresentation` + `meeting_scheduled=true` |
| Modo `closer` | `meeting_scheduled=false` por padrão; fechamento é `closing`, não `apresentation` |

**Exemplos de saída fornecidos no próprio prompt** (10 casos) — usados como treinamento in-context para respostas consistentes.

---

### 1.3 `_build_child_prompt_qualification()` — Filha Qualificação

**Papel da LLM no prompt:**
> "Você é a FILHA QUALIFICATION"

Opera em dois modos controlados por `response_style`. Coleta campos de qualificação um por vez, reformulando se já foram perguntados antes. Nunca agenda reunião nesta fase.

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

**Variáveis dinâmicas adicionais:**

| Variável | Descrição |
|---|---|
| `response_style` | `"active"` ou `"passive"` — controla se o agente pergunta proativamente ou persuade |
| `must_collect_with_questions` | Campos `mode=required` com `question` e `passive_hint` — injetado apenas em `active` |
| `nice_to_collect` | Campos `mode=optional` com `question` e `passive_hint` — ambos os estilos |
| `passive_hints` | Dicas de captura passiva por campo — injetado apenas em `passive` |
| `closing_questions` | Perguntas estratégicas de fechamento (alternativas binárias/confirmações) — única pergunta permitida no passivo |
| `current_field` | Campo específico a ser coletado neste turno |
| `asked_for_current` | Perguntas já feitas para este campo — a LLM deve REFORMULAR, não repetir |
| `route_to`, `confidence`, `reason` | Decisão da Mãe — injetada no prompt |

**Regras de copy/comportamento — modo `active`:**

```
Responde SEMPRE à mensagem do cliente antes de qualificar.
Se o cliente fez uma pergunta, responde usando offer_description e custom_instructions.
Depois, se houver campos obrigatórios em falta, adicione UMA pergunta de qualificação
natural ao final — usando a `question` configurada no campo, ou reformulando se já foi
perguntado antes.
Nunca respondas APENAS com uma pergunta de qualificação.
```

- Máximo 1 pergunta por turno (após a resposta ao cliente)
- `field` deve ser EXATAMENTE o `current_field` quando `should_ask=true`
- Campos `custom_*`: usar a `question` configurada em `qualification_fields`
- Proibido agendar reunião aqui

**Regras de copy/comportamento — modo `passive`:**

```
NUNCA faças perguntas para coletar dados de qualificação.
Responde sempre de forma persuasiva, guiando naturalmente para o próximo passo:
  - Use prova social, benefícios concretos e contexto da oferta para criar motivação
  - Conduza para o próximo passo (agendamento, proposta, pagamento) de forma direta mas sem pressão
Se o lead mencionar dados relevantes, registre internamente — mas não peça por eles.
ÚNICA EXCEÇÃO: se o campo tem `closing_question` configurada (confirmações e alternativas
binárias tipo "às 15h ou 16h?"), ela pode ser usada — nunca perguntas abertas.
```

---

### 1.4 `_build_child_prompt_apresentation()` — Filha Apresentação

**Papel da LLM no prompt:**
> "Você é a FILHA APRESENTATION"

É o prompt mais complexo do sistema. Tem dois modos de operação internos controlados por `presentation_variant`:

- **`sales`** — apresenta oferta com preço, conduz ao fechamento ou envio de link de checkout
- **`scheduler`** — conduz agendamento (propor horário, confirmar, reagendar, enviar link de call)

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

**Variáveis dinâmicas adicionais:**

| Variável | Origem | Descrição |
|---|---|---|
| `presentation_variant` | `ai_profiles` | `sales` ou `scheduler` |
| `hybrid_flow_style` | `ai_profiles` | `offer_then_schedule` ou `schedule_then_offer` |
| `offer_pack_summary` | `ai_profiles` > catálogo | itens da oferta, preços, mídia, garantia, preço âncora |
| `appointment_mode` | `ai_profiles` | `exploratory` ou `commercial` (para `hybrid_scheduler`) |
| `knowledge_items` | tabela `knowledge_items` | categorias comerciais (ver seção 1.4.2) |
| `warming_social_proof` | `ai_profiles` | texto de prova social configurado pelo usuário |
| `warming_session_preview` | `ai_profiles` | preview da sessão/serviço configurado pelo usuário |
| `template_key_for_warming` | `ai_profiles` | verifica se é `hybrid_scheduler` para ativar injeção |

**Regras de copy do modo `sales`:**
- **UM TURNO = UMA AÇÃO**: ou apresenta/confirma sem link, ou envia link — nunca os dois
- Quando confirma sem link: `checkout_sent=false` — proibido URL ou placeholder de link
- Quando envia link: `checkout_sent=true` — não pede permissão no mesmo turno
- Oferece `anchor_price` se disponível: "De R$X por apenas R$Y"
- Menciona `guarantee_text` se disponível
- Se `media_url` presente: a mídia já foi enviada automaticamente — NÃO mencionar "veja a imagem/vídeo"

**Regras de copy do modo `scheduler`:**
- Sempre preenche `meeting_proposed` e `meeting_datetime_candidate`
- ISO naive no timezone de `ai_profile.timezone` (ex.: `2026-03-05T17:00:00`)
- Se houver confirmação final: inclui `meeting_scheduled` nos signals

#### 1.4.1 Injeção WARMING (modo `exploratory`)

Ativado quando: `template_key == "hybrid_scheduler"` + fase pós-qualificação + `appointment_mode == "exploratory"`.

**Texto injetado no prompt:**
```
- ESTÁGIO WARMING (pós-qualificação aprovada para hybrid_scheduler): O lead acabou de concluir
  a qualificação. Antes de propor o agendamento, execute os 2 passos de aquecimento em UMA
  mensagem natural:
  1. PROVA SOCIAL: {warming_social_proof ou fallback padrão}
  2. PRÉVIA DA SESSÃO: {warming_session_preview ou fallback padrão}
  Combine os 2 passos de forma fluida e, ao final, proponha o agendamento da sessão.
  Não mencione os termos 'prova social' ou 'prévia da sessão' explicitamente — use linguagem natural.
```

**Fallback padrão de prova social** (quando não configurado):
```
"Tenho ajudado muitas pessoas a transformarem [área de atuação] com resultados concretos. Cada sessão é personalizada para o que você precisa."
```

**Fallback padrão de preview da sessão** (quando não configurado):
```
"Nossa sessão tem [duração configurável] — combinamos um horário que funcione para você, trabalhamos com foco total no seu objetivo e você sai com clareza e próximos passos concretos."
```

#### 1.4.2 Injeção COMMERCIAL (modo `commercial`)

Ativado quando: `template_key == "hybrid_scheduler"` + fase pós-qualificação + `appointment_mode == "commercial"`.

**Texto injetado no prompt:**
```
- MODO COMERCIAL (hybrid_scheduler — compromisso antes do agendamento):
  O lead concluiu a qualificação. Seu objetivo neste turno e nos seguintes é:
  1. Aquecer com prova social (se disponível)
  2. Apresentar os serviços/pacotes disponíveis com clareza
  3. Tratar objeções conforme as respostas configuradas
  4. Obter o compromisso verbal/escrito do lead com um serviço ou pacote específico
  5. SÓ ENTÃO propor o agendamento
  REGRA CRÍTICA: o pagamento é SEMPRE presencial na marcação — NUNCA envie link de checkout.
  Não mencione modalidade 'exploratória' ou 'diagnóstico gratuito' — a sessão já tem valor definido.
  PROVA SOCIAL: {social_proof ou fallback}
  TABELA DE SERVIÇOS/PREÇOS: {service_pricing_table ou fallback}
  OBJEÇÕES E RESPOSTAS: {commercial_objections ou fallback}
  [DIFERENCIAIS DO SERVIÇO: {service_differentials}]   ← se preenchido
  [CONDIÇÃO ESPECIAL VIGENTE: {active_promotion}]       ← se preenchida
  [POLÍTICA DE PAGAMENTO PRESENCIAL: {payment_policy}] ← se preenchida
  [FAQ PRÉ-COMPROMISSO: {pre_commitment_faq}]           ← se preenchido
  Após o lead confirmar a escolha de serviço/pacote, proponha o agendamento normalmente.
```

**Fallbacks por campo quando não configurado:**

| Campo | Fallback |
|---|---|
| `social_proof` | "(não configurada — use tom acolhedor e destaque o diferencial do profissional)" |
| `service_pricing_table` | "(não configurada — pergunte o interesse antes de citar valores)" |
| `commercial_objections` | "(não configurada — use empatia e reformule o valor entregue)" |

Os campos `service_differentials`, `active_promotion`, `payment_policy` e `pre_commitment_faq` só aparecem no prompt se estiverem preenchidos.

---

### 1.5 `_build_child_prompt_follow_up()` — Filha Follow-up

**Papel da LLM no prompt:**
> "Você é a FILHA FOLLOW-UP"

Responsável por re-engajar leads pós-apresentação. O comportamento muda radicalmente por `followup_variant`.

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

**Variáveis dinâmicas adicionais:**

| Variável | Descrição |
|---|---|
| `followup_summary` | goal, outcome, variant, attempts, max_attempts, meeting_happened, proposal_sent, operator_note, status |
| `followup_variant` | `sdr_scheduler`, `cart_recovery` ou `hybrid_scheduler` |
| `is_followup_tick` | `true` = disparo automático agendado; `false` = resposta a inbound |
| `next_attempt` | número da tentativa atual (para `cart_recovery`) |
| `attempt_instruction` | instrução específica para aquela tentativa |
| `outcome` | `interested_not_closed`, `reschedule_needed`, `converted`, etc. |

**Regras de copy por variante:**

#### `sdr_scheduler`
```
Variante sdr_scheduler: follow-up consultivo pós-reunião; reforçar valor, síntese do contexto
e próximo passo comercial.
```

#### `cart_recovery` (Agente 02 — low ticket)
```
Variante cart_recovery: recuperar pagamento pendente após link enviado. Mensagens curtas (máx 280 chars).
Tentativa 1: lembrete neutro (sem pressão)
Tentativa 2: benefício + objeção (tom amigável)
Tentativa 3: urgência máxima (CTA direto, não reabra qualificação)
```

#### `hybrid_scheduler` (Agente 03 — coaches/terapeutas)
```
Variante hybrid_scheduler: tom pessoal e próximo, como assistente do próprio profissional
— nunca SDR agressivo.
```

Por `outcome`:
| Outcome | Instrução |
|---|---|
| `interested_not_closed` | Retome contexto, remova objeção, ofereça nova data |
| `reschedule_needed` | Tom leve, ofereça 2-3 horários, encerre com pergunta fechada |
| `converted` | Tom de onboarding, parabenize, confirme próximo passo, envie link/instrução |
| outros | Priorizar recuperação de no-show |

**Comportamento especial em `is_followup_tick=true`:**
- `followup_contract_signals` é a fonte principal — não o histórico de qualificação
- Histórico é **memória contextual** — não é backlog de perguntas pendentes
- `missing_fields` de qualificação são **read-only** — proibido usá-los como alvo de coleta
- Só faz nova pergunta se diretamente ligada ao objetivo do follow-up (remarcação, confirmação de presença)

---

### 1.6 `_build_child_prompt_closing()` — Filha Closing

**Papel da LLM no prompt:**
> "Você é a FILHA CLOSING"

Conduz o fechamento. O comportamento por `agent_mode` é central.

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

**Regras de copy por `agent_mode`:**

| Modo | Comportamento |
|---|---|
| `consultivo` | Não fecha sozinho; responde curto e encaminha para humano |
| `agenda` | Fechamento operacional — confirma horário, políticas, pagamento |
| `direto` | Conduz fechamento e confirmação de pagamento com objetividade |

**Variáveis dinâmicas:** mesmas das outras filhas + `required_fields` e `missing_fields` explicitados no prompt.

---

### 1.7 `_build_child_prompt()` — Filha genérica (fallback)

**Papel da LLM no prompt:**
> "Você é uma LLM FILHA"

Fallback usado quando nenhuma fase especializada é selecionada. Sem persona, sem instruções de modo.

**Output esperado:** mesmo schema das outras filhas.

---

### 1.8 Contrato de Qualificação — `qualification_fields`

O AI Profile é a **única fonte de verdade** de qualificação. O campo `qualification_fields` unifica o que o agente pergunta, como infere passivamente, e o que bloqueia avanço de estágio no Kanban.

**Schema do campo:**

```typescript
interface QualificationField {
  key: string;                  // Campo do sistema: "availability_window", "service_interest", etc.
                                // Campo personalizado: "custom_" + slug(label) — ex: "custom_nome_do_pet"
  label: string;                // "Disponibilidade" | "Nome do pet"
  question?: string;            // Pergunta para modo ativo: "Qual horário funciona?"
  passive_hint?: string;        // Como capturar passivamente: "Se lead mencionar horário"
  closing_question?: string;    // Pergunta estratégica de fechamento (alternativas binárias/confirmações)
  allow_closing_question: boolean;
  mode: 'required' | 'optional' | 'off';
  group?: 'f1' | 'f2' | 'f3'; // Apenas para SDR (agent_mode="sdr_scheduler")
}
```

**Campos do sistema predefinidos** (extraction engine extrai automaticamente):

| key | label sugerida |
|---|---|
| `service_interest` | Serviço de interesse |
| `availability_window` | Disponibilidade |
| `price_acceptance` | Aceitação de preço |
| `location_preference` | Preferência de local |
| `urgency` | Urgência |
| `decision_role` | Decisor |
| `budget_or_price_acceptance` | Orçamento |
| `constraints` | Restrições |

**Campos personalizados (`custom_*`):** o `field_extractor.py` usa a `question` para extrair via LLM e armazena o resultado em `data_json` de `lead_qualification_state` sob a `key` configurada.

**Como os campos são injetados no prompt:**

```
# Modo active → must_collect_with_questions + nice_to_collect
Informações OBRIGATÓRIAS:
  - Disponibilidade: pergunta "Qual horário funciona para você?" | inferir: "se lead mencionar horário"
  - [custom] Nome do pet: pergunta "Qual o nome do seu pet?"

Informações DESEJÁVEIS (capturar se surgir):
  - Serviço de interesse: pergunta "O que você busca?" | inferir: "pelo contexto"

# Modo passive → passive_hints + closing_questions
Capturar passivamente (sem perguntar):
  - Disponibilidade: "Capturar se lead mencionar horário, data ou 'semana que vem'"

Perguntas estratégicas de fechamento permitidas:
  - Disponibilidade: "Você teria disponibilidade na quinta às 14h ou na sexta às 10h?"
```

**Derivação automática:** `qualification_required_fields` é derivado como `qualification_fields.filter(mode="required").map(key)` ao salvar o AI Profile. Guardrails do Kanban e executores leem `qualification_required_fields`. `qualification_fields=null` ou `qualification_required_fields=null` → nenhum campo obrigatório, sem fallback.

---

## 2. Extrator de Campos — `field_extractor.py`

**Papel da LLM no prompt:** instrução técnica direta, sem persona.

> "Você é um extractor de campos de qualificação."

**Função:** `extract_fields_llm(context, fields_schema)`

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

**Variáveis dinâmicas injetadas:**

| Variável | Descrição |
|---|---|
| `fields_schema` | Schema JSON com campos e tipos — inclui campos do sistema e campos `custom_*` de `qualification_fields` do AI Profile. Para `custom_*`, o `passive_hint` configurado é incluído como instrução de extração. |
| `inbound` | Mensagem atual do lead |
| `history` (últimas 6) | Histórico recente formatado como `[bot/lead]: texto` |

---

## 3. Geração de Outreach — `llm.py`

Este arquivo tem dois papéis LLM distintos, definidos como **system prompts fixos**, não dinâmicos.

### System prompts

| Função | System Prompt | Uso |
|---|---|---|
| `_chat_text()` | `"Você é um assistente de prospecção objetivo e cordial."` | Geração de texto livre (scripts de ligação) |
| `_chat_json()` | `"Você escreve e-mails comerciais objetivos e cordiais."` | Geração de JSON estruturado (e-mail, WhatsApp, Instagram) |

### `generate_for_lead()` — Prompts por canal

**Função:** `generate_for_lead(lead, channels, tone, language, context, sender)`

**Bloco de contexto comum** (injetado em todos os canais):
```
Empresa do prospect: {lead.companyName}
Cenário: {scenario}
Contexto: {ctx_summary}
Remetente: Nome={sender.name}; Empresa={sender.company}; Email={sender.email}; Telefone={sender.phone}
NUNCA use placeholders como [Seu Nome] ou [Sua Empresa]; use os dados do Remetente fornecidos.
Se contactName estiver vazio, cumprimente pela empresa (ex.: 'Olá, A Casa do Porco Bar').
```

**Variáveis dinâmicas globais:**

| Variável | Origem | Conteúdo |
|---|---|---|
| `lead.companyName` | banco CRM | nome da empresa prospectada |
| `lead.contactName` | banco CRM | nome do contato (pode ser vazio) |
| `scenario` | computado | `no_site`, `weak_site` ou `decent_site` |
| `ctx_summary` | computado | flags formatadas: `mobile_ready`, `ssl_ok`, `issues_count`, `services_keywords`, `instagram_handle`, `trust_score_adj`, `next_action` |
| `tone` | parâmetro | tom de voz escolhido pelo usuário |
| `language` | parâmetro | idioma do output (`pt-PT`, `pt-BR`, `en`, etc.) |
| `sender.name/company/email/phone/signature` | perfil do usuário | dados do remetente |

**Variáveis template pós-processadas** (não resolvidas pela LLM — substituídas depois):
- `{{prospect.company}}` — substituído pelo nome da empresa
- `{{sender.signature}}` — substituído pela assinatura do remetente

---

#### Canal: E-mail

**Prompt:**
```
[contexto comum]
Escreva um e-mail em {language} com tom {tone}.
Regras: assunto <= 60 caracteres; corpo com 120–180 palavras; sem links;
parágrafos separados por uma linha em branco;
CTA final: 'Posso enviar 2 ideias e valores?'.
Se cenário='no_site': proponha site próprio com CTA/WhatsApp.
Se cenário='weak_site': 2–3 melhorias rápidas (mobile/HTTPS/SEO) + convite para call de 15 min.
Se cenário='decent_site': foque em automações de captação (form->WhatsApp, agendador, chat) e teste-piloto.
Retorne como JSON: {"subject":"...","body":"..."}
Use as variáveis literais {{prospect.company}} e {{sender.signature}} nos locais apropriados.
```

**Comportamento de copy por cenário:**

| Cenário | Instrução ao LLM |
|---|---|
| `no_site` | Propor criação de site com CTA + WhatsApp |
| `weak_site` | 2–3 melhorias rápidas (mobile, HTTPS, SEO) + convite call 15 min |
| `decent_site` | Focar em automações (form→WhatsApp, agendador, chat) + teste-piloto |

---

#### Canal: WhatsApp

**Prompt:**
```
[contexto comum]
Escreva uma mensagem de WhatsApp em {language} com tom {tone}.
Comprimento: 4–6 linhas; sem links;
CTA final pedindo permissão para enviar 2 ideias e valores.
Use {{prospect.company}} onde a empresa deva aparecer e assine como '{{sender.name}}, {{sender.company}}'.
```

---

#### Canal: Instagram DM

**Prompt:**
```
[contexto comum]
Escreva uma DM curta em {language} com tom {tone}.
Comprimento: 2–4 linhas; amigável; sem parecer spam;
CTA: posso enviar 2 ideias curtas?
Use {{prospect.company}} e '@handle' se existir.
```

---

#### Canal: Roteiro de Ligação

**Prompt:**
```
[contexto comum]
Monte um roteiro de ligação em {language} com bullets:
abertura (10–15s), 2–3 perguntas, pitch 20s (site/automação) e CTA de próximo passo.
```

---

## 4. Variáveis de identidade e copy do `ai_profile`

Estas variáveis são injetadas nos prompts do `decision_engine` e controlam o tom e a persona da LLM ao responder o lead:

| Campo | Chave | Descrição |
|---|---|---|
| Nome do agente/marca | `brand_name` | Usado em apresentações e assinatura |
| Tom de voz | `tone_of_voice` | Ex.: "formal e empático", "descontraído e direto" |
| Nicho | `niche` | Segmento de mercado — contextualiza respostas |
| Público-alvo | `target_audience` | Quem é o lead ideal — afeta linguagem |
| Oferta | `offer_description` | Resumo do que está sendo vendido |
| Objetivos | `goals` | O que o agente deve alcançar (ex.: "agendar consulta") |
| Instruções customizadas | `custom_instructions` | Campo livre — regras específicas do usuário |
| Modo de identidade | `identity_mode` | Define como o agente se apresenta (ex.: como assistente do profissional) |
| Política de handoff | `handoff_policy` | Quando e como transferir para humano |
| Texto de handoff | `handoff_custom_text` | Mensagem usada na transferência |
| Prova social (warming) | `warming_social_proof` | Texto de prova social para fase de aquecimento |
| Preview da sessão | `warming_session_preview` | Descrição do que acontece na marcação |
| Modo de compromisso | `appointment_mode` | `exploratory` ou `commercial` (Agente 03) |
| Estilo de resposta | `response_style` | `"active"` (pergunta proativamente) ou `"passive"` (persuade sem perguntar). Default `"passive"` quando `null`. |
| Campos de qualificação | `qualification_fields` | `QualificationField[]` — source of truth para guardrails, prompts e extraction engine (ver seção 1.8) |
| Campos obrigatórios | `qualification_required_fields` | Derivado de `qualification_fields[mode=required].map(key)`. Lido pelos guardrails do Kanban e executores. `null` = nenhum campo obrigatório. |

---

## 5. Mapa de injeções condicionais

Alguns blocos só são injetados no prompt se certas condições forem atendidas:

| Bloco | Condição de ativação |
|---|---|
| `must_collect_with_questions` | `response_style == "active"` + `qualification_fields` com `mode=required` |
| `nice_to_collect` | `qualification_fields` com `mode=optional` (ambos os estilos) |
| `passive_hints` | `response_style == "passive"` + `passive_hint` preenchido em pelo menos um campo |
| `closing_questions` | `response_style == "passive"` + campo com `allow_closing_question=true` e `closing_question` preenchida |
| `WARMING INJECTION` | `template_key == "hybrid_scheduler"` + pós-qualificação + `appointment_mode == "exploratory"` |
| `COMMERCIAL INJECTION` | `template_key == "hybrid_scheduler"` + pós-qualificação + `appointment_mode == "commercial"` |
| `VARIANT_RULE cart_recovery` | `followup_variant == "cart_recovery"` |
| `VARIANT_RULE hybrid_scheduler` | `followup_variant == "hybrid_scheduler"` |
| `FOLLOWUP_PRIORITY_RULE` (modo tick) | `is_followup_tick == true` |
| `offer_pack_summary` com mídia | `offer_pack_summary.media_url` preenchido |
| `anchor_price` no pitch | `offer_pack_summary.anchor_price` preenchido |
| `guarantee_text` no pitch | `offer_pack_summary.guarantee_text` preenchido |
| Campos comerciais knowledge | `appointment_mode == "commercial"` + campo preenchido em `knowledge_items` |

---

## 6. Referências no código

| Arquivo | Relevância |
|---|---|
| [backend-executors/app/services/decision_engine.py](../backend-executors/app/services/decision_engine.py) | Todos os prompts do funil de vendas WhatsApp (Mãe + 5 Filhas); lê `response_style` e `qualification_fields` |
| [backend-executors/app/services/field_extractor.py](../backend-executors/app/services/field_extractor.py) | Extração estruturada de campos — inclui campos `custom_*` do AI Profile |
| [backend-executors/app/contracts/qualification_contract.py](../backend-executors/app/contracts/qualification_contract.py) | Contrato de qualificação do executor |
| [backend-crm/automations/assistente_ia/llm.py](../backend-crm/automations/assistente_ia/llm.py) | Geração de outreach multicanal (e-mail, WhatsApp, Instagram, ligação) |
| [backend-crm/routes/executor.py](../backend-crm/routes/executor.py) | Monta o `ContextBundle` + injeta `knowledge_items` antes de enviar ao `decision_engine` |
| [backend-crm/services/ai_orchestrator/orchestrator.py](../backend-crm/services/ai_orchestrator/orchestrator.py) | Orquestra o fluxo inbound; constrói `must_collect_with_questions`, `nice_to_collect`, `passive_hints` |
| [backend-crm/services/qualification_guardrails.py](../backend-crm/services/qualification_guardrails.py) | Guardrail do Kanban — chamado apenas em rotas manuais de `routes/leads.py` |
| [backend-core/app/models/ai_profile.py](../backend-core/app/models/ai_profile.py) | Modelo SQLAlchemy — inclui `qualification_fields` (JSON nullable) |
| [backend-core/app/api/ai_profiles.py](../backend-core/app/api/ai_profiles.py) | API de AI Profile; deriva `qualification_required_fields` de `qualification_fields` ao salvar |
| [frontend-crm/src/types/agente.ts](../frontend-crm/src/types/agente.ts) | Tipos TypeScript — interface `QualificationField` e campo `qualification_fields` em `AgentConfig` |
