# Fix: acessibilidade mobile da página /lara-ia-v1

**Branch:** (a criar)
**Status:** Aguardando Plan Mode

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`fix-mobile-lara-hero.md`. Naquela implementação, a Fase 4 (correções de
acessibilidade: `aria-label` no botão "voltar ao topo", landmark `<main>`,
ordem de headings no footer) foi aplicada só em
`website/src/pages/CRMLandingV2.tsx` (`/lara-ia`), porque foi a página
auditada com Lighthouse mobile (score de acessibilidade 88 → 96 após a
correção). A página `/lara-ia-v1` (`website/src/pages/CRMLanding.tsx`) tem
a mesma base de código e provavelmente os mesmos 3 problemas, mas não foi
auditada nem corrigida.

## Área do sistema

`website/src/pages/CRMLanding.tsx` — mesmo padrão de footer/botão
"voltar ao topo"/estrutura de `<section>`s que `CRMLandingV2.tsx` tinha
antes da Fase 4 daquela implementação (usar o commit `452a2a2` como
referência do que foi feito lá).

Diagnóstico (Plan Mode) ainda não feito — próximo passo é rodar
`lighthouse_audit(device: "mobile")` em `/lara-ia-v1` para confirmar quais
falhas realmente existem antes de replicar a correção.
