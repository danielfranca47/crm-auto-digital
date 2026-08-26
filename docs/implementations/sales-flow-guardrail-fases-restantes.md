# Guardrail de gatilhos pendentes — fases restantes (p1, p3b, p4, p5, client-list)

**Branch:** `feat/sales-flow-guardrail-fases-restantes`
**Status:** Em andamento

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`docs/implementations/sales-flow-guardrail-p0-recepcao.md` (feature que deu a p0 o mesmo
guardrail de "gatilhos sequenciais pendentes bloqueiam avanço automático de fase" já existente
para p2/p3a). O usuário pediu explicitamente uma auditoria de cobertura completa — todas as
fases em que o bot é responsável, não só as já corrigidas.

Escopo definido pelo usuário na sessão anterior: qualificação (p1), agendamento (p3b),
follow-up (p4), fechamento (p5) e lista de clientes (`client-list`). Fora de escopo, por
decisão do usuário: arquivados (`prospect-refused`) e desqualificados (`disqualified`) — não
são fases onde o bot está ativo.

Este arquivo absorve integralmente `docs/implementations/sales-flow-guardrail-p3b-p4.md`
(removido nesta fase) — mesmo escopo para p3b/p4, criado antes desta auditoria mais ampla,
com a mesma investigação e a mesma solução.

---

## Problemas Identificados (estado anterior)

1. **p3b (agendamento) sem guardrail** (`backend-executors/app/services/decision_engine.py`) —
   `_ALLOWED_ADVANCE["agendamento"] = {"follow-up", "client-list"}` já define condições de saída
   válidas, mas nenhum `_enforce_agendamento_sales_flow_pending` existe para bloquear a Mãe de
   pular a fase inteira num único turno enquanto houver gatilhos sequenciais configurados nela
   ainda não disparados — mesma classe de bug que já foi corrigida em p2/p3a.
2. **p4 (follow-up) sem guardrail** (mesmo arquivo) — `_ALLOWED_ADVANCE["follow-up"] = {"closing"}`
   também não tem `_enforce_followup_sales_flow_pending` correspondente.
3. **Documentação desatualizada** (`docs/architecture/sales-flow.md:282-288`) — descreve p3b/p4/p5
   como "sem guardrail (deliberado)" e a auditoria de p1/p5/client-list como "ainda não feita",
   sem refletir a investigação já concluída nesta implementação.

---

## Abordagem

Diagnóstico completo (3 agentes de exploração cobrindo `decision_engine.py`, o subsistema de
follow-up, e p5/client-list) concluído em Plan Mode. Resultado por fase:

### p1 (qualificação) — sem gap real, nenhuma mudança de código
Já coberta indiretamente por 3 pontos em `decide()`/`compose_decision_output()` (Regra 3 + escape
valve `is_upper_stage`, auto-promote de runtime, Regra 1 + fallback `ask_qualification`), todos
gateados por `_phase_pending_sequential_triggers("p1", ...)`. O único bypass (`is_upper_stage`) é
intencional — trata de um lead que já está numa categoria persistida posterior e cuja Mãe tentou
rotear de volta a qualificação por engano; não é "saindo de p1 agora". **Decisão: não criar
função dedicada** — só formalizar a conclusão em `docs/architecture/sales-flow.md`.

### p3b (agendamento) — gap real, mesma receita de p2/p3a
`_enforce_agendamento_sales_flow_pending`, cópia exata do padrão de
`_enforce_pre_agendamento_sales_flow_pending`. O bug separado de `client-list` fora de
`_STAGE_INDEX` (achado durante a investigação, ver "Ajustes Possíveis") não afeta este guardrail:
ele só depende de `mother_decision.route_to` via `_ALLOWED_ADVANCE`, nunca chama
`apply_mother_category_guardrails`.

### p4 (follow-up) — gap real, mesma receita, com uma exclusão específica
Achado-chave: o resultado de `decide()` durante um job `whatsapp.followup.tick`
(`suggested_category`, `system_actions`, `mark_trigger_fired`/`mark_phase_triggered`) é
**descartado** por `complete_job_internal` (`backend-crm/routes/executor.py:948-1007`) — só
`job_type == "whatsapp.inbound.n8n"` aplica esses efeitos. O guardrail nunca tem nada a proteger
nem a conflitar durante o próprio tick (que só decide qual Filha responde via
`force_followup_route`, sobrescrevendo `route_for_child` sem depender do guardrail). A saída real
de p4 → closing só acontece num turno inbound ao vivo — mesmo caminho que p2/p3a já usam hoje.

Risco que exige exclusão explícita: o check-in automático pós-venda
(`start_client_checkin_followup`, `followup_state.py`) reusa a fase p4 com
`followup_variant="client_checkin"` **sem mover `lead.category` para `"follow-up"`** (o lead
permanece em `"client-list"`). Como `phases_triggered` é cumulativo, um lead que já passou por p4
antes de virar cliente carrega `"p4"` em `phases_triggered` para sempre. **Decisão: o guardrail
só age quando `lead.category` normalizado é `"follow-up"`** — não usa o sinal alternativo
`"p4" in phases_triggered` que as outras funções usam, justamente por causa dessa sobreposição.

### p5 (fechamento) — não aplicável, closing é terminal
Confirmado em 4 lugares independentes (`_STAGE_ORDER`, `_ALLOWED_ADVANCE` sem chave `"closing"`,
`MotherDecision.route_to`/`perceived_category` Literal sem valor além de `"closing"`, e as 3
sequências de `_SALES_FLOW_PHASE_SEQUENCE_BY_AGENT_MODE` terminando em `"p5"`). Não há "para onde"
bloquear a saída. O guardrail equivalente (proteger a *entrada* prematura em closing) é exatamente
`_enforce_followup_sales_flow_pending` (p4→closing). **Decisão: nenhuma função nova.**

### `client-list` — não aplicável, não é fase do sales_flow
Não tem `phase_id` próprio; a transição para lá acontece via webhook de pagamento
(`backend-crm/routes/webhooks.py`), fora de `decide()`; o check-in pós-venda que roda ali reusa
p4 (ver acima). **Decisão: nenhuma função nova.**

```
Mãe decide route_to="agendamento"|"follow-up" (tentando sair da fase)
  → _enforce_agendamento_sales_flow_pending / _enforce_followup_sales_flow_pending
      ├─ gatilho sequencial pendente na fase → força route_to de volta à fase atual
      └─ sem pendência → route_to original passa
```

---

## Plano de Implementação

### Fase 1 — p3b (agendamento)

**Objetivo:** bloquear a Mãe de pular a fase de agendamento enquanto houver gatilhos sequenciais
pendentes configurados nela.

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/decision_engine.py` | Nova função `_enforce_agendamento_sales_flow_pending`; chamada adicionada à cadeia de `decide()` |
| `backend-executors/tests/test_agendamento_sales_flow_pending.py` | Novo — espelha `test_pre_agendamento_sales_flow_pending.py` |
| `docs/implementations/sales-flow-guardrail-p3b-p4.md` | Removido (`git rm`) — absorvido por este arquivo |

### Fase 2 — p4 (follow-up)

**Objetivo:** bloquear a Mãe de pular para "closing" enquanto houver gatilhos sequenciais
pendentes configurados em p4, sem afetar o check-in de relacionamento (`client_checkin`) nem o
subsistema de ticks agendados.

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/decision_engine.py` | Nova função `_enforce_followup_sales_flow_pending` (engajamento só via `category == "follow-up"`); chamada adicionada à cadeia de `decide()` |
| `backend-executors/tests/test_followup_sales_flow_pending.py` | Novo — caso padrão, caso de exclusão `client_checkin`, caso de tick |

### Fase 3 — Documentação e graduação

| Arquivo | O que muda |
|---|---|
| `docs/architecture/sales-flow.md` | Seção "Guardrail de gatilhos pendentes...": adiciona p3b/p4 à lista; reescreve o parágrafo final com o estado real (p1 auditado/suficiente, p5 e client-list não aplicáveis) |

---

## Checks de Validação

Mudança 100% backend/lógica de decisão determinística — sem UI/browser envolvido. Validação via
testes automatizados (pytest).

### Cenário T1 — p3b bloqueia com gatilho pendente
- [ ] Rodar `pytest backend-executors/tests/test_agendamento_sales_flow_pending.py`
- [ ] Confirmar: caso com gatilho pendente força `route_to` de volta a `"agendamento"`; caso sem
      pendência deixa o `route_to` original passar

### Cenário T2 — p4 bloqueia com gatilho pendente
- [ ] Rodar `pytest backend-executors/tests/test_followup_sales_flow_pending.py`
- [ ] Confirmar: caso padrão bloqueia; caso `client_checkin`/`client-list` não intervém; caso de
      tick não quebra o `force_followup_route` existente

### Cenário T3 — Regressão da suíte completa
- [ ] Rodar `pytest backend-executors/tests/` (suíte inteira)
- [ ] Confirmar: nenhum teste existente de p0/p2/p3a regride

---

## Ajustes Possíveis Pós-Implementação

1. **Bug `client-list` fora de `_STAGE_INDEX`/`_STAGE_ORDER`** — torna
   `_ALLOWED_ADVANCE["agendamento"]["client-list"]` inalcançável via `apply_mother_category_guardrails`
   (sempre cai em `"invalid"`). **Achado ampliado durante a Fase 1** (confirmado por teste que
   falhou ao tentar construir `MotherDecision(route_to="client-list")`):
   `MotherDecision.route_to` (Literal, `orchestrator_models.py`) nem aceita esse valor — o bug é
   mais profundo do que só `apply_mother_category_guardrails`; a Mãe estruturalmente nunca
   consegue emitir `route_to="client-list"`, tornando essa entrada de `_ALLOWED_ADVANCE`
   inalcançável por dois caminhos independentes. Não afeta os guardrails desta implementação
   (`_enforce_agendamento_sales_flow_pending` só verifica se o `route_to` da Mãe pertence ao
   conjunto — nunca precisa que "client-list" seja de fato alcançável); bug real separado, não
   corrigido aqui.
2. **Constante duplicada** `_SCHEDULING_AGENT_TEMPLATES` vs. `_SCHEDULING_AGENT_TEMPLATES_SET` —
   mesmo valor, dois símbolos; risco de divergência se um template agendador for adicionado no
   futuro.
3. **`perceived_category` vs `route_to` não sincronizados** — todos os `_enforce_*_sales_flow_pending`
   (incluindo os 2 novos) só mutam `route_to`; `apply_mother_category_guardrails` só lê
   `perceived_category`. Se a Mãe emitir um `perceived_category` já avançado enquanto `route_to` é
   corrigido pelo guardrail, a categoria persistida pode divergir do conteúdo real gerado no turno.
   Característica pré-existente do mecanismo, não introduzida aqui.
