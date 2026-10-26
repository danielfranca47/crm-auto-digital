---
description: Aplica os vereditos do usuário sobre investigações de docs/discovery/ — promove para implementations ou plans, marca stand-by com gatilho, ou descarta. Passo 3 do fluxo de discovery
---

Leia `docs/discovery/_guia-discovery.md` (Passo 5) e `docs/discovery/_radar.md`.

**Pré-requisito:** vereditos explícitos do usuário nesta conversa, por investigação
(ex.: "rag → stand-by, faq-fora → implementations"). Vereditos do usuário:
$ARGUMENTS

Se não houver vereditos explícitos, mostre a secção "Prontas para decisão" do radar com
o veredito proposto de cada uma e pergunte — **não aplique nada por conta própria**. Um
veredito "stand-by" sem gatilho não é válido: proponha um gatilho mensurável e peça
confirmação.

Para cada investigação decidida:

- **Implementations** → crie `docs/implementations/<slug>.md` com
  `**Status:** Aguardando Plan Mode`, no formato reduzido do `/statusplans-avancar`
  (Motivação / Área do sistema / Próximo passo), levando da investigação a evidência,
  a solução recomendada e as fontes, e com `**Origem:** docs/discovery (investigação
  <slug>, graduada em AAAA-MM-DD)`. Remova o arquivo de discovery (`git rm`).
- **Plans** → acrescente o item ao arquivo de `docs/plans/` da área (ou crie
  `<area>-melhorias-futuras.md`), com o problema, a recomendação, o esforço estimado e
  as fontes. Remova o arquivo de discovery.
- **Stand-by** → mantenha o arquivo, status `Stand-by`, gatilho preenchido; mova a
  linha do radar para "Stand-by (gatilhos)".
- **Descartar** → remova o arquivo; acrescente uma linha em "Descartados" do radar
  (tema, motivo, data).

Atualize o `_radar.md` e faça um **commit único** (`docs:`), sem push.

**Resumo ao usuário:** tabela investigação → destino. Se algo foi para implementations,
feche perguntando se quer iniciar o Plan Mode de algum agora — não entre em Plan Mode
sem essa escolha.
