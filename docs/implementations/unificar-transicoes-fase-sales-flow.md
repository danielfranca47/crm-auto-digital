# Unificar `_ALLOWED_ADVANCE`/`_STAGE_ORDER` com a sequência de fases do Fluxo de Venda

**Branch:** (a definir)
**Status:** Aguardando Plan Mode

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`fix-intent-trigger-fase-entrada.md`.

Ao corrigir o bug de timing do `intent_trigger` na Camada 7 (Fluxo de Venda), foi
criada a constante `_SALES_FLOW_PHASE_SEQUENCE_BY_AGENT_MODE` em
`backend-executors/app/services/decision_engine.py`, mapeando a sequência de fases
ativas (`p0`→`p1`→`p2`→...) por `agent_mode_normalized` (`consultivo`/`direto`/`agenda`).

Já existia, no mesmo arquivo, uma lógica paralela e semanticamente equivalente:
`_ALLOWED_ADVANCE`/`_STAGE_ORDER` (`decision_engine.py:~3969`), usada pelos
guardrails de categoria (`apply_mother_category_guardrails()`,
`_apply_child_micro_adjustment()`, dentro de `compose_decision_output()`) para decidir
se o `suggested_category` de um lead pode avançar de X para Y no mesmo turno.

As duas estruturas divergem em vocabulário (`route_to`/categoria vs `phase_id`) e em
escopo (`_ALLOWED_ADVANCE` é único/global, não filtra por `agent_mode` — inclui
`pre-agendamento`/`agendamento` mesmo para agentes fora do grupo `agenda`; essa
filtragem é feita depois, separadamente, via checagem de `template_key`). Ter duas
fontes de verdade para "que transições são válidas" é um risco de divergência futura:
se uma for atualizada (ex.: um novo `agent_mode` ou uma nova fase) e a outra não, os
guardrails de categoria e o Fluxo de Venda podem discordar sobre o que é uma transição
válida.

**Evidência concreta observada (19/08/2026, investigação do perfil `id=5` local):**
`apply_mother_category_guardrails()` (`decision_engine.py:~4165`) só avança
`leads.category` quando `mother_decision.perceived_category` muda — e a Mãe mantém
`perceived_category` == `lead.category` por instrução própria do prompt ("quando em
dúvida, mantenha igual"), mesmo quando `route_to`/`effective_route_to` já aponta para
uma fase adiante no mesmo turno. Confirmado via log: lead saiu de `qualification`
direto para `pre-agendamento` persistido no banco, sem nunca persistir `apresentation`
entre os dois — apesar de `_evaluate_sales_flow_phases()` ter avaliado e disparado
corretamente os blocos da fase `apresentation` (`p2`) nesse mesmo turno, porque essa
função usa `effective_route_to` (decisão efêmera do turno), não a categoria persistida.
Ou seja: o Fluxo de Venda (fonte B) já não depende da categoria persistida para
funcionar corretamente turno a turno, mas a categoria persistida (fonte A, usada pelo
Kanban e por qualquer outro consumidor de `leads.category`) pode ficar
"desatualizada"/pular fases visíveis ao operador. Não causou nenhum bug de conteúdo
observável até agora (o Fluxo de Venda continua funcionando via `effective_route_to`),
mas é sintoma direto da duplicação de fonte de verdade descrita acima, e pode
manifestar-se de outras formas (ex.: Kanban mostrando o lead na coluna errada) à medida
que mais lógica passar a depender de `leads.category` persistido.

---

## Problemas Identificados (estado anterior)

1. **Duas fontes de verdade para transições de fase/categoria:**
   `_SALES_FLOW_PHASE_SEQUENCE_BY_AGENT_MODE` (`decision_engine.py`, introduzida no
   fix `fix-intent-trigger-fase-entrada`) e `_ALLOWED_ADVANCE`/`_STAGE_ORDER`
   (`decision_engine.py:~3969`, pré-existente) descrevem essencialmente o mesmo
   conceito — "a partir daqui, para onde o lead pode ir" — em vocabulários diferentes
   e sem nenhuma relação declarada entre elas.

---

## Abordagem

(A definir em Plan Mode — precisa avaliar se a unificação é uma tradução simples via
`_ROUTE_TO_PHASE_ID`/`_CATEGORY_TO_PHASE_ID` já existentes, ou se `_ALLOWED_ADVANCE`
tem nuances — como permitir saltos de `apresentation` direto para `closing` — que a
sequência linear por `agent_mode` não captura da mesma forma e que precisam ser
preservadas.)

---

## Plano de Implementação

(A preencher após diagnóstico em Plan Mode — ver
`docs/implementations/_guia-documentar-implementacao.md`, Passo 0.)

---

## Checks de Validação

(A definir junto com o plano de implementação.)
