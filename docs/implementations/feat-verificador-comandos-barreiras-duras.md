# Verificador de comandos para as barreiras duras do Claude Code

**Branch:** `worktree-feat+verificador-comandos-barreiras-duras` (worktree `.claude/worktrees/feat+verificador-comandos-barreiras-duras`)
**Status:** Em andamento
**Origem:** este item surgiu como "Ajuste possível" na graduação de `feat-modo-auto-sem-cliques.md` (04/10/2026), marcado como urgente pelo utilizador

---

## Motivação

As barreiras duras do projeto são regras `deny` e `ask` em
`.claude/settings.json` (push forçado, apagar ou desligar coisas no Railway,
mexer em variáveis de produção). Essas regras comparam o **texto do comando**
com um padrão, por isso só apanham a forma habitual de o escrever. O mesmo
comando escrito de outra maneira não casa com a regra, e a única proteção que
sobra é o revisor automático, que não é uma garantia. Isto ganha peso com o
objetivo seguinte — um agente que executa a fila sozinho, sem ninguém a olhar
para o ecrã.

Comportamento desejado: as ações proibidas são recusadas (e as sensíveis
perguntam) independentemente da forma como o comando foi escrito.

---

## Problemas Identificados (estado anterior)

Diagnóstico de 04/10/2026, contra a documentação oficial do Claude Code e o
`railway --help` (CLI 5.15.0) desta máquina.

**Já estava coberto** (não era um buraco): o Claude Code separa cadeias
(`&&`, `||`, `;`, `|`), subshells e `$(...)` e aplica `deny`/`ask` a cada
pedaço. `cd pasta && git push --force` já era recusado; `--force-with-lease`
também (casa com `git push --force*`).

**Buracos confirmados** — nenhum destes casava com as regras de
`.claude/settings.json`:

1. **Nomes alternativos do Railway.** A CLI aceita `railway rm` / `remove`
   (apaga o projeto), `railway project delete`, `railway volumes …`,
   `railway env delete`, `railway vars` / `var`, `railway local` (= `run`).
   É o buraco mais sério: são formas normais de escrever, não truques.
2. **Opções antes do subcomando.** `git -C . push -f`,
   `git -c x=y push --force`, `railway -s backend-crm volume delete`.
3. **Outro nome do executável.** `git.exe push -f`, `/usr/bin/git push -f`,
   `git 'push' -f`.
4. **Forçar sem a opção habitual.** `git push origin +main`,
   `git push --mirror`, opções abreviadas (`--forc`) ou agrupadas (`-fu`).
5. **Shell dentro de shell.** `bash -c "…"`, `cmd /c …`,
   `powershell -Command …`, `-EncodedCommand`, `eval`, `Invoke-Expression`,
   `Start-Process`.
6. **Dentro de um script.** `bash deploy.sh`, `npm run deploy`,
   `python publicar.py` com a ação lá dentro.
7. **Não existia nenhum hook.** `.claude/settings.json` só tinha o bloco
   `permissions`.

---

## Abordagem

Um script (`scripts/claude_hooks/verificar_comando.py`) ligado ao evento
`PreToolUse` das ferramentas `Bash` e `PowerShell`. Recebe o comando inteiro,
**lê a estrutura** em vez de comparar o início do texto, e responde:

```
comando → separar em comandos simples (cadeias, subshells, $(...), crases)
  → em cada um: tirar VAR=valor e invólucros (env, timeout, sudo, xargs, npx…)
  → reduzir o executável ao nome base (sem pasta, sem .exe, sem aspas)
  ├─ git      → saltar opções globais → subcomando push?
  │              ├─ --force / -f / --force-with-lease / --mirror / +destino → RECUSAR
  │              └─ argumento só conhecido ao executar + sinal de força no texto → PERGUNTAR
  ├─ railway  → saltar opções, normalizar nomes alternativos
  │              ├─ down, delete, environment|project|service delete,
  │              │  volume delete|rm|remove|detach, volume files delete → RECUSAR
  │              └─ variable, run, shell, connect, ssh, up, volume files upload → PERGUNTAR
  ├─ outra shell (bash -c, cmd /c, powershell -Command, eval…) → analisar o texto de dentro
  ├─ script (.sh .ps1 .bat .cmd, npm run) → ler o ficheiro e analisar como comandos
  ├─ código (.py .js, python -c, node -e) → procurar as mesmas ações no texto → PERGUNTAR
  ├─ forma ilegível (variável no lugar do programa, `| bash`, aspas por fechar)
  │    e o texto aparenta uma ação vigiada → PERGUNTAR
  └─ resto → nada (segue para as regras de permissão e o revisor automático)
```

Decisões tomadas:

- **Python, só biblioteca padrão.** Já é exigido pelo projeto e os testes
  correm com `python -m pytest`, que já está na lista `allow`.
- **Em `scripts/`, não em `.claude/hooks/`.** `.claude/` está no `.gitignore`
  (só `settings.json` foi versionado à força); em `scripts/` o ficheiro chega a
  todas as worktrees e dispositivos.
- **O script nunca responde "permitir".** Só recusa, pergunta, ou fica calado.
- **As regras `deny`/`ask` de `.claude/settings.json` ficam como estão.** Se o
  hook falhar por fora (sem `python` no PATH, ou tempo limite), o Claude Code
  deixa o comando seguir — as regras continuam a valer nesse caso, e um hook
  nunca as consegue anular.
- **Falha fechada por dentro.** Erro inesperado no script → código 2, que
  bloqueia o comando.
- **Texto que é dado, não comando, não conta:** mensagem de `git commit -m`,
  heredoc lido por `cat`, argumento de `grep`/`echo`. Um commit que fala de
  push forçado não é travado.
- **Descartado: substituir as regras pelo hook** — perderia a camada que
  funciona quando o hook está partido.
- **Descartado: filtrar o hook com o campo `if`** — usa a mesma comparação de
  texto de que se quer fugir.

---

## Plano de Implementação

### Fase 1 — Verificador + testes (ainda desligado)

**Objetivo:** criar o script e a bateria de testes; nada muda no comportamento
do Claude Code.

| Arquivo | O que muda |
|---|---|
| `scripts/claude_hooks/verificar_comando.py` | novo — leitura do comando e decisão |
| `scripts/claude_hooks/tests/test_verificar_comando.py` | novo — 200 casos (texto do comando → decisão esperada) |
| `docs/implementations/feat-verificador-comandos-barreiras-duras.md` | template preenchido |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `cee2ab7` | script verificador + 200 testes + este arquivo preenchido |

**Detalhes do commit `cee2ab7`:**
- `scripts/claude_hooks/verificar_comando.py` — `_Leitor` separa o texto em comandos simples respeitando aspas, heredocs e substituições (Bash e PowerShell); `_git` e `_railway` aplicam a lista de barreiras; `_Analise` trata invólucros, shell dentro de shell, scripts em disco e formas ilegíveis; `main` lê o JSON do hook e falha fechada (código 2)
- `scripts/claude_hooks/tests/test_verificar_comando.py` — tabelas de casos por decisão esperada, scripts criados em pasta temporária, e o contrato do hook testado pelo stdin

### Relatório da Fase 1 — o que mudou na prática

**Antes:** não existia nenhum programa a olhar para o comando inteiro — só as regras de texto.
**Agora:** existe o verificador e a sua bateria de testes, mas **ainda desligado**: o comportamento do Claude Code é exatamente o mesmo de antes.
**Para validar:** Cenário T1, abaixo (já validado — é automático).

### Fase 2 — Ligar o verificador e documentar

**Objetivo:** ativar o hook e atualizar a doc de operação.

| Arquivo | O que muda |
|---|---|
| `.claude/settings.json` | bloco `hooks.PreToolUse` (`matcher: "Bash\|PowerShell"`); `permissions` intacto |
| `docs/ops/local-dev.md` | secção "Modo auto e regras de permissão do Claude Code" descreve as duas camadas |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `d3d56fb` | hook `PreToolUse` ligado + doc de operação |

**Detalhes do commit `d3d56fb`:**
- `.claude/settings.json` — bloco `hooks.PreToolUse` com `python "${CLAUDE_PROJECT_DIR}/scripts/claude_hooks/verificar_comando.py"`, tempo limite de 10 s; `permissions` sem alterações (ficheiro dentro de pasta ignorada: `git add -f`)
- `docs/ops/local-dev.md` — nova subsecção "Verificador de comandos" (o que recusa, o que pergunta, formas cobertas, limites)

### Relatório da Fase 2 — o que mudou na prática

**Antes:** uma ação proibida escrita de forma diferente da habitual (por exemplo `railway volumes delete`, ou `git -C . push -f`) passava pelas regras e só o revisor automático a podia travar.
**Agora:** antes de cada comando de shell, o verificador lê o comando inteiro e recusa essas ações (ou pergunta, nas sensíveis) seja qual for a forma. As regras antigas continuam ativas por baixo.
**Atenção:** só vale em conversas abertas numa pasta que já tenha esta alteração — hoje, só a worktree; a pasta principal passa a ter depois do merge.
**Para validar:** Cenários A1 a A4, abaixo.

### Fase 3 — (opcional, fora do repositório) Proteção do lado do GitHub

**Objetivo:** regra no repositório `danielfranca47/crm-auto-digital` que recusa
push forçado na `main`, qualquer que seja a ferramenta ou a forma do comando.
Push normal continua igual. Só é feita com um "sim" explícito do utilizador no
momento, porque altera uma configuração externa.

**Feita em 04/10/2026**, com o "sim" do utilizador. Não tem commit: é uma
configuração do GitHub, não um ficheiro do repositório.

- Regra criada (`gh api -X POST repos/danielfranca47/crm-auto-digital/rulesets`):
  ruleset **`main - sem push forcado`**, id `24438757`, estado `active`, alvo
  a branch por omissão (`main`), uma única regra `non_fast_forward`, sem
  ninguém na lista de exceções (vale também para o dono do repositório).
- Antes não havia nenhuma proteção: a lista de rulesets estava vazia e a
  proteção clássica respondia "Branch not protected".
- Como desfazer: GitHub → Settings → Rules → Rulesets → apagar ou desativar
  `main - sem push forcado`.

### Relatório da Fase 3 — o que mudou na prática

**Antes:** se um push forçado para a `main` escapasse às camadas do Claude Code, o GitHub aceitava-o.
**Agora:** o GitHub recusa qualquer push forçado na `main`, venha de onde vier e escrito como for. Push normal e o fluxo de graduação continuam iguais. As outras branches não são afetadas.
**Para validar:** Cenário G1, abaixo.

---

## Checks de Validação

Prefixos: `T` = teste automático, `A` = ponta a ponta numa sessão do Claude
Code. Nenhum cenário executa a ação real — usam `--dry-run` ou `--help`.

### Cenário T1 — Bateria de testes do verificador (Fase 1)
- [x] Na worktree: `python -m pytest scripts/claude_hooks/tests -q`
- [x] Confirmar: todos passam
- **Validado em:** 04/10/2026 — 200 testes passam (formas de push forçado em
  Bash e PowerShell, nomes alternativos do Railway, comandos normais que não
  podem ser travados, scripts em disco, entrada inválida → código 2)

### Cenário A1 — Push forçado escrito de outra forma é recusado (Fase 2)
- [x] Abrir uma sessão do Claude Code **dentro da worktree** (o hook só existe aí até ao merge)
- [x] Pedir: corre `git -C . push --force --dry-run origin HEAD:refs/heads/teste-inexistente`
- [x] Confirmar: o comando é recusado, com a mensagem do verificador ("Barreira dura do projeto: push forçado…")
- **Validado em:** 04/10/2026 — sessão sem ecrã (`claude -p`, CLI 2.1.288, modo auto) aberta na worktree; o comando não chegou a correr e o resultado foi a mensagem do verificador

### Cenário A2 — Nome alternativo do Railway é recusado (Fase 2)
- [x] Na mesma sessão, pedir: corre `railway volumes delete --help`
- [x] Confirmar: recusado pelo verificador (a regra antiga não apanhava `volumes`)
- **Validado em:** 04/10/2026 — mesma sessão; recusado com "Barreira dura do projeto: comandos do Railway que apagam ou desligam coisas…"

### Cenário A3 — Ação sensível pergunta; sem ecrã é recusada (Fase 2)
- [x] Sessão interativa: pedir `railway vars --help` → aparece o pedido de confirmação
- [x] Sessão sem ecrã (`claude -p`, a partir da worktree): o mesmo pedido termina sem executar o comando
- **Validado em:** 04/10/2026 — sessão interativa: o utilizador viu a caixa de confirmação com a mensagem do verificador antes de o comando correr, aprovou, e o comando mostrou a ajuda normal; sessão sem ecrã: o Claude Code registou a recusa com origem no hook (`decision_reason_type: hook`) e a mensagem "Ação sensível no Railway… precisa de confirmação do utilizador"; o comando não correu

### Cenário A4 — Não atrapalha o trabalho normal (Fase 2)
- [x] Na sessão da worktree: `git status`, `railway status` e `python -m pytest scripts/claude_hooks/tests -q` correm sem pergunta nova
- [x] Um commit cuja mensagem cita "git push --force" é feito sem pergunta nova
- **Validado em:** 04/10/2026 — na sessão sem ecrã (onde uma pergunta seria uma recusa) os três comandos correram (200 testes a passar) e `git commit --dry-run --allow-empty -m "docs: git push --force é recusado"` passou pelo verificador; o git respondeu "nothing to commit", como esperado num ensaio

### Cenário G1 — O GitHub recusa push forçado na `main` (Fase 3)
- [x] Ler as regras ativas na branch: `gh api repos/danielfranca47/crm-auto-digital/rules/branches/main`
- [x] Confirmar: aparece a regra `non_fast_forward`, vinda do ruleset `24438757`
- **Validado em:** 04/10/2026 — a resposta foi `{"ruleset_id":24438757,"type":"non_fast_forward"}` e o ruleset está `active`. Não foi tentado um push forçado real.

### Cenário T2 — Barreiras adicionais do Railway (Fase 4)
- [x] Na worktree: `python -m pytest scripts/claude_hooks/tests -q`
- [x] Confirmar: todos passam, incluindo os casos de `service delete`, `shell` e `connect`
- **Validado em:** 04/10/2026 — 211 testes passam

---

## Fase 4 — Barreiras adicionais do Railway (04/10/2026)

### Necessidade identificada

O diagnóstico encontrou ações do Railway do mesmo tipo das barreiras, mas fora
da lista aprovada. O utilizador decidiu incluir três: recusar
`railway service delete` e perguntar em `railway shell` e `railway connect`.

### Alteração

| Arquivo | Mudança |
|---|---|
| `scripts/claude_hooks/verificar_comando.py` | `service` junta-se a `environment` e `project` (apagar → recusar); `shell` e `connect` juntam-se às ações que perguntam |
| `scripts/claude_hooks/tests/test_verificar_comando.py` | 11 casos novos |
| `.claude/settings.json` | regras `deny` para `railway service delete` e `ask` para `railway shell` / `railway connect`, em `Bash` e `PowerShell` |
| `docs/ops/local-dev.md` | listas de barreiras atualizadas |

`railway service files delete` também é recusado: a regra apanha qualquer
`delete` / `rm` / `remove` dentro de `railway service`, tal como já acontece
com os volumes.

### Commits Fase 4

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `27518fb` | barreiras para apagar serviço, `shell` e `connect` |

### Relatório da Fase 4 — o que mudou na prática

**Antes:** apagar um serviço do Railway, ou abrir uma shell com as variáveis de produção, só dependia do revisor automático.
**Agora:** apagar um serviço é recusado sempre; `railway shell` e `railway connect` pedem confirmação (em sessão sem ecrã, são recusados).
**Para validar:** Cenário T2, acima (já validado — é automático).

---

## Ajustes Possíveis Pós-Implementação

- **Não é uma garantia absoluta.** Um verificador de texto não apanha
  ofuscação deliberada (script que gera outro script, comando montado letra a
  letra, atalho de git gravado na configuração do repositório). Para o push
  forçado na `main`, a garantia que não depende do texto é a regra do GitHub
  (Fase 3); para o Railway não existe equivalente.
- **A regra do GitHub só cobre push forçado.** Apagar a branch `main` no
  remoto não é travado por ela; o GitHub tem uma regra própria para isso
  ("Restrict deletions"), que não foi pedida.
- **Ações do Railway parecidas que continuam de fora:** `railway redeploy` /
  `restart`, `railway volume files rename`, apagar domínios ou buckets.
- **Apagar uma branch remota** (`git push origin :main`, `git push --delete`)
  não é barreira hoje e continua a não ser.
- **Pergunta a mais em casos raros:** `git push -u origin "$RAMO" && rm -f tmp`
  pergunta, porque o push tem uma parte só conhecida ao executar e há um `-f`
  na mesma linha. Em sessão sem ecrã isso é uma recusa; basta separar os dois
  comandos.
- **Scripts:** só são lidos os ficheiros até 512 KB chamados diretamente pelo
  comando; um script que chama outro script noutra pasta pode não ser seguido.
