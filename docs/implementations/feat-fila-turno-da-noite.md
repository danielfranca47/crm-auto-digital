# Fila automática — turno da noite (rotina na cloud)

**Branch:** `worktree-feat+fila-turno-da-noite` (worktree `.claude/worktrees/feat+fila-turno-da-noite`)
**Status:** Em andamento — Fase 1 implementada; Fases 2 a 4 por fazer
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

A lançar pelo utilizador num terminal (`claude --cloud "<texto>"`) ou a partir
de claude.ai/code — a sessão do Claude Code não consegue lançá-la sozinha.

Conforme o resultado: se `python` não existir na cloud, corrigir a forma de
chamar o verificador em `.claude/settings.json`; se a sessão tiver ferramentas
de GitHub que juntem código sem passar pela linha de comandos, acrescentar a
recusa; se o push aparecer no GitHub como uma aplicação, propor a regra do
lado do GitHub.

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

### Fase 4 — Ligar o horário

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

### Cenário T2 — Os testes do backend-crm não dependem do `.env` (Fase 1)
- [x] Exportar `backend-crm` do repositório para uma pasta vazia (sem `.env`)
- [x] Nessa pasta: `python -m pytest tests/ -q`
- [x] Confirmar: tudo aprovado
- **Validado em:** 04/10/2026 — 242 testes passam numa cópia limpa sem `.env`
  (com os pacotes já instalados no Python da máquina; a instalação do zero é
  confirmada na sonda, ponto 5)

### Cenário S1 — Sonda na cloud (Fase 2)
- [ ] Lançar a sessão da cloud com o texto de `## Texto da sonda`
- [ ] Registar aqui as respostas aos 8 pontos
- [ ] Confirmar: o ponto 3 é recusado pelo verificador (prova de que ele corre
      na cloud); o ponto 5 termina com os 242 testes aprovados; o ponto 7 não
      encontra nenhum `.env`

### Cenário N1 — Uma noite inteira, disparada à mão (Fase 3)
- [ ] Disparar a rotina à mão
- [ ] Confirmar: existe `origin/claude/<slug>`; o `.md` do item diz
      `Implementado de noite — por validar` (ou `Só plano — precisa da tua
      decisão`); a secção `## Testes automáticos (turno da noite)` está
      preenchida; `main` não mudou

### Cenário N2 — A barreira funciona na cloud (Fase 3)
- [ ] Numa sessão da cloud sobre esta branch: `git push --dry-run origin HEAD:main`
- [ ] Confirmar: recusado pelo verificador, com a mensagem das sessões da cloud

### Cenário N3 — Rotina sem acessos a mais (Fase 3)
- [ ] Confirmar na rotina: zero conectores
- [ ] Confirmar no registo da execução: nenhum `.env`, nenhum comando do
      Railway, nenhum pedido de permissão

### Cenário N4 — Consumo de uma noite (Fase 3)
- [ ] Registar o uso do plano antes e depois do disparo à mão

### Cenário D1 — Hora da rotina (Fase 4)
- [ ] O utilizador escolhe a hora, com a medida do N4
- [ ] Confirmar no dia seguinte: a execução agendada aconteceu

---

## Ajustes Possíveis Pós-Implementação

- **A barreira não é uma garantia absoluta.** É um verificador de texto: não
  apanha ofuscação deliberada, nem uma ferramenta de GitHub que não passe pela
  linha de comandos (a verificar na sonda). A garantia que não depende do
  texto seria uma regra do GitHub — só possível se a cloud for vista como uma
  aplicação diferente do utilizador.
- **Código que menciona `git push` num comentário é recusado na cloud** quando
  o ficheiro é executado diretamente (`python ficheiro.py`). Não afeta
  `python -m pytest`.
- **`gh pr create` continua permitido na cloud** — abre um pedido, não junta
  código. Se a noite começar a abrir pedidos que ninguém pediu, acrescentar à
  lista.
