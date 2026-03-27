# CLAUDE.md — crm-auto-digital

Guia de referência para o Claude Code trabalhar neste repositório.

---

## Visão geral

SaaS de CRM com automação de vendas via WhatsApp (IA). Arquitetura multi-serviço:
- 3 backends FastAPI (Python)
- 2 frontends React (TypeScript)
- 1 agente local de prospecção (Python)

---

## Mapa de serviços

```
crm-auto-digital/
├── backend-core/       # Auth, usuários, planos, WhatsApp connections
├── backend-crm/        # Lógica central do CRM, IA, leads, follow-up
├── backend-executors/  # Executor assíncrono de envio WhatsApp
├── frontend-crm/       # SPA do CRM (React + Vite)
├── website/            # Site de marketing multi-idioma (React + Vite)
└── agent-local/        # Agente local de prospecção/scraping (Python)
```

---

## backend-core

**Porta padrão:** 8001
**Stack:** FastAPI + SQLAlchemy ORM + SQLite (`app/core.db`)
**Responsabilidade:** fonte de verdade de autenticação e configuração de conta

### Domínios
- `auth` — login, JWT
- `users` — perfil de usuário
- `plans` / `subscriptions` — planos e assinaturas SaaS
- `catalog` / `products` — catálogo de produtos
- `ai_profiles` — configuração do perfil de IA por usuário (`agent_mode`, `presentation_variant`, `offer_pack`, etc.)
- `whatsapp_connections` / `whatsapp_instances` — conexões WhatsApp via UazAPI
- `whatsapp_send` — envio de mensagem pelo core

### Provider externo
- UazAPI (`app/providers/uazapi_client.py`) — API de WhatsApp

### Padrão de banco
- ORM SQLAlchemy, modelos em `app/models/`
- Migrations via `ensure_*` functions em `app/db.py` e `seed_initial_data` no startup

---

## backend-crm

**Porta padrão:** 8000
**Stack:** FastAPI + SQLite raw (`sqlite3`) — sem ORM
**Banco:** `database/crm.db`
**Responsabilidade:** toda a lógica de CRM, pipeline de vendas e IA

### Auth
- Todas as rotas privadas usam `require_crm_access` (em `security_core.py`)
- Valida Bearer token consultando `/users/me` e `/me/entitlements` no backend-core
- `CORE_API_BASE` aponta para o backend-core
- `CORE_SERVICE_TOKEN` usado para chamadas server-to-server

### Rotas principais
| Prefixo | Arquivo | Descrição |
|---|---|---|
| `/api/leads` | `routes/leads.py` | CRUD de leads, movimentação Kanban |
| `/api/prospeccao` | `routes/prospeccao.py` | Prospecção automatizada |
| `/api/appointments` | `routes/appointments.py` | Agenda e compromissos |
| `/api/agents` | `routes/agents.py` | Gestão de agentes locais |
| `/api/assistente-ia` | `routes/assistente_ia.py` | Chat com assistente IA |
| `/api/knowledge` | `routes/knowledge.py` | Base de conhecimento |
| `/api/usage` | `routes/usage.py` | Consumo do plano |
| `/webhooks/whatsapp/inbound` | `routes/webhooks.py` | Webhook inbound WhatsApp (Orion) |

### Multitenancy
- Todas as tabelas têm `user_id`
- Queries sempre filtram por `user_id` derivado do token do core

### Banco de dados (CRM)
- Queries manuais com `get_connection()` retornando `sqlite3.Connection`
- `conn.row_factory = sqlite3.Row` — linhas acessadas como dicionário
- `ensure_column()` para migrações idempotentes
- Migrations SQL em `migrations/`

### Pipeline de IA (fluxo inbound)
```
WhatsApp → UazAPI → POST /webhooks/whatsapp/inbound
  → services/whatsapp_inbound/inbound_handler.py
  → services/whatsapp_inbound/guardrail.py      # verifica se deve responder
  → services/ai_orchestrator/orchestrator.py    # monta contexto + histórico
  → services/ai_playbooks/                      # regras de playbook por agente
  → automations/assistente_ia/llm.py            # chamada ao LLM
  → automations/assistente_ia/processor.py      # pós-processamento
  → job enfileirado → backend-executors → UazAPI → WhatsApp
```

### Serviços críticos de negócio

- **`services/qualification_state.py`** — extrai e persiste campos de qualificação do lead
- **`services/qualification_guardrails.py`** — bloqueia avanço de estágio se qualificação incompleta
  Campos mínimos por modo: `consultivo` (6 campos), `agenda` (4 campos), `direto` (3 campos)
- **`services/followup_state.py`** — máquina de estado de follow-up, agenda próximo envio
- **`services/followup_reconciler.py`** — reconcilia estado de follow-up
- **`services/lead_category_policy.py`** — side-effects de movimentação de categoria
  Ex.: entrar em `closing` pode desabilitar o bot automaticamente
- **`services/agent_type.py`** — resolve tipo de agente (`agent_1`, `agent_3`) do lead
- **`services/jobs_service.py`** — fila de jobs com lease, retry e backoff

### Jobs (fila interna)
Tipos de job:
- `whatsapp.send.local` — envio de mensagem
- `whatsapp.inbound.n8n` — inbound via n8n
- `whatsapp.followup.tick` — tick de follow-up agendado
- `maps.search.local` / `maps.enrich.local` — prospecção Google Maps

### Categorias de lead (pipeline Kanban)
Estágios: lead entra na fila → qualificação → closing → arquivado
A movimentação entre estágios tem guardrails e side-effects definidos em `services/`.

### Tipos de agente (agent_mode)
- `consultivo` — atendimento consultivo aprofundado
- `agenda` / `sdr_scheduler` — foco em agendamento
- `direto` / `closer` — fechamento direto

### Variantes de apresentação
- `sales` — oferta direta
- `scheduler` — agendamento primeiro
- `hybrid` — combinação configurável via `hybrid_flow_style`

---

## backend-executors

**Stack:** FastAPI + workers assíncronos
**Responsabilidade:** executar jobs de envio WhatsApp desacoplado do CRM

### Estrutura
- `app/runners/whatsapp.py` — runner de envio
- `app/workers/whatsapp_worker.py` — worker que consome a fila
- `app/api/health.py` — health check
- `app/clients/` — clientes HTTP para UazAPI
- `app/contracts/` — contratos compartilhados (ex.: `qualification_contract.py`)

---

## frontend-crm

**Stack:** React 18 + TypeScript + Vite + TailwindCSS + shadcn/ui + Radix UI
**Porta dev:** 8080 (ou 5173)

### Páginas (`src/pages/`)
- `Index.tsx` — KanbanBoard principal (pipeline de leads)
- `Dashboard.tsx` — métricas e agenda do dia
- `AssistenteIA.tsx` — chat com IA
- `Prospeccao.tsx` — prospecção
- `Pesquisa.tsx` — busca de leads
- `AiProfile.tsx` — configuração do perfil de IA
- `Assinatura.tsx` — plano e assinatura
- `MinhaConta.tsx` / `UsoDoPlano.tsx` — conta e consumo
- `SaaSAdmin/` — área administrativa SaaS

### Componentes chave (`src/components/`)
- `KanbanBoard.tsx` / `KanbanColumn.tsx` / `LeadCard.tsx` — pipeline visual
- `LeadCardDialog.tsx` — modal completo do lead
- `FollowUpTransitionModal.tsx` — modal de transição de follow-up
- `ScheduleAppointmentDialog.tsx` — agendamento
- `SearchAutocomplete.tsx` — busca

### Estado global
- `LeadsContext` (`src/contexts/`) — estado do Kanban, colunas, leads
- React Query — fetching/caching de dados assíncronos
- `src/services/api.ts` — cliente HTTP centralizado para o backend-crm

---

## website

**Stack:** React + TypeScript + Vite + i18next
**Idiomas suportados:** `en`, `pt`, `es`
**Roteamento:** prefixo de idioma (`/en`, `/pt`, `/es`)
Separado do frontend-crm; deploy independente.

---

## agent-local

**Stack:** Python standalone com `.venv` próprio
Agente de prospecção local (scraping, coleta de posts).
Configuração via `.env` e `.env.agent1` / `.env.agent2`.

---

## Variáveis de ambiente (backend-crm)

| Variável | Descrição |
|---|---|
| `CORE_API_BASE` | URL do backend-core (ex.: `http://localhost:8001`) |
| `CORE_SERVICE_TOKEN` | Token server-to-server para chamadas ao core |
| `CRM_WEBHOOK_SECRET` | Segredo para validar webhooks inbound da UazAPI |
| `CRM_PUBLIC_BASE_URL` | URL pública do CRM (ex.: `https://api.danielfranca.pt`) |
| `CRM_DB_PATH` | Caminho do SQLite CRM (ex.: `database/crm.db`) |
| `PRIVATE_ORIGINS` | Origins CORS do frontend-crm |
| `PUBLIC_ORIGINS` | Origins CORS do website |

---

## Convenções de código

### Backend (Python)
- Sem ORM no `backend-crm` — usar `get_connection()` e queries SQL manuais
- Sempre filtrar por `user_id` nas queries de dados de negócio
- Migrações via `ensure_column()` (idempotente) — não alterar schema diretamente
- Guardrails de negócio ficam em `services/`, não nas rotas
- Rotas devem ser finas — delegar lógica para `services/`

### Frontend (TypeScript/React)
- Componentes UI base via shadcn/ui (em `src/components/ui/`)
- Dados do servidor via React Query — não usar `useState` para dados remotos
- Estado de leads centralizado no `LeadsContext`
- Chamadas HTTP somente via `src/services/api.ts`

---

## Como rodar localmente

```bash
# backend-core (porta 8001)
cd backend-core && pip install -r requirements.txt && uvicorn app.main:app --port 8001

# backend-crm (porta 8000)
cd backend-crm && pip install -r requirements.txt && uvicorn app:app --port 8000

# backend-executors
cd backend-executors && pip install -r requirements.txt && uvicorn app.main:app --port 8002

# frontend-crm
cd frontend-crm && npm install && npm run dev

# website
cd website && npm install && npm run dev
```

> O backend-crm depende do backend-core estar rodando primeiro.

---

## Git workflow

**Regra obrigatória:** após cada implementação concluída (nova funcionalidade ou correção), o Claude **deve** criar um commit na branch atual com a descrição da tarefa antes de encerrar a resposta.

### Convenção de mensagem (Conventional Commits)

```
feat: <descrição curta do que foi adicionado>
fix: <descrição curta do que foi corrigido>
```

### Corpo do commit

Incluir no corpo:
- Arquivos alterados e o que mudou em cada um
- Motivação da mudança (contexto mínimo)

Exemplo:
```
feat: adicionar rota de exportação de leads

- backend-crm/routes/leads.py: nova rota GET /api/leads/export
- backend-crm/services/export_service.py: lógica de geração CSV
```

### Regras

- Sempre commitar na **branch atual** (nunca trocar de branch)
- **Nunca** usar `--amend` em commits já publicados no remote
- **Nunca** fazer push automático — somente commit local
- Usar `git add` nos arquivos específicos alterados (evitar `git add -A` com arquivos sensíveis)
- Se não houver alteração de código (apenas leitura/análise), **não criar commit**
