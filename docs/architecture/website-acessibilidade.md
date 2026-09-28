# Website — Acessibilidade e contraste de cor

Regras de contraste (WCAG AA) das páginas públicas do `website/`. Alvo: zero
itens na auditoria `color-contrast` do Lighthouse e acessibilidade 100 em
`/lara-ia`, `/lara-ai`, `/lara-ia-v1` e `/pt` (mobile).

---

## Mínimos WCAG AA

| Tipo de texto | Contraste mínimo |
|---|---|
| Normal (< 24px, ou < 18.66px em negrito) | 4.5:1 |
| Grande (≥ 24px, ou ≥ 18.66px em negrito) | 3:1 |
| Estados `disabled:`, ícones e elementos puramente decorativos sem texto | isentos |

---

## Paleta (`website/src/index.css`) e contrastes de referência

O site é escuro: fundo `--background` (`hsl(220 15% 5%)`), cartões
`--card`/`.portfolio-card` (~`hsl(220 15% 8–12%)`).

| Cor de texto | Sobre fundo / cartão | Uso |
|---|---|---|
| `text-foreground` (branco) | 19.6 / 18.5 | texto principal |
| `text-muted-foreground` (`hsl(220 15% 65%)`) | 7.5 / 7.2 | texto secundário |
| `text-primary` (`hsl(220 80% 50%)`) | **3.5 / 3.3 — reprova** | não usar como cor de texto sobre fundo escuro |
| azul claro `hsl(220 80% 65%)` | 6.1 / 5.3 | texto do `.btn-outline` |
| ciano `#4DD4FF` | ~10.8 | destaques inline nas landings Lara |
| violeta `#A78BFA` (badge do agente Híbrido) | ~5.6 | `badgeColor` em `CRMLandingV2.tsx` |

Rodapés com fundo `bg-primary` (azul): texto branco precisa de alfa ≥ 90%
(`text-primary-foreground/90` = 4.83:1). `/80` já reprova (4.15:1).

---

## Regras

1. **Não aplicar `opacity-*` nem alfa (`/NN`) a texto.** Para texto
   secundário usar `text-muted-foreground`; a hierarquia vem do tamanho
   (`text-xs`/`text-sm`) e da cor, não da transparência. Sobre o cinza,
   `opacity-70` já cai para ~4.2:1 e `opacity-60` para ~3.4:1.
2. **Exceção — texto grande decorativo** (ex.: números 01/02/03 das etapas e
   bónus nas landings Lara, `text-3xl`/`text-5xl`): transparência permitida
   desde que o resultado fique ≥ 3:1. O ciano `#4DD4FF` usa opacidade mínima
   0.55.
3. **Cartões "em breve"** (planos indisponíveis) usam `opacity-80` no cartão
   inteiro — é o mínimo que mantém o botão interno ("Entrar na lista →")
   acima de 4.5:1 (4.75:1).
4. Transparência livre apenas em elementos sem texto: ícones, barras de
   gráfico (`bg-muted-foreground opacity-50`), bordas e fundos.

---

## Como verificar

Com o dev server do website rodando (porta 5175):

```bash
npx lighthouse@12 http://localhost:5175/lara-ia --only-categories=accessibility \
  --form-factor=mobile --output=json --output-path=./a11y.json --chrome-flags="--headless=new"
```

Em modo dev, cada nó reprovado traz `data-lov-id="<arquivo>:<linha>:<coluna>"`
no `snippet` do relatório, o que aponta direto para a linha do JSX.
