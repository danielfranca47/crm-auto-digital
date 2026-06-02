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

`name` é uma coluna adicionada por migração idempotente — `ensure_user_columns()` em `app/db.py` faz `ALTER TABLE` apenas se a coluna não existir. Chamado no startup.

---

## Endpoints de Auth

**Prefixo:** `/auth` — `backend-core/app/api/auth.py`

| Endpoint | Auth | Descrição |
|---|---|---|
| `POST /auth/register` | Público | Cria conta; aceita `email`, `password`, `name` (opcional) |
| `POST /auth/login` | Público | Devolve JWT Bearer (TTL: `ACCESS_TOKEN_EXPIRE_MINUTES`) |
| `GET /users/me` | Bearer | Perfil do utilizador autenticado |
| `POST /auth/forgot-password` | Público | Gera token de reset (TTL 2h), envia email; **sempre retorna 200** |
| `POST /auth/reset-password` | Público | Valida token, actualiza `password_hash`, marca `used_at` |
| `POST /auth/change-password` | Bearer | Utilizador autenticado altera a própria senha |

### JWT

- Algoritmo: `HS256`
- Payload: `{ sub: user_id, email, type: "access", exp }`
- Admin tokens: `{ sub: "admin", role: "admin", type: "access" }`

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
| `SMTP_PORT` | `587` | STARTTLS |
| `SMTP_USER` | `resend` | Literal — exigido pelo Resend |
| `SMTP_PASS` | API key Resend (`re_...`) | |
| `SMTP_FROM` | `Digital Pro <noreply@danielfranca.pt>` | Domínio verificado no Resend |
| `SMTP_TLS` | `true` | |
| `CRM_FRONTEND_URL` | `https://crmapp.danielfranca.pt` | Base para links nos emails |

**Templates disponíveis:**

- `render_welcome_email(name, temp_password, login_url)` → email de boas-vindas com senha temporária
- `render_reset_email(reset_url)` → email com botão "Redefinir senha"

Rodapé fixo: `"Digital Pro — CRM com IA para vendas via WhatsApp"`

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

## Modelo Subscription — Campos relevantes

**Tabela:** `subscriptions` (backend-core)

| Campo | Tipo | Notas |
|---|---|---|
| `status` | String | `"active"` / `"cancelled"` |
| `current_period_start` | DateTime | Início do período actual |
| `current_period_end` | DateTime nullable | Expiração do período |
| `trial_ends_at` | DateTime nullable | Preenchido quando `is_trial=true`; `None` = não é trial |

`trial_ends_at` adicionado via `ensure_subscription_columns()` em `app/db.py`.

---

## Modelo PlanLimits — Feature-gates

Colunas adicionadas via `ensure_plan_limits_columns()`:

| Campo | Tipo | Default | Descrição |
|---|---|---|---|
| `follow_up_enabled` | Boolean | `True` | Se False, bloqueia follow-up automático (etapa-9-4) |
| `playground_monthly_limit` | Integer nullable | `None` | `None` = ilimitado; `5` = 5 testes/mês no Start |

**Planos comerciais activos:**

| Plano | Código | Leads | Conv. IA | WA/dia | Follow-up | Playground |
|---|---|---|---|---|---|---|
| Start | `crm_start` | 500 | 250 | 50 | ❌ | 5/mês |
| Growth | `crm_growth` | 1500 | 500 | 100 | ✅ | ∞ |
| Interno | `crm_internal` | ∞ | ∞ | ∞ | ✅ | ∞ |
