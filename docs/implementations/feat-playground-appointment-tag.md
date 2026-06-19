# Feat: Playground passa a criar appointment real com tag "[Playground]"

**Branch:** `main`
**Status:** Em andamento

---

## Motivação

O Playground já consulta a disponibilidade real (`calendar_busy_slots`) antes de propor
horário, com paridade total com o WhatsApp real — mas nunca chega a criar o appointment
quando a IA confirma um agendamento. Isso foi uma decisão de design documentada
(`docs/architecture/agenda.md:257-259`: "sandbox não cria appointments reais"), mas o
utilizador quer o comportamento contrário para poder validar o fluxo ponta-a-ponta durante
demos de venda: o appointment deve ser criado de verdade, na Agenda real da conta, mas com
o título prefixado `"[Playground]"` para não ser confundido com um agendamento de cliente
real.

---

## Problemas Identificados (estado anterior)

1. **`handle_meeting_scheduled` nunca é chamada pelo Playground:** `backend-executors/app/services/meeting_scheduler.py:377`
   só é invocada em `backend-executors/app/runners/whatsapp.py:756` (fluxo real). O endpoint
   `backend-executors/app/api/playground_internal.py:47-58` chama só `decision_engine.decide()`
   e devolve — sem nenhum passo de agendamento.
2. **Sem suporte a `source` na criação de appointment:** `backend-crm/models.py::AppointmentCreate`
   (linha 91) não tem campo `source`; o INSERT em `backend-crm/routes/appointments.py::create_appointment`
   (linha 256) não escreve a coluna `source` (cai no default `'crm'` da tabela). Não há como
   marcar um appointment como originado do Playground.
3. **Side-effects indesejados para um lead fake:** a mesma rota de criação sempre agenda
   lembrete por WhatsApp (`_schedule_reminder_jobs`) e faz push para o Google Calendar real do
   utilizador (`gcal_push`, linha 300) — ambos indesejados para uma simulação (o lead sandbox
   tem telefone fake `playground_xxxx`, e o Google Calendar do utilizador é real).
4. **Sem limpeza de appointments de teste:** `backend-crm/routes/playground.py::_reset_sandbox_lead`
   (linha 236) limpa mensagens e `qualification_state`, mas não os appointments do lead — testes
   repetidos acumulariam compromissos `[Playground]` na Agenda real, podendo bloquear (`409`)
   agendamentos reais futuros no mesmo horário via `_check_conflict`.

---

## Abordagem

```
Playground confirma horário (decision_trace.meeting_scheduled=true)
  → playground_internal.py::playground_decide() [backend-executors]
      → decision_engine.decide(context_bundle)            (já existia)
      → meeting_scheduler.handle_meeting_scheduled(        (NOVO)
            context_bundle, decision, client=crm_client, is_playground=True)
          ├─ reaproveita parsing de data/hora + checagem de conflito contra
          │  calendar_busy_slots (mesma lógica do fluxo real, zero duplicação)
          ├─ sem conflito → crm_client.create_lead_appointment(..., source="playground",
          │     title="[Playground] Reunião agendada")
          │     → backend-crm POST /api/appointments
          │         → INSERT com source='playground'
          │         → pula reminder jobs + briefing + push Google Calendar
          └─ com conflito → devolve mensagem de correção
                → anexada a decision.system_actions (send_message)
                → playground.py já sabe exibir isso (auto_messages/auto_items)
  → operador vê "[Playground] Reunião agendada" na Agenda real
  → _reset_sandbox_lead() agora também apaga appointments do lead sandbox
```

---

## Plano de Implementação

### Fase 1 — Criação tagueada + side-effects suprimidos + cleanup no reset

**Objetivo:** appointment real criado a partir do Playground, visivelmente marcado, sem
poluir lembretes/Google Calendar reais, e sem acumular lixo entre testes.

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/meeting_scheduler.py` | `handle_meeting_scheduled(..., is_playground: bool = False)`. Quando `True`: `title="[Playground] Reunião agendada"`, `description="Reunião simulada no Playground."`, passa `source="playground"` ao client. |
| `backend-executors/app/clients/crm_client.py` | `create_lead_appointment(..., source: str \| None = None)` — inclui `source` no payload POST apenas se fornecido. |
| `backend-executors/app/api/playground_internal.py` | Após `decision_engine.decide(...)`, chama `meeting_scheduler.handle_meeting_scheduled(context_bundle, result, client=crm_client, is_playground=True)`. Mensagem de conflito (se houver) é anexada a `result.system_actions`. |
| `backend-crm/models.py` | `AppointmentCreate.source: Optional[str] = None`. |
| `backend-crm/routes/appointments.py::create_appointment` | INSERT passa a escrever `source` (`payload.source or "crm"`). Bloco de reminders/briefing/Google push só corre quando `payload.source != "playground"`. |
| `backend-crm/routes/playground.py::_reset_sandbox_lead` | `DELETE FROM appointments WHERE lead_id = ?` antes do reset de mensagens. |
| `backend-crm/routes/playground.py` (`DecisionTrace` + `_build_decision_trace`) | Novo campo opcional `meeting_scheduled: Optional[bool]`, lido de `trace.get("meeting_scheduled")`. |

```python
# ANTES — meeting_scheduler.py
client.create_lead_appointment(
    lead_id=signal.lead_id,
    title="Reunião agendada",
    description="Reunião confirmada pelo SDR Scheduler.",
    appointment_type="meeting",
    start_at=start_iso,
    end_at=end_iso,
)

# DEPOIS
title = "[Playground] Reunião agendada" if is_playground else "Reunião agendada"
description = (
    "Reunião simulada no Playground." if is_playground
    else "Reunião confirmada pelo SDR Scheduler."
)
client.create_lead_appointment(
    lead_id=signal.lead_id,
    title=title,
    description=description,
    appointment_type="meeting",
    start_at=start_iso,
    end_at=end_iso,
    source="playground" if is_playground else None,
)
```

Sem teste automatizado novo nesta fase — `backend-crm` não tem suíte de testes no
repositório, e o fluxo depende de round-trip HTTP cross-service + SQLite real. Validação
é manual, via Playground + tela de Agenda (checks abaixo).

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `2ee3a02` | `is_playground`/`source` em meeting_scheduler, crm_client, models, appointments; chamada em playground_internal.py; cleanup em `_reset_sandbox_lead`; `meeting_scheduled` no trace |

---

## Checks de Validação

### Cenário P1 — Agendamento confirmado no Playground cria appointment tagueado
- [ ] Playground, perfil hybrid_scheduler (agent_mode=agenda), lead novo, confirmar um
      horário livre na conversa
- [ ] Abrir `/agenda` (conta real) e confirmar que aparece `"[Playground] Reunião agendada"`
      no horário certo
- [ ] Confirmar que **não** foi criado job de lembrete WhatsApp nem evento no Google Calendar
      real (se a conta tiver Google conectado)

### Cenário P2 — Conflito de horário é respeitado
- [ ] Criar manualmente um appointment real num horário X
- [ ] No Playground, levar a IA a confirmar o mesmo horário X
- [ ] Confirmar: appointment **não** duplicado; mensagem de correção aparece no chat do
      Playground

### Cenário P3 — Reset do lead sandbox limpa appointments de teste
- [ ] Repetir P1 (criar um `[Playground]`)
- [ ] No Playground, fazer reset do lead sandbox
- [ ] Confirmar na Agenda que o appointment `[Playground]` anterior foi removido

### Cenário C1 — Fluxo real inalterado
- [ ] Confirmar agendamento real via WhatsApp (número de teste)
- [ ] Confirmar que o título continua `"Reunião agendada"` (sem prefixo), lembrete e push
      Google Calendar continuam a funcionar como antes

---

## Ajustes Possíveis Pós-Implementação

- Sandbox leads criados sem `reset` (cada sessão nova sem reutilizar `lead_id`) continuam a
  acumular ao longo do tempo — pré-existente, não tratado aqui.
- Poderia-se adicionar um botão "Limpar todos os testes" na UI do Playground para apagar
  todos os leads/appointments `is_playground=1` de uma vez — não pedido nesta iteração.
