# Fix: overflow horizontal com URL longa no campo Obs do LeadCard

**Branch:** `fix/leadcard-obs-url-overflow`
**Status:** Em andamento

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

---

## Problemas Identificados (estado anterior)

1. **Sem quebra de palavra no campo Obs:** `LeadCard.tsx:233` — o parágrafo
   de observações usa `line-clamp-2` (limita a 2 linhas, com
   `overflow: hidden`), mas nenhuma classe de quebra de palavra. Uma URL
   longa como um único "token" sem espaço força a largura mínima de
   conteúdo a propagar para os elementos ancestrais sem `min-width: 0`,
   causando overflow horizontal no nível da página.

---

## Abordagem

Adicionar `break-words` (Tailwind → `overflow-wrap: break-word`) à classe do
parágrafo de observações. Isso permite que uma palavra/URL longa quebre para
a linha seguinte em vez de vazar pela largura do card — funciona junto com o
`line-clamp-2` existente (que continua limitando a 2 linhas visíveis).

---

## Plano de Implementação

### Fase 1 — Quebra de palavra no campo Obs

**Objetivo:** URL longa sem espaço quebra de linha em vez de vazar pela
largura do card.

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/components/LeadCard.tsx` | Linha 233: adicionar `break-words` à classe do parágrafo de observações |

```tsx
// ANTES
<p className="text-xs mt-1 line-clamp-2">{lead.observations}</p>

// DEPOIS
<p className="text-xs mt-1 line-clamp-2 break-words">{lead.observations}</p>
```

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `69813f8` | break-words no campo Obs do LeadCard |

**Detalhes do commit `69813f8`:**
- `frontend-crm/src/components/LeadCard.tsx` — `break-words` adicionado ao parágrafo de observações
- `docs/architecture/kanban-responsive.md` — nova seção "Campo de observações"; removida a "Limitação conhecida" (resolvida por este fix)

### Relatório da Fase 1 — o que mudou na prática

**Antes:** quando um lead tinha uma URL bem longa (sem espaços) anotada no
campo "Obs" do card, o texto vazava para fora do card e podia deixar a
página inteira com uma rolagem horizontal indesejada, especialmente em
celular.

**Agora:** URLs e palavras longas nesse campo quebram para a linha seguinte
normalmente, como o resto do texto — sem vazar do card e sem causar rolagem
horizontal na página. O card continua mostrando no máximo 2 linhas de
observação, igual antes.

**Para validar:** Cenário P1, abaixo.

---

## Checks de Validação

### Cenário P1 — URL longa não causa overflow horizontal
- [ ] Emular viewport mobile em retrato (ex.: 390x844)
- [ ] Abrir o Kanban com o lead "Barbershop Orlando - Underground" (tem URL longa no campo Obs)
- [ ] Confirmar visualmente: o texto da URL quebra para a linha seguinte, não vaza para fora do card
- [ ] Confirmar via script: `document.documentElement.scrollWidth === document.documentElement.clientWidth`
- [ ] Confirmar: o card continua mostrando no máximo 2 linhas de observação (line-clamp-2 preservado)

---

## Ajustes Possíveis Pós-Implementação

<a preencher após os testes, se necessário>
