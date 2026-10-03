# Verificador de comandos para as barreiras duras do Claude Code

**Branch:** (a criar)
**Status:** Aguardando Plan Mode
**Origem:** este item surgiu como "Ajuste possível" na graduação de `feat-modo-auto-sem-cliques.md` (04/10/2026), marcado como urgente pelo utilizador

---

## Motivação

As barreiras duras do projeto são regras `deny` e `ask` em
`.claude/settings.json` (push forçado, apagar ou desligar coisas no Railway,
mexer em variáveis de produção). Essas regras comparam o **início do texto do
comando** com um padrão, por isso só apanham a forma habitual de o escrever.
O mesmo comando escrito de outra maneira não casa com a regra:

- opções antes do subcomando (`git -c ... push --force`, `git -C <pasta> push -f`)
- o comando perigoso no meio de uma cadeia (`cd pasta && git push --force`)
- variantes da opção (`--force-with-lease`, `+main` no destino do push)
- o comando dentro de um script ou de outra shell

Nesses casos a única proteção que sobra é o revisor automático, que não é uma
garantia. Isto ganha peso com o objetivo seguinte — um agente que executa a
fila sozinho, sem ninguém a olhar para o ecrã.

Comportamento desejado: as ações proibidas são recusadas (e as sensíveis
perguntam) independentemente da forma como o comando foi escrito.

## Área do sistema

- `.claude/settings.json` — bloco `hooks`, evento `PreToolUse` para as
  ferramentas `Bash` e `PowerShell`
- Um script novo, versionado, que recebe o comando inteiro e decide
  (permitir / perguntar / recusar)
- `docs/ops/local-dev.md`, secção "Modo auto e regras de permissão do Claude Code"

Diagnóstico (Plan Mode) ainda não feito — próximo passo é seguir o Passo 0 de
`_guia-documentar-implementacao.md`. A decidir nesse passo:

- Em que linguagem fica o script (tem de correr em Windows, na shell que o
  Claude Code usa para hooks) e onde vive no repositório.
- Lista exata de formas alternativas a cobrir, e como testar cada uma sem
  executar a ação real (ex.: `--dry-run`, `--help`).
- Comportamento do hook em sessões sem ecrã (`claude -p`), onde "perguntar"
  equivale a recusar.
- Se as regras `deny`/`ask` atuais se mantêm como primeira camada ou são
  substituídas pelo hook.
