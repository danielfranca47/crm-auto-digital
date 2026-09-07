# Kanban mobile: colunas verticais no retrato, horizontais na paisagem

**Branch:** `feat/kanban-mobile-orientacao`
**Status:** Em andamento

---

## Motivação

A página do Kanban (`frontend-crm`) funciona bem no desktop, mas a experiência
em mobile está ruim. Pedido do utilizador: colunas empilhadas na vertical
quando o telemóvel está na orientação normal (retrato), e lado a lado na
horizontal quando o utilizador vira o telemóvel (paisagem).

---

## Problemas Identificados (estado anterior)

1. **Colunas sempre em layout horizontal:** `KanbanBoard.tsx:544` renderiza o
   container das colunas com `flex gap-4 overflow-x-auto` fixo — sem nenhuma
   ramificação por tamanho de tela ou orientação.
2. **Largura de coluna fixa:** `KanbanColumn.tsx:41` usa `w-72 flex-shrink-0`
   fixo — não há modo "largura total" para empilhar verticalmente.
3. **Hook de mobile existente, mas não usado:** `hooks/use-mobile.tsx` já tem
   `useIsMobile()` (breakpoint 768px), mas não é usado no Kanban nem no
   header. Não havia nenhum uso de `matchMedia('orientation: ...')` no
   projeto.
4. **Header sem tratamento responsivo:** `CrmHeader.tsx:30` é uma única linha
   `flex items-center justify-between` sem `flex-wrap` — título, busca
   (`SearchAutocomplete`, `flex-1 max-w-md mx-8`) e 4 botões não cabem numa
   tela de telemóvel e estouram horizontalmente, tornando a página
   inutilizável em mobile independentemente da direção das colunas.

---

## Abordagem

Detectar "mobile + retrato" via um novo hook reativo (`useIsPortrait`, ao
lado do `useIsMobile` já existente) e usar isso para alternar a direção do
container de colunas e a largura de cada coluna. O cabeçalho é ajustado
separadamente, só com classes responsivas do Tailwind (sem JS).

```
useIsMobile() && useIsPortrait()
  true  → colunas empilhadas (flex-col, w-full) — retrato
  false → colunas lado a lado (flex-row, overflow-x-auto, w-72) — atual
          (cobre desktop e mobile em paisagem)
```

Decisão registrada: no modo retrato as colunas ficam todas empilhadas e
abertas (sem accordion/colapsáveis) — mantém o pedido original simples; cada
coluna já tem scroll interno próprio (`KanbanColumn.tsx:57`,
`calc(100vh - 200px)`).

---

## Plano de Implementação

### Fase 1 — Layout responsivo do Kanban + header mobile

**Objetivo:** colunas alternam vertical/horizontal por orientação em mobile,
e o header não quebra em telas estreitas.

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/hooks/use-mobile.tsx` | Novo hook `useIsPortrait()` via `matchMedia('(orientation: portrait)')` |
| `frontend-crm/src/components/KanbanBoard.tsx` | `stackVertical = useIsMobile() && useIsPortrait()`; container de colunas alterna `flex-col`/`flex-row overflow-x-auto`; passa `fullWidth={stackVertical}` para `KanbanColumn` |
| `frontend-crm/src/components/KanbanColumn.tsx` | Novo prop `fullWidth?: boolean`; largura `w-full` ou `w-72 flex-shrink-0` |
| `frontend-crm/src/components/CrmHeader.tsx` | Header com `flex-wrap`; título menor em telas pequenas; botões com `flex-wrap` |
| `frontend-crm/src/components/SearchAutocomplete.tsx` | Wrapper passa a `w-full` + `order-3` em mobile (cai para linha própria abaixo de título/botões), mantém `flex-1 max-w-md mx-8` em `sm:` (desktop inalterado) |

---

## Checks de Validação

### Cenário P1 — Mobile retrato: colunas empilhadas
- [ ] Emular viewport mobile em retrato (ex.: 390x844)
- [ ] Confirmar: colunas do Kanban aparecem empilhadas verticalmente, largura total
- [ ] Confirmar: header não estoura horizontalmente

### Cenário P2 — Mobile paisagem: colunas lado a lado
- [ ] Girar o mesmo viewport para paisagem (ex.: 844x390)
- [ ] Confirmar: colunas voltam a ficar lado a lado com scroll horizontal (comportamento atual)

### Cenário P3 — Desktop sem regressão
- [ ] Redimensionar para desktop (ex.: 1440x900)
- [ ] Confirmar: layout idêntico ao estado anterior (colunas horizontais, header em uma linha)

### Cenário P4 — Drag-and-drop nos 3 modos
- [ ] Arrastar um lead entre colunas em retrato, paisagem e desktop
- [ ] Confirmar: `@dnd-kit` continua funcionando sem alteração de comportamento

---

## Ajustes Possíveis Pós-Implementação

- Se o número de colunas crescer muito, empilhar tudo em retrato pode deixar
  a página longa para rolar — accordion/colapsável foi avaliado e descartado
  nesta iteração por decisão do utilizador (manter simples).
