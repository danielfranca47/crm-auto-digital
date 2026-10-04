# Fila automática — turno da noite (rotina na cloud)

**Branch:** `worktree-feat+fila-turno-da-noite` (worktree `.claude/worktrees/feat+fila-turno-da-noite`)
**Status:** Em andamento — Fases 1 a 4 implementadas; por validar: N2 (recusa do push para `main` na cloud) e N4 (consumo); Fase 5 (ligar o horário) por fazer
**Autonomia:** manual
**Origem:** Fase 2 do plano aprovado em 04/10/2026 (contrato: `docs/ops/fila-automatica.md`)

---

## Motivação

As regras da fila automática já estão escritas em
[`docs/ops/fila-automatica.md`](../ops/fila-automatica.md), mas nada corre
sozinho: a fila continua parada até o utilizador dar o "start".

Comportamento desejado: todas as noites, com o PC do utilizador desligado, uma
rotina na cloud pega **um** item elegível, segue a secção "Turno da noite" e
deixa o resultado numa branch `claude/<slug>` — nunca em `main`.

---

## Problemas Identificados (estado anterior)

Diagnóstico de 04/10/2026, contra a documentação oficial do Claude Code
(rotinas, sessões na cloud, ambientes da cloud) e o estado da conta.

1. **Não existe nenhuma rotina para este repositório.** A conta tem uma única
   rotina, local e de outro projeto. Nenhuma branch `claude/*` no remoto.
2. **A cloud não impede um push para `main`.** O briefing de 03/10 assumia que
   a rotina só conseguia escrever em `claude/*`. A documentação diz o
   contrário: a sessão empurra para `claude/` por omissão, mas o intermediário
   do GitHub "não limita que branches um push pode atualizar". "A noite nunca
   chega a `main`" era só uma frase — e push em `main` é deploy.
3. **Uma rotina leva, por omissão, todos os conectores da conta** (Drive,
   Canva, Docs…) e pode usá-los sem perguntar.
4. **O limite de uso pode cortar a sessão sem aviso.** O estado "Interrompido
   de noite" só era escrito quando a sessão dava por isso — num corte seco
   nunca chegava a ser.
5. **O procedimento não dizia como instalar dependências.** O clone da cloud
   traz Python, `pip`, `pytest`, Node e `npm`, mas não os pacotes do projeto.
6. **Dois itens em curso noutras worktrees apareciam em `main` como
   elegíveis** (`fix-disponibilidade-campo-duplo-sentido`,
   `otimizar-imagem-hero-lara-desktop`): a noite pegá-los-ia em duplicado.
7. **Por verificar na cloud:** se `python` existe (o verificador é chamado
   assim; se só houver `python3`, fica mudo), que ferramentas de GitHub a
   sessão tem além da linha de comandos, e quem aparece como autor de um push.

O que já estava bem: o plano Pro inclui rotinas na cloud, sem custo à parte
(gastam o limite de uso normal); o `CLAUDE.md` e o `.claude/settings.json` do
repositório valem na cloud; PyPI e npm estão acessíveis por omissão; não há
`.env`, Railway nem browser.

---

## Abordagem

Nenhum serviço novo. Três peças:

```
rotina na cloud (sem conectores, texto fino)
  └─ "lê docs/ops/fila-automatica.md, secção Turno da noite, e executa"
       ├─ regras e passos: moram no repositório
       └─ barreira por código: verificador de comandos, só em sessões da cloud
            git push  → só para claude/… escrita por extenso   → senão RECUSA
            gh        → nada que altere o repositório           → senão RECUSA
```

Decisões tomadas:

- **A barreira do push fica no verificador que já existe**
  (`scripts/claude_hooks/verificar_comando.py`), ativada pela variável
  `CLAUDE_CODE_REMOTE=true` que a cloud define. Em sessões locais nada muda —
  a graduação continua a fazer `git push origin main`.
- **Push sem destino é recusado na cloud.** `git push` e `git push origin`
  dependem da configuração do git, que a própria sessão pode alterar; só passa
  um destino `claude/…` escrito no comando.
- **Na cloud, a dúvida é uma recusa.** Não há ninguém para responder a uma
  pergunta.
- **Dependências instaladas pela própria sessão**, como passo do
  procedimento. Sem script de ambiente nem hook de arranque: menos uma peça
  fora do repositório.
- **Estado "Interrompido" escrito no primeiro commit** e trocado só no fim,
  com push a cada commit — um corte seco deixa sempre o item reconhecível.
- **Descartado: regra do GitHub a exigir pull request para `main`** — já
  estava descartado no contrato (quem faz o merge é a sessão local do
  avaliador). Uma regra que distinga a cloud do PC só é possível se o GitHub
  vir a cloud como uma aplicação diferente do utilizador — a verificar na
  Fase 2.

Desvio do plano aprovado: a sonda vinha primeiro. `claude --cloud` exige um
terminal interativo e não pôde ser lançado pela sessão; a barreira e o
procedimento, que não dependem da sonda, passaram a Fase 1.

---

## Plano de Implementação

### Fase 1 — Barreira do push e procedimento

**Objetivo:** fechar por código o caminho da cloud para `main` e completar o
procedimento da noite. Nada corre sozinho ainda.

| Arquivo | O que muda |
|---|---|
| `scripts/claude_hooks/verificar_comando.py` | regras das sessões da cloud: `_git_cloud` (push só para `claude/…`), `_gh_cloud` (sem escrita no repositório), `_ramo_atual`, e a recusa nas formas ilegíveis |
| `scripts/claude_hooks/tests/test_verificar_comando.py` | 65 casos novos |
| `docs/ops/fila-automatica.md` | "Turno da noite": a barreira, estado "Interrompido" desde o 1.º commit, push a cada commit, instalar dependências, rotina sem conectores |
| `docs/ops/local-dev.md` | "Verificador de comandos": as regras das sessões da cloud |
| `docs/implementations/fix-disponibilidade-campo-duplo-sentido.md`, `otimizar-imagem-hero-lara-desktop.md` | `**Autonomia:** manual` |
| `docs/plans/fila-automatica-melhorias-futuras.md` | M3: confirmado que um push só de documentação cria um deploy |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `032edf5` | barreira do push na cloud + procedimento da noite |

**Detalhes do commit `032edf5`:**
- `scripts/claude_hooks/verificar_comando.py` — `_git_cloud` (lê o destino de cada `git push`; só passa `claude/…` escrito no comando), `_ramo_atual` (branch atual lida de `.git/HEAD`, para `git push origin HEAD`), `_gh_cloud` e `_gh_api_escreve` (comandos `gh` que alteram o repositório), `_procura_solta_cloud` (as mesmas regras em código que não é shell); `_Analise` recebe `cloud` e `main` lê `CLAUDE_CODE_REMOTE`
- `scripts/claude_hooks/tests/test_verificar_comando.py` — tabelas `CLOUD_RECUSA` e `CLOUD_LIVRES`, branch atual em pasta temporária (repositório normal e worktree), e o contrato do hook com e sem a variável da cloud

### Relatório da Fase 1 — o que mudou na prática

**Antes:** nada impedia uma sessão na cloud de enviar código para `main` (e
portanto para produção) — só a regra escrita.
**Agora:** numa sessão da cloud, o verificador recusa qualquer envio que não
seja para uma branch `claude/…`, e recusa juntar código pelo GitHub. No teu PC
nada mudou. O procedimento da noite passou a dizer como instalar as
dependências e a marcar o item como "interrompido" logo no início, para que um
corte a meio nunca passe despercebido. **Ainda nada corre sozinho.**
**Para validar:** Cenários T1 e T2 (automáticos, já validados).

### Fase 2 — Sonda na cloud (só leitura)

**Objetivo:** confirmar na cloud o que só lá se vê, antes de criar a rotina.
Uma sessão única, sem commits nem pushes reais, com o texto de
`## Texto da sonda`, abaixo.

Feita em 04/10/2026 com o "sim" do utilizador: a rotina "Fila automática —
turno da noite" (`trig_01H55ZGUhNCdAcHqzkri2djD`,
https://claude.ai/code/routines/trig_01H55ZGUhNCdAcHqzkri2djD) foi criada sem
conectores e usada para três sondas de leitura. A API não aceita uma rotina
"sem horário": foi criada com um disparo único (a primeira sonda) e ficou
desligada depois dele; as outras duas foram disparos à mão. A API também
anexou por omissão os conectores da conta — retirados antes do primeiro
disparo.

O que as sondas obrigaram a mudar:

| Arquivo | O que muda |
|---|---|
| `.claude/settings.json` | regra `deny` para `mcp__github` — todas as ferramentas de GitHub que a cloud traz e que escrevem sem passar pela linha de comandos |
| `docs/ops/fila-automatica.md` | "Turno da noite": dependências e `pytest` instalados num ambiente virtual em `/tmp/venv` (o `pip` do sistema falha); as ferramentas `mcp__github__…` estão recusadas |
| `docs/ops/local-dev.md` | a regra `deny` nova |

Não foi preciso mexer na forma de chamar o verificador: `python` existe na
cloud e o verificador recusou o push forçado de ensaio.

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `1848093` | recusa das ferramentas de GitHub da cloud + instalação em ambiente virtual + resultados das sondas |

### Relatório da Fase 2 — o que mudou na prática

**Antes:** a barreira da Fase 1 só olhava para comandos de terminal. A cloud
tem, além disso, ferramentas próprias de GitHub que juntam pull requests e
escrevem ficheiros diretamente numa branch — incluindo `main`. E a noite não
conseguiria correr um único teste: nem as dependências nem o `pytest` se
instalavam.
**Agora:** essas ferramentas estão todas recusadas por regra; o procedimento
diz como instalar as dependências de forma que funciona (confirmado na cloud:
242 testes do backend-crm e a verificação do frontend passam).
**Falta um passo teu:** a cloud consegue ler o repositório (é público) mas
**não consegue escrever** — o GitHub recusa o push. É preciso instalar a
aplicação do Claude no repositório (Cenário N0).
**Para validar:** Cenário S1 (validado) e N0 (precisa de ti).

### Fase 3 — Ensaio: rotina sem horário + um disparo à mão

**Objetivo:** ver a noite inteira a funcionar uma vez, com o utilizador a
olhar.

- Criar a rotina "Fila automática — turno da noite" **só com o "sim" do
  utilizador no momento**: repositório `danielfranca47/crm-auto-digital`,
  ambiente por omissão, zero conectores, sem horário.
- As regras desta implementação ainda não estão em `main`: para o ensaio, a
  rotina aponta para esta branch (enviada para o GitHub só para isso).
- Item esperado: `fix-docs-campos-obrigatorios-qualificacao` (o único `fix-*`
  elegível; corrige três documentos).
- Medir o consumo do limite de uso antes e depois.

**Feito em 04/10/2026**, com o "sim" do utilizador (execução
`cse_01U7DJUnyute8d69DVr3eWQN`, 87 segundos, Sonnet 5.5, sem conectores). Não
tem commit próprio nesta branch: o que produziu está em
`origin/claude/fix-docs-campos-obrigatorios-qualificacao` (2 commits).

### Relatório da Fase 3 — o que o ensaio mostrou

**Correu bem:** a noite escolheu o item esperado, marcou-o como interrompido
no primeiro commit, corrigiu cinco documentos, deixou o trabalho numa branch
`claude/…` com o estado `Implementado de noite — por validar`, e avisou por si
que o item toca no `CLAUDE.md` (sobe para ti). `main` não mudou. A ferramenta
de GitHub da cloud foi recusada pela regra.
**Correu mal:** a barreira da Fase 1 recusou um push legítimo, escrito como
`git push -u origin claude/<slug> 2>&1 | tail -3` — a noite contornou com um
push simples. Corrigido na Fase 4.
**Ficou por provar:** a recusa de um push para `main` na cloud. O comando de
ensaio correu antes de a sessão mudar para esta branch, com o verificador de
`main` (sem a regra). O que ficou provado é o contrário: sem a regra, a cloud
consegue mesmo escrever em `main`.

### Fase 4 — Redirecionamentos lidos como destinos do push (04/10/2026)

#### Necessidade identificada

Quem lê o comando (`_Leitor.ler`) partia `2>&1` em dois e deixava o `2` e o
destino de um `>` como argumentos do comando. Para as regras antigas isso não
tinha efeito; para a regra do push na cloud, cada um desses bocados era lido
como uma branch de destino que não começa por `claude/` — e o push era
recusado.

#### Alteração

| Arquivo | Mudança |
|---|---|
| `scripts/claude_hooks/verificar_comando.py` | em `_Leitor.ler`, um redirecionamento de saída (`>`, `>>`, `2>`, `>&`, `&>`) deixa de gerar argumentos e `>&` / `&>` deixam de partir o comando em dois. O redirecionamento de entrada (`<`) fica como estava: `bash < script.sh` continua a ser lido |
| `scripts/claude_hooks/tests/test_verificar_comando.py` | 19 casos novos |

#### Commits Fase 4

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | *(hash a registar)* | redirecionamento de saída deixa de contar como argumento |

#### Relatório da Fase 4 — o que mudou na prática

**Antes:** na cloud, um envio para a branch certa era recusado se o comando
guardasse ou cortasse a saída (`2>&1 | tail`, `> ficheiro`), que é como o
Claude costuma escrevê-lo.
**Agora:** esses envios passam; um envio para `main` com os mesmos
acrescentos continua recusado. As barreiras de sempre (push forçado, Railway)
não mudaram.
**Para validar:** Cenário T1 (automático) e N2 (na cloud).

### Fase 5 — Ligar o horário

**Objetivo:** a noite passa a correr sozinha. Hora escolhida pelo utilizador
com a medida da Fase 3; rotina a apontar para `main` depois do merge; tabela
"Estado atual" de `docs/ops/fila-automatica.md` com "Turno da noite: Ligado".

---

## Texto da sonda

```text
Sonda só de leitura do ambiente da cloud para o repositório crm-auto-digital. Regras: não faças commits, não cries branches, não alteres ficheiros versionados, e não faças nenhum push real — só os dois `--dry-run` pedidos abaixo. Não uses conectores. Corre cada ponto exatamente como está e, no fim, responde com um relatório numerado, com a saída literal de cada comando (curta).

1. `command -v python; python --version; command -v python3; python3 --version; node --version; npm --version; python3 -m pytest --version`
2. `echo CLAUDE_CODE_REMOTE=$CLAUDE_CODE_REMOTE; echo CLAUDE_PROJECT_DIR=$CLAUDE_PROJECT_DIR; pwd; git branch --show-current; git remote -v`
3. Corre `git push --force --dry-run origin HEAD:refs/heads/teste-inexistente` e diz exatamente o que aconteceu: foi recusado antes de correr (por um hook? com que mensagem, palavra por palavra?) ou chegou a correr (com que saída)?
4. Corre `git push --dry-run origin HEAD:refs/heads/claude/sonda-teste` e reporta a saída.
5. Em `backend-crm`: `python3 -m pip install -r requirements.txt` (diz quanto demorou e se falhou) e depois `python3 -m pytest tests/ -q` — mostra as últimas 15 linhas.
6. Lista os nomes das ferramentas que tens disponíveis relacionadas com GitHub (embutidas ou MCP) e os conectores que vês (Drive, Canva, Docs, etc.) — só os nomes, sem as usar.
7. `find . -name ".env" -not -path "*/node_modules/*" | head` — existe algum `.env` no clone?
8. `gh auth status 2>&1 | head -5; gh api user --jq .login` — que identidade aparece?
```

---

## Checks de Validação

Prefixos: `T` = teste automático, `S` = sonda, `N` = noite na cloud, `D` =
decisão do utilizador.

### Cenário T1 — Bateria de testes do verificador (Fase 1)
- [x] Na worktree: `python -m pytest scripts/claude_hooks/tests -q`
- [x] Confirmar: todos passam, incluindo os casos das sessões da cloud
- **Validado em:** 04/10/2026 — 276 testes passam (211 anteriores + 65 novos:
  push para `main` e outras branches recusado, push sem destino recusado,
  apagar e `--all` recusados, `gh pr merge` e `gh api` de escrita recusados,
  push para `claude/…` e trabalho normal passam, e fora da cloud nada muda)
- **Revalidado em:** 04/10/2026, depois da Fase 4 — 295 testes passam (mais
  19: push com `2>&1 | tail`, `> ficheiro` e `&> ficheiro`)

### Cenário T2 — Os testes do backend-crm não dependem do `.env` (Fase 1)
- [x] Exportar `backend-crm` do repositório para uma pasta vazia (sem `.env`)
- [x] Nessa pasta: `python -m pytest tests/ -q`
- [x] Confirmar: tudo aprovado
- **Validado em:** 04/10/2026 — 242 testes passam numa cópia limpa sem `.env`
  (com os pacotes já instalados no Python da máquina; a instalação do zero é
  confirmada na sonda, ponto 5)

### Cenário S1 — Sonda na cloud (Fase 2)
- [x] Lançar a sessão da cloud com o texto de `## Texto da sonda`
- [x] Registar aqui as respostas aos 8 pontos
- [x] Confirmar: o ponto 3 é recusado pelo verificador (prova de que ele corre
      na cloud); o ponto 5 termina com os 242 testes aprovados; o ponto 7 não
      encontra nenhum `.env`
- **Validado em:** 04/10/2026 — em três execuções (a instalação só passou à
  terceira, com ambiente virtual)
- **Executado em:** 04/10/2026, 12:58 (Lisboa) — rotina
  `trig_01H55ZGUhNCdAcHqzkri2djD`, execução `cse_01J5526SvLVEYr3923bb9ffn`,
  55 segundos, modelo Sonnet 5.5, sem conectores. Resultados:

| Ponto | Resultado |
|---|---|
| 1. Ferramentas | `python` e `python3` existem (3.11.15); Node 22.22.0, npm 10.9.4. **`pytest` não está instalado**, ao contrário do que a documentação diz. |
| 2. Ambiente | `CLAUDE_CODE_REMOTE=true`; pasta `/home/user/crm-auto-digital`; branch `main`. |
| 3. Push forçado de ensaio | ✅ **Recusado pelo verificador antes de correr**, com a mensagem da barreira — o `.claude/settings.json` e o verificador valem na cloud. |
| 4. Push de ensaio para `claude/…` | ❌ Falhou com erro 403: "Claude doesn't have GitHub access to danielfranca47/crm-auto-digital". O clone funciona porque o repositório é público; **o push precisa de a aplicação do Claude estar instalada no repositório** (passo do utilizador). |
| 5. Dependências e testes | ❌ `pip install -r requirements.txt` falhou ao compilar o pacote `googlemaps`; sem `pytest`, os testes não correram. |
| 7. `.env` | ✅ Nenhum no clone. |
| 8. Identidade | `gh api user` responde `danielfranca47` — as chamadas ao GitHub aparecem como o utilizador. |

- **Segunda sonda** (execução `cse_014PJPcGv7ojbJGEj7UuUiNA`, 39 s) — causa
  da falha de instalação e ferramentas de GitHub:
  - `googlemaps` falha com `AttributeError: install_layout`: o `pip` do
    sistema (24.0, instalado pelo Debian, com `setuptools` 68.1.2) não se
    entende com o Python 3.11.15 da cloud. Atualizar `setuptools`/`wheel` não
    resolve (o sistema não deixa desinstalar os seus).
  - **A sessão tem ferramentas de GitHub que não passam pela linha de
    comandos:** `mcp__github__merge_pull_request`, `push_files`,
    `create_or_update_file`, `delete_file`, `create_branch`,
    `enable_pr_auto_merge`, `actions_run_trigger`, `create_pull_request`, e
    as de leitura. O verificador de comandos não as vê.
- **Terceira sonda** (execução `cse_01QHae3DwQGnzxL4pSccnANi`, 146 s) — a
  correção da instalação:
  - ambiente virtual em `/tmp/venv` + `pip install -r requirements.txt pytest`:
    ✅ 32 s; `pytest tests/ -q` no backend-crm: ✅ **242 passed**
  - `npm ci` no frontend-crm: ✅ 87 s; `npx tsc --noEmit`: ✅ sem erros
  - `git status` limpo no fim — a sonda não deixou nada no clone
- **Por validar no S1:** nada — o ponto 3 foi recusado pelo verificador, o
  ponto 5 passa com o ambiente virtual, o ponto 7 não encontrou `.env`. O que
  ficou por resolver (acesso de escrita ao repositório, ponto 4) passa para o
  Cenário N0.

### Cenário N0 — A cloud consegue escrever em `claude/…` (pré-requisito da Fase 3)
- [x] O utilizador instala a aplicação do Claude no GitHub para
      `danielfranca47/crm-auto-digital`
      (https://github.com/apps/claude/installations/select_target)
- [x] Numa sessão da cloud: `git push --dry-run origin HEAD:refs/heads/claude/sonda-teste`
- [x] Confirmar: deixa de dar o erro 403 "Claude doesn't have GitHub access"
- **Validado em:** 04/10/2026 — execução `cse_019trzxU7ujSGsbPRUyH6sDm` (13 s):
  o push de ensaio terminou com código 0 e
  `* [new branch] HEAD -> claude/sonda-teste`; o remoto continua só com
  `main` (o ensaio não cria nada). O primeiro push a sério acontece no
  Cenário N1.

### Cenário N1 — Uma noite inteira, disparada à mão (Fase 3)
- [x] Disparar a rotina à mão
- [x] Confirmar: existe `origin/claude/<slug>`; o `.md` do item diz
      `Implementado de noite — por validar` (ou `Só plano — precisa da tua
      decisão`); a secção `## Testes automáticos (turno da noite)` está
      preenchida; `main` não mudou
- **Validado em:** 04/10/2026 — existe
  `origin/claude/fix-docs-campos-obrigatorios-qualificacao` (commits `0387450`
  e `4424527`); estado `Implementado de noite — por validar`; a secção de
  testes diz "alteração só de documentação: não corri testes de código";
  `origin/main` continua em `db1e175`. A instalação e os testes em si foram
  vistos a funcionar na terceira sonda (S1), não nesta execução.

### Cenário N2 — A barreira funciona na cloud (Fase 3)
- [ ] Numa sessão da cloud sobre esta branch: `git push --dry-run origin HEAD:main`
- [ ] Confirmar: recusado pelo verificador, com a mensagem das sessões da cloud
- [x] Na mesma sessão: pedir uma ferramenta `mcp__github__…` de leitura (ex.: `get_me`)
- [x] Confirmar: recusada pela regra `deny`
- **Validado em (só a parte das ferramentas):** 04/10/2026 — no ensaio,
  `mcp__github__get_me` respondeu "Permission to use mcp__github__get_me has
  been denied" (recusa por regra).
- **Pendente:** a recusa do push para `main`. No ensaio o comando correu
  antes de a sessão mudar para esta branch e não foi recusado (ver "Relatório
  da Fase 3").

### Cenário N3 — Rotina sem acessos a mais (Fase 3)
- [x] Confirmar na rotina: zero conectores
- [x] Confirmar no registo da execução: nenhum `.env`, nenhum comando do
      Railway, nenhum pedido de permissão
- **Validado em:** 04/10/2026 — a rotina tem `mcp_connections: []`; o registo
  do ensaio não tem leituras de `.env` nem comandos do Railway; as 3 recusas
  registadas são as esperadas (a ferramenta de GitHub e os dois pushes do
  defeito da Fase 4), nenhuma ficou à espera de resposta.

### Cenário N4 — Consumo de uma noite (Fase 3)
- [ ] Registar o uso do plano antes e depois do disparo à mão
- **Antes do ensaio:** sessão 24% usado, semana 4% usado (conta Pro,
  04/10/2026). **Depois:** por registar.

### Cenário D1 — Hora da rotina (Fase 4)
- [ ] O utilizador escolhe a hora, com a medida do N4
- [ ] Confirmar no dia seguinte: a execução agendada aconteceu

---

## Ajustes Possíveis Pós-Implementação

- **A barreira não é uma garantia absoluta.** O verificador lê texto e não
  apanha ofuscação deliberada; a regra `deny` cobre o servidor `github` de
  hoje, não um servidor novo com outro nome que a cloud venha a trazer. A
  garantia que não depende de nada disto seria uma regra do GitHub — só
  possível se o GitHub distinguir a cloud do PC do utilizador, e a sonda
  mostrou que as chamadas aparecem como `danielfranca47`. A rever depois de a
  aplicação do Claude estar instalada (o push pode aparecer como a aplicação).
- **A regra `deny` de `mcp__github` vale também no PC.** Hoje não tem efeito
  (não há servidor com esse nome); se um dia se quiser um servidor de GitHub
  local, tem de ter outro nome ou a regra tem de ser afinada.
- **A API das rotinas anexa todos os conectores da conta por omissão.** Ao
  alterar a rotina pela interface web, confirmar que continuam a zero.
- **Código que menciona `git push` num comentário é recusado na cloud** quando
  o ficheiro é executado diretamente (`python ficheiro.py`). Não afeta
  `python -m pytest`.
- **`gh pr create` continua permitido na cloud** — abre um pedido, não junta
  código. Se a noite começar a abrir pedidos que ninguém pediu, acrescentar à
  lista.
