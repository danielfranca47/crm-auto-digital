# Fix: responsividade mobile das páginas Lara (/lara-ia e /lara-ia-v1)

**Branch:** `worktree-fix+mobile-lara-hero` (nota: a ferramenta `EnterWorktree`
desta sessão saneou o nome pedido `fix/mobile-lara-hero` para este formato —
ver `docs/ops/local-dev.md` se precisar investigar; a branch parte de `main`
normalmente, só o nome difere da convenção `fix/<slug>`)
**Status:** Todos os cenários validados (17/09/2026)

---

## Motivação

O utilizador reportou que na página https://danielfranca.pt/lara-ia (rota
principal da Lara, `website/src/pages/CRMLandingV2.tsx`) o texto da frase
inicial (H1) parece grande demais no mobile. Teste ao vivo via Chrome
DevTools MCP (viewport 390x844) confirmou: `.text-hero`
(`website/src/index.css:60,168-172`) é `font-size: 3.5rem` (56px) **fixo,
sem nenhum breakpoint responsivo**. No mobile isso ocupa 554px de altura só
com o H1, empurrando o CTA principal para 1087px do topo — mais de 1 tela
inteira de rolagem (viewport tem 844px) antes do primeiro botão de
conversão aparecer. `.text-heading` (2.25rem, `index.css:61,174-178`) tem o
mesmo problema estrutural.

Durante a investigação encontrei mais 3 pontos de otimização mobile reais
na mesma página, que o utilizador pediu para incluir:
- Tabela comparativa corta a 3ª coluna no mobile (sem scroll horizontal).
- Imagem de fundo do hero (389KB) é baixada inteira no mobile mesmo quase
  toda coberta pelo gradiente escuro.
- 3 falhas de acessibilidade mobile do Lighthouse (accessibility score 88).

Um agente Explore confirmou que a página v1 (`CRMLanding.tsx`,
`/lara-ia-v1`) tem os mesmos 3 primeiros bugs (mesma base de código) — o
utilizador pediu para corrigir os dois arquivos juntos nesses pontos. A
Fase 4 (acessibilidade) fica restrita à V2, que foi a auditada.

---

## Problemas Identificados (estado anterior)

1. **H1/H2 sem tipografia responsiva:** `.text-hero` e `.text-heading` em
   `website/src/index.css` usam `font-size` fixo sem media query, usados em
   `CRMLandingV2.tsx:320` (H1) e 15 outros locais (H2), e
   `CRMLanding.tsx:263` (H1) e 14 outros locais (H2).
2. **Tabela comparativa clipada no mobile:** `CRMLandingV2.tsx:683-711` e
   `CRMLanding.tsx:546-573` — `<table>` dentro de `.portfolio-card
   overflow-hidden p-0` sem wrapper de scroll horizontal; 3ª coluna ("Bot
   genérico") fica cortada/invisível em viewports estreitos.
3. **Imagem de fundo pesada carregada sempre:** `hero-mascot.jpeg` (389KB)
   referenciada via `style={{ backgroundImage: ... }}` inline em
   `CRMLandingV2.tsx:296` e `CRMLanding.tsx:239`, sem variante mobile —
   baixada mesmo quando majoritariamente coberta pelo gradiente escuro.
4. **Falhas de acessibilidade (Lighthouse mobile, só V2):** botão "voltar
   ao topo" sem `aria-label` (`CRMLandingV2.tsx:1256-1259`); página sem
   landmark `<main>`; `<h4>Produto</h4>`/`<h4>Contato</h4>` no footer
   pulam do H2 sem H3 intermediário (`CRMLandingV2.tsx:1234,1243`).

---

## Abordagem

Trocar `.text-hero`/`.text-heading` por classes Tailwind responsivas
nativas **só dentro dos dois arquivos de página** (não nas classes CSS
compartilhadas, que têm ~38 outras ocorrências fora do escopo pedido),
reaproveitando o padrão já usado em outras páginas do site
(`text-4xl md:text-5xl lg:text-6xl` em `ProfessionalWebsites.tsx`,
`text-3xl md:text-4xl` em vários H2s). Tabela ganha wrapper
`overflow-x-auto` (padrão já usado em `frontend-crm/Pesquisa.tsx:224`).
Imagem de fundo migra de `style` inline para uma classe CSS
(`.hero-mascot-bg`) com a imagem condicionada a `@media (min-width: 768px)`.

---

## Plano de Implementação

### Fase 1 — Tipografia responsiva do H1 e headings (V2 + V1)

**Objetivo:** H1/H2 escalam por breakpoint em vez de tamanho fixo,
liberando o CTA principal para aparecer bem mais cedo no scroll mobile.

| Arquivo | O que muda |
|---|---|
| `website/src/pages/CRMLandingV2.tsx:320` | H1: `text-hero` → `text-4xl md:text-5xl lg:text-6xl font-extrabold` |
| `website/src/pages/CRMLandingV2.tsx` (15 ocorrências de `text-heading`) | → `text-3xl md:text-4xl font-bold` |
| `website/src/pages/CRMLanding.tsx:263` | H1: `text-hero` → `text-4xl md:text-5xl lg:text-6xl font-extrabold` |
| `website/src/pages/CRMLanding.tsx` (14 ocorrências de `text-heading`) | → `text-3xl md:text-4xl font-bold` |

```tsx
// ANTES
<h1 className="text-hero mb-6 animate-fade-in animate-delay-100">

// DEPOIS
<h1 className="text-4xl md:text-5xl lg:text-6xl font-extrabold mb-6 animate-fade-in animate-delay-100">
```

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `732253b` | H1/H2 responsivos em CRMLandingV2.tsx e CRMLanding.tsx |

**Detalhes do commit `732253b`:**
- `website/src/pages/CRMLandingV2.tsx` — H1: `text-hero` → `text-4xl md:text-5xl lg:text-6xl font-extrabold`; 15 H2s: `text-heading` → `text-3xl md:text-4xl font-bold`
- `website/src/pages/CRMLanding.tsx` — mesma mudança (H1 + 14 H2s)

### Relatório da Fase 1 — o que mudou na prática

**Antes:** o título da primeira tela ("Recupere sua primeira venda...") usava
um tamanho de letra fixo (56px) em qualquer tela. No celular isso fazia o
título sozinho ocupar quase 2 telas de altura, empurrando o botão "Ativar
minha Lara agora" para bem depois da primeira rolagem.
**Agora:** o título (e os subtítulos das seções) reduzem de tamanho
automaticamente em telas estreitas. No celular o botão principal já aparece
na primeira tela, sem precisar rolar.
**Para validar:** Cenários P1 e P2, abaixo.

### Fase 2 — Tabela comparativa com scroll horizontal (V2 + V1)

**Objetivo:** 3ª coluna deixa de ficar cortada no mobile.

| Arquivo | O que muda |
|---|---|
| `website/src/pages/CRMLandingV2.tsx:683-711` | `<table>` envolvida por `<div className="overflow-x-auto">` |
| `website/src/pages/CRMLanding.tsx:546-573` | Mesma mudança |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `4bd7a33` | Wrapper `overflow-x-auto` na tabela comparativa das duas páginas |

**Detalhes do commit `4bd7a33`:**
- `website/src/pages/CRMLandingV2.tsx` — `<table>` envolvida por `<div className="overflow-x-auto">`
- `website/src/pages/CRMLanding.tsx` — mesma mudança

### Relatório da Fase 2 — o que mudou na prática

**Antes:** na tabela "Por que somos diferentes", a coluna "Bot genérico" (a
3ª coluna) ficava cortada fora da tela no celular, sem nenhuma forma de vê-la.
**Agora:** a tabela ganhou rolagem lateral própria — arrastando o dedo para
o lado dentro da tabela, a coluna "Bot genérico" aparece inteira.
**Para validar:** Cenário P3, abaixo.

### Fase 3 — Ocultar imagem de fundo do hero no mobile (V2 + V1)

**Objetivo:** eliminar 389KB de download em telas onde o gradiente já
cobre a imagem.

| Arquivo | O que muda |
|---|---|
| `website/src/index.css` | Nova classe `.hero-mascot-bg`: sem imagem por padrão; `@media (min-width: 768px)` aplica `background-image`/`size`/`position`/`repeat` |
| `website/src/pages/CRMLandingV2.tsx:292-301` | `<section id="home">` usa `hero-mascot-bg` no `className`, remove `style` de background |
| `website/src/pages/CRMLanding.tsx:235-244` | Mesma mudança |

### Commits Fase 3

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `dbb5afd` | Classe `.hero-mascot-bg` condicionada a `md+`; aplicada nas duas páginas |

**Detalhes do commit `dbb5afd`:**
- `website/src/index.css` — nova classe `.hero-mascot-bg` (sem imagem por padrão; imagem só via `@media (min-width: 768px)`)
- `website/src/pages/CRMLandingV2.tsx` — `section#home` usa `hero-mascot-bg`, `style` inline removido
- `website/src/pages/CRMLanding.tsx` — mesma mudança

### Relatório da Fase 3 — o que mudou na prática

**Antes:** o celular baixava a foto de fundo do hero (389KB) mesmo ela
ficando quase toda escondida atrás do degradê escuro — desperdício de dados
e tempo de carregamento no mobile.
**Agora:** no celular a foto não é mais baixada (só o fundo escuro/degradê,
que já cobria a maior parte dela mesmo). No computador a foto continua
aparecendo normalmente.
**Para validar:** Cenário P4, abaixo.

### Fase 4 — Acessibilidade mobile (Lighthouse) — só V2

**Objetivo:** resolver `button-name`, `landmark-one-main` e
`heading-order` do Lighthouse mobile.

| Arquivo | O que muda |
|---|---|
| `website/src/pages/CRMLandingV2.tsx:1256-1259` | Botão "voltar ao topo" ganha `aria-label="Voltar ao topo"` |
| `website/src/pages/CRMLandingV2.tsx:292,1214` | `<section>`s entre header e footer envolvidas por `<main>` |
| `website/src/pages/CRMLandingV2.tsx:1234,1243` | `<h4>` → `<h3>` (Produto/Contato) |

### Commits Fase 4

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `452a2a2` | aria-label no botão "voltar ao topo", landmark `<main>`, h4→h3 no footer |

**Detalhes do commit `452a2a2`:**
- `website/src/pages/CRMLandingV2.tsx` — `aria-label="Voltar ao topo"` no botão de ícone; `<section>`s entre header e footer envolvidas por `<main>`; `<h4>Produto</h4>`/`<h4>Contato</h4>` → `<h3>`

### Relatório da Fase 4 — o que mudou na prática

**Antes:** o Lighthouse (auditoria automática do Google para acessibilidade)
apontava 3 problemas na página: um botão só com ícone que leitores de tela
não conseguiam identificar, a página sem uma marcação de "conteúdo
principal", e os títulos do rodapé pulando um nível (H2 direto para H4).
**Agora:** os 3 problemas foram corrigidos. O score de acessibilidade do
Lighthouse mobile subiu de 88 para 96.
**Para validar:** Cenário P5, abaixo.

---

## Checks de Validação

### Cenário P1 — H1 responsivo no mobile (V2)
- [x] Emular viewport 390x844 em `/lara-ia`
- [x] Medir altura do H1 e posição Y do CTA principal
- [x] Confirmar: CTA aparece bem antes de 1087px (idealmente < 1 tela)
- **Validado em:** 17/09/2026 — H1 caiu de 554px para 240px de altura
  (font-size 56px → 36px); CTA principal passou de 1087px para 772px do
  topo, dentro da primeira tela (844px) — antes exigia mais de 1 tela de
  rolagem, agora nenhuma.

### Cenário P2 — H1 responsivo no mobile (V1)
- [x] Mesmo teste em `/lara-ia-v1`
- **Validado em:** 17/09/2026 — H1 com 280px de altura (36px font-size),
  CTA principal a 780px do topo, dentro da primeira tela.

### Cenário P3 — Tabela comparativa com scroll (V2 e V1)
- [x] Emular mobile, rolar até a seção de comparação
- [x] Confirmar: 3 colunas acessíveis via scroll horizontal, sem clipping
- **Validado em:** 17/09/2026 — wrapper com `overflow-x-auto` confirmado
  (`scrollWidth > clientWidth` em ambas as páginas); rolando a tabela para a
  direita a coluna "Bot genérico" (com os ✗ em vermelho) aparece inteira.

### Cenário P4 — Imagem de fundo não carrega no mobile (V2 e V1)
- [x] `list_network_requests` (resourceTypes: image) em viewport mobile — `hero-mascot.jpeg` não deve aparecer
- [x] Repetir em viewport desktop — imagem deve carregar normalmente
- **Validado em:** 17/09/2026 — `hero-mascot.jpeg` ausente da lista de
  requisições em 390x844 (V2 e V1); presente normalmente (200/304) em
  1440x900.

### Cenário P5 — Lighthouse mobile accessibility (V2)
- [x] Rodar `lighthouse_audit(device: "mobile")` novamente
- [x] Confirmar: `button-name`, `landmark-one-main`, `heading-order` não aparecem mais como falhas
- **Validado em:** 17/09/2026 — accessibility score 88 → 96; as 3 falhas
  não aparecem mais no relatório (falhas restantes são pré-existentes e
  fora de escopo: contraste de cor, cookies de terceiros do YouTube, llms.txt).

---

## Ajustes Possíveis Pós-Implementação

- Gerar variante `.webp`/redimensionada de `hero-mascot.jpeg` para telas
  `md+` também se ganhar performance (fora de escopo — só ocultação no
  mobile foi decidida nesta implementação).
- Corrigir os problemas de contraste de cor (WCAG AA) encontrados pelo
  Lighthouse em textos com `opacity-50/60/70` — afeta o site inteiro, não
  só estas duas páginas; ficou fora de escopo por ser mudança ampla.
- Aplicar a Fase 4 (acessibilidade) também na v1, se o Lighthouse mobile
  for rodado nela.
