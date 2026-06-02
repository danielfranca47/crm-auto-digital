# Mapa do Sistema — Arquitectura Geral

Visão global de todos os componentes, seus arquivos responsáveis e como se interligam.
Leia este arquivo antes de trabalhar em qualquer área desconhecida do sistema,
ou quando precisar perceber onde uma mudança vai ter impacto.

Para saber qual **doc de arquitectura** ler por área específica, ver [`_overview.md`](_overview.md).

---

## Serviços e portas

```
backend-core        :8001  ← fonte de verdade de auth, users, AI Profile, WhatsApp connections
backend-crm         :8000  ← lógica de CRM, leads, pipeline de IA, webhooks, jobs
backend-executors   :8002  ← worker assíncrono: consome jobs, chama LLM, envia WhatsApp
frontend-crm        :5173  ← SPA principal do CRM (React + Vite)
frontend-admin      :5174  ← painel SaaS admin isolado (React + Vite)
website             :5175  ← site de marketing multi-idioma (React + Vite)
agent-local         local  ← agente Python local de prospecção/scraping
```

---

## backend-core

**Banco:** `backend-core/core.db` (SQLite via SQLAlchemy ORM)
**Responsabilidade:** autenticação, planos, AI Profile, conexões WhatsApp

### Arquivos críticos

| Arquivo | Responsabilidade |
|---|---|
| `app/main.py` | Startup, inclusão de routers, seed inicial |
| `app/db.py` | `ensure_column()`, migrations, `seed_initial_data()` |
| `app/models/user.py` | Model ORM User |
| `app/models/ai_profile.py` | Model ORM AI Profile (inclui `sales_flow`, `audio_transcription_enabled`) |
| `app/models/whatsapp_connection.py` | Model ORM WhatsApp connection/instance |
| `app/api/auth.py` | Login, JWT, `/users/me`, forgot/reset/change-password |
| `app/models/password_reset_token.py` | Tokens de reset de senha (TTL 2h) |
| `app/services/email_service.py` | Envio SMTP via Resend; templates welcome + reset |
| `app/api/ai_profiles.py` | CRUD `/ai-profiles/me` |
| `app/api/whatsapp_connections.py` | Conexão QR, `/resolve-token`, `/resolve-by-user` |
| `app/api/whatsapp_send.py` | Endpoint `/whatsapp/send` (despacha para UazAPI) |
| `app/api/plans.py` | Planos e assinaturas |
| `app/api/admin.py` | Endpoints admin (`/admin/*`) |
| `app/providers/uazapi_client.py` | Cliente HTTP da UazAPI (`send_text`, `send_media`, `qr_code`) |

### Integrações externas

- **UazAPI** — broker WhatsApp Web; endpoints `/send/text`, `/send/media`, `/message/download`, `/qr`
- **Resend** — SMTP relay para email transacional; domínio verificado `danielfranca.pt`; `SMTP_USER=resend`, `SMTP_PASS=<api_key>`
- **Kiwify** — plataforma de pagamentos; webhook `POST /webhooks/kiwify` activa subscriptions; HMAC-SHA1 via `?signature=`

---

## backend-crm

**Banco:** `backend-crm/database/crm.db` (SQLite raw via `sqlite3`, sem ORM)
**Responsabilidade:** toda a lógica de CRM, pipeline de IA, inbound WhatsApp, jobs

### Arquivos críticos — Rotas

| Arquivo | Rota(s) | Responsabilidade |
|---|---|---|
| `routes/webhooks.py` | `POST /webhooks/whatsapp/uazapi` | Recebe eventos UazAPI; normaliza messageType; filtra grupos |
| `routes/leads.py` | `/api/leads/*` | CRUD de leads, movimentação Kanban, qualification-fields |
| `routes/executor.py` | `/internal/jobs/*` | Endpoint de conclusão de jobs; `_dispatch_system_actions()` |
| `routes/playground.py` | `/api/playground/*` | Simulação de conversa; upload de áudio |
| `routes/agents.py` | `/api/agents/*` | Ciclo de vida dos agentes locais |
| `routes/appointments.py` | `/api/appointments/*` | Agenda e compromissos |
| `routes/knowledge.py` | `/api/knowledge/*` | Base de conhecimento; upload de mídia para Fluxo de Venda |
| `routes/usage.py` | `/api/usage/*` | Consumo do plano |
| `routes/whatsapp_connect.py` | `/api/whatsapp/*` | Conexão QR (proxy para backend-core) |

### Arquivos críticos — Serviços

| Arquivo | Responsabilidade |
|---|---|
| `services/whatsapp_inbound/inbound_handler.py` | Orquestra inbound: normalização de tipo, áudio, media_fallback, buffer, enfileiramento |
| `services/whatsapp_inbound/guardrail.py` | Decide se o sistema processa a mensagem (bot_disabled, categoria, etc.) |
| `services/ai_orchestrator/orchestrator.py` | Monta e enriquece `ContextBundle`; `enrich_context_bundle()` |
| `services/ai_playbooks/__init__.py` | Playbooks por template_key; perguntas de qualificação hardcoded |
| `services/audio_transcription.py` | Transcrição via OpenAI Whisper (`transcribe_audio_from_url`, `transcribe_audio_from_path`) |
| `services/qualification_state.py` | Extrai e persiste campos de qualificação do lead |
| `services/qualification_guardrails.py` | Bloqueia avanço se qualificação incompleta (campos mínimos por agent_mode) |
| `services/followup_state.py` | Máquina de estado de follow-up; agenda próximo envio |
| `services/followup_reconciler.py` | Reconcilia follow-ups pendentes; circuit breaker (24h cooldown) |
| `services/lead_category_policy.py` | Side-effects de mudança de categoria (ex.: closing → desactiva bot) |
| `services/jobs_service.py` | Fila de jobs: create, claim (lease), complete, fail, backoff |
| `services/agent_type.py` | Resolve tipo de agente (`agent_1`, `agent_3`) do lead |
| `core_client.py` | Chamadas server-to-server ao backend-core: AI Profile, token WhatsApp, envio directo |
| `database.py` | `get_connection()`, `ensure_column()`, `init_db()` — schema SQLite |
| `security_core.py` | `require_crm_access()` — valida JWT via backend-core |

### Tipos de job (tabela `jobs`)

| Tipo | Processado por | Descrição |
|---|---|---|
| `whatsapp.inbound.n8n` | backend-executors | Job de mensagem inbound — LLM decide e envia resposta |
| `whatsapp.send.local` | agent-local | Envio via agente local (Selenium) |
| `whatsapp.followup.tick` | backend-executors | Tick de follow-up agendado |
| `maps.search.local` | agent-local | Busca Google Maps |
| `maps.enrich.local` | agent-local | Enriquecimento de lead via Maps |

---

## backend-executors

**Responsabilidade:** worker assíncrono que consome jobs `whatsapp.inbound.n8n`,
chama o LLM (Mãe + Filha) e envia a resposta ao WhatsApp.

### Arquivos críticos

| Arquivo | Responsabilidade |
|---|---|
| `app/workers/whatsapp_worker.py` | Loop de polling; consome jobs; chama runner |
| `app/runners/whatsapp.py` | Executa um job: contexto → decide → envia; `_send_sales_flow_action()` |
| `app/services/decision_engine.py` | Motor de decisão: `decide()`, `_build_mother_prompt()`, `_evaluate_sales_flow_phases()`, todas as LLMs Filhas |
| `app/services/orchestrator_models.py` | Schemas Pydantic: `MotherDecision`, `ChildResult`, `DecisionOutput` |
| `app/services/llm_service.py` | Chamada HTTP ao LLM (Claude/OpenAI format) |
| `app/services/fast_path.py` | Decisões sem LLM (handoff imediato, bot desabilitado) |
| `app/services/handoff_policy.py` | Política de handoff humano |
| `app/services/meeting_scheduler.py` | Agendamento de reuniões pós-decisão |
| `app/clients/core_client.py` | Chamadas ao backend-core: contexto de execução, envio de mensagem, fallback de instância |
| `app/clients/crm_client.py` | Chamadas ao backend-crm: completar/falhar job, reportar resultado |
| `app/contracts/qualification_contract.py` | Extracção de campos de qualificação por regex/heurística |
| `app/schemas/decision.py` | Schema `DecisionOutput` (campos de saída do executor) |

### Fluxo de execução

```
whatsapp_worker (polling)
  → GET /internal/jobs/next (backend-crm)
  → GET /whatsapp/execution-context?job_id=N (backend-crm)
      ← ContextBundle (ai_profile, lead, history, qualification_state, ...)
  → decision_engine.decide(context)
      → LLM Mãe → MotherDecision (route_to, detected_intents, ...)
      → _evaluate_sales_flow_phases() → system_actions, prompt_injections
      → LLM Filha(route_to) → ChildResult (message_text, ...)
      → compose_decision_output() → DecisionOutput
  → send_whatsapp_message() via backend-core → UazAPI
  → POST /internal/jobs/{id}/complete (backend-crm) com result_payload
```

---

## frontend-crm

**Stack:** React 18 + TypeScript + Vite + TailwindCSS + shadcn/ui + Radix UI
**Porta dev:** 5173

### Arquivos críticos

| Arquivo | Responsabilidade |
|---|---|
| `src/pages/Index.tsx` | KanbanBoard principal (pipeline de leads) |
| `src/pages/Dashboard.tsx` | Métricas e agenda do dia |
| `src/pages/AiProfile.tsx` | Configuração completa do agente (todas as camadas) |
| `src/pages/Playground.tsx` | Simulação de conversa; coordena upload de áudio + chat |
| `src/pages/AssistenteIA.tsx` | Chat com IA assistente |
| `src/pages/Prospeccao.tsx` | Prospecção de leads |
| `src/contexts/LeadsContext.tsx` | Estado global do Kanban; `moveLead` com revert optimista |
| `src/services/api.ts` | Cliente HTTP centralizado para backend-crm e backend-core |
| `src/components/KanbanBoard.tsx` | Pipeline visual de leads |
| `src/components/LeadCardDialog.tsx` | Modal completo do lead (qualificação, bot toggle, etc.) |
| `src/components/agente/CamadaFluxoVenda.tsx` | Builder visual da Camada 7 (blocos, triggers, RuleBuilderModal) |
| `src/components/agente/CamadaPipeline.tsx` | Configuração de pipeline: buffer, delays, agent_mode |
| `src/components/playground/PlaygroundChat.tsx` | Input do playground: texto, áudio, modo lote |
| `src/components/playground/MessageBubble.tsx` | Bolha de mensagem (texto, áudio com player, auto_items) |
| `src/types/agente.ts` | Tipos: `SalesFlowBlock`, `SalesFlowPhaseId`, `AiProfile`, etc. |

---

## frontend-admin

**Porta dev:** 5174
**Responsabilidade:** painel SaaS admin isolado — gestão de utilizadores, instâncias, agentes

### Arquivos críticos

| Arquivo | Responsabilidade |
|---|---|
| `src/pages/AdminLogin.tsx` | Login admin independente |
| `src/pages/AdminDashboard.tsx` | KPIs globais e instâncias offline |
| `src/pages/AdminUsers.tsx` | Listagem e gestão de extensões de utilizadores |
| `src/pages/AdminInstances.tsx` | Reconexão de instâncias WhatsApp |
| `src/pages/AdminAgents.tsx` | Agentes, playbooks e diff de AI Profile por utilizador |
| `src/lib/admin-token.ts` | persist/read/clear/validate JWT admin |
| `src/services/api.ts` | Cliente admin-only (core + crm) sem LeadsContext |
| `src/components/AdminGuard.tsx` | Guard de autenticação via `<Navigate>` |

---

## website

**Stack:** React + TypeScript + Vite + i18next
**Idiomas:** `en`, `pt`, `es` (prefixo de rota)
Site de marketing; deploy independente.

---

## agent-local

**Stack:** Python standalone com `.venv` próprio
**Responsabilidade:** agente de prospecção local (scraping Google Maps, envio WhatsApp via Selenium)
**Config:** `.env`, `.env.agent1`, `.env.agent2`

Consome jobs `whatsapp.send.local` e `maps.*.local` via `GET /api/agents/next-job`.

---

## Fluxo de dados principal (inbound WhatsApp)

```
Lead envia mensagem no WhatsApp
  │
  ▼
UazAPI → POST /webhooks/whatsapp/uazapi (backend-crm)
  → routes/webhooks.py: normaliza messageType, filtra grupo
  → inbound_handler.py: bot_disabled? audio? media_fallback? buffer?
  → guardrail.py: deve processar?
  → orchestrator.py: monta ContextBundle
  → jobs_service.py: cria job whatsapp.inbound.n8n (scheduled_at = now + buffer)
                                │
  ┌─────────────────────────────┘
  │
  ▼
backend-executors (worker polling)
  → decision_engine.decide(context)
      → LLM Mãe (routing + detected_intents)
      → _evaluate_sales_flow_phases() (triggers, system_actions)
      → LLM Filha(route_to) (message_text, category suggestion)
  → send via backend-core → UazAPI → WhatsApp
  → POST /internal/jobs/{id}/complete → executor.py persiste
      → apply_suggested_category() → move lead no Kanban
      → _dispatch_system_actions() → mark_phase_triggered, triggers_fired, etc.
```

---

## Fluxo de dados principal (playground)

```
Operador escreve mensagem no Playground (frontend-crm)
  → POST /api/playground/chat (backend-crm)
  → routes/playground.py
      → build_context_bundle_for_playground()
      → enrich_context_bundle()    ← mesmo ponto de convergência do inbound real
      → decide_next_action(bundle) → decision_engine.decide()
      → LLM Mãe + Filha
  ← PlaygroundChatResponse { message, auto_items, phase_trigger_fired,
                              suppress_llm_response, simulated_delay_seconds, ... }
```

---

## Integrações externas

| Sistema | Usado em | Para quê |
|---|---|---|
| **UazAPI** | backend-core (envio), backend-crm (webhook recepção + download de media) | Broker WhatsApp Web (QR session) |
| **OpenAI Whisper** | backend-crm (`audio_transcription.py`) | Transcrição de áudio PTT |
| **LLM (Claude/OpenAI compat.)** | backend-executors (`llm_service.py`) | Decisões Mãe + Filha |

---

## Bases de dados

| BD | Localização | ORM | Usado por |
|---|---|---|---|
| `core.db` | `backend-core/core.db` | SQLAlchemy ORM | backend-core |
| `crm.db` | `backend-crm/database/crm.db` | `sqlite3` raw | backend-crm, backend-executors (leitura via core_client) |

### Tabelas críticas do `crm.db`

| Tabela | Campos-chave | Descrição |
|---|---|---|
| `leads` | `id, user_id, category, bot_disabled, bot_disabled_reason, phases_triggered, triggers_fired` | Lead no pipeline |
| `jobs` | `id, type, status, payload, result, scheduled_at, attempts` | Fila de jobs |
| `messages` | `lead_id, role, content, created_at` | Histórico de conversa |
| `lead_qualification_state` | `lead_id, data_json` | Campos de qualificação extraídos |
| `ai_profiles` | — | Espelho cache do AI Profile (via backend-core) |
| `agents` | `id, token, status, capabilities` | Agentes locais registados |
| `knowledge_items` | `user_id, category, content` | Base de conhecimento do agente |
| `knowledge_item_media` | `item_id, media_url, media_type` | Mídias associadas ao conhecimento |
| `followup_reconcile_guard` | `lead_id, job_id, due_at` | Guard anti-loop do reconciliador |

---

## Autenticação e multi-tenancy

- **Tokens de utilizador:** JWT emitido pelo backend-core em `POST /auth/login`
- **Validação no CRM:** `require_crm_access()` em `security_core.py` — valida Bearer token via `GET /users/me` no backend-core
- **Token server-to-server:** `CORE_SERVICE_TOKEN` para chamadas backend-crm → backend-core sem token de utilizador
- **Multi-tenancy:** todas as tabelas do `crm.db` têm `user_id`; queries sempre filtradas pelo `user_id` derivado do token

---

## Variáveis de ambiente críticas (backend-crm)

| Variável | Descrição |
|---|---|
| `CORE_API_BASE` | URL do backend-core (ex.: `http://localhost:8001`) |
| `CORE_SERVICE_TOKEN` | Token server-to-server |
| `CRM_WEBHOOK_SECRET` | Segredo para validar webhooks inbound UazAPI |
| `CRM_PUBLIC_BASE_URL` | URL pública do CRM (usada para configurar webhook na UazAPI) |
| `OPENAI_API_KEY` | Para transcrição Whisper |
| `UAZAPI_BASE_URL` | Endpoint UazAPI (ex.: `https://free.uazapi.com`) |
