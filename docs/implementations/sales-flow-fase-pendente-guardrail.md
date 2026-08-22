# Guardrail geral de "gatilhos pendentes" além de p2 (apresentação)

**Branch:** `feat-fluxo-vendas-ramificacao`
**Status:** Em andamento

---

## Motivação

Durante a validação ao vivo do `requires_block_id` (feature graduada nesta mesma branch),
configurei um `phase_trigger` + `kw_trigger` na Fase 0 (Recepção) de um agente real
(`agenda`/`hybrid_scheduler`, 0 campos de qualificação obrigatórios) e observei o lead
avançar de Recepção (p0) direto para Apresentação (p2) dentro do **mesmo primeiro turno** —
os gatilhos configurados em p0/p1 nunca chegaram a ser avaliados.

Investigação (3 agentes Explore em paralelo + leitura direta do código) confirmou: existe
**exatamente um** guardrail deste tipo hoje — `_enforce_apresentation_sales_flow_pending`
(`decision_engine.py:4536-4601`), construído especificamente para p2 depois de um bug
idêntico ter sido reportado lá (`docs/implementations/fix-fluxo-vendas-sequencial.md`, já
graduado). p0/p1 nunca tiveram o equivalente. Ao verificar o próprio p2 mais a fundo, também
foi encontrada uma **falha nova, não documentada**: mesmo o guardrail de p2 tem um buraco
(`apresentation_complete_auto_advance`) que o contorna silenciosamente — ver Problema 2 abaixo.

Plano completo (com validação via 3 Explore agents + Plan Mode) registado em
`C:\Users\Daniel França\.claude\plans\synchronous-singing-willow.md`.

---

## Problemas Identificados (estado anterior)

1. **p1 (Qualificação) não tem guardrail de gatilhos pendentes:** 3 pontos independentes em
   `decision_engine.py` promovem `route_to`/`effective_route_to` de `"qualification"` para
   `"apresentation"` assim que `missing_fields` está vazio, sem checar se a fase p1 tem
   `kw_trigger`/`intent_trigger` (`fire_once=True`) ainda por disparar:
   - Regra 3 pré-check (`decide():5178-5188`)
   - Auto-promote de runtime (`decide():5311-5323`)
   - Regra 1 + fallback `ask_qualification` (`compose_decision_output:4764-4779` e `4889-4894`)

2. **p2 (Apresentação) tem um buraco não documentado no guardrail existente:**
   `_enforce_apresentation_sales_flow_pending` protege o `route_to` da Mãe, mas
   `apresentation_complete_auto_advance` (`compose_decision_output:4780-4794`) — disparado
   pelo sinal `did_complete_phase` da **Filha** (não determinístico) — avança
   `suggested_category` (persistido) sem consultar gatilhos pendentes de p2 nenhuma vez.

3. **p3a (Pré-Agendamento) não tem guardrail nenhum ao nível da Mãe:** só
   `pre_agendamento_complete_auto_advance` (`4796-4810`, sinal da Filha) existe — mesma
   classe de bug que p2 tinha antes de ser corrigido.

---

## Abordagem

```
Mãe decide route_to/perceived_category (todo turno, com ou sem Fluxo de Venda configurado)
  → guardrails determinísticos pós-decisão consultam estado já persistido
    (leads.triggers_fired, leads.phases_triggered) — sem chamada extra de LLM
  → NOVO: helper partilhado _phase_pending_sequential_triggers(phase_id, ai_profile, triggers_fired)
    ├─ fase sem gatilho sequencial configurado (fire_once=True) → [] → guardrail não interfere
    ├─ gatilho configurado e já disparado → [] → guardrail não interfere
    └─ gatilho configurado e ainda não disparado → [ids pendentes] → bloqueia o avanço desta fase
```

Extrai o scan inline já existente em `_enforce_apresentation_sales_flow_pending:4581-4593`
(sem mudar seu comportamento) para um helper reutilizável, e adiciona o mesmo gate nos
pontos de decisão que hoje não o consultam (mapa completo no plano aprovado).

---

## Plano de Implementação

### Fase 1 — Qualificação (p1): fecha o bug reportado

**Objetivo:** os 3 pontos que promovem `qualification → apresentation` passam a respeitar
gatilhos sequenciais pendentes configurados em p1.

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/decision_engine.py` | novo `_phase_pending_sequential_triggers()`; gate nos 3 pontos de auto-promote de qualificação |
| `backend-executors/tests/test_mother_qualification_route_guardrail.py` | novos casos: pendente bloqueia, disparado libera, sem gatilho comportamento inalterado, escape valve `is_upper_stage` preservado |

```python
# ANTES (decide():5178-5188) — Regra 3
if is_upper_stage or not missing_pre:
    route_for_child = "apresentation"

# DEPOIS
if is_upper_stage or (not missing_pre and not _phase_pending_sequential_triggers("p1", ai_profile, triggers_fired)):
    route_for_child = "apresentation"
```

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | *(pendente)* | |

---

## Checks de Validação

### Fase 1 — Qualificação (p1)
- [ ] `pytest tests/test_mother_qualification_route_guardrail.py -v` — todos passam
- [ ] Suite completa sem regressão (comparar contra baseline pré-existente)
- [ ] Gatilho sequencial pendente em p1 → `decide()` mantém `effective_route_to="qualification"`
- [ ] Mesmo gatilho já em `triggers_fired` → promove normalmente para apresentação
- [ ] Sem nenhum gatilho sequencial em p1 → comportamento idêntico ao atual (regressão)
- [ ] `is_upper_stage=True` com p1 pendente → ainda promove (escape valve preservado)

### Fase 2 — Apresentação (p2): fecha o buraco novo
- [ ] `_enforce_apresentation_sales_flow_pending` refatorado para usar o helper — sem regressão em `test_sales_flow_intent_trigger_phase_entry.py`
- [ ] `apresentation_complete_auto_advance` gateado — teste novo prova que `suggested_category` não avança com gatilho pendente em p2

### Fase 3 — Pré-Agendamento (p3a), só relevante para `agenda`
- [ ] Novo `_enforce_pre_agendamento_sales_flow_pending` na cadeia de guardrails
- [ ] `pre_agendamento_complete_auto_advance` gateado

---

## Ajustes Possíveis Pós-Implementação

- **p0/Recepção:** fora do escopo — exige primeiro dar a `"recepcao"` uma entrada em
  `_STAGE_ORDER`/`_ALLOWED_ADVANCE` (hoje ausente por design), mudança estrutural com maior
  raio de impacto. Decisão separada, não descartada.
- **p3b→follow-up, p4→closing:** fora do escopo — sem atalho de auto-advance hoje, menor
  urgência. p4/follow-up interage com `followup_state.py`/`followup_reconciler.py` e merece
  olhar dedicado.
- **Log de "pendente há N turnos":** fast-follow opcional (observabilidade), não bloqueia
  esta implementação.
