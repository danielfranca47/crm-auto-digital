# Setup e Desenvolvimento Local

## `.env.local` nunca deve ser commitado (backend-crm)

`backend-crm/app.py` faz `load_dotenv(".env", ...)` seguido de
`load_dotenv(".env.local", override=True)`. Qualquer variável definida em
`.env.local` **sobrepõe** o que estiver no ambiente real do processo — incluindo
variáveis injectadas pelo Railway em produção. Se este ficheiro for commitado no
git, ele é incluído no build/deploy e passa a sobrepor silenciosamente a
configuração de produção, sem que apareça nenhum erro nas variáveis do Railway
(elas continuam a mostrar o valor "correcto" no dashboard — só o processo em
runtime é que usa outro valor).

`.env.local` está no `.gitignore`. Usar este ficheiro só para overrides pessoais
de desenvolvimento local (ex.: apontar para serviços locais em portas
diferentes) — nunca para valores que possam acabar commitados.

---

## Pré-requisitos

- Python 3.11+ com `venv` por serviço
- Node.js + npm para os frontends
- SQLite (incluído no Python)

---

## Subir todos os serviços

### Backend-core (porta 8001)

```powershell
cd backend-core
.\.venv\Scripts\activate
python -m uvicorn app.main:app --reload --port 8001
```

### Backend-crm (porta 8000)

> Depende do backend-core estar rodando primeiro.

```powershell
cd backend-crm
.\.venv\Scripts\activate
uvicorn app:app --reload --port 8000
```

### Backend-executors (porta 8010)

Em um terminal:
```powershell
cd backend-executors
.\.venv\Scripts\activate
uvicorn app.main:app --reload --port 8010 --app-dir .
```

Em outro terminal (worker de processamento de jobs):
```powershell
cd backend-executors
.\.venv\Scripts\activate
python -m app.workers.whatsapp_worker
```

> Para execução de jobs, garantir que o usuário tenha uma instância WhatsApp conectada.

### Agent-local

Confirmar `.env` com:
```
BACKEND_URL=http://localhost:8000
AGENT_ID=...
AGENT_TOKEN=...
JOB_TYPES=whatsapp_send,maps_search_fallback,maps_enrich_fallback
```

```powershell
cd agent-local
.\.venv\Scripts\activate
python main.py
```

### Frontend-crm (porta 8080)

```powershell
cd frontend-crm
npm install
npm run dev -- --port 8080
```

---

## Ordem recomendada de inicialização

1. backend-core (8001)
2. backend-crm (8000)
3. backend-executors — servidor (8010) + worker
4. agent-local (se precisar de prospecção local)
5. frontend-crm (8080)
