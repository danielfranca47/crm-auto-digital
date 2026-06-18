# Desativar roteamento para "closing" no agente híbrido agendador

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

Causa raiz: já existe um guardrail parcial (`guardrail_hybrid_scheduler_no_closing`,
em `compose_decision_output()`) que impede a categoria persistida do lead de virar
"closing" para `hybrid_scheduler`, mas ele atua tarde demais — depois que
`effective_route_to` já foi fixado em `mother_decision.route_to` e depois que
`_is_sdr_escalate_closing()` já avaliou `route_to`/`perceived_category`
diretamente. Por isso o bot ficava mudo mesmo a categoria do Kanban nunca
chegando a "closing" de fato.

O utilizador decidiu desativar/ocultar a rota "closing" para o agente híbrido
agendador por agora (deixando apenas qualification/apresentation/pre-agendamento/
agendamento/follow-up). Reativar "closing" para negociação de pacotes/planos de
recorrência em campanhas de follow-up fica como melhoria futura, fora de escopo.

---

## Problemas Identificados (estado anterior)

1. **Guardrail de categoria atua tarde demais:** `backend-executors/app/services/decision_engine.py`
   — `guardrail_hybrid_scheduler_no_closing` (em `compose_decision_output()`) só
   corrige `suggested_category`, não `mother_decision.route_to`/`perceived_category`,
   que já alimentaram `route_for_child` e `_is_sdr_escalate_closing()` antes disso.
2. **Sem regra na Mãe para "depois de agendamento confirmado":** o prompt da Mãe
   não tem nenhuma instrução específica de hybrid_scheduler dizendo que "closing"
   não existe neste template — ela cai na heurística genérica "confirmação =
   fechamento".

---

## Abordagem

```
Mother LLM decide route_to/perceived_category
  → _enforce_qualification_route_when_missing()
  → _enforce_greeting_first()
  → _enforce_hybrid_scheduler_no_closing()   [NOVO]
       se template_key == "hybrid_scheduler" e route/perceived == "closing":
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

### Fase 1 — Backend: nova função de enforcement + documentação

| Arquivo | O que mudou |
|---|---|
| `backend-executors/app/services/decision_engine.py` | Nova função `_enforce_hybrid_scheduler_no_closing()`, chamada em `decide()` logo após `_enforce_greeting_first()` |
| `docs/architecture/pipeline-phases.md` | Nota sobre "closing" desativado por design para `hybrid_scheduler` |

### Commits

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `ec3337d` | feat: desativar roteamento para closing no agente híbrido agendador |
| 2 | `8b44e94` | docs: registar hash do commit ec3337d no arquivo de implementação |
| 3 | _(pendente)_ | test: regressão automatizada para o cenário local (substitui validação manual de P1/P2) |

---

## Checks de Validação

### Cenário P1 — Confirmação de horário não fica muda (validado localmente, via teste automatizado)
- [x] Reproduzido via `backend-executors/tests/test_hybrid_scheduler_no_closing.py::test_booking_confirmation_does_not_escalate_to_silent_closing` — simula exatamente o caso real (hybrid_scheduler, `requires_handoff=true`, lead em "agendamento", Mãe decide `closing`)
- [x] Confirmado: `decision.message_text != ""`, `next_action != "ignore"`
- [x] Confirmado: `reason` contém `hybrid_scheduler_closing_disabled:agendamento`, `trace.guardrail_sdr_escalate_closing` não é `True`
- **Validado em:** 19/06/2026 — teste local, `pytest` verde
- **Pendente:** confirmação visual no Playground real (UI) antes de considerar este cenário totalmente fechado

### Cenário P2 — Regressão: agentes não-hybrid_scheduler continuam normais (validado localmente)
- [x] `test_non_hybrid_scheduler_agent_still_escalates_closing` — mesmo cenário (lead em "agendamento", "sim", `requires_handoff=true`) mas com `template_key=sdr_padrao`: confirma que `guardrail_sdr_escalate_closing=True` e `message_text=""` continuam ocorrendo normalmente
- **Validado em:** 19/06/2026 — teste local, `pytest` verde

### Cenário extra — Fallback para apresentation fora de agendamento (validado localmente)
- [x] `test_closing_signal_from_apresentation_falls_back_to_apresentation` — lead em "apresentation", Mãe decide `closing` → fallback correto para `apresentation` (não regride nem avança indevidamente)
- **Validado em:** 19/06/2026 — teste local, `pytest` verde

### Cenário C1 — Suite de testes sem regressão
- [x] `pytest backend-executors/tests` — 21 falhas pré-existentes (confirmadas idênticas via `git stash` antes/depois da mudança), 47 passando (44 + 3 novos), sem novas falhas
- **Validado em:** 19/06/2026

---

## Ajustes Possíveis Pós-Implementação

- Reativar "closing" especificamente para negociação de pacotes/planos de
  recorrência em campanhas de follow-up — exige planejamento próprio (sinal
  diferenciado de "fechamento de pacote" vs. "confirmação de sessão única").
