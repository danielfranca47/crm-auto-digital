# Feature-Gates: Follow-up e Playground por Plano

**Branch:** `etapa-9-planos-limites`
**Status:** Todos os cenários validados (02/06/2026) — G2/G3 validados via teste directo de lógica; integração end-to-end pendente de reinício do servidor 8001

---

## Motivação

Os campos `follow_up_enabled` e `playground_monthly_limit` existem no DB (`plan_limits`) desde etapa-9-3, mas o endpoint de entitlements (`GET /me/entitlements`) ainda não os expõe. O backend-crm não tem qualquer verificação de plano antes de iniciar follow-up ou processar playground. Utilizadores no plano Start conseguem usar follow-up e fazer testes ilimitados no playground, o que contradiz a proposta de valor dos planos.

---

## Problemas Identificados (estado anterior)

1. **`follow_up_enabled` não exposto via entitlements (`backend-core/app/api/subscriptions.py:33`):** `UserLimits` não tem o campo; `_calculate_limits` não o computa.

2. **`playground_monthly_limit` não exposto via entitlements (mesmo ficheiro):** mesma situação.

3. **Sem gate de follow-up (`backend-crm/routes/leads.py:487`):** `start_followup_transition()` não verifica `follow_up_enabled` antes de processar.

4. **Sem gate de playground (`backend-crm/routes/playground.py:456`):** endpoint `/chat` não verifica quota mensal.

---

## Abordagem

```
Fase 1 (backend-core): UserLimits expõe follow_up_enabled e playground_monthly_limit
  → backend-crm recebe via current_user.entitlements["limits"]

Fase 2 (backend-crm): gate de follow-up
  start_followup_transition()
    → check_follow_up_enabled(entitlements)
    ├─ True  → processa normalmente
    └─ False → 403 { error: "follow_up_not_included" }

Fase 3 (backend-crm): gate de playground
  playground_chat()
    → check_playground_limit(user_id, entitlements, conn)
    ├─ None (ilimitado) → processa
    ├─ limite > uso_mensal → processa + incrementa contador
    └─ limite ≤ uso_mensal → 403 { error: "playground_limit_reached" }
```

---

## Plano de Implementação

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `6b30c58` | UserLimits + follow_up_enabled / playground_monthly_limit; _calculate_limits atualizado |

### Fase 1 — Expor feature-gates via entitlements (backend-core)

| Arquivo | O que muda |
|---|---|
| `backend-core/app/api/subscriptions.py` | `UserLimits` + 2 campos; `_calculate_limits()` computa-os |

### Fase 2 — Gate de follow-up (backend-crm)

| Arquivo | O que muda |
|---|---|
| `backend-crm/services/plan_gates.py` | Novo. `check_follow_up_enabled(entitlements)` |
| `backend-crm/routes/leads.py` | `start_followup_transition()`: chamar `check_follow_up_enabled` antes de processar |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `21635a2` | plan_gates.py + gate follow-up em start_followup_transition |

### Fase 3 — Gate de playground (backend-crm)

| Arquivo | O que muda |
|---|---|
| `backend-crm/services/plan_gates.py` | `check_playground_limit(user_id, entitlements, conn)` — tabela playground_usage_monthly |
| `backend-crm/routes/playground.py` | Endpoint `/chat`: chamar `check_playground_limit` antes de processar |

### Commits Fase 3

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `a6ccbab` | gate de playground — tabela mensal + 403 ao exceder limite |

---

## Checks de Validação

### Cenário G1 — Entitlements expõem os novos campos
- [x] Utilizador com `crm_start` → `GET /me/entitlements`: `follow_up_enabled: False`, `playground_monthly_limit: 5`
- [x] Utilizador com `crm_growth` → `follow_up_enabled: True`, `playground_monthly_limit: None`
- **Validado em:** 02/06/2026 — via curl na porta 8012 (novo código)

### Cenário G2 — Follow-up bloqueado no Start
- [x] `check_follow_up_enabled({"limits": {"follow_up_enabled": False}})` → 403 `follow_up_not_included`
- [x] Growth (True) → passa; Legado (sem campo) → passa (default True)
- **Validado em:** 02/06/2026 — teste directo de lógica via Python

### Cenário G3 — Playground limitado a 5/mês no Start
- [x] Usos 1 e 2 com limite=2 → passam
- [x] Uso 3 → 403 `playground_limit_reached`, `used: 2`
- [x] `playground_monthly_limit: None` (Growth) → ilimitado, sempre passa
- **Validado em:** 02/06/2026 — teste directo com DB em memória

### Cenário G4 — Utilizadores legados não são bloqueados
- [x] `crm_pro` → `follow_up_enabled: True`, `playground_monthly_limit: None`
- **Validado em:** 02/06/2026 — entitlements via curl na porta 8012

---

## Ajustes Possíveis Pós-Implementação

- Frontend-crm: mostrar mensagem de upgrade quando 403 follow_up_not_included
- Frontend-crm: indicador de usos restantes do playground no mês
- etapa-9-5 usa alertas quando usos de conversas IA se aproximam do limite
