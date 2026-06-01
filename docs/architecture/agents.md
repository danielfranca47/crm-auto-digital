# Agentes e AI Profiles

## Dois conceitos distintos

O sistema tem dois endpoints chamados "agente" com responsabilidades completamente diferentes:

| Conceito | Endpoint | Serviço | O que representa |
|---|---|---|---|
| **Agente Local** | `GET /api/agents/` | `backend-crm` (porta 8000) | Runner local que processa jobs de envio |
| **AI Profile** | `GET /ai-profiles/me` | `backend-core` (porta 8001) | Comportamento e personalidade do agente de IA |

**Para a tela de configuração do agente, ambos os endpoints são necessários.**

---

## Agentes Locais (Infrastructure Layer)

### Tabela `agents` (SQLite, backend-crm)

| Coluna | Tipo | Descrição |
|---|---|---|
| `id` | TEXT (PK) | UUID do agente |
| `name` | TEXT | Nome amigável |
| `token` | TEXT | Token de autenticação |
| `status` | TEXT | `offline\|online\|disabled` |
| `capabilities` | TEXT (JSON) | Tipos de job suportados |
| `version` | TEXT | Versão informada no registro |
| `last_seen_at` | DATETIME | Heartbeat recente (usado para status online/offline) |
| `revoked_at` | DATETIME | Preenchido quando revogado; token deixa de funcionar |

### Endpoints de ciclo de vida

| Método | Rota | Descrição |
|---|---|---|
| `POST` | `/api/agents/provision` | Gera `(agent_id, agent_token)` vinculado ao usuário |
| `GET` | `/api/agents` | Lista agentes do usuário (sem expor token) |
| `POST` | `/api/agents/register` | Heartbeat: atualiza status, capabilities, `last_seen_at` |
| `GET` | `/api/agents/next-job` | Busca próximo job para o agente (com lease) |
| `POST` | `/api/agents/report` | Reporta conclusão/erro de um job |
| `POST` | `/api/agents/{id}/revoke` | Revoga o agente (`revoked_at`, `status=disabled`) |
| `POST` | `/api/agents/{id}/reprovision` | Gera novo token para o mesmo agente |
| `GET` | `/api/agents/overview` | Lista com contadores (painel admin/usuário) |

### Schema de resposta `GET /api/agents/`

| Campo | Tipo | Descrição |
|---|---|---|
| `agent_id` | string | UUID (alias do campo `id`) |
| `name` | string\|null | Nome amigável |
| `capabilities` | string[]\|null | Lista de job types suportados |
| `status` | string\|null | `"online"`, `"offline"` ou `"disabled"` |
| `last_seen_at` | string (ISO-8601)\|null | Último heartbeat |
| `revoked` | boolean | `true` se `revoked_at != NULL` |
| `online` | boolean | `true` se `last_seen_at >= agora - seconds` |

### Job types canônicos

- `whatsapp.send.local` — envio de WhatsApp via runner local
- `whatsapp.followup.tick` — tick de follow-up agendado
- `maps.search.local` — busca Google Maps
- `maps.enrich.local` — enriquecimento de lead via Maps

Aliases aceitos: `whatsapp_send`, `maps_search_fallback`, `maps_enrich_fallback`

### Fila resiliente

- `scheduled_at` respeitado — jobs futuros não são entregues antes da hora
- Lease/TTL: jobs `in_progress` há mais de 10min são reabertos para `pending`
- Backoff em falha: tentativa 1 → +60s; tentativa 2 → +180s; tentativa 3 → `failed` definitivo
- `report` falha com `409` se job não estiver mais `in_progress` (protege contra report atrasado)

---

## AI Profile (Business Layer)

### Schema do `GET /ai-profiles/me` (backend-core)

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | integer | ID interno |
| `user_id` | integer | ID do dono |
| `template_key` | string | Template base do agente |
| `name` | string | Nome do agente (como se apresenta ao lead) |
| `brand_name` | string | Nome da empresa/marca |
| `tone_of_voice` | string | Tom de comunicação (texto livre) |
| `timezone` | string\|null | Fuso horário (padrão: `"UTC"`) |
| `niche` | string | Nicho de mercado |
| `target_audience` | string | Descrição do público-alvo |
| `offer_description` | string | Descrição completa da oferta |
| `goals` | string | Objetivos do agente |
| `custom_instructions` | string\|null | Instruções injetadas no system prompt |
| `agent_mode` | string (enum) | Forma de vender (padrão: `"sdr_scheduler"`) |
| `presentation_variant` | string\|null | Variante de apresentação |
| `hybrid_flow_style` | string\|null | Estilo do fluxo híbrido |
| `offer_pack` | object\|null | JSON de configuração da oferta |
| `identity_mode` | string (enum) | Modo de identidade (padrão: `"human_agent"`) |
| `handoff_policy` | string (enum) | Política de handoff (padrão: `"keep_active_notify"`) |
| `handoff_custom_text` | string\|null | Mensagem enviada ao lead no handoff |
| `requires_handoff` | boolean | Se o fluxo sempre exige handoff ao final |
| `human_in_loop` | boolean | Se humano deve aprovar mensagens antes do envio |
| `audio_transcription_enabled` | boolean | Se o agente transcreve áudios PTT via Whisper (padrão: `false`) |
| `response_style` | string | `"active"` (pergunta proativamente) ou `"passive"` (infere silenciosamente) |
| `qualification_fields` | list\|null | Campos de qualificação configurados via UI — substitui os defaults hardcoded quando presente. Cada entrada: `{key, label, question, passive_hint, mode, group?, qualify_if?, disqualify_if?}` |
| `sales_flow` | object\|null | Fluxo de Venda — `{enabled, phases: [{id, blocks[]}]}`. Ver [`sales-flow.md`](sales-flow.md) |
| `offer_pack` | object\|null | JSON com configurações de oferta e comportamento de mídia (ver abaixo) |
| `origin_inbound_opener` | string\|null | Instrução de tom/abertura injectada no prompt quando `lead_origin=inbound` (lead veio ter com o operador) |
| `origin_outbound_opener` | string\|null | Instrução de tom/abertura injectada no prompt quando `lead_origin=outbound` (lead foi prospectado) |
| `appointment_reminder_offsets` | list[int]\|null | Offsets em minutos relativos ao início do appointment para enviar lembretes (ex: `[-1440, -60]` = 24h e 1h antes). Default por template se ausente |
| `briefing_enabled` | boolean\|null | Activa dossiê pré-reunião enviado ao operador (padrão: `true`) |
| `briefing_channel` | string\|null | Canal de envio do dossiê (padrão: `"whatsapp"`) |
| `briefing_lead_time` | integer\|null | Minutos de antecedência para enviar o dossiê (padrão: `120`) |
| `operator_whatsapp` | string\|null | Número WhatsApp do operador — destino do dossiê e dos alertas de sinal de compra |
| `buying_signal_keywords` | list[str]\|null | Keywords que detectam intenção de compra no inbound (ex: `["quanto custa", "como assino"]`). Detecção case-insensitive via substring |
| `payment_gateway` | string\|null | Identificador do gateway de pagamento (ex: `"hotmart"`, `"stripe"`) — compõe a URL do webhook |
| `payment_webhook_secret` | string\|null | Token de autenticação do webhook de pagamento |
| `first_reply_delay_min_seconds` | integer\|null | Delay mínimo (s) antes de responder à **primeira** mensagem de um lead (padrão: `0` = sem delay) |
| `first_reply_delay_max_seconds` | integer\|null | Delay máximo (s) antes da primeira resposta; o valor real é sorteado entre min e max (padrão: `0`) |
| `reply_delay_min_seconds` | integer\|null | Delay mínimo (s) antes de respostas a mensagens subsequentes (padrão: `0`) |
| `reply_delay_max_seconds` | integer\|null | Delay máximo (s) para mensagens subsequentes (padrão: `0`) |
| `availability_mode` | string (enum) | Janela de horário de trabalho do agente (padrão: `"24h"`) |
| `followup_sdr_instructions` | string\|null | Instrução de texto livre injectada no prompt de follow-up quando `followup_variant=sdr_scheduler`. Sobrescreve as regras genéricas da variante com contexto específico do negócio |
| `followup_recovery_instructions` | string\|null | Instrução de texto livre para follow-up de cart recovery (`followup_variant=cart_recovery`) |
| `followup_postsession_instructions` | string\|null | Instrução de texto livre para follow-up pós-sessão (`followup_variant=hybrid_scheduler`) |
| `followup_goal_instructions` | object\|null | Dict por `followup_goal` para Agent 1 — ex: `{"advance_closing": "...", "nurture": "..."}`. Chaves opcionais; usa default da variante se ausente |
| `cart_recovery_attempt_instructions` | list[str\|null]\|null | Lista de 3 strings para Agent 2 — uma instrução por tentativa (1, 2, 3). Posição `null` mantém o default |
| `followup_outcome_instructions` | object\|null | Dict por `outcome` para Agent 3 — ex: `{"interested_not_closed": "...", "reschedule_needed": "..."}`. Chaves opcionais; usa default se ausente |

### Enums

**`template_key`**
| Valor | Tipo de agente |
|---|---|
| `"sdr_padrao"` | SDR Padrão (agent_1) |
| `"consultor_especialista"` | Consultor Especialista (agent_1) |
| `"closer_agressivo"` | Closer Agressivo (agent_2) |
| `"hybrid_scheduler"` | Híbrido Agendador (agent_3) |

**`agent_mode`**
| Valor | Campos obrigatórios de qualificação | Normalizado para |
|---|---|---|
| `"sdr_scheduler"` | 4 campos | `"agenda"` |
| `"closer"` | 3 campos | `"direto"` |
| `"consultivo"` | 6 campos | `"consultivo"` |
| `"agenda"` | 4 campos | `"agenda"` |
| `"direto"` | 3 campos | `"direto"` |

**`presentation_variant`**: `"sales"`, `"scheduler"`, `null`

**`hybrid_flow_style`**: `"offer_then_schedule"`, `"schedule_then_offer"`, `null`

**`identity_mode`**: `"human_agent"`, `"virtual_assistant"`, `"user_clone"`

**`handoff_policy`**: `"disable_bot"`, `"keep_active_notify"`, `"ignore"`

**`availability_mode`**: `"24h"` (sem restrição), `"business_hours"` (Seg–Sex 09h–18h no `timezone` do perfil), `"custom"` (grade de dias/horas configurada na UI)

### Campos do `offer_pack` (subobject)

| Campo | Descrição |
|---|---|
| `media_fallback` | Comportamento quando chega mídia inválida ou áudio com toggle OFF: `"ignorar"` (padrão), `"continuar"`, `"pausar"` |
| `media_fallback_msg` | Mensagem enviada ao lead quando `media_fallback = "continuar"` ou `"pausar"` |
| `multi_message_buffer_seconds` | Janela de absorção de mensagens consecutivas em segundos (0 = desligado) |
| `anchor_price` | Preço âncora injectado no pitch de apresentação — ex: `"R$997"` → bot usa "De R$997 por apenas R$X" |
| `guarantee_text` | Garantia injectada na mensagem de apresentação — ex: `"7 dias de garantia"` |

### Atualização parcial

`PUT /ai-profiles/me` aceita atualização parcial (`exclude_unset=True`). Só campos presentes no body são alterados.

---

## Lembretes de Appointment

Quando um appointment é criado, `_schedule_reminder_jobs()` em `appointments.py` cria jobs `whatsapp.appointment.reminder` agendados para cada offset configurado.

- Se `appointment_reminder_offsets` estiver preenchido no AI Profile, usa esses valores
- Caso contrário, usa defaults por `template_key` (Agent 1: `-1440` e `-60` minutos = 24h e 1h antes)
- Jobs com `send_at <= now` são silenciosamente ignorados (appointment já passou)

---

## Dossiê Pré-Reunião (Briefing)

Quando `briefing_enabled ≠ false`, `_schedule_briefing_job()` em `appointments.py` cria um job `whatsapp.appointment.briefing` agendado para `appointment_start_at - briefing_lead_time` minutos.

O job é processado por `briefing_service.py`, que monta e envia para `operator_whatsapp` um dossiê com:
- Dados do lead (nome, empresa, canal, origem)
- Scores de qualificação BANT (poder de decisão, urgência, orçamento, prazo) em formato visual `█░░`
- Últimas 10 mensagens da conversa
- Detalhes do appointment (título, horário)

**Arquivos:** `backend-crm/services/briefing_service.py`, `backend-crm/routes/appointments.py`

---

## Sinais de Compra

Quando `buying_signal_keywords` está configurado no AI Profile, o decision engine verifica cada mensagem inbound contra a lista (substring case-insensitive via `_detect_buying_signals()`).

Ao detectar uma keyword:
- `crm_client.create_buying_signal_notification(lead_id)` notifica o CRM
- `decision_trace.buying_signal_detected = True` para observabilidade

**Arquivo:** `backend-executors/app/services/decision_engine.py`

---

## Webhook de Pagamento

Configura a recepção de eventos de pagamento confirmado de gateways externos.

**URL gerada** (property `payment_webhook_url` em `ai_profile.py`):
```
{CRM_PUBLIC_BASE_URL}/webhooks/payment/{payment_gateway}?token={payment_webhook_secret}
```

**Ao receber evento confirmado** (`POST /webhooks/payment/{gateway}` em `webhooks.py`):
1. Autentica via `payment_webhook_secret` (header `X-Webhook-Secret` ou query `?token=`)
2. Identifica o lead por email ou telefone
3. Move lead para `"client-list"`
4. Para cart recovery activo
5. Enfileira mensagem de boas-vindas

**Arquivo:** `backend-crm/routes/webhooks.py`

---

## Contexto Inbound/Outbound no LLM

O orchestrator calcula `lead_origin` a partir do campo `lead.origin`:
- Origens `"whatsapp"`, `"inbound"`, `"manual"`, `"planilha"` ou vazio → `"inbound"`
- Qualquer outro valor (ex.: `"prospeccao"`) → `"outbound"`

O decision engine selecciona o opener correspondente do AI Profile:
- `lead_origin=outbound` → usa `origin_outbound_opener`
- `lead_origin=inbound` → usa `origin_inbound_opener`

O opener é injectado no início do prompt de cada Filha para calibrar o tom de abertura (ex.: "Este lead foi prospectado — aborda de forma mais consultiva").

**Arquivos:** `backend-crm/services/ai_orchestrator/orchestrator.py`, `backend-executors/app/services/decision_engine.py`

---

## Toggle de Bot por Lead

O flag `bot_disabled` na tabela `leads` (backend-crm) permite desactivar o agente para um lead individual sem afectar os outros.

| Campo | Tipo | Descrição |
|---|---|---|
| `bot_disabled` | `INTEGER` (0/1) | `1` = agente desactivado para este lead |
| `bot_disabled_reason` | `TEXT NULL` | Motivo: `"manual_disable"`, `"category_closing"`, `"media_fallback"` |

**Fontes de desactivação:**
- **Manual:** utilizador clica "Desativar bot" no `LeadCardDialog`; confirma modal com checkbox
- **Automático (closing):** `lead_category_policy.py` desactiva o bot ao entrar em `closing` (apenas para `agent_mode=agenda`)
- **Automático (media_fallback):** quando `media_fallback="pausar"` e chega mensagem de mídia inválida

**Reactivação:** botão "Reativar bot" no alert block do `LeadCardDialog`. Quando `bot_disabled_reason="manual_disable"`, exibe modal de aviso adicional.

**Verificação no guardrail:** `inbound_handler.py` verifica `lead.bot_disabled` antes de qualquer processamento — `bot_disabled=1` resulta em `{"status": "ignored", "reason": "bot_disabled"}` sem criar job.

---

## Fluxo end-to-end do agente local

1. Usuário seleciona leads → `POST /api/prospeccao/whatsapp/enqueue`
2. Backend cria jobs `whatsapp.send.local` na tabela `jobs`
3. Agente Local faz `GET /api/agents/next-job` → recebe job
4. Executa automação via Selenium/Chrome local
5. Reporta resultado em `POST /api/agents/report`
6. Backend atualiza status do job e move lead quando apropriado

---

## Arquivos críticos

| Arquivo | Responsabilidade |
|---|---|
| `backend-crm/routes/agents.py` | Endpoints de ciclo de vida do agente local |
| `backend-crm/services/jobs_service.py` | Fila de jobs (create, claim, complete, fail, backoff) |
| `backend-crm/routes/prospeccao.py` | Enqueue de jobs de prospecção |
| `backend-core/app/models/ai_profile.py` | Model ORM do AI Profile |
| `backend-core/app/api/ai_profiles.py` | Endpoints CRUD do AI Profile |
| `backend-crm/services/agent_type.py` | Mapeamento template_key → agent_type |
