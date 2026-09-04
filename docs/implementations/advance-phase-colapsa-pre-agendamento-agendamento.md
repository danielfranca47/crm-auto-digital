# `advance_phase` colapsa p3a/p3b em "apresentation" (categoria nunca vira pre-agendamento/agendamento)

**Branch:** `fix/advance-phase-colapsa-pre-agendamento-agendamento`
**Status:** Em andamento

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`unificar-transicoes-fase-sales-flow.md`.

Durante a investigação dessa implementação, foi encontrado `_PHASE_ID_TO_CATEGORY`,
duplicado identicamente em `backend-crm/routes/executor.py:266` e
`backend-crm/routes/playground.py:194`:

```python
_PHASE_ID_TO_CATEGORY = {
    "p1":  "qualification",
    "p2":  "apresentation",
    "p3a": "apresentation",
    "p3b": "apresentation",
    "p4":  "followup",
    "p5":  "closing",
}
```

Usado pela ação `advance_phase` do Fluxo de Venda (builder `CamadaFluxoVenda.tsx`,
tipo de ação num bloco de fase): quando esse bloco é configurado nas fases **p3a
(pré-agendamento)** ou **p3b (agendamento)**, a categoria persistida do lead
(`leads.category`) é sempre movida para `"apresentation"` — nunca para
`"pre-agendamento"`/`"agendamento"`. Ou seja, um operador que configure
"avançar de fase" dentro de p3a/p3b no builder nunca vê o lead realmente mover
para essas colunas do Kanban via essa ação — ele fica preso (ou volta) para
`apresentation`.

Isso é inconsistente com `_CATEGORY_TO_PHASE_ID` (`decision_engine.py:1112`,
local a `_collect_intent_triggers_for_lead_phase`), que mapeia p3a→`pre_agendamento`
e p3b→`agendamento` corretamente, sem colapsar — ou seja, já existe no
código uma tradução correta para o mesmo conceito, só que numa direção/lugar
diferente de `_PHASE_ID_TO_CATEGORY`.

---

## Diagnóstico (Plan Mode)

### 1. O bug é observável na prática, ou só risco teórico?

Consultada diretamente a base local `backend-core/core.db` (`ai_profiles.sales_flow`).
Existem 2 perfis com `agent_mode` do grupo `agenda` (`sdr_scheduler`/`sdr_padrao`
e `agenda`/`hybrid_scheduler`) com fases `p3a`/`p3b` presentes no JSON, mas
**nenhum bloco `avancar_fase` configurado nelas ainda** (`blocks: []`).

**Conclusão:** risco teórico, ainda não acionado — nenhum utilizador real foi
afetado até agora, mas qualquer configuração futura desse tipo cairia no bug.

### 2. É só trocar os 2 valores, ou há razão deliberada para o colapso?

Investigados os guardrails de `template_key`/`_SCHEDULING_AGENT_TEMPLATES` em
`decision_engine.py` (linhas ~4695-5175):

- `_STAGE_ORDER`/`_ALLOWED_ADVANCE` (`decision_engine.py:4695-4701`) já usam
  `"pre-agendamento"`/`"agendamento"` (com hífen) como categorias válidas de
  primeira classe.
- O guardrail da linha 5084 (`suggested_category in {"pre-agendamento",
  "agendamento"} and template_key not in _SCHEDULING_AGENT_TEMPLATES` →
  rebaixa para `"apresentation"`) atua sobre `suggested_category` calculada
  **dentro do `decide()` do decision_engine** (backend-executors) — caminho
  totalmente separado de `_PHASE_ID_TO_CATEGORY`, que só é consultado em
  `backend-crm` ao despachar a `system_action` `advance_phase`. Não há
  interação entre os dois.
- `LEAD_CATEGORIES_SET` (`backend-crm/services/jobs_service.py:101-116`) já
  inclui `"pre-agendamento"` e `"agendamento"` como categorias válidas,
  aceites por `apply_suggested_category()` (usada pelo executor real) — a
  troca não introduz um valor desconhecido ao resto do sistema.
- As fases p3a/p3b só são renderizadas no builder e só existem na sequência
  do `agent_mode` para o grupo `agenda`
  (`_SALES_FLOW_PHASE_SEQUENCE_BY_AGENT_MODE`), grupo que corresponde
  exatamente aos `template_key` em `_SCHEDULING_AGENT_TEMPLATES`
  (`sdr_padrao`, `hybrid_scheduler`) — logo o guardrail da linha 5084 nunca
  rebaixaria uma categoria vinda de um perfil que legitimamente configurou
  blocos em p3a/p3b.

**Conclusão:** não há razão deliberada para o colapso — é um bug de
digitação/cópia. A correção é só trocar os 2 valores no dicionário, em ambos
os arquivos (mantendo-os idênticos, como já são hoje).

### 3. Escopo: só `advance_phase`, ou também `_CATEGORY_TO_PHASE_ID`?

`_CATEGORY_TO_PHASE_ID` (`decision_engine.py:1112`) já mapeia corretamente
`pre_agendamento→p3a` e `agendamento→p3b` — não precisa de nenhuma mudança.
Escopo fica restrito a `_PHASE_ID_TO_CATEGORY` nos 2 arquivos do `backend-crm`.

---

## Problemas Identificados (estado anterior)

1. **`_PHASE_ID_TO_CATEGORY` colapsa p3a/p3b em "apresentation":**
   `backend-crm/routes/executor.py:266`, `backend-crm/routes/playground.py:194`
   — usados em `executor.py:328`, `playground.py:828`, `playground.py:962`.
2. **Inconsistência com `_CATEGORY_TO_PHASE_ID`:** `decision_engine.py:1112`
   mapeia p3a/p3b corretamente, sem colapsar — duas fontes divergentes para a
   mesma tradução phase_id↔categoria.

---

## Abordagem

Corrigir `_PHASE_ID_TO_CATEGORY` nos dois arquivos para usar as categorias
corretas (`"pre-agendamento"`/`"agendamento"`, com hífen — mesma grafia usada
em `_STAGE_ORDER`/`_ALLOWED_ADVANCE`/`LEAD_CATEGORIES_SET`). Nenhuma outra
mudança de código é necessária: `apply_suggested_category()` (executor real)
e `_update_lead_category()` (playground) já aceitam essas strings sem
alteração; o Kanban (`frontend-crm`) já tem colunas/labels para
`pre-agendamento`/`agendamento`.

---

## Plano de Implementação

### Fase 1 — Corrigir `_PHASE_ID_TO_CATEGORY` em executor.py e playground.py

**Objetivo:** fazer `advance_phase` mover o lead para as categorias corretas
quando configurado nas fases p3a/p3b.

| Arquivo | O que muda |
|---|---|
| `backend-crm/routes/executor.py` | `_PHASE_ID_TO_CATEGORY["p3a"]` → `"pre-agendamento"`, `["p3b"]` → `"agendamento"` |
| `backend-crm/routes/playground.py` | idêntico |

```python
# ANTES (ambos os arquivos)
_PHASE_ID_TO_CATEGORY = {
    "p1":  "qualification",
    "p2":  "apresentation",
    "p3a": "apresentation",
    "p3b": "apresentation",
    "p4":  "followup",
    "p5":  "closing",
}

# DEPOIS
_PHASE_ID_TO_CATEGORY = {
    "p1":  "qualification",
    "p2":  "apresentation",
    "p3a": "pre-agendamento",
    "p3b": "agendamento",
    "p4":  "followup",
    "p5":  "closing",
}
```

---

## Checks de Validação

### Cenário P1 — Playground: `avancar_fase` em p3a move para pre-agendamento
- [ ] Perfil de teste com `agent_mode=agenda`/`sdr_scheduler` (template
      `sdr_padrao` ou `hybrid_scheduler`)
- [ ] Configurar no builder um bloco `avancar_fase` na fase p3a com
      `target_phase="p3a"`, associado a um trigger simples (ex.: `kw_trigger`)
- [ ] Disparar o trigger no Playground
- [ ] Confirmar: `lead.category` muda para `"pre-agendamento"` (não fica em
      `"apresentation"`)

### Cenário P2 — Playground: `avancar_fase` em p3b move para agendamento
- [ ] Mesmo perfil, bloco `avancar_fase` na fase p3b (`target_phase="p3b"`)
- [ ] Disparar o trigger
- [ ] Confirmar: `lead.category` muda para `"agendamento"`

### Cenário P3 — Regressão: p2/p4/p5 continuam corretos
- [ ] Confirmar que `avancar_fase` configurado em p2 continua movendo para
      `"apresentation"`, p4 para `"followup"`, p5 para `"closing"` (sem
      regressão nas fases não tocadas)

---

## Ajustes Possíveis Pós-Implementação

Nenhum identificado — correção pontual e completa dentro do escopo
investigado.
