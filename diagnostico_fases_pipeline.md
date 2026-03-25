# Diagnóstico — Fases do Pipeline por Agente

*Gerado em: março 2026 | Branch: feature/etapa-8-n8n-orion*
*Contexto: AgentOS — auditoria pós-implementação Etapa 8*

---

## Princípio arquitetural (leia antes de tudo)

> **O AI Profile é a fonte de verdade de todo comportamento do bot.**
>
> As promessas documentadas por agente (perguntas, tons, cadências, instruções de fase)
> são *exemplos* do que cada tipo de agente costuma precisar — não templates fixos.
> O que o LLM recebe deve vir das configurações que **o próprio usuário definiu** no AI Profile.
>
> Se uma instrução não existe como campo configurável no AI Profile, ou existe mas não chega
> ao prompt do LLM, o sistema está incompleto — independente de funcionar em testes.

**Consequência direta:** os hardcodes em `services/ai_playbooks/__init__.py` e em
`services/ai_orchestrator/orchestrator.py` são muletas temporárias. A meta é migrar
cada um deles para campos JSON/String no `AIProfile` model, expor via API e UI,
e injetá-los dinamicamente no prompt.

---

## Resumo executivo

| Fase | Agent 1 (sdr_scheduler) | Agent 2 (closer_agressivo) | Agent 3 (hybrid_scheduler) |
|------|--------------------------|----------------------------|----------------------------|
| **Qualification** | ⚠️ Parcial | ⚠️ Parcial | ⚠️ Parcial |
| **Presentation** | ⚠️ Parcial | ⚠️ Parcial | ⚠️ Parcial |
| **Closing** | ⚠️ Parcial | ⚠️ Parcial | ⚠️ Parcial |
| **Outbound / Origem** | ❌ Faltando | ❌ Faltando | ❌ Faltando |

**Estado geral:** ~60% implementado | ~30% parcial | ~10% ausente

---

## Mapa de campos: o que chega ao LLM hoje

O prompt construído em `backend-executors/app/services/decision_engine.py:588-683`
injeta os seguintes campos do AI Profile:

| Campo | Chega ao LLM? | Observação |
|-------|:---:|---|
| `brand_name` | ✅ | Sempre |
| `tone_of_voice` | ✅ | Sempre |
| `niche` | ✅ | Sempre |
| `target_audience` | ✅ | Sempre |
| `offer_description` | ✅ | Sempre |
| `goals` | ✅ | Sempre |
| `custom_instructions` | ✅ | Sempre |
| `agent_mode` (normalizado) | ✅ | Normalizado para consultivo/agenda/direto |
| `offer_pack` (resumo) | ✅ | Via `_build_offer_pack_summary()` |
| `identity_mode` | ✅ | Sempre |
| `handoff_policy` | ✅ | Sempre |
| `handoff_custom_text` | ✅ | Sempre |
| `presentation_variant` | ✅ | Resolvido no orchestrator |
| `followup_cadence` | ⚠️ | Usado no followup_state, não chega ao prompt de qualificação/apresentação |
| `followup_allowed_hours` | ⚠️ | Usado na fila de jobs, não no prompt |
| `hybrid_flow_style` | ⚠️ | Definido mas sem execução distinta no decision_engine |
| `qualification_questions` | ❌ | **Não existe** — hardcoded em `ai_playbooks/__init__.py` |
| `inbound_opener` | ❌ | **Não existe** |
| `outbound_opener` | ❌ | **Não existe** |
| `lead_origin` (inbound/outbound) | ❌ | Não propagado do lead até o prompt |
| `closing_keywords` | ❌ | **Não existe** — sem detecção de sinais de compra |
| `cart_recovery_strategy` | ❌ | **Não existe** — hardcoded em `ai_playbooks/__init__.py:39-61` |
| `followup_strategy` | ❌ | **Não existe** — hardcoded em `ai_playbooks/__init__.py:73-92` |
| `response_style` | ❌ | **Não existe** — hardcoded por template_key |
| `max_chars` | ❌ | **Não existe como campo** — hardcoded no orchestrator por agent_mode |
| `appointment_reminder_offsets` | ❌ | **Não existe** |
| `briefing_template` | ❌ | **Não existe** |

---

## Hardcodes identificados que devem migrar para AI Profile

### H1 — Perguntas de qualificação
**Onde:** `backend-crm/services/ai_playbooks/__init__.py:9-30`
```python
"sdr_padrao": {
    "qualification_questions": [
        "Qual é o principal objetivo da sua empresa ao usar nosso produto?",
        "Qual o tamanho da sua equipe atualmente?",
    ],
}
```
**Problema:** Perguntas genéricas sem relação com o negócio do usuário. Um
advogado, uma clínica e uma consultoria precisam de perguntas completamente
diferentes — mas recebem as mesmas.

**Campo novo:** `qualification_questions: JSON (list[string])` no AIProfile

---

### H2 — Overrides de comportamento por modo
**Onde:** `backend-crm/services/ai_orchestrator/orchestrator.py:87-108`
```python
if agent_mode_normalized == "consultivo":
    merged.update({
        "max_chars": 700,
        "qualification_depth": "high",
        "max_questions_per_turn": 1,
        "must_handoff_on_high_intent": True,
    })
elif agent_mode_normalized == "agenda":
    merged.update({ "max_chars": 350, "qualification_depth": "medium", ... })
elif agent_mode_normalized == "direto":
    merged.update({ "max_chars": 300, "qualification_depth": "low", "cta_every_turn": True })
```
**Problema:** Limites e profundidade de qualificação são fixos. Um closer
agressivo que vende serviços de alto ticket pode precisar de respostas mais
longas; um SDR para infoproduto pode precisar de qualificação ainda mais rápida.

**Campo novo:** `behavior_overrides: JSON` no AIProfile
(ex: `{"max_chars": 300, "max_questions_per_turn": 1, "cta_every_turn": false}`)

---

### H3 — Estratégia de cart recovery
**Onde:** `backend-crm/services/ai_playbooks/__init__.py:39-61`
```python
"closer_agressivo_cart_recovery": {
    "attempts": [
        {"tone_rule": "neutral", "instruction": "Lembrete neutro..."},
        {"tone_rule": "benefit_objection", "instruction": "Reforce benefício..."},
        {"tone_rule": "urgency", "instruction": "Urgência máxima..."},
    ]
}
```
**Problema:** As instruções de cada tentativa de cart recovery são fixas.
O usuário não consegue personalizar o que o bot fala em cada tentativa.

**Campo novo:** `cart_recovery_strategy: JSON` no AIProfile
(lista de instruções por tentativa, com `tone_rule` e `instruction` editáveis)

---

### H4 — Estratégia de follow-up pós-sessão (Agent 3)
**Onde:** `backend-crm/services/ai_playbooks/__init__.py:73-92`
```python
"hybrid_scheduler_followup": {
    "followup_outcomes": {
        "interested_not_closed": {"tone_rule": "...", "instruction": "..."},
        "reschedule_needed": {"tone_rule": "...", "instruction": "..."},
        "converted": {"tone_rule": "...", "instruction": "..."},
    }
}
```
**Problema:** O que o bot diz para cada outcome pós-sessão é fixo.
Um coach e um terapeuta têm abordagens radicalmente diferentes para
"interessado mas não fechou".

**Campo novo:** `followup_strategy: JSON` no AIProfile
(por outcome: `interested_not_closed`, `reschedule_needed`, `converted`)

---

### H5 — Abertura por origem do lead (inbound vs outbound)
**Onde:** Inexistente. O campo `origin` de `leads` não é propagado ao prompt.

**Problema:** O bot não sabe se o lead veio te procurar ou foi abordado.
A abertura de uma conversa inbound ("Olá, vi seu anúncio...") e outbound
("Oi, você me indicaram para...") são completamente diferentes.

**Campos novos:** `inbound_opener: String` e `outbound_opener: String` no AIProfile
E correção: `lead.origin` deve ser incluído no ContextBundle e no prompt.

---

### H6 — Keywords de sinal de compra (closing)
**Onde:** Inexistente no código. Não há detecção de sinais de compra.

**Problema:** O bot não sabe quando o lead está pronto para fechar.
Keywords como "quanto custa", "como contrato", "tem garantia" são sinais
críticos, especialmente para Agent 1 (notificar vendedor) e Agent 2 (enviar CTA).

**Campo novo:** `closing_signal_keywords: JSON (list[string])` no AIProfile

---

### H7 — Lembretes de appointment
**Onde:** Inexistente. Appointments têm `start_at` mas nenhum job é
agendado para disparar lembretes.

**Problema:** Sem lembrete, no-show rate será alto — especialmente
para leads outbound que têm menos comprometimento inicial.

**Campo novo:** `appointment_reminder_offsets: JSON` no AIProfile
(ex: `[-1440, -60]` = 24h e 1h antes, em minutos)

---

## Qualification

### O que está implementado (comum a todos os agentes)

- Campos obrigatórios por `agent_mode` — `backend-crm/services/qualification_guardrails.py:8-28`
  - `consultivo`: 6 campos | `agenda`: 4 campos | `direto`: 3 campos ✅
- Bloqueio de avanço: HTTP 409 se campos faltantes — `backend-crm/routes/leads.py:408-430` ✅
- Extração heurística de campos por regex/keywords — `backend-executors/app/contracts/qualification_contract.py:60-113` ✅
- Persistência em `lead_qualification_state` com histórico de perguntas (max 3/campo) ✅
- Evitar repetição de perguntas via SequenceMatcher — `backend-executors/app/services/decision_engine.py` ✅

---

### Agent 1 — sdr_scheduler

#### Gaps e severidade

| Gap | Causa raiz | Severidade |
|-----|-----------|-----------|
| Perguntas de qualificação são genéricas ("qual o tamanho da sua equipe") — sem relação com o nicho do usuário | `qualification_questions` hardcoded no playbook; não existe como campo editável no AI Profile | **Crítico** |
| Lead inbound e outbound recebem a mesma abordagem — bot não adapta abertura ou tom por origem | `lead.origin` não chega ao ContextBundle nem ao prompt | **Crítico** |
| Lógica de "filtro progressivo" (F1 fit → F2 dor → F3 4Ps) não existe — há apenas verificação de campos preenchidos | Não há campo `qualification_flow` no AI Profile para definir sequência de filtros | **Crítico** |
| Score de qualificação (Poder/Prioridade/Preço/Timing) inexistente — avanço binário (preenchido/vazio) | Não há campos de scoring no contrato | **Crítico** |
| Leads descartados na qualificação vão para `"disqualified"` sem distinção de nurture passivo | Sem lógica de `lead_nurture` como categoria ou status separado | **Parcial** |

---

### Agent 2 — closer_agressivo

#### Gaps e severidade

| Gap | Causa raiz | Severidade |
|-----|-----------|-----------|
| Perguntas são genéricas ("quando implementar", "quem decide") — sem relação com o produto do usuário | `qualification_questions` hardcoded; sem campo editável | **Crítico** |
| Não existe lógica de "qualquer sinal positivo → avança ao pitch" — ainda exige 3 campos obrigatórios | Guardrail baseado só em campos, sem pontuação de intento | **Parcial** |
| Sem diferenciação de fluxo inbound (1-2 perguntas) vs outbound (1 pergunta de dor) | `lead.origin` não chega ao prompt | **Crítico** |

---

### Agent 3 — hybrid_scheduler

#### Gaps e severidade

| Gap | Causa raiz | Severidade |
|-----|-----------|-----------|
| `tone_rule: "pessoal e próximo"` existe no playbook mas não como campo editável no AI Profile — se o usuário não colocar nada em `tone_of_voice`, o sistema usa o default hardcoded | `tone_rule` é propriedade do playbook, não do AI Profile | **Parcial** |
| Passo de aquecimento (social proof + preview da sessão) antes de propor agendamento: inexistente | Sem campo `warmup_message` ou `social_proof` no AI Profile | **Crítico** |
| Sem diferenciação de abertura outbound ("como se o profissional estivesse mandando") | `lead.origin` não chega ao prompt; `outbound_opener` não existe | **Crítico** |
| 6 campos obrigatórios do modo `consultivo` raramente são preenchidos sem perguntas diretas | Sem perguntas configuráveis + sem passo de aquecimento cria dead-end na extração heurística | **Crítico** |

---

## Presentation

### O que está implementado (comum a todos os agentes)

- Variantes `"sales"` e `"scheduler"` resolvidas no orchestrator ✅
- `offer_pack` (JSON) injetado no prompt via `_build_offer_pack_summary()` ✅
- Guardrails de reversão por mode (agenda sem horário → volta para qualification) ✅
- `hybrid_flow_style` definido no AI Profile (`offer_then_schedule` / `schedule_then_offer`) ⚠️ (campo existe, execução parcial)

---

### Agent 1 — sdr_scheduler

| Gap | Causa raiz | Severidade |
|-----|-----------|-----------|
| Sem integração com calendário externo (Calendly, Google Calendar) — appointment só no SQLite | Integração inexistente no código | **Crítico** |
| Dossiê pré-reunião (dor, qualificação, histórico) não é gerado nem enviado ao vendedor | Sem lógica de geração de briefing; sem campo `operator_whatsapp` no AI Profile | **Crítico** |
| Lembretes automáticos (24h e 1h antes) não implementados | Sem job de lembrete; `appointment_reminder_offsets` não existe no AI Profile | **Crítico** |
| Confirmação estruturada de agendamento ao lead: sem lógica dedicada | Dependente do LLM mencionar o horário livremente, sem template configurável | **Parcial** |

---

### Agent 2 — closer_agressivo

| Gap | Causa raiz | Severidade |
|-----|-----------|-----------|
| Mídia rica (imagens, vídeo, áudio) não enviável — `offer_pack` sem campos de URL de mídia | `offer_pack.items[]` não tem campos `media_url`/`media_type` | **Crítico** |
| FAQ de objeções: campo `faq` existe no contrato do `offer_pack` mas não há matching estruturado — é injetado como bloco de texto no prompt | Decision engine não tem lógica de "se lead menciona X, responda com FAQ[X]" | **Parcial** |
| Instruções de cart recovery (o que dizer em cada tentativa) são fixas | `cart_recovery_strategy` hardcoded no playbook; não existe como campo editável | **Crítico** |
| `hybrid_flow_style` não se aplica ao Agent 2, mas `handoff_policy` pode forçar handoff indesejado se mal configurado | Sem lock que impeça handoff para `agent_mode = "direto"` + `presentation_variant = "sales"` | **Parcial** |

---

### Agent 3 — hybrid_scheduler

| Gap | Causa raiz | Severidade |
|-----|-----------|-----------|
| Sem integração com Google Calendar / Calendly | Integração inexistente | **Crítico** |
| Confirmação dupla (WhatsApp + e-mail) impossível — sem módulo de e-mail | Sem integração de e-mail | **Crítico** |
| Lembretes 24h e 2h antes não implementados | Sem job de lembrete; `appointment_reminder_offsets` não existe | **Crítico** |
| Briefing ao profissional antes da sessão inexistente | Sem geração de briefing; sem destino configurável | **Crítico** |
| `hybrid_flow_style` não altera execução do decision_engine de forma estruturada — mencionado no ContextBundle mas sem branches claros no prompt | Lógica parcialmente implementada | **Parcial** |

---

## Closing

### O que está implementado (comum a todos os agentes)

- Bot desabilitado ao entrar em closing para agents de agenda (Agent 1, 3) ✅
- Bot permanece ativo para Agent 2 (`presentation_variant = "sales"`) ✅
- Parada de follow-up ao mover para `"client-list"`, `"prospect-refused"`, `"disqualified"` ✅
- Appointments com outcomes (`completed`, `no_show`, `rescheduled`) ✅
- Registro de temperatura pós-reunião via `FollowUpTransitionModal` (Etapa 8) ✅

---

### Agent 1 — sdr_scheduler

| Gap | Causa raiz | Severidade |
|-----|-----------|-----------|
| Detecção de keywords de compra ("quanto custa", "como assino") inexistente | `closing_signal_keywords` não existe no AI Profile; decision engine não tem lógica dedicada | **Crítico** |
| Alerta imediato ao vendedor ao detectar sinal: inexistente | Sem sistema de notificação ao operador | **Crítico** |
| Bot envia link de contrato automaticamente ao detectar sinal: inexistente | Sem trigger por keyword; `offer_pack.checkout_link` existe mas não há disparo automático | **Crítico** |

---

### Agent 2 — closer_agressivo

| Gap | Causa raiz | Severidade |
|-----|-----------|-----------|
| Confirmação automática de pagamento: completamente ausente | Nenhum gateway integrado (Hotmart, Stripe, Kiwify, PagSeguro) | **Crítico** |
| Entrega automática de produto digital: ausente | Nenhuma lógica após pagamento confirmado | **Crítico** |
| Upsell pós-compra: ausente | Inexistente | **Crítico** |
| NPS após 7 dias: ausente | Inexistente | **Crítico** |
| Closing hoje exige ação manual do operador (mover para "client-list") | Sem webhook de pagamento para automatizar | **Crítico** |

---

### Agent 3 — hybrid_scheduler

| Gap | Causa raiz | Severidade |
|-----|-----------|-----------|
| Follow-up de onboarding após "convertido": playbook define o outcome mas sem template editável pelo usuário | `followup_strategy.converted` hardcoded; não editável no AI Profile | **Parcial** |
| Re-oferta automática de horários quando `reschedule_needed` sem integração de calendário real | Sem Calendly/Google Calendar para buscar slots disponíveis | **Parcial** |
| Bot não tenta fechar antes da sessão: correto ✅ | — | — |

---

## Outbound / Origem do lead

### O que está implementado

- Campo `origin` existe na tabela `leads` (string livre) ✅
- Valores possíveis: "Manual", "Planilha", "WhatsApp", nome do agent-local

### Gaps

| Gap | Causa raiz | Severidade |
|-----|-----------|-----------|
| Página de Prospecção não seta `origin = "outbound"` de forma garantida — o campo é parâmetro livre | Sem valor forçado na rota de criação via Prospecção | **Crítico** |
| `lead.origin` não está no ContextBundle — não chega ao decision engine nem ao prompt do LLM | `build_context_bundle_from_inbound()` no orchestrator não inclui `lead.origin` | **Crítico** |
| O bot não adapta abordagem por origem — usa mesma abertura para lead que veio procurar você e para lead que foi abordado | Decorrência do gap acima + ausência de `inbound_opener` / `outbound_opener` no AI Profile | **Crítico** |
| Sem separação visual no Kanban ou em relatórios entre inbound e outbound | Campo existe no banco mas sem filtro ou tag na UI | **Parcial** |

---

## Plano de implementação: AI Profile como fonte de verdade

> **Critério de design:** cada campo novo deve ser:
> 1. Opcional com fallback sensato (não quebrar quem não preencher)
> 2. Visível na UI do AI Profile de forma contextual ao tipo de agente
> 3. Injetado no prompt do LLM de forma clara e sem poluir o contexto
> 4. Com default derivado do `template_key` selecionado — o usuário parte de um bom ponto e customiza

---

### Etapa A — Contexto inbound/outbound no LLM *(bloqueador, todos os agentes)*

**Backend CRM — `services/ai_orchestrator/orchestrator.py`**
1. Adicionar `lead.origin` ao `ContextBundle` (campo `lead_origin: str`)
2. Normalizar: se `origin` contém "outbound" ou veio da página Prospecção → `"outbound"`; demais → `"inbound"`

**Backend CRM — `routes/prospeccao.py` ou `routes/leads.py`**
3. Garantir que criação de lead via Prospecção sete `origin = "outbound"` forçado

**Backend Executors — `services/decision_engine.py`**
4. Injetar no prompt: `"ORIGEM DO LEAD: inbound (veio te procurar) / outbound (foi abordado por você)"`
5. Usar `inbound_opener` / `outbound_opener` do AI Profile como instrução de abertura, se preenchidos

**Backend Core — `models/ai_profile.py`**
6. Novos campos:
   - `inbound_opener: String (nullable)` — instrução de tom/texto para abertura inbound
   - `outbound_opener: String (nullable)` — instrução de tom/texto para abertura outbound

**Frontend — `src/pages/AiProfile.tsx`**
7. Seção "Comportamento por origem do lead" com dois campos de texto (textareas) nas configurações avançadas do agente

---

### Etapa B — Perguntas de qualificação configuráveis *(todos os agentes)*

**Backend Core — `models/ai_profile.py`**
1. Novo campo: `qualification_questions: JSON (nullable)` — lista de strings

**Backend CRM — `services/ai_playbooks/__init__.py`**
2. O playbook de cada template passa a ter `qualification_questions: []` (vazio)
3. `build_context_bundle` sobrescreve com `ai_profile.qualification_questions` se preenchido
4. Se vazio, LLM gera perguntas baseado em `niche`, `target_audience` e `offer_description`

**Frontend — `src/pages/AiProfile.tsx`**
5. Campo de perguntas editáveis na aba "Qualificação": lista dinâmica (add/remove/reorder)
6. Mostrado dinamicamente: Agent 1 sugere 2-3 perguntas, Agent 2 sugere 1-2, Agent 3 sugere 2-3

---

### Etapa C — Estratégia de follow-up configurável *(Agent 2 cart recovery, Agent 3 outcomes)*

**Backend Core — `models/ai_profile.py`**
1. `cart_recovery_strategy: JSON (nullable)` — lista de `{tone_rule, instruction}` por tentativa
2. `followup_strategy: JSON (nullable)` — dict com chaves `interested_not_closed`, `reschedule_needed`, `converted` (cada com `instruction`)

**Backend CRM — `services/ai_playbooks/__init__.py`**
3. Valores hardcoded viram defaults que são sobrescritos pelos campos do AI Profile

**Backend Executors — `services/decision_engine.py`**
4. `_build_followup_prompt()` usa campos do AI Profile; fallback nos defaults do playbook

**Frontend — `src/pages/AiProfile.tsx`**
5. Seção "Estratégia de Follow-up" na aba "Follow-up" (já existente):
   - Agent 2: campos de instrução por tentativa (1, 2, 3) com label descritivo
   - Agent 3: campos de instrução por outcome (fechou, não fechou, reagendou)
6. Esses campos aparecem apenas para o tipo de agente correspondente (condicional por `agent_mode`)

---

### Etapa D — Lembretes de appointment configuráveis *(Agent 1, Agent 3)*

**Backend Core — `models/ai_profile.py`**
1. `appointment_reminder_offsets: JSON (nullable)` — lista de inteiros negativos em minutos
   Ex: `[-1440, -60]` = 24h e 1h antes

**Backend CRM — `services/jobs_service.py`**
2. Novo job type: `whatsapp.appointment.reminder`
3. Ao criar appointment, para cada offset configurado: `schedule_job(run_at = start_at + offset_minutes)`

**Backend Executors**
4. Runner para job `whatsapp.appointment.reminder`: busca appointment, monta mensagem de lembrete via LLM com instrução do AI Profile, enfileira envio

**Frontend — `src/pages/AiProfile.tsx`**
5. Campo "Lembretes de reunião" na aba do agente: input de offsets (ex: "24h antes, 1h antes") com UI amigável (checkboxes ou chips)

---

### Etapa E — Dossiê/briefing pré-reunião *(Agent 1, Agent 3)*

**Backend Core — `models/ai_profile.py`**
1. `briefing_destination: String (nullable)` — número de WhatsApp do vendedor/profissional para receber o dossiê
2. `briefing_offset_minutes: Integer (nullable)` — quantos minutos antes da reunião enviar o dossiê (ex: 60)

**Backend CRM — novo serviço `services/briefing_service.py`**
3. `generate_briefing(lead_id, user_id)` — monta resumo: dor relatada, campos de qualificação, últimas 5 mensagens, canal de origem, score (se implementado)
4. Disparado quando `appointment.status` muda para `"pending"` com `start_at - briefing_offset_minutes <= now`
5. Enfileira job de envio para `briefing_destination`

**Frontend — `src/pages/AiProfile.tsx`**
6. Campo "Enviar dossiê antes da reunião" nas configurações avançadas: toggle + número do WhatsApp + "X minutos antes"

---

### Etapa F — Sinais de compra e alerta ao vendedor *(Agent 1)*

**Backend Core — `models/ai_profile.py`**
1. `closing_signal_keywords: JSON (nullable)` — lista de strings (ex: `["quanto custa", "como assino", "tem contrato"]`)
2. `closing_alert_destination: String (nullable)` — número para alerta (pode ser mesmo do `briefing_destination`)

**Backend Executors — `services/decision_engine.py`**
3. Após processar resposta inbound, verificar se `message_text` contém alguma das `closing_signal_keywords`
4. Se sim: marcar `signals_structured.closing_signal_detected = true` e enfileirar job de alerta

**Backend CRM — `services/jobs_service.py`**
5. Novo job type: `whatsapp.closing.alert` — envia mensagem de alerta ao vendedor com contexto do lead

**Frontend — `src/pages/AiProfile.tsx`**
6. Seção "Sinais de fechamento" (visível apenas para Agent 1): lista editável de keywords + campo de número para alerta

---

### Etapa G — Campos de mídia no offer_pack *(Agent 2)*

**Backend Core — `models/ai_profile.py`** (via `offer_pack` JSON — sem novo campo)
1. Expandir contrato do `offer_pack.items[]` para incluir:
   - `media_url: string (optional)` — URL de imagem, vídeo ou áudio
   - `media_type: "image"|"video"|"audio" (optional)`
   - `anchor_price: string (optional)` — preço de ancoragem ("de R$ 997")
   - `guarantee: string (optional)` — descrição da garantia

**Backend Executors — `services/decision_engine.py`**
2. `_build_offer_pack_summary()` inclui `media_url`, `anchor_price`, `guarantee` no resumo
3. Runner detecta `media_url` no job payload e enfileira envio de mídia antes do texto

**Frontend — `src/pages/AiProfile.tsx`**
4. UI do offer_pack expandida com campos de mídia, preço âncora e garantia por item

---

### Etapa H — Integração de pagamento *(Agent 2)*

> Esta etapa depende de decisão de produto: qual gateway suportar primeiro.

1. Criar rota `POST /webhooks/payment/{gateway}` com validação por token
2. Ao confirmar pagamento: mover lead para `"client-list"`, parar cart recovery, enfileirar mensagem de boas-vindas
3. Campo `payment_webhook_token: String (nullable)` no AI Profile (configurado pelo usuário)
4. UI: seção "Integração de pagamento" na aba de fechamento

---

### Etapa I — Integração de calendário *(Agent 1, Agent 3)*

> Implementar como integrações opcionais; appointments locais continuam funcionando como fallback.

1. Campo `calendar_integration: JSON (nullable)` no AI Profile com `{provider, credentials_token, calendar_id}`
2. Ao criar appointment local, tentar sincronizar com calendário externo (Calendly ou Google Calendar)
3. UI: seção "Calendário" com OAuth ou token

---

## Campos a adicionar no AI Profile — tabela consolidada

| Campo | Tipo | Default | Visível para |
|-------|------|---------|-------------|
| `inbound_opener` | String | null | Todos os agentes |
| `outbound_opener` | String | null | Todos os agentes |
| `qualification_questions` | JSON (list[str]) | [] | Todos os agentes |
| `behavior_overrides` | JSON | null | Avançado — todos |
| `appointment_reminder_offsets` | JSON (list[int]) | null | Agent 1, Agent 3 |
| `briefing_destination` | String | null | Agent 1, Agent 3 |
| `briefing_offset_minutes` | Integer | 60 | Agent 1, Agent 3 |
| `closing_signal_keywords` | JSON (list[str]) | [] | Agent 1 |
| `closing_alert_destination` | String | null | Agent 1 |
| `cart_recovery_strategy` | JSON | null (usa default do playbook) | Agent 2 |
| `followup_strategy` | JSON | null (usa default do playbook) | Agent 3 |
| `payment_webhook_token` | String | null | Agent 2 |
| `calendar_integration` | JSON | null | Agent 1, Agent 3 |

---

## Problemas críticos (lista priorizada)

### P0 — Sem esses itens o produto não funciona como prometido

| # | Problema | Etapa | Agentes |
|---|----------|-------|---------|
| 1 | `lead.origin` não chega ao LLM — bot não diferencia inbound de outbound | A | Todos |
| 2 | Perguntas de qualificação são genéricas e fixas — não refletem o negócio do usuário | B | Todos |
| 3 | Instruções de cart recovery são hardcoded — usuário não consegue personalizar | C | Agent 2 |
| 4 | Lembretes de appointment não existem — no-show rate alto esperado | D | Agent 1, Agent 3 |
| 5 | Dossiê pré-reunião inexistente — vendedor entra na call sem contexto do lead | E | Agent 1, Agent 3 |
| 6 | Integração de pagamento ausente — Agent 2 não confirma fechamento automaticamente | H | Agent 2 |

### P1 — Funcionalidades prometidas ausentes

| # | Problema | Etapa | Agentes |
|---|----------|-------|---------|
| 7 | Detecção de sinais de compra + alerta ao vendedor | F | Agent 1 |
| 8 | Mídia rica no pitch (imagens, vídeo, áudio) | G | Agent 2 |
| 9 | `followup_strategy` (outcomes pós-sessão) não editável pelo usuário | C | Agent 3 |
| 10 | Passo de aquecimento (social proof + preview) antes de propor agendamento | — | Agent 3 |
| 11 | Integração com calendário externo | I | Agent 1, Agent 3 |

### P2 — Parcialmente implementados ou menores

| # | Problema | Impacto |
|---|----------|---------|
| 12 | `hybrid_flow_style` sem execução distinta no decision_engine | Agent 3 não alterna entre "oferta primeiro" vs "agenda primeiro" |
| 13 | Nurture passivo: leads descartados vão para `disqualified` sem diferenciação | Sem canal de reativação futura |
| 14 | Score de qualificação (4Ps) inexistente | Avanço de fase binário, sem critério consultivo |
| 15 | Separação visual inbound/outbound no Kanban | Sem filtro de canal na UI |

---

## Próximos passos sugeridos

**Sprint 1 (Etapa 9A):** Contexto inbound/outbound + `inbound_opener`/`outbound_opener` no AI Profile → Etapas A
**Sprint 2 (Etapa 9B):** Perguntas de qualificação configuráveis → Etapa B
**Sprint 3 (Etapa 9C):** Lembretes de appointment + dossiê pré-reunião → Etapas D e E
**Sprint 4 (Etapa 9D):** Estratégias de follow-up editáveis (cart recovery + outcomes) → Etapa C
**Sprint 5 (Etapa 9E):** Sinais de compra + alertas + campos de mídia no offer_pack → Etapas F e G
**Sprint 6 (Etapa 9F):** Integração de pagamento → Etapa H
**Sprint 7 (Etapa 9G):** Integração de calendário → Etapa I

---

*Arquivos de referência principais:*
- [backend-core/app/models/ai_profile.py](backend-core/app/models/ai_profile.py)
- [backend-crm/services/ai_playbooks/__init__.py](backend-crm/services/ai_playbooks/__init__.py)
- [backend-crm/services/ai_orchestrator/orchestrator.py](backend-crm/services/ai_orchestrator/orchestrator.py)
- [backend-executors/app/services/decision_engine.py](backend-executors/app/services/decision_engine.py)
- [backend-crm/services/qualification_guardrails.py](backend-crm/services/qualification_guardrails.py)
- [backend-crm/routes/leads.py](backend-crm/routes/leads.py)
- [backend-crm/services/lead_category_policy.py](backend-crm/services/lead_category_policy.py)
- [backend-crm/services/followup_state.py](backend-crm/services/followup_state.py)
- [frontend-crm/src/pages/AiProfile.tsx](frontend-crm/src/pages/AiProfile.tsx)
