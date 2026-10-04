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

## Comandos slash locais (`.claude/commands/`) não são versionados

`.claude/` inteiro está no `.gitignore` (linha 42), então os slash commands definidos em
`.claude/commands/*.md` (`/statusdev`, `/statusplans`, `/statusplans-verificar`,
`/statusplans-avancar`, `/discovery-status`, `/discovery-levantar`,
`/discovery-aprofundar`, `/discovery-decidir`) **não acompanham** o repositório quando ele é clonado ou puxado
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

### `/statusplans-avancar` — limpeza + geração do sprint + arquivos "Aguardando Plan Mode" (passo 3 de 3)

**O que é:** aplica o que foi confirmado no passo anterior — remove de `docs/plans/*`
os itens já feitos/obsoletos, gera `docs/plans/plano-sprint-YYYY-MM-DD.md`, e cria um
`docs/implementations/<slug>.md` para cada item confirmado, já com
`Status: Aguardando Plan Mode` e a Motivação preenchida. **Não** entra em Plan Mode
sozinho — isso custaria tokens investigando código em até 6 itens de uma vez só para
priorizar. O Plan Mode só roda depois, quando o usuário escolher por qual item começar.

**Onde entra no processo:** cobre os Passos 5 e 6 ("Priorização" e "Proposta e geração
do arquivo") de `_guia-analise-planos.md` e o início do Passo 1 ("Criar a branch e
nomear o arquivo") de `_guia-documentar-implementacao.md` — mas parando antes do Passo 0
(Diagnóstico em Plan Mode), que é deixado pendente de propósito. Ver a nota "Exceção —
arquivo criado como Aguardando Plan Mode" em `_guia-documentar-implementacao.md`.

**Arquivo:** `.claude/commands/statusplans-avancar.md`

```markdown
---
description: Aplica as confirmações de /statusplans-verificar — limpa itens já feitos/obsoletos de docs/plans/, gera o sprint plan, e já cria os arquivos docs/implementations/<slug>.md correspondentes com status "Aguardando Plan Mode" (sem gastar tokens rodando o diagnóstico agora). Passo 3 do fluxo
---

**Pré-requisito:** uma classificação já confirmada pelo usuário nesta conversa (via
`/statusplans-verificar`). Se não houver confirmação explícita, **não prossiga** — peça
para rodar `/statusplans-verificar` primeiro.

Este comando cobre a transição entre o Passo 5/6 de
[`_guia-analise-planos.md`](../../docs/plans/_guia-analise-planos.md) ("Priorização" +
"Proposta e geração do arquivo") e o **início do Passo 1** de
[`_guia-documentar-implementacao.md`](../../docs/implementations/_guia-documentar-implementacao.md)
("Criar a branch e nomear o arquivo") — mas **sem** executar o Passo 0 (Diagnóstico em
Plan Mode) ainda. Plan Mode é uma investigação de código que custa tokens; fazer isso
automaticamente para até 6 itens de uma vez é caro e desnecessário se o usuário só quer
priorizar agora e decidir depois por qual começar. Em vez disso, este comando **cria os
arquivos de implementação já com o contexto conhecido, marcados como pendentes** — o
Plan Mode roda depois, só para o item que o usuário escolher, quando escolher.

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

### 1. Gerar o sprint plan

Gere `docs/plans/plano-sprint-YYYY-MM-DD.md` (data de hoje), no formato de
[`_template-plano-semanal.md`](../../docs/plans/_template-plano-semanal.md): diagnóstico,
mapa de dependências/sinergias, e tabela de "Tracking de absorção" — já preenchendo a
coluna "Arquivo de implementação" (ver passo 2 abaixo, os nomes já são conhecidos neste
momento) com status inicial `⏳ Aguardando Plan Mode`.

Se algum item tiver uma pergunta de produto/negócio/experiência sem resposta óbvia no
código ou nos plans, **pare e pergunte ao usuário** antes de seguir com aquele item —
não adivinhe decisão de negócio (ver critérios de "Perguntas ao admin" no Passo 4 do
guia de análise).

### 2. Criar o arquivo de implementação pendente, por item

Para cada item do Grupo B, **direto na pasta principal** (sem criar branch/worktree
ainda — isso só acontece depois do Passo 0 ser aprovado, ver abaixo), criar
`docs/implementations/<slug>.md` com esta estrutura reduzida:

```markdown
# <Título do item>

**Status:** Aguardando Plan Mode
**Autonomia:** noturna
**Sprint:** `docs/plans/plano-sprint-YYYY-MM-DD.md` (item P<N>)
**Origem:** `docs/plans/<arquivo-original>.md` — <seção/item de origem>

---

## Motivação

<Mesmo conteúdo que iria num prompt: comportamento actual, comportamento desejado,
por que agora / o que está em risco ou a ganhar.>

---

## Área do sistema

<Serviço(s) envolvidos (backend-core / backend-crm / frontend-crm / etc.) — sem
prescrever arquivo, linha ou abordagem técnica, isso é trabalho do Plan Mode.>

---

## Próximo passo

Este arquivo ainda não passou pelo **Passo 0 (Diagnóstico em Plan Mode)** de
`_guia-documentar-implementacao.md`. Para iniciar: entrar em Plan Mode usando o
contexto acima como ponto de partida, responder as 3 perguntas do Passo 0, e só depois
de aprovado seguir para a criação de branch + worktree (Passo 1).
```

**Nome do arquivo:** seguir o Passo 1 de `_guia-documentar-implementacao.md` — slug
descritivo direto (sem código de etapa, já que ainda não houve Plan Mode para confirmar
o escopo exato).

**Linha `Autonomia`:** `noturna` deixa a fila automática pegar no item sozinha; trocar
para `manual` se o usuário disser que quer acompanhar esse item de perto (ver
`docs/ops/fila-automatica.md`).

Isso não conta como "avançar para código sem plano aprovado" — nenhuma branch, worktree
ou linha de código é criada aqui, só um documento de fila com o contexto já levantado.

## Fechamento

1. Faça um **commit único** cobrindo tudo (limpeza de plans + sprint plan + os novos
   arquivos `docs/implementations/*.md` pendentes), seguindo a convenção de commit do
   `CLAUDE.md` (`git add` nos arquivos específicos, mensagem Conventional Commits,
   corpo listando o que mudou em cada arquivo e a motivação). Tudo isso é documentação —
   não abre worktree/branch própria, é feito direto na branch atual.
2. Mostre ao usuário um resumo curto: quais arquivos de plans foram limpos/removidos, e
   a lista dos itens criados em `docs/implementations/` (P1..P6, cada um com o nome do
   arquivo e uma linha de título).
3. Feche perguntando por qual item ele quer começar agora (ou se prefere só deixar
   todos na fila). Deixe claro que escolher um item é o que dispara o Plan Mode
   (Passo 0) — só nesse momento o código é investigado, e só para o item escolhido.

**Nota técnica para quando um item for escolhido depois:** `EnterWorktree` cria a
branch a partir de `origin/<branch base>`. Se o commit deste comando ainda não foi
enviado ao remoto (`git push`), a worktree nova não terá o arquivo pendente
automaticamente — nesse caso, ao entrar na worktree, recrie o arquivo lá com o mesmo
conteúdo (já está disponível no contexto ou pode ser lido da pasta principal antes de
trocar) antes de completá-lo com o diagnóstico do Plan Mode.

Não entre em Plan Mode nesta resposta para nenhum item — isso só acontece quando o
usuário escolher explicitamente por qual começar.
```

### `/discovery-status` — painel de `docs/discovery/` (só leitura)

**O que é:** mostra o que está pronto para decidir, verifica gatilhos de stand-by e lembra se as metas do produto ainda estão em rascunho.

**Onde entra no processo:** ponto de entrada do fluxo de discovery (ver `docs/discovery/_guia-discovery.md`) — não altera nada.

**Arquivo:** `.claude/commands/discovery-status.md`

```markdown
---
description: Painel não-técnico de docs/discovery/ — o que está pronto para decidir, gatilhos de stand-by, metas por validar. Só leitura
---

Leia `docs/discovery/_radar.md`, `docs/discovery/_metas-produto.md` e todos os
`docs/discovery/*.md` que não começam com `_` nem são `README.md`. Não leia código-fonte,
exceto para verificar gatilhos de stand-by (ponto 3).

Responda em linguagem não-técnica (o usuário não é programador):

1. **Metas** — se `_metas-produto.md` ainda estiver marcado como RASCUNHO, comece por
   aqui: mostre as metas numa tabela curta e peça validação.
2. **Prontas para decisão** — tabela: tema (1 frase), meta, score RICE, veredito
   proposto, perguntas pendentes. Ordene por score. Se houver perguntas de negócio,
   liste-as numeradas para o usuário responder de uma vez.
3. **Stand-by** — para cada gatilho, verifique se já disparou (quando for verificável:
   banco local, código, docs). Diga "disparou" / "não disparou" / "não verificável
   daqui".
4. **Em investigação / Levantadas** — quantas e qual aprofundar a seguir (a ligada à
   meta mais prioritária), com o comando pronto: `/discovery-aprofundar <slug>`.
5. **Inconsistências** — radar desalinhado com os arquivos (investigação sem linha no
   radar ou o contrário). Só aponte; não corrija.

Feche com a próxima ação recomendada numa frase.

Não crie, edite nem apague nenhum arquivo nesta resposta.
```

### `/discovery-levantar` — levantamento → investigações (passo 1 de 3)

**O que é:** recebe um material bruto (conversa, relatório, feedback), guarda-o em `docs/discovery/levantamentos/`, verifica cada afirmação no código e faz a triagem: bug confirmado vai direto para `docs/implementations/` (Aguardando Plan Mode), incerteza vira investigação `Levantado`.

**Onde entra no processo:** Passos 1 e 2 de `docs/discovery/_guia-discovery.md`.

**Arquivo:** `.claude/commands/discovery-levantar.md`

```markdown
---
description: Divide um levantamento (conversa, relatório, feedback) em investigações de discovery — bugs confirmados vão direto para implementations. Passo 1 do fluxo de discovery
---

Leia `docs/discovery/_guia-discovery.md` e siga os **Passos 1 e 2** (levantamento →
gaps → triagem) sobre o material indicado a seguir: $ARGUMENTS

Se `$ARGUMENTS` estiver vazio, pergunte ao usuário qual é o levantamento (caminho de
arquivo ou texto colado) e pare.

1. **Guardar o levantamento** em `docs/discovery/levantamentos/AAAA-MM-DD-<tema>.<ext>`
   (data de hoje). Se o material foi colado como texto, salve-o num `.md`. Se é um
   arquivo noutra pasta do repo, mova com `git mv` (ou mova e depois `git add`, se não
   era rastreado). Não edite o conteúdo original.
2. **Verificar cada afirmação no código** antes de a aceitar — cite arquivo:linha.
   Leia também `docs/discovery/_radar.md`: não recrie investigação que já exista, esteja
   em stand-by ou em "Descartados" (a não ser que o levantamento traga facto novo —
   nesse caso diga qual).
3. **Triagem**, conforme a tabela do Passo 2 do guia:
   - Bug confirmado + solução óbvia → `docs/implementations/<slug>.md` com
     `**Status:** Aguardando Plan Mode`, no mesmo formato reduzido que o
     `/statusplans-avancar` usa (Motivação / Área do sistema / Próximo passo), com
     `**Origem:**` apontando para o levantamento.
   - Já existe / não se aplica → sem arquivo; só no resumo ao usuário.
   - Incerteza → `docs/discovery/<slug>.md` a partir de
     `docs/discovery/_template-investigacao.md`, `**Status:** Levantado`, preenchendo
     **só** as secções marcadas com (L). Não aprofunde agora — isso é o
     `/discovery-aprofundar`.
4. **Atualizar `docs/discovery/_radar.md`** (secção "Em investigação / Levantadas").
5. **Commit único** seguindo as regras do `CLAUDE.md` (`docs:` + `git add` nos arquivos
   específicos + corpo listando cada arquivo). Sem push.

**Resumo ao usuário** (linguagem não-técnica): tabela com cada gap → destino
(implementations / investigação / já existe / não se aplica) e porquê numa frase.
Feche sugerindo qual investigação aprofundar primeiro (a de meta mais prioritária em
`_metas-produto.md`) com o comando pronto: `/discovery-aprofundar <slug>`.
```

### `/discovery-aprofundar` — investigação completa de um tema (passo 2 de 3)

**O que é:** preenche uma investigação com evidência no código, pesquisa de mercado com fontes, opções de solução, pontuação RICE e veredito proposto.

**Onde entra no processo:** Passos 3 e 4 de `docs/discovery/_guia-discovery.md`.

**Arquivo:** `.claude/commands/discovery-aprofundar.md`

```markdown
---
description: Investigação completa de um tema de docs/discovery/ — código, mercado (com fontes), opções de solução, RICE e veredito proposto. Passo 2 do fluxo de discovery
---

Leia `docs/discovery/_guia-discovery.md` (Passos 3 e 4) e
`docs/discovery/_metas-produto.md`, depois aprofunde a investigação
`docs/discovery/$ARGUMENTS.md`.

Se `$ARGUMENTS` estiver vazio, leia `docs/discovery/_radar.md`, sugira a investigação
`Levantado` ligada à meta mais prioritária e pergunte se é essa — não comece sem
confirmação.

1. Mude o status para `Em investigação`.
2. Preencha, pela ordem do template: **Evidência no código** (arquivo:linha + medições
   quando possível), **Como o mercado faz** (2–4 referências via WebSearch, cada uma em
   "Fontes"), **Opções de solução** (2–3, sempre incluindo "não fazer nada / adiar"),
   **Recomendação**, **Pontuação RICE** (com justificativa de cada valor),
   **Veredito proposto** (com gatilho se for stand-by), **Perguntas ao utilizador**
   (só negócio/experiência) e **Em aberto**.
3. Respeite o limite de tempo do guia (~6 pesquisas web, leitura de código focada). Se
   não couber, registe em "Em aberto" e proponha dividir.
4. Mude o status para `Pronta para decisão` e mova a linha no `_radar.md` para
   "Prontas para decisão" (meta, score, veredito proposto, perguntas pendentes).
5. Commit único (`docs:`), sem push.

**Resposta ao usuário** (não-técnica, curta): a pergunta, o que se descobriu, a
recomendação e o veredito proposto — e, se houver, as perguntas de negócio. Não despeje
o documento inteiro no chat. Feche lembrando que pode decidir agora com
`/discovery-decidir` ou acumular mais investigações e decidir em lote depois.

Não crie código de produto nem arquivos em `docs/implementations/` ou `docs/plans/`
nesta resposta — isso só acontece no `/discovery-decidir`.
```

### `/discovery-decidir` — aplica os vereditos (passo 3 de 3)

**O que é:** aplica os vereditos dados pelo usuário: promove para `implementations/` ou `plans/`, marca stand-by com gatilho ou descarta.

**Onde entra no processo:** Passo 5 de `docs/discovery/_guia-discovery.md`.

**Arquivo:** `.claude/commands/discovery-decidir.md`

```markdown
---
description: Aplica os vereditos do usuário sobre investigações de docs/discovery/ — promove para implementations ou plans, marca stand-by com gatilho, ou descarta. Passo 3 do fluxo de discovery
---

Leia `docs/discovery/_guia-discovery.md` (Passo 5) e `docs/discovery/_radar.md`.

**Pré-requisito:** vereditos explícitos do usuário nesta conversa, por investigação
(ex.: "rag → stand-by, faq-fora → implementations"). Vereditos do usuário:
$ARGUMENTS

Se não houver vereditos explícitos, mostre a secção "Prontas para decisão" do radar com
o veredito proposto de cada uma e pergunte — **não aplique nada por conta própria**. Um
veredito "stand-by" sem gatilho não é válido: proponha um gatilho mensurável e peça
confirmação.

Para cada investigação decidida:

- **Implementations** → crie `docs/implementations/<slug>.md` com
  `**Status:** Aguardando Plan Mode`, no formato reduzido do `/statusplans-avancar`
  (Motivação / Área do sistema / Próximo passo), levando da investigação a evidência,
  a solução recomendada e as fontes, e com `**Origem:** docs/discovery (investigação
  <slug>, graduada em AAAA-MM-DD)`. Remova o arquivo de discovery (`git rm`).
- **Plans** → acrescente o item ao arquivo de `docs/plans/` da área (ou crie
  `<area>-melhorias-futuras.md`), com o problema, a recomendação, o esforço estimado e
  as fontes. Remova o arquivo de discovery.
- **Stand-by** → mantenha o arquivo, status `Stand-by`, gatilho preenchido; mova a
  linha do radar para "Stand-by (gatilhos)".
- **Descartar** → remova o arquivo; acrescente uma linha em "Descartados" do radar
  (tema, motivo, data).

Atualize o `_radar.md` e faça um **commit único** (`docs:`), sem push.

**Resumo ao usuário:** tabela investigação → destino. Se algo foi para implementations,
feche perguntando se quer iniciar o Plan Mode de algum agora — não entre em Plan Mode
sem essa escolha.
```

### Manutenção desta seção

Sempre que um novo comando for criado em `.claude/commands/`, adicionar aqui uma
subseção igual às acima — o que é, onde entra no processo, e o conteúdo completo em
bloco de código — senão o comando se perde na próxima vez que o projeto for aberto
noutro dispositivo.

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
lido por `cat`, argumento de `grep` ou `echo`.

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
