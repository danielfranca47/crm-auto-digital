# [TEMPLATE] Título da investigação (uma pergunta)

> Estrutura de cada arquivo `docs/discovery/<slug>.md`. Processo completo em
> `_guia-discovery.md`. Em status `Levantado` só as secções marcadas com (L)
> são preenchidas; as restantes ficam para o `/discovery-aprofundar`.

---

**Status:** Levantado | Em investigação | Pronta para decisão | Stand-by
**Origem:** `levantamentos/AAAA-MM-DD-<tema>.<ext>` — <trecho/tema de origem> (L)
**Meta ligada:** M<N> — <nome da meta em `_metas-produto.md`> (L)
**Área do sistema:** <serviços envolvidos, ex.: backend-executors / frontend-crm> (L)

---

## Pergunta a responder (L)

<Uma pergunta, em linguagem simples. Ex.: "Os leads fazem perguntas na fase de
qualificação que a IA não consegue responder por falta de FAQ?">

## O que já se sabe (L)

<Factos já verificados no levantamento, com arquivo:linha. Distinguir o que é
confirmado do que é hipótese.>

---

## Evidência no código

<Como funciona hoje, com arquivo:linha. Medições quando possível (banco local,
logs de produção).>

## Como o mercado faz

| Referência | Como resolve | Aplica-se a nós? |
|---|---|---|
| <plataforma/artigo> | <resumo> | <sim/parcial/não — porquê> |

## Opções de solução

### Opção A — Não fazer nada / adiar
- **Prós:** …
- **Contras:** …

### Opção B — <nome>
- **O que é:** …
- **Prós:** …
- **Contras:** …
- **Esforço:** ~N fases

### Opção C — <nome> (se houver)
…

## Recomendação

<Uma opção + porquê em 2–3 frases, sem jargão.>

## Pontuação RICE

| R | I | C | E | Score |
|---|---|---|---|---|
| 1–3 | 0.5–3 | 0.5–1 | fases | R×I×C÷E |

<Uma linha a justificar cada valor.>

## Veredito proposto

**<Implementations | Plans | Stand-by | Descartar>** — <porquê numa frase>
**Gatilho de revisão (só stand-by):** <condição mensurável>

## Perguntas ao utilizador

<Só decisões de negócio/experiência. "Nenhuma" é válido.>

## Em aberto

<O que ficou por investigar por limite de tempo. "Nada" é válido.>

## Fontes

- [Título](url)
