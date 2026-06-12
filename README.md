# crm-auto-digital

SaaS de CRM com automação de vendas via WhatsApp e IA. Arquitectura multi-serviço com 3 backends FastAPI, 3 frontends React e 1 agente local de prospecção.

---

## Serviços

| Serviço | Porta | Stack | Responsabilidade |
|---|---|---|---|
| `backend-core` | 8001 | FastAPI + SQLAlchemy + SQLite | Auth, usuários, planos, conexões WhatsApp |
| `backend-crm` | 8000 | FastAPI + SQLite (raw) | Lógica CRM, pipeline de vendas, IA |
| `backend-executors` | 8002 | FastAPI + workers async | Executor de envio WhatsApp desacoplado |
| `frontend-crm` | 5173 | React + TypeScript + Vite + Tailwind | SPA principal do CRM |
| `frontend-admin` | 5174 | React + TypeScript + Vite + Tailwind | Painel SaaS admin isolado |
| `website` | — | React + TypeScript + Vite + i18next | Site de marketing (pt/en/es) |
| `agent-local` | — | Python standalone | Agente de prospecção/scraping local |

---

## Como rodar localmente

> O `backend-crm` depende do `backend-core` estar a correr primeiro.

```bash
# backend-core
cd backend-core && pip install -r requirements.txt
uvicorn app.main:app --port 8001

# backend-crm
cd backend-crm && pip install -r requirements.txt
uvicorn app:app --port 8000

# backend-executors
cd backend-executors && pip install -r requirements.txt
uvicorn app.main:app --port 8002

# frontend-crm
cd frontend-crm && npm install && npm run dev

# frontend-admin
cd frontend-admin && npm install && npm run dev

# website
cd website && npm install && npm run dev
```

---

## Variáveis de ambiente principais (backend-crm)

| Variável | Descrição |
|---|---|
| `CORE_API_BASE` | URL do backend-core (ex.: `http://localhost:8001`) |
| `CORE_SERVICE_TOKEN` | Token server-to-server para chamadas ao core |
| `CRM_WEBHOOK_SECRET` | Segredo para validar webhooks inbound da UazAPI |
| `CRM_PUBLIC_BASE_URL` | URL pública do CRM |
| `CRM_DB_PATH` | Caminho do SQLite CRM (ex.: `database/crm.db`) |
| `PRIVATE_ORIGINS` | Origins CORS do frontend-crm |

Cada serviço tem um `.env.example` na sua pasta raiz.

---

## Documentação

| Caminho | Conteúdo |
|---|---|
| [`docs/architecture/`](docs/architecture/) | Arquitectura actual de cada área do sistema |
| [`docs/plans/`](docs/plans/) | Roadmap, milestones e funcionalidades planeadas |
| [`docs/ops/`](docs/ops/) | Setup, deploy e operação |
| [`CLAUDE.md`](CLAUDE.md) | Guia técnico detalhado para o agente de IA |
