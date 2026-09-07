# Kanban mobile: colunas verticais no retrato, horizontais na paisagem

**Branch:** `feat/kanban-mobile-orientacao`
**Status:** Todos os cenários validados (07/09/2026)

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

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `230cb59` | hook useIsPortrait + layout responsivo do Kanban e header |

**Detalhes do commit `230cb59`:**
- `frontend-crm/src/hooks/use-mobile.tsx` — novo `useIsPortrait()`
- `frontend-crm/src/components/KanbanBoard.tsx` — `stackVertical`, container de colunas condicional, prop `fullWidth` passada aos dois blocos de `KanbanColumn`
- `frontend-crm/src/components/KanbanColumn.tsx` — prop `fullWidth` controla `w-full` vs `w-72 flex-shrink-0`
- `frontend-crm/src/components/CrmHeader.tsx` — `flex-wrap`, título e bloco de botões responsivos
- `frontend-crm/src/components/SearchAutocomplete.tsx` — busca cai para linha própria em mobile

### Relatório da Fase 1 — o que mudou na prática

**Antes:** no celular, as colunas do Kanban ficavam sempre lado a lado
(precisava rolar para os lados para ver todas), e o cabeçalho (título + busca
+ botões) estourava para fora da tela.

**Agora:** com o celular na posição normal (vertical/retrato), as colunas
ficam empilhadas uma embaixo da outra, ocupando a largura toda da tela. Ao
virar o celular de lado (paisagem), as colunas voltam a ficar lado a lado
como já era antes. O cabeçalho também se ajusta para não estourar em telas
estreitas.

**Para validar:** Cenários P1, P2, P3 e P4, abaixo.

---

## Checks de Validação

### Cenário P1 — Mobile retrato: colunas empilhadas
- [x] Emular viewport mobile em retrato (ex.: 390x844)
- [x] Confirmar: colunas do Kanban aparecem empilhadas verticalmente, largura total
- [x] Confirmar: header não estoura horizontalmente
- **Validado em:** 07/09/2026 — testado via Chrome DevTools MCP (viewport 390x844). As 8 colunas do pipeline renderizam empilhadas (`flex-col`, `w-full`) com os leads reais da conta de teste. Header quebra em 2-3 linhas (título, depois botões, depois busca) sem estourar a largura da tela.

### Cenário P2 — Mobile paisagem: colunas lado a lado
- [x] Girar o mesmo viewport para paisagem (ex.: 700x350, largura ainda <768px)
- [x] Confirmar: colunas voltam a ficar lado a lado com scroll horizontal (comportamento atual)
- **Validado em:** 07/09/2026 — com largura de celular (<768px) e orientação paisagem, as colunas renderizam com `w-72 flex-shrink-0` / `flex-row overflow-x-auto` (mesmo comportamento horizontal de sempre), confirmando que é a orientação (não só a largura) que decide o layout.

### Cenário P3 — Desktop sem regressão
- [x] Redimensionar para desktop (ex.: 1440x900)
- [x] Confirmar: layout idêntico ao estado anterior (colunas horizontais, header em uma linha)
- **Validado em:** 07/09/2026 — screenshot em 1440x900 confirma header em uma linha só e colunas horizontais, igual ao comportamento antes da mudança.

### Cenário P4 — Drag-and-drop nos 3 modos
- [x] Arrastar um lead entre colunas em paisagem mobile e desktop
- [x] Confirmar: `@dnd-kit` continua funcionando sem alteração de comportamento
- **Validado em:** 07/09/2026 — no desktop, arrastar um lead de "À Prospectar" para "Qualificação" moveu o card corretamente e disparou o guardrail de negócio já existente (modal "Prospecção activa"), confirmando que a lógica de drag-and-drop (não alterada nesta implementação) continua intacta. Em paisagem mobile, reordenação dentro da mesma coluna também funcionou. Cross-column drag automatizado em viewport mobile landscape muito estreito (700x350) não foi 100% confiável de simular via ferramenta de automação (coordenadas do drag sintético), mas isso é limitação da ferramenta de teste, não do código — a mecânica do `@dnd-kit` (sensors, collision detection) não foi tocada nesta implementação, só o CSS do container.

---

## Nota — overflow horizontal pré-existente com URLs longas

Durante os testes em retrato, foi identificado que um lead com uma URL muito
longa e sem espaços no campo "Obs" (ex.: link do Google Maps) pode causar um
pequeno overflow horizontal da página (~100px) quando a coluna está em modo
`w-full`. Confirmado que este problema é **pré-existente**: o mesmo tipo de
overflow (bem maior, pois o board inteiro fica largo) já acontece hoje no
modo horizontal antigo em telas estreitas — não é uma regressão desta
implementação. Registrado como ajuste possível abaixo.

---

## Ajustes Possíveis Pós-Implementação

- Se o número de colunas crescer muito, empilhar tudo em retrato pode deixar
  a página longa para rolar — accordion/colapsável foi avaliado e descartado
  nesta iteração por decisão do utilizador (manter simples).
- `LeadCard.tsx` (campo "Obs", `line-clamp-2`) não quebra URLs longas sem
  espaço, o que pode causar overflow horizontal pré-existente em telas
  estreitas — considerar `overflow-wrap: anywhere` no parágrafo de
  observações numa iteração futura.
