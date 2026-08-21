# Fluxo de Venda — bloco de Lógica de Ramificação (branching real, estilo ManyChat/n8n)

**Branch:** `feat-fluxo-vendas-ramificacao` (criada a partir de `fix-fluxo-vendas-sequencial`)
**Status:** Em andamento

---

## Motivação

Depois de graduar `fix-fluxo-vendas-sequencial.md` (gating sequencial de gatilhos, guardrail de
transição de fase, funil visual no Kanban), o utilizador observou o modal "Adicionar ao gatilho"
→ aba Lógica → bloco Condição e apontou uma limitação: hoje "Condição a avaliar", "Caminho SIM" e
"Caminho NÃO" são três campos de **texto livre** — não uma lógica executável. Pediu para
transformar isto num nó de ramificação real, visual e hierárquico (inspirado em ManyChat/n8n):
nome da lógica em vez de "condição a avaliar"; caminhos nomeados e renomeáveis (não fixos
sim/não), extensíveis a N caminhos; cada caminho com o seu critério de avaliação pela IA; blocos
filhos reais dentro de cada caminho (não descrição em texto); e, como consequência, redução de
poluição de tokens — depois de um lead seguir por um caminho, os blocos dos caminhos irmãos ficam
fora do prompt enviado à IA.

Isto encaixa no objetivo mais amplo já discutido nesta sessão: depender menos do "raciocínio
solto" da LLM a cada turno e mais de guardrails/estrutura determinística — a mesma motivação por
trás do gating sequencial já construído em `fix-fluxo-vendas-sequencial.md`.

---

## Problemas Identificados (estado anterior)

1. **Bloco `condicao` 100% inerte:** `backend-executors/app/services/decision_engine.py:649-657`
   só empurra `{"type":"condition", "condition", "branch_yes", "branch_no"}` para `system_actions`
   — nada em `backend-executors/app/runners/whatsapp.py` nem em
   `backend-crm/routes/executor.py::_dispatch_system_actions` (276-431) trata `type == "condition"`;
   cai no `if/elif` sem `else`, é silenciosamente descartado. Confirmado também por
   `docs/implementations/sales-flow-webhook-condicao-espera-runtime.md` (stub nunca implementado)
   — este trabalho absorve e substitui a parte de `condicao` desse stub; `webhook`/`espera`
   continuam fora de escopo.
2. **Modelo de dados sem noção de ramo:** `SalesFlowPhaseData.blocks: SalesFlowBlock[]` é uma
   lista plana sem `parentId`/`children`. O "agrupamento visual" que já existe (blocos indentados
   sob um gatilho) é puramente um truque de render em `PhaseSection`
   (`frontend-crm/src/components/agente/CamadaFluxoVenda.tsx:1083-1171`) — não persiste nada.
3. **Gating sequencial (Fase anterior) é um único booleano global por fase:** `_prereqs_satisfied`
   em `_evaluate_sales_flow_phases` não distingue "ramos" — não há como um gatilho dentro de um
   caminho A ficar isolado de um gatilho no caminho B.
4. **Campos "Caminho SIM"/"Caminho NÃO" são texto livre**, sem lista extensível de caminhos e sem
   mecanismo de avaliação por LLM.

---

## Abordagem

```
Bloco `condicao` vira um nó de ramificação com N `branches: {id, label, criteria}[]`
  → blocos filhos ganham `branch_group_id` (= id do nó) + `branch_id` (= qual ramo)
  → prompt da Mãe ganha bloco [LÓGICA DE RAMIFICAÇÃO] (mesmo padrão de [DETECÇÃO DE INTENÇÃO]
     já usado por intent_trigger) — Mãe devolve branch_selections: {node_id: branch_id} no
     MESMO JSON que já produz route_to/detected_intents (sem chamada de LLM extra)
  → _evaluate_sales_flow_phases: bloco com branch_group_id só é avaliado se
     active_branches.get(branch_group_id) == branch_id; senão `continue` antes de tocar
     prompt_injections/system_actions (é aqui que a redução de tokens acontece)
  → gating sequencial (_prereqs_satisfied) passa a ser por escopo (root vs cada ramo ativo),
     isolando o gatilho de um ramo dos gatilhos dos ramos irmãos
  → opcional "sticky" (default ligado): ramo escolhido persiste em leads.branches_selected
     (nova coluna, mesmo padrão de triggers_fired) — deixa de reperguntar à Mãe nos turnos
     seguintes, mais economia de tokens
```

Decisões de desenho completas (com justificação) estão registadas no plano aprovado em
`C:\Users\Daniel França\.claude\plans\cryptic-chasing-bengio.md`.

### Fora de escopo (deliberado)

- `webhook` e `espera` continuam sem execução em runtime.
- Ramificação de segundo nível na UI (ramo contendo outro nó `condicao`) — modelo de dados já
  suporta (via `branch_group_id` genérico), mas o editor visual desta versão não expõe.
- Drag-and-drop de blocos dentro de um ramo — inserção sempre no fim do ramo.
- Migração de blocos `condicao` antigos — como nunca tiveram efeito real, um bloco com o shape
  antigo é apresentado como "desatualizado — remova e reconfigure", sem migração de dados.

---

## Plano de Implementação

### Fase 1 — Backend: motor de ramificação + escolha pela Mãe

**Objetivo:** `_evaluate_sales_flow_phases` passa a avaliar ramos de verdade; `MotherDecision`
ganha `branch_selections`; persistência opcional (`sticky`) via `leads.branches_selected`.

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/orchestrator_models.py` | `MotherDecision.branch_selections: Dict[str,str]` |
| `backend-executors/app/services/decision_engine.py` | `_collect_branch_nodes_for_lead_phase()`, bloco `[LÓGICA DE RAMIFICAÇÃO]` no prompt da Mãe, `prereqs_satisfied_by_scope` (troca do booleano único), filtro de escopo de ramo no loop, `_load_branches_selected_map()`, `mark_branch_selected` em `compose_decision_output` |
| `backend-crm/database.py` | `ensure_column(leads.branches_selected)` |
| `backend-crm/routes/executor.py`, `backend-crm/routes/playground.py` | tratar `mark_branch_selected` (mesmo padrão de `mark_trigger_fired`) |
| `backend-crm/services/ai_orchestrator/orchestrator.py` | conferir os 3 pontos de construção de `ContextBundle` (308, 390, 808) |
| `backend-executors/tests/test_sales_flow_branching.py` (novo) | cobertura da ramificação |

**Nota de implementação:** o `mark_branch_selected` acabou por ser gerado dentro do próprio
`_evaluate_sales_flow_phases()` (no ponto em que o nó `condicao` resolve o ramo), não como
código adicional em `compose_decision_output` — o `system_actions` desse resultado já é
copiado para `decision.system_actions` pelo caminho existente, então não foi preciso tocar
`compose_decision_output` além de passar `branch_selections` na chamada.

**Confirmado (Passo de paridade Playground ↔ WhatsApp real):** os 3 pontos que constroem
`ContextBundle` (`orchestrator.py:308, 390, 808`) usam todos o mesmo helper `_load_lead()`
(`SELECT * FROM leads` + `{key: row[key] for key in row.keys()}`) — a nova coluna
`branches_selected` chega automaticamente aos 3 caminhos (inbound real, n8n, playground) sem
precisar de mudança em `enrich_context_bundle()`.

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `ce311b2` | Motor de ramificação completo: schema, engine, persistência, testes |

**Detalhes do commit `ce311b2`:**
- `orchestrator_models.py` — `MotherDecision.branch_selections: Dict[str,str]`
- `decision_engine.py` — `_load_branches_selected_map`, `_collect_branch_nodes_for_lead_phase`,
  bloco `[LÓGICA DE RAMIFICAÇÃO]` no prompt da Mãe, reescrita de `_evaluate_sales_flow_phases`
  (filtro de escopo de ramo, resolução do nó `condicao`, `prereqs_satisfied_by_scope`), 5 call
  sites actualizados para passar `branch_selections`
- `database.py` — `ensure_column(leads.branches_selected)`
- `executor.py`, `playground.py` — dispatch de `mark_branch_selected`
- `test_sales_flow_branching.py` — 15 testes novos

### Fase 2 — Frontend: schema + formulário do nó de ramificação

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/types/agente.ts` | `SalesFlowBranch`, `SalesFlowBlock.branches/sticky/branch_group_id/branch_id`, unificar label divergente |
| `frontend-crm/src/components/agente/CamadaFluxoVenda.tsx` | `case 'condicao'` reescrito: nome da lógica, lista dinâmica de ramos (add/remove/renomear), critério por ramo, checkbox "fixar caminho" |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `dc221db` | Schema + formulário do nó de ramificação |

**Detalhes do commit `dc221db`:**
- `types/agente.ts` — `SalesFlowBranch`, campos novos em `SalesFlowBlock`, label unificado
- `CamadaFluxoVenda.tsx` — `emptyBlock('condicao')` semeia 2 caminhos + sticky=true;
  `blockSummary` mostra nome + contagem; `BlockForm` reescreve o formulário completo, com
  aviso de "bloco desatualizado" para o formato antigo

`tsc --noEmit` limpo — sem validação visual ainda (é a Fase 3, que adiciona a renderização
aninhada dos caminhos e o botão de adicionar bloco a um caminho).

### Fase 3 — Frontend: render aninhado + "adicionar bloco a este caminho"

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/components/agente/CamadaFluxoVenda.tsx` | `PhaseSection` reconhece nó de ramificação e sub-agrupa por `branch_id`; novo `saveBranchBlock()`; exclusão do bucket genérico |

### Fase 4 — Validação ao vivo + docs + graduação

Playground (chrome-devtools MCP) no perfil de teste "Daniel", `docs/architecture/sales-flow.md`
atualizado, `sales-flow-webhook-condicao-espera-runtime.md` com a secção `condicao` removida,
graduação deste arquivo.

---

## Checks de Validação

### Fase 1 — Motor de ramificação (backend)
- [x] `python -m pytest tests/test_sales_flow_branching.py -v` — 15/15 passam
- [x] Suite completa sem regressão — comparado via `git stash` contra a baseline limpa:
      65 falhas pré-existentes idênticas antes/depois (não relacionadas a este trabalho —
      `test_qualification_contract.py`, `test_qualification_state_loop.py`, etc., falham
      igualmente sem nenhuma mudança); 172 passed no branch (157 baseline + 15 novos)
- **Validado em:** 22/08/2026 — automatizado (pytest), sem intervenção manual necessária

---

## Ajustes Possíveis Pós-Implementação

_A preencher na graduação._
