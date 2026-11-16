---
description: Lê docs/plans/ e dá um panorama rápido de prioridades (sem auditar código) — passo 1 do fluxo, antes de /statusplans-verificar
---

Leia todos os arquivos `.md` de `docs/plans/`, **exceto** os arquivos-guia que começam
com `_` (`_guia-analise-planos.md`, `_template-plano-semanal.md`,
`_versionamento-agent-local.md`) e o `README.md` da pasta — esses são meta-documentação
de processo, não itens de trabalho. Inclua qualquer `plano-sprint-*.md` existente — é um
item de trabalho em andamento, não um guia.

Um arquivo de plans pode conter vários itens (M1, M2, Etapa A/B/C, ou seções por título).
Identifique cada item individualmente — não trate o arquivo inteiro como uma linha só,
a menos que ele não tenha subdivisão.

Monte uma tabela com:

- **Arquivo** — nome do arquivo de origem (sem extensão)
- **Item** — identificador dentro do arquivo (M1, Etapa C, etc.) ou "arquivo inteiro"
  se não houver subdivisão
- **O que é** — 1-2 frases, linguagem não-técnica (o usuário não é programador), focada
  em comportamento observável
- **Prioridade declarada** — como está escrita no arquivo (ALTA/MÉDIA/BAIXA), ou
  "não declarada"
- **Prioridade recomendada** — Alta / Média-alta / Média / Baixa, considerando a
  prioridade declarada + se o texto cita bloqueio de receita, segurança ou usuários
  actuais + quão antigo parece o contexto do plano
- **Possível obsolescência** — 🟢 sem indício, ou 🟡 revisar (ex.: o item cita um
  provedor, integração ou fluxo que pode ter mudado desde que o plano foi escrito).
  **Não confirme obsolescência aqui** — apenas sinalize. Confirmar é trabalho do
  próximo comando, que lê o código.

Esta resposta é uma leitura de inventário, não uma auditoria — **não abra arquivos de
código-fonte** nesta resposta, só os arquivos de `docs/plans/`.

Depois da tabela, destaque em texto corrido:
- Duplicação/sobreposição entre dois arquivos tratando do mesmo assunto
- Um `plano-sprint-*.md` já existente e não fechado — avisar que ele deveria ser tratado
  junto ou primeiro, e apontar quantos itens dele ainda estão `⏳ Pendente`
- Ordem sugerida de ataque: **até 6 itens**, ordenados por prioridade recomendada,
  priorizando quem tem 🟡 na coluna de obsolescência (verificar isso primeiro evita
  migrar trabalho desnecessário para implementations)

Feche perguntando se o usuário quer rodar `/statusplans-verificar` sobre a lista
sugerida, ou se prefere indicar uma lista customizada de itens.

Não crie, edite nem apague nenhum arquivo nesta resposta — só leitura e priorização.
