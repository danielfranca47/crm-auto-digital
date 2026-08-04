# Indicador visual de agendamento real no Playground

**Branch:** `fix/deteccao-intencao-reagendamento-ia`
**Status:** Todos os cenários validados (05/08/2026) — pronto para graduação

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

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `f551f0b` | feat: propaga evento de agendamento real do Playground (Fase 1 backend) |

**Detalhes do commit `f551f0b`:**
- `backend-executors/app/services/meeting_scheduler.py` — parâmetro opcional `events` em `handle_meeting_scheduled()`/`handle_meeting_cancel_or_reschedule()`, populado no caminho feliz
- `backend-executors/app/api/playground_internal.py` — coleta `events` e anexa `appointment_event` a `system_actions`
- `backend-crm/routes/playground.py` — novo campo `appointment_event` em `PlaygroundChatResponse`, captura nos dois loops de `system_actions`
- `backend-executors/tests/test_meeting_scheduled_events.py` (novo) + `test_meeting_cancel_reschedule_action.py` (estendido) — cobertura dos 3 caminhos de sucesso + confirmação de que o fluxo real (sem `events=`) não quebra

### Relatório da Fase 1 — o que mudou na prática

**Antes:** quando o Playground criava, reagendava ou cancelava um agendamento real por
trás da simulação, essa informação não saía do backend — o response só tinha o texto
da resposta do bot.

**Agora:** o `POST /api/playground/chat` já devolve um campo `appointment_event` (ex.:
`{"action": "created", "start_at": "...", "end_at": "..."}`) sempre que isso acontece
de verdade nesse turno. Ainda não há nada visível na tela — essa é a Fase 2.

**Para validar:** ainda não há cenário de UI para testar (a Fase 2 adiciona o chip
visual). Só é possível confirmar via Cenário C1 (pytest) por enquanto.

---

### Fase 2 — Frontend: renderizar o chip na conversa

**Objetivo:** o chip aparece na timeline do Playground logo após a confirmação do bot.

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/services/api.ts` | Novo tipo `PlaygroundAppointmentEvent`; novo campo `appointment_event?: PlaygroundAppointmentEvent \| null` em `PlaygroundChatResponse` |
| `frontend-crm/src/components/playground/MessageBubble.tsx` | `ChatMessage`: novos campos opcionais `isAppointmentEvent`, `appointmentEventAction`, `appointmentEventStartAt`. Import de `Calendar` (lucide-react). Novo early-return no render, chip centrado com cor/ícone distintos por acção |
| `frontend-crm/src/pages/Playground.tsx` | Novo helper `appendAppointmentEvent()` (mesmo padrão de `appendPhaseAdvances`); chamado nos 5 pontos onde esse padrão já se repete |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `ec2e60e` | feat: renderiza chip de agendamento real no Playground (Fase 2 frontend) |

**Detalhes do commit `ec2e60e`:**
- `frontend-crm/src/services/api.ts` — tipo `PlaygroundAppointmentEvent`, campo `appointment_event` em `PlaygroundChatResponse`
- `frontend-crm/src/components/playground/MessageBubble.tsx` — chip visual (early-return, mesmo padrão de `isPhaseAdvance`), ícone `Calendar`, cor âmbar
- `frontend-crm/src/pages/Playground.tsx` — `appendAppointmentEvent()` chamado nos 5 call sites existentes

### Relatório da Fase 2 — o que mudou na prática

**Antes:** quando o bot confirmava, reagendava ou cancelava uma reunião de verdade
durante uma simulação no Playground, a conversa não mostrava nenhuma diferença — parecia
uma resposta de texto qualquer.

**Agora:** aparece um chip destacado na conversa (📅 "Reunião confirmada para
`<data/hora>`", 🔄 "Reunião reagendada para `<data/hora>`" ou ❌ "Reunião cancelada")
sempre que isso acontece de verdade, ajudando quem está a testar a distinguir uma
confirmação real de uma resposta apenas conversacional. Uma mensagem neutra (sem sinal
de agendamento) continua sem mostrar nenhum chip.

**Para validar:** Cenários P1, P2, P3 e a Regressão, abaixo — já testados ao vivo via
browser nesta sessão (ver checks marcados).

**Nota:** a data/hora exibida no chip usa o fuso do browser (`toLocaleString`), não o
fuso de negócio do AI Profile — decisão consciente para manter o escopo pequeno (ver
"Formatação de data/hora" no plano aprovado). Numa validação real observou-se
`start_at` UTC `09:00` a aparecer como `10:00` no chip, por causa do fuso local do
browser usado no teste — comportamento esperado, não um bug.

---

## Checks de Validação

### Cenário C1 — Testes automatizados (pytest)
- [x] `pytest backend-executors/tests/test_meeting_scheduled_events.py backend-executors/tests/test_meeting_cancel_reschedule_action.py backend-executors/tests/test_meeting_management.py backend-executors/tests/test_meeting_scheduler_structured_candidate.py` passa — 05/08/2026 (26 testes, incluindo os novos `test_handle_meeting_scheduled_populates_events_when_provided`, `test_handle_meeting_scheduled_without_events_param_does_not_raise`, `test_cancel_populates_events_when_provided`, `test_reschedule_populates_events_when_provided`, `test_conflict_does_not_populate_events`).

### Cenário P1 — Playground, chip de confirmação
- [x] Com `agent_mode="agenda"`, confirmar uma reunião no Playground — 05/08/2026.
- [x] Confirmar: chip "📅 Reunião confirmada para `<data/hora>`" aparece na timeline —
  05/08/2026 ("📅 Reunião confirmada para 05/08, 10:00").

### Cenário P2 — Playground, chip de reagendamento
- [x] Pedir reagendamento (implícito ou explícito) de uma reunião já confirmada —
  05/08/2026.
- [x] Confirmar: chip "🔄 Reunião reagendada para `<data/hora>`" aparece — 05/08/2026
  ("🔄 Reunião reagendada para 05/08, 12:00").

### Cenário P3 — Playground, chip de cancelamento
- [x] Pedir cancelamento de uma reunião já confirmada — 05/08/2026.
- [x] Confirmar: chip "❌ Reunião cancelada" aparece — 05/08/2026.

### Regressão — Mensagem neutra não produz chip
- [x] Enviar mensagem neutra (sem sinal de agendamento) após reunião confirmada —
  05/08/2026.
- [x] Confirmar: nenhum chip aparece — 05/08/2026 (`appointment_event: null` na
  resposta, nenhum chip renderizado).
