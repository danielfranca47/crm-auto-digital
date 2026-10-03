# Limpar as regras antigas de "permitir sempre" do Claude Code

**Branch:** (a criar)
**Status:** Aguardando Plan Mode
**Origem:** este item surgiu como "Ajuste possível" na graduação de `feat-modo-auto-sem-cliques.md` (04/10/2026), marcado como urgente pelo utilizador

---

## Motivação

Antes do modo auto, cada clique em "permitir sempre" acrescentava uma regra
`allow` às definições do Claude Code. Ficaram acumuladas 232 regras nas
definições pessoais (`~/.claude/settings.json`) e 83 nas do projeto
(`.claude/settings.json`). Com o modo auto ativo, a maioria é redundante — o
revisor automático já aprova esse trabalho sem clique — mas continuam a ter
efeito: um comando que casa com uma regra `allow` corre **sem passar pelo
revisor**.

Dois problemas concretos:

- **12 regras pessoais têm o que parece ser uma senha ou token escrito no
  próprio texto da regra** (ex.: comandos `curl` de login guardados por
  inteiro). Não estão no repositório, mas ficam em texto simples num ficheiro
  de definições.
- **Regras largas demais** deixam passar comandos que o revisor devia ver. As
  de intérprete com código livre e `railway run *` já saíram na implementação
  anterior; falta rever as restantes com o mesmo critério.

Comportamento desejado: listas `allow` curtas, só com o que comprovadamente
poupa tempo e não abre caminho a código arbitrário; nenhuma credencial dentro
de uma regra.

## Área do sistema

- `.claude/settings.json` (versionado) — o Claude pode editar
- `~/.claude/settings.json` (na máquina) — **quem aplica é o utilizador**: o
  revisor automático recusa que o Claude altere as próprias regras de permissão
  (motivo `[Self-Modification]`). O Claude prepara a lista do que sai e um
  script; o utilizador corre-o, como na implementação anterior.
- `docs/ops/local-dev.md`, secção "Modo auto e regras de permissão do Claude Code"

Diagnóstico (Plan Mode) ainda não feito — próximo passo é seguir o Passo 0 de
`_guia-documentar-implementacao.md`. A decidir nesse passo:

- Critério de corte: apagar tudo e deixar só o revisor decidir, ou manter um
  núcleo de regras de leitura (ver a skill `fewer-permission-prompts`).
- Se as credenciais que aparecem nas 12 regras ainda são válidas e devem ser
  trocadas, além de removidas do ficheiro.
- Alternativa de uma linha a considerar: `autoMode.classifyAllShell: true` faz o
  revisor ver todos os comandos de shell independentemente das regras `allow`
  (custo: cada comando espera pela decisão do revisor).
