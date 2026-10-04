# Fila automática — turno do dia e avaliador em modo sombra

**Branch:** `worktree-feat+fila-turno-do-dia-avaliador`
**Status:** Em andamento
**Autonomia:** manual
**Origem:** Fase 3 do plano aprovado em 04/10/2026 (contrato: `docs/ops/fila-automatica.md`)

---

## Motivação

O que o turno da noite deixa numa branch `claude/<slug>` ainda não foi visto a
funcionar: na cloud não há browser nem os dados locais. Falta quem teste, quem
avalie e quem diga ao utilizador, em linguagem simples, se aquilo resolve a dor
inicial.

Comportamento desejado: com o PC ligado, o comando `/fila-validar` segue a
secção "Turno do dia" de
[`docs/ops/fila-automatica.md`](../ops/fila-automatica.md) — traz a branch,
corre os testes, valida os checks via browser, corre o script do que sobe
sempre e lança o avaliador. Nesta fase o avaliador está em **modo sombra**: dá
o veredito e o relatório, mas quem decide o merge é o utilizador, e cada caso
entra no placar.

O último passo do item é ligar o horário da rotina da noite, que ficou
desligada (decisão do utilizador, 04/10/2026) para não se acumularem branches
sem ninguém a testar nem a avaliar.

`Autonomia: manual` porque mexe nas regras do próprio agente.

---

## Problemas Identificados (estado anterior)

1. **As regras do dia existem, mas ninguém as executa.**
   `docs/ops/fila-automatica.md` descreve "Turno do dia", "Avaliador" e "Placar
   do modo sombra"; não existe o comando `/fila-validar` (`.claude/commands/`
   só tem os comandos de status e discovery) nem forma de lançar o avaliador.
2. **Aviso "this workspace has not been trusted" também na pasta principal.**
   Medido em 04/10/2026: uma sessão sem ecrã (`claude -p`) lançada de
   `C:\crm-auto-digital`, por Bash e por PowerShell, mostra o aviso. O Claude
   Code procura a chave `C:/crm-auto-digital` em `~/.claude.json`, que tem
   `hasTrustDialogAccepted: false`; a que está aceite é `C:\crm-auto-digital`.
   A hipótese do M1 de `docs/plans/modo-auto-melhorias-futuras.md` ("lançar da
   pasta principal evita o aviso") não se confirmou.
3. **O contrato contradiz-se sobre `.env`.** Uma sessão da fila "nunca lê ou
   escreve `.env`", mas o passo 4 do turno do dia manda preparar o ambiente
   local, que exige copiar os `.env` para a worktree.
4. **Não está definido o que acontece ao item quando o utilizador diz "não".**
   Apagar só a branch faria a noite refazer o mesmo item, igual: a
   elegibilidade só olha para "não existe `origin/claude/<slug>`".
5. **Não está definido que casos contam para os 5 vereditos do placar.**
6. **M4 (tranca do GitHub contra a cloud em `main`) não é possível.** O GitHub
   regista o push da noite como `danielfranca47` (tipo User), igual a um push
   do utilizador
   (`gh api "repos/danielfranca47/crm-auto-digital/activity?ref=refs/heads/claude/fix-docs-campos-obrigatorios-qualificacao"`);
   só os commits aparecem como "claude". Um ruleset não distingue os dois. A
   reconfirmar na primeira execução agendada — o ensaio de 04/10 foi lançado à
   mão.

---

## Abordagem

```
/fila-validar (pasta principal, sessão da fila)
  → para cada origin/claude/* "Implementado de noite — por validar"
      worktree claude+<slug> + main junto
      testes automáticos · checks via browser
      python scripts/fila/categorias_que_sobem.py     → sobe / não sobe
      python scripts/fila/lancar_avaliador.py         → aprovado / não aprovado
          └─ sessão separada, sem ecrã, na pasta principal, só de leitura
             pedido fixo (só o nome da branch) · modelo Opus
             o script escreve "## Avaliação" no .md do item
      "## Relatório para decisão" + Status + push para claude/<slug>
  → relatório na conversa, com link do ficheiro no GitHub
  → o utilizador decide: juntar · devolver com correções · fechar · depois
  → linha no placar (conta só se o avaliador pudesse decidir sozinho)
```

Decisões do utilizador (04/10/2026):

- **Placar:** contam só os casos que o avaliador decidiria sozinho — branch
  que não toca em nada que sobe sempre e com todos os checks validados. Os
  outros ficam registados como "não conta". Descartado "contam todos": inclui
  casos fáceis em que concordar não prova muito.
- **Modelo do avaliador:** Opus. Descartado o Sonnet da noite: quem avaliava
  era o mesmo modelo que implementou.

Decisões de desenho:

- **Avaliador como sessão sem ecrã, não como subagente.** Um subagente recebe
  um pedido escrito por quem testou, que pode levar contexto a mais. O script
  monta um pedido fixo e só aceita o nome da branch.
- **`--permission-mode dontAsk` com lista fechada de ferramentas.** Medido em
  04/10/2026: nesta combinação a shell corre `git log` e `git status` e recusa
  `git add -n .` ("Permission to use Bash has been denied because Claude Code
  is running in don't ask mode"). Não depende das regras `allow` do projeto,
  por isso o aviso do ponto 2 não o afeta. Descartado acrescentar regras
  `Bash(git diff *)`: uma regra dessas deixaria passar `git diff --output=…`,
  que escreve um ficheiro.
- **A sessão corre na pasta principal**, para que os critérios venham de
  `main` e não de uma branch que os possa ter alterado.
- **É o script que escreve a secção `## Avaliação`** — o avaliador não tem como
  escrever, e quem testou não deve transcrever o veredito.
- **Relatório:** fica no `.md` do item, na branch (é de onde o painel vai ler).
  Para o utilizador o ler sem abrir a branch, o `/fila-validar` mostra-o na
  conversa com o link do GitHub. Sem pasta nem ficheiro novo.

---

## Plano de Implementação

### Fase 1 — Avaliador

**Objetivo:** existir uma forma única, testada e só de leitura de lançar o
avaliador sobre uma branch `claude/<slug>`.

| Arquivo | O que muda |
|---|---|
| `scripts/fila/lancar_avaliador.py` | Novo. Valida o nome da branch, monta o pedido fixo, lança `claude -p` na pasta principal (Opus, `dontAsk`, `Read,Grep,Glob,Bash`, sem MCP), lê a resposta em JSON e escreve `## Avaliação` no item. Saída 0 / 1 / 2 |
| `scripts/fila/tests/test_lancar_avaliador.py` | Novo. Nomes de branch, comando montado, leitura da resposta, secção escrita, falha fechada. Nenhuma sessão real é lançada |
| `docs/ops/fila-automatica.md` | Secção "Avaliador": como se lança e o que o script garante |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `67405fd` | Lançador do avaliador, testes e secção "Avaliador" do contrato |

**Detalhes do commit `67405fd`:**
- `scripts/fila/lancar_avaliador.py` — novo: valida a branch, monta o pedido fixo, lança a sessão na pasta principal, lê a resposta, escreve `## Avaliação`
- `scripts/fila/tests/test_lancar_avaliador.py` — novo: 48 casos, sem lançar sessão real
- `docs/ops/fila-automatica.md` — secção "Avaliador"

### Relatório da Fase 1 — o que mudou na prática

**Antes:** as regras diziam que um avaliador independente dava o veredito
sobre cada branch da noite, mas não havia forma de o lançar.
**Agora:** um comando lança o avaliador sobre uma branch. Ele corre numa sessão
à parte, sem saber nada de quem implementou ou testou, sem conseguir alterar
nenhum ficheiro, e lê os critérios da versão em produção das regras — não da
branch que está a avaliar. O veredito e a explicação, em linguagem simples,
ficam escritos no ficheiro do item. No ensaio com a branch que a noite já
deixou, respondeu "não aprovado" com três motivos concretos, e custou 1,07 USD
de referência.
**Para validar:** Cenários A1 e A2, abaixo — já validados em 04/10/2026.

### Fase 2 — Turno do dia, decisão e placar

**Objetivo:** `/fila-validar` leva uma branch da noite até ao relatório, o
utilizador decide, e a decisão é executada e registada no placar.

| Arquivo | O que muda |
|---|---|
| `docs/ops/fila-automatica.md` | "Turno do dia" com os passos concretos (incluindo a exceção dos `.env` e o relatório); subsecção nova "Decisão do utilizador (modo sombra)"; regra do placar e coluna "Conta?"; linha em "Turno da noite" sobre `## Correções pedidas`; "Estado atual" |
| `docs/ops/local-dev.md` | Subsecção `/fila-validar` em "Comandos slash locais" |
| `.claude/commands/fila-validar.md` (pasta principal, não versionado) | Novo — só o gatilho. **Criado na graduação**, depois de sair da worktree: a sessão da implementação não consegue escrever na pasta principal, e o comando só faz sentido com as regras novas já em `main` |

Consequência para os testes: antes do merge, `/fila-validar` na pasta
principal leria as regras antigas. Por isso os Cenários D1 a D3 são executados
pela sessão da implementação, a seguir a secção "Turno do dia" **desta branch**
passo a passo, como o comando fará. O comando verdadeiro é exercitado no D4.

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `4a8debf` | Regras do turno do dia, da decisão do utilizador e do placar; comando `/fila-validar` registado |

**Detalhes do commit `4a8debf`:**
- `docs/ops/fila-automatica.md` — "Turno do dia" passo a passo, "Decisão do utilizador", regra do placar e coluna "Conta?", retoma pela secção `## Correções pedidas`, exceção dos `.env`, "Estado atual"
- `docs/ops/local-dev.md` — subsecção `/fila-validar` com o conteúdo do comando

### Relatório da Fase 2 — o que mudou na prática

**Antes:** as regras diziam em traços largos o que o dia fazia com uma branch
da noite, mas não havia comando para o lançar, não estava escrito o que
acontecia quando o utilizador dizia "não", nem que casos contavam para os 5
vereditos seguidos.
**Agora:** está escrito, passo a passo, o que o `/fila-validar` faz com cada
branch: testa, verifica, corre o script do que sobe sempre, lança o avaliador,
escreve um relatório em linguagem simples e mostra-o na conversa com um link.
No fim o utilizador escolhe uma de quatro respostas — juntar, devolver à noite
com correções, fechar, ou decidir depois — e cada uma tem um efeito definido.
Fechar deixa o item marcado para a noite não o refazer igual. O placar só soma
nos casos em que o avaliador poderia ter decidido sozinho.
**Para validar:** Cenários D1, D2 e D3, abaixo. O D4 só é possível depois do
merge e da primeira branch real da noite.

### Fase 3 — Ligar a noite

**Objetivo:** a rotina da noite passa a correr às 04:07 de Lisboa.

| Arquivo | O que muda |
|---|---|
| `docs/ops/local-dev.md` | Parágrafo "Sessões sem ecrã" com o que foi medido |
| `docs/plans/modo-auto-melhorias-futuras.md` | M1 sai, se L1 se confirmar |
| `docs/plans/fila-automatica-melhorias-futuras.md` | M4 sai, com o achado registado no contrato |
| `docs/ops/fila-automatica.md` | "Estado atual": turno da noite ligado; achado do M4 em "Turno da noite" |

Fora do repositório, com o "sim" do utilizador no momento: aceitar o aviso de
confiança (o utilizador corre `claude` uma vez num terminal na pasta
principal) e ligar o horário da rotina `trig_01H55ZGUhNCdAcHqzkri2djD`,
confirmando que continua sem conectores.

---

## Checks de Validação

Prefixo `A` = avaliador, `D` = turno do dia, `L` = ligar a noite.

### Cenário A1 — Avaliador contra a branch do ensaio
- [x] Com a worktree `.claude/worktrees/claude+fix-docs-campos-obrigatorios-qualificacao`
      criada, correr `python scripts/fila/lancar_avaliador.py --ramo claude/fix-docs-campos-obrigatorios-qualificacao`
- [x] Confirmar: o item nessa worktree ganha `## Avaliação` em linguagem simples, com veredito e os 6 critérios
- [x] Confirmar: a pasta principal fica sem alterações (`git status` limpo) e a sessão não escreveu nada
- [x] Anotar o consumo
- **Validado em:** 04/10/2026 — saída 1, veredito "não aprovado": critérios 1, 3
  e 4 cumpridos; 2 (os dois checks do item por marcar, e o segundo não consegue
  passar como está escrito), 5 (hash do commit por registar) e 6 (o mapa do
  sistema ainda fala em campos mínimos por tipo de agente) por cumprir. Texto
  sem nomes de função nem de ficheiro de código. Pasta principal limpa depois
  da sessão. Consumo: 38 turnos, 1,07 USD de referência, modelo Opus. Duas
  ações recusadas, ambas comandos de leitura escritos com `cd … &&` e com
  `git -C` — o avaliador seguiu com `git diff main...` simples; o pedido passou
  a dizer-lhe isso à partida. A worktree e a branch local do ensaio foram
  removidas a seguir, para o D1 partir do zero.

### Cenário A2 — Falha fechada
- [x] `--ramo main` e `--ramo claude/item-que-nao-existe` saem com código 2, sem lançar sessão
- [x] `python -m pytest scripts/fila/tests -q` — tudo aprovado
- **Validado em:** 04/10/2026 — as duas chamadas saíram com 2 e a mensagem
  "Tratar como NÃO APROVADO"; 142 testes aprovados em `scripts/fila/tests`
  (437 com `scripts/claude_hooks/tests`).

### Cenário D1 — Turno do dia de ponta a ponta
- [ ] Sem worktree `claude+…` aberta, seguir a secção "Turno do dia" desta branch
      para `claude/fix-docs-campos-obrigatorios-qualificacao`
- [ ] Confirmar: worktree criada, `main` junto, testes e checks registados no item
- [ ] Confirmar: o script do que sobe sempre responde "sobe" (`CLAUDE.md`)
- [ ] Confirmar: veredito do avaliador no item, `Status: À espera da tua decisão`, relatório na conversa com link e push feito para `claude/<slug>`

### Cenário D2 — Decisão do utilizador e placar
- [ ] Responder à decisão pedida no fim do D1
- [ ] Confirmar: a ação correspondente foi executada
- [ ] Confirmar: o placar ganhou a linha, marcada "não conta" (sobe sempre), e "Seguidas" não mudou

### Cenário D3 — Worktree em duplicado
- [ ] Com uma worktree do mesmo slug já aberta, voltar ao passo 1 do turno do dia
- [ ] Confirmar: não avança e reporta trabalho em duplicado

### Cenário D4 — Comando verdadeiro e primeiro caso que conta para o placar
- [ ] Depois do merge: `.claude/commands/fila-validar.md` existe na pasta principal e `/fila-validar` aparece na lista de comandos
- [ ] Com a primeira branch da noite que não toque em nada que sobe sempre: `/fila-validar` + decisão
- [ ] Confirmar: a linha do placar fica marcada "conta" e "Seguidas" passa a 1 (ou 0, se houver discordância)

### Cenário L1 — Pasta principal de confiança
- [ ] O utilizador corre `claude` num terminal em `C:\crm-auto-digital` e aceita o aviso
- [ ] `claude -p "Responde apenas: ok" --model haiku --no-session-persistence` na pasta principal já não mostra "has not been trusted"

### Cenário L2 — Horário ligado
- [ ] Rotina `trig_01H55ZGUhNCdAcHqzkri2djD` com horário 04:07 de Lisboa, todos os dias, e zero conectores

### Cenário L3 — Primeira noite agendada
- [ ] No dia seguinte: a execução aconteceu à hora prevista
- [ ] Quem o GitHub regista como autor do push (confirma ou desmente o achado do M4)
- [ ] Consumo de uma noite com o PC desligado

---

## Ajustes Possíveis Pós-Implementação

- **Reinício de produção num push só de documentos** — cada decisão que não
  seja "juntar" envia para `main` um commit só com a linha do placar. É o M3
  de `docs/plans/fila-automatica-melhorias-futuras.md`, que continua lá.
- **O avaliador não corre os testes** — confia no registo do turno do dia. Se
  um dia o turno do dia correr sem ninguém a ver, pode valer a pena o avaliador
  repetir os testes numa cópia própria.
- **Sem a pasta principal marcada como de confiança**, uma sessão sem ecrã
  ignora as regras `allow` do projeto (testes, browser). Não afeta o avaliador;
  afeta `feat-fila-arranque-de-dia-e-painel`.
