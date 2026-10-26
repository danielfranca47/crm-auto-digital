# Remarcação grava a contraproposta do agente sem o cliente aceitar

**Branch:** `worktree-fix+remarcacao-grava-contraproposta`
**Status:** Em andamento
**Autonomia:** manual
**Origem:** "Ajuste possível" na graduação de `fix-conflito-horario-comparado-como-texto.md` (26/10/2026)
— visto na bancada local `.claude/agentes/sensi-vitae`, cenário `pos-marcacao`
(`tentativas/20261026-1211-A1-ocupado-pos-marcacao.md` + `.json`) e em produção
(`tentativas/20261026-1058-PROD07-pos-marcacao.md`).
**Sobe ao utilizador:** sim — toca instruções da IA (prompt de gestão pós-marcação). Só se junta a
`main` com o "sim" do utilizador.

---

## Motivação

Cliente com sessão marcada (ter 27/10 14h, Val) escreve "Afinal preciso de remarcar para quinta às 15h".
Quinta 15–16h está ocupada. A Lara responde "Esse horário já está ocupado. Podemos marcar a sessão para
quinta-feira às 16h15? … Que acha?" — e, **no mesmo turno**, a marcação real é mudada para quinta 16h15
(evento `rescheduled`), antes de o cliente responder. Além disso, 16h15 está fora do limite da Val (sessão
de 60 min tem de começar até às 16h). O cliente pode aparecer à hora antiga, ou a terapeuta ficar com uma
sessão que não pode dar.

Em produção (PROD07) a variante foi outra: a Filha deixou como candidato o próprio horário pedido (15h,
ocupado), o CRM recusou (409) e o cliente recebeu duas explicações seguidas — "[auto] … o horário
confirmado ficou indisponível. Poderia sugerir um novo horário?" e a da Lara, que já propunha 16h.

---

## Problemas Identificados (estado anterior) (*)

1. **Remarca no turno da contraproposta:** a gestão pós-marcação (`_decide_post_meeting_management`,
   `decision_engine.py`) só confere o dia do candidato (`_apply_meeting_date_guard`); não confere se o
   candidato é o horário que o cliente pediu ou aceitou. A conferência da confirmação nova
   (`_apply_meeting_confirmation_guard`) não corre neste caminho.
2. **Sem conferência de agenda/horário do terapeuta antes de remarcar:**
   `meeting_scheduler.handle_meeting_cancel_or_reschedule` aplica qualquer candidato; a única barreira é
   o 409 do CRM. O horário do profissional (`professional_hours.py`) nunca é conferido aqui.
3. **Sugestão calculada pela IA:** com o horário pedido ocupado, o facto da agenda
   (`requested_slot.build_agenda_fact_block`) só diz "proponha o horário livre mais próximo que caiba no
   horário de atendimento" — a IA faz a conta e erra (16h15).
4. **Mensagem de conflito duplicada e errada:** no 409 da remarcação, a mensagem de conflito é enviada
   **além** do texto da Lara (runner e Playground), e diz "o horário que acabou de confirmar ficou
   indisponível" — numa remarcação a sessão original continua de pé.

---

## Abordagem (*)

```
Filha (gestão pós-marcação) → candidato + meeting_reschedule_requested
  → _apply_meeting_date_guard (dia)
  → _apply_meeting_reschedule_guard (NOVO)
      ├─ candidato = hora que o cliente escreveu agora, ou opção que ele aceitou da última proposta
      │     (meeting_proposal.reschedule_origin, reutiliza last_proposal + accepted_slot)
      │     ├─ livre na agenda e cabe no horário do terapeuta → remarca (como hoje)
      │     └─ ocupado / fora do horário → não remarca; texto "remarcado" é trocado por frase fixa
      └─ candidato é proposta da própria Lara neste turno → não remarca; o texto (a contraproposta)
            segue; quando o cliente aceitar, o turno seguinte remarca
  → handle_meeting_cancel_or_reschedule
      └─ 409 (corrida) → substitui o texto da Lara pela mensagem de remarcação (sessão original
            mantém-se), sem segunda mensagem
```

Na Fase 2, o facto da agenda "ocupado" passa a trazer o início livre mais próximo que cabe na agenda e
no horário do terapeuta (calculado em código), e o prompt de gestão pós-marcação diz que, nesse caso, a
remarcação só se grava quando o cliente aceitar.

---

## Plano de Implementação (*)

### Fase 1 — Conferência em código

**Objetivo:** a marcação só muda quando o cliente pediu ou aceitou aquele horário, e ele está livre e
cabe no horário do terapeuta; o 409 deixa de gerar mensagem duplicada.

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/meeting_proposal.py` | `reschedule_origin(...)`: o candidato é a hora dita pelo cliente, a opção aceite, ou contraproposta da Lara |
| `backend-executors/app/services/decision_engine.py` | `_apply_meeting_reschedule_guard` (origem + agenda + horário do terapeuta), chamado em `_decide_post_meeting_management` |
| `backend-executors/app/services/meeting_scheduler.py` | 409 na remarcação: escreve a mensagem de remarcação em `decision.message_text` e devolve `None` |
| `backend-executors/tests/test_meeting_reschedule_guard.py` | testes novos |
| `backend-executors/tests/test_meeting_cancel_reschedule_action.py` | teste do 409 atualizado |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `8c3a364` | Conferência da remarcação (origem + agenda + horário do profissional) e 409 sem 2.ª mensagem |

**Detalhes do commit `8c3a364`:**
- `meeting_proposal.py` — `reschedule_origin` (`lead_stated` / `accepted` / `counter_proposal`),
  `announces_reschedule`, `reschedule_unavailable_text`, `reschedule_confirm_text`
- `decision_engine.py` — `_apply_meeting_reschedule_guard` + `_current_meeting`, chamados em
  `_decide_post_meeting_management` depois do date guard
- `meeting_scheduler.py` — 409 em `handle_meeting_cancel_or_reschedule` escreve a frase em
  `decision.message_text` e devolve `None`
- `docs/architecture/agenda.md` — "Cancelamento e reagendamento via IA"
- Testes: 448 passam em `backend-executors/tests` (9 novos em `test_meeting_reschedule_guard.py`)

### Relatório da Fase 1 — o que mudou na prática

**Antes:** quando o cliente pedia para remarcar para um horário ocupado, a Lara propunha outro horário
e a marcação era logo mudada para essa proposta, mesmo fora do horário da terapeuta e antes de o cliente
responder. Se o CRM recusasse, o cliente recebia duas mensagens a explicar a mesma coisa.
**Agora:** a marcação só muda quando o cliente pediu ou aceitou aquele horário, e só se ele estiver livre
e couber no horário da terapeuta. Enquanto isso, a sessão antiga continua de pé. Se o CRM recusar à
última hora, sai uma só mensagem: "esse horário já não está disponível; a sua sessão de … mantém-se".
A Lara ainda pode **propor** um horário fora do horário da terapeuta (isso trata a Fase 2), mas esse
horário já não é gravado.
**Para validar:** Cenários P1 (sem evento `rescheduled` nem "[auto]") e P2, abaixo. O P1 "propõe um
horário que cabe" só fica garantido depois da Fase 2.

### Fase 2 — Sugestão calculada + prompt

**Objetivo:** com o horário pedido ocupado, a Lara propõe um horário que cabe (calculado em código) e
não anuncia remarcação antes de o cliente aceitar.

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/professional_hours.py` | início livre mais próximo que cabe (agenda + horário), passos de 15 min |
| `backend-executors/app/services/requested_slot.py` / `decision_engine.py` | facto "ocupado" com a sugestão calculada (marcação nova e remarcação) |
| `backend-executors/app/services/decision_engine.py` | frase na regra de REAGENDAMENTO de `_build_child_prompt_meeting_management` |
| `docs/prompts_llms.md`, `docs/architecture/pipeline-phases.md` | refletir o estado novo (`agenda.md` já foi na Fase 1) |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `52f6a93` | Alternativa livre calculada em código (agenda + horário) e regras de remarcação no prompt |

**Detalhes do commit `52f6a93`:**
- `professional_hours.py` — `nearest_free_start` (mesmo dia, inícios de 15 em 15 min + o último
  possível, livre na agenda, dentro do horário; empate → o mais tarde)
- `requested_slot.py` — `build_agenda_fact_block(..., alternative=, hours_known=)`: facto "ocupado"
  com "proponha <hora> com <profissional> … proponha exatamente este" ou "proponha outro dia"
- `decision_engine.py` — `_build_agenda_fact_block` usa a alternativa em "ocupado" e em "fora do
  horário" (antes, a sugestão de "fora" ignorava a agenda); prompt de gestão pós-marcação: duas regras
  novas (ocupado/fora → propor sem remarcar, com exemplo ✅; lead aceita a proposta → remarcar)
- `docs/prompts_llms.md` (1.4.5 + regras de remarcação), `docs/architecture/pipeline-phases.md`
- Testes: 453 passam (5 novos em `test_professional_hours.py`)

### Relatório da Fase 2 — o que mudou na prática

**Antes:** quando o horário pedido estava ocupado, era a IA que escolhia a alternativa a propor, e
podia escolher uma que não cabia no horário da terapeuta (16h15 com a Val).
**Agora:** o sistema calcula o horário livre mais próximo que cabe na agenda e no horário da
terapeuta, e a Lara propõe exatamente esse. Se nesse dia não houver nenhum, pede outro dia. Na
remarcação, a Lara propõe sem mudar nada e diz que a sessão antiga se mantém. Quando o cliente
responde "pode ser", remarca. Isto vale também para marcações novas com o horário ocupado.
**Para validar:** Cenários P1, P2, P3 e C1, abaixo.

---

## Fase 3 — Diagnóstico + Correção (26/10/2026)

### Problema identificado

O teste P2 na bancada (`tentativas/20261026-1718-E1-pos-remarca-aceita.md`) mostrou que a Lara propôs
**quinta** às 16h, o cliente respondeu "Pode ser às 16h", e a sessão foi remarcada para **terça** às 16h,
o dia da sessão antiga. A resposta ainda perguntava "Posso confirmar?".

Causas:
1. A Filha seguiu a regra do prompt "só hora, sem dia → mesmo dia da sessão marcada".
   `reschedule_origin` olhava primeiro para "a hora que o cliente escreveu" e por isso deixou passar
   terça às 16h, embora `accepted_slot` desse quinta às 16h como aceite.
2. A frase da Fase 2 "A sua sessão de terça às 14h mantém-se" era lida por `last_proposal` como mais
   uma opção. Com um "Pode ser" sozinho, a aceitação ficaria ambígua e a remarcação seria bloqueada.

### Correção

| Arquivo | Mudança |
|---|---|
| `backend-executors/app/services/decision_engine.py` | `_reschedule_fact` (proposta sem a sessão já marcada) + `_meeting_start`; `_apply_meeting_reschedule_guard`: opção aceite → candidato corrigido com `reconcile_confirmation`; remarcação que segue com texto que não a dá como feita → `reschedule_done_text`; prompt: exceção à regra "só hora → mesmo dia" |
| `backend-executors/app/services/meeting_proposal.py` | `reschedule_origin`: `accepted` antes de `lead_stated`; `reschedule_done_text` |
| `backend-executors/tests/test_meeting_reschedule_guard.py` | 3 casos novos |
| `docs/architecture/agenda.md`, `docs/prompts_llms.md` | conferência em três passos |

### Commits Fase 3

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `512ebfc` | Remarcação aceite grava o dia da proposta; texto "fica remarcada" |

**Detalhes do commit `512ebfc`:** ver tabela acima. Testes: 456 passam em `backend-executors/tests`.

### Relatório da Fase 3 — o que mudou na prática

**Antes:** quando o cliente aceitava a proposta da Lara dizendo só a hora ("pode ser às 16h"), a sessão
podia ir para o dia antigo em vez do dia proposto. Às vezes a Lara ainda pedia confirmação quando a
remarcação já estava feita.
**Agora:** quando o cliente aceita uma proposta, a sessão é remarcada para o dia e a hora dessa
proposta, e a Lara confirma numa frase: "Combinado! A sua sessão fica remarcada para quinta-feira,
29/10, às 16h com Val." Um "Pode ser" sozinho também funciona. Na bancada a IA ainda escreveu terça
nas duas corridas, e foi o código que corrigiu.
**Para validar:** P2 e P2b, abaixo.

---

## Checks de Validação (*)

Bancada `.claude/agentes/sensi-vitae`: core e CRM de `ambiente/codigo`, backend-executors desta
worktree na porta 8102 (com o `.env` da bancada) e evento ocupado qui 29/10 15–16h. O evento é
inserido pelo script `simular_ocupado.py`, porque o `simular.py` apaga as marcações no arranque.

### Cenário P1 — Remarcação para horário ocupado (`pos-marcacao`)
- [x] Turno 4: a Lara diz que quinta 15h está ocupado e propõe um horário que cabe (com a Val, até às 16h)
- [x] Turno 4: **nenhum** evento `rescheduled` e nenhuma mensagem "[auto]"
- [x] Turno 5: a marcação continua ter 27/10 14h
- **Validado em:** 26/10/2026 — `E1` (Fase 2) e `E2` (Fase 3): "quinta às 15h já está ocupado. Pode ser
  quinta às 16h com a Val? A sua sessão de terça às 14h mantém-se"; sem evento; turno 5 "a sua sessão
  de amanhã às 14h mantém-se".

### Cenário P2 — Cliente aceita a contraproposta (`pos-remarca-aceita`, "Pode ser às 16h")
- [x] Evento `rescheduled` para qui 29/10 16h; resposta "fica remarcada para quinta-feira, 29/10, às 16h"
- **Validado em:** 26/10/2026 — `E1` falhou (remarcou para terça às 16h → Fase 3); `E2` ✅. A Filha
  devolveu terça às 16h e o guardrail corrigiu (`event=meeting_reschedule_corrected`).

### Cenário P2b — Cliente aceita só com "Pode ser" (`pos-remarca-pode-ser`)
- [x] Evento `rescheduled` para qui 29/10 16h
- **Validado em:** 26/10/2026 — `E2` ✅ (corrigido pelo guardrail, como no P2).

### Cenário P3 — Regressão marcação nova (`p-aceita-2a`, `p-cedo-tarde`)
- [x] Marcação gravada no horário aceite; sugestões dentro do horário do terapeuta
- **Validado em:** 26/10/2026 — `E1` e `E2`: p-cedo-tarde propõe 18h30 com o Daniel (último início),
  depois grava sexta 11h ou quinta 18h30, conforme o aceite; p-aceita-2a grava quinta 16h/17h.
  Observação fora do âmbito: em `E1` p-aceita-2a, com duas opções e "Pode ser sim", ficou gravada a
  1.ª. É a regra de `fix-confirmacao-grava-proposta-antiga` (candidato que é uma das opções passa).

### Cenário C1 — Playground de produção (`--prod`, depois do deploy)
- [ ] P1 e P3 com `--prod`, com o mesmo resultado

---

## Ajustes Possíveis Pós-Implementação

- `handle_meeting_scheduled` (marcação nova) continua a enviar a mensagem de conflito **além** do texto
  da Filha no 409 — a mesma duplicação pode acontecer numa marcação nova numa corrida.
- A Filha de gestão pós-marcação ignorou a exceção nova do prompt ("hora da sua proposta → dia da
  proposta") nas 2 corridas; quem garante o dia certo é o guardrail. Se a Filha deixar
  `meeting_reschedule_requested=false` num "Pode ser" (aceitação sem pedido de remarcação), nada é
  remarcado — o guardrail não preenche o sinal.
- Com duas opções em aberto e um "Pode ser sim" ambíguo, a marcação nova grava a opção que a Filha
  escolher (regra de `fix-confirmacao-grava-proposta-antiga`).
