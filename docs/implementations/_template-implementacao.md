# [TEMPLATE] Nome da Feature ou Fix

> Este arquivo é um exemplo concreto preenchido. Use-o como referência visual
> ao criar um novo arquivo de implementação. Para o processo completo (Plan Mode,
> ciclo de vida, regras de escrita), ver `_guia-documentar-implementacao.md`.

---

**Branch:** `feat/etapa-X-Y-slug-descritivo` (ou `fix/...` para correções)
**Status:** Em andamento
**Sprint:** `docs/plans/plano-sprint-YYYY-MM-DD.md` *(remover linha se não veio de sprint plan)*

---

## Motivação

O sistema fazia X ao acontecer Y, mas o comportamento esperado era Z. O utilizador
reportou que ao tentar A, recebia erro B sem indicação de como resolver.

Causa raiz identificada: o handler `foo.py` não distinguia caso X de caso Y e
aplicava sempre o comportamento padrão.

---

## Problemas Identificados (estado anterior)

1. **Nome do problema (arquivo:linha):** `backend-crm/routes/foo.py:45` — a função
   `handle_foo()` retornava 400 sem payload quando o campo `bar` estava ausente,
   deixando o frontend sem informação para exibir ao utilizador.

2. **Estado local corrompido após erro:** `frontend-crm/src/contexts/FooContext.tsx` —
   o update optimista não revertia em caso de falha HTTP, deixando o lead na
   coluna errada no Kanban.

3. **Sem interface para acção manual:** Não havia forma de o utilizador corrigir
   manualmente o estado X — só a IA o fazia.

---

## Abordagem

```
Utilizador tenta mover lead → PUT /api/leads/{id}
  → backend verifica campo obrigatório
  ├─ campo presente → 200 OK
  └─ campo ausente → 409 { error: "foo_incomplete", missing: ["campo_a", "campo_b"] }
       → frontend reverte update optimista
       → toast actionable: "Preencha os campos X antes de avançar"
```

---

## Plano de Implementação

### Fase 1 — Backend: validação e resposta estruturada

**Objetivo:** retornar erro 409 com payload que indique o que falta

| Arquivo | O que muda |
|---|---|
| `backend-crm/routes/leads.py` | Novo check antes do PATCH; retorna `{error, missing}` em vez de 400 genérico |
| `backend-crm/services/foo_guardrail.py` | Nova função `check_foo_complete(lead_id, user_id)` |

```python
# ANTES — erro opaco
if not lead.get("bar"):
    raise HTTPException(status_code=400, detail="Campo obrigatório ausente")

# DEPOIS — erro com contexto
missing = check_foo_complete(lead_id, user_id)
if missing:
    raise HTTPException(status_code=409, detail={"error": "foo_incomplete", "missing": missing})
```

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `abc1234` | backend: check_foo_complete + 409 estruturado |

**Detalhes do commit `abc1234`:**
- `backend-crm/routes/leads.py` — importa `check_foo_complete`; novo bloco de validação antes do PATCH
- `backend-crm/services/foo_guardrail.py` — nova função criada; lê `lead_qualification_state`

---

### Fase 2 — Frontend: revert optimista + toast actionable

**Objetivo:** impedir que o Kanban fique dessincronizado após 409

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/contexts/LeadsContext.tsx` | `moveLead`: snapshot antes do optimistic update; revert no catch de 409 |
| `frontend-crm/src/components/KanbanBoard.tsx` | Interpreta `error: "foo_incomplete"` e exibe toast com link para o card |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `def5678` | frontend: revert optimista + toast actionable para foo_incomplete |

---

## Checks de Validação

### Cenário P1 — Seção aparece quando configurado (playground / UI)
- [x] Abrir card de lead com AI Profile com `foo_fields` configurados
- [x] Confirmar: seção "Foo" renderiza com os campos e badge de pendentes
- **Validado em:** 28/05/2026 — 4 campos visíveis, badge "2 pendentes"

### Cenário P2 — Editar e salvar persiste
- [x] Clicar "Editar" → inputs aparecem
- [x] Preencher campo → Salvar → PATCH retorna 200
- [x] Badge actualiza de "2 pendentes" para "1 pendente"
- **Validado em:** 28/05/2026 — campo "X" salvo, badge mudou

### Cenário P3 — Badge "Completo" quando todos required preenchidos
- [ ] Preencher todos os required fields
- [ ] Confirmar: badge verde "Completo" aparece
- **Pendente:** requer preencher os campos restantes no lead de teste

### Cenário C1 — 409 reverte lead no Kanban (WhatsApp real)
- [x] Arrastar lead com campos pendentes para coluna seguinte
- [x] Confirmar: lead reverte para coluna original
- [x] Toast "Preencha os campos X antes de avançar" aparece
- **Validado em:** 28/05/2026 — revert confirmado, toast exibido com texto correto

---

## Fase 3 — Diagnóstico + Fix: campo X causava crash (29/05/2026)

### Problema identificado

Ao abrir o card de um lead sem `ai_profile` configurado, a seção Foo crashava com
`TypeError: Cannot read property 'foo_fields' of undefined`. O `useEffect` tentava
acessar `aiProfile.foo_fields` antes da chamada HTTP completar.

Causa raiz: `getAiProfileMe()` estava sendo chamada pelo namespace errado
(`api.getAiProfileMe()` em vez de `api.core.getAiProfileMe()`).

### Correção

| Arquivo | Mudança |
|---|---|
| `frontend-crm/src/components/FooSection.tsx` | `api.getAiProfileMe()` → `api.core.getAiProfileMe()` |

### Commits Fix

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `ghi9012` | fix: namespace correto para getAiProfileMe em FooSection |

---

## Ajustes Possíveis Pós-Implementação

- P3 (badge "Completo") pode ser validado quando o utilizador preencher os campos restantes.
- Se o número de campos for grande (>8), a seção poderia ter collapse/expand.
- Futuramente: ao preencher manualmente e tentar mover, o guardrail poderia ser
  bypassável com confirmação directa em vez de ir ao card.
