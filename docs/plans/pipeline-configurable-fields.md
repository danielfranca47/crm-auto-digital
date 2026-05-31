# AI Profile como Fonte de Verdade — Campos Configuráveis

> **Status: PARCIALMENTE IMPLEMENTADO**
> 7 de 9 etapas concluídas. Etapas B, C e I pendentes.
> **Pendências sujeitas a reavaliação** — decidir se ainda são necessárias antes de implementar.

## Princípio geral

O objetivo é migrar hardcodes de comportamento do bot para campos configuráveis no AI Profile. Cada novo campo deve:
1. Ser opcional com fallback sensato (não quebrar quem não preencher)
2. Ser visível na UI do AI Profile de forma contextual ao tipo de agente
3. Ser injetado no prompt do LLM de forma clara
4. Ter default derivado do `template_key` selecionado

---

## Etapas concluídas

### Etapa A — Contexto inbound/outbound no LLM ✅ *(todos os agentes)*

`lead_origin` no `ContextBundle`. Campos `origin_inbound_opener` e `origin_outbound_opener` no AI Profile.
Leads de Prospecção recebem `origin = "outbound"` forçado.

---

### Etapa D — Lembretes de appointment ✅ *(Agent 1, Agent 3)*

Campo `appointment_reminder_offsets: JSON` no AI Profile (lista de inteiros negativos em minutos).
Ao criar appointment, jobs de lembrete são agendados em `appointments.py` para cada offset.

---

### Etapa E — Dossiê/briefing pré-reunião ✅ *(Agent 1, Agent 3)*

Implementado como: `briefing_enabled`, `briefing_channel`, `briefing_lead_time`, `operator_whatsapp` no AI Profile.
Serviço de briefing disponível. Jobs enfileirados via appointments.

---

### Etapa F — Sinais de compra e alerta ao vendedor ✅ *(Agent 1)*

Campo `buying_signal_keywords: JSON` no AI Profile.
Detecção via `_detect_buying_signals()` em `decision_engine.py`.
Alerta enviado para `operator_whatsapp`.

---

### Etapa G — Campos de mídia no offer_pack ✅ *(Agent 2)*

`anchor_price` e `guarantee_text` consumidos pelo `decision_engine.py`.
Quando presentes, o prompt da Filha inclui preço âncora e garantia na mensagem de apresentação.

---

### Etapa H — Integração de pagamento ✅ *(Agent 2)*

Campos `payment_gateway` e `payment_webhook_secret` no AI Profile.
Rota `POST /webhooks/payment/{gateway}` em `backend-crm/routes/webhooks.py`.
Ao confirmar pagamento: lead movido para `"client-list"`, cart recovery interrompido, boas-vindas enfileiradas.

---

### Etapa I — Integração de calendário ⚠️ Stub *(Agent 1, Agent 3)*

Campo `calendar_integration` existe no AI Profile (valor padrão `"none"`).
**Sem integração real implementada** — apenas o campo de configuração. Appointments locais funcionam como fallback.

---

## Etapas pendentes (sujeitas a reavaliação)

> As etapas abaixo foram planejadas mas não implementadas. Avaliar se ainda fazem sentido antes de prosseguir.

### Etapa B — Perguntas de qualificação configuráveis ❌ *(todos os agentes)*

**Objetivo:** substituir perguntas genéricas hardcoded em `ai_playbooks/__init__.py` por perguntas específicas do negócio do usuário.

**O que implementar:**
1. Novo campo `qualification_questions: JSON (nullable)` em `ai_profiles` — lista de strings
2. Playbook passa a ter `qualification_questions: []` (vazio como default)
3. `build_context_bundle` usa `ai_profile.qualification_questions` se preenchido; senão LLM gera baseado em `niche`, `target_audience`, `offer_description`
4. UI: lista dinâmica (add/remove/reorder) na aba "Qualificação" do AI Profile

**Arquivos afetados:**
- `backend-core/app/models/ai_profile.py`
- `backend-crm/services/ai_playbooks/__init__.py`
- `backend-crm/services/ai_orchestrator/orchestrator.py`
- `frontend-crm/src/pages/AiProfile.tsx`

---

### Etapa C — Estratégia de follow-up configurável ❌ *(Agent 2, Agent 3)*

**Agent 2 — Cart recovery:**
Campo novo: `cart_recovery_strategy: JSON (nullable)` — lista de `{tone_rule, instruction}` por tentativa

**Agent 3 — Outcomes pós-sessão:**
Campo novo: `followup_strategy: JSON (nullable)` — dict com chaves `interested_not_closed`, `reschedule_needed`, `converted`

Valores hardcoded em `ai_playbooks/__init__.py` virariam defaults sobrescritíveis pelos campos do AI Profile.

**Arquivos afetados:**
- `backend-core/app/models/ai_profile.py`
- `backend-crm/services/ai_playbooks/__init__.py`
- `backend-executors/app/services/decision_engine.py`
- `frontend-crm/src/pages/AiProfile.tsx`

---

## Tabela de campos no AI Profile

| Campo | Tipo | Status |
|---|---|---|
| `origin_inbound_opener` | String | ✅ Implementado |
| `origin_outbound_opener` | String | ✅ Implementado |
| `qualification_questions` | JSON (list[str]) | ❌ Pendente |
| `appointment_reminder_offsets` | JSON (list[int]) | ✅ Implementado |
| `briefing_enabled` / `briefing_lead_time` / `operator_whatsapp` | Boolean/Int/String | ✅ Implementado |
| `buying_signal_keywords` | JSON (list[str]) | ✅ Implementado |
| `payment_gateway` / `payment_webhook_secret` | String | ✅ Implementado |
| `cart_recovery_strategy` | JSON | ❌ Pendente |
| `followup_strategy` | JSON | ❌ Pendente |
| `calendar_integration` | String | ⚠️ Stub |
