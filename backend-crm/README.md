# Backend CRM

Este serviço agora utiliza exclusivamente o backend-core para autenticação. Cada chamada privada deve enviar `Authorization: Bearer <token_do_core>` com um token obtido no backend-core (`CORE_API_BASE`). Configure o `.env` com `CORE_API_BASE` apontando para a URL do core.

Principais mudanças:
- Dependência de autenticação via `require_crm_access`, que consulta `/users/me` e `/me/entitlements` no backend-core.
- Coluna `user_id` adicionada às tabelas principais (leads, jobs, prospection_logs, agents) para isolar dados por usuário.
- Todas as rotas privadas de leads, prospecção, agentes e pesquisa exigem bearer token, validam assinatura CRM ativa e filtram dados por `user_id`.
- Leads e fluxos de prospecção agora são multiusuário, sempre gravando e consultando dados com `user_id` derivado do backend-core.

## Validação de assinatura do produto CRM

- O backend-CRM usa `CORE_API_BASE` (ex.: `http://localhost:8000`) para consultar o backend-core com o mesmo Bearer token da requisição recebida.
- A dependência `require_crm_access` chama o endpoint autenticado do core `GET /me/entitlements` e verifica se existe uma assinatura **ativa** para o produto `crm`.
- Se não houver assinatura ativa para `crm`, o CRM retorna `403 Assinatura do produto CRM ausente ou inativa` antes de executar qualquer rota privada.

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

## Provisionamento do agente local (multiusuário)

1. Autentique-se no backend-core e obtenha um `access_token`.
2. Chame `POST /api/agents/provision` no backend-CRM com `Authorization: Bearer <token_do_core>` para gerar um par `(agent_id, agent_token)` vinculado ao seu usuário.
3. Configure o `.env` do projeto `agent-local/` com os valores retornados (`AGENT_ID`, `AGENT_TOKEN`).
4. O agente local continuará usando `/api/agents/register`, `/api/agents/next-job` e `/api/agents/report`, mas agora o CRM valida o par `(agent_id, agent_token)` e entrega jobs apenas do respectivo `user_id`.
5. Para gestão operacional, use as rotas autenticadas do CRM (todas exigem assinatura ativa do produto `crm`):
   - `GET /api/agents` — lista apenas os agentes do usuário, com `online` calculado a partir de `last_seen_at`.
   - `POST /api/agents/{agent_id}/revoke` — marca `revoked_at` e passa a recusar `register/next-job/report` com o token antigo.
   - `POST /api/agents/{agent_id}/reprovision` — gera um novo `agent_token` (o antigo deixa de funcionar) e retorna instruções para atualizar o `.env` do agent-local.

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
     -d '{"agent_id":"<AGENT_ID>","token":"<AGENT_TOKEN>","capabilities":["whatsapp_send"],"version":"qa"}'
   ```

3. **next-job com fila vazia**
   ```bash
   curl "http://localhost:8010/api/agents/next-job?agent_id=<AGENT_ID>&token=<AGENT_TOKEN>&types=whatsapp_send"
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
   curl "http://localhost:8010/api/agents/next-job?agent_id=<AGENT_ID>&token=<AGENT_TOKEN>&types=whatsapp_send"
   ```
   Deve retornar o job criado no passo anterior.

6. **report (completed)**
   ```bash
   curl -X POST http://localhost:8010/api/agents/report \
     -H "Content-Type: application/json" \
     -d '{"agent_id":"<AGENT_ID>","token":"<AGENT_TOKEN>","job_id":<JOB_ID>,"status":"completed","result":{"ok":true}}'
   ```

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
   - Cria (ou reutiliza) uma mensagem e um job `whatsapp_send` na tabela `jobs`, ambos com `user_id` do A.
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
   - O agente chama `GET /api/agents/next-job?agent_id=...&token=...&types=whatsapp_send` e receberá apenas jobs do seu `user_id`.
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

### 4) Observações e Troubleshooting

- **Se retornar 401**: verifique se está enviando `Authorization: Bearer <token>` e se `CORE_API_BASE` do CRM aponta para o core correto.
- **Se jobs ficarem pending**: confirme que o `agent-local` está rodando com `AGENT_ID/AGENT_TOKEN` do usuário certo e que ele aceita `whatsapp_send` em `types`.
- **Se uma rota de prospecção responder 404**: normalmente o `lead_id` pertence a outro usuário ou não existe; revise o token usado.
