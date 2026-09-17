# Otimizar imagem de fundo do hero (Lara) para desktop

**Branch:** (a criar)
**Status:** Aguardando Plan Mode

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`fix-mobile-lara-hero.md`. Naquela implementação, `hero-mascot.jpeg`
(389KB, sem variante otimizada) passou a não carregar mais no mobile
(`@media (min-width: 768px)` em `website/src/index.css`, classe
`.hero-mascot-bg`), mas no desktop continua sendo servido no tamanho/
formato original — sem `.webp`, sem redimensionamento, sem `srcset`.

## Área do sistema

`website/public/hero-mascot.jpeg` (e `hero-mascot.png`, 1.67MB, aparenta
ser não utilizado — confirmar antes de mexer), referenciado via classe CSS
`.hero-mascot-bg` em `website/src/index.css` e usado em
`website/src/pages/CRMLandingV2.tsx` (`/lara-ia`) e
`website/src/pages/CRMLanding.tsx` (`/lara-ia-v1`).

Diagnóstico (Plan Mode) ainda não feito — próximo passo é seguir o Passo 0
de `_guia-documentar-implementacao.md` antes de qualquer código.
