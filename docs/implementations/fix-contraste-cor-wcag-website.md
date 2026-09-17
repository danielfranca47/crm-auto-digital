# Fix: contraste de cor (WCAG AA) no website

**Branch:** (a criar)
**Status:** Aguardando Plan Mode

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`fix-mobile-lara-hero.md`. Um audit Lighthouse mobile em `/lara-ia` (score
de acessibilidade 88 antes da correção daquela implementação) apontou
dezenas de elementos com contraste abaixo do mínimo WCAG AA (4.5:1),
tipicamente textos com `text-muted-foreground` combinados com
`opacity-50`/`opacity-60`/`opacity-70` (ex.: rodapés de preço, badges de
categoria, links do footer, notas de garantia). Ficou fora do escopo da
implementação anterior por afetar o site inteiro, não só as páginas Lara.

## Área do sistema

`website/src/` — padrão de design system em `website/src/index.css`
(variáveis `--muted-foreground` etc.) e uso disseminado da combinação
`text-muted-foreground opacity-NN` em várias páginas/componentes
(`CRMLandingV2.tsx`, `CRMLanding.tsx`, e possivelmente outras páginas do
site — precisa de levantamento completo).

Diagnóstico (Plan Mode) ainda não feito — próximo passo é rodar
`lighthouse_audit` nas páginas do site para mapear todas as ocorrências
antes de decidir a abordagem (ex.: ajustar as variáveis de opacidade do
design system vs. correções pontuais).
