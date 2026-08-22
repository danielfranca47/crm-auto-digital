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
| 1 | `57901b2` | Helper `_phase_pending_sequential_triggers()` + gate nos 3 pontos de auto-promoção de qualificação |

**Detalhes do commit `57901b2`:**
- `decision_engine.py` — `_phase_pending_sequential_triggers(phase_id, ai_profile, triggers_fired)`
  novo (extrai o scan hardcoded de `_enforce_apresentation_sales_flow_pending`, sem alterá-lo
  ainda — isso é Fase 2); gate em 3 pontos: Regra 3 (`decide()`, só o ramo `not missing_pre`,
  `is_upper_stage` preservado ungated), auto-promote de runtime (`decide()`), Regra 1 +
  fallback `ask_qualification` (`compose_decision_output()`)
- `test_qualification_sales_flow_pending.py` (novo) — 4 testes: pendente bloqueia, disparado
  libera, sem gatilho sequencial comportamento inalterado, escape valve `is_upper_stage`
  preservado
- Suite completa: 23 failed / 210 passed — mesmo conjunto de 23 falhas pré-existentes
  (confirmado via `git stash` comparando antes/depois linha a linha), 4 testes novos passando,
  sem regressão

### Relatório da Fase 1 — o que mudou na prática

**Antes:** um agente sem campos de qualificação obrigatórios configurados avançava
automaticamente da fase de Qualificação para Apresentação assim que a Mãe (IA) decidia isso,
mesmo que houvesse um gatilho de palavra-chave configurado em Qualificação que ainda não
tinha disparado — o gatilho era pulado silenciosamente, sem nunca ter a chance de disparar.

**Agora:** se houver pelo menos um gatilho sequencial (palavra-chave ou intenção, marcado
"disparar apenas uma vez") configurado na fase de Qualificação e ele ainda não disparou para
aquele lead, o sistema não avança automaticamente para Apresentação — o gatilho tem a chance
de disparar primeiro. Agentes sem esse tipo de gatilho configurado em Qualificação continuam
funcionando exatamente como antes (nada muda para eles).

**Para validar:** testes automatizados (pytest) já rodados e confirmados nesta fase — ver
tabela de commits acima. Não há cenário de UI/Playground específico desta fase isolada (é uma
mudança só de backend); o cenário ao vivo fica reservado para o final da Fase 2, quando
também o buraco de p2 estiver fechado — nesse ponto dá para repetir a mesma técnica desta
sessão (blocos de teste temporários no builder + Playground) e confirmar que o gatilho de p1
agora tem a chance de disparar no turno seguinte.

### Fase 2 — Apresentação (p2): fecha o buraco novo

**Objetivo:** `_enforce_apresentation_sales_flow_pending` passa a usar o helper partilhado (sem
mudar comportamento), e o buraco em `apresentation_complete_auto_advance` — que avançava
`suggested_category` sem checar gatilhos pendentes de p2 — é fechado.

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/decision_engine.py` | `_enforce_apresentation_sales_flow_pending` refatorado para chamar `_phase_pending_sequential_triggers("p2", ...)`; gate `and not p2_pending_compose` em `apresentation_complete_auto_advance` |
| `backend-executors/tests/test_apresentation_complete_auto_advance_pending.py` | novo: pendente bloqueia, disparado libera, sem gatilho comportamento inalterado |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `d6d9f6a` | Refactor do guardrail de p2 para usar o helper + gate em `apresentation_complete_auto_advance` |

**Detalhes do commit:**
- `decision_engine.py` — `_enforce_apresentation_sales_flow_pending` (linhas ~4609-4614): o scan
  inline hardcoded para p2 foi substituído pela chamada a `_phase_pending_sequential_triggers("p2",
  ai_profile, _load_triggers_fired_set(context))` — comportamento idêntico, confirmado pela suite de
  regressão `test_sales_flow_intent_trigger_phase_entry.py` (27/27 passam, incluindo os 6 testes
  específicos de `_enforce_apresentation_pending_*`)
- `decision_engine.py` — `apresentation_complete_auto_advance` (`compose_decision_output`, ~linha
  4810-4820): novo `p2_pending_compose = _phase_pending_sequential_triggers("p2", ...)` e gate
  `and not p2_pending_compose` na condição que avança `suggested_category`. Este é o guardrail que
  fecha o buraco novo (Problema 2 da Motivação) — `did_complete_phase` é sinal da Filha, não
  determinístico, e podia contornar silenciosamente o gatilho pendente
- `test_apresentation_complete_auto_advance_pending.py` (novo) — 3 testes: gatilho pendente em p2
  bloqueia o avanço (verificado que falha sem o gate — `assert 'pre-agendamento' == 'apresentation'`
  — antes de confirmar que passa com o gate reativado), gatilho já disparado avança normalmente,
  sem gatilho sequencial configurado comportamento idêntico ao atual
- Suite completa: 23 failed / 213 passed — mesmo conjunto de 23 falhas pré-existentes da Fase 1
  (confirmado via `git stash` comparando os 3 arquivos de teste do subset qualification/
  sales_flow/apresentation/pre_agendamento antes/depois, linha a linha), 3 testes novos passando
  (210→213), sem regressão

### Relatório da Fase 2 — o que mudou na prática

**Antes:** mesmo com o guardrail de p2 (`_enforce_apresentation_sales_flow_pending`) protegendo o
`route_to` decidido pela Mãe, havia um caminho paralelo — `apresentation_complete_auto_advance` —
que avançava a categoria persistida do lead (`suggested_category`) para pré-agendamento/agendamento/
follow-up assim que a Filha sinalizava `did_complete_phase=true`, sem nunca checar se havia um
gatilho sequencial configurado em Apresentação que ainda não tinha disparado. Era o mesmo tipo de
bug que já tinha sido corrigido uma vez para p2 (via `route_to`), mas reaberto por um caminho
diferente que ninguém tinha coberto.

**Agora:** os dois caminhos que podem avançar a categoria para além de Apresentação —
o `route_to` da Mãe e o `did_complete_phase` da Filha — respeitam a mesma regra: se houver um
gatilho sequencial pendente em p2, nenhum dos dois avança a categoria. Como bónus, o scan que
antes estava duplicado (hardcoded dentro do guardrail de `route_to`) agora usa a mesma função
partilhada que a Fase 1 já criou para p1 — só existe uma implementação da regra "gatilhos
sequenciais pendentes numa fase" no código todo.

**Para validar:** testes automatizados (pytest) já rodados e confirmados nesta fase — ver tabela
de commits acima, incluindo a confirmação manual de que o teste falha sem o gate (prova de que
o teste captura o bug, não é vacuamente verdadeiro). Sanity check ao vivo fica reservado para o
final da Fase 3 (ou pode ser feito agora, opcionalmente, reusando a técnica de blocos de teste
temporários no builder + Playground desta vez em p2).

### Fase 3 — Pré-Agendamento (p3a): mesma classe de bug que p2 tinha antes de ser corrigida

**Objetivo:** p3a (só relevante para `agenda`, único modo que a visita) passa a ter os dois
mesmos guardrails que p2 já tem desde a Fase 2 — um novo `_enforce_pre_agendamento_sales_flow_pending`
ao nível da Mãe (p3a nunca teve nenhum guardrail deste tipo, mesma classe de bug que p2 tinha
antes de `fix-fluxo-vendas-sequencial.md`) e o gate em `pre_agendamento_complete_auto_advance`
ao nível da Filha.

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/decision_engine.py` | novo `_enforce_pre_agendamento_sales_flow_pending()` (espelha o de p2, trocando p2→p3a e `_ALLOWED_ADVANCE["pre-agendamento"]`), adicionado como 5º guardrail na cadeia de `decide()`; gate `and not p3a_pending_compose` em `pre_agendamento_complete_auto_advance` |
| `backend-executors/tests/test_pre_agendamento_sales_flow_pending.py` | novo: 10 testes — 6 espelhando os do guardrail de p2 (`_enforce_apresentation_sales_flow_pending`) adaptados para p3a/pre-agendamento, 3 espelhando os do gate em `apresentation_complete_auto_advance` adaptados para `pre_agendamento_complete_auto_advance` |

### Commits Fase 3

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | _(pendente)_ | Novo guardrail `_enforce_pre_agendamento_sales_flow_pending` + gate em `pre_agendamento_complete_auto_advance` |

**Detalhes do commit _(pendente)_:**
- `decision_engine.py` — `_enforce_pre_agendamento_sales_flow_pending()` novo, logo após
  `_enforce_apresentation_sales_flow_pending`: mesma estrutura (checa `phases_triggered`
  conter "p3a" OU `lead.category == "pre-agendamento"` como sinal de "engajado com a fase",
  depois `_ALLOWED_ADVANCE["pre-agendamento"]` para saber se a rota da Mãe está tentando sair
  dela, depois `_phase_pending_sequential_triggers("p3a", ...)`); adicionado à cadeia de
  guardrails em `decide()` logo após o de p2 (vira o 5º)
- `decision_engine.py` — `pre_agendamento_complete_auto_advance` (`compose_decision_output`):
  novo `p3a_pending_compose = _phase_pending_sequential_triggers("p3a", ...)` e gate
  `and not p3a_pending_compose` na condição que avança `suggested_category` para "agendamento"
- `test_pre_agendamento_sales_flow_pending.py` (novo) — 10 testes: bloqueia salto da Mãe
  (route_to), cobre todos os alvos permitidos de `_ALLOWED_ADVANCE["pre-agendamento"]`
  (agendamento, follow-up), libera quando já disparado, ignora outras categorias correntes,
  no-op sem sales_flow configurado, usa `phases_triggered` quando `lead.category` está
  defasado, gatilho pendente bloqueia `pre_agendamento_complete_auto_advance` (verificado que
  falha sem o gate — `assert 'agendamento' == 'pre-agendamento'` — antes de confirmar que
  passa com o gate reativado), gatilho já disparado avança normalmente, sem gatilho
  comportamento inalterado
- Suite completa: 23 failed / 223 passed — mesmo conjunto de 23 falhas pré-existentes desde a
  Fase 1 (confirmado via `git stash` comparando a suite completa antes/depois linha a linha,
  não só o subset), 10 testes novos passando (213→223), sem regressão

### Relatório da Fase 3 — o que mudou na prática

**Antes:** p3a (Pré-Agendamento) não tinha nenhum guardrail de gatilhos pendentes — nem ao
nível da Mãe (`route_to`), nem ao nível da Filha (`did_complete_phase`). Um agente `agenda`
com um gatilho sequencial configurado em Pré-Agendamento (ex.: "confirmar disponibilidade
antes de fechar o horário") podia ter esse gatilho pulado silenciosamente se a Mãe decidisse
avançar direto para Agendamento num único turno, ou se a Filha sinalizasse `did_complete_phase`
sem o gatilho ter disparado — exatamente o mesmo tipo de bug que p2 já teve e já foi corrigido.

**Agora:** p3a tem os mesmos dois guardrails que p2 — gatilhos sequenciais pendentes bloqueiam
tanto o `route_to` da Mãe quanto o avanço de categoria vindo do sinal `did_complete_phase` da
Filha. Como só o modo `agenda` visita p3a, este guardrail é inofensivo (no-op) para
`consultivo`/`direto` — `_phase_pending_sequential_triggers` nunca encontra a fase "p3a" no
profile desses modos.

**Para validar:** testes automatizados (pytest) já rodados e confirmados nesta fase — ver
tabela de commits acima. Com isto, as 3 fases planejadas em
`C:\Users\Daniel França\.claude\plans\synchronous-singing-willow.md` estão code-complete e
todos os checks de validação (pytest) estão marcados. Falta decidir: (a) fazer o sanity check
ao vivo opcional no Playground (mencionado como opcional no plano, nunca feito nesta
implementação) e/ou (b) seguir para a graduação (`_processo-graduacao-implementacao.md`) —
migrar o mapa de guardrails para `docs/architecture/sales-flow.md`/`pipeline-phases.md`, `git
rm` deste arquivo, commit único de graduação.

---

## Checks de Validação

### Fase 1 — Qualificação (p1)
- [x] `pytest tests/test_qualification_sales_flow_pending.py -v` — todos passam
- [x] Suite completa sem regressão (23 failed / 210 passed — mesmo conjunto de falhas
      pré-existentes que os 23 failed / 206 passed do baseline, confirmado via `git stash`)
- [x] Gatilho sequencial pendente em p1 → `decide()` mantém `effective_route_to="qualification"`
- [x] Mesmo gatilho já em `triggers_fired` → promove normalmente para apresentação
- [x] Sem nenhum gatilho sequencial em p1 → comportamento idêntico ao atual (regressão)
- [x] `is_upper_stage=True` com p1 pendente → ainda promove (escape valve preservado)
- **Validado em:** 22/08/2026 — automatizado (pytest), sem intervenção manual necessária

### Fase 2 — Apresentação (p2): fecha o buraco novo
- [x] `_enforce_apresentation_sales_flow_pending` refatorado para usar o helper — sem regressão em `test_sales_flow_intent_trigger_phase_entry.py` (27/27 passam)
- [x] `apresentation_complete_auto_advance` gateado — teste novo prova que `suggested_category` não avança com gatilho pendente em p2 (falha sem o gate, passa com o gate)
- [x] Gatilho já disparado em p2 → avança normalmente para `pre-agendamento`
- [x] Sem nenhum gatilho sequencial em p2 → comportamento idêntico ao atual (regressão)
- [x] Suite completa sem regressão (23 failed / 213 passed — mesmas 23 falhas pré-existentes, 210→213 com os 3 testes novos)
- **Validado em:** 22/08/2026 — automatizado (pytest), sem intervenção manual necessária

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
