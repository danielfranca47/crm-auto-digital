# Guia: Discovery — de um levantamento a uma decisão

Este arquivo é um guia de instrução para o Claude. Ler antes de criar ou
aprofundar qualquer arquivo em `docs/discovery/`, e sempre que um comando
`/discovery-*` for executado.

---

## Para que serve

`docs/discovery/` é a frente de **descoberta** do produto; `docs/plans/` e
`docs/implementations/` são a frente de **entrega**. Aqui entra o que ainda tem
**incerteza**: não sabemos se o problema é real, quão grande é, ou qual é a
melhor solução. O resultado de cada investigação é uma **decisão fundamentada**,
não código.

| Pasta | Pergunta que responde | Resultado |
|---|---|---|
| `discovery/` | Vale a pena? Qual a melhor solução? | Veredito com evidência |
| `plans/` | O que está na fila para construir? | Sprint |
| `implementations/` | Como estamos a construir isto agora? | Código validado |

Base de mercado: *Product Discovery / Dual-Track Agile* (descobrir e entregar em
paralelo), *spike* (investigação com tempo limitado que termina num documento
com recomendação), *Opportunity Solution Tree* (meta → oportunidade → solução) e
*Technology Radar* (vereditos adotar / avaliar / suspender).

---

## Estrutura da pasta

| Arquivo | Papel |
|---|---|
| `_guia-discovery.md` | Este guia |
| `_template-investigacao.md` | Estrutura de cada investigação |
| `_metas-produto.md` | Metas do produto — âncora de toda a priorização |
| `_radar.md` | Painel: todas as investigações abertas + stand-by + descartados |
| `levantamentos/` | Material bruto de origem (conversas, relatórios, feedbacks) |
| `<slug>.md` | Uma investigação por gap |

---

## Passo 1 — Levantamento → gaps (`/discovery-levantar`)

1. Guardar o material bruto em `levantamentos/AAAA-MM-DD-<tema>.<ext>` (se veio
   de fora do repo ou está solto noutra pasta, mover para aqui com `git mv`).
2. Ler o levantamento **e verificar cada afirmação no código**. Um levantamento
   externo (ex.: outra IA, um consultor) não conhece o sistema: separar o que se
   aplica, o que já existe e o que não se aplica. Citar arquivo:linha.
3. Listar os gaps encontrados. Um gap = uma pergunta que pode ter uma decisão
   própria. Não juntar temas diferentes num gap só para "poupar arquivos".

## Passo 2 — Triagem de cada gap

| Situação | Destino |
|---|---|
| Bug confirmado no código **e** solução óbvia | `docs/implementations/<slug>.md` como `Aguardando Plan Mode` (formato do `/statusplans-avancar`) — **não** passa pela discovery |
| Já existe / não se aplica ao sistema | Não cria arquivo — registar só no resumo ao utilizador (e em "Descartados" do radar se for provável alguém voltar a propor) |
| Incerteza sobre problema, tamanho ou solução | `docs/discovery/<slug>.md` com status `Levantado` |

**Regra anti-burocracia:** a discovery é para incerteza. Se o problema e a
solução são claros, mandar direto para implementations. Na dúvida sobre se é
"claro", perguntar ao utilizador numa frase.

Na criação (`Levantado`), preencher só: Origem, Pergunta a responder, Meta
ligada (provável) e "O que já se sabe". O resto fica para o Passo 3 — assim um
levantamento com 8 gaps não gasta tokens a investigar todos de uma vez.

## Passo 3 — Aprofundar (`/discovery-aprofundar <slug>`)

Uma investigação por vez. Status passa para `Em investigação` no início e para
`Pronta para decisão` no fim.

1. **Evidência no código e nos dados reais** — como funciona hoje, com
   arquivo:linha. Quando possível, medir: tamanho de dados, frequências, e
   **conversas reais de produção** para medir a efetividade do agente (ex.:
   quantas vezes disse "vou confirmar com a equipa"). Um número vale mais que uma
   opinião.
   - **Produção:** o utilizador autorizou (23/09/2026) leituras de produção para
     investigações, incluindo conteúdo. Sempre **só leitura** (SQLite com
     `?mode=ro`) via `railway ssh -s backend-crm`; logs de decisão da IA no serviço
     `worker backend-executors` (ver memória `reference-railway-production-access`).
     O modo automático pode pedir confirmação a cada acesso — é esperado.
   - **Privacidade:** nos arquivos de discovery só entram números agregados e
     trechos anonimizados — nunca nomes, telefones ou conversas identificáveis.
2. **Como o mercado faz** — 2 a 4 referências (plataformas concorrentes ou de
   referência, documentação técnica, artigos de engenharia), via WebSearch. Cada
   afirmação com link em "Fontes". Adaptar ao nosso contexto: o que funciona para
   uma empresa com 10 mil clientes pode ser exagero para nós.
3. **Opções de solução** — 2 a 3, incluindo sempre "não fazer nada / adiar" como
   base de comparação. Para cada uma: o que é, prós, contras, esforço
   aproximado (em número de fases de implementação).
4. **Recomendação** — uma opção, com o porquê em 2–3 frases.
5. **RICE** (ver abaixo) e **veredito proposto**.
6. **Perguntas ao utilizador** — só decisões de negócio/experiência que o código
   não responde (mesmos critérios de "Perguntas ao admin" em
   `docs/plans/_guia-analise-planos.md`). Nunca perguntas técnicas.

**Limite de tempo (spike):** no máximo ~6 pesquisas web e leitura de código
focada nos arquivos do gap. Se a investigação precisar de mais, parar,
registar o que falta em "Em aberto" e propor dividir em duas investigações —
nunca deixar uma investigação crescer sem fim.

## Passo 4 — Pontuação RICE

Escala simples, pensada para poucos clientes:

| Fator | Pergunta | Valores |
|---|---|---|
| **R**each (alcance) | Quantos clientes/leads isto afeta? | 1 = poucos casos · 2 = parte dos clientes · 3 = todos |
| **I**mpact (impacto) | Quanto move a meta ligada? | 0.5 = mínimo · 1 = baixo · 2 = médio · 3 = alto |
| **C**onfidence (confiança) | Quão forte é a evidência? | 0.5 = hipótese · 0.8 = indícios · 1 = medido/confirmado |
| **E**ffort (esforço) | Quantas fases de implementação? | 1, 2, 3… |

**Score = R × I × C ÷ E.** Serve para comparar investigações entre si no radar,
não como verdade absoluta. Uma investigação sem meta ligada em
`_metas-produto.md` tem Impact máximo de 1 — se não serve nenhuma meta, é
provavelmente um "seria bom ter".

## Passo 5 — Veredito (`/discovery-decidir`)

O Claude **propõe**; o utilizador **decide**, em lote, pelo `/discovery-status`.

| Veredito | Quando | O que acontece |
|---|---|---|
| **Implementations** | Score alto e ligado a meta ativa, sem bloqueios | Stub `docs/implementations/<slug>.md` `Aguardando Plan Mode`, com a Motivação e a solução recomendada; o arquivo de discovery é removido |
| **Plans** | Vale a pena, mas não agora | Item acrescentado ao arquivo de `docs/plans/` da área (ou arquivo novo), com a recomendação e o link das fontes; arquivo de discovery removido |
| **Stand-by** | Só vale a pena se algo mudar | Arquivo **fica** em `docs/discovery/` com status `Stand-by` e **gatilho obrigatório** (condição mensurável, ex.: "algum cliente com >50 mil caracteres de conhecimento"). Sem gatilho, não é stand-by — é descartar |
| **Descartar** | Não compensa ou não se aplica | Arquivo removido; uma linha em "Descartados" do radar com o motivo, para não reabrir sem facto novo |

O conteúdo útil de uma investigação promovida **viaja com ela** (motivação,
evidência, fontes) — o stub ou o item de plans deve dispensar reler a
investigação.

---

## `_metas-produto.md`

- 3 a 5 metas, cada uma com um indicador observável.
- O Claude pode propor rascunhos ou alterações, mas **só o utilizador valida**.
  Enquanto estiver marcado como rascunho, o `/discovery-status` lembra disso.
- Revisão rara: quando a estratégia comercial muda. Não pedir revisão a cada
  investigação.

## `_radar.md`

Espelho do estado atual, sem histórico (o histórico está no git). Atualizar em
**todo** comando que muda o estado de uma investigação. Secções: "Prontas para
decisão", "Em investigação / Levantadas", "Stand-by (gatilhos)", "Descartados".

---

## Git

Trabalho de discovery é só documentação. Seguir as regras de commit do
`CLAUDE.md` (Conventional Commits com prefixo `docs:`, `git add` nos arquivos
específicos). Um comando = um commit. Nunca push automático.

Se a sessão estiver numa worktree de implementação, fazer o commit na branch
dessa worktree; se estiver na pasta principal, a discovery pode ser commitada
direto na branch atual (mesma exceção que o `/statusplans-avancar` usa para
documentos de fila).

## Regras de escrita

1. **Linguagem simples** nas secções que o utilizador lê (Pergunta,
   Recomendação, Veredito, Perguntas) — ele não é programador.
2. **Evidência antes de opinião:** arquivo:linha, número medido ou link.
3. **Sem histórico no texto** — reescrever a secção, não acrescentar "agora
   passou a…".
4. **Uma investigação, uma pergunta.** Se surgir outra pergunta, abrir outra
   investigação.
