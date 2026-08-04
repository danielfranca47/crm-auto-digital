# Indicador visual de agendamento real no Playground

**Branch:** `fix/deteccao-intencao-reagendamento-ia`
**Status:** Em andamento

---

## Motivação

Durante a revalidação de `fix-deteccao-intencao-reagendamento-ia.md` (Cenários P1-P4),
confirmou-se que o Playground já cria/reagenda/cancela appointments **reais** por trás
da simulação (`meeting_scheduler.handle_meeting_scheduled`/
`handle_meeting_cancel_or_reschedule`, chamados via
`backend-executors/app/api/playground_internal.py`), mas isso não aparece de forma
distinta na conversa — a confirmação sai como texto normal do bot, indistinguível de
qualquer outra resposta. Ficou registado como "Ajuste Possível" no arquivo dessa fix.

**Comportamento actual:** nenhuma indicação visual de que um appointment real mudou.
**Comportamento desejado:** um chip/pill na timeline do Playground quando um agendamento
é criado, reagendado ou cancelado de verdade — mesmo padrão visual já usado para
`phase_advances` ("Fase avançada").

---

## Problemas Identificados (estado anterior)

1. **Dados de sucesso descartados:** `handle_meeting_scheduled()`/
   `handle_meeting_cancel_or_reschedule()`
   (`backend-executors/app/services/meeting_scheduler.py:685,806`) retornam
   `Optional[str]` — só a mensagem de conflito. Nos caminhos de sucesso (criar: linha
   ~793-803; cancelar: linha ~848-867; reagendar: linha ~908-915), os dados do
   appointment (start_at/end_at) são computados mas nunca propagados para fora da função.

2. **Nenhum campo no response do Playground:** `PlaygroundChatResponse`
   (`backend-crm/routes/playground.py:154-173`) não tem nenhum campo que carregue esse
   tipo de evento — o loop de `system_actions` (linhas ~663, ~744) já processa vários
   tipos (`send_message`, `send_media`, `advance_phase`, etc.), mas nenhum para
   agendamento.

3. **Sem indicador visual no frontend:** `MessageBubble.tsx` já tem o padrão exacto
   necessário (`isPhaseAdvance`, linha ~234-243, chip centrado) mas nada equivalente
   para eventos de agendamento — a resposta do bot que confirma/reagenda/cancela é um
   balão de texto normal.

---

## Abordagem

```
handle_meeting_scheduled(..., events=[])            → sucesso: events.append({...})
handle_meeting_cancel_or_reschedule(..., events=[])  → sucesso: events.append({...})
        ↓ (só quando o chamador passa events= — real WhatsApp não passa, não muda)
playground_internal.py: se events, anexa a result.system_actions
  {"type": "appointment_event", "action": ..., "start_at": ..., "end_at": ...}
        ↓ (mesmo canal já usado hoje para injetar a mensagem de conflito)
backend-crm/routes/playground.py: novo branch no loop de system_actions existente
  → captura em `appointment_event` local → PlaygroundChatResponse.appointment_event
        ↓
frontend: PlaygroundChatResponse.appointment_event (novo campo opcional)
  → appendAppointmentEvent() (mesmo padrão de appendPhaseAdvances)
  → MessageBubble: novo early-return chip (mesmo padrão de isPhaseAdvance)
```

`handle_meeting_scheduled`/`handle_meeting_cancel_or_reschedule` são compartilhadas com
o fluxo real do WhatsApp (`app/runners/whatsapp.py:793-796`), que as chama sem passar
`events`. A mudança é estritamente aditiva (novo parâmetro opcional, default `None`,
tipo de retorno inalterado) — zero mudança de comportamento fora do Playground.

Não se inclui `title` no evento — `calendar_busy_slots` (usado para localizar o
appointment no cancelamento/reagendamento) só tem `id`/`lead_id`/`start_at`/`end_at`
(`orchestrator.py::_load_calendar_busy_slots`), sem título.

---

## Plano de Implementação

### Fase 1 — Backend: capturar e propagar o evento de agendamento

**Objetivo:** o Playground passa a devolver `appointment_event` no
`POST /api/playground/chat` sempre que um appointment real for criado/reagendado/
cancelado nesse turno.

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/meeting_scheduler.py` | `handle_meeting_scheduled()` (linha 685): novo parâmetro `events: Optional[List[dict]] = None`; no sucesso, `events.append({"action": "created", "start_at": start_iso, "end_at": end_iso})`. `handle_meeting_cancel_or_reschedule()` (linha 806): mesmo parâmetro; cancelamento `events.append({"action": "canceled", "start_at": same_lead_slots[0]["start_at"], "end_at": same_lead_slots[0]["end_at"]})`; reagendamento `events.append({"action": "rescheduled", "start_at": start_iso, "end_at": end_iso})` |
| `backend-executors/app/api/playground_internal.py` | `playground_decide()` (linha 50): cria `events: List[dict] = []`, passa `events=events` nas duas chamadas; depois do bloco de `conflict_message`, se `events`, anexa `{"type": "appointment_event", **events[-1]}` a `result.system_actions` |
| `backend-crm/routes/playground.py` | `PlaygroundChatResponse`: novo campo `appointment_event: Optional[Dict[str, Any]] = None`. Loop `for action in raw_system_actions:` (2 ocorrências): novo branch `elif atype == "appointment_event"`. Construção do response: passar `appointment_event=appointment_event` |

```python
# meeting_scheduler.py — ANTES (handle_meeting_scheduled, trecho do sucesso)
client.create_lead_appointment(...)
client.set_lead_bot_disabled(signal.lead_id, True, reason="meeting_scheduled")
return None

# DEPOIS
client.create_lead_appointment(...)
client.set_lead_bot_disabled(signal.lead_id, True, reason="meeting_scheduled")
if events is not None:
    events.append({"action": "created", "start_at": start_iso, "end_at": end_iso})
return None
```

### Fase 2 — Frontend: renderizar o chip na conversa

**Objetivo:** o chip aparece na timeline do Playground logo após a confirmação do bot.

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/services/api.ts` | Novo tipo `PlaygroundAppointmentEvent`; novo campo `appointment_event?: PlaygroundAppointmentEvent \| null` em `PlaygroundChatResponse` |
| `frontend-crm/src/components/playground/MessageBubble.tsx` | `ChatMessage`: novos campos opcionais `isAppointmentEvent`, `appointmentEventAction`, `appointmentEventStartAt`. Import de `Calendar` (lucide-react). Novo early-return no render, chip centrado com cor/ícone distintos por acção |
| `frontend-crm/src/pages/Playground.tsx` | Novo helper `appendAppointmentEvent()` (mesmo padrão de `appendPhaseAdvances`); chamado nos 5 pontos onde esse padrão já se repete |

---

## Checks de Validação

### Cenário C1 — Testes automatizados (pytest)
- [ ] `pytest backend-executors/tests/test_meeting_scheduler_structured_candidate.py backend-executors/tests/test_meeting_cancel_reschedule_action.py backend-executors/tests/test_meeting_management.py` passa, incluindo novas asserções de `events` (criar/reagendar/cancelar) e confirmação de que chamar sem `events=` (como o `whatsapp.py` real faz) não quebra nada.

### Cenário P1 — Playground, chip de confirmação
- [ ] Com `agent_mode="agenda"`, confirmar uma reunião no Playground.
- [ ] Confirmar: chip "📅 Reunião confirmada para `<data/hora>`" aparece na timeline.

### Cenário P2 — Playground, chip de reagendamento
- [ ] Pedir reagendamento (implícito ou explícito) de uma reunião já confirmada.
- [ ] Confirmar: chip "🔄 Reunião reagendada para `<data/hora>`" aparece.

### Cenário P3 — Playground, chip de cancelamento
- [ ] Pedir cancelamento de uma reunião já confirmada.
- [ ] Confirmar: chip "❌ Reunião cancelada" aparece.

### Regressão — Mensagem neutra não produz chip
- [ ] Enviar mensagem neutra (sem sinal de agendamento) após reunião confirmada.
- [ ] Confirmar: nenhum chip aparece.
