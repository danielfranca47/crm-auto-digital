# Fila automática — contrato (regras, elegibilidade e o que sobe sempre)

**Branch:** `worktree-feat+fila-automatica` (worktree `.claude/worktrees/feat+fila-automatica`)
**Status:** Em andamento — Fase 1 implementada; Cenário D1 por validar
**Autonomia:** manual

---

## Motivação

A fila de `docs/implementations/` e `docs/plans/` só anda quando o utilizador
escreve "faz o ficheiro X" e fica a acompanhar. Um item pequeno custa-lhe o
mesmo que um grande. O objetivo é o trabalho avançar sem o "start" dele, e ele
entrar só para decidir o que o agente não conseguiu validar.

Os cliques de permissão já estavam resolvidos (modo auto). Faltava a segunda
metade: quem pega nos itens, quem valida, e quem decide se vai para produção.

### Decisões do utilizador

De 03/10/2026:

1. Deploy automático é aceite (push em `main` → Railway).
2. O portão para `main` é um agente avaliador, não o utilizador. Não aprova →
   relatório em linguagem simples.
3. O PC fica desligado à noite: o turno da noite não depende dele.
4. Continua a poder ver e testar localmente via browser o que o agente fez.
5. O repositório fica público (rever aos 10 utilizadores ativos).
6. Sem agente de permissões próprio nem registo multi-projeto; relatório no
   painel admin adiado.

De 04/10/2026 (Plan Mode):

7. Desenho noite/dia: de noite uma rotina na cloud implementa numa branch
   `claude/<item>`; de dia, no PC, corre o teste via browser e o avaliador.
8. Sobem sempre para ele: pagamento e cobrança; envio real a clientes;
   estrutura da base de dados; instruções da IA. Mais as regras do próprio
   agente.
9. Todos os itens são elegíveis por defeito; só fica de fora o que ele marcar
   `manual`. Item grande ou com decisão de produto em aberto → só o plano.
10. Modo sombra: 5 vereditos seguidos a concordar com ele antes de o avaliador
    poder mergear.

---

## Problemas Identificados (estado anterior)

1. **Sem procedimento escrito** para uma sessão trabalhar a fila sem o
   utilizador: nem turno da noite, nem turno do dia, nem avaliador.
2. **Sem forma de dizer que itens podem ser pegos** — os ficheiros "Aguardando
   Plan Mode" não tinham nenhum campo de elegibilidade.
3. **Sem lista do que sobe sempre**, nem nada que a aplicasse de forma
   mecânica.
4. **Três pontos do processo exigiam resposta do utilizador** (aprovar plano,
   confirmar nome da branch, triagem dos "Ajustes Possíveis" —
   `_processo-graduacao-implementacao.md`, Passo 5b) sem regra para quando ele
   não está.
5. **Sem backup da base de dados de produção** — 2 volumes no Railway
   (`backend-core-volume`, `backend-crm-volume`), nenhuma rotina de backup no
   código nem em `docs/ops/`.
6. **`main` sem proteção no GitHub** (confirmado: "Branch not protected").

---

## Abordagem

Nenhum serviço novo: procedimentos versionados + gatilhos finos + um script.

```
NOITE — cloud, PC desligado                 DIA — PC ligado
  clone limpo do repositório                  traz a branch claude/<item>
  1 item: diagnóstico → plano → código        testes + teste via browser
  testes automáticos                          script: toca no que sobe sempre?
  push só para claude/<item>                  avaliador: resolve a dor inicial?
                                              aprovado → main · senão → relatório
```

Decisões tomadas:

- **A regra mora no repositório, não no gatilho.** A rotina e o comando só
  dizem "lê a secção X de `docs/ops/fila-automatica.md` e executa".
- **O que sobe sempre é decidido por código** (`scripts/fila/categorias_que_sobem.py`),
  não pelo avaliador. Na dúvida, sobe: erro a ler as alterações conta como
  "sobe".
- **Elegibilidade por ausência:** sem a linha `**Autonomia:**` vale `noturna`.
  Evita editar os ficheiros que já estão na fila, que estão a ser trabalhados
  noutras worktrees.
- **Entrega em fatias, uma implementação por fase do plano.** A rotina da
  noite clona `main`; se o plano inteiro vivesse num só ficheiro, as regras só
  chegariam a `main` semanas depois (o modo sombra precisa de 5 noites). Esta
  implementação é a Fase 1; as Fases 2 a 5 e o backup ficam como itens próprios
  na fila, todos `Autonomia: manual`.
- **Descartado: exigir pull request para `main`** (recomendação do briefing de
  03/10) — incompatível com a decisão 2: quem faz o merge é a sessão local do
  avaliador. Fica só a proteção contra push forçado.

---

## Plano de Implementação

### Fase 1 — Contrato da fila

**Objetivo:** escrever as regras, a elegibilidade e a verificação do que sobe
sempre. Nada corre sozinho ainda.

| Arquivo | O que muda |
|---|---|
| `docs/ops/fila-automatica.md` | novo — procedimento completo (elegibilidade, o que sobe, exceções, turno da noite, turno do dia, avaliador, placar, pausar e desfazer) |
| `scripts/fila/categorias_que_sobem.py` | novo — lê o que a branch alterou e diz que categorias sensíveis tocou |
| `scripts/fila/tests/test_categorias_que_sobem.py` | novo — 94 casos |
| `CLAUDE.md` | secção "Fila automática"; regra de push passa a prever a branch `claude/<slug>` |
| `docs/implementations/_template-implementacao.md`, `_guia-documentar-implementacao.md` | linha `**Autonomia:**`; nota sobre sessões da fila; aviso ao começar à mão um item que estava na fila |
| `docs/implementations/_processo-graduacao-implementacao.md` | Passo 5b: triagem sem perguntas em sessões da fila |
| `docs/implementations/README.md`, `docs/ops/README.md`, `docs/plans/README.md` | estados novos, índice, `Prioridade: por definir` |
| `docs/ops/local-dev.md` | bloco do `/statusplans-avancar`: linha `**Autonomia:** noturna` nos ficheiros que cria |
| `docs/implementations/feat-backup-volumes-producao.md` | novo item na fila |
| `docs/implementations/feat-fila-turno-da-noite.md`, `feat-fila-turno-do-dia-avaliador.md`, `feat-fila-poder-de-merge.md`, `feat-fila-arranque-de-dia-e-painel.md` | novos itens na fila (Fases 2 a 5 do plano) |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `1f5e190` | contrato da fila: procedimento, script + testes, guias e itens seguintes |

**Detalhes do commit `1f5e190`:**
- `docs/ops/fila-automatica.md` — regras completas; tabela "Estado atual" com o poder de merge desligado
- `scripts/fila/categorias_que_sobem.py` — `classificar` (caminhos e linhas alteradas → categorias), `ler_diff` (separa ficheiros e linhas do `git diff -U0`), `avaliar_ramo` (compara `base...ramo`), `main` (saída 0/1/2, texto ou `--json`)
- `scripts/fila/tests/test_categorias_que_sobem.py` — tabelas de casos por categoria + repositório temporário para a ponta a ponta
- `CLAUDE.md` — secção "Fila automática" no fim; regra de push automático
- guias de `docs/implementations/`, `docs/ops/local-dev.md`, `docs/plans/README.md` — linha `Autonomia`, exceções das sessões da fila, `Prioridade: por definir`

### Relatório da Fase 1 — o que mudou na prática

**Antes:** não havia regras para o Claude trabalhar a fila sem ti, nem forma de
marcar um item como "não pegar", nem nada que travasse uma mudança sensível.
**Agora:** as regras estão escritas num só sítio; qualquer item da fila é
elegível salvo os que marcares `manual`; e existe um programa que olha para o
que uma branch alterou e diz se toca em pagamento, envio a clientes, estrutura
da base de dados, instruções da IA ou nas regras do próprio agente. **Ainda
nada corre sozinho** — a rotina da noite e o turno do dia são os itens
seguintes.
**Para validar:** Cenários T1 e T2 (já validados, são automáticos) e D1 (precisa de ti).

---

## Checks de Validação

Prefixos: `T` = teste automático, `D` = decisão do utilizador.

### Cenário T1 — Bateria de testes do script
- [x] Na worktree: `python -m pytest scripts/fila/tests -q`
- [x] Confirmar: todos passam
- **Validado em:** 04/10/2026 — 94 testes passam (caminhos por categoria,
  caminhos que não sobem, linhas alteradas, leitura do diff, e ponta a ponta
  num repositório temporário, incluindo ficheiro apagado e base inexistente →
  código 2)

### Cenário T2 — O script acerta em branches reais
- [x] Correr `python scripts/fila/categorias_que_sobem.py --base main --ramo <branch>` em quatro branches em andamento
- [x] Confirmar: o resultado bate com o que cada uma faz
- **Validado em:** 04/10/2026 — imagem do hero: não sobe; correção dos testes
  do backend-crm: não sobe; disponibilidade em dois campos: sobe (coluna nova
  no AI Profile + `decision_engine.py`); verificador de comandos: sobe (regras
  do próprio agente)

### Cenário D1 — Três pontos que foram além do plano aprovado
- [ ] `CLAUDE.md` entra na categoria fixa "regras do próprio agente" (o plano
      não o listava). Consequência: uma graduação que acrescente uma linha ao
      `CLAUDE.md` sobe para ti.
- [ ] Quando não sobra nenhum item em `docs/implementations/`, a noite pega o
      primeiro item `Prioridade: ALTA` de `docs/plans/` (MÉDIA, BAIXA e "por
      definir" nunca).
- [ ] As Fases 2 a 5 do plano passaram a itens próprios na fila, em vez de
      fases deste ficheiro, para as regras chegarem já a `main`.

---

## A fazer no merge para `main`

- Atualizar o ficheiro local `.claude/commands/statusplans-avancar.md` na
  pasta principal com o bloco novo de `docs/ops/local-dev.md` (o comando não é
  versionado).

---

## Ajustes Possíveis Pós-Implementação

- **Dependências (`requirements.txt`, `package.json`, lockfiles) não sobem.**
  Um pacote novo é uma porta de entrada para código de terceiros; pode
  justificar uma sexta categoria.
- **O script reconhece pelo nome e por padrões de texto.** Um ficheiro novo de
  pagamento com um nome que não diga "efi", "checkout", "plan"… só é apanhado
  se as linhas o denunciarem. A lista de padrões precisa de acompanhar o código.
- **Prompt no meio de um texto longo:** uma linha alterada dentro de um prompt
  de várias linhas, num ficheiro que não esteja na lista, não é reconhecida.
  Os ficheiros que hoje têm prompts estão todos na lista.
- **Push de documentação em `main` dispara redeploy no Railway?** Por
  confirmar; o placar do modo sombra vai gerar esses pushes.
