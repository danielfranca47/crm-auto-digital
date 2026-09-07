# Kanban — Layout Responsivo (Mobile)

Comportamento do quadro Kanban (`frontend-crm`) em diferentes tamanhos e
orientações de tela.

---

## Regra de layout

O container das colunas alterna entre vertical (empilhado) e horizontal
(lado a lado, com scroll) com base em **largura + orientação**, não só
largura:

```
isMobile (largura < 768px) && isPortrait (orientação retrato)
  true  → colunas empilhadas: flex-col, cada coluna w-full
  false → colunas lado a lado: flex-row + overflow-x-auto, cada coluna w-72
          (cobre desktop e mobile em paisagem)
```

- `useIsMobile()` e `useIsPortrait()` — `frontend-crm/src/hooks/use-mobile.tsx`.
  `useIsPortrait()` usa `matchMedia('(orientation: portrait)')` com listener
  de `change`, reagindo a rotação do dispositivo em tempo real.
- `stackVertical = isMobile && isPortrait` — calculado em
  `frontend-crm/src/components/KanbanBoard.tsx` e passado como prop
  `fullWidth` para `KanbanColumn` (`frontend-crm/src/components/KanbanColumn.tsx`),
  que decide `w-full` vs. `w-72 flex-shrink-0`.
- No modo empilhado (retrato), cada coluna pode ser colapsada/expandida
  manualmente (ver "Colapso de colunas", abaixo). Cada coluna mantém seu
  próprio scroll interno vertical (`calc(100vh - 200px)`) quando expandida.
- A lógica de drag-and-drop (`@dnd-kit`, sensors, `closestCorners`) não muda
  entre os modos — só a direção do flex container e a largura da coluna.

## Colapso de colunas (retrato mobile)

Só disponível quando `stackVertical` é `true` (retrato mobile) — em
desktop e paisagem não existe botão de colapso, colunas sempre mostram todo
o conteúdo.

- `useCollapsedColumns()` — `frontend-crm/src/hooks/useCollapsedColumns.ts`.
  Guarda o `Set` de ids de colunas colapsadas, persistido em `localStorage`
  (chave `"kanban:collapsedColumns"`) — preferência por navegador/
  dispositivo, não sincronizada entre aparelhos, não passa pelo backend.
  Expõe `isCollapsed(id)`, `toggle(id)` e `expand(id)` (idempotente).
- Todas as colunas começam **abertas** por padrão — nenhuma colapsa
  automaticamente (ex.: por estar vazia).
- `KanbanColumn.tsx`: prop `collapsible` (= `stackVertical`) controla se o
  botão de colapso (chevron) aparece no cabeçalho; `isCollapsed` esconde o
  bloco de leads (o cabeçalho com título e contagem continua sempre
  visível). O `useDroppable` (`setNodeRef`) fica no wrapper externo da
  coluna (não só no bloco de leads), para a coluna continuar sendo uma área
  de drop válida mesmo colapsada.
- Auto-expand durante drag: `KanbanBoard.tsx` → `handleDragOver` chama
  `expand(overColumn.id)` sempre que `stackVertical` é `true` e o ponteiro
  está sobre uma coluna — se ela estiver colapsada, expande sozinha para
  revelar o conteúdo antes do drop.

## Header (`CrmHeader.tsx`)

Usa `flex-wrap` (Tailwind, sem JS) para não estourar em telas estreitas:
título, busca (`SearchAutocomplete`) e bloco de botões podem cair em linhas
separadas. A busca usa `order-3` para sempre cair por último em mobile,
ocupando a largura toda da própria linha.

## Limitação conhecida

Um lead com uma URL muito longa e sem espaços no campo `observations` pode
causar um pequeno overflow horizontal da página no modo empilhado (o texto
não quebra dentro do `line-clamp-2` de `LeadCard.tsx`). Pré-existente ao
layout responsivo (já ocorria, de forma pior, no modo horizontal fixo em
telas estreitas). Correção rastreada em
`docs/implementations/fix-leadcard-obs-url-overflow.md`.
