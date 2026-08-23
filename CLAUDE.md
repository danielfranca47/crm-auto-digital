# CLAUDE.md — crm-auto-digital

Guia de referência para o Claude Code trabalhar neste repositório.

---

## Visão geral

SaaS de CRM com automação de vendas via WhatsApp (IA). Arquitetura multi-serviço:
- 3 backends FastAPI (Python)
- 3 frontends React (TypeScript)
- 1 agente local de prospecção (Python)

---

## Mapa de serviços

```
crm-auto-digital/
├── backend-core/       # Auth, usuários, planos, WhatsApp connections
├── backend-crm/        # Lógica central do CRM, IA, leads, follow-up
├── backend-executors/  # Executor assíncrono de envio WhatsApp
├── frontend-crm/       # SPA do CRM (React + Vite)
├── frontend-admin/     # Painel SaaS admin isolado (React + Vite, porta 5174)
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

### Paridade Playground ↔ WhatsApp Real

> **Leia antes de alterar:** `routes/playground.py`, `services/whatsapp_inbound/inbound_handler.py`, `routes/executor.py` ou `services/ai_orchestrator/orchestrator.py`.
> Documentação completa: [`backend-crm/docs/playground-whatsapp-parity.md`](backend-crm/docs/playground-whatsapp-parity.md)

**Regra central:** todo campo novo do `ContextBundle` que afeta o comportamento do LLM deve ser adicionado via `enrich_context_bundle()` em `services/ai_orchestrator/orchestrator.py` — nunca diretamente em apenas um dos builders. Isso garante que o playground e o executor (agente real) recebam contexto equivalente.

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

## frontend-admin

**Porta dev:** 5174
**Stack:** React 18 + TypeScript + Vite + TailwindCSS + shadcn/ui
**Responsabilidade:** painel SaaS admin completamente isolado do `frontend-crm`

Separado do frontend-crm para evitar colisões com o contexto de autenticação de usuário (o CRM redirecionava `/saas-admin` para `/login` por falta de token de usuário).

### Páginas (`src/pages/`)
- `AdminLogin.tsx` — login admin independente
- `AdminDashboard.tsx` — KPIs globais e instâncias offline
- `AdminUsers.tsx` — listagem e gestão de extensões de usuários
- `AdminInstances.tsx` — reconexão de instâncias WhatsApp
- `AdminAgents.tsx` — agentes, playbooks e diff de AI profile por usuário

### Estrutura
- `src/lib/admin-token.ts` — persist/read/clear/validate JWT admin
- `src/services/api.ts` — cliente admin-only (core + crm), sem LeadsContext
- `src/components/AdminGuard.tsx` — guard de autenticação via `<Navigate>`
- `src/components/AdminLayout.tsx` — sidebar com NavLink

### Env
- `VITE_CORE_BASE` — URL do backend-core
- `VITE_CRM_BASE` — URL do backend-crm

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

### Painel Admin — Agentes e AI Profiles

**Regra obrigatória:** sempre que um novo campo for adicionado ao AI profile (`ai_profiles`) ou um novo estágio/variável de agente for introduzido no sistema, `docs/architecture/admin-agents-contract.md` deve ser atualizado. Verificar também se `AdminAgents.tsx` precisa capturar e exibir o novo campo.

Contexto: o painel admin em `frontend-admin/src/pages/AdminAgents.tsx` consome `GET /admin/agents/overview` e `GET /admin/agents/users/{id}` do backend-crm (montados sem o prefixo `/api/`). O contrato de campos está documentado em `docs/architecture/admin-agents-contract.md`.

---

## Documentação de Arquitetura

Os arquivos abaixo descrevem a estrutura **atual** de cada área do sistema. Ler o arquivo relevante antes de trabalhar em uma área desconhecida.

| Arquivo | Cobre |
|---|---|
| [`docs/architecture/pipeline-phases.md`](docs/architecture/pipeline-phases.md) | Fases de qualificação, apresentação e fechamento por tipo de agente; guardrails anti-loop |
| [`docs/architecture/sales-flow.md`](docs/architecture/sales-flow.md) | Camada 7 — Fluxo de Venda: fases p0–p5, tipos de bloco, pipeline por agent_mode, execução backend |
| [`docs/architecture/followup.md`](docs/architecture/followup.md) | Arquitetura de follow-up: estados, reconciliador, jobs, modal |
| [`docs/architecture/llm-architecture.md`](docs/architecture/llm-architecture.md) | LLMs Mãe e Filhas, contratos, fluxo de decisão |
| [`docs/architecture/agents.md`](docs/architecture/agents.md) | Agentes locais e AI Profiles: campos, endpoints, ciclo de vida |
| [`docs/architecture/webhooks.md`](docs/architecture/webhooks.md) | Webhook inbound WhatsApp: filtros, fluxo, grupos ignorados |
| [`docs/architecture/playground-parity.md`](docs/architecture/playground-parity.md) | Paridade Playground ↔ WhatsApp real (ContextBundle) |
| [`docs/architecture/admin-agents-contract.md`](docs/architecture/admin-agents-contract.md) | Contrato AdminAgents frontend ↔ backend |

**Intenções futuras e roadmaps:** [`docs/plans/`](docs/plans/)
**Setup e operação:** [`docs/ops/`](docs/ops/)

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

# frontend-admin (porta 5174)
cd frontend-admin && npm install && npm run dev

# website
cd website && npm install && npm run dev
```

> O backend-crm depende do backend-core estar rodando primeiro.

---

## Git workflow

**Regra obrigatória:** após cada implementação concluída (nova funcionalidade ou correção), o Claude **deve** criar um commit na branch da implementação com a descrição da tarefa antes de encerrar a resposta.

### Estratégia de branch por implementação

Cada implementação (arquivo em `docs/implementations/`) vive na sua própria branch, criada a partir da branch em que o utilizador estiver a trabalhar no momento (normalmente `main`, mas pode ser outra branch de feature — ver "Branches aninhadas" abaixo).

**Criação:**
- Ocorre logo após o plano ser aprovado no Plan Mode (Passo 0 do guia de implementações), antes de criar o arquivo `.md`.
- Nome: `fix/<slug>` ou `feat/<slug>` — o mesmo slug usado no nome do arquivo de implementação.
- Claude **propõe o nome e pede confirmação** antes de criar a branch (`git checkout -b`) — não é automático.

**Trabalho em paralelo (várias implementações ao mesmo tempo):**
- Usar `git worktree add <pasta> -b <branch>` para cada implementação ativa em paralelo, cada uma na sua pasta isolada — evita `stash`/`checkout` para alternar entre tarefas.
- Remover a worktree (`git worktree remove <pasta>`) depois do merge de volta.

**Quando a implementação é graduada** (todos os checks validados, ver processo de graduação):
1. Voltar para a branch que originou a branch de feature.
2. `git merge` local da branch de feature nela (merge direto, sem PR).
3. `git push` da branch original.
4. Apagar a branch de feature local (`git branch -d`) depois do merge confirmado.

Merges são sempre sequenciais — nunca simultâneos. Se duas branches estiverem prontas ao mesmo tempo, mergear e dar push de uma primeiro; só depois mergear a segunda, resolvendo ali qualquer conflito que surja.

**Branches aninhadas:** se, dentro de uma branch de feature (que não é `main`), for necessária uma nova implementação/sub-tarefa, a nova branch nasce a partir da branch de feature atual — não de `main` — e o merge de volta é só para ela, nunca direto para `main`. Evitar mais de 1 nível de aninhamento.

**Resolução de conflitos:** se `git merge` reportar conflito, Claude **nunca resolve sozinho e commita silenciosamente**. Parar o merge, explicar em linguagem simples o que cada lado mudou nos trechos conflitantes, propor uma resolução e só finalizar o merge (`git add` + `git commit`) depois de confirmação explícita do utilizador. Nunca usar `--ours`/`--theirs` sem explicar antes.

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

- Commitar sempre na branch da implementação em curso (ver "Estratégia de branch por implementação" acima) — nunca trocar de branch no meio de uma fase sem commitar (ou stash) o que estiver pendente
- **Nunca** usar `--amend` em commits já publicados no remote
- Push automático só ocorre no passo de merge de volta de uma implementação graduada (ver "Estratégia de branch por implementação"); fora disso, **nunca** fazer push automático — somente commit local
- Usar `git add` nos arquivos específicos alterados (evitar `git add -A` com arquivos sensíveis)
- Se não houver alteração de código (apenas leitura/análise), **não criar commit**

### Manutenção de docs de arquitetura

Antes de criar o commit, verificar se alguma alteração afeta uma área documentada em `docs/architecture/`. Se sim:
- Abrir o arquivo correspondente
- Atualizar apenas as seções afetadas para refletir o estado atual
- **Sem histórico**: reescrever a seção, não acrescentar parágrafos de "agora passou a..."
- Se a funcionalidade for nova e não existir doc correspondente, criar `docs/architecture/<nome>.md`

O objetivo dos docs de arquitetura é ser um espelho do código atual — enxuto e confiável.

---

## Workflow de Implementação de Features

Todo pedido de nova funcionalidade ou correção não-trivial segue este ciclo obrigatório. Os arquivos guia estão em `docs/implementations/`.

### Ciclo de vida

```
1. Plan Mode (obrigatório antes de qualquer código)
   → ler _guia-documentar-implementacao.md
   → diagnóstico: já existe? o que construir? riscos?
   → aguardar aprovação do utilizador

2. Criar a branch da implementação (fix/<slug> ou feat/<slug>)
   → propor o nome e pedir confirmação antes de criar (ver "Estratégia de
     branch por implementação")
   → criar docs/implementations/<etapa>-<slug>.md nessa branch
   → preencher com template de _template-implementacao.md
   → branch + arquivo só criados APÓS aprovação do plano

3. Implementar fase a fase
   → cada fase = 1 commit
   → registar hash do commit no arquivo .md imediatamente após o commit
   → escrever relatório da fase em linguagem simples no .md + perguntar se
     quer teste automatizado agora — sempre acompanhado de um prompt de
     retomada pronto para colar (ver `_guia-documentar-implementacao.md`,
     secção "Antes de pedir validação ao utilizador")

4. Validar os checks — duas formas possíveis, conforme a resposta no passo 3
   → Se aceitou teste automatizado: Claude testa ao vivo via browser (MCP),
     com o utilizador acompanhando, e já marca [x] no arquivo com data
   → Se não (ou prefere manual): aguardar o utilizador testar e reportar —
     nesta conversa ou numa nova, usando o prompt de retomada do passo 3 —
     e então marcar [x] no arquivo com data
   → se teste revelar problema: nova fase no mesmo arquivo (Plan Mode novamente)

5. Graduação (só quando TODOS os checks estão [x])
   → seguir _processo-graduacao-implementacao.md
   → migrar informação arquitectural relevante para docs/architecture/
   → git rm do arquivo de implementação
   → commit único de graduação
   → merge da branch de volta para a que a originou + push (ver "Estratégia
     de branch por implementação")
```

### Regras críticas

- **Nunca avançar para código sem plano aprovado.** Plan Mode não é opcional.
- **Nunca graduar com checks `[ ]` em aberto.** Checks marcados `[⏭️]` (pulados justificados) são permitidos.
- **O arquivo .md é o contrato vivo da feature** — deve reflectir sempre o estado real da implementação.
- **Cada fase tem exactamente 1 commit.** O hash é registado no .md logo após o commit.
- **O commit não é o fim da fase.** Nunca terminar a resposta só com o commit — escrever o relatório em linguagem simples e perguntar sobre teste automatizado (com prompt de retomada pronto) é parte obrigatória do fecho da fase, não um passo opcional do guia.
- Um arquivo de implementação com `Status: Em andamento` significa que há testes pendentes — não iniciar nova etapa sobreposta sem validar primeiro.

### Arquivos de referência

| Arquivo | Propósito |
|---|---|
| [`docs/implementations/_guia-documentar-implementacao.md`](docs/implementations/_guia-documentar-implementacao.md) | Processo completo passo a passo |
| [`docs/implementations/_template-implementacao.md`](docs/implementations/_template-implementacao.md) | Template concreto preenchido |
| [`docs/implementations/_processo-graduacao-implementacao.md`](docs/implementations/_processo-graduacao-implementacao.md) | Como graduar para docs/architecture/ |

