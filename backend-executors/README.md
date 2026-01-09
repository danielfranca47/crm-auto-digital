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

> Para usar o runner contra o CRM, defina `CRM_SERVICE_TOKEN` no `.env` (ou variáveis de ambiente) para autenticar os endpoints internos.

## Variáveis de ambiente LLM

Para a decisão via IA, o executor usa:

- `LLM_API_BASE`: base URL do provedor (ex.: `https://api.openai.com/v1/responses`).
- `LLM_API_KEY`: token de autenticação. Se vazio, usa stub local.
- `LLM_MODEL`: identificador do modelo (ex.: `gpt-4o-mini`).
- `LLM_TIMEOUT_SECONDS`: timeout em segundos (default 20).

### Modo stub (sem key)

Se `LLM_API_KEY` não estiver configurado, o serviço retorna uma resposta JSON fixa e válida
para permitir testes end-to-end do pipeline.
