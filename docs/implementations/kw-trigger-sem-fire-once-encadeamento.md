# Decidir comportamento de `kw_trigger` sem `fire_once` no encadeamento sequencial

**Branch:** `<a definir no Plan Mode>`
**Status:** Aguardando Plan Mode

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de `fix-fluxo-vendas-sequencial.md`.

As Fases 1 e 2 desse trabalho introduziram o conceito de gatilho "sequencial" —
`phase_trigger` ou `kw_trigger`/`intent_trigger` com `fire_once: true` — usado tanto
para o gating dentro da fase (`_evaluate_sales_flow_phases`, `_is_sequential_trigger_block`)
quanto para o guardrail que impede a Mãe de saltar a fase de apresentation inteira
(`_enforce_apresentation_sales_flow_pending`). Um `kw_trigger` **sem** `fire_once`
(pensado para disparar toda vez que o lead repetir uma palavra-chave, não só na
primeira) foi deliberadamente deixado de fora desse encadeamento — na prática, hoje:
- não é bloqueado por gatilhos sequenciais anteriores ainda não satisfeitos
- não bloqueia gatilhos sequenciais seguintes
- não conta como "pendência" para o guardrail de transição de fase

Essa decisão foi tomada porque não existe hoje nenhum registo persistido de "já
disparou" para um `kw_trigger` sem `fire_once` — ele é reavaliado a cada turno,
puramente a partir da mensagem actual, sem estado.

**Pergunta em aberto (a decidir em Plan Mode, com o utilizador):** faz sentido um
`kw_trigger` repetível também participar do encadeamento — ou seja, um utilizador
que configure um gatilho de palavra-chave sem "disparar só uma vez" no meio de uma
sequência esperaria que ele também "trave a vez" dos blocos seguintes até a
palavra-chave aparecer pela primeira vez? Ou o comportamento actual (transparente,
fora do encadeamento) já é o esperado para esse tipo de gatilho, e este item deveria
ser fechado sem mudança de código — só clarificação na documentação/UI do builder?

---

## Problemas Identificados (estado anterior)

1. Nenhum bug confirmado — comportamento actual é uma decisão de escopo deliberada
   da Fase 1, não um erro. Este item é sobre validar se essa decisão continua a
   fazer sentido à medida que utilizadores configuram sequências mais complexas no
   builder, ou se precisa de ajuste.

---

## Abordagem

A definir em Plan Mode. Se a decisão for "sim, deve participar", a abordagem mais
provável é: registar satisfação persistida para `kw_trigger` sem `fire_once`
também (ex.: um novo campo/lista separada de "primeira ocorrência", distinta de
`triggers_fired` para não mudar a semântica de re-disparo já existente) — precisa
de diagnóstico cuidadoso para não quebrar fluxos já configurados que dependem do
comportamento actual (reavaliação a cada turno, sem checkpoint).

---

## Plano de Implementação

A preencher após o diagnóstico em Plan Mode ser aprovado pelo utilizador.

**Arquivos prováveis:**
- `backend-executors/app/services/decision_engine.py` — `_is_sequential_trigger_block()`, `_evaluate_sales_flow_phases()`, `_enforce_apresentation_sales_flow_pending()`
- `backend-executors/tests/test_sales_flow_intent_trigger_phase_entry.py`
- `docs/architecture/sales-flow.md` — secção "Modelo sequencial de trigger"

---

## Checks de Validação

A preencher após o Plano de Implementação ser definido.
