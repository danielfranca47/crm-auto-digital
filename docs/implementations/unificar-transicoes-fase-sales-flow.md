# Unificar `_ALLOWED_ADVANCE`/`_STAGE_ORDER` com a sequência de fases do Fluxo de Venda

**Branch:** `fix/unificar-transicoes-fase-sales-flow`
**Status:** Todos os cenários validados (26/08/2026)

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

### Diagnóstico (Plan Mode)

Investigação confirmou que `_ALLOWED_ADVANCE` **é**, na prática, a união das
transições sequenciais `p_i → p_{i+1}` das 3 sequências de `agent_mode` em
`_SALES_FLOW_PHASE_SEQUENCE_BY_AGENT_MODE`, traduzidas de `phase_id` para
categoria — mais 2 "escape valves" que não vêm de nenhuma sequência linear:

- `pre-agendamento → follow-up` — desistência no meio do agendamento (o lead
  não confirma horário e a Mãe o move para nutrição, fora do pipeline
  estrito de `agenda`).
- `agendamento → client-list` — `client-list` não tem `phase_id` nenhum; é um
  estado fora do funil de fases do Fluxo de Venda (lead virou cliente).

Verificação de todas as bordas de `_ALLOWED_ADVANCE` contra as 3 sequências
(consultivo/direto/agenda), par a par:

| De → Para | Vem de qual sequência? |
|---|---|
| `recepcao → qualification` | p0→p1, todas |
| `qualification → apresentation` | p1→p2, todas |
| `apresentation → follow-up` | p2→p4, `consultivo` |
| `apresentation → closing` | p2→p5, `direto` |
| `apresentation → pre-agendamento` | p2→p3a, `agenda` |
| `pre-agendamento → agendamento` | p3a→p3b, `agenda` |
| `pre-agendamento → follow-up` | **não deriva de nenhuma sequência** (escape valve) |
| `agendamento → follow-up` | p3b→p4, `agenda` |
| `agendamento → client-list` | **não deriva de nenhuma sequência** (`client-list` sem `phase_id`) |
| `follow-up → closing` | p4→p5, `consultivo`/`agenda` |

Achados adicionais (fora do escopo deste item, ver "Ajustes Possíveis" abaixo):
- `_PHASE_ID_TO_CATEGORY`, duplicada identicamente em
  `backend-crm/routes/executor.py:266` e `backend-crm/routes/playground.py:194`,
  mapeia **p3a e p3b para `"apresentation"`** (não para
  `pre-agendamento`/`agendamento`) — usada só pela ação `advance_phase`.
- `_CATEGORY_TO_PHASE_ID` (local a `_collect_intent_triggers_for_lead_phase`,
  `decision_engine.py:1112`) mapeia p3a/p3b corretamente (sem colapsar) —
  inconsistente com a estrutura acima.
- O mirror no frontend (`frontend-crm/src/types/agente.ts:131`,
  `SALES_FLOW_PHASES_BY_AGENT_MODE`) está idêntico ao backend — sem divergência.
- Nenhuma outra lógica de ordenação/transição encontrada em
  `followup_state.py`, `followup_reconciler.py`, `lead_category_policy.py`,
  `agent_type.py`, ou no Kanban do frontend.

### Decisão

Duas abordagens foram avaliadas com o utilizador:
1. Derivar `_ALLOWED_ADVANCE` em runtime a partir de
   `_SALES_FLOW_PHASE_SEQUENCE_BY_AGENT_MODE` (unificação real de fonte única,
   mas toca um arquivo crítico de guardrails).
2. Manter as duas estruturas exatamente como estão e só adicionar uma rede de
   segurança automatizada (teste) que acusa divergência futura.

**Escolhida a opção 2** — risco quase zero, sem mudança de comportamento em
produção. `_ALLOWED_ADVANCE` e `_SALES_FLOW_PHASE_SEQUENCE_BY_AGENT_MODE`
continuam duas estruturas hand-maintained, mas agora com uma checagem
automatizada de consistência entre elas.

---

## Plano de Implementação

### Fase 1 — Teste de consistência entre as duas tabelas

**Objetivo:** adicionar um teste automatizado que falha se
`_SALES_FLOW_PHASE_SEQUENCE_BY_AGENT_MODE` for alterada (nova fase, novo
`agent_mode`, reordenação) sem que `_ALLOWED_ADVANCE` seja atualizada para
continuar permitindo essas transições.

| Arquivo | O que muda |
|---|---|
| `backend-executors/tests/test_transition_tables_consistency.py` | Novo. Ver detalhes abaixo. |

Lógica do teste:
1. Constrói `phase_id → categoria` reaproveitando estruturas de produção já
   existentes (sem criar um 5º dicionário duplicado): inverte
   `decision_engine._ROUTE_TO_PHASE_ID`, filtrando só as chaves que aparecem em
   `decision_engine._STAGE_ORDER` (+ `"recepcao"`) — garante pegar a grafia
   canônica com hífen e não as variantes com underscore que também existem
   nesse dict.
2. Para cada sequência em `_SALES_FLOW_PHASE_SEQUENCE_BY_AGENT_MODE.values()`,
   para cada par consecutivo `(phase_i, phase_{i+1})`: traduz os dois para
   categoria e assere que `categoria_seguinte in _ALLOWED_ADVANCE.get(categoria_atual, set())`.
   Mensagem de falha cita o `agent_mode`, o par de fases e a categoria
   faltante.
3. Segundo teste documenta as 2 exceções conhecidas
   (`pre-agendamento→follow-up`, `agendamento→client-list`) via uma lista
   explícita `_KNOWN_NON_SEQUENTIAL_EDGES` no próprio teste.

Nenhum arquivo de produção é alterado nesta fase.

---

## Checks de Validação

### Cenário T1 — Teste passa com o estado atual das tabelas
- [x] Rodar `pytest backend-executors/tests/test_transition_tables_consistency.py -v`
- [x] Confirmar que todos os testes passam
- **Validado em:** 26/08/2026 — 3 passed (test_phase_id_to_category_covers_every_phase_used_in_sequences, test_allowed_advance_covers_every_sequential_edge, test_known_non_sequential_edges_still_present)

### Cenário T2 — Teste detecta divergência futura
- [x] Alterar temporariamente `_SALES_FLOW_PHASE_SEQUENCE_BY_AGENT_MODE`
      (adicionada fase inexistente `"p6"` na sequência `agenda`, e reordenado
      `p5`/`p4` na sequência `consultivo` para forçar a borda inválida
      `closing → follow-up`)
- [x] Rodar o teste e confirmar que ele **falha** com mensagem clara
      apontando a transição faltante
- [x] Reverter a alteração temporária
- **Validado em:** 26/08/2026 — `p6` sem categoria disparou
  `test_phase_id_to_category_covers_every_phase_used_in_sequences`; a
  reordenação `closing→follow-up` disparou
  `test_allowed_advance_covers_every_sequential_edge` com a mensagem
  `agent_mode='consultivo': p5(closing) -> p4(follow-up) não está em
  _ALLOWED_ADVANCE['closing']=set()` — exatamente o comportamento esperado.
  `git checkout` confirmou que `decision_engine.py` voltou ao estado original
  antes do commit.

---

### Relatório da Fase 1 — o que mudou na prática

**Antes:** existiam duas "listas de regras" separadas no código
(`decision_engine.py`) dizendo, cada uma à sua maneira, para onde um lead pode
avançar no funil de vendas. Elas nunca eram comparadas entre si — se alguém
mudasse uma sem lembrar da outra, o sistema podia ficar com regras
contraditórias sem nenhum aviso.

**Agora:** existe um teste automatizado que compara as duas listas a cada
execução. Se no futuro alguém adicionar uma nova fase, um novo tipo de agente,
ou reordenar o funil numa das listas sem atualizar a outra, o teste falha
imediatamente com uma mensagem dizendo exatamente qual transição ficou
desalinhada — em vez de o problema só aparecer meses depois como um lead
"pulando" uma etapa no Kanban sem explicação (o mesmo tipo de sintoma já
observado uma vez, descrito na Motivação acima).

Nenhum comportamento do sistema em produção mudou — só foi adicionada essa
rede de segurança.

**Para validar:** Cenários T1 e T2, acima — já executados e registrados por
mim durante a implementação (não há UI/WhatsApp envolvido nesta fase, então
não há teste manual pendente do usuário).

---

## Ajustes Possíveis Pós-Implementação

1. **`_PHASE_ID_TO_CATEGORY` colapsa p3a/p3b em "apresentation"** — em
   `backend-crm/routes/executor.py:266` e `backend-crm/routes/playground.py:194`.
   A ação `advance_phase` do Fluxo de Venda, quando configurada nas fases
   p3a (pré-agendamento) ou p3b (agendamento), sempre persiste a categoria
   como `"apresentation"`, nunca `"pre-agendamento"`/`"agendamento"` — possível
   bug silencioso para builders que configurem `advance_phase` nessas fases.
2. **`_CATEGORY_TO_PHASE_ID` (decision_engine.py:1112) diverge de
   `_PHASE_ID_TO_CATEGORY`** — o primeiro mapeia p3a/p3b corretamente
   (sem colapsar), o segundo colapsa ambos em "apresentation". Duas fontes
   inconsistentes para a mesma tradução phase_id↔categoria.

Ambos ficam fora do escopo deste item (que trata só de
`_ALLOWED_ADVANCE`/`_SALES_FLOW_PHASE_SEQUENCE_BY_AGENT_MODE`) — registrar para
triagem do usuário na graduação.
