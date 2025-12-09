# Backend CRM

Este serviço agora utiliza exclusivamente o backend-core para autenticação. Cada chamada privada deve enviar `Authorization: Bearer <token_do_core>` com um token obtido no backend-core (`CORE_API_BASE`). Configure o `.env` com `CORE_API_BASE` apontando para a URL do core.

Principais mudanças:
- Dependência de autenticação via `get_current_user` consultando o `/users/me` do core.
- Coluna `user_id` adicionada às tabelas principais (leads, jobs, prospection_logs, agents) para isolar dados por usuário.
- Todas as rotas privadas de leads, prospecção, agentes e pesquisa exigem bearer token e filtram dados por `user_id`.

## Provisionamento do agente local (multiusuário)

1. Autentique-se no backend-core e obtenha um `access_token`.
2. Chame `POST /api/agents/provision` no backend-CRM com `Authorization: Bearer <token_do_core>` para gerar um par `(agent_id, agent_token)` vinculado ao seu usuário.
3. Configure o `.env` do projeto `agent-local/` com os valores retornados (`AGENT_ID`, `AGENT_TOKEN`).
4. O agente local continuará usando `/api/agents/register`, `/api/agents/next-job` e `/api/agents/report`, mas agora o CRM valida o par `(agent_id, agent_token)` e entrega jobs apenas do respectivo `user_id`.
