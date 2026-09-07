# Kanban mobile: accordion/colapso de colunas no retrato

**Branch:** `feat/kanban-mobile-accordion-colunas`
**Status:** Todos os cenários validados (07/09/2026)

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`kanban-mobile-orientacao.md` (colunas verticais no retrato, horizontais na
paisagem, graduado em 07/09/2026).

Na implementação graduada, o modo retrato empilha **todas** as colunas do
pipeline abertas, uma embaixo da outra — decisão consciente para manter o
escopo simples (ver `docs/architecture/kanban-responsive.md`). Se o número de
colunas do pipeline crescer (hoje são 8: À Prospectar, Qualificação,
Apresentação, Pré-Agendamento, Agendamento, Acompanhamento, Fechamento, Lista
de Clientes), a página em retrato fica muito longa para rolar, mesmo cada
coluna tendo scroll interno próprio.

---

## Problemas Identificados (estado anterior)

1. **Sem colapso de colunas:** `KanbanColumn.tsx` sempre renderiza a lista
   completa de leads — não há forma de esconder o conteúdo de uma coluna
   para reduzir o comprimento da página no modo retrato.

---

## Abordagem

Colapso **manual** por coluna (usuário toca no cabeçalho), só no modo
retrato mobile (`stackVertical`). Todas as colunas começam abertas. Estado
lembrado via `localStorage`. Arrastar um lead sobre uma coluna colapsada a
expande automaticamente.

```
Usuário toca no cabeçalho da coluna → toggle(columnId)
  ├─ estava aberta → colapsa (esconde lista de leads, mantém cabeçalho)
  └─ estava colapsada → expande

Drag sobre coluna colapsada (onDragOver) → expand(columnId) automaticamente
```

---

## Plano de Implementação

### Fase 1 — Hook de colapso + UI + auto-expand no drag

**Objetivo:** colunas colapsáveis manualmente no retrato mobile, com estado
persistido e auto-expand durante drag-and-drop.

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/hooks/useCollapsedColumns.ts` | Novo hook: estado de colunas colapsadas + persistência em `localStorage` |
| `frontend-crm/src/components/KanbanColumn.tsx` | Botão de colapso (chevron) no cabeçalho; `setNodeRef` movido para o wrapper externo; conteúdo só renderiza se não colapsado |
| `frontend-crm/src/components/KanbanBoard.tsx` | Usa o hook; passa props de colapso para `KanbanColumn`; auto-expand em `handleDragOver` |
| `docs/architecture/kanban-responsive.md` | Nova seção "Colapso de colunas (retrato mobile)" |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `6287872` | hook de colapso + UI + auto-expand no drag |

**Detalhes do commit `6287872`:**
- `frontend-crm/src/hooks/useCollapsedColumns.ts` — novo hook, estado + localStorage
- `frontend-crm/src/components/KanbanColumn.tsx` — botão chevron no cabeçalho; `setNodeRef` movido para o wrapper externo; conteúdo condicional
- `frontend-crm/src/components/KanbanBoard.tsx` — usa o hook; passa props; auto-expand em `handleDragOver`
- `docs/architecture/kanban-responsive.md` — nova seção "Colapso de colunas (retrato mobile)"

### Relatório da Fase 1 — o que mudou na prática

**Antes:** no retrato mobile, todas as colunas do pipeline ficavam sempre
abertas, uma embaixo da outra — sem forma de esconder as que você não quer
ver no momento.

**Agora:** cada coluna tem uma setinha (chevron) ao lado do nome; tocando
nela, a coluna fecha (só o cabeçalho com o nome e a contagem de leads fica
visível) e a página encolhe. Tocar de novo abre. O estado de aberto/fechado
fica salvo no navegador — se fechar uma coluna e recarregar a página, ela
continua fechada. Se você arrastar um lead para cima de uma coluna fechada,
ela abre sozinha para você ver onde está soltando. Em desktop e no celular
na horizontal, nada mudou — não existe botão de fechar ali.

**Para validar:** Cenários P1, P2, P3 e P4, abaixo.

---

## Checks de Validação

### Cenário P1 — Colapsar/expandir manualmente (retrato)
- [x] Emular viewport mobile em retrato (ex.: 390x844)
- [x] Clicar no cabeçalho de uma coluna
- [x] Confirmar: lista de leads esconde, cabeçalho continua visível, ícone do chevron muda de direção
- [x] Clicar de novo → confirmar que expande
- **Validado em:** 07/09/2026 — testado via Chrome DevTools MCP. Coluna "À Prospectar" colapsou ao clicar (chevron `>`, só cabeçalho + contagem visíveis), demais colunas continuaram abertas normalmente.

### Cenário P2 — Persistência entre recarregamentos
- [x] Colapsar uma coluna
- [x] Recarregar a página (`F5`)
- [x] Confirmar: a coluna continua colapsada
- **Validado em:** 07/09/2026 — após reload, `aria-label` do botão da coluna colapsada permaneceu "Expandir coluna" (`aria-expanded="false"`), confirmando leitura correta do `localStorage`.

### Cenário P3 — Auto-expand durante drag
- [x] Colapsar uma coluna que tenha leads
- [x] Arrastar um lead de outra coluna até a coluna colapsada
- [x] Confirmar: a coluna expande sozinha durante o arrasto e o drop funciona normalmente
- **Validado em:** 07/09/2026 — simulação de drag via eventos de ponteiro (mousedown/mousemove em passos/mouseup) sobre a coluna colapsada: o botão mudou de "Expandir coluna" para "Colapsar coluna" durante o arrasto (auto-expand confirmado) e o lead foi movido com sucesso (contagens das colunas atualizaram corretamente). Nota: a ferramenta de drag automática de alto nível (`drag(from,to)`) não gerou eventos de ponteiro suficientes para o dnd-kit detectar o hover corretamente nesta viewport — mesma limitação de ferramenta já registrada na implementação `kanban-mobile-orientacao`; a simulação manual de eventos contornou isso.

### Cenário P4 — Sem regressão em desktop e paisagem
- [x] Verificar em desktop (ex.: 1440x900) e em paisagem mobile (ex.: 700x350)
- [x] Confirmar: nenhum botão de colapso aparece; colunas sempre abertas, como antes desta implementação
- **Validado em:** 07/09/2026 — confirmado em ambos os viewports via screenshot/DOM: nenhum botão com `aria-label` de colapso presente, colunas lado a lado como no comportamento pré-existente.

---

## Ajustes Possíveis Pós-Implementação

Nenhum identificado durante os testes desta fase.
