# Fix: overflow horizontal com URL longa no campo Obs do LeadCard

**Branch:** (a definir — nasce no Passo 0/1 do guia de implementação)
**Status:** Aguardando Plan Mode

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`kanban-mobile-orientacao.md` (colunas verticais no retrato, horizontais na
paisagem, graduado em 07/09/2026).

Durante os testes daquela implementação (Cenário P1, viewport mobile
390x844), foi identificado que um lead com uma URL muito longa e sem espaços
no campo "Obs" (ex.: link do Google Maps) causa um pequeno overflow
horizontal da página (~100px) quando a coluna está em largura total
(`w-full`, modo retrato mobile). Confirmado que este problema já existe hoje
no modo horizontal (`w-72` fixo) em telas estreitas, de forma pior (a página
inteira fica maior ainda) — não é uma regressão da implementação graduada,
mas ficou mais visível nela.

## Causa provável

`frontend-crm/src/components/LeadCard.tsx` — o parágrafo de observações usa
`line-clamp-2`, que limita linhas verticalmente mas não força quebra de
palavras/URLs sem espaço. Uma URL longa como uma "palavra" única não quebra
e vaza horizontalmente pela largura do card.

## Notas para o Plan Mode

- Correção provável: adicionar `overflow-wrap: anywhere` (ou classe
  Tailwind equivalente, ex. `break-words`/`break-all`) ao parágrafo de
  observações em `LeadCard.tsx`.
- Confirmar se a mesma classe já existe em outros campos de texto livre do
  card (ex.: nome do lead) para manter consistência.
- Validar em viewport mobile estreito com um lead de teste contendo uma URL
  longa (ex.: o lead "Barbershop Orlando - Underground" na base de teste
  local, ver `docs/implementations/_conta-teste-local.md`).
