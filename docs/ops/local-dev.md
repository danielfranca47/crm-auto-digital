# Setup e Desenvolvimento Local

## `.env.local` nunca deve ser commitado (backend-crm)

`backend-crm/app.py` faz `load_dotenv(".env", ...)` seguido de
`load_dotenv(".env.local", override=True)`. Qualquer variável definida em
`.env.local` **sobrepõe** o que estiver no ambiente real do processo — incluindo
variáveis injectadas pelo Railway em produção. Se este ficheiro for commitado no
git, ele é incluído no build/deploy e passa a sobrepor silenciosamente a
configuração de produção, sem que apareça nenhum erro nas variáveis do Railway
(elas continuam a mostrar o valor "correcto" no dashboard — só o processo em
runtime é que usa outro valor).

`.env.local` está no `.gitignore`. Usar este ficheiro só para overrides pessoais
de desenvolvimento local (ex.: apontar para serviços locais em portas
diferentes) — nunca para valores que possam acabar commitados.

---

## Worktree nova precisa de `.env` copiado manualmente antes de testar backend

`EnterWorktree` cria a worktree a partir de `origin/<branch base>`, mas `.env`
é gitignored nos três backends (`backend-core`, `backend-crm`,
`backend-executors`) — por isso não é copiado automaticamente. A worktree
nasce só com `.env.example`. Sem o `.env` real, testes de `tests/` que
dependem de configuração (tokens, URLs de serviço) falham logo na primeira
execução — não por bug de produto, mas por falta desse passo manual.

**Antes de rodar `pytest` numa worktree nova**, copiar o `.env` real da pasta
principal (`C:\crm-auto-digital\<backend>\.env`) para o mesmo caminho dentro
da worktree, para cada backend cujos testes forem rodar.

`.venv` também não é herdado, pelo mesmo motivo (cada `venv`/`.venv` tem seu
próprio `.gitignore` interno com `*`, então o git nunca o rastreia, nem em
worktrees). Duas opções: usar o Python global do sistema se os pacotes já
estiverem instalados nele, ou criar um `.venv` novo na worktree com
`pip install -r requirements.txt` — neste segundo caso, atenção a possíveis
diferenças de versão de pacote em relação ao `.venv` da pasta principal.

**Sintoma a reconhecer:** se os testes falham por erro de configuração/conexão
(não por asserção de lógica de negócio) logo na primeira execução numa
worktree recém-criada, o passo acima provavelmente foi esquecido.

---

## Correr os testes do backend-crm

A partir da pasta `backend-crm`:

```bash
python -m pytest tests/ -q
```

**Resultado esperado:** tudo aprovado, zero falhados. Uma falha é sempre algo
a investigar — não há falhas "conhecidas" que se possam ignorar. Nada corre
estes testes fora da máquina local (os workflows do GitHub só fazem deploy
dos frontends), por isso convém corrê-los antes de mergear uma implementação
que toque no `backend-crm`.

Cada ficheiro tem também de passar sozinho
(`python -m pytest tests/test_<nome>.py -q`) — o resultado não pode depender
de que outros testes correram antes.

`pytest` não está em `requirements.txt`; tem de estar instalado no Python
usado para correr a suíte.

### Regras ao escrever ou alterar testes

- **Usar o `fastapi`, `pydantic` e `httpx` verdadeiros.** Nunca instalar uma
  versão de faz-de-conta em `sys.modules`: ela só entra quando o pacote
  verdadeiro ainda não foi importado, o que faz o teste comportar-se de uma
  forma sozinho e de outra na suíte inteira, e deixa de funcionar assim que o
  código de produção importa mais um nome do pacote.
- **Módulo carregado com `importlib.util.spec_from_file_location` é registado
  em `sys.modules` com um nome único antes de `exec_module`**
  (`sys.modules[spec.name] = modulo`). Sem isso, modelos `pydantic` definidos
  num ficheiro com `from __future__ import annotations` falham com
  "is not fully defined". O nome único mantém uma cópia privada, para que
  funções substituídas num teste não afetem os outros.
- **Rotas fecham a ligação ao banco que recebem.** Para verificar o resultado
  depois de chamar uma rota, usar banco em ficheiro temporário e abrir uma
  ligação separada — não reutilizar a ligação entregue à rota, nem `:memory:`.
- **No Windows, um `.db` aberto não pode ser apagado.** Fechar as ligações que
  o teste abre (`contextlib.closing(get_connection())` — o `with` do `sqlite3`
  só faz commit, não fecha) e criar a pasta temporária com
  `tempfile.TemporaryDirectory(ignore_cleanup_errors=True)`.
- **Chamadas ao backend-core e criação de jobs são substituídas no teste**
  (`unittest.mock.patch`), para o teste não depender de rede nem escrever no
  banco real.
- **Tabelas criadas à mão no teste têm de acompanhar o esquema real.** Quando
  o código passa a ler ou gravar uma coluna nova, os testes que montam essa
  tabela à mão precisam da mesma coluna.

---

## Comandos slash (`.claude/commands/`)

Os comandos slash do projeto estão versionados em `.claude/commands/` e chegam a qualquer máquina
ou sessão que clone o repositório. O ficheiro de cada comando é a única fonte do texto — esta tabela
só diz para que serve cada um.

| Comando | Para que serve | Ficheiro |
|---|---|---|
| `/statusdev` | panorama de `docs/implementations/` | [`.claude/commands/statusdev.md`](../../.claude/commands/statusdev.md) |
| `/statusplans` | inventário de `docs/plans/` (passo 1 de 3) | [`.claude/commands/statusplans.md`](../../.claude/commands/statusplans.md) |
| `/statusplans-verificar` | auditoria e obsolescência (passo 2 de 3) | [`.claude/commands/statusplans-verificar.md`](../../.claude/commands/statusplans-verificar.md) |
| `/statusplans-avancar` | limpeza + geração do sprint + arquivos "Aguardando Plan Mode" (passo 3 de 3) | [`.claude/commands/statusplans-avancar.md`](../../.claude/commands/statusplans-avancar.md) |
| `/discovery-status` | painel de `docs/discovery/` (só leitura) | [`.claude/commands/discovery-status.md`](../../.claude/commands/discovery-status.md) |
| `/discovery-levantar` | levantamento → investigações (passo 1 de 3) | [`.claude/commands/discovery-levantar.md`](../../.claude/commands/discovery-levantar.md) |
| `/discovery-aprofundar` | investigação completa de um tema (passo 2 de 3) | [`.claude/commands/discovery-aprofundar.md`](../../.claude/commands/discovery-aprofundar.md) |
| `/discovery-decidir` | aplica os vereditos (passo 3 de 3) | [`.claude/commands/discovery-decidir.md`](../../.claude/commands/discovery-decidir.md) |
| `/fila-validar` | turno do dia da fila automática | [`.claude/commands/fila-validar.md`](../../.claude/commands/fila-validar.md) |

Ao criar um comando novo, acrescentar uma linha a esta tabela.

---

## Modo auto e regras de permissão do Claude Code

O Claude Code trabalha neste projeto em **modo auto**: em vez de pedir um clique
de permissão a cada comando, um segundo modelo (o "revisor automático") avalia
cada ação antes de ela correr e bloqueia o que for perigoso. A configuração vive
em dois sítios — um versionado, outro não.

### No repositório (versionado) — `.claude/settings.json`

Vale em qualquer modo de permissão e em todas as worktrees:

- **`deny` — nunca corre, nem com pedido explícito:** `git push` forçado
  (`--force`, `-f`), e no Railway tudo o que apaga ou desliga coisas — apagar ou
  desanexar um volume, apagar ficheiros dentro de um volume (é onde ficam as
  bases de dados e os backups), `railway down`, `railway delete`,
  `railway environment delete`, `railway service delete`. E todas as
  ferramentas do servidor `github` (`mcp__github`): as sessões da cloud trazem
  ferramentas que juntam pull requests e escrevem ficheiros numa branch sem
  passar pela linha de comandos, fora do alcance do verificador de comandos.
  No PC esse servidor não existe — o GitHub usa-se pela CLI `gh`.
- **`ask` — pergunta sempre, mesmo em modo auto:** `railway variable*` (ler
  expõe segredos; alterar dispara redeploy), `railway run`, `railway shell` e
  `railway connect` (abrem uma shell com as variáveis de produção, ou na base
  de dados), `railway ssh`, `railway up`, e enviar ficheiros para um volume
  (`railway volume files upload`).
- **`allow` — corre sem passar pelo revisor.** Lista curta e fechada, só com
  três grupos:
  - **Testes automáticos:** `pytest`, `unittest` e `npx tsc --noEmit`, nas
    formas `python -m …` e `.venv/Scripts/python.exe -m …`, para `Bash` e
    `PowerShell`.
  - **Browser, na página já aberta** (servidores `chrome-devtools` do plugin e
    `chrome-devtools-manual`): olhar (`take_snapshot`, `take_screenshot`,
    `list_pages`, `select_page`, `wait_for`, pedidos de rede e mensagens da
    consola) e interagir (`click`, `hover`, `fill`, `fill_form`, `type_text`,
    `press_key`, `handle_dialog`, `resize_page`, `emulate`).
  - **Desktop, só olhar:** `screenshot`, `screenshot_window`, `list_windows`,
    `cursor_position` do `desktop-control`.

O que **não** entra em `allow`, nem com um clique em "permitir sempre":

- **Qualquer comando que não seja teste** — `git add`/`commit`/`push`, `curl`,
  `npm install`/`run`, término de processos. É o revisor que impede um segredo
  de entrar num commit deste repositório público; uma regra `allow` tira-lhe
  essa oportunidade. Regras com coringa enganam: `curl -s http://localhost:*`
  aceita um segundo endereço externo a seguir ao primeiro.
- **Intérprete com código livre** (`python -c ' *`, `python -`, `node -e`,
  `powershell -Command ' *`) — conteúdo malicioso lido de uma página ou ficheiro
  poderia ser executado sem revisão.
- **Ferramentas de browser que abrem um endereço ou executam código**
  (`navigate_page`, `new_page`, `evaluate_script`, `upload_file`) e clique ou
  teclado ao nível do desktop.
- **Regras de leitura** (`ls`, `grep`, `git status`, …) — em modo auto os
  comandos só de leitura já correm sem revisor e sem clique, por isso a regra
  não acrescenta nada. Pelo mesmo motivo, não usar a skill
  `fewer-permission-prompts` neste projeto.
- **Um comando inteiro com senha, token ou chave** — a regra guarda o texto do
  comando tal como foi escrito, em texto simples.

`git push` normal não leva pergunta: faz parte do fluxo de graduação (ver
`CLAUDE.md`, "Estratégia de branch por implementação").

Estas regras comparam o texto do comando com um padrão, por isso só apanham a
forma habitual de o escrever. As outras formas ficam a cargo do verificador,
abaixo.

#### Verificador de comandos — `scripts/claude_hooks/verificar_comando.py`

Segunda camada das barreiras `deny` e `ask`. Está ligado no bloco `hooks` de
`.claude/settings.json` (evento `PreToolUse`, ferramentas `Bash` e
`PowerShell`): corre antes de cada comando de shell, lê a estrutura do comando
em vez de comparar o início do texto, e aplica a mesma lista de barreiras:

- **Recusa** push forçado (`--force`, `-f`, `--force-with-lease`, `--mirror`,
  destino a começar por `+`) e, no Railway, `down`, `delete`, apagar um
  ambiente, um serviço ou o projeto, apagar ou desanexar um volume, apagar
  ficheiros de um volume.
- **Pergunta** em `railway variable`, `run`, `shell`, `connect`, `ssh`, `up` e
  `volume files upload`.
- **Não diz nada** no resto — o comando segue para as regras acima e para o
  revisor automático. O verificador nunca aprova um comando.

Formas que cobre e que as regras não apanham:

- nomes alternativos do Railway: `rm` / `remove`, `project delete`, `volumes`,
  `env`, `vars` / `var`, `local`
- opções antes do subcomando: `git -C . push -f`, `railway -s <serviço> volume delete`
- outro nome do executável: `git.exe`, caminho completo, aspas, `npx @railway/cli`
- invólucros: `env`, `timeout`, `sudo`, `xargs`, `find -exec`, `git submodule foreach`
- shell dentro de shell: `bash -c`, `cmd /c`, `powershell -Command`,
  `-EncodedCommand`, `eval`, `Invoke-Expression`, `Start-Process`
- scripts chamados pelo comando (`.sh`, `.ps1`, `.bat`, `.cmd`, `npm run`): o
  ficheiro é lido e analisado como comandos; em código (`.py`, `.js`,
  `python -c`) as mesmas ações são procuradas no texto e, se aparecerem,
  pergunta
- formas que não dá para ler (variável no lugar do programa ou da opção,
  `| bash`, aspas por fechar): pergunta quando o texto aparenta uma das ações

Texto que é dado e não comando não conta: mensagem de `git commit -m`, heredoc
lido por `cat`, argumento de `grep` ou `echo`, e o destino de um
redirecionamento de saída (`> ficheiro`, `2>&1`).

**Só em sessões da cloud** (variável `CLAUDE_CODE_REMOTE=true` — a rotina do
turno da noite da [fila automática](fila-automatica.md)) recusa também:

- qualquer `git push` que não seja para uma branch `claude/…` escrita por
  extenso no comando: push para `main` ou outra branch, push sem destino
  (`git push`, `git push origin` — aí quem decide é a configuração do git),
  `--all`, `--delete`, `:branch`, e destino só conhecido ao executar;
  `git push origin HEAD` só passa se a branch atual for `claude/…`
- os comandos `gh` que alteram o repositório no GitHub: `gh pr merge`,
  `gh api` de escrita (método que não seja GET, ou campos sem método),
  `gh workflow run`, `gh secret` / `variable set`, `gh repo edit`,
  `gh release create`
- formas que não dá para ler com um `git … push` ou um `gh … merge|api` no
  texto: nas sessões da cloud não há quem responda a uma pergunta, por isso a
  dúvida é uma recusa

Numa sessão local estas três regras não existem — o fluxo de graduação
continua a fazer `git push origin main` como sempre.

Limites — o que é preciso saber:

- **Não é uma garantia absoluta.** Não apanha ofuscação deliberada (script que
  gera outro script, comando montado letra a letra, atalho de git gravado na
  configuração do repositório). O revisor automático continua a ser a camada
  seguinte.
- **Se o verificador não arrancar, o comando segue.** Sem `python` no PATH, ou
  se o script passar do tempo limite (10 s), o Claude Code trata o hook como
  "sem decisão". É por isso que as regras `deny`/`ask` acima se mantêm: valem
  mesmo com o verificador partido, e nenhum hook as consegue anular. Um erro
  dentro do script, pelo contrário, bloqueia o comando (código de saída 2).
- **Dispositivo novo:** confirmar que `python --version` responde na shell.
- **Alterar a lista de barreiras** exige mexer nos dois sítios: as regras em
  `.claude/settings.json` e as tabelas no topo do script. Os testes correm com
  `python -m pytest scripts/claude_hooks/tests -q` e só passam texto ao script
  — nenhum comando real é executado.
- **Pergunta a mais em casos raros.** Um `git push` com uma variável nos
  argumentos, na mesma linha de outro comando com `-f`, pergunta. Separar os
  dois comandos resolve.

#### Do lado do GitHub — push forçado na `main`

O repositório `danielfranca47/crm-auto-digital` tem um ruleset ativo,
**`main - sem push forcado`** (GitHub → Settings → Rules → Rulesets), com uma
única regra: recusar push forçado na branch por omissão. Não tem exceções, por
isso vale também para o dono do repositório, e não depende do Claude Code nem
da forma do comando. Push normal e as outras branches não são afetados.

- Conferir: `gh api repos/danielfranca47/crm-auto-digital/rules/branches/main`
  deve listar `non_fast_forward`.
- Só cobre push forçado; apagar a branch no remoto é outra regra do GitHub
  ("Restrict deletions"), que não está ligada.
- Não vive no repositório: num fork ou num repositório novo tem de ser criada
  de novo.

### Na máquina (não versionado) — `~/.claude/settings.json`

O Claude Code não lê a configuração do revisor a partir do repositório, só das
definições pessoais. Num dispositivo novo, acrescentar a `~/.claude/settings.json`:

```json
{
  "permissions": {
    "defaultMode": "auto"
  },
  "autoMode": {
    "environment": [
      "$defaults",
      "Organization: Daniel França, solo founder. Primary use of Claude Code: software development of the crm-auto-digital SaaS (CRM with WhatsApp sales automation) and a few smaller personal projects.",
      "Source control: github.com/danielfranca47. Repository visibility: the crm-auto-digital repository is PUBLIC. Secrets, .env contents, customer data, production database files or their backups must never enter a commit, a push, or PR/issue text.",
      "CI/CD deploy targets: pushing to the main branch of crm-auto-digital automatically deploys to production (Railway redeploys the backends; GitHub Actions deploy the frontends to Cloudflare). The user knows this and treats a normal, non-forced push to main as routine: it is the last step of the project's documented graduation flow (merge the feature branch into main, then push).",
      "Key internal services: the Railway project linked to the crm-auto-digital folder, environment 'production' (services backend-core, backend-crm, backend-executors and its worker). Read-only Railway CLI commands are routine: status, logs, deployment list, volume list, volume files list/download.",
      "Sensitive remote targets: the same Railway production environment. Commands that change it (variable set, up, redeploy, run, ssh, volume files upload/rename, anything that deletes or detaches a volume) need the user to have asked for that specific change.",
      "Trusted internal domains: api.danielfranca.pt and the local development servers on localhost ports 8000, 8001, 8002, 8010, 8080, 5173 and 5174.",
      "Sensitive data locations & audiences: the .env files inside backend-core, backend-crm, backend-executors and agent-local hold real API keys and payment-provider credentials; the production SQLite databases (core.db, crm.db) and any backup or downloaded copy of them hold customer personal data. Audience: the user only, on this machine. Never copy them into the repository working tree or send them to any external service."
    ]
  }
}
```

Pontos a saber:

- **`permissions.allow` pessoal fica vazia.** As definições pessoais valem em
  todos os projetos, por isso uma regra ali salta o revisor em todo o lado. O
  que faz sentido manter está na lista do projeto, acima.
- **`autoMode.classifyAllShell` fica desligado.** Ligado, obriga todos os
  comandos de shell a passar pelo revisor e anula as regras de teste da lista
  `allow` do projeto. Só ligar se essas regras forem retiradas.
- **Quem aplica é o utilizador, não o Claude.** O revisor automático recusa que
  o Claude altere as próprias regras de permissão (motivo `[Self-Modification]`)
  — é o comportamento esperado e não deve ser contornado.
- **VS Code:** a extensão lembra-se do último modo escolhido. Clicar uma vez no
  indicador de modo, por baixo da caixa de texto, e escolher **Auto**.
- **Terminal:** exige a CLI na versão 2.1.283 ou superior
  (`npm i -g @anthropic-ai/claude-code@latest`); em versões antigas a sessão
  arranca em modo manual, clique a clique.
- **As regras são lidas no arranque da sessão, da pasta onde ela foi aberta.**
  Uma alteração a `.claude/settings.json` só vale em conversas novas, e uma
  regra que ainda só existe numa worktree não vale numa conversa aberta na pasta
  principal.
- **Sessões sem ecrã (`claude -p`):** uma regra `ask`, ou um "perguntar" do
  verificador de comandos, conta como recusa, porque
  não há quem responda ao pedido. Numa pasta que nunca foi aberta de forma
  interativa, as regras `allow` do projeto são ignoradas ("this workspace has
  not been trusted"); as `deny` e `ask` valem na mesma e o revisor automático
  decide o resto.
- **Conferir o que está ativo:** `claude auto-mode config` imprime as regras que
  o revisor está realmente a usar.
- **Ver o que foi bloqueado:** `/permissions`, separador "Recently denied". Se o
  mesmo destino legítimo for bloqueado repetidamente, acrescentar uma linha a
  `autoMode.environment` em vez de criar regras `allow`.

---

## Pré-requisitos

- Python 3.11+ com `venv` por serviço
- para instalar o ambiente virtual roda python -m venv venv
- Node.js + npm para os frontends
- SQLite (incluído no Python)

---

## Subir todos os serviços

### Backend-core (porta 8001)

```powershell
cd backend-core
code -n .
.\.venv\Scripts\activate
python -m uvicorn app.main:app --reload --port 8001
```

### Backend-crm (porta 8000)

> Depende do backend-core estar rodando primeiro.

```powershell
cd backend-crm
code -n .
.\.venv\Scripts\activate
uvicorn app:app --reload --port 8000
```

### Backend-executors (porta 8010)

Em um terminal:
```powershell
cd backend-executors
code -n .
.\.venv\Scripts\activate
uvicorn app.main:app --reload --port 8010 --app-dir .
```

Em outro terminal (worker de processamento de jobs):
```powershell
cd backend-executors
code -n .
.\.venv\Scripts\activate
python -m app.workers.whatsapp_worker
```

> Para execução de jobs, garantir que o usuário tenha uma instância WhatsApp conectada.

Em outro terminal (worker de envio de email de prospecção — cold outreach):
```powershell
cd backend-executors
code -n .
.\.venv\Scripts\activate
python -m app.workers.email_worker
```

> Para execução de jobs, garantir que o usuário tenha conectado uma conta SMTP em
> `PUT /users/me/smtp` (backend-core).

### Agent-local

Confirmar `.env` com:
```
BACKEND_URL=http://localhost:8000
AGENT_ID=...
AGENT_TOKEN=...
JOB_TYPES=whatsapp_send,maps_search_fallback,maps_enrich_fallback
```

```powershell
cd agent-local
code -n .
.\.venv\Scripts\activate
python main.py
```

### Frontend-crm (porta 8080)

```powershell
cd frontend-crm
code -n .
npm install
npm run dev -- --port 8080
```

---

## Ordem recomendada de inicialização

1. backend-core (8001)
2. backend-crm (8000)
3. backend-executors — servidor (8010) + worker
4. agent-local (se precisar de prospecção local)
5. frontend-crm (8080)
