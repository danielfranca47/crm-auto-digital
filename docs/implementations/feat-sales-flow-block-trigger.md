# Gatilho leve `block_trigger` — trava de dependência para "Sem gatilho"

**Branch:** `feat/sales-flow-block-trigger`
**Status:** Em andamento

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

---

## Checks de Validação

### Cenário P1 — "Sem gatilho" sem dependência mantém comportamento legado
- [ ] Criar bloco de ação via "Sem gatilho" sem escolher "Depende de"
- [ ] Confirmar: nenhum bloco `block_trigger` persistido, JSON igual ao comportamento anterior

### Cenário P2 — "Sem gatilho" com dependência dispara no turno certo
- [ ] Criar bloco de ação via "Sem gatilho" com "Depende de" = "Fase Iniciada"
- [ ] Simular conversa no Playground: turno de entrada na fase → resposta do lead
- [ ] Confirmar: a ação dispara no turno seguinte à entrada na fase, não no mesmo turno

### Cenário P3 — Não repete em turnos seguintes
- [ ] Continuar a conversa por mais 1-2 turnos após o disparo do Cenário P2
- [ ] Confirmar: a ação não dispara de novo

### Cenário P4 — Dependência quebrada é sinalizada
- [ ] Remover o bloco "Fase Iniciada" referenciado por um `block_trigger` existente
- [ ] Confirmar: aviso "⚠ dependência quebrada — bloco removido" aparece no builder

---

## Ajustes Possíveis Pós-Implementação

- Retrofit: hoje só é possível anexar dependência a um grupo "Sem gatilho" **no momento da
  criação**. Grupos "Sem gatilho" já existentes na fase não têm gatilho editável — precisaria de
  lógica de inserção no início do array de blocos da fase (fora de escopo desta versão).
