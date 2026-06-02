# Planos Correctos + Admin Atribuir Plano

**Branch:** `etapa-9-planos-limites`
**Status:** Em andamento

---

## Motivação

O seed de planos tem nomes de desenvolvimento (`crm_free`, `crm_basic`, `crm_pro`) que não correspondem ao modelo de negócio definido (Start/Growth/Internal). O modelo `PlanLimits` não tem campos de feature-gate (`follow_up_enabled`, `playground_monthly_limit`). O painel admin mostra o plano de cada utilizador mas não tem forma de o atribuir ou alterar. Esta etapa corrige tudo isso e entrega gestão manual de planos pelo painel.

---

## Problemas Identificados (estado anterior)

1. **Planos errados no seed (`backend-core/app/seed.py:78`):** `crm_free`/`crm_basic`/`crm_pro` com limites de desenvolvimento, não os planos comerciais definidos.

2. **Sem feature-gates em PlanLimits (`backend-core/app/models/plan_limits.py`):** colunas `follow_up_enabled` e `playground_monthly_limit` inexistentes.

3. **Sem `trial_ends_at` em Subscription (`backend-core/app/models/subscription.py`):** impossível marcar contas de trial.

4. **Sem endpoint admin para atribuir plano (`backend-core/app/api/admin.py`):** admin não consegue mudar o plano de um utilizador via painel.

5. **Sem UI de atribuição de plano (`frontend-admin/src/pages/AdminUsers.tsx`):** painel mostra plano em read-only, sem controlo para alterar.

---

## Abordagem

```
Admin abre modal "Plano" num utilizador
  → dropdown de planos CRM disponíveis (GET /plans?product_code=crm)
  → opção "Trial 7 dias" (checkbox)
  → confirmar → POST /admin/users/{id}/subscription
      → desactiva subscription activa existente (status=cancelled)
      → cria nova Subscription com plan + period_end
      → se trial: sets trial_ends_at + period_end = now + 7 dias
  → frontend recarrega lista → novo plano aparece no badge
```

---

## Plano de Implementação

### Fase 1 — Backend: schema + seed

**Objetivo:** planos comerciais correctos no DB com limites e feature-gate columns.

| Arquivo | O que muda |
|---|---|
| `backend-core/app/models/plan_limits.py` | Adicionar `follow_up_enabled` (Boolean, default True), `playground_monthly_limit` (Integer nullable) |
| `backend-core/app/models/subscription.py` | Adicionar `trial_ends_at` (DateTime nullable) |
| `backend-core/app/db.py` | `ensure_plan_limits_columns()` e `ensure_subscription_columns()` |
| `backend-core/app/main.py` | Chamar ambos no startup |
| `backend-core/app/seed.py` | Adicionar `crm_start`, `crm_growth`, `crm_internal`; manter planos existentes |

### Fase 2 — Backend: endpoint admin atribuir plano

**Objetivo:** `POST /admin/users/{id}/subscription` atribui plano e activa subscription.

| Arquivo | O que muda |
|---|---|
| `backend-core/app/api/admin.py` | Novo endpoint `POST /admin/users/{user_id}/subscription` |

### Fase 3 — Frontend admin: modal de plano

**Objetivo:** botão "Plano" no painel abre modal para atribuir/alterar plano.

| Arquivo | O que muda |
|---|---|
| `frontend-admin/src/services/api.ts` | Métodos `listPlans()` e `assignPlan()` |
| `frontend-admin/src/pages/AdminUsers.tsx` | Botão "Plano" + modal com dropdown + opção trial |

---

## Checks de Validação

### Cenário S1 — Planos correctos no DB após restart
- [ ] Reiniciar backend-core → confirmar `crm_start`, `crm_growth`, `crm_internal` criados no DB
- [ ] `GET /plans?product_code=crm` retorna os 3 novos planos
- [ ] `crm_start` tem `max_leads=500`, `follow_up_enabled=false`, `playground_monthly_limit=5`
- [ ] `crm_internal` tem todos os limites null

### Cenário S2 — Admin atribui plano pelo painel
- [ ] Painel admin → Usuários → clicar "Plano" num utilizador
- [ ] Modal abre com dropdown de planos
- [ ] Seleccionar `crm_start` → confirmar → badge do utilizador actualiza para "Start"
- [ ] Seleccionar `crm_growth` → confirmar → badge actualiza para "Growth"

### Cenário S3 — Trial 7 dias
- [ ] Modal → marcar "Trial 7 dias" → confirmar
- [ ] `GET /me/entitlements` retorna plano activo
- [ ] BD: `trial_ends_at` preenchido; `current_period_end` = now + 7 dias

### Cenário S4 — Entitlements correctos após atribuição
- [ ] Atribuir `crm_start` a utilizador → `GET /me/entitlements` retorna `max_leads: 500`
- [ ] Atribuir `crm_internal` → `GET /me/entitlements` retorna `max_leads: null`

---

## Ajustes Possíveis Pós-Implementação

- Mostrar data de expiração do trial no badge do painel
- Enviar email automático quando trial expira (etapa futura)
- etapa-9-4 usa `follow_up_enabled` e `playground_monthly_limit` para os feature-gates
