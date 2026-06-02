# Feature-Gates: Follow-up e Playground por Plano

**Branch:** `etapa-9-planos-limites`
**Status:** Em andamento

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

### Fase 1 — Expor feature-gates via entitlements (backend-core)

| Arquivo | O que muda |
|---|---|
| `backend-core/app/api/subscriptions.py` | `UserLimits` + 2 campos; `_calculate_limits()` computa-os |

### Fase 2 — Gate de follow-up (backend-crm)

| Arquivo | O que muda |
|---|---|
| `backend-crm/services/plan_gates.py` | Novo. `check_follow_up_enabled(entitlements)` |
| `backend-crm/routes/leads.py` | `start_followup_transition()`: chamar `check_follow_up_enabled` antes de processar |

### Fase 3 — Gate de playground (backend-crm)

| Arquivo | O que muda |
|---|---|
| `backend-crm/services/plan_gates.py` | `check_playground_limit(user_id, entitlements, conn)` usando padrão `consume_monthly_units` |
| `backend-crm/routes/playground.py` | Endpoint `/chat`: chamar `check_playground_limit` antes de processar |

---

## Checks de Validação

### Cenário G1 — Entitlements expõem os novos campos
- [ ] Utilizador com `crm_start` → `GET /me/entitlements` contém `follow_up_enabled: false` e `playground_monthly_limit: 5`
- [ ] Utilizador com `crm_growth` → `follow_up_enabled: true`, `playground_monthly_limit: null`

### Cenário G2 — Follow-up bloqueado no Start
- [ ] Utilizador com `crm_start` → tentar iniciar follow-up → 403 com `error: follow_up_not_included`
- [ ] Utilizador com `crm_growth` → iniciar follow-up → funciona normalmente

### Cenário G3 — Playground limitado a 5/mês no Start
- [ ] Utilizador com `crm_start` → primeiros 5 usos do playground funcionam
- [ ] 6.º uso → 403 com `error: playground_limit_reached`
- [ ] Utilizador com `crm_growth` → usos ilimitados

### Cenário G4 — Utilizadores sem plano (legados) não são bloqueados
- [ ] Utilizador com `crm_pro` (legado) → follow-up e playground funcionam normalmente
- [ ] `follow_up_enabled` default é `True` para planos sem o campo definido

---

## Ajustes Possíveis Pós-Implementação

- Frontend-crm: mostrar mensagem de upgrade quando 403 follow_up_not_included
- Frontend-crm: indicador de usos restantes do playground no mês
- etapa-9-5 usa alertas quando usos de conversas IA se aproximam do limite
