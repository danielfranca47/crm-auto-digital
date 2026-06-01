# Admin Painel — Informações Completas de Usuários

**Branch:** `etapa-9-planos-limites`
**Status:** Em andamento — checks A1 e regressão validados; A2/A3 pendentes de dados de teste

---

## Motivação

O painel admin (`AdminUsers.tsx`) mostra apenas email e extensões ativas. Não é possível ver o plano contratado, datas de assinatura, status da conta ou nome do cliente — informações essenciais para administrar o SaaS. O modelo `User` também não tem coluna `name`, apesar de já existir o campo no schema Pydantic como fallback silencioso.

---

## Problemas Identificados (estado anterior)

1. **Sem coluna `name` no model User (`backend-core/app/models/user.py`):** `name` é referenciado via `getattr(u, "name", None)` no endpoint sem existir na tabela. O campo é sempre `null`.

2. **Endpoint `GET /admin/users` retorna dados insuficientes (`backend-core/app/api/admin.py:80`):** Retorna apenas `id`, `email`, `name`, `enabled_extensions`. Falta: `status`, `created_at`, plano ativo, status da assinatura, datas do período.

3. **Frontend AdminUsers sem informações de negócio (`frontend-admin/src/pages/AdminUsers.tsx`):** Lista email + badges de extensão. Sem plano, sem datas, sem status — impossível gerir clientes pelo painel.

---

## Abordagem

```
GET /admin/users
  → query User
  → LEFT JOIN Subscription (status=active) + Plan
  → retorna: id, email, name, status, created_at,
             plan_name, plan_code, sub_status, sub_period_end

Frontend AdminUsers
  → tabela: nome/email | plano (badge) | status | membro desde | período até
  → modal de extensões mantido
  → botão "Criar conta" (implementado na etapa-9-2)
```

---

## Plano de Implementação

### Fase 1 — Backend: migração + endpoint enriquecido

**Objetivo:** adicionar coluna `name` à tabela `users` e enriquecer `GET /admin/users` com dados de assinatura e plano.

| Arquivo | O que muda |
|---|---|
| `backend-core/app/models/user.py` | Adicionar coluna `name` (String, nullable) |
| `backend-core/app/db.py` | Nova função `ensure_user_columns()` que adiciona `name` via ALTER TABLE idempotente |
| `backend-core/app/main.py` | Chamar `ensure_user_columns()` no `on_startup` |
| `backend-core/app/api/admin.py` | Novo `UserAdminOut` com campos completos; enriquecer query com Subscription+Plan |

### Fase 2 — Frontend: tabela rica

**Objetivo:** exibir no AdminUsers as informações completas de cada usuário.

| Arquivo | O que muda |
|---|---|
| `frontend-admin/src/services/api.ts` | Atualizar tipo `AdminUser` com novos campos |
| `frontend-admin/src/pages/AdminUsers.tsx` | Tabela: nome/email, plano (badge colorido por plano), status (badge), membro desde, período de assinatura |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `2c1e662` | backend: coluna name + ensure_user_columns + endpoint enriquecido |

**Detalhes do commit `2c1e662`:**
- `backend-core/app/models/user.py` — coluna `name` adicionada ao model
- `backend-core/app/db.py` — `ensure_user_columns()` com ALTER TABLE idempotente para SQLite/PG
- `backend-core/app/main.py` — `ensure_user_columns()` chamado no startup
- `backend-core/app/api/admin.py` — `UserAdminOut` com 6 campos novos; query faz lookup de Subscription + Plan por user

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `927b415` | frontend: AdminUsers tabela rica com plano, datas, status |
| 2 | `de7e01b` | fix: grid `1fr` colapsava para 36px — corrigido para `minmax(0,1fr)` |

**Detalhes do commit `927b415`:**
- `frontend-admin/src/services/api.ts` — tipo `AdminUser` com 5 campos novos
- `frontend-admin/src/pages/AdminUsers.tsx` — tabela 6 colunas; badge de plano colorido por tier; busca por nome

**Detalhes do commit `de7e01b`:**
- `frontend-admin/src/pages/AdminUsers.tsx` — grid template `1fr` → `minmax(0,1fr)`, colunas fixas reduzidas de `[1fr_140px_90px_110px_110px_100px]` para `[minmax(0,1fr)_105px_75px_95px_95px_80px]`

---

## Checks de Validação

### Cenário A1 — Usuário com assinatura ativa aparece com plano
- [x] Abrir AdminUsers
- [x] Confirmar: coluna "Plano" mostra nome do plano (CRM Pro / CRM Free)
- [x] Confirmar: "Membro desde" mostra a data de criação da conta
- **Validado em:** 01/06/2026 — 4 utilizadores visíveis, badges CRM Pro/CRM Free, datas corretas; busca por email filtra para 1 resultado; modal de extensões + save funcionam
- **Fix detectado:** grid `1fr` colapsava para 36px — corrigido para `minmax(0,1fr)` + colunas fixas reduzidas (`de7e01b`)

### Cenário A2 — Usuário sem assinatura ativa
- [⏭️] Confirmar: coluna "Plano" mostra "Sem plano"
- [⏭️] Confirmar: não causa erro na listagem
- **Motivo skip:** todos os utilizadores de teste têm assinatura ativa; código cobre o caminho com `if sub and sub.plan else None` (backend) + `?? "Sem plano"` (frontend)

### Cenário A3 — Campo `name` persiste e aparece
- [⏭️] Criar user com nome via endpoint (etapa-9-2) ou editar diretamente
- [⏭️] Confirmar: nome aparece na tabela do admin
- **Motivo skip:** campo `name` só será preenchido após etapa-9-2 (criação de conta); validar em conjunto

---

## Ajustes Possíveis Pós-Implementação

- Ordenação clicável por coluna (membro desde, plano)
- Filtro por plano no campo de busca
- Botão "Criar conta" será adicionado na etapa-9-2
