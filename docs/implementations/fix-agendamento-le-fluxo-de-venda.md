# Pré-agendamento e Agendamento passam a ler as orientações do Fluxo de Venda

**Branch:** (a criar)
**Status:** Aguardando Plan Mode
**Autonomia:** manual
**Origem:** `docs/plans/fluxo-vendas-melhorias-futuras.md` — M14 (Prioridade ALTA), reforçado pela bateria
PROD07 do agente Sensi Vitae (26/10/2026), problema C.
**Plano de execução:** [`docs/plans/plano-sprint-2026-10-26-agenda-sensi-vitae.md`](../plans/plano-sprint-2026-10-26-agenda-sensi-vitae.md) — P4

---

## Motivação

Na fase em que o cliente já quer marcar, a Lara (Sensi Vitae) assume o tipo de massagem sem
perguntar, diz que "a relaxante só tem 60 min" em vez de oferecer a Lomi Lomi de 90 min, e ignora
perguntas quando o cliente faz várias na mesma mensagem. Parte disto resolve-se na configuração
(versão c14 — ver o plano), mas há um limite de código: **as duas fases onde a marcação acontece não
recebem as orientações do Fluxo de Venda**, por isso o dono do negócio não consegue dar uma regra só
para essas fases — tudo tem de ir para as instruções gerais, que valem para todas as fases e competem
com o roteiro fixo de cada fase.

## Causa confirmada (investigação de 26/10/2026)

1. `_build_child_prompt_pre_agendamento()` (`backend-executors/app/services/decision_engine.py:4267`)
   e `_build_child_prompt_agendamento()` (`:4438`) não chamam
   `_build_sales_flow_phases_block(_evaluate_sales_flow_phases(...))` (`:1007`, `:580`); as outras 5
   fases chamam. `docs/architecture/sales-flow.md` diz que "todas as fases" injetam os blocos
   `orientacao`. Confirmado em teste T03 (README da bancada): um bloco em p3b nunca chegou à IA.
2. **O roteiro fixo da fase compete com as instruções da conta.** PROD07 `p-micas`, turno 3
   ("Quero uma massagem relaxante de 90 min"): a Mãe mandou para **pré-agendamento**, cujo roteiro
   fixo (`decision_engine.py:4340-4371`) é "capturar um dia estimado / pedir permissão de check-in" e
   diz "NÃO repita preços". As instruções da conta (que mandam explicar Clássica vs Exótica e oferecer
   a Lomi Lomi de 90) entram depois, como bloco genérico (`_build_custom_instructions_block`, `:1199`).
   Resultado: "A massagem relaxante que mencionou é apenas de 60 min".
3. A base de conhecimento da conta está certa (produção, `knowledge_items` do user 4: "Relaxante Exótica
   (Lomi Lomi) 90 min 110 €") — o erro não vem dos dados.
4. **A verificar no Plan Mode:** em PROD07 `p-ruben` o cliente disse "Pode enviar a tabela" num turno que
   a Mãe mandou para agendamento, e a tabela (gatilho de intenção em p2 + 3 imagens) não foi enviada.
   Pode ser o mesmo limite (blocos de ação também não avaliados nestas fases) — o M14 já pede para
   conferir os blocos de ação em p3a/p3b.

## O que fica para a configuração (c14) e o que é código

| Sintoma PROD07 | Configuração (c14) | Código |
|---|---|---|
| Assume Clássica/Exótica sem perguntar (`p-micas`, `p-ruben`, `p-fora-horario`) | Regra própria "antes de propor horário, confirme o tipo" fora do parágrafo de horários | Esta implementação: poder pôr essa regra como orientação de p3a/p3b, perto do roteiro da fase |
| "Relaxante só tem 60 min" (`p-micas`) | Frase pronta: "a de 90 min é a Relaxante Exótica (Lomi Lomi), 110 €" | Idem + rever o "NÃO repita preços" do roteiro fixo do pré-agendamento |
| Ignora boxer/duche (`p-ruben`) | Exceção à regra "uma ou duas frases": responder a cada pergunta numa frase | — (deve bastar a configuração; reavaliar depois do c14) |
| Grava sem tipo/duração/nome (`p-fora-horario`) | Reforço no passo 5 | Já coberto pela Fase 2 de `fix-confirmacao-grava-proposta-antiga.md` (é o bloco "MARCAÇÃO JÁ GRAVADA" que manda confirmar) |

## Opções de solução

| # | Opção | Prós | Contras |
|---|---|---|---|
| 1 | **Ligar o bloco do Fluxo de Venda às duas Filhas** (como nas outras fases), com p3a → pré-agendamento e p3b → agendamento, e conferir os blocos de ação | O dono passa a poder dar regras por fase; alinha código e doc | Instruções da IA — risco de mudar respostas em contas com blocos já configurados em p3a/p3b que hoje são ignorados (verificar em produção quantas contas têm blocos aí antes de ligar) |
| 2 | Esconder p3a/p3b no construtor do Fluxo e corrigir o doc | Honesto e pequeno | Não resolve o problema da Sensi Vitae |

**Recomendada:** 1, com a verificação prévia em produção (só leitura) de que contas têm blocos em
p3a/p3b, para avisar o utilizador do que muda nelas.

## Área do sistema

- `backend-executors/app/services/decision_engine.py` (`_build_child_prompt_pre_agendamento`,
  `_build_child_prompt_agendamento`, `decide()` onde o resultado do Fluxo de Venda é usado) — **instruções da IA**
- `docs/architecture/sales-flow.md`, `docs/prompts_llms.md`
- Frontend: nenhum previsto (p3a/p3b já aparecem no construtor)

## Dependências e sobreposição

- **Worktree `feat+temperatura-respostas-ia`** cria `_SALES_FLOW_INJECTING_CHILD_ROUTES` =
  {recepcao, qualification, apresentation, follow-up, closing} e lê-o em `decide()` para a
  temperatura baixa das orientações "seguir à risca". Esta implementação tem de **acrescentar
  pre-agendamento e agendamento a esse conjunto** — por isso deve começar depois dessa worktree
  estar em `main`.
- **Worktree `fix+disponibilidade-campo-duplo-sentido`** altera o mesmo `_build_child_prompt_agendamento`
  (bloco "DISPONIBILIDADE DO PROFISSIONAL") — começar depois dela estar em `main`.
- **`fix-confirmacao-grava-proposta-antiga.md`** altera o mesmo construtor (bloco "MARCAÇÃO JÁ
  GRAVADA") — começar depois dela.

## Riscos

- Instruções da IA → só junta a `main` com o "sim" do utilizador. Ler antes
  `docs/architecture/prompt-engineering-principles.md` e `docs/prompts_llms.md`.
- Posição do bloco no prompt: as orientações de fase têm de ficar antes dos blocos "de facto" do fim
  (`_build_agenda_fact_block`, "MARCAÇÃO JÁ GRAVADA"), que precisam de continuar a vencer.

## Como validar

- Testes unitários: um bloco `orientacao` em p3a aparece no prompt de pré-agendamento; em p3b no de
  agendamento; contas sem blocos → prompt igual ao de hoje.
- Bancada (com c14 aplicada e uma orientação de teste em p3b): `python simular.py p-relax-sem-tipo C1`,
  `python simular.py p-micas C1`, `python simular.py p-varias-perguntas C1`, `python simular.py p-ruben C1`
  → pergunta o tipo, oferece a Lomi Lomi de 90, responde a todas as perguntas, envia a tabela quando pedida.
- Regressão: `python simular.py p-ricardo C1`, `python simular.py p-cedo-tarde C1`, `python simular.py pos-marcacao C1`.
