# Auth, Gestão de Utilizadores e Email — backend-core

Cobre autenticação, ciclo de vida de contas, recuperação de senha e envio de email transacional.

---

## Modelo User

**Tabela:** `users` (backend-core, SQLAlchemy ORM)

| Campo | Tipo | Notas |
|---|---|---|
| `id` | Integer PK | |
| `email` | String unique | index |
| `password_hash` | String | pbkdf2_sha256 via passlib |
| `name` | String nullable | adicionado via `ensure_user_columns()` |
| `status` | String | `"active"` por defeito |
| `created_at` | DateTime | |
| `google_access_token` | String nullable | Access token OAuth2 Google |
| `google_refresh_token` | String nullable | Refresh token OAuth2 Google (longa duração) |
| `google_token_expiry` | String nullable | ISO datetime de expiração do access token |
| `google_calendar_id` | String nullable | Calendário Google alvo (default `"primary"`) |
| `google_email` | String nullable | Email da conta Google conectada (exibido na UI) |
| `smtp_host` | String nullable | Ex.: `smtp.gmail.com` — conta SMTP própria do utilizador para cold outreach por email |
| `smtp_port` | String nullable | Ex.: `587` |
| `smtp_username` | String nullable | Username da conta SMTP |
| `smtp_password_encrypted` | String nullable | Senha/senha de app cifrada (Fernet, `WHATSAPP_TOKEN_ENC_KEY` — mesma chave/helper `app/utils/crypto.py` usado para tokens de instância WhatsApp) |
| `smtp_from_name` | String nullable | Nome do remetente exibido nos emails enviados |
| `smtp_verified_at` | String nullable | ISO datetime da última verificação bem-sucedida; `NULL` = nunca conectado/desconectado |

`name`, as 5 colunas Google e as 6 colunas SMTP são adicionadas por `ensure_user_columns()` /
`ensure_smtp_columns()` em `app/db.py` (migrações idempotentes via `ALTER TABLE`). Chamadas no
startup.

`GET /users/me` inclui `google_calendar_connected: bool` — `True` quando `google_access_token IS NOT NULL`.

---

## Endpoints de Auth

**Prefixo:** `/auth` — `backend-core/app/api/auth.py`

| Endpoint | Auth | Descrição |
|---|---|---|
| `POST /auth/register` | Público | Cria conta; aceita `email`, `password`, `name` (opcional) |
| `POST /auth/login` | Público | Devolve JWT Bearer (TTL: `ACCESS_TOKEN_EXPIRE_MINUTES`) |
| `GET /users/me` | Bearer | Perfil do utilizador autenticado |
| `POST /auth/forgot-password` | Público | Gera token de reset (TTL 2h), envia email; **sempre retorna 200** |
| `POST /auth/reset-password` | Público | Valida token, actualiza `password_hash`, marca `used_at`; envia email de confirmação |
| `POST /auth/change-password` | Bearer | Utilizador autenticado altera a própria senha; envia email de confirmação |
| `POST /auth/register` | Público | Cria conta auto-serve; envia email de boas-vindas "A Lara está pronta para ti" |

### JWT

- Algoritmo: `HS256`
- Payload: `{ sub: user_id, email, type: "access", exp }`
- Admin tokens: `{ sub: "admin", role: "admin", type: "access" }`
- `SECRET_KEY` (`backend-core/app/config.py`) é campo obrigatório, sem default — `Settings()` levanta `ValidationError` no arranque se a env var não estiver definida, em vez de assinar tokens com um valor fraco conhecido.

---

## Google Calendar OAuth — backend-core

**Arquivo:** `backend-core/app/api/auth_google.py`

| Endpoint | Auth | Descrição |
|---|---|---|
| `GET /auth/google/calendar` | Bearer | Inicia OAuth2 — redireciona para consent screen Google |
| `GET /auth/google/calendar/callback` | Público (state assinado) | Recebe `code` do Google, troca por tokens, guarda em `users` |
| `DELETE /auth/google/calendar` | Bearer | Desconecta — limpa os 5 campos Google na tabela `users` |
| `GET /auth/google/tokens/{user_id}` | `x-service-token` | Service-to-service — backend-crm lê tokens do utilizador |
| `PUT /auth/google/tokens/{user_id}` | `x-service-token` | Service-to-service — backend-crm persiste token renovado após refresh |

**State assinado:** o parâmetro `state` do OAuth é um JWT HMAC-SHA256 com `{ user_id, exp: now+10min }` — não requer sessão server-side. O callback valida a assinatura e extrai `user_id`.

**Scopes solicitados:** `https://www.googleapis.com/auth/calendar.events`

**Variáveis de ambiente** (`backend-core/.env`):

| Variável | Descrição |
|---|---|
| `GOOGLE_CLIENT_ID` | OAuth2 client ID do Google Cloud Console |
| `GOOGLE_CLIENT_SECRET` | OAuth2 client secret |
| `GOOGLE_REDIRECT_URI` | URI de callback registada no Google Cloud (`/auth/google/calendar/callback`) |

---

## Conta SMTP do Utilizador (cold outreach por email)

**Arquivo:** `backend-core/app/api/smtp_accounts.py`

Permite ao utilizador conectar a própria conta de email (Gmail com senha de app, ou email
comercial/hosting) para o backend-crm/backend-executors enviarem o primeiro contacto frio por
email em nome dele — v1 é **SMTP genérico apenas**; Outlook/Hotmail/Microsoft 365 ficam fora de
escopo (exigiriam OAuth Microsoft).

| Endpoint | Auth | Descrição |
|---|---|---|
| `PUT /users/me/smtp` | Bearer | Testa login SMTP real (`smtplib`, sem enviar mensagem) **antes** de salvar — só persiste se autenticar. 400 com mensagem amigável se falhar (dica específica para Gmail sem senha de app) |
| `GET /users/me/smtp/status` | Bearer | `{ connected, username, host, port, from_name, verified_at }` — nunca devolve a senha |
| `DELETE /users/me/smtp` | Bearer | Desconecta — limpa as 6 colunas SMTP em `users` |
| `GET /users/{user_id}/smtp-credentials` | `X-Service-Token` | Service-to-service — backend-executors busca a credencial (senha decifrada) para enviar o job `email.send.cold` |

**Encriptação:** senha cifrada com `encrypt_secret`/`decrypt_secret` (`app/utils/crypto.py`),
reaproveitando a chave `WHATSAPP_TOKEN_ENC_KEY` já existente (helper genérico de "segredos de
provedor em repouso", mesmo padrão dos tokens de instância WhatsApp — nenhuma chave nova criada).

**Consumo:** ver [`agent-local-app.md`](agent-local-app.md#conta-de-email-smtp) para a tela de
conexão no app desktop, e [`plans-limits.md`](plans-limits.md) para o job `email.send.cold` e o
limite diário `max_email_send_daily`.

**Resultado do envio:** `sent`/`failed` ficam gravados em `prospection_logs`
(`channel="email"`) e visíveis no histórico — ver
[`agents.md`](agents.md#fluxo-end-to-end-via-backend-executors-ex-email-cold-outreach) para o
pipeline completo e [`agent-local-app.md`](agent-local-app.md#histórico) para as telas.

---

## Recuperação de Senha

**Model:** `password_reset_tokens` — `backend-core/app/models/password_reset_token.py`

| Campo | Tipo | Notas |
|---|---|---|
| `id` | Integer PK | |
| `user_id` | FK → users | ON DELETE CASCADE |
| `token` | String unique | UUID urlsafe (32 bytes) |
| `expires_at` | DateTime | UTC + 2h |
| `used_at` | DateTime nullable | `None` = ainda válido |
| `created_at` | DateTime | |

**Fluxo:**
```
POST /auth/forgot-password { email }
  → invalida tokens anteriores não usados do mesmo utilizador
  → gera token (secrets.token_urlsafe(32))
  → salva em password_reset_tokens
  → envia email com link {CRM_FRONTEND_URL}/reset-password?token=<token>
  → retorna 200 sempre (não revela se email existe)

POST /auth/reset-password { token, new_password }
  → valida: token existe + used_at IS NULL + expires_at > now()
  → actualiza password_hash
  → marca used_at
```

**Tabela criada por:** `Base.metadata.create_all()` no startup — não requer `ensure_*` manual.

---

## Criação de Conta pelo Admin

**Endpoint:** `POST /admin/users` — `backend-core/app/api/admin.py`

- Requer token admin
- Gera senha temporária (8 chars alfanum sem ambíguos)
- Cria `User` com `password_hash` da senha temporária
- Envia email de boas-vindas com a senha
- Retorna `{ ok, user_id, email, email_sent }` — `email_sent: false` se SMTP falhar (conta ainda é criada)

---

## Serviço de Email

**Arquivo:** `backend-core/app/services/email_service.py`

Usa `smtplib` (stdlib Python) com STARTTLS. Configuração via `.env`:

| Variável | Valor actual | Notas |
|---|---|---|
| `SMTP_HOST` | `smtp.resend.com` | Provider: Resend |
| `SMTP_PORT` | `2587` | STARTTLS. **Tem de ser 2587 em produção (Railway):** a Railway bloqueia egress nas portas SMTP padrão (25/465/587) — conexões à 587 dão `[Errno 110] Connection timed out` e nenhum email sai. A 2587 é a porta alternativa oficial do Resend para estes ambientes. Localmente 587 também funciona, mas usar 2587 em ambos mantém paridade |
| `SMTP_USER` | `resend` | Literal — exigido pelo Resend |
| `SMTP_PASS` | API key Resend (`re_...`) | |
| `SMTP_FROM` | `Digital Pro <noreply@danielfranca.pt>` | Domínio verificado no Resend |
| `SMTP_TLS` | `true` | |
| `CRM_FRONTEND_URL` | `https://crmapp.danielfranca.pt` | Base para links nos emails |

**Templates disponíveis:**

| Função | Trigger | Assunto |
|---|---|---|
| `render_welcome_email(name, temp_password, login_url)` | Admin cria conta **ou** webhook Efí (`action=activate`/`renew`) para email desconhecido | "Bem-vindo à Lara AI — as tuas credenciais de acesso" |
| `render_reset_email(reset_url)` | `forgot-password` | "Recuperação de senha — Digital Pro" |
| `render_password_changed_email(name)` | `reset-password` / `change-password` | "Senha alterada — Digital Pro" |
| `render_register_welcome_email(name, login_url)` | `POST /auth/register` | "Bem-vindo ao Digital Pro" |
| `render_subscription_activated_email(name, plan_name, period_end, login_url)` | Webhook Efí (`action=activate`) ou admin atribui plano | "A Lara está activa!" |
| `render_trial_started_email(name, plan_name, trial_end, login_url)` | Admin atribui trial | "Trial iniciado — Digital Pro" |
| `render_subscription_renewed_email(name, plan_name, new_end)` | Webhook Efí (`action=renew`) | "A Lara continua activa!" |
| `render_subscription_cancelled_email(name, plan_name)` | Qualquer `action=cancel` em `payment_event` — Webhook Efí ou reembolso via admin (`billing-efi.md`) | "Subscrição cancelada" |
| `render_subscription_expiring_email(name, plan_name, period_end, checkout_url)` | Job diário — 3 dias antes de expirar | "A Lara para em breve ⚠️" |
| `render_subscription_expired_email(name, plan_name, checkout_url)` | Job diário — subscription expirada | "A Lara está pausada" |

**Branding:** todos os emails usam rodapé `"Lara by Digital Pro — A tua IA de vendas via WhatsApp"` (constante `_FOOTER` / `_FOOTER_TEXT` em `email_service.py`).

**Padrão não-bloqueante:** todas as chamadas de `send_email()` estão em `try/except` — falha de SMTP nunca faz rollback de operação de negócio.

---

## Rotas Públicas no Frontend-CRM

**Arquivo:** `frontend-crm/src/App.tsx`

Rotas fora do wrapper `Protected` (sem verificação de auth):

| Rota | Componente | Descrição |
|---|---|---|
| `/login` | `Login.tsx` | Login com "Esqueci a senha" + link "Criar conta" |
| `/register` | `Register.tsx` | Auto-registo: nome (opcional), email, senha |
| `/forgot-password` | `ForgotPassword.tsx` | Formulário de email; mostra confirmação após submit |
| `/reset-password` | `ResetPassword.tsx` | Lê `?token=` da URL; form nova senha + confirmar |

**Após sucesso:**
- `/register` → `/login?registered=1` (mensagem "Conta criada com sucesso!")
- `/reset-password` → `/login?reset=1` (mensagem "Senha redefinida com sucesso!")

---

## Guarda no LeadsContext

`frontend-crm/src/contexts/LeadsContext.tsx` carrega leads no mount. Para evitar redirect para `/login` em rotas públicas (quando não há token ou o token não tem acesso ao CRM):

1. `useEffect` inicial só chama `reloadAllLeads()` se `readAuthToken()` retornar valor
2. `reloadAllLeads` não chama `handleError` para 401/403 — esses erros são tratados pelo componente `Protected`

---

## Painel Admin — Utilizadores

**Endpoint:** `GET /admin/users` — `backend-core/app/api/admin.py`

Retorna por utilizador: `id`, `email`, `name`, `status`, `created_at`, `plan_name`, `plan_code`, `subscription_status`, `subscription_period_start`, `subscription_period_end`, `subscription_is_trial`, `enabled_extensions`.

**Frontend:** `frontend-admin/src/pages/AdminUsers.tsx` — tabela com colunas: usuário (nome+email), plano (badge por tier + badge Trial), status, início de subscrição, data de expiração. Botão "Criar conta" abre modal email + nome. Botão "Plano" abre modal para atribuir/alterar plano com duração e opção trial.

**Endpoint atribuir plano:** `POST /admin/users/{user_id}/subscription`
- Cancela subscription activa existente (`status=cancelled`)
- Cria nova com `period_end = now + 30*months dias` (ou 7 dias se `is_trial=true`)
- Se trial: `trial_ends_at = period_end`
- Aceita: `{ plan_code, months (default 1), is_trial (default false) }`

---

## Painel Admin — Planos

**Endpoint:** `GET /admin/plans` — `backend-core/app/api/admin.py`

Retorna planos CRM activos com limites completos: `plan_code`, `plan_name`, `max_leads`, `max_ia_conversas_monthly`, `max_whatsapp_send_daily`, `follow_up_enabled`, `playground_monthly_limit`, `max_agents_local`.

**Frontend:** `frontend-admin/src/pages/AdminPlans.tsx` — tabela de comparação planos comerciais vs legados; rota `/planos` na sidebar.

---

## Gateway de pagamento (Efí)

A activação/renovação/cancelamento automático de subscriptions é accionada por webhook do gateway
de pagamento Efí Bank — fluxo completo, cliente HTTP e variáveis de ambiente documentados em
[`billing-efi.md`](billing-efi.md). Aqui ficam só as tabelas relevantes ao domínio de auth/email
(User, templates, Subscription).

---

## Alertas de consumo (frontend-crm)

`GET /api/usage` (backend-crm) inclui `ia_monthly: { used, limit, pct }` e `checkout_links` com
URLs de checkout Efí geradas sob demanda — ver [`billing-efi.md`](billing-efi.md).

`UsageAlertBanner` em `frontend-crm/src/components/UsageAlertBanner.tsx` aparece no AppShell:
- `pct >= 80` → banner amarelo com link de upgrade
- `pct >= 100` → banner vermelho + "Comprar mais"

---

## Modelo Subscription — Campos relevantes

**Tabela:** `subscriptions` (backend-core)

| Campo | Tipo | Notas |
|---|---|---|
| `status` | String | `"active"` / `"cancelled"` / `"expired"` |
| `current_period_start` | DateTime | Início do período actual |
| `current_period_end` | DateTime nullable | Expiração do período |
| `trial_ends_at` | DateTime nullable | Preenchido quando `is_trial=true`; `None` = não é trial |
| `expiry_warning_sent` | Boolean | `False` por defeito; `True` após job enviar aviso de expiração |
| `efi_charge_id` | Integer nullable | `charge_id` da cobrança Efí mais recente (activação ou renovação) — usado para reembolso via admin, ver [`billing-efi.md`](billing-efi.md#reembolso) |

**Status `"expired"`:** atribuído pelo job diário quando `current_period_end < now` e `status == "active"`. Distinto de `"cancelled"` (cancelamento activo) e `"inactive"` (nunca teve plano).

`GET /me/entitlements` retorna `subscription_status`:
- `"active"` — tem sub activa
- `"expired"` — última sub expirou (não renovada)
- `"inactive"` — nunca teve sub

Cada entrada em `products[]` inclui `current_period_end` (nullable ISO datetime) — usada pelo frontend em `Assinatura.tsx` para exibir data de renovação do plano actual.

`GET /admin/users` mostra plano e status da sub mais recente (activa ou expirada), ordenado por `current_period_end desc`.

Colunas adicionadas via `ensure_subscription_columns()` em `app/db.py`.

---

## Job de Expiração Automática de Subscriptions

**Arquivo:** `backend-core/app/jobs/subscription_jobs.py`

Job diário que processa dois tipos de pendentes:

1. **Subscriptions expiradas** — `status == "active"` e `current_period_end < now` → muda para `"expired"` + envia `render_subscription_expired_email`
2. **Avisos antecipados em múltiplos estágios** (30/15/7/3/2/1/0 dias antes) — ver
   [`billing-efi.md`](billing-efi.md#ciclo-de-vida-de-avisos-de-expiração) para o mecanismo
   completo (`expiry_warning_stage`, reset na renovação, copy por `origin_offer`)

**Scheduler:** `APScheduler BackgroundScheduler` (corre dentro do processo uvicorn)
- Configurado em `app/main.py` no `@app.on_event("startup")`
- Schedule: `CronTrigger(hour=12, minute=0, timezone="UTC")` — 09:00 hora de Brasília
- **Execução no startup:** o job corre uma vez imediatamente ao arrancar o servidor, para recuperar pendentes de quando o servidor esteve offline

**Trigger manual (admin):** `POST /admin/cron/daily` — executa o job e retorna sumário `{ expired, warnings_sent, errors, ran_at }`. Usado para testes e recovery manual.

**Links de checkout por plano** (incluídos nos emails de aviso/expiração, via `_get_checkout_url`)
— apontam para o endpoint de checkout sob demanda da Efí, com fallback para
`{CRM_FRONTEND_URL}/assinatura`; ver [`billing-efi.md`](billing-efi.md) para a tabela completa de
ofertas e variáveis de ambiente.

**Nota sobre disponibilidade:** como o scheduler corre dentro do processo, se o servidor estiver offline quando o job devia correr, o job salta esse dia. A execução no startup compensa este comportamento para o contexto de deploy local via tunnel.

---

## Modelo PlanLimits — Feature-gates

Colunas adicionadas via `ensure_plan_limits_columns()`:

| Campo | Tipo | Default | Descrição |
|---|---|---|---|
| `follow_up_enabled` | Boolean | `True` | Se False, bloqueia follow-up automático (etapa-9-4) |
| `playground_monthly_limit` | Integer nullable | `None` | `None` = ilimitado; `5` = 5 testes/mês no Start |

**Planos comerciais activos:**

| Plano | Código | Leads | Conv. IA | WA/dia | Email/dia | Follow-up | Playground |
|---|---|---|---|---|---|---|---|
| Start | `crm_start` | 500 | 250 | 50 | 30 | ❌ | 5/mês |
| Growth | `crm_growth` | 1500 | 500 | 100 | 60 | ✅ | ∞ |
| Interno | `crm_internal` | ∞ | ∞ | ∞ | ∞ | ✅ | ∞ |
