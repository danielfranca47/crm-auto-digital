# INVESTIGAÇÃO FRONTEND — Estrutura do Sistema CRM

> Análise técnica do código-fonte realizada em 2026-03-22.
> Nenhum código foi alterado — documento de referência apenas.

---

## INVESTIGAÇÃO 1 — Estrutura de Rotas e URLs

---

### 1. Framework web utilizado

**FastAPI 0.116.2** com servidor ASGI Uvicorn.

```python
# app.py:11
from fastapi import FastAPI

# app.py:44
app = FastAPI(title="CRM API", version="1.0.0")
```

O sistema de roteamento usa `APIRouter` nativo do FastAPI, sem nenhuma camada extra de roteamento.

---

### 2. Rotas que servem páginas HTML

**Nenhuma.** O `backend-crm` é uma API REST pura — todas as rotas retornam JSON.

Não existe `HTMLResponse`, `TemplateResponse`, diretório de templates ou arquivos `.html` renderizáveis no projeto. A interface visual é inteiramente responsabilidade do `frontend-crm` (React/Vite em porta separada).

---

### 3. Prefixo de contexto global

**Sim. Todas as rotas privadas usam o prefixo `/api`.**

```python
# app.py:70-80
app.include_router(leads.router,        prefix="/api/leads",       ...)
app.include_router(search.router,       prefix="/api/pesquisa",    ...)
app.include_router(assistente_ia.router, prefix="/api/assistente-ia", ...)
app.include_router(agents.router,       prefix="/api/agents",      ...)
app.include_router(appointments.router, prefix="/api/appointments", ...)
app.include_router(knowledge.router,    prefix="/api/knowledge",   ...)
app.include_router(usage.router,        prefix="/api/usage",       ...)
```

Outros prefixos presentes:
- `/webhooks` — recepção de eventos inbound da UazAPI
- `/public` — sub-app montada para endpoints sem autenticação (ex: captura de leads via formulário)

**Mapa completo de rotas registradas:**

| Módulo | Prefixo | Autenticação |
|---|---|---|
| leads | `/api/leads` | `require_crm_access` |
| agents | `/api/agents` | Misto (algumas com token de agente) |
| appointments | `/api/appointments` | `require_crm_access` |
| assistente-ia | `/api/assistente-ia` | `require_crm_access` |
| prospeccao | `/api/prospeccao` | `require_crm_access` |
| knowledge | `/api/knowledge` | `require_crm_access` |
| usage | `/api/usage` | `require_crm_access` |
| executor (interno) | `/api` | Service token |
| webhooks | `/webhooks` | Webhook secret header |
| public | `/public` | Form token próprio |

---

### 4. Como funciona a autenticação

**Bearer Token (JWT) validado via HTTP Authorization header, sem cookies ou sessão.**

**Fluxo completo:**

1. O usuário faz login no `backend-core` (`POST /auth/login`) — o JWT é emitido pelo core
2. O `frontend-crm` armazena o token e envia em toda requisição como `Authorization: Bearer <token>`
3. O `backend-crm` valida assim:

```python
# security_core.py:7
security = HTTPBearer(auto_error=False)

# security_core.py:18-31 — get_current_user()
# Extrai Bearer token → chama fetch_core_user(token) no backend-core
# Valida o token consultando GET /users/me no backend-core

# security_core.py:34-47 — require_crm_access()
# Verifica entitlements via GET /me/entitlements no backend-core
# Exige product_code="crm" com status="active"
```

**Rota de login:** `POST /auth/login` — no `backend-core` (porta 8001), não no `backend-crm`.

**Sistema stateless:** não há sessão, cookie ou refresh token no CRM. Cada requisição valida o JWT contra o core.

---

### 5. Padrões de URL com ID de usuário ou agente

**ID de usuário nunca aparece na URL.** A identidade do usuário é derivada do JWT token e injetada internamente como `current_user.id`. Todas as queries filtram por esse ID internamente.

**ID de agente aparece no path em rotas de ação:**

```python
# routes/agents.py:83
POST /api/agents/{agent_id}/revoke

# routes/agents.py:88
POST /api/agents/{agent_id}/reprovision

# routes/agents.py:111-116
GET /api/agents/next-job?agent_id=<id>&token=<token>
```

**ID de lead aparece no path:**

```python
# routes/leads.py
GET /api/leads/{lead_id}/appointments
```

**Padrão geral:** coleção (`/api/agents`) → recurso (`/api/agents/{id}`) → ação (`/api/agents/{id}/acao`).

---

### 6. URLs recomendadas para as novas páginas

Com base no padrão de roteamento atual do `backend-crm`:

**Endpoints de API para o Dashboard do Agente:**
```
GET /api/agents/{agent_id}
```
Retornaria status, fila de jobs, estado de conexão e métricas do agente. Segue o padrão RESTful de recurso já existente.

**Endpoints de API para Configuração do Agente:**
```
PATCH /api/agents/{agent_id}
```
Para atualização de campos individuais (nome, capacidades, configurações). Consistente com o padrão PATCH usado em `routes/leads.py`.

> **Nota sobre o frontend:** as URLs navegáveis pelo usuário são definidas no `frontend-crm` (React Router), não no backend. Para as páginas React:
> - Dashboard: `/agentes/{agent_id}` ou `/agentes/{agent_id}/dashboard`
> - Configuração: `/agentes/{agent_id}/configuracoes`
>
> Esse padrão é consistente com as páginas já existentes no frontend (ex: `/ai-profile`, `/assinatura`, `/minha-conta`).

---

## INVESTIGAÇÃO 2 — Estrutura de Dados do Kanban

---

### 1. Onde os dados do Kanban são carregados

**Endpoint:** `GET /api/leads/`

**Arquivo:** `backend-crm/routes/leads.py`, linhas 263–303

**Query SQL executada:**

```sql
-- routes/leads.py:272-296
SELECT l.*,
       next_app.start_at    AS next_start_at,
       next_app.description AS next_description
FROM leads l
LEFT JOIN (
    SELECT lead_id, start_at, description
    FROM (
        SELECT a.lead_id,
               a.start_at,
               a.description,
               ROW_NUMBER() OVER (
                   PARTITION BY a.lead_id
                   ORDER BY datetime(a.start_at) ASC
               ) AS rn
        FROM appointments a
        WHERE datetime(a.start_at) >= datetime('now')
    )
    WHERE rn = 1
) AS next_app ON next_app.lead_id = l.id
WHERE l.user_id = ?
ORDER BY l.createdAt DESC
```

A resposta enriquece cada lead com um campo sintético `nextScheduledAction` montado em `routes/leads.py:48-66` a partir do próximo agendamento.

---

### 2. Campos disponíveis em cada card de lead

**Schema inicial da tabela `leads`** (`database.py:525-541`):

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `id` | INTEGER PK | AUTOINCREMENT | Identificador único |
| `user_id` | INTEGER | — | Dono do lead |
| `companyName` | TEXT | — | Nome da empresa |
| `contactName` | TEXT | NULL | Nome do contato |
| `phone` | TEXT | NULL | Número de telefone |
| `email` | TEXT | NULL | Email |
| `origin` | TEXT | `'Manual'` | Origem do lead |
| `category` | TEXT | `'to-prospect'` | Coluna do Kanban |
| `customMessage` | TEXT | NULL | Mensagem personalizada |
| `observations` | TEXT | NULL | Observações livres |
| `potentialValue` | REAL | `0` | Valor potencial do negócio |
| `kanban_highlight` | TEXT | NULL | Destaque visual no Kanban |
| `kanban_highlight_at` | DATETIME | NULL | Timestamp do destaque |
| `createdAt` | DATETIME | CURRENT_TIMESTAMP | Data de criação |
| `lastMovement` | DATETIME | CURRENT_TIMESTAMP | Última movimentação |
| `priority` | INTEGER | `1` | Prioridade estática |

**Campos adicionados por migrations** (`database.py:662-668`):

| Campo | Tipo | Descrição |
|---|---|---|
| `bot_disabled` | INTEGER (0/1) | Bot ativo ou pausado |
| `bot_disabled_reason` | TEXT | Motivo da pausa |
| `agent_type` | TEXT | Tipo de agente associado |
| `followup_contract` | TEXT (JSON) | Contrato de follow-up serializado |
| `followup_status` | TEXT | Status do follow-up (`active`, `closed`, etc.) |
| `next_followup_at` | DATETIME | Próximo disparo agendado |

**Campo sintético adicionado na resposta da API** (`routes/leads.py:48-66`):

| Campo | Tipo | Descrição |
|---|---|---|
| `nextScheduledAction` | Object `{date, description}` | Próximo agendamento do lead |

---

### 3. Colunas do Kanban — campo e valores no banco

**Campo:** `category` (TEXT, `database.py:533`)

| Coluna no Kanban | Valor no banco | Referência no código |
|---|---|---|
| Prospecção / Fila | `to-prospect` | `database.py:533` (DEFAULT) |
| Qualificação | `qualification` | `routes/leads.py:491`, `guardrail.py` |
| Apresentação | `apresentation` | `routes/leads.py:424-425` |
| Follow-up | `follow-up` | `routes/leads.py:491,533` |
| Fechamento | `closing` | `lead_category_policy.py:26` |

> **Atenção ortográfica:** o valor no banco é `apresentation` (sem 'p' duplo), não `presentation`. Respeitar esse valor exato ao criar filtros ou queries.

**Categorias de saída do pipeline** (não são colunas ativas do Kanban):
- `prospect-refused` — recusou contato
- `disqualified` — desqualificado
- `archived` — arquivado

---

### 4. Campo de score ou temperatura

**Não existe um campo dedicado de score/temperatura na tabela `leads`.**

**O que existe hoje:**

| Campo | Onde | Limitação |
|---|---|---|
| `potentialValue` (REAL) | Tabela `leads`, `database.py:536` | Campo financeiro, não de engajamento |
| `kanban_highlight` (TEXT) | Tabela `leads`, `database.py:537` | Visual apenas, sem semântica de score |
| `temperature` dentro de `followup_contract` | JSON em `routes/leads.py:477` | Só existe durante follow-up ativo; não é um campo indexável |

**Recomendação para implementação futura:**

Adicionar via `ensure_column()` no padrão já usado em `database.py:662-668`:

```python
ensure_column(conn, "leads", "lead_score", "INTEGER DEFAULT 0")
```

Isso é idempotente e não quebra registros existentes. O score seria atualizado a cada inbound processado pelo orquestrador.

---

### 5. Endpoint de contagem de leads por coluna

**Não existe nenhum endpoint que retorne contagem agrupada por `category`.**

**O que existe mais próximo:**

| Endpoint | O que retorna | Arquivo |
|---|---|---|
| `GET /api/usage` | Total geral de leads (`COUNT(*)`) | `routes/usage.py:34,92-100` |
| `GET /api/agents/jobs/summary` | Resumo de jobs de agentes | `routes/agents.py:143-145` |
| `GET /api/prospeccao/whatsapp/summary` | Resumo de envios WhatsApp | `routes/prospeccao.py:211-216` |

**Para calcular a contagem no frontend**, os dados já estão disponíveis: o `GET /api/leads/` retorna todos os leads com o campo `category`. O frontend pode agrupar por `category` e contar localmente sem nova requisição.

**Query que um futuro endpoint `GET /api/leads/stats` precisaria executar:**

```sql
SELECT category, COUNT(*) as count
FROM leads
WHERE user_id = ?
GROUP BY category
```

---

### 6. Campo de estágio de qualificação (F1, F2, F3)

**Não existe um campo F1/F2/F3 na tabela `leads` nem em nenhuma tabela.**

O sistema não usa estágios discretos de qualificação. Em vez disso, usa **extração campo a campo**, rastreada em uma tabela separada:

**Tabela:** `lead_qualification_state` (`database.py:641-654`)

| Campo | Tipo | Descrição |
|---|---|---|
| `lead_id` | INTEGER FK | Referência ao lead |
| `stage` | TEXT | Estágio genérico (DEFAULT `'qualification'`) |
| `data_json` | TEXT (JSON) | Campos coletados até o momento |
| `asked_questions_json` | TEXT (JSON) | Histórico de perguntas feitas |
| `last_questioned_field` | TEXT | Último campo perguntado |
| `attempts_json` | TEXT (JSON) | Tentativas por campo |
| `playbook_key` | TEXT | Playbook de qualificação em uso |
| `agent_mode_normalized` | TEXT | Modo do agente (consultivo/agenda/direto) |

**Acesso via `qualification_state.py`:**

```python
# qualification_state.py:61
get_qualification_state(lead_id)  # retorna estado completo

# qualification_state.py:127
upsert_qualification_state(...)   # atualiza estado
```

**Campos mínimos por modo** (definidos em `qualification_guardrails.py`):
- `consultivo` — 6 campos obrigatórios
- `agenda` — 4 campos obrigatórios
- `direto` — 3 campos obrigatórios

A "etapa" atual de qualificação é inferida pela proporção de campos preenchidos em `data_json` versus os campos mínimos requeridos para o modo. Se for necessário expor F1/F2/F3 no frontend, precisaria ser calculado dinamicamente com base nessa proporção.

---

*Gerado por análise de código-fonte — sem alterações no sistema*
*Branch: `feature/etapa-8-n8n-orion` — backend-crm*
