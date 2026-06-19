# Desativar roteamento para "closing" nos agentes de agendamento (hybrid_scheduler + sdr_padrao)

**Branch:** `main`
**Status:** Em andamento

---

## Motivação

No teste de Playground da Lara (`template_key=hybrid_scheduler`, `agent_mode=agenda`,
`requires_handoff=true`), ao confirmar um horário de sessão ("sim"), a LLM Mãe
decidiu `route_to="closing"` — interpretação livre de "confirmação = sinal de
fechamento", sem nenhuma regra específica do template dizendo o contrário. Isso
disparou o guardrail `guardrail_sdr_escalate_closing` (silencia o bot,
`message_text=""`) — comportamento correto quando "closing" é real, mas aqui é
falso positivo: este agente faz agendamento de sessões recorrentes sem checkout;
confirmar um horário não é uma venda fechada.

Causa raiz: já existia um guardrail parcial (`guardrail_hybrid_scheduler_no_closing`,
em `compose_decision_output()`) que impedia a categoria persistida do lead de virar
"closing" para `hybrid_scheduler`, mas atuava tarde demais — depois que
`effective_route_to` já tinha sido fixado em `mother_decision.route_to` e depois que
`_is_sdr_escalate_closing()` já tinha avaliado `route_to`/`perceived_category`
diretamente. Por isso o bot ficava mudo mesmo a categoria do Kanban nunca
chegando a "closing" de fato.

O utilizador decidiu desativar/ocultar a rota "closing" para o agente híbrido
agendador (Fase 1), e depois pediu para aplicar a mesma correção a `sdr_padrao`
(Fase 2) — o outro template do grupo `_SCHEDULING_AGENT_TEMPLATES` que também tem
fases de pré-agendamento/agendamento sem etapa comercial de fechamento. Reativar
"closing" para negociação de pacotes/planos de recorrência em campanhas de
follow-up fica como melhoria futura, fora de escopo.

---

## Problemas Identificados (estado anterior)

1. **Guardrail de categoria atua tarde demais:** `backend-executors/app/services/decision_engine.py`
   — `guardrail_hybrid_scheduler_no_closing` (em `compose_decision_output()`) só
   corrigia `suggested_category`, não `mother_decision.route_to`/`perceived_category`,
   que já alimentaram `route_for_child` e `_is_sdr_escalate_closing()` antes disso.
2. **Sem regra na Mãe para "depois de agendamento confirmado":** o prompt da Mãe
   não tem nenhuma instrução dizendo que "closing" não existe nestes templates —
   ela cai na heurística genérica "confirmação = fechamento".
3. **(Fase 2) Correção restrita a `hybrid_scheduler`:** a Fase 1 só cobria
   `template_key == "hybrid_scheduler"`, mas `sdr_padrao` tem exatamente o mesmo
   problema (mesmo grupo `_SCHEDULING_AGENT_TEMPLATES`, mesmas fases p3a/p3b).

---

## Abordagem

```
Mother LLM decide route_to/perceived_category
  → _enforce_qualification_route_when_missing()
  → _enforce_greeting_first()
  → _enforce_scheduling_agent_no_closing()
       se template_key in _SCHEDULING_AGENT_TEMPLATES ({"sdr_padrao", "hybrid_scheduler"})
       e route/perceived == "closing":
         fallback = categoria atual (se já em agendamento/pre-agendamento)
                    senão "apresentation"
         route_to / perceived_category ← fallback
  → route_for_child / _is_sdr_escalate_closing() nunca mais veem "closing"
```

Tanto `app/runners/whatsapp.py` (WhatsApp real) quanto `app/api/playground_internal.py`
(Playground) chamam a mesma `decision_engine.decide()` — a correção vale para os
dois caminhos automaticamente.

---

## Plano de Implementação

### Fase 1 — Backend: enforcement para hybrid_scheduler + documentação

| Arquivo | O que mudou |
|---|---|
| `backend-executors/app/services/decision_engine.py` | Nova função `_enforce_hybrid_scheduler_no_closing()`, chamada em `decide()` logo após `_enforce_greeting_first()` |
| `docs/architecture/pipeline-phases.md` | Nota sobre "closing" desativado por design para `hybrid_scheduler` |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `ec3337d` | feat: desativar roteamento para closing no agente híbrido agendador |
| 2 | `8b44e94` | docs: registar hash do commit ec3337d no arquivo de implementação |
| 3 | `2dcd3ff` | test: regressão automatizada (3 testes) para o cenário local |

### Fase 2 — Generalizar para sdr_padrao

| Arquivo | O que mudou |
|---|---|
| `backend-executors/app/services/decision_engine.py` | `_enforce_hybrid_scheduler_no_closing()` renomeada para `_enforce_scheduling_agent_no_closing()`; condição passa de `template_key != "hybrid_scheduler"` para `template_key not in _SCHEDULING_AGENT_TEMPLATES`; tag de reason `hybrid_scheduler_closing_disabled` → `scheduling_agent_closing_disabled`; o backstop antigo `guardrail_hybrid_scheduler_no_closing` (em `compose_decision_output()`) passa a usar a mesma checagem por conjunto, renomeado para `guardrail_scheduling_agent_no_closing` |
| `backend-executors/tests/test_hybrid_scheduler_no_closing.py` → `test_scheduling_agent_no_closing.py` | Testes parametrizados para `["hybrid_scheduler", "sdr_padrao"]`; teste de regressão passa a usar `closer_agressivo` (em vez de `sdr_padrao`, que deixou de ser o caso negativo) |
| `docs/architecture/pipeline-phases.md` | Nota movida de "Agent 3 (hybrid_scheduler)" para uma secção própria "Agentes de agendamento (sdr_padrao, hybrid_scheduler)", explicitando que `consultor_especialista` (que partilha `agent_1` com `sdr_padrao` na tabela de mapeamento) **não** é afetado |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | _(pendente)_ | feat: generalizar desativação de closing para sdr_padrao |

---

## Checks de Validação

### Cenário P1 — Confirmação de horário não fica muda (validado localmente, via teste automatizado)
- [x] `test_scheduling_agent_no_closing.py::test_booking_confirmation_does_not_escalate_to_silent_closing` (parametrizado `hybrid_scheduler` + `sdr_padrao`) — simula o caso real (`requires_handoff=true`, lead em "agendamento", Mãe decide `closing`)
- [x] Confirmado: `decision.message_text != ""`, `next_action != "ignore"`
- [x] Confirmado: `reason` contém `scheduling_agent_closing_disabled:agendamento`, `trace.guardrail_sdr_escalate_closing` não é `True`
- **Validado em:** 19/06/2026 — teste local, `pytest` verde (Fase 1 + Fase 2)
- **Pendente:** confirmação visual no Playground real (UI) antes de considerar este cenário totalmente fechado

### Cenário P2 — Regressão: agentes fora do grupo de agendamento continuam normais (validado localmente)
- [x] `test_non_scheduling_agent_still_escalates_closing` (agora usando `closer_agressivo`) — confirma que `guardrail_sdr_escalate_closing=True` e `message_text=""` continuam ocorrendo normalmente para templates fora de `_SCHEDULING_AGENT_TEMPLATES`
- **Validado em:** 19/06/2026 — teste local, `pytest` verde

### Cenário extra — Fallback para apresentation fora de agendamento (validado localmente)
- [x] `test_closing_signal_from_apresentation_falls_back_to_apresentation` (parametrizado `hybrid_scheduler` + `sdr_padrao`) — lead em "apresentation", Mãe decide `closing` → fallback correto para `apresentation`
- **Validado em:** 19/06/2026 — teste local, `pytest` verde

### Cenário C1 — Suite de testes sem regressão
- [x] `pytest backend-executors/tests` — 21 falhas pré-existentes (confirmadas idênticas via `git stash` antes/depois da Fase 1), 49 passando (44 + 5 novos), sem novas falhas
- **Validado em:** 19/06/2026

---

## Ajustes Possíveis Pós-Implementação

- Reativar "closing" especificamente para negociação de pacotes/planos de
  recorrência em campanhas de follow-up — exige planejamento próprio (sinal
  diferenciado de "fechamento de pacote" vs. "confirmação de sessão única").
