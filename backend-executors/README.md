# Backend Executors (MVP)

Serviço FastAPI mínimo para executar jobs internos (executor), sem integrações externas nesta etapa.

## Como rodar (local)

1) Crie um `.env` em `backend-executors/` (ou copie `.env.example`).
2) Instale dependências:
   ```bash
   pip install -r backend-executors/requirements.txt
   ```
3) Suba o serviço:
   ```bash
   uvicorn app.main:app --reload --port 8010 --app-dir backend-executors
   ```

## Health check

```bash
curl http://localhost:8010/health
```

Resposta esperada:
```json
{"status":"ok","service":"executors","env":"dev"}
```

## PowerShell (exemplo)

```powershell
$env:CRM_API_BASE="http://localhost:8000"
$env:CORE_API_BASE="http://localhost:8001"
$env:CRM_SERVICE_TOKEN="<token>"
$env:CORE_SERVICE_TOKEN="<token>"
uvicorn app.main:app --reload --port 8010 --app-dir backend-executors
```

## CLI stub (runner)

```bash
python -m app.runners.whatsapp --job-id 123
```

Se `--job-id` não for informado, o comando falha com uma mensagem amigável.
