---
description: Lê todos os arquivos de docs/implementations/ e dá um panorama não-técnico (impacto, classificação, % concluído, prioridade)
---

Leia todos os arquivos `.md` de `docs/implementations/`, **exceto** os arquivos-guia que começam
com `_` (`_guia-documentar-implementacao.md`, `_guia-resolucao-conflitos.md`,
`_processo-graduacao-implementacao.md`, `_template-implementacao.md`, `_conta-teste-local.md`) e
o `README.md` da pasta — esses são meta-documentação de processo, não itens de trabalho.

Rode `git worktree list` para descobrir quais implementações têm uma worktree/branch ativa agora
(cada worktree fica em `.claude/worktrees/<tipo>/<slug>` e o slug corresponde ao nome do arquivo
de implementação, ex.: `feat/notificacoes-push` ↔ `feat-notificacoes-push.md`). Use isso para
marcar, por item, se há um worker em andamento — isso evita que o usuário inicie trabalho
duplicado em algo que já está sendo feito em outra sessão/worktree.

Para cada arquivo restante, monte uma tabela com:

- **Item** — nome do arquivo (sem extensão)
- **O que é** — descrição em 1-2 frases, linguagem não-técnica (o usuário não é programador),
  focada no comportamento observável, não em nomes de função/arquivo
- **Classificação** — um destes: 🔴 Crítico (bug ativo, risco de receita/segurança/conversão),
  🟡 Importante (funcionalidade real, não visual), 🟢 Estético/Cosmético, ⚪ Decisão de design
  (não é bug), 🔧 Débito técnico/risco arquitetural
- **% Concluído** — baseado no campo `Status:` do arquivo e nos checks de validação marcados
  `[x]` vs `[ ]`
- **Worker ativo** — 🟢 Livre (nenhuma worktree encontrada para o slug) ou 🔵 Em andamento
  (nome da branch/worktree ativa) — se estiver em andamento, avisar que iniciar trabalho nesse
  item agora provavelmente duplica esforço
- **Prioridade recomendada** — Alta / Média-alta / Média / Baixa, com justificativa curta

Depois da tabela, destaque em texto corrido:
- Qualquer item pronto para graduar (todos os checks `[x]`) que ainda não foi graduado
- Qualquer bug crítico confirmado e não resolvido (não só planejado)
- Qualquer sobreposição/duplicação entre dois arquivos tratando do mesmo assunto
- Qualquer item com worker ativo (🔵) — deixar claro que já há trabalho em andamento ali
- Uma ordem sugerida de ataque (top 3-5) com 1 linha de razão cada, **excluindo** itens com
  worker já ativo (esses não entram na lista de "por onde começar")

Feche perguntando ao usuário por qual item ele quer começar, ou se prefere consolidar algum
item duplicado/relacionado em Plan Mode primeiro.

Não sugira nem inicie nenhuma mudança de código nesta resposta — é só levantamento e priorização.
