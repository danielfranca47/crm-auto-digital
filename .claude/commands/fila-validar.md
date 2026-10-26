---
description: Turno do dia da fila automática — testa cada branch claude/* deixada pela noite, lança o avaliador e entrega o relatório para decisão
---

És uma sessão da fila automática (turno do dia), lançada pelo utilizador a partir da
pasta principal do repositório.

Lê o `CLAUDE.md` e `docs/ops/fila-automatica.md` e executa a secção "Turno do dia",
passo a passo, para cada branch `origin/claude/*` com
`Status: Implementado de noite — por validar`. As regras moram nesse ficheiro, não
aqui: se este texto e o ficheiro disserem coisas diferentes, vale o ficheiro.

Se o utilizador escreveu um slug a seguir ao comando, trata só essa branch:
$ARGUMENTS

Se a pasta atual não for a pasta principal (é uma worktree), não avances: diz ao
utilizador para lançar o comando a partir da pasta principal.

No fim, mostra o relatório de cada branch em linguagem simples, com o link do
ficheiro no GitHub, e pede a decisão como manda a subsecção "Decisão do utilizador".
Não juntes nada a `main`, não devolvas nem apagues nenhuma branch sem essa decisão.
