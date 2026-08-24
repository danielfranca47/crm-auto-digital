# Gatilho leve `block_trigger` — trava de dependência para "Sem gatilho"

**Branch:** `feat/sales-flow-block-trigger`
**Status:** Todos os cenários validados (25/08/2026)

---

## Motivação

O Fluxo de Venda (Camada 7) já tem um mecanismo de sequenciamento — `requires_block_id`
("Depende de") — que faz um gatilho só ficar elegível depois que outro gatilho sequencial da
mesma fase já disparou num turno **anterior** (nunca no mesmo turno). Hoje esse campo só existe
na configuração de `kw_trigger`/`intent_trigger`.

O utilizador estava usando `intent_trigger` (Intenção IA) só para ter acesso a esse campo — não
precisa de nenhuma condição de conteúdo/intenção, só quer que a próxima pergunta dispare
automaticamente depois que a pergunta anterior ("Fase Iniciada") já foi respondida. Configurar um
`intent_trigger` inteiro (intenção obrigatória, fire_once, suppress_llm_response, etc.) para isso
é excesso de formulário para o que ele precisa. Pedido explícito: disponibilizar essa trava de
dependência também para blocos "Sem gatilho" — sem virar um 5º card no seletor de gatilhos.

---

## Abordagem

Novo `typeId` interno de gatilho **`block_trigger`**, nunca exposto como card no grid "Escolher
gatilho" — criado implicitamente quando o utilizador clica no card tracejado "Sem gatilho" e
opcionalmente escolhe uma dependência. Dispara `fired=True` exatamente uma vez por lead, assim
que `requires_block_id` já tiver disparado num turno anterior — sem nenhuma condição de
conteúdo. Reaproveita toda a infraestrutura de `requires_block_id`/gating sequencial já
existente. Se nenhuma dependência for escolhida, colapsa para o comportamento legado
(`triggerBlock = null`, sem persistir bloco nenhum) — retrocompatível.

Plano completo (arquivos, linhas, achados de validação): ver histórico da conversa de
planejamento; resumo por fase abaixo.

---

## Plano de Implementação

### Fase 1 — Backend: novo tipo `block_trigger` no motor de decisão

**Objetivo:** o motor (`decision_engine.py`) reconhece `block_trigger`, participa do gating
sequencial e da checagem de pendência de avanço de fase, e dispara exatamente uma vez.

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/decision_engine.py` | `_TRIGGER_TYPES` inclui `block_trigger`; `_is_sequential_trigger_block()` retorna `True` para ele; `_trigger_persisted_satisfied()` ganha caso dedicado; loop principal ganha `elif type_id == "block_trigger"` com checagem explícita de "já disparou" (sem isso, reenviaria a ação todo turno); `_phase_pending_sequential_triggers()` passa a contá-lo como pendência |
| `backend-executors/tests/test_sales_flow_block_trigger.py` | Novo — cobre bloqueio no turno 1, disparo no turno 2, não-repetição no turno 3, fail-open com referência quebrada, pendência de avanço de fase |
| `docs/architecture/sales-flow.md` | Tabela de triggers, seção "Modelo sequencial de trigger", tabela "Avaliação por tipo de trigger", seção "Guardrail de gatilhos pendentes" |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `9160f4c` | backend: block_trigger no decision_engine.py + testes + docs/architecture/sales-flow.md |

**Detalhes do commit `9160f4c`:**
- `backend-executors/app/services/decision_engine.py` — novo `typeId` `block_trigger`: sempre sequencial (`_is_sequential_trigger_block`), persistência via `triggers_fired` (`_trigger_persisted_satisfied`), novo `elif` no loop principal com checagem obrigatória de "já disparou" (sem ela, reenviaria a ação todo turno), e conta como pendência em `_phase_pending_sequential_triggers`
- `backend-executors/tests/test_sales_flow_block_trigger.py` — novo, 5 testes: bloqueio até dependência persistida, disparo único, não-repetição, fail-open, pendência de avanço de fase
- `docs/architecture/sales-flow.md` — documenta o novo tipo nas 4 seções afetadas

**Validação:** 12/12 testes passam (5 novos + 6 de regressão `requires_block_id` + comparação de baseline). Suite completa comparada byte-a-byte com `main` sem alteração: 80 falhas pré-existentes idênticas antes/depois — nenhuma regressão introduzida.

---

### Fase 2 — Frontend: opção "Depende de" dentro do fluxo "Sem gatilho"

**Objetivo:** builder oferece o campo de dependência ao escolher "Sem gatilho", sem novo card,
retrocompatível quando a dependência fica vazia.

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/types/agente.ts` | `block_trigger` na union `SalesFlowBlockTypeId` + `SALES_FLOW_BLOCK_TYPE_LABELS`; **não** entra em `SALES_FLOW_BLOCK_CATEGORIES.trigger.types` |
| `frontend-crm/src/components/agente/CamadaFluxoVenda.tsx` | `BLOCK_META`/`BLOCK_TYPE_LABELS` locais; `isSequentialCapable()`; `blockSummary()`; novo `case 'block_trigger'` no formulário (só campo "Depende de"); card "Sem gatilho" abre esse mini-passo; colapso para `triggerBlock = null` quando a dependência fica vazia; `TRIGGER_IDS` do agrupamento de listagem; banner de aviso da Fase 0 |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `337f12a` | frontend: campo "Depende de" no fluxo "Sem gatilho" + colapso retrocompatível |

**Detalhes do commit `337f12a`:**
- `frontend-crm/src/types/agente.ts` — `block_trigger` na union e em `SALES_FLOW_BLOCK_TYPE_LABELS`; não entra em `SALES_FLOW_BLOCK_CATEGORIES` (não vira card)
- `frontend-crm/src/components/agente/CamadaFluxoVenda.tsx` — `BLOCK_META`/`BLOCK_TYPE_LABELS`/`blockSummary`/`isSequentialCapable`/`TRIGGER_IDS`/banner da Fase 0 reconhecem `block_trigger`; novo `case` no formulário (só "Depende de"); card "Sem gatilho" abre esse mini-passo; `confirmTriggerConfig()` colapsa para `triggerBlock = null` quando a dependência fica vazia

**Validação:** `tsc --noEmit` sem erros (Records exaustivos por `typeId` corretos). Falta validação manual via browser (checks abaixo).

---

## Checks de Validação

Testado ao vivo na conta de teste local (`_conta-teste-local.md`, AI Profile "Daniel"), com
`backend-executors`/`frontend-crm` rodando a partir desta worktree (código com as mudanças) e
`backend-core`/`backend-crm` a partir do checkout principal (código inalterado). Blocos de teste
criados e removidos ao final — perfil restaurado ao estado original (12 blocos, Fase 2 intacta).

### Cenário P1 — "Sem gatilho" sem dependência mantém comportamento legado
- [x] Criar bloco de ação via "Sem gatilho" sem escolher "Depende de"
- [x] Confirmar: rótulo volta a "⚡ Sempre ao entrar na fase" — `triggerBlock` colapsa para `null`, nenhum `block_trigger` fantasma
- **Validado em:** 25/08/2026 — Fase 0, confirmado na tela "Montar regra"

### Cenário P2 — "Sem gatilho" com dependência dispara no turno certo
- [x] Criar bloco de ação via "Sem gatilho" com "Depende de" = "Fase Iniciada"
- [x] Simular conversa no Playground: turno de entrada na fase → resposta do lead
- [x] Confirmar: a ação dispara no turno seguinte à entrada na fase, não no mesmo turno
- **Validado em:** 25/08/2026 — Fase 0, turno 1 só disparou "Fase Iniciada"; turno 2 (após resposta do lead) disparou o `block_trigger`

### Cenário P3 — Não repete em turnos seguintes
- [x] Continuar a conversa por mais 1-2 turnos após o disparo do Cenário P2
- [x] Confirmar: a ação não dispara de novo
- **Validado em:** 25/08/2026 — turno 3, LLM respondeu normalmente sem repetir a mensagem fixa

### Cenário P4 — Dependência quebrada é sinalizada
- [x] Remover o bloco "Fase Iniciada" referenciado por um `block_trigger` existente
- [x] Confirmar: aviso "⚠ dependência quebrada — bloco removido" aparece no builder
- **Validado em:** 25/08/2026 — aviso apareceu imediatamente após remover o bloco referenciado (achado bônus, durante a limpeza dos blocos de teste)

---

## Ajustes Possíveis Pós-Implementação

- Retrofit: hoje só é possível anexar dependência a um grupo "Sem gatilho" **no momento da
  criação**. Grupos "Sem gatilho" já existentes na fase não têm gatilho editável — precisaria de
  lógica de inserção no início do array de blocos da fase (fora de escopo desta versão).
