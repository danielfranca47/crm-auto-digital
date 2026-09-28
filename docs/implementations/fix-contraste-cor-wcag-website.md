# Fix: contraste de cor (WCAG AA) no website

**Branch:** `worktree-fix+contraste-cor-wcag-website`
**Status:** Em andamento — Fase 1 implementada, aguardando revisão visual (C5)

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`fix-mobile-lara-hero.md`. Um audit Lighthouse mobile em `/lara-ia` apontou
dezenas de elementos com contraste abaixo do mínimo WCAG AA (4.5:1 para
texto normal, 3:1 para texto grande), tipicamente textos com
`text-muted-foreground` combinados com `opacity-50`/`opacity-60`/`opacity-70`
(rodapés de preço, badges de categoria, links do footer, notas de garantia).
Ficou fora do escopo da implementação anterior por afetar o site inteiro.

## Área do sistema

`website/src/` — páginas `CRMLandingV2.tsx` (`/lara-ia`, `/lara-ia-v2`,
`/lara-ai`), `CRMLanding.tsx` (`/lara-ia-v1`), rodapé `components/Footer.tsx`
(páginas `/:lang`) e a classe `.btn-outline` em `index.css`.

---

## Problemas Identificados (estado anterior)

Baseline Lighthouse mobile (29/09/2026, dev server local): acessibilidade
**96** nas 4 rotas; 62 elementos reprovados em `/lara-ia` e `/lara-ai`, 53
em `/lara-ia-v1`, 22 em `/pt`.

As variáveis do design system estão corretas — `--muted-foreground` sobre o
fundo escuro dá 7.5:1. A causa raiz é **transparência aplicada por cima do
texto** nas páginas:

1. **Texto cinza com `opacity-50/60/70/75`** — cai para 2.7–4.3:1. Faixa de
   categorias, subtítulos e notas de preço, "(why)" do quiz, garantia
   (`CRMLandingV2.tsx` / `CRMLanding.tsx`).
2. **Preço riscado `opacity-50`** — 2.7:1.
3. **Cartões "em breve" com `opacity-60`** no cartão inteiro — todo o texto
   interno (preço, lista, botão "Entrar na lista →") cai para 3.2–3.7:1.
4. **Números decorativos ciano (01, 02…) a 25%/35%** — 1.75/2.34:1 (texto
   grande exige 3:1).
5. **Rodapés azuis com texto branco a 50–80%** — 2.5–4.16:1 (Lara v1, v2 e
   `Footer.tsx`).
6. **Violeta `#8B5CF6`** no badge/âncora do agente Híbrido — 3.83/4.13:1
   (`CRMLandingV2.tsx`, `badgeColor`).
7. **`.btn-outline` com texto `text-primary`** (azul 50%) sobre fundo escuro —
   3.32:1 ("Ver exemplos" em `ProjectCard.tsx`, e demais usos do botão).

---

## Abordagem

Correções pontuais, sem mexer nas variáveis de cor do design system (mudar
`--muted-foreground` clarearia todo o site sem necessidade). A hierarquia
visual do texto secundário continua garantida pelo tamanho (`text-xs`/
`text-sm`) e pela cor cinza — não pela transparência.

Regra que passa a valer no site: **não aplicar `opacity-*` (nem `/NN` de
alfa) a texto**; se o texto precisa ser secundário, usar
`text-muted-foreground`. Transparência só em elementos decorativos sem texto
(ícones, barras gráficas) ou em texto grande com contraste ≥ 3:1 confirmado.

---

## Plano de Implementação

### Fase 1 — Corrigir contraste nas páginas públicas

**Objetivo:** zerar as falhas de `color-contrast` do Lighthouse em todas as
rotas públicas do site.

| Arquivo | O que muda |
|---|---|
| `website/src/pages/CRMLandingV2.tsx` | Remove `opacity-*` de todo `text-muted-foreground` e do contentor da faixa de categorias; preço riscado vira `text-muted-foreground`; cartões "em breve" `opacity-60` → `opacity-80` (4.75:1 no botão); números decorativos ciano 0.25/0.35 → 0.55; rodapé `text-primary-foreground/50–70` → `/90` (4.83:1); `badgeColor` do Híbrido `#8B5CF6` → `#A78BFA` (5.6:1) |
| `website/src/pages/CRMLanding.tsx` | Mesmas correções (v1 da landing, sem o badge violeta) |
| `website/src/components/Footer.tsx` | Textos, links e placeholder `primary-foreground/60–80` → `/90` |
| `website/src/index.css` | `.btn-outline`: texto `text-primary` → `text-[hsl(220_80%_65%)]` (azul mais claro, 6.1:1); borda e hover inalterados |

Fora do escopo (isentos pela WCAG ou decorativos sem texto): estados
`disabled:` de `components/ui/*`, ícones (`CalendarIcon opacity-50`,
`text-white/30` em ícone) e as barras do gráfico
`bg-muted-foreground opacity-50`.

#### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `e3f6754` | Correção de contraste nas landings Lara, rodapé e `.btn-outline` |

#### Relatório da Fase 1 — o que mudou na prática

**Antes:** vários textos secundários do site (notas de preço, garantia,
categorias, textos do rodapé, números 01/02/03, planos "em breve") estavam
"apagados" com transparência, e ficavam difíceis de ler — sobretudo em
celular e sob luz forte. O Google Lighthouse dava 96/100 de acessibilidade e
reprovava até 62 elementos por página.

**Agora:** esses textos continuam com a mesma cor cinza/azul de antes, só que
sem a transparência por cima — ficam um pouco mais claros e legíveis. O
Lighthouse dá **100/100 em acessibilidade** nas 4 páginas testadas, com zero
itens de contraste reprovados. Os planos "em breve" continuam visivelmente
mais apagados que os disponíveis, só menos do que antes.

**Para validar:** Cenários C1–C4 (já validados via Lighthouse) e C5 (revisão
visual sua), abaixo.

---

## Checks de Validação

### Cenário C1 — `/lara-ia` sem falhas de contraste
- [x] Rodar Lighthouse mobile (acessibilidade) em `/lara-ia`
- [x] Confirmar: auditoria `color-contrast` sem itens; pontuação ≥ 95
- **Validado em:** 29/09/2026 — Lighthouse 12 headless, dev server local: 96 → 100, 62 → 0 itens

### Cenário C2 — `/lara-ai` (inglês)
- [x] Lighthouse mobile em `/lara-ai`: `color-contrast` sem itens
- **Validado em:** 29/09/2026 — 96 → 100, 62 → 0 itens

### Cenário C3 — `/lara-ia-v1`
- [x] Lighthouse mobile em `/lara-ia-v1`: `color-contrast` sem itens
- **Validado em:** 29/09/2026 — 96 → 100, 53 → 0 itens

### Cenário C4 — `/pt` (rodapé `Footer.tsx` e botão "Ver exemplos")
- [x] Lighthouse mobile em `/pt`: `color-contrast` sem itens
- **Validado em:** 29/09/2026 — 96 → 100, 22 → 0 itens

### Cenário C5 — Revisão visual (utilizador)
- [ ] Abrir `/lara-ia` no celular ou desktop
- [ ] Confirmar: texto principal vs. secundário ainda se distinguem (ex.: notas pequenas abaixo dos preços continuam "discretas")
- [ ] Confirmar: planos "em breve" ainda parecem inativos em relação aos disponíveis
- [ ] Confirmar: números 01/02/03 das etapas e bónus continuam decorativos (não competem com os títulos)
- [ ] Confirmar: rodapé azul e o botão contornado "Ver exemplos" (`/pt`) estão com aparência aceitável

---

## Ajustes Possíveis Pós-Implementação

- Páginas não roteadas hoje (`ProfessionalWebsites.tsx`, `SchedulingDemo.tsx`,
  `ComingSoon.tsx`, `AIWhatsAppAutomation.tsx`) não foram auditadas pelo
  Lighthouse por não terem rota; herdam a correção do `.btn-outline`, mas
  podem ter outros casos se voltarem a ser publicadas.
- Não existe um check automático de contraste no build/CI do website — uma
  regressão (alguém voltar a pôr `opacity-60` em texto) só seria detetada num
  novo audit manual.
