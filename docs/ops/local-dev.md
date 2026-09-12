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

## Comandos slash locais (`.claude/commands/`) não são versionados

`.claude/` inteiro está no `.gitignore` (linha 42), então os slash commands definidos em
`.claude/commands/*.md` (`/statusdev`, `/statusplans`, `/statusplans-verificar`,
`/statusplans-avancar`) **não acompanham** o repositório quando ele é clonado ou puxado
noutro computador — existem só na máquina onde foram criados.

**Sintoma a reconhecer:** num dispositivo novo, digitar `/statusplans` (ou qualquer um
dos comandos abaixo) não faz nada — o Claude Code não reconhece o comando — e a pasta
`.claude/commands/` está vazia ou não existe.

**Como recuperar:** colar este prompt no Claude Code, dentro da pasta do projeto, no
dispositivo novo:

> Lê `docs/ops/local-dev.md`, seção "Comandos slash locais", e recria cada um dos
> arquivos `.claude/commands/*.md` listados ali, com o conteúdo exato de cada bloco de
> código — sem alterar nada.

Claude vai ler os blocos abaixo e criar os arquivos correspondentes.

### `/statusdev` — panorama de `docs/implementations/`

**O que é:** lê tudo em `docs/implementations/` (exceto os arquivos-guia com `_` e o
`README.md`) e devolve uma tabela não-técnica — impacto, classificação, % concluído, se
já existe uma worktree/branch activa para o item, e prioridade recomendada.

**Onde entra no processo:** é o primeiro comando a rodar quando se quer saber o que está
em andamento nas implementações e por onde continuar — não altera nada, só levanta e
prioriza.

**Arquivo:** `.claude/commands/statusdev.md`

```markdown
---
description: Lê todos os arquivos de docs/implementations/ e dá um panorama não-técnico (impacto, classificação, % concluído, prioridade)
---

Leia todos os arquivos `.md` de `docs/implementations/`, **exceto** os arquivos-guia que começam
com `_` (`_guia-documentar-implementacao.md`, `_guia-resolucao-conflitos.md`,
`_processo-graduacao-implementacao.md`, `_template-implementacao.md`, `_conta-teste-local.md`) e
o `README.md` da pasta — esses são meta-documentação de processo, não itens de trabalho.

Rode `git worktree list` para descobrir quais implementações têm uma worktree/branch ativa agora
(cada worktree fica em `.claude/worktrees/<tipo>/<slug>` e o slug corresponde ao nome do arquivo
de implementação, ex.: `feat/notificacoes-push` ↔ `feat-notificacoes-push.md`). Use isso para
marcar, por item, se há um worker em andamento — isso evita que o usuário inicie trabalho
duplicado em algo que já está sendo feito em outra sessão/worktree.

Para cada arquivo restante, monte uma tabela com:

- **Item** — nome do arquivo (sem extensão)
- **O que é** — descrição em 1-2 frases, linguagem não-técnica (o usuário não é programador),
  focada no comportamento observável, não em nomes de função/arquivo
- **Classificação** — um destes: 🔴 Crítico (bug ativo, risco de receita/segurança/conversão),
  🟡 Importante (funcionalidade real, não visual), 🟢 Estético/Cosmético, ⚪ Decisão de design
  (não é bug), 🔧 Débito técnico/risco arquitetural
- **% Concluído** — baseado no campo `Status:` do arquivo e nos checks de validação marcados
  `[x]` vs `[ ]`
- **Worker ativo** — 🟢 Livre (nenhuma worktree encontrada para o slug) ou 🔵 Em andamento
  (nome da branch/worktree ativa) — se estiver em andamento, avisar que iniciar trabalho nesse
  item agora provavelmente duplica esforço
- **Prioridade recomendada** — Alta / Média-alta / Média / Baixa, com justificativa curta

Depois da tabela, destaque em texto corrido:
- Qualquer item pronto para graduar (todos os checks `[x]`) que ainda não foi graduado
- Qualquer bug crítico confirmado e não resolvido (não só planejado)
- Qualquer sobreposição/duplicação entre dois arquivos tratando do mesmo assunto
- Qualquer item com worker ativo (🔵) — deixar claro que já há trabalho em andamento ali
- Uma ordem sugerida de ataque (top 3-5) com 1 linha de razão cada, **excluindo** itens com
  worker já ativo (esses não entram na lista de "por onde começar")

Feche perguntando ao usuário por qual item ele quer começar, ou se prefere consolidar algum
item duplicado/relacionado em Plan Mode primeiro.

Não sugira nem inicie nenhuma mudança de código nesta resposta — é só levantamento e priorização.
```

### `/statusplans` — inventário de `docs/plans/` (passo 1 de 3)

**O que é:** lê `docs/plans/*.md` e devolve uma tabela de itens (M1, Etapa C, etc.) com
prioridade recomendada e um sinal de possível obsolescência — sem ler código-fonte.

**Onde entra no processo:** primeiro passo do fluxo de análise de plans (equivalente ao
Passo 1 "Inventário" de `_guia-analise-planos.md`, só que rápido e sem as perguntas ao
admin). Sugere até 6 itens para o próximo comando verificar.

**Arquivo:** `.claude/commands/statusplans.md`

```markdown
---
description: Lê docs/plans/ e dá um panorama rápido de prioridades (sem auditar código) — passo 1 do fluxo, antes de /statusplans-verificar
---

Leia todos os arquivos `.md` de `docs/plans/`, **exceto** os arquivos-guia que começam
com `_` (`_guia-analise-planos.md`, `_template-plano-semanal.md`,
`_versionamento-agent-local.md`) e o `README.md` da pasta — esses são meta-documentação
de processo, não itens de trabalho. Inclua qualquer `plano-sprint-*.md` existente — é um
item de trabalho em andamento, não um guia.

Um arquivo de plans pode conter vários itens (M1, M2, Etapa A/B/C, ou seções por título).
Identifique cada item individualmente — não trate o arquivo inteiro como uma linha só,
a menos que ele não tenha subdivisão.

Monte uma tabela com:

- **Arquivo** — nome do arquivo de origem (sem extensão)
- **Item** — identificador dentro do arquivo (M1, Etapa C, etc.) ou "arquivo inteiro"
  se não houver subdivisão
- **O que é** — 1-2 frases, linguagem não-técnica (o usuário não é programador), focada
  em comportamento observável
- **Prioridade declarada** — como está escrita no arquivo (ALTA/MÉDIA/BAIXA), ou
  "não declarada"
- **Prioridade recomendada** — Alta / Média-alta / Média / Baixa, considerando a
  prioridade declarada + se o texto cita bloqueio de receita, segurança ou usuários
  actuais + quão antigo parece o contexto do plano
- **Possível obsolescência** — 🟢 sem indício, ou 🟡 revisar (ex.: o item cita um
  provedor, integração ou fluxo que pode ter mudado desde que o plano foi escrito).
  **Não confirme obsolescência aqui** — apenas sinalize. Confirmar é trabalho do
  próximo comando, que lê o código.

Esta resposta é uma leitura de inventário, não uma auditoria — **não abra arquivos de
código-fonte** nesta resposta, só os arquivos de `docs/plans/`.

Depois da tabela, destaque em texto corrido:
- Duplicação/sobreposição entre dois arquivos tratando do mesmo assunto
- Um `plano-sprint-*.md` já existente e não fechado — avisar que ele deveria ser tratado
  junto ou primeiro, e apontar quantos itens dele ainda estão `⏳ Pendente`
- Ordem sugerida de ataque: **até 6 itens**, ordenados por prioridade recomendada,
  priorizando quem tem 🟡 na coluna de obsolescência (verificar isso primeiro evita
  migrar trabalho desnecessário para implementations)

Feche perguntando se o usuário quer rodar `/statusplans-verificar` sobre a lista
sugerida, ou se prefere indicar uma lista customizada de itens.

Não crie, edite nem apague nenhum arquivo nesta resposta — só leitura e priorização.
```

### `/statusplans-verificar` — auditoria e obsolescência (passo 2 de 3)

**O que é:** pega os itens sugeridos por `/statusplans` (ou uma lista dada pelo usuário,
até 6) e audita cada um no código real e em `docs/architecture/`, classificando como já
implementado, parcial, inexistente, ou **obsoleto** (o problema que originou o item já
não existe mais — ex.: cita um provedor ou fluxo que já foi substituído).

**Onde entra no processo:** equivalente ao Passo 2 "Auditoria técnica" de
`_guia-analise-planos.md`, mas focado só nos itens já pré-selecionados, e com a
classificação de obsolescência que o guia original não tinha. Não altera nenhum
arquivo — só apresenta e pede confirmação.

**Arquivo:** `.claude/commands/statusplans-verificar.md`

```markdown
---
description: Audita no código/arquitetura se os itens de docs/plans/ selecionados já foram feitos, estão obsoletos, ou ainda precisam ser implementados — pede confirmação antes de qualquer mudança. Passo 2 do fluxo, depois de /statusplans
---

**Pré-requisito:** uma lista de itens a verificar. Se o usuário não indicou quais nesta
mensagem, use a "ordem sugerida de ataque" da última resposta de `/statusplans` nesta
conversa. Se não houver nenhuma, peça para rodar `/statusplans` primeiro ou informar os
itens manualmente. **Limite a no máximo 6 itens por vez** — se a lista tiver mais,
verifique só os 6 de maior prioridade e avise quais ficaram de fora.

Para cada item, siga o **Passo 2 (Auditoria técnica)** de
[`docs/plans/_guia-analise-planos.md`](../../docs/plans/_guia-analise-planos.md): ler os
`docs/architecture/` relevantes e buscar no código os arquivos/comportamentos citados —
não confiar apenas na descrição do plano, ela pode estar desatualizada.

Classifique cada item em uma destas categorias, **citando arquivo:linha ou doc de
arquitetura como evidência** (nunca sem evidência):

- ✅ **Já implementado** — o comportamento descrito já existe no sistema tal como o
  plano pedia
- 🟡 **Parcialmente implementado** — existe estrutura, mas incompleta ou com gap
  relevante
- ❌ **Não implementado** — precisa ser construído do zero
- 🗑️ **Obsoleto** — o problema/contexto que originou o item não existe mais (ex.: o
  item cita um provedor, fluxo ou decisão que foi substituído por outro — ex.: melhoria
  de checkout de um provedor de pagamento quando o checkout já migrou para outro).
  Justifique dizendo o que mudou e, se souber, desde quando (commit ou doc de
  arquitetura que documenta a mudança).

Monte uma tabela: **Item | Classificação | Evidência | Ação proposta**

Ação proposta por classificação:
- ✅ ou 🗑️ → remover o item do arquivo de plans (ou apagar o arquivo inteiro se ele
  ficar sem nenhum item pendente)
- 🟡 ou ❌ → manter como candidato para avançar para implementations no próximo comando

**Não altere nenhum arquivo nesta resposta.** Apresente a tabela e peça confirmação
explícita do usuário — em especial:
- cada 🗑️ (a leitura de obsolescência pode estar errada — confirme o motivo com o
  usuário antes de descartar o item)
- cada ✅ (pode ter sido implementado parcialmente, num contexto diferente do que o
  plano pedia)

Feche perguntando se pode prosseguir para `/statusplans-avancar` com essa confirmação,
ou se algum item precisa de reclassificação.
```

### `/statusplans-avancar` — limpeza + geração do sprint (passo 3 de 3)

**O que é:** aplica o que foi confirmado no passo anterior — remove de `docs/plans/*`
os itens já feitos/obsoletos, e gera `docs/plans/plano-sprint-YYYY-MM-DD.md` com prompts
prontos para os itens que ainda precisam ser implementados (máximo 6 por vez).

**Onde entra no processo:** equivalente aos Passos 5 e 6 ("Priorização" e "Proposta e
geração do arquivo") de `_guia-analise-planos.md`. A partir daqui o fluxo normal de
`docs/implementations/` assume — o usuário copia o prompt de cada item do sprint e cola
para começar aquela implementação (Plan Mode, etc.).

**Arquivo:** `.claude/commands/statusplans-avancar.md`

```markdown
---
description: Aplica as confirmações de /statusplans-verificar — limpa itens já feitos/obsoletos de docs/plans/ e gera o sprint plan com prompts prontos para os itens confirmados (máx. 6). Passo 3 do fluxo
---

**Pré-requisito:** uma classificação já confirmada pelo usuário nesta conversa (via
`/statusplans-verificar`). Se não houver confirmação explícita, **não prossiga** — peça
para rodar `/statusplans-verificar` primeiro.

Separe os itens confirmados em dois grupos:

## Grupo A — ✅ já implementado / 🗑️ obsoleto (confirmados)

Para cada arquivo de `docs/plans/` afetado:
- Remova apenas a seção/item confirmado. **Sem histórico** — o objetivo é o arquivo
  refletir só o que ainda falta, não um changelog (não escrever "item removido por
  estar obsoleto"; simplesmente remover)
- Se o arquivo ficar sem nenhum item pendente, apague o arquivo inteiro (`git rm`)
- **Nunca** apague arquivos prefixados com `_` em `docs/plans/`
- **Nunca** apague `plano-sprint-*.md` aqui — isso só acontece no Passo 6b da graduação
  de implementations (ver
  [`_processo-graduacao-implementacao.md`](../../docs/implementations/_processo-graduacao-implementacao.md)),
  quando todos os itens daquele sprint já estiverem `✅` no tracking

## Grupo B — 🟡/❌ confirmados para avançar

**Máximo 6 itens.** Se houver mais confirmados que isso, avance só os 6 de maior
prioridade recomendada (da resposta de `/statusplans`) e avise quais ficaram de fora
para uma próxima rodada.

Siga os **Passo 5 e 6** de
[`docs/plans/_guia-analise-planos.md`](../../docs/plans/_guia-analise-planos.md) para
gerar `docs/plans/plano-sprint-YYYY-MM-DD.md` (data de hoje), no formato de
[`_template-plano-semanal.md`](../../docs/plans/_template-plano-semanal.md): diagnóstico,
um prompt pronto por item (**sem prescrever arquivo, linha ou abordagem técnica** — isso
é trabalho do Plan Mode de cada implementação) e tabela de "Tracking de absorção" com
todos os itens `⏳ Pendente`.

Se algum item do Grupo B tiver uma pergunta de produto/negócio/experiência sem resposta
óbvia no código ou nos plans, **pare e pergunte ao usuário** antes de escrever o prompt
daquele item — não adivinhe decisão de negócio (ver critérios de "Perguntas ao admin"
no Passo 4 do guia de análise).

## Fechamento

1. Faça um **commit único** cobrindo as duas mudanças (limpeza de plans + criação do
   sprint plan), seguindo a convenção de commit do `CLAUDE.md` (`git add` nos arquivos
   específicos, mensagem Conventional Commits, corpo listando o que mudou em cada
   arquivo e a motivação). Isso é manutenção de `docs/plans/`, feito direto na branch
   atual — não abre worktree/branch própria.
2. Mostre ao usuário: quais arquivos de plans foram limpos ou removidos, e o prompt
   pronto de cada item do sprint, para ele copiar e colar quando quiser iniciar cada
   implementação.

Não inicie nenhuma implementação nesta resposta — apenas gera o sprint plan e limpa os
plans já concluídos/obsoletos.
```

### Manutenção desta seção

Sempre que um novo comando for criado em `.claude/commands/`, adicionar aqui uma
subseção igual às acima — o que é, onde entra no processo, e o conteúdo completo em
bloco de código — senão o comando se perde na próxima vez que o projeto for aberto
noutro dispositivo.

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
