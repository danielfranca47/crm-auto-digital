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
| 1 | *(pendente — a criar)* | backend-core: colunas SMTP encriptadas + preferência de canal + limite diário |

---

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

---

## Ajustes Possíveis Pós-Implementação

- Outlook/Hotmail/Microsoft 365 permanecem fora de escopo — exigem OAuth Microsoft (fase futura separada).
- Só uma conta SMTP por usuário nesta v1 (sem múltiplas contas/alternância).
- Sem histórico/analytics de emails enviados nesta v1.
