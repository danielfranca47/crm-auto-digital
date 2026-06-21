# M1 — Ação real de cancelamento/reagendamento de compromisso

**Branch:** `main`
**Status:** Em andamento — pendente: Cenários C1 e C2 (validação manual: UI + WhatsApp real)
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

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `796bcf8` | Gate condicional + LLM dedicada de gestão pós-confirmação + sinais estruturados |

**Detalhes do commit `796bcf8`:**
- `backend-crm/services/whatsapp_inbound/inbound_handler.py` — gate de `bot_disabled` deixa passar quando `bot_disabled_reason == "meeting_scheduled"`
- `backend-crm/routes/executor.py` — propaga `bot_disabled_reason` no `ContextBundle.metadata`
- `backend-executors/app/services/decision_engine.py` — `_decide_post_meeting_management()` + `_build_child_prompt_meeting_management()`; branch novo em `decide()`
- `backend-executors/app/services/meeting_scheduler.py` — `_extract_cancel_reschedule_signal()` + `CancelRescheduleSignal`
- `backend-executors/tests/test_meeting_management.py` — 8 testes novos (todos passando)

### Relatório da Fase 1 — o que mudou na prática

**Antes:** depois que uma reunião era confirmada, o bot ficava completamente mudo para aquele lead — mesmo um "preciso cancelar" não chegava a ser processado pela IA no WhatsApp real (só "funcionava" no Playground, que ignora esse bloqueio).

**Agora:** quando o motivo do silêncio é especificamente "reunião confirmada" (não afeta outros motivos, como handoff humano), a mensagem volta a chegar à IA — mas por um caminho separado e mais cauteloso: ele só age se detectar um pedido real de cancelar ou reagendar; qualquer outra mensagem ("obrigada!", uma pergunta solta) recebe uma resposta curta e educada, sem reabrir conversa de venda. Essa decisão (cancelar / reagendar / nem um nem outro) já fica registrada de forma estruturada — falta só a Fase 2 para transformar essa decisão numa ação real no compromisso (cancelar de verdade, mover o horário, etc.).

**Para validar:** não há nada visível na UI ainda nesta fase (é só a camada de deteção) — a validação foi feita via 8 testes automatizados (`backend-executors/tests/test_meeting_management.py`), todos passando, cobrindo: deteção de cancelamento, deteção de reagendamento, mensagem neutra (resposta mínima), outros motivos de `bot_disabled` continuam bloqueados, e fallback quando a LLM falha.

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `da3aa5d` | Ação real: cancelar/reagendar appointment + limpeza de jobs + Google Calendar |

**Detalhes do commit `da3aa5d`:**
- `backend-crm/services/ai_orchestrator/orchestrator.py` — `_load_calendar_busy_slots` passa a incluir `a.id`
- `backend-executors/app/clients/crm_client.py` — `cancel_appointment()`, `reschedule_appointment()`
- `backend-executors/app/services/meeting_scheduler.py` — `handle_meeting_cancel_or_reschedule()`
- `backend-executors/app/runners/whatsapp.py` — chama a nova função ao lado de `handle_meeting_scheduled`
- `backend-crm/routes/appointments.py` — `_cancel_pending_appointment_jobs()`; `mark_canceled` apaga evento Google; `update_appointment` re-agenda jobs quando `start_at` muda
- `backend-executors/tests/test_meeting_cancel_reschedule_action.py` — 6 testes novos
- `backend-crm/tests/test_appointment_job_cleanup.py` — 4 testes novos

### Relatório da Fase 2 — o que mudou na prática

**Antes:** mesmo quando a IA detectava (Fase 1) que o lead queria cancelar ou reagendar, nada mudava de fato no sistema — o compromisso continuava `pending`, os lembretes automáticos continuavam agendados para o horário "cancelado", e o evento no Google Calendar do profissional não era tocado.

**Agora:** quando a IA confirma um cancelamento, o compromisso é marcado como cancelado de verdade, os lembretes e o aviso de briefing pendentes são cancelados, o evento correspondente é removido do Google Calendar (se conectado), e o bot volta a responder normalmente a esse lead. Quando é um reagendamento, o mesmo compromisso é atualizado para o novo horário (em vez de criar um segundo, "fantasma"), os lembretes são reagendados para a nova data, e o bot continua em modo de gestão (pronto para outro cancelamento/reagendamento, se precisar). Se o novo horário pedido já estiver ocupado por outro compromisso do profissional, o sistema avisa o lead e não aplica a mudança — em vez de silenciosamente quebrar a agenda. Esta mesma limpeza de lembretes/Google Calendar também passou a valer quando o **operador** cancela ou edita um compromisso manualmente pela UI, não só quando é a IA.

**Para validar:** Cenários T4, T5 e T6 (ação de cancelar/reagendar, conflito de horário, limpeza de jobs) cobertos por 10 testes automatizados — todos passando. Os Cenários C1 (cancelamento manual via UI limpa jobs/Google Calendar) e C2 (fluxo real WhatsApp ponta a ponta) ainda dependem de um ambiente com instância WhatsApp e Google Calendar conectados — ficam para validação manual.

---

## Checks de Validação

### Cenário T1 — Detecção de cancelamento (unitário, sem UI)
- [x] Simular `decide()` com `bot_disabled_reason="meeting_scheduled"` e mensagem "preciso cancelar"
- [x] Confirmar: `decision_trace.child_signals_structured.meeting_cancel_requested == True`
- **Validado em:** 21/06/2026 — `test_decide_post_meeting_management_detects_cancel`, passou

### Cenário T2 — Detecção de reagendamento (unitário)
- [x] Simular mensagem "posso remarcar para sexta às 15h?"
- [x] Confirmar: `meeting_reschedule_requested == True` e `meeting_datetime_candidate` preenchido
- **Validado em:** 21/06/2026 — `test_decide_post_meeting_management_detects_reschedule`, passou

### Cenário T3 — Mensagem neutra não reabre vendas (unitário)
- [x] Simular mensagem "obrigada!"
- [x] Confirmar: resposta mínima, sem sinais de cancelamento/reagendamento, sem `suggested_category`
- **Validado em:** 21/06/2026 — `test_decide_post_meeting_management_neutral_message_minimal_reply`, passou

### Cenário T4 — Cancelamento aplica de verdade (pytest, crm_client mockado)
- [x] `handle_meeting_cancel_or_reschedule` com sinal de cancelamento
- [x] Confirmar: `cancel_appointment` chamado + `set_lead_bot_disabled(lead_id, False)` chamado
- **Validado em:** 21/06/2026 — `test_cancel_calls_cancel_appointment_and_reactivates_bot` + `test_cancel_picks_soonest_appointment_when_multiple`, passaram

### Cenário T5 — Reagendamento aplica de verdade (pytest)
- [x] `handle_meeting_cancel_or_reschedule` com sinal de reagendamento + novo horário
- [x] Confirmar: `reschedule_appointment` chamado com novo `start_at`/`end_at`; bot permanece desativado
- [x] Confirmar: conflito de horário (409) devolve mensagem de correção em vez de aplicar a mudança
- **Validado em:** 21/06/2026 — `test_reschedule_calls_reschedule_appointment_and_keeps_bot_disabled` + `test_reschedule_conflict_returns_correction_message`, passaram (`backend-executors/tests/test_meeting_cancel_reschedule_action.py`, 6 testes no total)

### Cenário T6 — Limpeza de jobs de lembrete/briefing (pytest, backend-crm)
- [x] `_cancel_pending_appointment_jobs` cancela jobs `pending` de lembrete/briefing do appointment
- [x] Confirmar: jobs de outro appointment, já concluídos, ou de outro tipo não são tocados
- **Validado em:** 21/06/2026 — `backend-crm/tests/test_appointment_job_cleanup.py`, 4 testes, passaram via `python -m unittest`

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
