# Backend CRM

Este serviço agora utiliza exclusivamente o backend-core para autenticação. Cada chamada privada deve enviar `Authorization: Bearer <token_do_core>` com um token obtido no backend-core (`CORE_API_BASE`). Configure o `.env` com `CORE_API_BASE` apontando para a URL do core.

Principais mudanças:
- Dependência de autenticação via `get_current_user` consultando o `/users/me` do core.
- Coluna `user_id` adicionada às tabelas principais (leads, jobs, prospection_logs, agents) para isolar dados por usuário.
- Todas as rotas privadas de leads, prospecção, agentes e pesquisa exigem bearer token e filtram dados por `user_id`.
- Leads e fluxos de prospecção agora são multiusuário, sempre gravando e consultando dados com `user_id` derivado do backend-core.

## Provisionamento do agente local (multiusuário)

1. Autentique-se no backend-core e obtenha um `access_token`.
2. Chame `POST /api/agents/provision` no backend-CRM com `Authorization: Bearer <token_do_core>` para gerar um par `(agent_id, agent_token)` vinculado ao seu usuário.
3. Configure o `.env` do projeto `agent-local/` com os valores retornados (`AGENT_ID`, `AGENT_TOKEN`).
4. O agente local continuará usando `/api/agents/register`, `/api/agents/next-job` e `/api/agents/report`, mas agora o CRM valida o par `(agent_id, agent_token)` e entrega jobs apenas do respectivo `user_id`.

## Manual Testing Guide — Multiusuário (Leads, Prospecção, Assistente IA)

### 0) Pré-requisitos

- Suba o **backend-core** e o **backend-crm** (ambos carregam `.env` automaticamente). O CRM precisa da variável `CORE_API_BASE` apontando para a URL do core (ex.: `http://localhost:8000`).
- Crie dois usuários no core (ex.: `userA@example.com` e `userB@example.com`) via `POST /auth/register` e obtenha tokens via `POST /auth/login`. Anote `token_A` e `token_B`.
- Todas as rotas privadas do CRM exigem `Authorization: Bearer <token>`. Sempre envie o token do usuário que está testando.

### 1) Testes de Prospecção (Etapa 4.3 — prospecção + logs + jobs)

1. **Criar (ou localizar) um lead do usuário autenticado**
   ```bash
   curl -X POST http://localhost:8000/api/leads \
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
   curl -X POST http://localhost:8000/api/prospeccao/log \
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
   curl -X POST http://localhost:8000/api/prospeccao/whatsapp/enqueue \
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
   curl -X POST http://localhost:8000/api/agents/provision \
     -H "Authorization: Bearer $token_A" \
     -H "Content-Type: application/json" \
     -d '{"name": "Agente Local A"}'
   ```
   Copie `agent_id` e `agent_token` da resposta.

2. **Configurar e iniciar o `agent-local`**
   - No projeto `agent-local/`, defina no `.env`: `AGENT_ID=<agent_id>` e `AGENT_TOKEN=<agent_token>`.
   - Garanta que `CRM_API_BASE` aponte para o backend-CRM (ex.: `http://localhost:8000`).
   - Inicie o agente (ex.: `python main.py` no diretório `agent-local/`).

3. **Consumir jobs e reportar status**
   - O agente chama `GET /api/agents/next-job?agent_id=...&token=...&types=whatsapp_send` e receberá apenas jobs do seu `user_id`.
   - Após processar, o agente chama `POST /api/agents/report` com `status=completed` ou `failed`; o CRM atualiza `jobs` e grava logs em `prospection_logs` com o mesmo `user_id`.
   - Monitore `GET /api/prospeccao/whatsapp/recent` ou `GET /api/agents/jobs/summary` com `token_A` para ver o resultado.

4. **Isolamento entre usuários**
   - Repetir o fluxo com `token_B` gera um novo `agent_id`/`agent_token` e o agente só consumirá jobs do B.

### 3) Testes do Assistente IA (Etapa 4.3 — preview/import dedup)

1. **Gerar preview de um upload**
   ```bash
   curl -X POST http://localhost:8000/api/assistente-ia/preview \
     -H "Authorization: Bearer $token_A" \
     -H "Content-Type: application/json" \
     -d '{
           "upload_id": "meu_arquivo",   
           "overwrite": "update"         
         }'
   ```
   O arquivo `data/uploads/ai/meu_arquivo.xlsx` (ou `.csv`) deve existir. O preview deduplica apenas contra leads do `user_id` do token.
   ✅ Passo 1 — Colocar o arquivo
    Copie o arquivo para:
    backend-crm/data/uploads/ai/
    backend-crm/data/uploads/ai/leads_maps_manaus
    Passo 2 — Gerar preview
    ex: 
   {
        "upload_id": "leads_maps_manaus",
        "overwrite": "update"
      }'


2. **Importar/processar leads do assistente**
   ```bash
   curl -X POST http://localhost:8000/api/assistente-ia/processar \
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