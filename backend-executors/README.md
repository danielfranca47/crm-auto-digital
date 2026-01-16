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

## Worker de polling (5B.5.6)

Para rodar o worker contínuo (polling) que consome jobs WhatsApp automaticamente:

```bash
python -m app.workers.whatsapp_worker
```

### Variáveis de ambiente úteis

- `WHATSAPP_WORKER_TYPES` (default: `whatsapp.inbound.n8n`)
  - Lista separada por vírgula de tipos de job.
- `WHATSAPP_WORKER_MAX_JOBS` (opcional)
  - Finaliza após processar N jobs (útil para testes).
- `WHATSAPP_WORKER_MAX_RUNTIME_SECONDS` (opcional)
  - Finaliza após N segundos (útil para testes/caos).

### Observabilidade (logs)

Os logs incluem contexto mínimo por job: `job_id`, `lead_id`, `user_id`, `instance_id`, `provider`, `attempt`, `phase`.
Eventos principais: `job_found`, `job_claimed`, `decision_made`, `outbound_reserved`, `core_send_success`,
`mark_sent_success`, `job_retry_scheduled`, `job_failed_final`, `job_completed`.

### Simulação de falhas (exemplos)

- **Core fora do ar**: aponte `CORE_API_BASE` para uma porta inválida.
- **Token inválido**: defina `CORE_SERVICE_TOKEN` ou `CRM_SERVICE_TOKEN` incorreto.
- **Limitar execução**: use `WHATSAPP_WORKER_MAX_JOBS=1` para rodar só um job.

### Runner de validação (test_5b56_chaos.py)

O script `backend-executors/scripts/test_5b56_chaos.py` executa cenários de validação
com logs ao vivo do worker e resumo final em checklist.

Exemplos:

```bash
# Core indisponível (retry + backoff + failed)
CHAOS_SCENARIO=core_down MAX_RUNTIME_SECONDS=600 MAX_ATTEMPTS_WAIT=3 \
CRM_WEBHOOK_SECRET=... CRM_SERVICE_TOKEN=... CORE_SERVICE_TOKEN=... \
python backend-executors/scripts/test_5b56_chaos.py
```

```bash
# Token inválido no Core (falha definitiva)
CHAOS_SCENARIO=core_token_invalid CRM_WEBHOOK_SECRET=... CRM_SERVICE_TOKEN=... \
CORE_SERVICE_TOKEN=invalid python backend-executors/scripts/test_5b56_chaos.py
```

```bash
# Token inválido no CRM
CHAOS_SCENARIO=crm_token_invalid CRM_WEBHOOK_SECRET=... CRM_SERVICE_TOKEN=invalid \
python backend-executors/scripts/test_5b56_chaos.py
```

```bash
# Cenário crítico: mark-sent falha e depois recupera (sem reenvio ao Core)
CHAOS_SCENARIO=mark_sent_fail_then_recover MAX_RUNTIME_SECONDS=900 \
CRM_WEBHOOK_SECRET=... CRM_SERVICE_TOKEN=... CORE_SERVICE_TOKEN=... \
python backend-executors/scripts/test_5b56_chaos.py
```

## Variáveis de ambiente LLM

Para a decisão via IA, o executor usa:

- `LLM_API_BASE`: base URL do provedor (ex.: `https://api.openai.com/v1/responses`).
- `LLM_API_KEY`: token de autenticação. Se vazio, usa stub local.
- `LLM_MODEL`: identificador do modelo (ex.: `gpt-4o-mini`).
- `LLM_TIMEOUT_SECONDS`: timeout em segundos (default 20).

### Modo stub (sem key)

Se `LLM_API_KEY` não estiver configurado, o serviço retorna uma resposta JSON fixa e válida
para permitir testes end-to-end do pipeline.

## Onde configurar
backend-executors/.env

## Variáveis mínimas obrigatórias
Para OpenAI (exemplo mais comum hoje):
LLM_API_BASE=https://api.openai.com/v1/responses
LLM_API_KEY=sk-xxxxxxxxxxxxxxxx
LLM_MODEL=gpt-4o-mini
LLM_TIMEOUT_SECONDS=20


## O que cada uma faz (em linguagem leiga):

LLM_API_BASE
→ endereço do “servidor da IA”

LLM_API_KEY
→ sua chave secreta (se ficar vazia, o sistema entra em stub mode)

LLM_MODEL
→ qual “cérebro” a IA vai usar
(gpt-4o-mini é perfeito para esse caso: barato, rápido, bom em JSON)

LLM_TIMEOUT_SECONDS
→ quanto tempo o executor espera antes de desistir e cair no fallback
