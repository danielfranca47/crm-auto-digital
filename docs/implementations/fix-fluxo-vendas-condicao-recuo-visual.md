# Fix: renderizar `condicao` aninhado (recuado) dentro do grupo do gatilho que o precede

**Branch:** `feat-fluxo-vendas-ramificacao`
**Status:** Em andamento

---

## Motivação

Durante uma sessão de revisão do builder de Fluxo de Venda, o utilizador adicionou um bloco
`condicao` (Lógica de Ramificação) através do botão "+ ação/lógica" **dentro** do grupo do
"Phase Trigger — Auto ao entrar" na fase Apresentação. Na renderização, o card do `condicao`
apareceu no mesmo nível visual (mesma indentação, sem linha conectora) do bloco "mãe" — dando a
entender que seriam blocos paralelos/independentes, não mãe e filho.

Investigação confirmou: o **backend** (`decision_engine.py::_evaluate_sales_flow_phases`) já trata
`condicao` exatamente como um bloco de ação comum, gated pelo mesmo `last_trigger_active` do
gatilho mais próximo antes dele no array — a relação mãe/filho já existe de fato no motor de
decisão. O problema é 100% de renderização: `PhaseSection` (`CamadaFluxoVenda.tsx`) trata
`condicao` como um "boundary" de grupo (igual a um gatilho de verdade) no loop de agrupamento
visual, sempre iniciando um novo grupo de nível raiz — independente de como o bloco foi inserido
no array.

---

## Problemas Identificados (estado anterior)

1. **`condicao` sempre renderiza como grupo de nível raiz:**
   `frontend-crm/src/components/agente/CamadaFluxoVenda.tsx:1180-1184` — o loop de agrupamento de
   `PhaseSection` faz `flushCur()` + `groups.push({kind:'branch', node:b})` para QUALQUER bloco
   `condicao`, independente de ele ter sido inserido via "+ ação/lógica" (dentro de um grupo
   existente, logo após o último bloco daquele grupo no array — `saveGroupBlock`) ou como bloco
   solto. Resultado: nenhuma indicação visual de que o `condicao` herda o `last_trigger_active` do
   gatilho anterior no array.

---

## Abordagem

`condicao` deixa de ser tratado como boundary de grupo e passa a ser um item comum de
`group.actions` — como já acontece para `orientacao`/`mensagem`/`midia`, espelhando o que o
backend já faz. Só a renderização de item individual muda: se `b.typeId === 'condicao'`, desenhar
`<BranchGroupRow>` (componente já existente) em vez de `<BlockRow>` — reaproveitando a mecânica de
indentação/linha conectora que já existe para qualquer ação dentro de um grupo.

Nenhuma mudança de backend, tipos de dados (`SalesFlowBlock`/`SalesFlowBranch`), ou funções de
inserção/remoção de blocos (`saveBlock`/`saveGroupBlock`/`saveBranchBlock`/`removeBlock`) —
puramente o caminho de leitura/renderização em um único arquivo.

Plano completo (com validação via Explore + Plan agent) registado em
`C:\Users\Daniel França\.claude\plans\stateless-imagining-crane.md`.

---

## Plano de Implementação

### Fase 1 — Frontend: aninhar `condicao` no grupo do gatilho precedente

**Objetivo:** `PhaseSection` renderiza `condicao` recuado dentro do grupo do gatilho que o
precede no array, em vez de como card independente de nível raiz.

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/components/agente/CamadaFluxoVenda.tsx` | Loop de agrupamento (~1166-1192): remove o caso especial de `condicao`, colapsa `SimpleGroup \| BranchGroup` em `Group` único; render dos grupos (~1275-1279): remove o branch `kind === 'branch'` morto; render dos itens de `actions` (linha 1299): `condicao` → `<BranchGroupRow>`, resto → `<BlockRow>` (como hoje) |

```tsx
// ANTES — condicao sempre inicia um novo grupo de nível raiz
if (b.typeId === 'condicao') {
  flushCur();
  groups.push({ kind: 'branch', node: b });
  continue;
}

// DEPOIS — condicao cai no mesmo tratamento de qualquer ação (herda o gatilho do grupo atual)
// cai no `else { cur.actions.push(b) }` já existente
```

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | _(a preencher)_ | _(a preencher)_ |

---

## Checks de Validação

### Fase 1 — Aninhamento visual
- [ ] `npx tsc --noEmit` limpo em `frontend-crm/`
- [ ] `condicao` adicionado via "+ ação/lógica" dentro de um gatilho existente aparece recuado,
      com linha conectora, dentro do grupo desse gatilho (não mais como card independente)
- [ ] `condicao` sem gatilho precedente (primeiro bloco de uma fase vazia) continua aparecendo
      sob o rótulo "⚡ Sempre ao entrar na fase"
- [ ] Múltiplos `condicao`/ações intercaladas no mesmo grupo renderizam corretamente, sem
      chaves duplicadas nem quebra visual
- [ ] "+ ação/lógica" com um `condicao` como último item do grupo insere o novo bloco logo após
      o nó `condicao` no array (sem erro)

---

## Ajustes Possíveis Pós-Implementação

_A preencher na graduação._
