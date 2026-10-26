# Na confirmação, a marcação grava uma proposta antiga (e não a última aceite)

**Branch:** (a criar)
**Status:** Aguardando Plan Mode
**Autonomia:** manual
**Origem:** bateria PROD07 do agente Sensi Vitae (26/10/2026), cenário `p-cedo-tarde` — investigação em
`.claude/agentes/sensi-vitae/README.md`, secção "PROD07" (bug B).
**Plano de execução:** [`docs/plans/plano-sprint-2026-10-26-agenda-sensi-vitae.md`](../plans/plano-sprint-2026-10-26-agenda-sensi-vitae.md) — P2

---

## Motivação

O cliente pediu quinta às 21h; a Lara propôs **quinta 18h30 com o Daniel**; o cliente recusou e
pediu sexta às 9h; a Lara propôs **sexta 11h com a Val**; o cliente respondeu "Pode ser sim, marca
aí!" — e foi gravado e confirmado **quinta 18h30 com o Daniel**. O cliente apareceria no dia errado,
com o terapeuta errado. É o mesmo tipo de dano do erro de datas já corrigido
(`fix-data-dia-semana-agendamento`), por outro caminho.

## Causa confirmada (investigação de 26/10/2026)

1. **O histórico estava certo.** Em produção (`messages`, lead 105) as 8 mensagens estão completas e
   na ordem certa, incluindo a proposta de sexta 11h (id 922). Não é falha de contexto.
2. **Quem escolhe o horário a gravar é a Filha, sozinha.** No turno da confirmação a Mãe marca
   `meeting_scheduled=true`; a Filha de agendamento recebe `_build_meeting_already_booked_block()`
   (`backend-executors/app/services/decision_engine.py:1830`), que diz "o lead já aceitou o dia e o
   horário … preencha `meeting_datetime_candidate` … com o dia e a hora aceites" — sem dizer **qual**
   foi a última proposta. A Filha devolveu `meeting_datetime_candidate=2026-10-29T18:30:00` e escreveu
   a confirmação com 18h30 (rasto do turno 3 em `tentativas/20261026-1059-PROD07-p-cedo-tarde.json`).
   No turno 2 ela própria tinha devolvido `2026-10-30T11:00:00` — mas nada guarda isso.
3. **Nada no código guarda "a última proposta feita ao cliente".** Procurado em `decision_engine`,
   `meeting_scheduler`, `meeting_date_guard`, `requested_slot` e no backend-crm: o
   `meeting_datetime_candidate` de cada turno só existe no `decision_trace` desse turno.
4. **A proteção de datas não apanha este caso.** `meeting_date_guard.reconcile_meeting_date`
   (linhas 273–340), com `is_confirmation=True`, só exige que o dia do candidato "já tenha sido
   falado na conversa" — "quinta" tinha sido (pelo cliente, no 1.º turno), por isso passou. E a hora
   nunca é conferida.
5. `meeting_scheduler.handle_meeting_scheduled` grava o que vier no candidato
   (`parse_meeting_candidate`, fuso do perfil → UTC — esta parte está correta).

**Caso vizinho no mesmo bloco (PROD07 `p-fora-horario`):** o cliente disse "11h na segunda tá bom!
Pode marcar." sem ter dito tipo, duração nem nome; a Mãe marcou `meeting_scheduled=true`, o bloco
"MARCAÇÃO JÁ GRAVADA" mandou escrever a confirmação final, e a Filha inventou "Massagem Relaxante -
60 min". As instruções da conta (passo 3: "precisa de dia e hora, tipo, duração e nome") perdem para
esse bloco, que diz que ele "prevalece".

## Opções de solução

| # | Opção | Prós | Contras |
|---|---|---|---|
| 1 | **Ler a última proposta do histórico**: no turno da confirmação, extrair dia+hora das mensagens do agente desde a penúltima mensagem do lead (reusar `meeting_date_guard.latest_day_word` / `requested_slot.requested_time`) e (a) dizê-la à Filha no bloco "MARCAÇÃO JÁ GRAVADA" como facto, (b) conferir o candidato com ela depois da resposta | Sem coluna nova; o histórico já chega igual ao Playground e ao WhatsApp; segue o padrão de "o código decide, a Filha recebe o facto" de `requested_slot` | Ler horas de texto livre falha quando a mensagem tem duas opções ("11h ou 15h") — nesse caso conferir contra o conjunto, não contra uma |
| 2 | Guardar o `meeting_datetime_candidate` de cada turno com `meeting_proposed=true` no lead (coluna nova, lida via `enrich_context_bundle`) | Exato quando a Filha preenche o candidato | Estrutura da BD; a Filha nem sempre preenche o candidato ao propor 2 opções; precisa de paridade nas duas rotas que gravam o estado pós-decisão |
| 3 | Só reforçar o texto do bloco ("use a ÚLTIMA proposta") | Mínimo | Instrução de prompt para uma regra que o código pode verificar — contra os princípios em `docs/architecture/prompt-engineering-principles.md` |

**Recomendada:** opção 1. Regra de conferência proposta: se o lead, na mensagem de confirmação, não
disse ele próprio um dia/hora novo, o candidato tem de bater com uma das opções da última proposta do
agente; se bater com exatamente uma → segue; se não bater e a última proposta tem uma só opção →
corrigir candidato e texto para essa opção (como o `meeting_date_guard` já corrige o dia); se houver
várias opções e nenhuma bate → não gravar e perguntar qual prefere.

## Proposta de fases (a confirmar no Plan Mode)

- **Fase 1 — Última proposta como facto e conferência:** função nova (ex. em `meeting_date_guard.py`
  ou módulo `meeting_proposal.py`) que extrai a última proposta; o bloco "MARCAÇÃO JÁ GRAVADA" passa
  a nomeá-la; uma verificação depois da resposta da Filha (ao lado de `_apply_meeting_date_guard`,
  chamado em `decision_engine.py:4732` e `:5491`) confere e corrige o candidato.
- **Fase 2 — Não gravar sem os dados da marcação:** quando a Mãe marca `meeting_scheduled=true` mas
  faltam dados que a conta exige (tipo/duração/nome), o bloco deixa de mandar confirmar e a Filha
  pede o que falta; a gravação fica para o turno seguinte. Ponto aberto para o Plan Mode: de onde vêm
  os "dados exigidos" (hoje só existem em texto livre nas instruções da conta — avaliar um campo do
  AI profile vs. só a duração, que o código já sabe ler em `requested_slot.requested_duration`).

## Área do sistema

- `backend-executors/app/services/decision_engine.py` (`_build_meeting_already_booked_block`, chamada
  da conferência junto de `_apply_meeting_date_guard`) — **instruções da IA**
- `backend-executors/app/services/meeting_date_guard.py` (ou módulo novo)
- Não toca em `meeting_scheduler.py` (lê o candidato já conferido) — não colide com a Fase 2 de A.
- Docs: `docs/architecture/agenda.md`, `docs/prompts_llms.md` (bloco "MARCAÇÃO JÁ GRAVADA")

## Riscos

- Toca instruções da IA → só junta a `main` com o "sim" do utilizador. Ler antes
  `docs/architecture/prompt-engineering-principles.md` e `docs/prompts_llms.md`.
- Mesma função de construção do prompt de agendamento que `fix-agendamento-le-fluxo-de-venda.md` e a
  worktree `fix+disponibilidade-campo-duplo-sentido` alteram (blocos diferentes, mas o mesmo
  `_build_child_prompt_agendamento`) — ver ordem no plano.
- Leitura de horas em texto: mensagens com duas opções, "às 11h com a Val ou às 15h com o Daniel".

## Como validar

- Testes unitários da extração: uma opção, duas opções, proposta com dia por extenso e com dd/mm.
- Bancada: `python simular.py p-aceita-2a B1` (cenário novo: recusa a 1ª proposta, aceita a 2ª com
  "Pode ser sim, marca aí!") → gravado o horário da 2ª. `python simular.py p-cedo-tarde B1` → gravado
  sexta 11h.
- Fase 2: `python simular.py p-fora-horario B2` → pergunta o tipo/duração antes de gravar.
- Regressão: `python simular.py p-micas B1`, `python simular.py p-ricardo B1` (aceites à primeira
  continuam a gravar no turno certo). Depois do deploy, os mesmos com `--prod`.
