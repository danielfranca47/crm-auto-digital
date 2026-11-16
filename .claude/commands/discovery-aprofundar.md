---
description: Investigação completa de um tema de docs/discovery/ — código, mercado (com fontes), opções de solução, RICE e veredito proposto. Passo 2 do fluxo de discovery
---

Leia `docs/discovery/_guia-discovery.md` (Passos 3 e 4) e
`docs/discovery/_metas-produto.md`, depois aprofunde a investigação
`docs/discovery/$ARGUMENTS.md`.

Se `$ARGUMENTS` estiver vazio, leia `docs/discovery/_radar.md`, sugira a investigação
`Levantado` ligada à meta mais prioritária e pergunte se é essa — não comece sem
confirmação.

1. Mude o status para `Em investigação`.
2. Preencha, pela ordem do template: **Evidência no código** (arquivo:linha + medições
   quando possível), **Como o mercado faz** (2–4 referências via WebSearch, cada uma em
   "Fontes"), **Opções de solução** (2–3, sempre incluindo "não fazer nada / adiar"),
   **Recomendação**, **Pontuação RICE** (com justificativa de cada valor),
   **Veredito proposto** (com gatilho se for stand-by), **Perguntas ao utilizador**
   (só negócio/experiência) e **Em aberto**.
3. Respeite o limite de tempo do guia (~6 pesquisas web, leitura de código focada). Se
   não couber, registe em "Em aberto" e proponha dividir.
4. Mude o status para `Pronta para decisão` e mova a linha no `_radar.md` para
   "Prontas para decisão" (meta, score, veredito proposto, perguntas pendentes).
5. Commit único (`docs:`), sem push.

**Resposta ao usuário** (não-técnica, curta): a pergunta, o que se descobriu, a
recomendação e o veredito proposto — e, se houver, as perguntas de negócio. Não despeje
o documento inteiro no chat. Feche lembrando que pode decidir agora com
`/discovery-decidir` ou acumular mais investigações e decidir em lote depois.

Não crie código de produto nem arquivos em `docs/implementations/` ou `docs/plans/`
nesta resposta — isso só acontece no `/discovery-decidir`.
