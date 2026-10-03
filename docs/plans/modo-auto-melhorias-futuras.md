# Modo auto do Claude Code — melhorias futuras

> Contexto: item deixado de fora da graduação de
> `feat-modo-auto-sem-cliques.md` (04/10/2026). Os outros dois itens dessa
> graduação foram marcados como urgentes e estão em
> `docs/implementations/fix-limpeza-regras-permitir-sempre.md` e
> `docs/implementations/feat-verificador-comandos-barreiras-duras.md`.

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
