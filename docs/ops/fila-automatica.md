# Fila automática — o agente que executa a fila sozinho

Procedimento que uma sessão do Claude Code segue quando trabalha a fila de
`docs/implementations/` e `docs/plans/` **sem o utilizador a dar o "start"**.
Quem lança a sessão (a rotina da noite, o comando do dia) só diz "lê a secção
X deste ficheiro e executa" — as regras moram aqui, não no gatilho.

Uma sessão só é "da fila" quando foi lançada por um desses gatilhos. Numa
conversa normal com o utilizador vale o processo normal do `CLAUDE.md`.

---

## Estado atual

| Peça | Estado |
|---|---|
| Regras desta página, campo `Autonomia`, verificação do que sobe sempre | Em vigor |
| Turno da noite (rotina na cloud) | Por ligar |
| Turno do dia (`/fila-validar`) e avaliador | Por ligar |
| **Poder de merge do avaliador** | **Desligado** — modo sombra: o avaliador dá o veredito, o utilizador decide |

O poder de merge só passa a "Ligado" com as quatro condições juntas: backup
da base de dados de produção a funcionar, 5 vereditos seguidos no placar
(abaixo), `main` protegida contra push forçado no GitHub, e um "sim" explícito
do utilizador. Quem altera essa linha é uma sessão com o utilizador presente —
nunca uma sessão da fila.

---

## O desenho, em duas metades

```
NOITE — cloud, PC desligado                 DIA — PC ligado
  clone limpo do repositório                  traz a branch claude/<item>
  (sem .env, sem Railway, sem browser)        testes automáticos + teste via browser
  1 item: diagnóstico → plano → código        o que sobe sempre? (script)
  testes automáticos                          avaliador: resolve a dor inicial?
  push só para claude/<item>                  aprovado → main · senão → relatório
```

A noite nunca chega a `main`. O dia é o único sítio onde um item pode ir para
produção, e só depois de passar pelo script e pelo avaliador.

---

## Que itens a fila pode pegar

Um item é **elegível** quando, em `origin/main`:

- é um ficheiro de `docs/implementations/` (fora os que começam por `_` e o
  `README.md`) com `**Status:** Aguardando Plan Mode`;
- não tem `**Autonomia:** manual` no cabeçalho — a linha `**Autonomia:**`
  aceita `noturna` ou `manual`, e **sem a linha vale `noturna`**;
- não existe ainda a branch `origin/claude/<slug>` (o slug é o nome do
  ficheiro sem `.md`).

Ordem: primeiro uma branch `claude/*` com `Status: Interrompido de noite`,
depois os `fix-*`, depois o ficheiro que está na fila há mais tempo.

Quando não sobra nenhum, a noite pega o primeiro item com
`**Prioridade: ALTA**` de um `docs/plans/*-melhorias-futuras.md`: cria o
ficheiro de implementação na branch e retira o item do plano na mesma branch.
Itens MÉDIA, BAIXA ou "por definir" nunca são pegos — a prioridade é decisão
do utilizador.

Para tirar um item da fila automática: `**Autonomia:** manual` no cabeçalho.
Quem começa à mão um item que estava na fila faz essa alteração em `main`
antes de abrir a worktree.

---

## O que sobe sempre

Uma branch que toque numa destas categorias **nunca é mergeada pelo avaliador**,
mesmo com veredito favorável. Fica à espera da decisão do utilizador.

| Categoria | O que apanha |
|---|---|
| Regras do próprio agente | `.claude/`, `.github/`, `scripts/claude_hooks/`, `scripts/fila/`, este ficheiro, `CLAUDE.md` |
| Pagamento e cobrança | Efi, planos, assinaturas, checkout, reembolso |
| Envio real a clientes | UazAPI, envio de WhatsApp, email/SMTP, runners e workers do backend-executors |
| Estrutura da base de dados | `ensure_column`, criar/alterar/apagar tabela ou índice, `migrations/`, modelos e `db.py` do backend-core, `database.py` do backend-crm |
| Instruções da IA | `decision_engine`, `field_extractor`, `assistente_ia/llm.py`, playbooks, `meta_prompter`, Camada 7, e qualquer linha que monte um prompt |

Quem decide é um script, não uma opinião:

```bash
python scripts/fila/categorias_que_sobem.py --base origin/main --ramo claude/<slug>
```

Saída 0 = nada sobe; 1 = sobe (lista as categorias e o motivo); 2 = não
conseguiu ler as alterações — conta como "sobe". Documentação (`docs/`,
`.md`) não conta para as quatro últimas categorias; linhas de ficheiros de
teste também não. A lista exata de padrões está no próprio script e é coberta
por `scripts/fila/tests/`.

A noite **não deixa de implementar** um item por ele tocar numa categoria — o
portão é no merge. O utilizador recebe o trabalho feito e decide.

---

## Exceções ao processo normal (só em sessões da fila)

O `CLAUDE.md` e os guias de `docs/implementations/` pedem a resposta do
utilizador em três pontos. Numa sessão da fila:

| Ponto | Processo normal | Sessão da fila |
|---|---|---|
| Aprovar o plano | Plan Mode + aprovação | O agente escreve o diagnóstico e o plano no `.md` e segue — **salvo** os casos de "só plano", abaixo |
| Nome da branch | Proposto e confirmado | `claude/<slug-do-ficheiro>`, sem confirmação |
| Triagem dos "Ajustes Possíveis" na graduação | Pergunta item a item | Nada é descartado nem promovido a urgente: cada item vai para `docs/plans/<tema>-melhorias-futuras.md` com `**Prioridade: por definir**`. A triagem fica para a revisão do utilizador (`/statusplans`) |

Tudo o resto do processo mantém-se: uma fase = um commit, hash registado,
relatório da fase em linguagem simples, checks de validação executáveis, docs
de arquitetura atualizados.

Uma sessão da fila nunca: altera definições pessoais ou regras de permissão;
lê ou escreve `.env`; corre comandos do Railway que não sejam de leitura;
apaga ou enfraquece um teste para o fazer passar; faz push forçado.

---

## Turno da noite

Corre na cloud, num clone limpo. Um item por noite.

1. **Escolher** o item (secção "Que itens a fila pode pegar"). Sem item
   elegível: terminar e dizê-lo.
2. **Branch** `claude/<slug>` a partir de `origin/main`.
3. **Diagnóstico** — Passo 0 de
   [`_guia-documentar-implementacao.md`](../implementations/_guia-documentar-implementacao.md),
   escrito no próprio ficheiro (já existe? o que construir? riscos? fases?).
4. **Parar em "só plano"** quando acontecer qualquer destas — commit do `.md`,
   push, e `**Status:** Só plano — precisa da tua decisão`, com uma secção
   `## Decisões em aberto` em linguagem simples, cada uma com a opção
   recomendada:
   - há uma decisão de produto ou de negócio sem resposta óbvia no código ou
     nos docs;
   - o plano tem mais de 3 fases, ou não cabe numa noite;
   - depende de outro item que ainda não está em `main`;
   - a funcionalidade afinal já existe (dizer onde, e propor fechar o item).
5. **Implementar** fase a fase, como manda o guia. Os Checks de Validação têm
   de poder ser executados de dia por quem não viu esta sessão: setup, ação,
   o que confirmar.
6. **Testes automáticos** dos serviços tocados (`python -m pytest` no backend,
   `npx tsc --noEmit` no frontend). Registar no ficheiro, na secção
   `## Testes automáticos (turno da noite)`: o que correu e o resultado. Um
   teste que falha e não é resolvido fica dito com todas as letras.
7. **Push** só para `claude/<slug>` e
   `**Status:** Implementado de noite — por validar`.

Se o limite de uso acabar a meio: commit do que estiver coerente, push, e
`**Status:** Interrompido de noite — continuar`. A noite seguinte retoma essa
branch antes de pegar outra.

---

## Turno do dia

Corre no PC do utilizador, lançado a partir da pasta principal. Trata cada
branch `origin/claude/*` com `Status: Implementado de noite — por validar`.

1. `git fetch`. Se já existir uma worktree local com o mesmo slug, não avançar:
   reportar trabalho em duplicado.
2. Worktree `.claude/worktrees/claude+<slug>` sobre a branch; juntar-lhe
   `origin/main` (conflitos: [`_guia-resolucao-conflitos.md`](../implementations/_guia-resolucao-conflitos.md)).
3. Testes automáticos outra vez, já com `main` junto.
4. Ambiente local (ver [`local-dev.md`](local-dev.md), "Worktree nova precisa
   de `.env`…") e os Checks de Validação via browser, como no guia. Check
   validado: `[x]` com data e o que se viu. Check que precisa de WhatsApp real
   ou de produção fica `[ ]` — o item sobe por "não consegui validar".
5. Script do que sobe sempre.
6. Avaliador (secção seguinte).
7. Decisão:

| Situação | O que acontece |
|---|---|
| Sobe (script), ou algum check obrigatório por validar | Não é mergeado. `**Status:** À espera da tua decisão` + relatório |
| Avaliador não aprova | Não é mergeado. `**Status:** Avaliado: não passou` + relatório |
| Avaliador aprova, poder de merge **desligado** | Não é mergeado. Relatório com o veredito; o utilizador decide; a linha vai para o placar |
| Avaliador aprova, poder de merge **ligado** | Graduação (com a exceção da triagem), merge em `main`, push, limpeza da worktree e da branch local e remota |

O estado e o relatório ficam escritos no `.md` do item, na branch, e com push
— é daí que o painel lê.

---

## Avaliador

Uma sessão separada, lançada pelo turno do dia, **sem o histórico de quem
implementou ou testou** e só de leitura. Recebe o nome da branch e nada mais;
lê por si a Motivação do item, o que mudou em relação a `main`, os testes e os
checks.

Aprova só se **todas** forem verdade:

1. O que foi feito resolve a dor descrita na Motivação — não uma versão mais
   fácil do problema.
2. Todos os checks obrigatórios estão `[x]` com o que foi observado; nenhum
   `[⏭️]` sem justificação.
3. Os testes automáticos passam, e nenhum foi apagado ou enfraquecido.
4. A branch não faz mais do que o plano dizia.
5. As convenções do `CLAUDE.md` foram respeitadas (em especial: dados de
   negócio sempre filtrados por `user_id`).
6. Os docs de arquitetura afetados estão atualizados.

Responde `aprovado` ou `não aprovado` e escreve no `.md` do item a secção
`## Avaliação`, **em linguagem simples, sem detalhes de código**: o que foi
feito, porque passou ou não passou, o que propõe a seguir, e como desfazer.

---

## Placar do modo sombra

Enquanto o poder de merge está desligado, cada veredito é comparado com a
decisão do utilizador. Uma discordância repõe a contagem a zero.

| Data | Item | Veredito do avaliador | Decisão do utilizador | Seguidas |
|---|---|---|---|---|
| — | — | — | — | 0 |

---

## Pausar e desfazer

- **Pausar a noite:** desligar a rotina em claude.ai, ou pedir numa conversa
  "pausa a fila".
- **Tirar um item:** `**Autonomia:** manual` no cabeçalho.
- **Desfazer um item que já foi para produção:** pedir "desfaz o item
  `<slug>`". É um commit novo que anula o merge, seguido de push — nunca um
  push forçado. Uma alteração à estrutura da base de dados não se desfaz
  assim, e é por isso que essa categoria sobe sempre.
