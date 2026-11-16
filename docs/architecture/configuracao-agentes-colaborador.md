# Configuração de agentes por colaboradores (modo colaborador)

As skills `configuracao-personalizada` e `diagnosticar-agente` funcionam em dois modos, escolhidos por
`.claude/skills/diagnosticar-agente/scripts/verificar_ambiente.py` (primeiro passo de qualquer missão):

| | Modo dono | Modo colaborador |
|---|---|---|
| Quando | `railway` no PATH (sem `DIAG_MODO_COLABORADOR`) | sem Railway |
| Acesso à produção | `railway ssh` → `prod_turno.py` dentro do backend-core | rotas públicas com o login da conta de teste (`prod_http.py`) |
| Bancada local | sim (`preparar_bancada.py`, `.env` copiados) | não — tudo no Playground de produção da conta de trabalho |
| Cliente simulado | chave LLM local | `POST /api/playground/simulated-client` |
| Código | fluxo de implementação; regressão na bancada local | o mesmo fluxo; regressão = opt-in por omissão + 0 falhas novas nos testes (antes/depois) + validação em produção depois do deploy + revert |
| Confirmar deploy | código no container | `GET /version` (ação `versao`) |
| "Sim" das categorias que sobem | quem corre a sessão | quem corre a sessão (o colaborador) |
| Pedido de correção | — | só o que exige um dono do sistema (segredos, variáveis do servidor, serviços pagos, apagar dados) |

O deploy dos 4 serviços Railway vem do push no `main` do GitHub; publicar não exige acesso ao Railway.

## Transporte http (`prod_http.py`)

- `bancada.json`: `"transporte": "http"`; `prod.core_url` / `prod.crm_http_url` (por omissão os
  domínios Railway do `frontend-crm/.env.production`; `DIAG_CORE_URL` / `DIAG_CRM_URL` para testar
  contra backends locais).
- Credenciais em `.claude/agentes/_acesso.json` (`{email, senha}`, fora do git). Senha e token nunca
  são impressos.
- **Trava:** o `sub` do JWT do login tem de ser igual a `conta.prod_user_id` da bancada; senão
  `AcessoErro` (o colaborador nunca escreve na conta de um cliente).
- Ações (mesma saída que `prod_turno.py`): `perfil` (`GET /ai-profiles/me`, sem segredos),
  `conhecimento`, `chat` (`/api/playground/chat`), `limpar` (apaga só marcações `source=playground`),
  `sync`; mais `aplicar` (`PATCH /ai-profiles/me`; `simular.py --aplicar-prod` faz backup antes),
  `treino` (`/api/playground/training*`), `mensagens` (`/api/assistente-ia/messages/{lead_id}`),
  `conta` (user_id, plano, ai_profile_id), `pedido`/`pedidos`.
- `preparar_bancada.py <slug> --colaborador` cria a bancada a partir do login e tira o snapshot.

## Versão em produção (`GET /version`)

- backend-crm `GET /version` (público, só hashes): `{crm, core, executors}` via
  `services/deploy_version.py::versoes()` — `RAILWAY_GIT_COMMIT_SHA` do crm, `commit` do core
  (`GET /version`) e do executors (`GET /health`, campo `commit`); `None` se o serviço não responder.
- O `worker backend-executors` sai do mesmo commit e não tem HTTP.

## Cliente simulado no servidor

`POST /api/playground/simulated-client` (`routes/playground.py` →
`services/playground_simulated_client.py`), `require_crm_access`, sem estado:
- corpo `{persona ≤ 4000, agente: {nome, negocio, idioma}, conversa: [{de: cliente|agente, texto}] ≤ 40}`;
- resposta `{mensagem, fim}`; `fim` quando o texto contém `FIM`;
- prompt igual ao de `simular.py::cliente_ia` (gpt-4o-mini, temperatura 0.4, `OPENAI_API_KEY` do
  servidor); 503 sem chave, 502 em erro do LLM;
- não lê nem altera dados de nenhuma conta.

## Pedidos de correção

- Tabela `agent_fix_requests` (backend-crm, `ensure_agent_fix_requests_table` no `init_db`):
  `user_id, user_email, titulo, sintoma, evidencia, cenarios_json, bancada,
  estado (novo|em_curso|feito|descartado), nota_admin, created_at, updated_at`.
- `POST/GET /api/suporte/pedidos-correcao` (`require_crm_access`): o utilizador cria e lista **só os
  seus**; máximo 20 abertos (`novo`/`em_curso`) por utilizador → 429.
- `GET /admin/pedidos-correcao[?estado=]` e `PATCH /admin/pedidos-correcao/{id}` (`require_crm_admin`).
- frontend-admin: `AdminPedidos.tsx` (rota `/pedidos`, "Pedidos de correção" na barra lateral):
  filtro por estado, evidência, "Copiar prompt" (prompt pronto para o fluxo de implementação),
  mudar estado.

## Ficheiros

| Ficheiro | Papel |
|---|---|
| `.claude/skills/diagnosticar-agente/scripts/prod_http.py` | transporte http, trava, cliente simulado remoto |
| `.claude/skills/diagnosticar-agente/scripts/verificar_ambiente.py` | checklist do PC e modo |
| `.claude/skills/configuracao-personalizada/references/modo-colaborador.md` | como a skill trabalha no modo colaborador |
| `backend-crm/services/playground_simulated_client.py` | prompt e chamada do cliente simulado |
| `backend-crm/services/agent_fix_requests.py`, `routes/agent_fix_requests.py` | pedidos de correção |
| `frontend-admin/src/pages/AdminPedidos.tsx` | página dos pedidos |
