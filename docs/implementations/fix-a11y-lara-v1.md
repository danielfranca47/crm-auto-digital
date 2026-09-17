# Fix: acessibilidade mobile da página /lara-ia-v1

**Branch:** `worktree-fix+a11y-lara-v1` (nome sanitizado pelo `EnterWorktree`
desta sessão — ver `[[project-enterworktree-branch-naming]]` na memória;
pedido original foi `fix/a11y-lara-v1`)
**Status:** Todos os cenários validados (17/09/2026)

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`fix-mobile-lara-hero.md`. Naquela implementação, a Fase 4 (correções de
acessibilidade: `aria-label` no botão "voltar ao topo", landmark `<main>`,
ordem de headings no footer) foi aplicada só em
`website/src/pages/CRMLandingV2.tsx` (`/lara-ia`), porque foi a página
auditada com Lighthouse mobile (score de acessibilidade 88 → 96 após a
correção). O utilizador pediu para replicar na `/lara-ia-v1`.

---

## Problemas Identificados (estado anterior)

Confirmado por leitura direta de `website/src/pages/CRMLanding.tsx`
(estado atual em `main`) — estrutura idêntica, byte a byte, ao que a V2
tinha antes do commit `452a2a2`:

1. **Botão sem nome acessível:** `CRMLanding.tsx:985-988` — botão "voltar
   ao topo" só com ícone `<ArrowUp>`, sem `aria-label`.
2. **Sem landmark `<main>`:** `CRMLanding.tsx:232` (fim do `<header>`) até
   `:944` (`<footer>`) — nenhuma `<section>` está dentro de `<main>`.
3. **Ordem de headings quebrada:** `CRMLanding.tsx:963,972` —
   `<h4>Produto</h4>` e `<h4>Contato</h4>` no footer pulam do H2 direto
   para H4.

---

## Abordagem

Replicar exatamente o padrão já validado no commit `452a2a2` (V2): mesmos
3 ajustes de markup, mesmos pontos estruturais, sem mudança visual.

---

## Plano de Implementação

### Fase 1 — Acessibilidade mobile da v1

**Objetivo:** resolver `button-name`, `landmark-one-main` e
`heading-order` do Lighthouse mobile em `/lara-ia-v1`.

| Arquivo | O que muda |
|---|---|
| `website/src/pages/CRMLanding.tsx:985-988` | Botão "voltar ao topo" ganha `aria-label="Voltar ao topo"` |
| `website/src/pages/CRMLanding.tsx:232,944` | `<section>`s entre header e footer envolvidas por `<main>` |
| `website/src/pages/CRMLanding.tsx:963,972` | `<h4>` → `<h3>` (Produto/Contato) |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `2806328` | aria-label, `<main>`, h4→h3 em CRMLanding.tsx |

### Relatório da Fase 1 — o que mudou na prática

**Antes:** a página `/lara-ia-v1` tinha os mesmos 3 problemas de
acessibilidade que a `/lara-ia` tinha antes da correção anterior: um botão
só com ícone que leitores de tela não identificavam, a página sem marcação
de "conteúdo principal", e os títulos do rodapé pulando um nível.
**Agora:** os 3 problemas foram corrigidos, replicando exatamente o que já
foi validado na `/lara-ia`. Score de acessibilidade do Lighthouse mobile
subiu de 88 para 96 — igual ao resultado anterior.
**Para validar:** Cenários P1 e P2, abaixo.

---

## Checks de Validação

### Cenário P1 — Lighthouse mobile accessibility (V1)
- [x] Rodar `lighthouse_audit(device: "mobile")` em `/lara-ia-v1` antes e depois
- [x] Confirmar: `button-name`, `landmark-one-main`, `heading-order` não aparecem mais como falhas; score sobe
- **Validado em:** 17/09/2026 — accessibility score 88 → 96; as 3 falhas
  não aparecem mais (restam apenas itens fora de escopo: contraste de cor,
  cookies de terceiros do YouTube, llms.txt — os mesmos já conhecidos da V2).

### Cenário P2 — Sem mudança visual
- [x] Screenshot mobile (390x844) antes/depois — confirmar visual idêntico
- **Validado em:** 17/09/2026 — screenshot confirma layout idêntico ao
  estado atual da página, sem regressão.

---

## Ajustes Possíveis Pós-Implementação

Nenhum identificado — escopo fechado e idêntico ao já validado na V2.
