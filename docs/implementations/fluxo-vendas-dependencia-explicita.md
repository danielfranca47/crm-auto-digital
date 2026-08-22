# Dependência explícita entre gatilhos (`requires_block_id`) no Fluxo de Venda

**Branch:** `feat-fluxo-vendas-ramificacao`
**Status:** Em andamento

---

## Motivação

Discussão de arquitetura na sessão (não uma feature quebrada, uma limitação identificada): hoje
o encadeamento entre gatilhos sequenciais (`phase_trigger`, ou `kw_trigger`/`intent_trigger` com
`fire_once`) é **puramente posicional** — um gatilho só é liberado se o gatilho sequencial
imediatamente anterior no array (mesmo escopo — raiz ou o mesmo Caminho de uma ramificação) já
estiver satisfeito, via `_prereqs_satisfied_by_scope` (`decision_engine.py`). Esse mecanismo
permite satisfação **no mesmo turno** — na prática quase nunca causa problema (o lead não pode
"aceitar a tabela de preços" antes dela ter sido enviada), mas não é uma garantia técnica rígida.

O utilizador quer uma garantia explícita e nomeada: um gatilho poder declarar "só disparo depois
de **este bloco específico** já ter disparado num turno anterior — nunca no mesmo turno" — via
um seletor no builder (não texto livre), referenciando o **id** do bloco (imutável desde a
criação), não o seu nome/label (editável a qualquer momento) — para sobreviver a renomeações e a
uma futura reordenação de blocos na UI.

Expande o modelo de gating sequencial já existente (`fix-fluxo-vendas-sequencial.md`, graduado) e
a nomeação explícita de nós já usada por `condicao` (`fluxo-vendas-ramificacao.md`, graduado) —
mesma filosofia: tornar explícito o que hoje só existe implícito na posição do array.

---

## Problemas Identificados (estado anterior)

1. **Encadeamento entre gatilhos sequenciais é puramente posicional:**
   `_prereqs_satisfied_by_scope` (`decision_engine.py`) só sabe "o gatilho sequencial anterior
   no mesmo escopo" — não há como declarar uma dependência explícita a um bloco específico,
   nem uma garantia rígida de "nunca no mesmo turno" (o mecanismo atual aceita "antes deste
   turno OU disparando neste mesmo turno").
2. **Gatilhos (`kw_trigger`/`intent_trigger`/`phase_trigger`) não têm nome de exibição:** só
   `condicao` tem `label` — os demais só têm um resumo auto-gerado, por vezes truncado.

---

## Abordagem

Campo novo, opt-in, aditivo: `requires_block_id?: string` em blocos `kw_trigger`/`intent_trigger`,
referenciando o `id` de outro gatilho sequencial já existente na mesma fase. Quando presente, o
gatilho só pode disparar se o bloco referenciado já estiver persistido como disparado **antes**
deste turno (`leads.triggers_fired`/`leads.phases_triggered`) — nunca por ter disparado neste
mesmo turno. Blocos sem o campo continuam com o comportamento posicional atual, inalterado.

Reaproveita o `label` já existente em `SalesFlowBlock` (hoje só exposto para `condicao`),
estendido para `kw_trigger`/`intent_trigger` como nome de exibição opcional.

Referência quebrada (bloco apagado, OU bloco ainda existe mas deixou de ser sequencial — ex.:
`fire_once` desmarcado depois) **falha aberto** no backend (sem efeito, nunca bloqueia
permanentemente) e é sinalizada visualmente no builder, sem cascade-delete automático.

Proteção contra ciclo (A depende de B, B depende de A): o seletor filtra opções que fechariam
um ciclo de volta ao bloco atual.

Plano completo (com validação via Explore + Plan agent, 2 rodadas) registado em
`C:\Users\Daniel França\.claude\plans\stateless-imagining-crane.md`.

---

## Plano de Implementação

### Fase 1 — Backend: campo, resolução e gating

**Objetivo:** `_evaluate_sales_flow_phases()` passa a respeitar `requires_block_id` como trava
adicional, aditiva à trava posicional existente.

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/decision_engine.py` | import `Tuple`; `_build_block_lookup()`, `_requires_block_satisfied()` (fail-open: referência quebrada OU alvo não mais sequencial); combinação aditiva em `_locked` |
| `backend-executors/tests/test_sales_flow_requires_block_id.py` (novo) | cobertura: bloqueio/liberação, nunca-mesmo-turno, fail-open (2 casos), referência cross-fase |
| `docs/architecture/sales-flow.md` | nova subsecção "Dependência explícita (`requires_block_id`)" em "Modelo sequencial de trigger" |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `200b9cb` | Campo `requires_block_id`, resolução e gating no backend |

**Detalhes do commit `200b9cb`:**
- `decision_engine.py` — `_build_block_lookup()` (mapa `block_id → (block, phase_id)` de
  todas as fases), `_requires_block_satisfied()` (resolve contra estado persistido, nunca
  contra `fired` do mesmo turno; fail-open em referência quebrada OU bloco-alvo que deixou
  de ser sequencial); combinado aditivamente em `_locked` na avaliação de gatilhos, sem
  tocar `_prereqs_satisfied_by_scope`
- `test_sales_flow_requires_block_id.py` (novo) — 7 testes: bloqueio/liberação, garantia
  de "nunca no mesmo turno", fail-open (2 casos), referência cross-fase, comportamento
  inalterado sem o campo
- `sales-flow.md` — nova subsecção "2b) Dependência explícita (`requires_block_id`)"

Suite completa: 66 failed / 180 passed — idêntico ao baseline pré-existente (173 + 7
novos), sem regressão.

---

### Fase 2 — Frontend: seletor de dependência + nome do gatilho

**Objetivo:** builder permite nomear um gatilho e escolher, de um dropdown, outro gatilho
sequencial da mesma fase do qual ele depende; sinaliza dependência quebrada/inelegível.

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/types/agente.ts` | `SalesFlowBlock.requires_block_id`; comentário de `label` atualizado |
| `frontend-crm/src/components/agente/CamadaFluxoVenda.tsx` | `blockSummary()` prefere `label` para kw/intent trigger; helpers `isSequentialCapable`/`requiresChainIncludes`/`dependencyOptions`; `BlockForm` ganha campos "Nome do gatilho"/"Depende de"; `phaseBlocks` roteado por `BlockModal`/`RuleBuilderModal`/4 call sites; `BlockRow` sinaliza dependência quebrada |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | _(a preencher)_ | _(a preencher)_ |

---

## Checks de Validação

### Fase 1 — Backend
- [x] `pytest tests/test_sales_flow_requires_block_id.py -v` — todos passam
- [x] Suite completa sem regressão — 66 failed / 180 passed, idêntico à baseline de 66
      falhas pré-existentes documentada em `fix-fluxo-vendas-ramificacao.md` (173 + 7 novos)
- **Validado em:** 22/08/2026 — automatizado (pytest), sem intervenção manual necessária

### Fase 2 — Frontend
- [ ] `npx tsc --noEmit` limpo
- [ ] Criar gatilho, nomear, escolher dependência, salvar/recarregar/reabrir — valores persistem
- [ ] Remover bloco-alvo → aviso "dependência quebrada" aparece
- [ ] Desmarcar `fire_once` no bloco-alvo (sem remover) → mesmo aviso aparece
- [ ] Dependência circular (A→B, B→A) → opção não aparece no dropdown
- [ ] Teste funcional ao vivo (Playground): A (phase_trigger) → B (kw_trigger,
      `requires_block_id=A.id`); mensagem que dispara A e casaria com B no MESMO turno →
      B não dispara nesse turno, só no seguinte

---

## Ajustes Possíveis Pós-Implementação

_A preencher na graduação._
