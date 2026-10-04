# Modo auto do Claude Code — melhorias futuras

> Contexto: itens deixados de fora das graduações de
> `feat-modo-auto-sem-cliques.md` (M1) e de
> `feat-verificador-comandos-barreiras-duras.md` (M2 a M5), ambas de
> 04/10/2026. O estado atual das regras e do verificador está em
> [`docs/ops/local-dev.md`](../ops/local-dev.md), secção "Modo auto e regras de
> permissão do Claude Code".

## M1 — Sessões sem ecrã ignoram as regras `allow` do projeto em pasta não marcada como de confiança

**Prioridade: ALTA**

Uma sessão do Claude Code lançada sem ecrã (`claude -p`) numa pasta que nunca
foi aberta de forma interativa arranca com o aviso:

```
Ignoring 83 permissions.allow entries from .claude/settings.json: this
workspace has not been trusted.
```

As regras `deny` e `ask` continuam a valer e o revisor automático decide o
resto, por isso nada fica desprotegido — mas o trabalho que dependia das regras
`allow` passa a depender só do revisor. Observado em 04/10/2026 numa worktree
(`.claude/worktrees/...`): cada worktree é uma pasta nova, logo nunca está
marcada como de confiança.

**Por que é ALTA:** é pré-requisito do agente que vai executar a fila de
`docs/plans/` e `docs/implementations/` sozinho — esse agente trabalha
precisamente em sessões sem ecrã dentro de worktrees novas. Só importa quando
esse agente for construído.

**A decidir:** marcar a pasta como de confiança de forma automática ao criar a
worktree (a mensagem de aviso aponta para `hasTrustDialogAccepted` em
`~/.claude.json`, que é um ficheiro da máquina — ver a nota sobre quem aplica
alterações a definições pessoais em
[`docs/ops/local-dev.md`](../ops/local-dev.md), secção "Modo auto e regras de
permissão do Claude Code"), ou assumir que o agente da fila depende só do
revisor automático e das regras `deny`/`ask`. Se
`fix-limpeza-regras-permitir-sempre.md` reduzir as regras `allow` a quase nada,
a segunda opção pode bastar.

## M2 — Impedir que a branch `main` seja apagada no remoto

**Prioridade: MÉDIA**

Hoje só o push forçado é barreira. Apagar a `main` no GitHub
(`git push origin :main`, `git push --delete origin main`) não é travado nem
pelo verificador (`scripts/claude_hooks/verificar_comando.py`) nem pelo ruleset
`main - sem push forcado`, que só tem a regra `non_fast_forward`.

**A fazer:** ligar a regra "Restrict deletions" no ruleset do GitHub (é a
garantia que não depende do texto do comando — alteração externa, exige um
"sim" explícito do utilizador) e acrescentar ao verificador e às regras `deny`
de `.claude/settings.json` as formas de apagar uma branch remota. Decidir se a
barreira vale só para a `main` ou para qualquer branch remota — o fluxo de
graduação só apaga branches locais (`git branch -d`), por isso não é afetado.

## M3 — Mais ações do Railway vigiadas

**Prioridade: MÉDIA**

Ficaram fora da lista de barreiras: `railway redeploy` / `restart` (reiniciam
um serviço de produção), `railway volume files rename` (mexe nos ficheiros
onde vivem as bases de dados e os backups) e apagar domínios ou buckets.

**A decidir, ação a ação:** recusar, perguntar, ou deixar ao revisor
automático. Alterar a lista exige mexer nos dois sítios — regras em
`.claude/settings.json` e tabelas no topo do verificador — e acrescentar os
casos à bateria de testes.

## M4 — Seguir scripts chamados por outros scripts

**Prioridade: MÉDIA**

O verificador lê o script chamado diretamente pelo comando (até 512 KB). Se
esse script chamar outro script noutra pasta, o segundo pode não ser seguido,
e uma ação barrada lá dentro só depende do revisor automático.

**A fazer:** seguir as chamadas a scripts dentro de scripts, com limite de
profundidade e resolvendo os caminhos relativos à pasta do script que chama.
Ganha peso com o agente que executa a fila sozinho.

## M5 — Pergunta a mais em `git push` com variável na mesma linha de um `-f`

**Prioridade: MÉDIA**

`git push -u origin "$RAMO" && rm -f tmp` pergunta: o push tem um argumento só
conhecido ao executar e há um `-f` na mesma linha, embora pertença a outro
comando. Em sessão sem ecrã a pergunta vira uma recusa; hoje contorna-se
separando os dois comandos.

**A fazer:** procurar o sinal de força só dentro do próprio comando `git push`,
não na linha inteira.
