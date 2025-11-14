# Arquitetura do Agente Local

Este documento resume as principais mudanças introduzidas para suportar o Agente Local responsável por executar as automações (WhatsApp, e futuramente e-mail, etc.) diretamente na máquina do usuário.

## Modelo de dados

Novas tabelas criadas no SQLite:

> Para executar a migração manualmente:
> `sqlite3 backend/database/crm.db < backend/migrations/001_create_agents_jobs.sql`

### `agents`

| Coluna | Tipo | Descrição |
| ------ | ---- | --------- |
| `id` | TEXT (PK) | Identificador do agente local |
| `name` | TEXT | Nome amigável opcional |
| `token` | TEXT | Token simples usado para autenticação |
| `status` | TEXT | `offline` \| `online` \| `disabled` |
| `capabilities` | TEXT (JSON) | Lista de tipos de job suportados |
| `version` | TEXT | Versão do agente informada no registro |
| `last_seen` | DATETIME | Último heartbeat do agente |
| `created_at`/`updated_at` | DATETIME | Auditoria |

### `jobs`

| Coluna | Tipo | Descrição |
| ------ | ---- | --------- |
| `id` | INTEGER (PK) | Identificador do job |
| `type` | TEXT | Tipo do job (ex.: `whatsapp_send`) |
| `payload` | TEXT (JSON) | Dados necessários para execução (lead, mensagem, etc.) |
| `status` | TEXT | `pending` \| `in_progress` \| `completed` \| `failed` |
| `priority` | INTEGER | Prioridade (maior primeiro) |
| `attempts` | INTEGER | Número de tentativas |
| `assigned_agent_id` | TEXT | Agente que assumiu o job |
| `scheduled_at` | DATETIME | Disponibilidade do job |
| `started_at`/`completed_at` | DATETIME | Auditoria de execução |
| `result` | TEXT (JSON) | Resultado bruto reportado pelo agente |
| `error` | TEXT | Mensagem de erro, quando houver |

## Endpoints REST

### Registro e ciclo de vida do agente

- `POST /api/agents/register`
  ```json
  {
    "agent_id": "notebook-01",
    "token": "segredo",
    "name": "Notebook Comercial",
    "capabilities": ["whatsapp_send"],
    "version": "0.1.0"
  }
  ```
- `GET /api/agents/next-job?agent_id=notebook-01&token=segredo&types=whatsapp_send`
  Retorna `{ "job": { ... } }` ou `{ "job": null }` quando não há itens.
- `POST /api/agents/report`
  ```json
  {
    "agent_id": "notebook-01",
    "token": "segredo",
    "job_id": 42,
    "status": "completed",
    "result": { "status": "sent", "notes": "ok" }
  }
  ```
- `GET /api/agents/overview`
  Retorna lista de agentes (com campo `online`) e resumo da fila.
- `GET /api/agents/jobs/summary`
  Retorna contadores (`pending`, `sent_today`, `failed_today`).

### Fluxo de prospecção (frontend)

- `POST /api/prospeccao/whatsapp/enqueue`
  Recebe `{ "lead_ids": [1,2,3] }` e cria jobs `whatsapp_send`.
- `GET /api/prospeccao/whatsapp/queue?limit=25`
  Lista pendências diretamente da tabela `jobs`.
- `GET /api/prospeccao/whatsapp/recent?since_secs=180`
  Retorna jobs finalizados recentemente (status `completed` ou `failed`).
- `GET /api/prospeccao/whatsapp/summary`
  Wrapper para os contadores da fila (`jobs_service.get_whatsapp_summary`).

## Fluxo end-to-end

1. Usuário seleciona leads no CRM e aciona `POST /api/prospeccao/whatsapp/enqueue`.
2. O backend cria registros em `jobs` com `type=whatsapp_send` e armazena o payload necessário (telefone, mensagem, etc.).
3. O Agente Local chama `/api/agents/next-job`, recebe o job pendente e executa a automação no Chrome local via Selenium.
4. Ao concluir, o agente reporta o resultado em `/api/agents/report` (`completed` ou `failed`).
5. O backend atualiza o status do job, registra logs em `prospection_logs` e move o lead de estágio quando apropriado.
6. O frontend exibe o progresso utilizando `overview`, `queue` e `recent`, informando o usuário sobre a atuação do agente local.

## Texto de referência para repositório separado

```
### Dependências
- Python 3.11+
- requests, selenium, webdriver-manager, python-dotenv

### Variáveis de ambiente
BACKEND_URL=http://localhost:8000
AGENT_ID=notebook-01
AGENT_TOKEN=seu-token
JOB_TYPES=whatsapp_send
POLL_INTERVAL=5
IDLE_INTERVAL=15
CHROME_USER_DATA=%USERPROFILE%\.agent-local\chrome-profile

### Endpoints principais
POST /api/agents/register
GET  /api/agents/next-job
POST /api/agents/report
GET  /api/prospeccao/whatsapp/queue
POST /api/prospeccao/whatsapp/enqueue

### Estrutura sugerida
agent/
  config.py
  jobs_client.py
  whatsapp_runner.py
main.py
requirements.txt
README.md
```

Use este texto como base para documentação externa ou onboarding de novos desenvolvedores.
