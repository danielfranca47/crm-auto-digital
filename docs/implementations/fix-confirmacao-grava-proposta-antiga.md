# Na confirmação, a marcação grava uma proposta antiga (e não a última aceite)

**Branch:** `worktree-fix+confirmacao-grava-proposta-antiga` (worktree `.claude/worktrees/fix+confirmacao-grava-proposta-antiga`)
**Status:** Em andamento — Fase 1 implementada, por validar; Fase 2 por implementar
**Sobe ao utilizador:** sim — toca instruções da IA; só junta a `main` com o "sim" do utilizador
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

## Evidência adicional — confirmação que não grava nada (26/10/2026)

Vinda da graduação de `fix-conflito-horario-comparado-como-texto.md` ("Ajuste possível", juntado aqui por
decisão do utilizador): no turno da confirmação a Mãe marca `meeting_scheduled=true` e a Filha escreve
"Experiência Agendada", mas **não** devolve `meeting_datetime_candidate` → o executor regista
`event=meeting_datetime_source source=none_child_no_candidate` e `missing_start_at`, e **nada é gravado** —
o cliente fica a achar que tem marcação.

- Bancada local, `p-val-17h` (`tentativas/20261026-1208-A1-ocupado-p-val-17h.md`): 3.º turno ("Sim, pode
  confirmar!"), rota `pre-agendamento`, `reason=…|scheduling_agent_closing_disabled:pre-agendamento`.
- Produção, `pos-marcacao` (`tentativas/20261026-1234-PROD-A1-pos-marcacao.md`): 2.º turno ("Sim, confirmo")
  em `pre-agendamento`, sem evento de agenda.

Mesmo turno e mesmo bloco ("MARCAÇÃO JÁ GRAVADA" / candidato da Filha) que este item já vai reescrever —
incluir no Plan Mode um check: "confirmação com `meeting_scheduled=true` sem candidato nunca responde
'Experiência Agendada'".

---

## Problemas Identificados (estado anterior)

1. **A Filha escolhia sozinha o horário a gravar:** `_build_meeting_already_booked_block()`
   (`decision_engine.py`) dizia "preencha com o dia e a hora aceites" sem dizer quais.
2. **Nada lia "a última proposta":** o candidato de cada turno só ficava no `decision_trace` desse
   turno.
3. **A conferência de datas não via a hora:** `meeting_date_guard.reconcile_meeting_date` só
   confere o dia, e aceita qualquer dia já falado.
4. **Pré-agendamento sem candidato:** a confirmação cai em pré-agendamento quando a Mãe diz
   "closing" (`_enforce_scheduling_agent_no_closing` devolve a rota à categoria atual); o prompt
   dessa fase não tinha o bloco nem `meeting_datetime_candidate` no schema → "Experiência
   Agendada" sem nada gravado (`source=none_child_no_candidate`, `missing_start_at`).
5. **Grava com dados inventados** (p-fora-horario) — Fase 2.

---

## Abordagem

Opção 1 da tabela acima: ler a última proposta do histórico, dá-la à Filha como facto, e conferir
o candidato em código depois da resposta.

```
history + mensagem atual
  → meeting_proposal.last_proposal()   opções da última mensagem do agente com horas
                                        (ou a hora que o lead disse)
  → meeting_proposal.accepted_slot()   single_option | matched_option | ambiguous |
                                        lead_stated | none
  → prompt (apresentação / agendamento / pré-agendamento):
        bloco "MARCAÇÃO JÁ GRAVADA" com o horário aceite e o candidato exato
        (ambíguo → "pergunte qual das opções")
  → _apply_meeting_confirmation_guard (depois da Filha, antes do meeting_scheduler)
        aceite único ≠ candidato / candidato em falta → corrige candidato + texto
        ambíguo e candidato fora das opções → não grava, pergunta "prefere X ou Y?"
        lead_stated / none → sem alteração
```

`meeting_proposal.py` foi desenhado para o item E (`fix-remarcacao-grava-contraproposta.md`):
`last_proposal` + `accepted_slot` respondem "o candidato da Filha é uma contraproposta que o
cliente ainda não aceitou?" sem alteração ao módulo.

---

## Plano de Implementação

### Fase 1 — Última proposta como facto + conferência nas 3 rotas

**Objetivo:** no turno da confirmação, gravar sempre o horário que o cliente aceitou — ou
perguntar, quando há várias opções e ele não escolheu.

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/meeting_proposal.py` (novo) | `last_proposal`, `accepted_slot`, `options_in_text`, `reconcile_confirmation`, `describe`, `candidate_iso`, `ask_which_text` |
| `backend-executors/app/services/decision_engine.py` | `_confirmation_fact`, `_professional_names`; `_build_meeting_already_booked_block(accepted)` com o facto / variante ambígua; pré-agendamento ganha bloco + "SINAIS DA MARCAÇÃO" quando há horário proposto; `_apply_meeting_confirmation_guard` chamado logo após `decision_trace["is_phase_entry"]` |
| `backend-executors/tests/test_meeting_proposal.py` (novo) | leitura da proposta com as conversas reais PROD07 |
| `backend-executors/tests/test_meeting_confirmation_guard.py` (novo) | conferência, integração com o decision_engine, prompts |
| `docs/architecture/agenda.md` | secção "Turno da confirmação" |
| `docs/prompts_llms.md` | bloco "MARCAÇÃO JÁ GRAVADA" (facto, pré-agendamento, variante ambígua) |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `27b1aa9` | Leitura da última proposta, facto no bloco das 3 rotas, conferência do candidato |

### Relatório da Fase 1 — o que mudou na prática

**Antes:** quando o cliente dizia "pode marcar", a IA escolhia sozinha que horário gravar — e às
vezes gravava uma proposta que ele já tinha recusado. Se a conversa estivesse na fase de
pré-agendamento, a IA dizia "Experiência Agendada" mas nada ficava na agenda.
**Agora:** o sistema lê da conversa qual foi o último horário proposto e qual o cliente aceitou,
diz isso à IA, e confere a resposta antes de gravar: se a IA trocar o horário, o sistema corrige a
marcação e a mensagem; se houver duas opções e o cliente não disse qual, pergunta "prefere X ou
Y?" em vez de gravar. Funciona também na fase de pré-agendamento.
**Para validar:** Cenários P2, P3 e P5 (bancada local) e, depois do deploy, C1.

### Fase 2 — Não gravar sem duração/serviço

**Objetivo:** com `meeting_scheduled=true` e a duração por saber (não dita pelo lead, não na
proposta aceite, não única na tabela de serviços), perguntar em vez de gravar. Nome do cliente e
campo "dados exigidos" no AI profile ficam fora (ver Ajustes Possíveis).

---

## Checks de Validação

### Cenário P1 — testes unitários
- [x] `pytest tests/test_meeting_proposal.py tests/test_meeting_confirmation_guard.py` — 29 passam
- [x] suite completa do backend-executors — 434 passam
- **Validado em:** 26/10/2026 — local, worktree

### Cenário P2 — bancada local: aceita a 2.ª proposta (Fase 1)
- [ ] Setup: bancada `.claude/agentes/sensi-vitae` com o código desta branch no backend-executors
- [ ] `python simular.py p-aceita-2a B1` → gravado o horário da 2.ª proposta
- [ ] `python simular.py p-cedo-tarde B1` → gravado sexta 11h com a Val

### Cenário P3 — bancada local: confirmação em pré-agendamento grava (Fase 1)
- [ ] `python simular.py p-val-17h B1` → evento agenda `created` no turno da confirmação; nunca
  "Experiência Agendada" sem evento

### Cenário P4 — bancada local: dados em falta (Fase 2)
- [ ] `python simular.py p-fora-horario B2` → pergunta tipo/duração antes de gravar

### Cenário P5 — regressão
- [ ] `python simular.py p-micas B1` e `python simular.py p-ricardo B1` → gravam no turno certo

### Cenário C1 — produção (`--prod`)
- [ ] Antes: confirmar no Railway que o deploy do backend-executors **e** do worker passou
- [ ] Os cenários P2–P5 com `--prod`

---

## Ajustes Possíveis Pós-Implementação

- Leitura de horas em texto livre: formatos raros ("ao meio-dia", "às onze") não são lidos — sem
  leitura, o guard não mexe (comportamento anterior).
- O texto da pergunta "Só para confirmar: prefere X ou Y?" é fixo em português, sem o tom da conta.
- Nome do cliente e "dados exigidos" configuráveis no AI profile (Fase 2 só trata duração/serviço).

