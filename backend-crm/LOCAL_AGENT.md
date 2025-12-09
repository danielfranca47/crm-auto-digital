# Arquitetura do Agente Local

Este documento resume as principais mudanças introduzidas para suportar o Agente Local responsável por executar as automações (WhatsApp, e futuramente e-mail, etc.) diretamente na máquina do usuário.

## Migração do banco e modelo de dados

As tabelas novas são criadas automaticamente sempre que a API inicializa, pois `backend/app.py` chama `init_db()` e ele executa `ensure_jobs_tables()`. Em outras palavras, subir o backend já garante que `agents` e `jobs` existam — não é necessário rodar nenhuma etapa manual em ambientes novos.

Se preferir aplicar a migração manualmente (por exemplo, antes de subir uma instância em produção), siga os passos abaixo:

1. Faça um backup opcional do banco atual: `cp backend/database/crm.db backend/database/crm.backup-$(date +%Y%m%d%H%M).db`
2. Rode o script SQL diretamente com o SQLite CLI: `sqlite3 backend/database/crm.db < backend/migrations/001_create_agents_jobs.sql`

Novas tabelas criadas no SQLite:

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

### Provisionamento e ciclo de vida do agente

| Método | Caminho completo | Descrição |
|--------|------------------|-----------|
| `POST` | `/api/agents/provision` | (Requer bearer token do core) Gera um par `(agent_id, agent_token)` vinculado ao usuário autenticado. |
| `POST` | `/api/agents/register` | Registro/heartbeat de um agente previamente provisionado. Atualiza status, capabilities e version. |
| `GET` | `/api/agents/next-job` | Busca do próximo job. Usa query `agent_id`, `token` e `types=whatsapp_send`. Retorna jobs apenas do mesmo `user_id` do agente. |
| `POST` | `/api/agents/report` | Reporte de conclusão/erro de um job. Valida `agent_id`+`token` e mantém o `user_id` do agente. |
| `GET` | `/api/agents/overview` | Lista agentes do usuário autenticado (token não é retornado) e contadores gerais. |
| `GET` | `/api/agents/jobs/summary` | Contadores específicos de jobs (pendentes, concluídos/erro no dia) filtrados por `user_id`. |

`POST /api/agents/provision`
```json
{
  "name": "Agente do Comercial"
}
```
Resposta (exemplo):
```json
{
  "agent_id": "2f3d...",
  "agent_token": "p5b...",
  "user_id": 123,
  "status": "offline"
}
```

Use `agent_id` e `agent_token` no `.env` do projeto `agent-local/` e siga com o registro:

`POST /api/agents/register`
```json
{
  "agent_id": "2f3d...",
  "token": "p5b...",
  "name": "Notebook Comercial",
  "capabilities": ["whatsapp_send"],
  "version": "0.1.0"
}
```

`GET /api/agents/next-job?agent_id=2f3d...&token=p5b...&types=whatsapp_send`

- Retorna `{ "job": { ... } }` quando há pendências ou `{ "job": null }` se a fila estiver vazia.

`POST /api/agents/report`
```json
{
  "agent_id": "2f3d...",
  "token": "p5b...",
  "job_id": 42,
  "status": "completed",
  "result": { "status": "sent", "notes": "ok" }
}
```

> Importante: o `agent_token` só é retornado no momento do provisionamento. Listagens como `/api/agents/overview` escondem o token para evitar vazamentos.

### Fluxo de prospecção (frontend)

- `POST /api/prospeccao/whatsapp/enqueue`
  Recebe `{ "lead_ids": [1,2,3] }` e cria jobs `whatsapp_send`.
- `GET /api/prospeccao/whatsapp/queue?limit=25`
  Lista pendências diretamente da tabela `jobs`.
- `GET /api/prospeccao/whatsapp/recent?since_secs=180`
  Retorna jobs finalizados recentemente (status `completed` ou `failed`).
- `GET /api/prospeccao/whatsapp/summary`
  Wrapper para os contadores da fila (`jobs_service.get_whatsapp_summary`).

### Endpoint rápido para testes manuais

- `POST /api/agents/jobs/manual-whatsapp`
  - **Payload mínimo:**
    ```json
    {
      "phone": "+5511999999999",
      "message": "Mensagem de teste enviada pelo agente local"
    }
    ```
  - Campos opcionais `lead_id` e `message_id` podem ser enviados para relacionar o job a um lead ou template salvo.
  - O backend responde com `{ "ok": true, "job": { ... } }`; o job fica imediatamente disponível para agentes autorizados a processar `whatsapp_send`.

## Fluxo end-to-end

1. Usuário seleciona leads no CRM e aciona `POST /api/prospeccao/whatsapp/enqueue`.
2. O backend cria registros em `jobs` com `type=whatsapp_send` e armazena o payload necessário (telefone, mensagem, etc.).
3. O Agente Local chama `/api/agents/next-job`, recebe o job pendente e executa a automação no Chrome local via Selenium.
4. Ao concluir, o agente reporta o resultado em `/api/agents/report` (`completed` ou `failed`).
5. O backend atualiza o status do job, registra logs em `prospection_logs` e move o lead de estágio quando apropriado.
6. O frontend exibe o progresso utilizando `overview`, `queue` e `recent`, informando o usuário sobre a atuação do agente local.

## Situação do worker antigo

- As rotas históricas que iniciavam/pausavam o worker backend (por exemplo `POST /api/whatsapp/worker/start`, `POST /api/whatsapp/worker/stop`, `GET /api/whatsapp/worker/status`, `GET /api/whatsapp/worker/state` e os aliases em `/api/whatsapp/worker/*` e `/api/whatsapp/worker`) agora retornam respostas estáticas indicando **"Worker desativado. Utilize o Agente Local"**.
- O frontend herdado continua podendo chamar essas rotas, mas apenas receberá o aviso acima; nenhuma automação Selenium é disparada no servidor.
- Qualquer fluxo de envio automático deve, portanto, utilizar a fila de jobs (`/api/prospeccao/whatsapp/enqueue` ou `/api/agents/jobs/manual-whatsapp`) para que o Agente Local assuma a execução.

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
