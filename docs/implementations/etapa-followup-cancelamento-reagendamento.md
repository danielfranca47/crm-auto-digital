# M1 — Ação real de cancelamento/reagendamento de compromisso

**Branch:** `main`
**Status:** Em andamento
**Plano:** `docs/plans/followup-proativo-e-cancelamento-agenda.md` (M1)

---

## Motivação

Quando um lead/paciente pede para cancelar ou reagendar uma reunião já confirmada, a IA responde no tom certo (instrução de `custom_instructions`), mas isso é só texto — o appointment original continua `status="pending"` no banco, intocado. Lembretes continuam agendados, o evento no Google Calendar não é atualizado, e se o lead aceitar um novo horário o sistema cria um segundo appointment em vez de atualizar o original.

Causa raiz adicional descoberta nesta investigação (não estava no plano original): depois que `handle_meeting_scheduled()` confirma uma reunião, ele desativa o bot (`bot_disabled=1`, `bot_disabled_reason="meeting_scheduled"`). A partir daí, **duas barreiras** impedem qualquer mensagem futura do lead de chegar à IA no WhatsApp real:
1. `backend-crm/services/whatsapp_inbound/inbound_handler.py:480-490` — não cria job quando `bot_disabled=1`.
2. `backend-executors/app/services/decision_engine.py:4190-4199` (`decide()`) — retorna `BOT_DISABLED_DECISION` sempre que `metadata.bot_disabled=True`.

Ou seja: hoje, "preciso cancelar" do lead nem chega a ser processado em produção — só "funciona" no Playground, que nunca checa `bot_disabled`. Resolver isto é pré-requisito para o M1 ter efeito prático.

---

## Problemas Identificados (estado anterior)

1. **Sem ação real de cancelamento/reagendamento:** `backend-executors/app/services/meeting_scheduler.py` só tem `handle_meeting_scheduled()` (criação). Sem equivalente para cancelar/atualizar o appointment original.
2. **Bot fica mudo após a confirmação:** `bot_disabled=1` bloqueia qualquer mensagem futura do lead nos dois pontos citados acima — mesmo um pedido de cancelamento nunca chega à LLM no fluxo real.
3. **`mark_canceled` (`routes/appointments.py`) não limpa side-effects:** cancela o `status` mas não cancela jobs `pending` de lembrete/briefing nem apaga o evento no Google Calendar (`delete_appointment` já faz isso, `mark_canceled` não).
4. **`update_appointment` (PUT) não re-agenda lembretes/briefing:** ao mudar `start_at`, os jobs de lembrete/briefing antigos continuam apontando para o horário velho.
5. **`_load_calendar_busy_slots` não expõe `id`:** só devolve `lead_id/start_at/end_at`, insuficiente para identificar qual appointment cancelar/atualizar.

---

## Abordagem

Criar um caminho dedicado e mínimo (mesmo padrão de `fast_path.try_fast_handoff()`), em vez de injetar este caso na pipeline Mãe/Filha existente — evita risco de regressão nos guardrails de categoria/qualificação já existentes.

```
Inbound (lead já tem reunião confirmada, bot_disabled=1, reason=meeting_scheduled)
  → inbound_handler.py: gate deixa passar (reason == meeting_scheduled) → cria job normalmente
  → decision_engine.decide(): em vez de BOT_DISABLED_DECISION, chama _decide_post_meeting_management()
      → 1 chamada LLM dedicada: "reunião já confirmada para <data>; decida se é pedido de
        cancelar/reagendar; senão, resposta mínima sem vender"
      → ChildResult.signals_structured: {meeting_cancel_requested, meeting_reschedule_requested,
        meeting_datetime_candidate}
  → DecisionOutput (next_action=reply, sem suggested_category — não move o Kanban)
  → runner (whatsapp.py): envia message_text normalmente
       + NOVO: meeting_scheduler.handle_meeting_cancel_or_reschedule(context, decision)
           → localiza o appointment original (calendar_busy_slots, filtrando lead_id, mais próximo)
           → cancelar → crm_client.cancel_appointment() → POST /api/appointments/{id}/cancel
           → reagendar → crm_client.reschedule_appointment() → PUT /api/appointments/{id}
           → reativa bot só no caso de cancelamento puro (sem novo horário)
```

**Decisão de produto confirmada com o utilizador:** se a mensagem do lead não for sobre cancelar/reagendar, o bot responde de forma mínima e cordial, sem reabrir vendas.

---

## Plano de Implementação

### Fase 1 — Detecção: reabrir a porta + LLM dedicada de gestão pós-confirmação

**Objetivo:** mensagens do lead voltam a chegar à IA quando `bot_disabled_reason="meeting_scheduled"`, e uma LLM dedicada decide se é cancelamento/reagendamento ou produz resposta mínima.

| Arquivo | O que muda |
|---|---|
| `backend-crm/services/whatsapp_inbound/inbound_handler.py` | Gate de `bot_disabled` (linha ~480-490): deixa passar quando `bot_disabled_reason == "meeting_scheduled"` (cria job normalmente); qualquer outro motivo mantém o skip atual |
| `backend-crm/routes/executor.py` | Propagar `bundle.metadata["bot_disabled_reason"]` junto com `bot_disabled` |
| `backend-executors/app/services/decision_engine.py` | `decide()`: branch novo para `bot_disabled_reason == "meeting_scheduled"` → `_decide_post_meeting_management()`. Novo `_build_child_prompt_meeting_management()`. |
| `backend-executors/app/services/meeting_scheduler.py` | Nova `_extract_cancel_reschedule_signal()` (paralela a `_extract_meeting_signal`) |

### Fase 2 — Ação real: aplicar no appointment + jobs + Google Calendar

**Objetivo:** os sinais da Fase 1 produzem mudança real e persistente.

| Arquivo | O que muda |
|---|---|
| `backend-crm/services/ai_orchestrator/orchestrator.py` | `_load_calendar_busy_slots`: adicionar `a.id` ao SELECT |
| `backend-executors/app/clients/crm_client.py` | Novo `cancel_appointment()` e `reschedule_appointment()` |
| `backend-executors/app/services/meeting_scheduler.py` | Nova `handle_meeting_cancel_or_reschedule()` |
| `backend-executors/app/runners/whatsapp.py` | Chamar a nova função ao lado de `handle_meeting_scheduled` |
| `backend-crm/routes/appointments.py` | `mark_canceled`: cancelar jobs pendentes + apagar evento Google. `update_appointment`: re-agendar jobs quando o horário muda. |

---

## Checks de Validação

### Cenário T1 — Detecção de cancelamento (unitário, sem UI)
- [ ] Simular `decide()` com `bot_disabled_reason="meeting_scheduled"` e mensagem "preciso cancelar"
- [ ] Confirmar: `decision_trace.child_signals_structured.meeting_cancel_requested == True`

### Cenário T2 — Detecção de reagendamento (unitário)
- [ ] Simular mensagem "posso remarcar para sexta às 15h?"
- [ ] Confirmar: `meeting_reschedule_requested == True` e `meeting_datetime_candidate` preenchido

### Cenário T3 — Mensagem neutra não reabre vendas (unitário)
- [ ] Simular mensagem "obrigada!"
- [ ] Confirmar: resposta mínima, sem sinais de cancelamento/reagendamento, sem `suggested_category`

### Cenário T4 — Cancelamento aplica de verdade (pytest, crm_client mockado)
- [ ] `handle_meeting_cancel_or_reschedule` com sinal de cancelamento
- [ ] Confirmar: `cancel_appointment` chamado + `set_lead_bot_disabled(lead_id, False)` chamado

### Cenário T5 — Reagendamento aplica de verdade (pytest)
- [ ] `handle_meeting_cancel_or_reschedule` com sinal de reagendamento + novo horário
- [ ] Confirmar: `reschedule_appointment` chamado com novo `start_at`/`end_at`; bot permanece desativado

### Cenário C1 — Cancelamento manual via UI limpa jobs e Google Calendar (manual)
- [ ] Criar appointment com lembrete agendado e evento Google
- [ ] Cancelar via UI (`mark_canceled`)
- [ ] Confirmar: job de lembrete cancelado, evento Google removido

### Cenário C2 — Fluxo real WhatsApp (manual, requer instância conectada)
- [ ] Lead com reunião confirmada (bot_disabled=1) envia "preciso cancelar"
- [ ] Confirmar: mensagem chega à IA, appointment cancelado, bot reativado

---

## Ajustes Possíveis Pós-Implementação

- Pedido de handoff humano explícito durante a janela `meeting_scheduled`-disabled não escala para humano — fica para iteração futura.
- Appointment fora da janela de 30 dias de `calendar_busy_slots` não é localizado.
- Mudança de categoria do lead (Kanban) não é tocada por este fluxo — território do M2.
- Gap de autenticação pré-existente em `routes/appointments.py` (`create_appointment`/`update_appointment`/`mark_canceled` sem `Depends(require_crm_access)`) não é corrigido aqui.
