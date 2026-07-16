# Email como primeiro contato (cold outreach) — v1 SMTP-only

**Branch:** `main`
**Status:** Em andamento

---

## Motivação

Hoje o agente local só prospecta por WhatsApp. O utilizador quer que a próxima versão do
agente local (v3) permita configurar, no perfil de IA, o **fluxo de primeiro contato
favorito**: `email primeiro` ou `somente WhatsApp`. Se escolher email, o utilizador
autentica a própria conta de email **dentro do app** e o sistema passa a enviar a
mensagem fria de abertura por email.

Depois de discutir viabilidade (Gmail/Outlook/Microsoft/comercial via OAuth vs SMTP),
ficou decidido:

- **v1 = SMTP genérico apenas.** Cobre Gmail pessoal (via "senha de app", exige 2FA
  ativado antes) e email comercial (cPanel/hosting próprio).
- **Outlook/Hotmail/Microsoft 365 ficam fora do escopo da v1** — a Microsoft desativou
  SMTP com autenticação básica para essas contas (set/2024 pessoais, 2022 empresariais);
  suportá-las exigiria OAuth Microsoft, um projeto à parte.
- Esta feature é **uma fase dentro do objetivo maior do agent-local v3**
  (`docs/plans/agent-local-melhorias-futuras-V3.md`).

---

## Problemas Identificados (estado anterior)

1. **Canal "email" existe só para gerar texto, nunca para enviar.**
   `backend-crm/models.py:70` define `Channel` incluindo `"email"`; `messages.subject`
   já existe; `POST /api/prospeccao/generate-copy` já gera copy de email via LLM. Mas
   `routes/prospeccao.py:151` só age sobre `channel == "whatsapp"` — email é só texto
   que o utilizador copia manualmente.
2. **Nenhuma infraestrutura de credencial de email por-usuário existe** — nem colunas,
   nem encriptação aplicada a esse caso, nem endpoint.
3. **Nenhum job type de envio de email existe** na fila (`jobs_service.py`).

---

## Abordagem

```
Utilizador conecta email (agent-local, Fase 5) → PUT /users/me/smtp (backend-core)
  → testa login SMTP (sem enviar nada) → só salva se autenticar
  → senha guardada encriptada (Fernet, reaproveitando WHATSAPP_TOKEN_ENC_KEY)

Utilizador define preferência de canal → PUT /ai-profiles/me { cold_outreach_channel }

Prospecção em massa (agent-local) → POST /api/prospeccao/email/enqueue (Fase 2)
  → cria job "email.send.cold" na fila (pula leads sem email preenchido)
  → backend-executors consome via /api/internal/jobs/next (Fase 3)
    → busca credencial em GET /users/{id}/smtp-credentials (backend-core)
    → envia via smtplib, reporta resultado
```

---

## Plano de Implementação

### Fase 1 — backend-core: credenciais SMTP + preferência de canal

**Objetivo:** o usuário consegue salvar/testar/remover uma credencial SMTP própria
(encriptada) e o AI Profile ganha o campo de preferência de canal.

| Arquivo | O que muda |
|---|---|
| `backend-core/app/db.py` | Nova `ensure_smtp_columns()` — 6 colunas em `users` (`smtp_host`, `smtp_port`, `smtp_username`, `smtp_password_encrypted`, `smtp_from_name`, `smtp_verified_at`); `max_email_send_daily` adicionada a `ensure_plan_limits_columns()`; `cold_outreach_channel` adicionada a `ensure_ai_profile_columns()` |
| `backend-core/app/main.py` | Chama `ensure_smtp_columns()` no startup; registra `smtp_accounts_router` |
| `backend-core/app/api/smtp_accounts.py` (novo) | `PUT /users/me/smtp` (testa login SMTP antes de salvar), `GET /users/me/smtp/status`, `DELETE /users/me/smtp`, `GET /users/{user_id}/smtp-credentials` (service-to-service, `X-Service-Token`) |
| `backend-core/app/api/__init__.py` | Inclui o novo router |
| `backend-core/app/models/ai_profile.py` | Nova coluna ORM `cold_outreach_channel` |
| `backend-core/app/api/ai_profiles.py` | Novo `ColdOutreachChannel` enum (`whatsapp_only`\|`email_first`); campo adicionado a `AIProfileBase`/`AIProfileUpdate` |
| `backend-core/app/models/plan_limits.py` | Nova coluna `max_email_send_daily` + `as_dict()` |
| `backend-core/app/api/subscriptions.py` | `UserLimits` e o dict `totals` de `/me/entitlements` ganham `max_email_send_daily` |
| `backend-core/app/seed.py` | `max_email_send_daily` semeado para `crm_start` (30/dia), `crm_growth` (60/dia), `crm_internal` (ilimitado) |
| `backend-core/.env.example` | Comentário de `WHATSAPP_TOKEN_ENC_KEY` atualizado (agora cifra mais do que só tokens WhatsApp) |

**Decisão técnica:** reaproveitada a chave de encriptação `WHATSAPP_TOKEN_ENC_KEY` e o
helper `app/utils/crypto.py` (`encrypt_secret`/`decrypt_secret`) já existentes — não foi
criada uma chave nova, pois o helper já é genérico ("segredos de provedor em repouso"),
mesma decisão do padrão usado para os tokens de instância WhatsApp.

**Teste de conexão obrigatório antes de salvar:** `_test_smtp_login()` faz login SMTP
real (sem enviar mensagem) e devolve erro 400 com mensagem amigável se falhar —
inclusive uma dica específica para o caso de Gmail sem senha de app.

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `a8cf7d0` | backend-core: colunas SMTP encriptadas + preferência de canal + limite diário |

---

### Relatório da Fase 1 — o que mudou na prática

**Antes:** o sistema não tinha nenhuma forma de guardar uma conta de email do usuário
nem de saber se ele prefere começar a prospecção por email ou só por WhatsApp.

**Agora:** o backend-core (a base de contas/autenticação) já sabe guardar uma conta
SMTP (Gmail com senha de app, ou email comercial) de forma segura — a senha é cifrada
antes de ir para o banco, e só é salva depois de o sistema confirmar que consegue
mesmo fazer login com aquela credencial. O perfil de IA também já tem o campo de
preferência de canal (`email primeiro` ou `só WhatsApp`), e o plano do usuário já
define quantos emails por dia ele pode mandar. **Nada disso tem interface ainda** —
por enquanto só existe o "motor" no backend; a tela para o usuário mexer nisso é a
Fase 5 (agent-local).

**Para validar:** Cenários P1 a P5, acima — todos já verificados nesta sessão via
scripts isolados. O Cenário P6 (conexão com credencial real) fica melhor validado
junto da Fase 5, quando existir uma tela de fato para o usuário digitar os dados.

## Checks de Validação

### Cenário P1 — Migração de colunas idempotente
- [x] Rodar `ensure_smtp_columns()` + `ensure_ai_profile_columns()` + `ensure_plan_limits_columns()` contra o `core.db` real de desenvolvimento
- [x] Confirmar as 6 colunas SMTP em `users`, `max_email_send_daily` em `plan_limits`, `cold_outreach_channel` em `ai_profiles`
- [x] Rodar novamente — nenhuma coluna duplicada, nenhum erro (idempotência confirmada)
- **Validado em:** 16/07/2026 — script Python isolado no `.venv` do backend-core

### Cenário P2 — Encriptação round-trip
- [x] `encrypt_secret`/`decrypt_secret` com a `WHATSAPP_TOKEN_ENC_KEY` já configurada no `.env` local — texto original recuperado corretamente
- **Validado em:** 16/07/2026

### Cenário P3 — Salvar/consultar/remover credencial SMTP (sem rede real)
- [x] `_save_smtp_account` → `_get_user_smtp_data` devolve os valores salvos (senha nunca em texto puro fora do encrypt)
- [x] `_clear_smtp_account` → todos os campos voltam a `None`
- **Validado em:** 16/07/2026 — usuário de teste real do `core.db` (revertido ao estado original ao final do teste)

### Cenário P4 — Teste de conexão falha com erro claro
- [x] `_test_smtp_login` contra host inexistente → `HTTPException(400, ...)` com mensagem legível, sem crash
- **Validado em:** 16/07/2026

### Cenário P5 — Rotas registradas sem colisão
- [x] `PUT/GET/DELETE /users/me/smtp*` e `GET /users/{user_id}/smtp-credentials` coexistem sem conflito de path com as rotas já existentes em `users.py`
- **Validado em:** 16/07/2026 — inspeção de `app.routes` via `TestClient`

### Cenário P6 — Teste de conexão real com credencial verdadeira (Gmail/comercial)
- [ ] Conectar uma conta Gmail real (senha de app) via `PUT /users/me/smtp` e confirmar sucesso
- [ ] Conectar uma conta de email comercial (cPanel/hosting) e confirmar sucesso
- **Pendente** — requer credencial real de teste; melhor validado junto da Fase 5 (UI no agent-local), quando há uma tela de fato para inserir os dados

### Cenário P7 — Enfileirar → enviar (fluxo completo simulado)
- [x] `enqueue_email_jobs` cria job `email.send.cold` com `email`/`subject`/`body` no payload
- [x] `execute_job` (runner) faz claim, busca credencial via `core_client.get_smtp_credentials(user_id)` — `user_id` vem do próprio job, não do payload — e chama `_send_email` com os parâmetros corretos
- [x] `complete_job` é chamado com `{"status": "sent", "lead_id", "email"}`
- **Validado em:** 16/07/2026 — teste isolado com `unittest.mock` (sem rede real)

### Cenário P8 — Usuário sem conta SMTP conectada
- [x] `core_client.get_smtp_credentials` levanta 404 → job falha com motivo claro
  ("usuário sem conta de email SMTP conectada"), `retryable=False`
- **Validado em:** 16/07/2026

### Cenário P9 — Falha de autenticação SMTP
- [x] `smtplib.SMTPAuthenticationError` → job falha com o erro real do servidor,
  `retryable=False` (tentar de novo sem o usuário corrigir a senha não adianta)
- **Validado em:** 16/07/2026

### Cenário C1 — Envio real ponta a ponta (nunca observado)
- [ ] Conectar uma conta SMTP real (Gmail com senha de app, ou comercial)
- [ ] Enfileirar um email de teste para um lead com email real
- [ ] Rodar `python -m app.workers.email_worker` e confirmar recebimento na caixa de entrada
- **Pendente** — melhor validado junto da Fase 5, quando existir UI para conectar a conta e disparar o envio

---

### Fase 2 — backend-crm: fila de jobs de email

**Objetivo:** enfileirar um job de envio de email por lead (mesmo padrão do WhatsApp),
com limite diário aplicado e leads sem email pulados automaticamente.

| Arquivo | O que muda |
|---|---|
| `backend-crm/services/jobs_service.py` | `TYPE_EMAIL_SEND_COLD = "email.send.cold"`; `_persist_email_message()` (mirror de `_persist_whatsapp_message`, com `subject`); nova `enqueue_email_jobs()` (mirror de `enqueue_whatsapp_jobs`) — usa `leads.email` em vez de `phone`, pula lead sem email (`reason: "email_ausente"`) |
| `backend-crm/services/rate_limit_service.py` | `LIMIT_KEYS_BY_TYPE` ganha `TYPE_EMAIL_SEND_COLD: "max_email_send_daily"` |
| `backend-crm/routes/prospeccao.py` | Novo `POST /api/prospeccao/email/enqueue` (mirror de `whatsapp/enqueue`) |

**Desvio do plano original (para menos trabalho):** o plano previa alterar o endpoint
interno `/api/internal/jobs/next` para aceitar `email.send.cold`. Na investigação,
`get_next_job_internal()` (`backend-crm/routes/executor.py:144`) já é genérico — recebe
`types` livre por query string, sem allowlist hardcoded — então nenhuma mudança foi
necessária ali. O mesmo vale para `claim`/`complete`/`fail` (linhas 696/769/870): são
genéricos por `job_id`, com tratamento especial só para `TYPE_WHATSAPP_INBOUND`
(irrelevante para email).

**Bug encontrado e corrigido durante o teste:** ao simular o limite diário esgotado
(`max_email_send_daily=0`), a `HTTPException(429)` levantada por
`rate_limit_state.ensure_can_consume()` estava sendo capturada pelo `except Exception`
genérico do laço e virando `{"reason": "erro_interno"}` — um erro opaco, sem indicar que
o motivo real era o limite do plano. Corrigido com um `except HTTPException` dedicado
que registra `{"reason": "limite_diario_atingido"}` e continua processando os demais
leads do lote (mesma filosofia de "skip com motivo claro" já usada para
`email_ausente`/`sem_mensagem`/`ja_pendente`). **Nota:** o mesmo problema existe hoje em
`enqueue_whatsapp_jobs` (não foi alterado — fora do escopo desta feature).

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `911fe2c` | backend-crm: fila de jobs de email + endpoint de enqueue |

### Relatório da Fase 2 — o que mudou na prática

**Antes:** não existia nenhuma forma de programar o envio de um email a partir do CRM —
só a fila de WhatsApp existia.

**Agora:** o agent-local (quando a Fase 5 tiver a tela pronta) já pode chamar
`POST /api/prospeccao/email/enqueue` com uma lista de leads + assunto/corpo, e o sistema
cria um job de email por lead, pulando automaticamente quem não tem email cadastrado ou
já tem um envio igual pendente, e respeitando o limite diário do plano do usuário. O
envio de fato (Fase 3) ainda não existe — o job fica na fila esperando um executor.

**Para validar:** testado nesta sessão via scripts isolados contra o `crm.db` real de
desenvolvimento (dados de teste criados e revertidos ao final) — caminho feliz, lead sem
email, duplicata, e limite diário esgotado, todos com o comportamento esperado.

### Fase 3 — backend-executors: envio real via SMTP

**Objetivo:** um worker assíncrono consome os jobs `email.send.cold` da fila e envia o
email de verdade, usando a credencial SMTP do próprio usuário.

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/clients/core_client.py` | Nova `get_smtp_credentials(user_id)` — chama `GET /users/{user_id}/smtp-credentials` no backend-core |
| `backend-executors/app/runners/email.py` (novo) | `execute_job()`: claim → lê payload do job (`lead_id`, `email`, `subject`, `body`, `user_id` do próprio job) → busca credencial no core → envia via `smtplib` → `complete_job`/`fail_job` |
| `backend-executors/app/workers/email_worker.py` (novo) | Loop de polling (mirror de `whatsapp_worker.py`) — consome `email.send.cold` via `crm_client.get_next_job` |
| `backend-executors/Procfile` | Novo processo `email_worker: python -m app.workers.email_worker` |
| `docs/ops/local-dev.md` | Instruções para rodar o worker de email localmente |

**Decisão técnica:** o runner de email é deliberadamente muito mais simples que
`runners/whatsapp.py` — não há LLM nem decision engine envolvidos, porque o
assunto/corpo do email já foi definido no momento do enqueue (Fase 2). O runner só
faz claim → SMTP send → complete/fail, sem chamar `execution-context`.

**Erros não-retryable (`fail_job` com `retryable: False`):** payload incompleto,
usuário sem conta SMTP conectada (404), e falha de autenticação SMTP — nesses três
casos, tentar de novo automaticamente não resolveria nada; exige ação do usuário.
Erros de rede/timeout/5xx são marcados `retryable: True`, deixando o
backoff existente do `jobs_service.py` (backend-crm) decidir se tenta de novo.

### Commits Fase 3

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `da35f28` | backend-executors: runner + worker de envio de email via SMTP |

### Relatório da Fase 3 — o que mudou na prática

**Antes:** o job de email ficava parado na fila para sempre — nada o processava.

**Agora:** existe um novo processo (`python -m app.workers.email_worker`, ou o processo
`email_worker` do Procfile em produção) que fica de olho na fila e, assim que encontra
um job de email pendente, busca a credencial SMTP do usuário (guardada de forma segura
no backend-core, Fase 1) e manda o email de verdade. Se o usuário ainda não conectou
nenhuma conta de email, ou se a senha estiver errada, o job falha com um motivo claro
em vez de ficar tentando de novo sem parar.

**Para validar:** testado nesta sessão com chamadas de rede simuladas (mock) — caminho
feliz (claim → busca credencial → envia → completa), usuário sem conta conectada, e
falha de autenticação SMTP. Falta testar com um envio real de ponta a ponta (Cenário C1
abaixo), que fica mais natural de fazer junto da Fase 5, quando existir uma tela de
verdade para conectar a conta e dar o comando de enviar.

### Fase 4 — frontend-crm: preferência de canal + uso do plano

**Objetivo:** o usuário consegue escolher, na configuração do agente, se o primeiro
contato frio prioriza email ou fica só WhatsApp, e visualiza quantos emails já usou/
quantos restam no dia no painel "Uso do Plano".

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/types/agente.ts` | `AgentConfig.cold_outreach_channel`; default `'whatsapp_only'`; novo `COLD_OUTREACH_CHANNEL_LABELS` |
| `frontend-crm/src/services/api.ts` | `AiProfilePayload.cold_outreach_channel`; `loadConfig()` mapeia o campo vindo do perfil; `saveConfig()` envia no `PUT /ai-profiles/me` |
| `frontend-crm/src/components/agente/CamadaIdentidade.tsx` | Novo `EditCard` "Canal de 1º contato" na seção "Contexto de abertura" (sem gate por `template_key` — vale para todos os modos); novo `DrawerColdOutreachChannel` (mirror de `DrawerResponseStyle`) com as opções "Somente WhatsApp" / "Email primeiro" |
| `frontend-crm/src/pages/AiProfile.tsx` | Novo `SummaryCard` "Canal de 1º contato" no painel Resumo |
| `frontend-crm/src/components/PlanLimitsCard.tsx` | `max_email_send_daily` adicionado a `LABELS` e `DAILY_KEYS` (componente já genérico) |
| `frontend-crm/src/pages/UsoDoPlano.tsx` | Novo `UsageCard` "Email do dia" (mirror do card de WhatsApp) |
| `backend-crm/routes/usage.py` | `max_email_send_daily` adicionado a `daily_keys` — sem isso `/api/usage` nunca preenchia `daily.max_email_send_daily` e os cards acima ficariam sempre vazios |
| `backend-crm/routes/admin_agents.py` | `cold_outreach_channel` incluído nos dois pontos onde o dict do perfil é montado (overview e detalhe do usuário) |
| `docs/architecture/admin-agents-contract.md` | Nova linha para `cold_outreach_channel` na tabela de campos do AI Profile |

**Decisão técnica:** a UI reaproveita 100% os padrões já existentes —
`EditCard`/`DrawerBase` (mesmo formato de `DrawerResponseStyle`) para a escolha de canal,
e `PlanLimitsCard`/`UsageCard` (já genéricos por chave) para o uso diário. Nenhum
componente novo de estilo foi criado.

**Lacuna da Fase 1 corrigida:** `cold_outreach_channel` afeta o comportamento do agente
(qual canal a prospecção fria usa) mas não tinha sido registado em
`admin-agents-contract.md` nem exposto por `GET /admin/agents/users/{user_id}`, como a
regra obrigatória do CLAUDE.md exige para todo novo campo de `ai_profiles`. Corrigido
nesta fase — documentado como "Não exibido no painel admin atualmente", mesmo
tratamento já dado a `sales_flow` (o `AdminAgents.tsx` hoje não tem um drawer genérico de
campos do profile; criar essa UI ficou fora do escopo desta fase).

**Fora de escopo:** conectar a própria conta SMTP continua sendo a Fase 5 (agent-local)
— o frontend-crm só expõe a *preferência* de canal, não a conexão da credencial.

### Commits Fase 4

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | *(pendente — a criar)* | frontend-crm: seletor de canal de 1º contato + uso diário de email; correção de lacuna do admin-agents-contract |

### Relatório da Fase 4 — o que mudou na prática

**Antes:** o campo de preferência de canal (email primeiro ou só WhatsApp) já existia no
backend desde a Fase 1, mas não havia nenhuma tela para o usuário escolher — e o painel
"Uso do Plano" não mostrava o limite diário de emails.

**Agora:** na configuração do agente (Identidade → Contexto de abertura), o usuário
escolhe "Somente WhatsApp" ou "Email primeiro" para o primeiro contato da prospecção
fria — com aviso de que "Email primeiro" exige conectar uma conta de email no agente
local (isso ainda não existe — é a Fase 5). O painel "Uso do Plano" agora mostra quantos
emails já foram enviados hoje e quantos restam, ao lado do card de WhatsApp.

**Para validar:** Cenários P10 e P11, abaixo.

## Checks de Validação — Fase 4

### Cenário P10 — Preferência de canal persiste
- [ ] Abrir AiProfile → Identidade, trocar "Canal de 1º contato" para "Email primeiro", salvar
- [ ] Recarregar a página e confirmar que o valor salvo permanece "Email primeiro"
- [ ] Trocar de volta para "Somente WhatsApp" e confirmar que também persiste
- **Pendente** — requer sessão de browser (frontend-crm rodando + backend-core + backend-crm)

### Cenário P11 — Card de uso de email no painel
- [ ] Abrir "Uso do Plano" e confirmar que aparece o card "Email do dia" com usado/limite/restante
- [ ] Enfileirar um job de email de teste (`POST /api/prospeccao/email/enqueue`) e confirmar que "usado" incrementa após o próximo carregamento da página
- **Pendente** — requer sessão de browser + dados de teste

## Ajustes Possíveis Pós-Implementação

- Outlook/Hotmail/Microsoft 365 permanecem fora de escopo — exigem OAuth Microsoft (fase futura separada).
- Só uma conta SMTP por usuário nesta v1 (sem múltiplas contas/alternância).
- Sem histórico/analytics de emails enviados nesta v1.
