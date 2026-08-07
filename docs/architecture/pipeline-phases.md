# Pipeline de Fases por Tipo de Agente

## Visão geral

O pipeline de vendas tem três fases comuns a todos os agentes: **Qualification → Presentation → Closing**. Para os templates de agendamento (`sdr_padrao`, `hybrid_scheduler` — `_SCHEDULING_AGENT_TEMPLATES`), existem duas fases intermédias entre Presentation e Closing: **Pré-agendamento → Agendamento** (e "Closing" fica desactivado por design — ver secção própria abaixo). A transição entre fases é controlada por guardrails no `backend-executors` e persistida via `backend-crm`. O comportamento do LLM em cada fase vem de uma "LLM Filha" especializada.

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
| `lead_origin` (computado) | ✅ | Calculado no orchestrator a partir de `lead.origin`; `"inbound"` ou `"outbound"` |
| `origin_inbound_opener` / `origin_outbound_opener` | ✅ | Injectado no início do prompt das Filhas consoante `lead_origin` |

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
- Cobertura: completa. No início de `decide()`, quando `mother_decision.route_to=="qualification"` (e não é um tick de follow-up), verifica se a categoria actual do lead já é uma fase posterior (`apresentation`/`pre-agendamento`/`agendamento`/`follow-up`/`closing`) ou se não há `missing_fields` — nesse caso força `route_for_child="apresentation"` independentemente do que a Mãe decidiu (`decision_trace.anti_loop_rule3_applied=True`, log `event=qualification_anti_loop_rule3`).
- Este mecanismo **não usa palavras-chave/texto livre** — decide só por estado (categoria actual + missing_fields). Um override por palavras-chave em português que partilhava este mesmo bloco condicional (sobrescrevia para `pre-agendamento`/`agendamento` quando o texto batia com uma lista de termos de agendamento) foi removido por ser frágil e acoplado a nicho/idioma — a homologação de categoria (abaixo) já cobre o mesmo caso de forma estrutural.

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

### Estágio de aquecimento e `appointment_mode` (só `hybrid_scheduler`)

Restrito a `template_key="hybrid_scheduler"`. Controlado pelo campo `appointment_mode`
do AI Profile (coluna de topo — ver [`agents.md`](agents.md)):

- **`"exploratory"`** (padrão): sessão sem compromisso de compra — aquece e propõe
  a sessão directamente.
- **`"commercial"`**: injeta um bloco "MODO COMERCIAL" no prompt — prova social,
  TABELA DE SERVIÇOS/PREÇOS (`knowledge_items["service_pricing_table"]`, pode haver
  mais de uma tabela — ver [`knowledge-base.md`](knowledge-base.md)), objeções,
  diferenciais, condição especial e política de pagamento (sempre presencial — nunca
  link de checkout). Objectivo: obter o compromisso verbal com um serviço/pacote
  específico antes de propor o agendamento.

**Gate de disparo (`_auto_promoted_from_qual`):** o bloco de aquecimento (comercial
ou exploratório) só é injectado no turno em que a qualificação é dada como concluída
e a apresentação é alcançada — não em todos os turnos de apresentation. Dispara
quando `missing_fields` está vazio **e** `mother_decision.route_to` é um dos dois
caminhos que levam a essa transição:
1. `"qualification"` — caminho directo: a Mãe roteou para qualification, mas já não
   há campos em falta (Regra 3 anti-loop promove para apresentation).

Quando a 1ª mensagem do lead já chega completa (nome + interesse + pedido de serviço),
`_enforce_greeting_first()` força `route_to="recepcao"` nesse turno (saudação é sempre
obrigatória no 1º contacto) — a Filha Recepção só cumprimenta e extrai o pedido pendente,
que é reencaminhado como um novo turno (ver "Saudação composta" em
[`llm-architecture.md`](llm-architecture.md)). O bloco de aquecimento não dispara no turno
da saudação; dispara no turno seguinte (o pedido reencaminhado), pelo caminho 1 acima, se
essa mensagem já trouxer campos suficientes para a Mãe rotear `"qualification"` com
`missing_fields` vazio.

Fora desses dois caminhos (ex.: lead já está em apresentation há vários turnos e a
Mãe devolve `route_to="apresentation"` directamente), o bloco de aquecimento não é
reinjectado — é um aquecimento de transição única, não recorrente.

**Conhecimento comercial sob demanda fora do turno único:** a sequência proativa
de aquecimento (prova social + apresentação completa da tabela) não repete, mas
o conteúdo das mesmas 6 categorias comerciais (`service_pricing_table`,
`commercial_objections`, `service_differentials`, `active_promotion`,
`payment_policy`, `pre_commitment_faq`) continua disponível à Filha em qualquer
turno de apresentation — mesmo padrão "usar APENAS se pedido explicitamente
neste turno" já aplicado a `objections_faq`/`service_faq` no mesmo bloco
(`_build_child_prompt_apresentation`, dentro de `if not commercial_injection:`).
Assim, se o lead perguntar o preço de novo dois ou três turnos depois do
aquecimento, a Filha ainda tem acesso ao valor real — só não o repete
proativamente sem ser perguntada.

---

## Pré-agendamento e Agendamento (só `_SCHEDULING_AGENT_TEMPLATES`)

Fases intermédias entre Presentation e Closing, usadas só por `sdr_padrao` e `hybrid_scheduler`. Não existem para outros templates — um lead fora destes templates nunca tem `category` nestes valores.

### Pré-agendamento

- Prompt: `_build_child_prompt_pre_agendamento` em `decision_engine.py`
- Distingue intenção **tentativa** ("vou ver", "semana que vem" → fica em pré-agendamento, negocia) de intenção **firme** (dia+hora específicos)
- **Homologação automática para Agendamento:** quando a mensagem do lead já tem dia+hora específicos, a filha devolve `recommended_next_category="agendamento"`. `compose_decision_output()` lê esse campo e avança a categoria do lead directamente para `agendamento` no mesmo turno — sem isto, a filha tratava um pedido com horário já definido como interesse tentativo sem data (resposta sem sentido tipo "posso mandar mensagem amanhã para confirmar?").

### Agendamento

- Prompt: `_build_child_prompt_agendamento` em `decision_engine.py`
- Confirma o horário pedido contra `calendar_busy_slots` (conflitos reais) e a disponibilidade configurada no AI Profile
- Devolve `signals_structured.meeting_datetime_candidate` (data/hora exacta da reunião, ISO) — `meeting_scheduler.py` usa este campo como fonte primária (`event=meeting_datetime_source source=structured_candidate`); só cai no fallback heurístico de extracção por texto (`extract_start_at`, que usa o instante de execução como base e é impreciso) quando o candidato estruturado está ausente ou inválido (`event=meeting_datetime_candidate_invalid`)
- **Homologação directa:** quando `effective_route_to=="agendamento"`, `compose_decision_output()` força `suggested_category="agendamento"` directamente — ignora o clamp de salto único de `apply_mother_category_guardrails()` (que bloquearia, por exemplo, um salto de `apresentation` para `agendamento` sem passar por `pre-agendamento`). Sem isto, a categoria do lead ficava presa na fase anterior mesmo depois de uma confirmação real, e o gate `is_phase_entry` (ver [`llm-architecture.md`](llm-architecture.md)) nunca via a categoria alcançar `agendamento` — bloqueando a criação do appointment indefinidamente.
- **Estilo de oferta de horário (`scheduling_offer_style` no AI Profile — ver [`agents.md`](agents.md)):** controla a instrução de oferta de horário no prompt desta filha. Default `"offer_alternatives"` sempre propõe 2-3 horários concretos, mesmo quando o horário pedido pelo lead está livre (tática comercial deliberada de escassez). `"confirm_exact"` substitui essa instrução por uma regra de confirmação directa: se o horário pedido não constar em `calendar_busy_slots`, confirma sem oferecer alternativas — só propõe alternativas quando há conflito real ou o lead não especificou horário. Quando a agenda está completamente livre, o bloco `calendar_busy_slots` declara isso explicitamente em vez de ficar omitido do prompt — ver "Agenda vazia" em [`agenda.md`](agenda.md#calendar_busy_slots--a-ia-consulta-disponibilidade-real-antes-de-proporconfirmar-horário). Configurável na UI em "Camada de Apresentação" → secção "Disponibilidade de horários".

### Resolução de datas relativas e nomes de dia da semana

Ambas as filhas acima (e a de Presentation) recebem `tabela_de_dias`: uma lista pronta com hoje + os próximos 14 dias, cada um já com a data e o nome do dia da semana calculados (`_calendar_lookup_table_pt()` em `decision_engine.py`). A instrução é "procure a linha correspondente — nunca calcule a data ou o dia da semana por conta própria". Dar só a data de hoje não bastou em teste real (a LLM ainda errava a contagem de dias para nomes de dia da semana, ex.: confirmava "quinta-feira" numa terça-feira real) — eliminar a aritmética do lado da LLM, trocando por uma busca em tabela, resolveu de forma confiável. Limite: cobre até 14 dias à frente; referências mais distantes ("mês que vem") caem de volta no fallback heurístico.

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

### Agentes de agendamento (`sdr_padrao`, `hybrid_scheduler`) — "Closing" desativado por design

`_SCHEDULING_AGENT_TEMPLATES = {"sdr_padrao", "hybrid_scheduler"}` em `decision_engine.py`
agendam sessões/reuniões sem etapa comercial de fechamento — confirmar um
horário não é uma venda fechada. Nota: `sdr_padrao` partilha o agente lógico
`agent_1` com `consultor_especialista` na tabela acima, mas esta regra aplica-se
só a `sdr_padrao` (não a `consultor_especialista`, que não tem fases de
pré-agendamento/agendamento).

`_enforce_scheduling_agent_no_closing()` intercepta a decisão da Mãe antes de
`route_for_child`/`_is_sdr_escalate_closing()`: sempre que `route_to`/
`perceived_category` seria `"closing"` para um destes templates, redireciona
para a categoria atual (se já em `agendamento`/`pre-agendamento`) ou
`apresentation`. Reativar "closing" para negociação de pacotes/recorrência em
follow-up é melhoria futura, ainda não implementada.

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
| `backend-executors/app/services/meeting_scheduler.py` | Criação de appointment a partir de `meeting_scheduled`; gate `is_phase_entry` (M3) |
