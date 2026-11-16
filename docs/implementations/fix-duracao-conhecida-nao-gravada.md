# A marcação fica com a duração padrão quando o cliente já disse a duração

**Branch:** (a criar)
**Status:** Aguardando Plan Mode
**Autonomia:** manual
**Origem:** bateria PROD08 do agente Sensi Vitae (16/11/2026), cenário `p-relax90`
(`.claude/agentes/sensi-vitae/tentativas/20261116-1357-PROD08-p-relax90.*`).

---

## Motivação

O cliente pediu "massagem relaxante de 90 minutos" e marcou terça às 14h. O recibo
"Experiência Agendada" diz "Lomi Lomi - 90 min", mas a marcação ficou gravada **14h–15h** (60 min,
a `default_session_duration_minutes` da conta). Com sessões seguidas e a margem entre sessões, a
agenda deixa marcar outro cliente às 15h30 por cima da sessão real (que acaba às 15h30 + 30 min
de margem). O terapeuta só descobre o choque no dia.

## Causa confirmada (16/11/2026)

1. No turno do resumo ("Pode confirmar?" = sim), a Filha devolveu `meeting_datetime_candidate`
   sem `meeting_duration_minutes` (o resumo dela também omitiu a duração).
2. A proteção do turno da confirmação (`_apply_meeting_confirmation_guard` em `decision_engine.py`,
   `_missing_booking_duration` → `meeting_proposal.missing_duration`) vê que a duração **já se sabe**
   — `requested_slot.requested_duration()` encontra "90 minutos" no texto do lead — e por isso deixa
   gravar, mas **não escreve essa duração no sinal**.
3. `meeting_scheduler.handle_meeting_scheduled()` usa `signal.duration_minutes or
   _resolve_default_duration_minutes(ai_profile)` → 60.

A tabela de serviços da conta está certa (Base de Conhecimento, `service_pricing_table`
`structured_v1` com 20/30/45/60 e Lomi Lomi 45/60/90).

## Direção da solução

Quando a proteção conclui que a duração se sabe (dita pelo lead ou escrita na proposta aceite) e a
Filha não a devolveu, preencher `signals_structured.meeting_duration_minutes` com essa duração antes
do `meeting_scheduler` (registar no `decision_trace.meeting_confirmation_guard`). A conferir no Plan
Mode: se a duração dita pela Filha contradiz a do lead, qual vence; e se a remarcação
(`handle_meeting_cancel_or_reschedule`, que usa a duração original) precisa do mesmo cuidado.

## Área do sistema

- `backend-executors/app/services/decision_engine.py` (proteção da confirmação) e
  `meeting_proposal.py` / `requested_slot.py` — não muda prompts
- `docs/architecture/agenda.md` ("Turno da confirmação", "Duração da sessão"); corrigir também em
  `docs/architecture/knowledge-base.md` as chaves do `structured_v1` (o código lê `nome`,
  `duracaoMinutos`, `preco`, `descricao`; o doc diz `name`, `duration_minutes`, `price`)

## Validação

Bancada `.claude/agentes/sensi-vitae/`: `python simular.py p-relax90 <rótulo>` e `p-relax-sem-tipo`
(a marcação tem de ficar com 90 min), mais regressão `p-micas`, `pos-marcacao`, `p-seguidas`; depois
os mesmos com `--prod`.
