# Backend CRM

Este serviço agora utiliza exclusivamente o backend-core para autenticação. Cada chamada privada deve enviar `Authorization: Bearer <token_do_core>` com um token obtido no backend-core (`CORE_API_BASE`). Configure o `.env` com `CORE_API_BASE` apontando para a URL do core.

Principais mudanças:
- Dependência de autenticação via `require_crm_access`, que consulta `/users/me` e `/me/entitlements` no backend-core.
- Coluna `user_id` adicionada às tabelas principais (leads, jobs, prospection_logs, agents) para isolar dados por usuário.
- Todas as rotas privadas de leads, prospecção, agentes e pesquisa exigem bearer token, validam assinatura CRM ativa e filtram dados por `user_id`.
- Leads e fluxos de prospecção agora são multiusuário, sempre gravando e consultando dados com `user_id` derivado do backend-core.

## Webhook WhatsApp inbound (ORION)

- Endpoint: `POST /webhooks/whatsapp/inbound`
- Segurança: header `X-Webhook-Secret` deve casar com `CRM_WEBHOOK_SECRET`; o CRM resolve o dono via core usando `CORE_SERVICE_TOKEN`.
- Idempotência: `inbound_events` evita duplicar por `(provider, instance_id, external_event_id)`.
- Efeitos: cria/acha lead por telefone, registra mensagem (model=`inbound`) e cria job `whatsapp.inbound.n8n`.

## Validação de assinatura do produto CRM

- O backend-CRM usa `CORE_API_BASE` (ex.: `http://localhost:8000`) para consultar o backend-core com o mesmo Bearer token da requisição recebida.
- A dependência `require_crm_access` chama o endpoint autenticado do core `GET /me/entitlements` e verifica se existe uma assinatura **ativa** para o produto `crm`.
- Se não houver assinatura ativa para `crm`, o CRM retorna `403 Assinatura do produto CRM ausente ou inativa` antes de executar qualquer rota privada.

## Rate limits por plano (janela diária UTC)

- Fonte da verdade: `GET /me/entitlements` do backend-core (campo `limits`).
- Chaves usadas neste MVP:
  - `max_prospects_daily` → consumo por prospect encontrado/enriquecido na automação de pesquisa (`/api/pesquisa/executar`), contando o número de itens retornados (API ou fallback via agent-local), mesmo sem criação de jobs.
  - `max_whatsapp_send_daily` → `whatsapp.send.local` (inclui aliases `whatsapp_send`).
  - `max_maps_search_daily` → `maps.search.local` (inclui alias `maps_search_fallback`).
  - `max_maps_enrich_daily` → `maps.enrich.local` (inclui alias `maps_enrich_fallback`).
- Contagem: diário (UTC) por `user_id`. Para WhatsApp/Maps jobs, conta todos os jobs do tipo canônico, independentemente do status. Para prospecção, consome **1 unidade por prospect** retornado na pesquisa (API ou fallback), mesmo quando não há job. A rota `/api/pesquisa/executar` faz pré-checagem do saldo antes de iniciar a busca (bloqueia se `quantity` for maior que o saldo disponível) e reserva o saldo para evitar corrida; após a busca, ajusta para o número real de itens retornados.
- Limite ausente/`null` = ilimitado (para não travar ambientes de dev). Limite 0 bloqueia qualquer nova criação/execução.
- Mensagem de bloqueio: `429 Limite diário atingido para <tipo>. Atualize seu plano.`
- Seeds atuais do backend-core:
  - `crm_free`: `max_whatsapp_send_daily=15`, `max_prospects_daily=15`, `max_maps_search_daily=10`, `max_maps_enrich_daily=20`.
  - `crm_basic`: `max_whatsapp_send_daily=30`, `max_prospects_daily=30`, `max_maps_search_daily=null`, `max_maps_enrich_daily=200`.
  - `crm_pro`: `max_whatsapp_send_daily=100`, `max_prospects_daily=100`, limites de Maps ilimitados (`null`).

### Checklist rápido (Swagger/curl na porta 8000)

1. Gere um token no core e confirme os limites: `curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/me/entitlements`.
2. Valide prospecção (plano `crm_free` com `max_prospects_daily=15`):
   ```bash
   curl -X POST http://localhost:8000/api/pesquisa/executar \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"country":"Brasil","state":"SP","city":"São Paulo","sector":"padaria","quantity":16}'
   ```
   Deve retornar `429` **antes de criar jobs ou abrir navegador** quando `quantity` exceder o saldo diário. No plano `crm_free`, a resposta deve ser `"Limite diário atingido para prospecção. Atualize seu plano."` e a tabela `jobs` não deve receber `maps.search.local` para essa chamada. Com `quantity` menor/igual ao saldo, a pesquisa completa normalmente, consumindo 1 unidade por prospect retornado (via API ou fallback agent-local). Exemplo: rode `quantity=5` três vezes (saldo 15) e a 4ª chamada com `quantity=5` deve retornar `429` já na pré-checagem.
3. Enfileire WhatsApp até atingir o limite diário (ex.: `crm_free` → 15 jobs):
   ```bash
   curl -X POST http://localhost:8000/api/prospeccao/whatsapp/enqueue \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"lead_ids":[1],"message":"Teste"}'
   ```
   Repita até a resposta ser `429` com `"Limite diário atingido para whatsapp.send.local. Atualize seu plano."` e sem novo `job_id`.
4. Manual WhatsApp (também conta para o limite):
   ```bash
   curl -X POST http://localhost:8000/api/agents/jobs/manual-whatsapp \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"phone":"+5511999999999","message":"Ping"}'
   ```
5. Maps: qualquer criação de `maps.search.local`/`maps.enrich.local` via automações/agent_jobs utiliza o contador diário de jobs; ao exceder, espere `429` com o tipo correspondente. O limite de prospecção (`max_prospects_daily`) continua sendo consumido 1× por prospect retornado na pesquisa, mesmo quando o fluxo usa API sem jobs.

Fluxo mínimo de teste (usando o core):

```bash
# 1) Registrar e logar no core
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"teste@example.com","password":"senha123"}'

TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"teste@example.com","password":"senha123"}' | jq -r .access_token)

# 2) Tentar acessar o CRM sem assinatura (deve retornar 403)
curl -i http://localhost:8010/api/leads \
  -H "Authorization: Bearer $TOKEN"

# 3) Criar assinatura de CRM no core
curl -X POST http://localhost:8000/subscriptions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"product_code":"crm","plan_code":"crm_basic"}'

# 4) Validar entitlements consolidados no core
curl http://localhost:8000/me/entitlements \
  -H "Authorization: Bearer $TOKEN"

# 5) Acessar o CRM agora autorizado
curl http://localhost:8010/api/leads \
  -H "Authorization: Bearer $TOKEN"
```

## Limites MVP (max_leads e max_agents_local)

- Fonte: `limits.max_leads` e `limits.max_agents_local` retornados pelo backend-core em `/me/entitlements`.
- Janela: total absoluto por usuário (não é diário). Valor `null` = ilimitado; valor `0` bloqueia novas criações.
- Respostas de bloqueio: `429`
  - Leads: `"Limite atingido de leads armazenados. Atualize seu plano."`
  - Agentes: `"Limite atingido de agentes locais. Atualize seu plano."`

### Onde bloqueia

- `POST /api/leads` (criação manual de lead) – aplica `max_leads` antes do INSERT.
- `POST /api/assistente-ia/processar` com `create_cards=true` – cada linha que criaria um lead novo respeita `max_leads`; quando não houver slots, a linha é pulada e adiciona erro `"Limite de leads atingido"` (updates continuam funcionando).
- `POST /api/agents/provision` – aplica `max_agents_local` antes de criar um novo agente.
- `POST /api/assistente-ia/messages/upsert` **não consome** max_copy_generation_monthly e também não conta para max_leads (apenas edita mensagens existentes).

### Como testar (PowerShell)

1) **Preparar token e plano**
   - Use um usuário com plano free (ex.: `max_leads=3`, `max_agents_local=1`, `max_copy_generation_monthly=3`).
   - Exemplo para ler entitlements: `Invoke-RestMethod -Headers @{Authorization="Bearer $TOKEN"} -Uri http://localhost:8000/me/entitlements`.

2) **Forçar limite de leads via API manual**
   ```powershell
   1..3 | ForEach-Object {
     Invoke-RestMethod -Method Post -Uri http://localhost:8010/api/leads -Headers @{Authorization="Bearer $TOKEN"} -ContentType 'application/json' -Body (@{companyName="Lead $_"; contactName="Pessoa $_"} | ConvertTo-Json)
   }
   # 4º lead deve falhar com 429
   Invoke-RestMethod -Method Post -Uri http://localhost:8010/api/leads -Headers @{Authorization="Bearer $TOKEN"} -ContentType 'application/json' -Body (@{companyName="Lead 4"; contactName="Pessoa 4"} | ConvertTo-Json)
   ```

3) **Validar contagem no SQLite (sem sqlite3 CLI)**
   ```powershell
   python - <<'PY'
import os
import sqlite3

conn = sqlite3.connect('crm.db')
conn.row_factory = sqlite3.Row
uid_env = os.environ.get('USER_ID')
uid = int(uid_env) if uid_env else None
for table in ['leads','agents']:
    row = conn.execute(f"SELECT COUNT(*) AS total FROM {table} WHERE user_id = ?", (uid,)).fetchone()
    print(table, row['total'])
conn.close()
PY
   ```
   (Defina `$env:USER_ID` com o id do usuário retornado pelo CRM/core.)

4) **Assistente IA batendo no teto de leads e copiando**
   - Configure planilha com 5 linhas e `channels` = `['email','whatsapp']`.
   - Com `max_leads=3` e apenas 1 lead existente, a quarta linha em diante será pulada com erro de limite; `stats.created` para em 2 novos leads e as demais permanecem em `errors`.
   - Quando `generate_copys=true`, respeita também `max_copy_generation_monthly` (saldo calculado antes e consumido por mensagem gerada). Se o saldo zerar no meio do lote, a resposta vem `quota_exceeded=true`, `stopped_reason="copy_quota_exceeded"` e `remaining_copy_quota` informado.

5) **Limite de agentes locais**
   ```powershell
   # 1º provisionamento (ok)
   Invoke-RestMethod -Method Post -Uri http://localhost:8010/api/agents/provision -Headers @{Authorization="Bearer $TOKEN"} -ContentType 'application/json' -Body (@{name='Agent 1'} | ConvertTo-Json)
   # 2º deve falhar com 429
   Invoke-RestMethod -Method Post -Uri http://localhost:8010/api/agents/provision -Headers @{Authorization="Bearer $TOKEN"} -ContentType 'application/json' -Body (@{name='Agent 2'} | ConvertTo-Json)
   ```

### Script rápido de regressão (Python)

Execute para validar helpers de contagem sem subir a API (assume DB local com tabelas padrão e um usuário `uid` existente):

```bash
python - <<'PY'
from services import rate_limit_service
uid = 1
print('leads:', rate_limit_service.get_total_leads(user_id=uid))
print('agents:', rate_limit_service.get_total_agents(user_id=uid))
print('remaining leads:', rate_limit_service.get_remaining_lead_slots(user_id=uid, entitlements={'limits': {'max_leads': 5}}))
try:
    rate_limit_service.ensure_max_leads(user_id=uid, entitlements={'limits': {'max_leads': 0}})
except Exception as exc:
    print('expected block for max_leads=0 ->', exc)
PY
```

## Provisionamento do agente local (multiusuário)

1. Autentique-se no backend-core e obtenha um `access_token`.
2. Chame `POST /api/agents/provision` no backend-CRM com `Authorization: Bearer <token_do_core>` para gerar um par `(agent_id, agent_token)` vinculado ao seu usuário.
3. Configure o `.env` do projeto `agent-local/` com os valores retornados (`AGENT_ID`, `AGENT_TOKEN`).
4. O agente local continuará usando `/api/agents/register`, `/api/agents/next-job` e `/api/agents/report`, mas agora o CRM valida o par `(agent_id, agent_token)` e entrega jobs apenas do respectivo `user_id`.
5. Para gestão operacional, use as rotas autenticadas do CRM (todas exigem assinatura ativa do produto `crm`):
   - `GET /api/agents` — lista apenas os agentes do usuário, com `online` calculado a partir de `last_seen_at`.
   - `POST /api/agents/{agent_id}/revoke` — marca `revoked_at` e passa a recusar `register/next-job/report` com o token antigo.
   - `POST /api/agents/{agent_id}/reprovision` — gera um novo `agent_token` (o antigo deixa de funcionar) e retorna instruções para atualizar o `.env` do agent-local.

### Convenção de job types (multi-canal + executor)

- Formato canônico: `<canal>.<ação>.<executor>`, onde `executor ∈ {local, n8n}`.
- Tipos canônicos atuais (agent-local):
  - `whatsapp.send.local`
  - `maps.search.local`
  - `maps.enrich.local`
- Aliases legados aceitos por normalização (para não quebrar jobs já gravados):
  - `whatsapp_send` → `whatsapp.send.local`
  - `maps_search_fallback` → `maps.search.local`
  - `maps_enrich_fallback` → `maps.enrich.local`
- Exemplos de query param `types` no `/api/agents/next-job`:
  - `types=whatsapp.send.local`
  - `types=whatsapp.send.local,maps.search.local,maps.enrich.local`
  - Aliases continuam válidos, mas o backend sempre responde com o tipo canônico.

### Convenção de job types (multi-canal + executor)

- Formato canônico: `<canal>.<ação>.<executor>`, onde `executor ∈ {local, n8n}`.
- Tipos canônicos atuais (agent-local):
  - `whatsapp.send.local`
  - `maps.search.local`
  - `maps.enrich.local`
- Aliases legados aceitos por normalização (para não quebrar jobs já gravados):
  - `whatsapp_send` → `whatsapp.send.local`
  - `maps_search_fallback` → `maps.search.local`
  - `maps_enrich_fallback` → `maps.enrich.local`
- Exemplos de query param `types` no `/api/agents/next-job`:
  - `types=whatsapp.send.local`
  - `types=whatsapp.send.local,maps.search.local,maps.enrich.local`
  - Aliases continuam válidos, mas o backend sempre responde com o tipo canônico.

### Checklist de testes manuais (agente local)

Sequência completa sugerida (via curl ou Swagger) para validar provisionamento, heartbeat, fila, revogação e reprovisionamento:

1. **Provisionar**
   ```bash
   curl -X POST http://localhost:8010/api/agents/provision \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"name":"Agent QA"}'
   ```
   Guarde `agent_id` e `agent_token`.

2. **Registrar (heartbeat inicial)**
   ```bash
   curl -X POST http://localhost:8010/api/agents/register \
     -H "Content-Type: application/json" \
     -d '{"agent_id":"<AGENT_ID>","token":"<AGENT_TOKEN>","capabilities":["whatsapp.send.local","maps.search.local","maps.enrich.local"],"version":"qa"}'
   ```

3. **next-job com fila vazia**
   ```bash
   curl "http://localhost:8010/api/agents/next-job?agent_id=<AGENT_ID>&token=<AGENT_TOKEN>&types=whatsapp.send.local"
   curl "http://localhost:8010/api/agents/next-job?agent_id=<AGENT_ID>&token=<AGENT_TOKEN>&types=whatsapp.send.local"
   ```
   Deve retornar `{ "job": null }` quando não há pendências.

4. **Criar job manual**
   ```bash
   curl -X POST http://localhost:8010/api/agents/jobs/manual-whatsapp \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"phone":"+5511999999999","message":"Mensagem de teste"}'
   ```

5. **next-job com job pendente**
   ```bash
   curl "http://localhost:8010/api/agents/next-job?agent_id=<AGENT_ID>&token=<AGENT_TOKEN>&types=whatsapp.send.local"
   curl "http://localhost:8010/api/agents/next-job?agent_id=<AGENT_ID>&token=<AGENT_TOKEN>&types=whatsapp.send.local"
   ```
   Deve retornar o job criado no passo anterior. Confirme que o payload inclui `assigned_agent_id` igual a `<AGENT_ID>` e `type=whatsapp.send.local` (o mesmo valor salvo no banco ao fazer o claim; aliases são normalizados).

5.1 **Concorrência por canal (apenas 1 in_progress por canal/user)**
   - Crie um **segundo** job manual de WhatsApp para o mesmo usuário (repita o passo 4).
   - Em dois terminais (ou dois agentes registrados com o mesmo `agent_id/token`), chame `/api/agents/next-job`:
     - O primeiro claimará o job WhatsApp e ficará `in_progress`.
     - O segundo deve receber `{ "job": null }` enquanto houver outro job WhatsApp `in_progress` para o mesmo usuário.
   - Se você criar um job de Maps (`maps.search.local`) e outro de WhatsApp, dois agentes podem receber ambos simultaneamente (canais diferentes).
   - Após o job WhatsApp ser reportado como `completed`/`failed`, o próximo `/next-job` deve entregar o próximo WhatsApp pendente.

6. **report (completed)**
   ```bash
   curl -X POST http://localhost:8010/api/agents/report \
     -H "Content-Type: application/json" \
     -d '{"agent_id":"<AGENT_ID>","token":"<AGENT_TOKEN>","job_id":<JOB_ID>,"status":"completed","result":{"ok":true}}'
   ```
   A resposta deve incluir `status":"completed"` e um objeto `job` com `status=completed` e `completed_at` preenchido. Se o job já tiver sido atualizado ou não pertencer ao agente/usuário, o endpoint retornará erro.

7. **Listar agentes e checar online/offline**
   ```bash
   curl http://localhost:8010/api/agents?seconds=90 \
     -H "Authorization: Bearer $TOKEN"
   ```
   O campo `online` reflete `last_seen_at`; nenhum token é retornado.

8. **Revogar agente**
   ```bash
   curl -X POST http://localhost:8010/api/agents/<AGENT_ID>/revoke \
     -H "Authorization: Bearer $TOKEN"
   ```

9. **Falha esperada após revogação**
   ```bash
   curl -i "http://localhost:8010/api/agents/next-job?agent_id=<AGENT_ID>&token=<AGENT_TOKEN>"
   ```
   Deve responder `403 Agent revoked` (mesma validação vale para `register` e `report`).

10. **Reprovisionar (rotacionar token)**
    ```bash
    curl -X POST http://localhost:8010/api/agents/<AGENT_ID>/reprovision \
      -H "Authorization: Bearer $TOKEN"
    ```
    Atualize o `.env` do agent-local com o novo `agent_token` retornado (mantendo o `AGENT_ID`).

11. **Registrar/next-job novamente (sucesso esperado)**
    Repita os passos 2 e 3 com o novo token; o agente volta a consumir jobs normalmente.

### Fila resiliente (scheduled_at, TTL e backoff)

- TTL de lease: **10 minutos**. Jobs `in_progress` com `started_at` mais antigo voltam para `pending` (limpando `assigned_agent_id`/`started_at`) ou viram `failed` definitivo se `attempts >= 3`.
- `scheduled_at` é respeitado em `/api/agents/next-job`: jobs futuros não são entregues antes da hora.
- Backoff de falhas: tentativa 1 → +60s, tentativa 2 → +180s, tentativa 3 → `failed` definitivo. O job volta para `pending` com `scheduled_at` ajustado.
- Reports atrasados são rejeitados se o job já foi reentregue (status diferente de `in_progress` ou `assigned_agent_id` divergente).

Checklist rápido (use a porta em que o CRM estiver rodando, ex.: `http://localhost:<PORT>`):

1. **scheduled_at futuro bloqueado**
   - Criar job com `scheduled_at` no futuro.
   - Chamar `/api/agents/next-job` com o agente autorizado → deve retornar `{"job": null}` até o horário chegar.
2. **TTL requeue**
   - Claimar um job e editar `started_at` no banco para `agora - 11 minutos`.
   - Nova chamada a `/api/agents/next-job` deve reentregar o job (status volta para `pending`).
3. **Report atrasado rejeitado**
   - Após o passo anterior, deixe outro agente claimar o mesmo job.
   - O agente antigo ao tentar `report` deve receber `409` informando requeue/ownership divergente.
4. **Backoff e max attempts**
   - Reportar `failed` duas vezes: o job volta para `pending` com `scheduled_at` futuro (+60s, depois +180s).
   - Na terceira falha, o status permanece `failed` definitivo e o job deixa de ser reentregue.

### Sanity rápido (Swagger/curl na porta 8000)

1. **Claim**
   - Chame `POST http://localhost:8000/api/agents/next-job` com `agent_id`, `token` e `types` válidos.
   - O job retornado deve estar com `status: in_progress` e `assigned_agent_id` preenchido.
2. **Report completed**
   - Chame `POST http://localhost:8000/api/agents/report` informando `status=completed` e o `job_id` do passo anterior.
   - A resposta deve trazer o job atualizado com `status: completed` e `completed_at` preenchido.
3. **Fila vazia**
   - Rechame `POST http://localhost:8000/api/agents/next-job` com os mesmos parâmetros.
   - O resultado deve ser `{"job": null}` enquanto não houver novos jobs pendentes.

## Manual Testing Guide — Multiusuário (Leads, Prospecção, Assistente IA)

### 0) Pré-requisitos

- Suba o **backend-core** e o **backend-crm** (ambos carregam `.env` automaticamente). O CRM precisa da variável `CORE_API_BASE` apontando para a URL do core (ex.: `http://localhost:8000`).
- Crie dois usuários no core (ex.: `userA@example.com` e `userB@example.com`) via `POST /auth/register` e obtenha tokens via `POST /auth/login`. Anote `token_A` e `token_B`.
- Todas as rotas privadas do CRM exigem `Authorization: Bearer <token>`. Sempre envie o token do usuário que está testando.
- Tokens **sem assinatura ativa do produto `crm`** retornam `403` em qualquer rota privada do CRM. Crie a assinatura via `POST /subscriptions` no core e valide com `GET /me/entitlements` (veja o fluxo mínimo acima).

### 1) Testes de Prospecção (Etapa 4.3 — prospecção + logs + jobs)

1. **Criar (ou localizar) um lead do usuário autenticado**
   ```bash
   curl -X POST http://localhost:8010/api/leads \
     -H "Authorization: Bearer $token_A" \
     -H "Content-Type: application/json" \
     -d '{
           "companyName": "Loja A",
           "contactName": "Ana",
           "phone": "+55 11 99999-0000",
           "email": "contato@lojaa.com",
           "category": "novo"
         }'
   ```
   A resposta traz o `id` do lead (use `lead_id_A`).

2. **Registrar uma mensagem/log de prospecção**
   ```bash
   curl -X POST http://localhost:8010/api/prospeccao/log \
     -H "Authorization: Bearer $token_A" \
     -H "Content-Type: application/json" \
     -d '{
           "lead_id": LEAD_ID_A,
           "action": "queued",
           "channel": "whatsapp",
           "message_id": null,
           "notes": "Primeiro contato"
         }'
   ```
   O log é salvo em `prospection_logs` já com `user_id = token_A`.

3. **Enfileirar mensagem para WhatsApp (cria job + log)**
   ```bash
   curl -X POST http://localhost:8010/api/prospeccao/whatsapp/enqueue \
     -H "Authorization: Bearer $token_A" \
     -H "Content-Type: application/json" \
     -d '{
           "lead_ids": [LEAD_ID_A],
           "message": "Olá! Tudo bem?"
         }'
   ```
   - Cria (ou reutiliza) uma mensagem e um job `whatsapp.send.local` na tabela `jobs`, ambos com `user_id` do A. Aliases legados (`whatsapp_send`) continuam aceitos via normalização.
   - Também grava log `queued` em `prospection_logs` com o mesmo `user_id`.

4. **Validar escopo multiusuário**
   - Liste a fila do próprio usuário: `GET /api/prospeccao/whatsapp/queue` com `token_A` (retorna só jobs do A).
   - Consulte o resumo/últimos envios: `GET /api/prospeccao/whatsapp/recent` e `GET /api/prospeccao/whatsapp/summary` com `token_A`.
   - Tente registrar log ou enfileirar para `LEAD_ID_A` usando `token_B`: `POST /api/prospeccao/log` ou `/whatsapp/enqueue` deve responder `404` (lead não encontrado), garantindo isolamento.

5. **Listar/inspecionar logs (leitura por usuário)**
   - Não há rota dedicada de listagem de `prospection_logs`; use `GET /api/prospeccao/whatsapp/recent` para ver movimentos de jobs ou consulte diretamente o banco se precisar auditar.

### 2) Testes do Agent + WhatsApp Job

1. **Provisionar agente vinculado ao usuário**
   ```bash
   curl -X POST http://localhost:8010/api/agents/provision \
     -H "Authorization: Bearer $token_A" \
     -H "Content-Type: application/json" \
     -d '{"name": "Agente Local A"}'
   ```
   Copie `agent_id` e `agent_token` da resposta.

2. **Configurar e iniciar o `agent-local`**
   - No projeto `agent-local/`, defina no `.env`: `AGENT_ID=<agent_id>` e `AGENT_TOKEN=<agent_token>`.
   - Garanta que `CRM_API_BASE` aponte para o backend-CRM (ex.: `http://localhost:8010`).
   - Inicie o agente (ex.: `python main.py` no diretório `agent-local/`).

3. **Consumir jobs e reportar status**
   - O agente chama `GET /api/agents/next-job?agent_id=...&token=...&types=whatsapp.send.local` (aliases como `whatsapp_send` continuam válidos) e receberá apenas jobs do seu `user_id`.
   - Após processar, o agente chama `POST /api/agents/report` com `status=completed` ou `failed`; o CRM atualiza `jobs` e grava logs em `prospection_logs` com o mesmo `user_id`.
   - Monitore `GET /api/prospeccao/whatsapp/recent` ou `GET /api/agents/jobs/summary` com `token_A` para ver o resultado.

4. **Isolamento entre usuários**
   - Repetir o fluxo com `token_B` gera um novo `agent_id`/`agent_token` e o agente só consumirá jobs do B.

5. **Listar status / heartbeat**
   - `GET /api/agents?seconds=90` com `token_A` retorna apenas agentes do usuário, sem expor token. O campo `online` fica `true` se `last_seen_at` estiver dentro da janela informada.
   - O `last_seen_at` é atualizado em `register`, `next-job` e `report`.

6. **Revogar credencial**
   - `curl -X POST http://localhost:8010/api/agents/{agent_id}/revoke -H "Authorization: Bearer $token_A"`
   - O agente local existente passará a falhar no próximo `register/next-job/report` com erro `403 Agent revoked`.

7. **Reprovisionar (rotacionar token)**
   - `curl -X POST http://localhost:8010/api/agents/{agent_id}/reprovision -H "Authorization: Bearer $token_A"`
   - A resposta traz apenas uma vez o novo `agent_token` e um texto curto de instrução. Atualize `AGENT_TOKEN` (mantendo o mesmo `AGENT_ID`) no `.env` do agent-local e reinicie o processo; o agente volta a consumir jobs normalmente.

### 3) Testes do Assistente IA (Etapa 4.3 — preview/import dedup)

1. **Gerar preview de um upload**
   ```bash
   curl -X POST http://localhost:8010/api/assistente-ia/preview \
     -H "Authorization: Bearer $token_A" \
     -H "Content-Type: application/json" \
     -d '{
           "upload_id": "meu_arquivo",   
           "overwrite": "update"         
         }'
   ```
   O arquivo `data/uploads/ai/meu_arquivo.xlsx` (ou `.csv`) deve existir. O preview deduplica apenas contra leads do `user_id` do token.

2. **Importar/processar leads do assistente**
   ```bash
   curl -X POST http://localhost:8010/api/assistente-ia/processar \
     -H "Authorization: Bearer $token_A" \
     -H "Content-Type: application/json" \
     -d '{
           "upload_id": "meu_arquivo",
           "create_cards": true,
           "generate_copys": false,
           "channels": ["whatsapp"],
           "overwrite": "update"
         }'
   ```
   - Novos leads são criados com `user_id` do token; duplicatas seguem a regra de `overwrite` somente dentro do espaço do usuário.
   - Mensagens copiadas/geradas também ficam associadas ao `user_id` correto.

3. **Validar isolamento**
   - Troque para `token_B` e repita os dois passos. O preview não deve mostrar leads do A e o import cria registros separados.

#### Limite mensal de geração de copys (POST /api/assistente-ia/processar)

- Chave de entitlement: `limits.max_copy_generation_monthly` (None = ilimitado, `0` = sempre bloqueia). Contagem mensal UTC em `limit_usage_monthly.month_utc` (formato `YYYY-MM`). Unidade = 1 mensagem gerada automaticamente por lead × canal; o endpoint manual `/api/assistente-ia/messages/upsert` **não** consome quota.
- Comportamentos esperados no processar:
  - Se `generate_copys=false` ou `channels=[]`: não consome quota.
  - Se o saldo mensal é 0 antes de iniciar: HTTP 429 com `"Limite mensal atingido para geração de copys. Atualize seu plano."`.
  - Se o saldo acaba no meio do lote: responde 200 com geração parcial, `quota_exceeded=true`, `stopped_reason="copy_quota_exceeded"` e `remaining_copy_quota` com o saldo final. Leads continuam sendo criados/atualizados sem chamar o LLM para novos textos.
- PowerShell para testar localmente (ajuste `upload_id` e token):
  ```powershell
  # 1) Upload do arquivo
  Invoke-RestMethod -Method Post -Uri http://localhost:8010/api/uploads `
    -Headers @{ Authorization = "Bearer $token_A" } `
    -Form @{ file = Get-Item '.\\leads.xlsx' }

  # 2) Processar pedindo 2 canais (consumo = leads * 2)
  Invoke-RestMethod -Method Post -Uri http://localhost:8010/api/assistente-ia/processar `
    -Headers @{ Authorization = "Bearer $token_A" } `
    -ContentType 'application/json' `
    -Body (@{
      upload_id     = "meu_arquivo"
      create_cards  = $true
      generate_copys = $true
      channels      = @("email","whatsapp")
      overwrite     = "update"
    } | ConvertTo-Json)

  # 3) Consultar saldo usado no mês (python embutido, sem depender do sqlite3 CLI)
  python - <<'PY'
import sqlite3
conn = sqlite3.connect('backend-crm/database/crm.db')
conn.row_factory = sqlite3.Row
rows = conn.execute("SELECT user_id, limit_key, month_utc, used FROM limit_usage_monthly").fetchall()
for r in rows:
    print(dict(r))
PY
  ```
- Para simular um limite baixo (ex.: 3/mês), use um usuário/plano com `max_copy_generation_monthly=3`, processe 2 leads com 2 canais (4 unidades) e valide:
  - Primeira chamada gera até esgotar o saldo (resposta 200 com `quota_exceeded=true`).
  - Nova chamada com saldo 0 retorna 429 com a mensagem de limite.

### 4) Observações e Troubleshooting

- **Se retornar 401**: verifique se está enviando `Authorization: Bearer <token>` e se `CORE_API_BASE` do CRM aponta para o core correto.
- **Se jobs ficarem pending**: confirme que o `agent-local` está rodando com `AGENT_ID/AGENT_TOKEN` do usuário certo e que ele aceita `whatsapp.send.local` (aliases legados ainda funcionam) em `types`.
- **Se uma rota de prospecção responder 404**: normalmente o `lead_id` pertence a outro usuário ou não existe; revise o token usado.
