# Auth — Email SMTP + Criação de Conta + Recuperação de Senha

**Branch:** `etapa-9-planos-limites`
**Status:** Em andamento — implementação completa, aguarda testes

---

## Motivação

O sistema não tem nenhuma infraestrutura de email nem fluxo de recuperação de senha. Clientes que esquecem a senha ficam bloqueados sem saída. O admin não consegue criar contas novas pelo painel — precisa de acesso direto ao banco. O auto-registo existe no backend (`POST /auth/register`) mas sem UI. Esta etapa entrega: serviço de email SMTP, recuperação de senha, alteração de senha, criação de conta pelo admin e auto-registo no frontend-crm.

---

## Problemas Identificados (estado anterior)

1. **Sem serviço de email (`backend-core/app/config.py`):** Nenhuma variável SMTP configurada, nenhum serviço de envio.

2. **Sem fluxo de recuperação de senha (`backend-core/app/api/auth.py`):** Nenhum endpoint `forgot-password` ou `reset-password`. Nenhuma tabela de tokens de reset.

3. **Sem UI de auto-registo (`frontend-crm/src/pages/`):** `POST /auth/register` existe no backend mas sem página de registo no frontend-crm.

4. **Admin não consegue criar contas (`backend-core/app/api/admin.py`):** Não existe `POST /admin/users`. Criar conta exige acesso direto ao banco.

5. **Login sem link "Esqueci senha" (`frontend-crm/src/pages/Login.tsx`):** Página de login sem caminho de recuperação.

---

## Abordagem

```
Fluxo recuperação de senha:
  Utilizador clica "Esqueci senha" → /forgot-password
    → POST /auth/forgot-password { email }
    → gera UUID token (TTL 2h) → salva em password_reset_tokens
    → envia email com link {CRM_PUBLIC_BASE_URL}/reset-password?token=<token>
    → utilizador clica link → /reset-password?token=<token>
    → POST /auth/reset-password { token, new_password }
    → valida token → atualiza password_hash → marca token como usado

Fluxo criação de conta pelo admin:
  Admin preenche email + nome → POST /admin/users
    → gera senha temporária (8 chars) → cria User
    → envia email de boas-vindas com temp password

Fluxo auto-registo:
  /register → POST /auth/register { email, name, password }
    → cria User → redireciona para /login com mensagem

Fluxo alteração de senha (utilizador logado):
  POST /auth/change-password { current_password, new_password }
    → valida senha atual → atualiza hash
```

---

## Plano de Implementação

### Fase 1 — Infraestrutura de email SMTP

**Objetivo:** serviço capaz de enviar emails via SMTP próprio.

| Arquivo | O que muda |
|---|---|
| `backend-core/app/config.py` | Adicionar: `SMTP_HOST`, `SMTP_PORT` (int, default 587), `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM`, `SMTP_TLS` (bool, default True) |
| `backend-core/app/services/email_service.py` | Novo. `send_email(to, subject, html, text)` via `smtplib`. Templates: `render_welcome_email(name, temp_password, login_url)`, `render_reset_email(reset_url)` |

### Fase 2 — Recuperação e alteração de senha

**Objetivo:** utilizadores conseguem recuperar acesso sem intervenção manual.

| Arquivo | O que muda |
|---|---|
| `backend-core/app/models/password_reset_token.py` | Novo model: `id`, `user_id` (FK), `token` (UUID único), `expires_at`, `used_at` |
| `backend-core/app/models/__init__.py` | Importar `PasswordResetToken` |
| `backend-core/app/db.py` | Nova `ensure_password_reset_tokens_table()` |
| `backend-core/app/main.py` | Chamar `ensure_password_reset_tokens_table()` no startup |
| `backend-core/app/api/auth.py` | `POST /auth/forgot-password`, `POST /auth/reset-password`, `POST /auth/change-password` |
| `frontend-crm/src/pages/ForgotPassword.tsx` | Nova. Campo email + submit. Após envio: mensagem "Verifique o seu email." |
| `frontend-crm/src/pages/ResetPassword.tsx` | Nova. Lê `?token=` da URL. Form: nova senha + confirmar. |
| `frontend-crm/src/pages/Login.tsx` | Link "Esqueci a senha" → `/forgot-password` |
| `frontend-crm/src/App.tsx` | Rotas públicas `/forgot-password` e `/reset-password` |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `0dfb5ad` | config SMTP + email_service.py com send_email, render_welcome_email, render_reset_email |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `e4b0fcf` | backend: PasswordResetToken model + forgot/reset/change-password endpoints |
| 2 | `d3e74ff` | frontend-crm: ForgotPassword, ResetPassword, Register pages + Login actualizado |

### Fase 3 — Criação de conta: admin + auto-registo

**Objetivo:** admin cria contas pelo painel; clientes podem auto-registar-se.

| Arquivo | O que muda |
|---|---|
| `backend-core/app/api/admin.py` | `POST /admin/users` — cria User com senha temporária, envia email de boas-vindas |
| `backend-core/app/api/auth.py` | `POST /auth/register` aceita campo `name` opcional |
| `frontend-admin/src/pages/AdminUsers.tsx` | Botão "Criar conta" + modal (email + nome) |
| `frontend-admin/src/services/api.ts` | Método `createUser(email, name?)` |
| `frontend-crm/src/pages/Register.tsx` | Nova. Email + nome + senha + confirmar senha. Após sucesso → /login |
| `frontend-crm/src/App.tsx` | Rota pública `/register` |
| `frontend-crm/src/pages/Login.tsx` | Link "Não tem conta? Criar conta" → `/register` |

### Commits Fase 3

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `f9a1290` | POST /admin/users + modal "Criar conta" no AdminUsers |

---

## Checks de Validação

### Cenário P1 — Email de recuperação enviado
- [ ] Clicar "Esqueci senha" na página de login do frontend-crm
- [ ] Inserir email registado → submeter
- [ ] Confirmar: email chega na caixa de entrada com link de reset
- [ ] Confirmar: página mostra "Verifique o seu email"

### Cenário P2 — Reset com link funciona
- [ ] Clicar link no email → abrir `/reset-password?token=<token>`
- [ ] Preencher nova senha → submeter
- [ ] Confirmar: redireciona para login
- [ ] Confirmar: login com nova senha funciona

### Cenário P3 — Token expirado recusado
- [ ] Usar token com mais de 2h → confirmar: erro "Link expirado ou inválido"

### Cenário P4 — Admin cria conta → utilizador recebe email
- [ ] Painel admin → "Criar conta" → inserir email + nome → confirmar
- [ ] Confirmar: email de boas-vindas com senha temporária chega
- [ ] Confirmar: login com senha temporária funciona

### Cenário P5 — Auto-registo funciona
- [ ] Aceder `/register` no frontend-crm
- [ ] Preencher email + nome + senha → submeter
- [ ] Confirmar: redireciona para login com mensagem de sucesso
- [ ] Confirmar: login com credenciais recém-criadas funciona

### Cenário P6 — Alteração de senha (utilizador logado)
- [ ] Aceder página de conta no frontend-crm (a definir — ou testar via curl)
- [ ] Preencher senha atual + nova senha → confirmar
- [ ] Confirmar: login com nova senha funciona; senha antiga recusada

---

## Ajustes Possíveis Pós-Implementação

- Templates de email em HTML com estilo da marca AutoDigital
- Throttle em `forgot-password` (máximo N requests por email por hora)
- Expiração mais curta para senha temporária (forçar troca no primeiro login)
- Página de "Alterar senha" no frontend-crm (perfil do utilizador) — atualmente só via curl/API
