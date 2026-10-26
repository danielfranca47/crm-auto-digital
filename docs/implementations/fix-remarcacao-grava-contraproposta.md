# Remarcação grava a contraproposta do agente sem o cliente aceitar

**Branch:** (a criar)
**Status:** Aguardando Plan Mode
**Autonomia:** manual
**Origem:** "Ajuste possível" na graduação de `fix-conflito-horario-comparado-como-texto.md` (26/10/2026)
— visto na bancada local `.claude/agentes/sensi-vitae`, cenário `pos-marcacao`
(`tentativas/20261026-1211-A1-ocupado-pos-marcacao.md` + `.json`).

---

## Motivação

Este item surgiu como 'Ajuste possível' na graduação de `fix-conflito-horario-comparado-como-texto.md`.

Cliente com sessão marcada (ter 27/10 14h, Val) escreve "Afinal preciso de remarcar para quinta às 15h".
Quinta 15–16h está ocupada. A Lara responde "Esse horário já está ocupado. Podemos marcar a sessão para
quinta-feira às 16h15? … Que acha?" — e, **no mesmo turno**, a marcação real é mudada para quinta 16h15
(evento `rescheduled`), antes de o cliente responder. Além disso, 16h15 está fora do limite da Val (sessão
de 60 min tem de começar até às 16h). O cliente pode aparecer à hora antiga, ou a terapeuta ficar com uma
sessão que não pode dar.

## O que já se sabe (só leitura, 26/10/2026)

- No turno 4 a Filha de gestão pós-marcação devolveu `meeting_reschedule_requested=true` e
  `meeting_datetime_candidate=2026-10-29T16:15:00` — a **sua própria sugestão**, não o horário pedido.
- O prompt (`backend-executors/app/services/decision_engine.py`, bloco de gestão pós-confirmação,
  ~linhas 4630–4655) manda "CONFIRME DIRETAMENTE neste turno" quando o cliente dá dia e hora; não diz o
  que fazer quando esse horário está ocupado.
- `meeting_scheduler.handle_meeting_cancel_or_reschedule` (~linha 851) aplica o candidato que vier, só
  com o 409 do CRM como barreira — não confere se o candidato é o horário pedido pelo cliente nem se cabe
  no horário do profissional (`professional_hours.py`, já usado no agendamento novo).
- Com o código antigo (comparação como texto) o 16h15 também não colidia — não foi introduzido pela
  correção de conflitos.

## Área do sistema

- `backend-executors/app/services/decision_engine.py` (prompt de gestão pós-confirmação — **instruções da
  IA**, sobe ao utilizador)
- `backend-executors/app/services/meeting_scheduler.py` (`handle_meeting_cancel_or_reschedule`)
- `backend-executors/app/services/professional_hours.py` / `requested_slot.py` (reutilizar)
- Docs: `docs/architecture/agenda.md` (secção gestão pós-confirmação)

## Relação com outros itens

- B (`fix-confirmacao-grava-proposta-antiga`) já está em `main` (26/10/2026) e deixou a leitura
  pronta para reutilizar: `backend-executors/app/services/meeting_proposal.py` —
  `last_proposal(history, inbound)` dá as opções que o agente propôs por último (ou a hora que o
  cliente disse) e `accepted_slot(inbound, proposal)` diz se o cliente aceitou alguma. Aqui a
  pergunta é "o candidato da Filha é uma opção da proposta deste turno, que o cliente ainda não
  aceitou?". A conferência de B (`_apply_meeting_confirmation_guard`) não corre na gestão
  pós-marcação (`_build_child_prompt_meeting_management`, chamada a `_apply_meeting_date_guard`
  em `_decide_post_meeting_management`) — é lá que entra a deste item. Ver `docs/architecture/agenda.md`,
  "Turno da confirmação".
