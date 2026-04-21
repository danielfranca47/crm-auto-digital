# AI Profile como Fonte de Verdade — Campos Configuráveis

## Contexto

O objetivo é migrar hardcodes de comportamento do bot (perguntas de qualificação, estratégias de follow-up, limites de chars, etc.) para campos configuráveis no AI Profile. Cada novo campo deve:
1. Ser opcional com fallback sensato (não quebrar quem não preencher)
2. Ser visível na UI do AI Profile de forma contextual ao tipo de agente
3. Ser injetado no prompt do LLM de forma clara
4. Ter default derivado do `template_key` selecionado

---

## Etapa A — Contexto inbound/outbound no LLM *(bloqueador, todos os agentes)*

**Problema:** `lead.origin` não chega ao ContextBundle — bot não diferencia lead que veio te procurar de lead que foi abordado.

**O que implementar:**
1. Adicionar `lead.origin` ao `ContextBundle` (`lead_origin: str`)
2. Normalizar: Prospecção → `"outbound"`; demais → `"inbound"`
3. Garantir que criação de lead via Prospecção sete `origin = "outbound"` forçado
4. Injetar no prompt: `"ORIGEM DO LEAD: inbound / outbound"`
5. Usar `inbound_opener` / `outbound_opener` do AI Profile se preenchidos

**Campos novos no `ai_profiles`:**
- `inbound_opener: String (nullable)` — instrução de tom/abertura para lead inbound
- `outbound_opener: String (nullable)` — instrução de tom/abertura para lead outbound

---

## Etapa B — Perguntas de qualificação configuráveis *(todos os agentes)*

**Problema:** perguntas são genéricas e hardcoded em `ai_playbooks/__init__.py`, sem relação com o negócio do usuário.

**O que implementar:**
1. Novo campo `qualification_questions: JSON (nullable)` em `ai_profiles` — lista de strings
2. Playbook passa a ter `qualification_questions: []` (vazio)
3. `build_context_bundle` usa `ai_profile.qualification_questions` se preenchido; senão LLM gera baseado em `niche`, `target_audience`, `offer_description`
4. UI: lista dinâmica (add/remove/reorder) na aba "Qualificação" do AI Profile

---

## Etapa C — Estratégia de follow-up configurável *(Agent 2, Agent 3)*

**Agent 2 — Cart recovery:**
Campo novo: `cart_recovery_strategy: JSON (nullable)` — lista de `{tone_rule, instruction}` por tentativa

**Agent 3 — Outcomes pós-sessão:**
Campo novo: `followup_strategy: JSON (nullable)` — dict com chaves `interested_not_closed`, `reschedule_needed`, `converted`

Valores hardcoded em `ai_playbooks/__init__.py` viram defaults que são sobrescritos pelos campos do AI Profile.

---

## Etapa D — Lembretes de appointment *(Agent 1, Agent 3)*

**Problema:** appointments têm `start_at` mas nenhum job é agendado para disparar lembretes.

**O que implementar:**
1. Campo `appointment_reminder_offsets: JSON (nullable)` em `ai_profiles` — lista de inteiros negativos em minutos (ex: `[-1440, -60]` = 24h e 1h antes)
2. Novo job type: `whatsapp.appointment.reminder`
3. Ao criar appointment, para cada offset: `schedule_job(run_at = start_at + offset_minutes)`
4. Runner no backend-executors: busca appointment, monta mensagem de lembrete, enfileira envio

---

## Etapa E — Dossiê/briefing pré-reunião *(Agent 1, Agent 3)*

**Problema:** vendedor entra na reunião sem contexto do lead.

**O que implementar:**
1. `briefing_destination: String (nullable)` — número de WhatsApp do vendedor
2. `briefing_offset_minutes: Integer (nullable)` — minutos antes da reunião para enviar (ex: 60)
3. Serviço `services/briefing_service.py`: monta resumo (dor, qualificação, últimas 5 mensagens, canal, score)
4. Job enfileirado quando appointment.status muda para `"pending"` dentro da janela de tempo

---

## Etapa F — Sinais de compra e alerta ao vendedor *(Agent 1)*

**Problema:** bot não detecta quando lead está pronto para fechar.

**O que implementar:**
1. `closing_signal_keywords: JSON (nullable)` — lista de keywords (ex: `["quanto custa", "como assino"]`)
2. `closing_alert_destination: String (nullable)` — número para alerta
3. Após processar inbound: verificar keywords no `message_text`
4. Se detectado: `signals_structured.closing_signal_detected = true` + job de alerta `whatsapp.closing.alert`

---

## Etapa G — Campos de mídia no offer_pack *(Agent 2)*

**Expandir contrato de `offer_pack.items[]`:**
- `media_url: string (optional)` — URL de imagem, vídeo ou áudio
- `media_type: "image"|"video"|"audio" (optional)`
- `anchor_price: string (optional)` — preço de ancoragem ("de R$ 997")
- `guarantee: string (optional)` — descrição da garantia

Backend-executors: runner detecta `media_url` e enfileira envio de mídia antes do texto.

---

## Etapa H — Integração de pagamento *(Agent 2)*

> Depende de decisão de produto: qual gateway suportar primeiro.

1. Rota `POST /webhooks/payment/{gateway}` com validação por token
2. Ao confirmar pagamento: mover lead para `"client-list"`, parar cart recovery, enfileirar boas-vindas
3. Campo `payment_webhook_token: String (nullable)` no AI Profile

---

## Etapa I — Integração de calendário *(Agent 1, Agent 3)*

> Appointments locais continuam funcionando como fallback.

1. Campo `calendar_integration: JSON (nullable)` — `{provider, credentials_token, calendar_id}`
2. Ao criar appointment local, tentar sincronizar (Calendly ou Google Calendar)
3. UI: seção "Calendário" com OAuth ou token

---

## Tabela consolidada de campos a adicionar

| Campo | Tipo | Agentes |
|---|---|---|
| `inbound_opener` | String | Todos |
| `outbound_opener` | String | Todos |
| `qualification_questions` | JSON (list[str]) | Todos |
| `behavior_overrides` | JSON | Avançado |
| `appointment_reminder_offsets` | JSON (list[int]) | Agent 1, Agent 3 |
| `briefing_destination` | String | Agent 1, Agent 3 |
| `briefing_offset_minutes` | Integer | Agent 1, Agent 3 |
| `closing_signal_keywords` | JSON (list[str]) | Agent 1 |
| `closing_alert_destination` | String | Agent 1 |
| `cart_recovery_strategy` | JSON | Agent 2 |
| `followup_strategy` | JSON | Agent 3 |
| `payment_webhook_token` | String | Agent 2 |
| `calendar_integration` | JSON | Agent 1, Agent 3 |

---

## Arquivos afetados

| Arquivo | O que mudar |
|---|---|
| `backend-core/app/models/ai_profile.py` | Adicionar novos campos |
| `backend-crm/services/ai_playbooks/__init__.py` | Migrar hardcodes para defaults sobrescritíveis |
| `backend-crm/services/ai_orchestrator/orchestrator.py` | Incluir `lead.origin` no ContextBundle |
| `backend-executors/app/services/decision_engine.py` | Usar campos do AI Profile nos prompts |
| `frontend-crm/src/pages/AiProfile.tsx` | Expor novos campos na UI |
