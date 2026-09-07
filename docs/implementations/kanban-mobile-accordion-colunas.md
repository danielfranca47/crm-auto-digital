# Kanban mobile: accordion/colapso de colunas no retrato

**Branch:** (a definir — nasce no Passo 0/1 do guia de implementação)
**Status:** Aguardando Plan Mode

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

## Problema a investigar

Avaliar se colunas vazias ou pouco usadas deveriam nascer colapsadas (só o
cabeçalho visível, expandindo ao toque) no modo retrato mobile, para reduzir
o comprimento total da página.

## Notas para o Plan Mode

- Ler `docs/architecture/kanban-responsive.md` antes de diagnosticar.
- Decidir: colapso automático por critério (ex.: coluna vazia) ou controlado
  pelo usuário (lembrar preferência)?
- Considerar impacto na acessibilidade e no drag-and-drop (`@dnd-kit`) — uma
  coluna colapsada ainda precisa aceitar itens soltos nela.
