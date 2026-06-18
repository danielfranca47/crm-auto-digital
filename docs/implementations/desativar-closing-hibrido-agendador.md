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
| 1 | _(pendente)_ | feat: desativar roteamento para closing no agente híbrido agendador |

---

## Checks de Validação

### Cenário P1 — Playground: confirmação de horário não fica muda
- [ ] Reproduzir: saudação → "gostaria de agendar uma sessão" → "amanhã as 12h" → "sim"
- [ ] Confirmar: última resposta não fica vazia
- [ ] Confirmar no trace/log: reason contém `hybrid_scheduler_closing_disabled`, sem `guardrail_sdr_escalate_closing` neste ponto

### Cenário P2 — Regressão: agentes não-hybrid_scheduler continuam normais
- [ ] Confirmar que `sdr_padrao`/`closer_agressivo`/`consultivo` continuam roteando para "closing" quando aplicável, sem mudança de comportamento

### Cenário C1 — Suite de testes sem regressão
- [ ] `pytest backend-executors/tests` — mesma contagem de falhas pré-existentes, sem novas falhas

---

## Ajustes Possíveis Pós-Implementação

- Reativar "closing" especificamente para negociação de pacotes/planos de
  recorrência em campanhas de follow-up — exige planejamento próprio (sinal
  diferenciado de "fechamento de pacote" vs. "confirmação de sessão única").
