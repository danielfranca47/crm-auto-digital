# `advance_phase` colapsa p3a/p3b em "apresentation" (categoria nunca vira pre-agendamento/agendamento)

**Branch:** (a definir)
**Status:** Aguardando Plan Mode

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

**Contexto crítico apontado pelo utilizador antes de investigar:** as fases
p3a/p3b só existem no pipeline do `agent_mode = "agenda"`
(`_SALES_FLOW_PHASE_SEQUENCE_BY_AGENT_MODE["agenda"]` inclui p3a/p3b;
`consultivo` e `direto` não). Em particular, o **Agente 2 (`direto` — venda
direta/closer)** não foi desenhado para usar pré-agendamento/agendamento — o
builder já restringe a renderização de p3a/p3b a `agentGroup === 'agenda'`
(ver `docs/architecture/sales-flow.md`, tabela de fases). A investigação
precisa confirmar, antes de propor a correção:

1. Se o bug é observável na prática (algum perfil real com `agent_mode=agenda`
   já configurou `advance_phase` em p3a/p3b?) ou só um risco teórico ainda não
   acionado.
2. Se a correção é só trocar os 2 valores no dicionário (p3a→`pre-agendamento`,
   p3b→`agendamento`), ou se há alguma razão deliberada para o colapso atual
   (ex.: os guardrails de `template_key`/`_SCHEDULING_AGENT_TEMPLATES` em
   `decision_engine.py` que rebaixam essas categorias fora de agentes de
   agendamento — around linha ~4998 — podem depender implicitamente desse
   colapso em algum caminho não óbvio).
3. Escopo exato: só `advance_phase` (executor.py + playground.py), ou também
   `_CATEGORY_TO_PHASE_ID` precisa ficar consistente/ser unificado com o
   dicionário corrigido.

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

(A definir em Plan Mode — ver Passo 0 de
`docs/implementations/_guia-documentar-implementacao.md`. Ler
`_SCHEDULING_AGENT_TEMPLATES`/guardrails de `template_key` em
`decision_engine.py` e a jornada completa da ação `advance_phase` no builder
antes de propor a correção, para confirmar que trocar o valor no dicionário
não quebra nenhum guardrail que dependa do colapso atual.)

---

## Plano de Implementação

(A preencher após diagnóstico em Plan Mode.)

---

## Checks de Validação

(A definir junto com o plano de implementação.)
