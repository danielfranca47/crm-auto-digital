# Website (acessibilidade) — Melhorias Futuras

> Contexto: item deixado de fora da graduação do fix
> `fix-contraste-cor-wcag-website.md` (29/09/2026). Regras atuais em
> [`docs/architecture/website-acessibilidade.md`](../architecture/website-acessibilidade.md).

## M1 — Verificação automática de contraste no website

**Prioridade: BAIXA**

Hoje não há nenhum check automático de contraste no build/CI do `website/`.
Uma regressão (ex.: alguém voltar a pôr `opacity-60` ou `text-primary` num
texto sobre fundo escuro) só é detetada num audit Lighthouse manual.

Opções a avaliar quando for priorizado: regra de lint simples que proíba
`opacity-*`/alfa na mesma `className` que uma cor de texto; ou um script
(`npx lighthouse` / `@axe-core/cli`) sobre as rotas públicas que falhe se
`color-contrast` tiver itens.
