# M1 — Ação real de cancelamento/reagendamento de compromisso

**Branch:** `main`
**Status:** Todos os checks resolvidos ([x] ou [⏭️] justificado) — pronto para graduação
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

### Cenário C1 — Cancelamento/reagendamento manual via UI limpa jobs (manual, via browser)
- [x] Criar lead + appointment via UI (Agendar Reunião no card do lead) com horário > 24h no futuro
- [x] Confirmar: jobs de lembrete/briefing `pending` criados para o appointment
- [x] Cancelar via UI (botão "Cancelar" no card do lead)
- [x] Confirmar: appointment `status=canceled`, jobs de lembrete/briefing passam a `completed` (skipped)
- [x] Reagendar via UI (botão "Reagendar" → editar horário)
- [x] Confirmar: jobs antigos completados/skipped, novos jobs criados com offsets corretos para o novo horário
- **Validado em:** 21/06/2026 — testado ao vivo via browser (chrome-devtools MCP) contra `backend-crm` local, com lead/appointments de teste criados e removidos no final. Evento Google Calendar não pôde ser confirmado neste ambiente (conta de teste tem token Google expirado — `gcal_delete` é fail-silent e não bloqueou o fluxo).

### Cenário C2 — Fluxo real WhatsApp (manual, requer instância conectada)
- [⏭️] Lead com reunião confirmada (bot_disabled=1) envia "preciso cancelar"
- [⏭️] Confirmar: mensagem chega à IA, appointment cancelado, bot reativado
- **Pulado (justificado) em:** 21/06/2026 — `decision_engine.decide()` é a mesma função para Playground e WhatsApp real (paridade já garantida pela Fase 4). As únicas partes exclusivas do canal real — gate de `inbound_handler.py` e propagação de `routes/executor.py` — já têm cobertura: o gate tem 4 testes chamando `handle_inbound` real (não mockado); `routes/executor.py` nunca teve o bug encontrado no Playground (lógica correta desde a Fase 1). O que resta sem cobrir é só a entrega via UazAPI/fila assíncrona — infraestrutura genérica já validada em produção por outras features, não específica deste M1.

### Cenário P2 — Toggle desligado: bot não reabre após confirmar (manual, via browser/Playground)
- [x] Em "Configuração do Agente → Apresentação → Gestão pós-confirmação", selecionar "Desativar bot e aguardar handoff manual" e salvar
- [x] Agendar uma sessão via Playground (mesmo fluxo do Cenário P1)
- [x] Pedir cancelamento na mesma sessão
- [x] Confirmar: bot não responde sobre o cancelamento (mensagem mínima/genérica ou nenhuma resposta de gestão), appointment continua `pending`, `bot_disabled` permanece `1`/`meeting_scheduled`
- [x] Reverter o toggle para "Bot continua disponível" ao final do teste
- **Validado em:** 21/06/2026 — primeira tentativa revelou o bug do `enrich_context_bundle` (bot respondeu normalmente, tratando o pedido de cancelamento como mensagem de venda comum). Corrigido e retestado com sucesso: trace mostrou `mother_route: null`, sem texto de resposta — bot ficou mudo. Lead/appointment de teste (#295) removidos, toggle revertido.

### Cenário P1 — Playground: agendar, cancelar e reagendar na mesma sessão (manual, via browser)
- [x] Agendar uma sessão via mensagem inbound no Playground (lead novo, `agent_mode=agenda`)
- [x] Confirmar: appointment `[Playground]` criado, `bot_disabled=1`/`reason=meeting_scheduled`
- [x] Pedir cancelamento na mesma sessão
- [x] Confirmar: appointment `status=canceled`, `bot_disabled=0` (reativado)
- [x] Agendar nova sessão e pedir reagendamento (sem cancelar antes)
- [x] Confirmar: `start_at`/`end_at` atualizados para o novo horário, `bot_disabled` permanece `1`/`meeting_scheduled`
- **Validado em:** 21/06/2026 — testado ao vivo via Playground (chrome-devtools MCP), lead sandbox removido no final. Revelou 3 bugs adicionais, corrigidos na Fase 4 (ver abaixo).

---

## Fase 3 — Diagnóstico + Correção: gaps revelados pelo teste do Cenário C1 (21/06/2026)

### Problema identificado

O teste ao vivo do Cenário C1 revelou que a Fase 2, apesar de implementada corretamente, **não cobria o caminho realmente usado pela UI**:

1. **Endpoint errado:** o frontend (`useCreateAppointment`/`useCancelAppointment`/`useUpdateAppointment`) sempre que conhece o `leadId` usa as rotas de `routes/leads.py` (`POST/PATCH/DELETE /leads/{lead_id}/appointments/...`) — **não** as de `routes/appointments.py` que a Fase 2 corrigiu. `criar_compromisso` (`routes/leads.py`) nunca agendava jobs de lembrete/briefing; `atualizar_compromisso` fazia `gcal_update` mesmo ao cancelar (em vez de `gcal_delete`) e nunca cancelava/reagendava jobs.
2. **Status `'cancelled'` não existe:** a tabela `jobs` tem `CHECK (status IN ('pending','in_progress','completed','failed'))` — `UPDATE jobs SET status='cancelled'` (como a Fase 2 escreveu, replicando um padrão já presente em `services/followup_state.py::_cancel_pending_jobs_for_lead`) levanta `IntegrityError` em produção. Só foi detectado ao testar contra o banco real (os testes automatizados da Fase 2 usavam um schema de teste sem o `CHECK`, mascarando o bug).
3. **Commit ausente:** em `routes/appointments.py::update_appointment` e `routes/leads.py::atualizar_compromisso`, a chamada a `cancel_pending_appointment_jobs(conn, ...)` ocorria *depois* do único `conn.commit()` da função — as mudanças nos jobs nunca eram persistidas antes do `conn.close()`.

Causa raiz comum aos três: a Fase 2 foi implementada e testada via pytest com mocks/schemas simplificados, sem uma passagem ao vivo contra o fluxo real da UI — exatamente o que o Cenário C1 existe para pegar.

### Correção

| Arquivo | Mudança |
|---|---|
| `backend-crm/services/jobs_service.py` | `cancel_pending_appointment_jobs` movida para aqui (de `routes/appointments.py`) para ser compartilhada; usa `status='completed'` + `result={"skipped":true,...}` em vez de `'cancelled'`. Nova `schedule_appointment_reminder_jobs` (movida de `routes/appointments.py::_schedule_reminder_jobs`). |
| `backend-crm/services/briefing_service.py` | Nova `schedule_briefing_job_for_appointment` (wrapper que resolve `briefing_enabled`/`briefing_lead_time` do AI Profile — movida de `routes/appointments.py::_schedule_briefing_job`). |
| `backend-crm/routes/appointments.py` | Usa as funções compartilhadas acima em vez das cópias locais; `update_appointment` agora faz `conn.commit()` após cancelar/reagendar jobs; `delete_appointment` também cancela jobs pendentes (mesma lacuna, mesma correção). |
| `backend-crm/routes/leads.py` | **`criar_compromisso`** passa a agendar jobs de lembrete/briefing (faltava por completo). **`atualizar_compromisso`**: ao cancelar, cancela jobs pendentes e usa `gcal_delete` em vez de `gcal_update`; ao reagendar (`start_at` mudou), cancela jobs antigos e cria novos para o novo horário; `conn.commit()` adicionado ao final. **`remover_compromisso`** (DELETE) também cancela jobs pendentes. |
| `backend-crm/tests/test_appointment_job_cleanup.py` | Schema de teste passa a incluir o `CHECK` real da tabela `jobs` (teria pego o bug do status `'cancelled'`); asserções atualizadas para `status='completed'` + `result`. |

### Commits Fase 3

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `e70ecdd` | Correção dos 3 gaps encontrados no teste do Cenário C1 |

### Relatório da Fase 3 — o que mudou na prática

**Antes (mesmo depois da Fase 2):** criar um compromisso pela tela do lead (o fluxo que qualquer operador realmente usa) nunca agendava lembrete nem briefing — a Fase 2 só tinha corrigido uma rota alternativa que a UI não chama quando já sabe o lead. Cancelar pela UI quebrava com erro 500 (constraint do banco). Mesmo corrigindo o status, as mudanças nos jobs não ficavam salvas.

**Agora:** criar, cancelar e reagendar um compromisso pela tela do lead (testado ao vivo, ponta a ponta) cria, cancela e recria os lembretes corretamente — confirmado lendo o banco de dados diretamente após cada ação, não só pela resposta da tela.

**Para validar:** Cenário C1 validado ao vivo (ver acima). Suítes automatizadas de `backend-crm` e `backend-executors` continuam sem regressão (mesmas falhas pré-existentes, confirmadas via `git stash` antes/depois).

---

## Fase 4 — Diagnóstico + Correção: paridade Playground + bugs revelados pelo Cenário P1 (21/06/2026)

### Problema identificado

O utilizador pediu para testar via Playground (lead agendando, pedindo para cancelar e remarcar). Investigação prévia (antes de tentar) revelou que o Playground **não exercitaria o caminho novo**: `build_context_bundle_for_playground`/`enrich_context_bundle` nunca propagava `bot_disabled`/`bot_disabled_reason` no `metadata` — só `routes/executor.py` (fluxo real) fazia isso. Sem essa paridade, `decision_engine.decide()` nunca chamaria `_decide_post_meeting_management()` no Playground.

Decisão (confirmada com o utilizador): corrigir a paridade em vez de pular o teste. Ao corrigir e testar ao vivo, mais 3 bugs apareceram:

1. **`playground_internal.py` nunca chamava `handle_meeting_cancel_or_reschedule`** — só `handle_meeting_scheduled`. O bot respondia "cancelado"/"reagendado" mas nada mudava no banco (mesmo padrão de falso-positivo que todo o M1 existe para eliminar — desta vez no próprio código novo).
2. **Prompt de `_build_child_prompt_meeting_management` hesitante:** mesmo com dia+horário explícitos na mensagem ("posso mudar para domingo às 11h?"), o LLM às vezes respondia "vou confirmar" sem preencher `meeting_reschedule_requested=true` no mesmo turno — exigindo outro turno para committar, ao contrário do cancelamento (que já era direto).
3. **`routes/appointments.py::update_appointment` — `AttributeError: 'AppointmentUpdate' object has no attribute 'lead_id'`:** bug pré-existente (não introduzido pelo M1) nunca antes exposto porque nenhum caller real batia neste endpoint sem passar `lead_id` — `crm_client.reschedule_appointment()` foi o primeiro. Causava 500 em todo `PUT /api/appointments/{id}`, ou seja, **todo reagendamento real (via IA) estava silenciosamente falhando** mesmo depois da Fase 3.

### Correção

| Arquivo | Mudança |
|---|---|
| `backend-crm/services/ai_orchestrator/orchestrator.py` | `enrich_context_bundle`: propaga `bot_disabled`/`bot_disabled_reason` no `metadata` quando `reason == "meeting_scheduled"` (só este motivo — outros, como `handoff_requested`, continuam não propagados no Playground, propositalmente). |
| `backend-executors/app/api/playground_internal.py` | Passa a chamar `meeting_scheduler.handle_meeting_cancel_or_reschedule()` ao lado de `handle_meeting_scheduled()`, mesmo padrão de `app/runners/whatsapp.py`. |
| `backend-executors/app/services/decision_engine.py` | `_build_child_prompt_meeting_management`: instrução de reagendamento reforçada — proíbe respostas hesitantes ("vou confirmar", "um momento") quando dia+horário já foram informados; exige `meeting_reschedule_requested=true` no mesmo turno. |
| `backend-crm/routes/appointments.py` | `update_appointment`: remove todas as referências a `payload.lead_id` (campo que não existe em `AppointmentUpdate` — `lead_id` não é alterável por este endpoint, por design). |
| `backend-crm/tests/test_calendar_busy_slots.py` | 3 testes novos para a propagação de `bot_disabled` em `enrich_context_bundle`. |
| `backend-crm/tests/test_update_appointment_route.py` | 2 testes novos — regressão do `AttributeError`, chamando a rota de verdade (não mockada) com um payload sem `lead_id`. |

### Commits Fase 4

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `ecb4cbb` | Paridade Playground + 3 bugs corrigidos |

### Relatório da Fase 4 — o que mudou na prática

**Antes:** o Playground não conseguia testar cancelamento/reagendamento de forma realista — silenciosamente caía no fluxo de vendas normal. Mesmo corrigindo isso, o reagendamento via IA continuava falhando de verdade (erro 500 interno) em qualquer canal — Playground ou WhatsApp real — porque o endpoint que aplica a mudança tinha um bug não relacionado ao M1, nunca antes exposto.

**Agora:** uma sessão completa no Playground — agendar, cancelar (bot reativado), agendar de novo, reagendar (mantendo o bot em modo de gestão) — funciona ponta a ponta, confirmado lendo o banco de dados a cada passo. O reagendamento real (IA confirmando um novo horário para um compromisso já existente) passa a funcionar em qualquer canal, não só no Playground.

**Para validar:** Cenário P1 validado ao vivo (ver acima). Suítes automatizadas sem regressão (mesma baseline pré-existente).

---

## Fase 5 — Toggle de conta: bot fica disponível ou desativa com handoff após confirmar reunião

### Problema identificado

As Fases 1–4 fizeram o bot reabrir e gerir cancelamento/reagendamento de forma **incondicional**, para todas as contas, sempre que `bot_disabled_reason="meeting_scheduled"`. O utilizador pediu uma camada de escolha por conta: cada usuário decide se quer esse comportamento, ou prefere que o bot fique mudo após confirmar a reunião (handoff manual, comportamento anterior ao M1).

Investigação no AI Profile (`backend-core/app/models/ai_profile.py`, `app/api/ai_profiles.py`) não encontrou nenhum campo equivalente. Os candidatos mais próximos (`handoff_policy`, `requires_handoff`) pertencem a um mecanismo diferente — disparam apenas quando a pipeline Mãe/Filha decide `next_action="handoff"` durante qualificação/venda (`backend-executors/app/services/handoff_policy.py`). O gate pós-confirmação de reunião é um curto-circuito separado (mesmo padrão de `fast_path`), então reaproveitar `handoff_policy` misturaria dois conceitos distintos.

### Correção

Novo campo booleano no AI Profile: **`meeting_management_enabled`** (default `True` — obrigatório, não é preferência de produto: o comportamento das Fases 1–4 já está em produção para todas as contas; um default `False` desativaria silenciosamente uma capacidade já existente).

| Arquivo | Mudança |
|---|---|
| `backend-core/app/models/ai_profile.py` | Nova coluna `meeting_management_enabled` (Boolean, default `True`). |
| `backend-core/app/db.py::ensure_ai_profile_columns()` | Nova entrada de migração idempotente, mesmo padrão de `briefing_enabled`. |
| `backend-core/app/api/ai_profiles.py` | `meeting_management_enabled: bool = True` em `AIProfileBase`; `Optional[bool] = None` em `AIProfileUpdate`. |
| `backend-crm/services/whatsapp_inbound/inbound_handler.py` | Gate de job creation (Fase 1): só deixa passar quando `bot_disabled_reason == "meeting_scheduled"` **e** `meeting_management_enabled` é `True`. Lê do `ai_profile` já resolvido em `_ai_profile_for_delay`, sem fetch extra. |
| `backend-crm/routes/executor.py` | Propagação de `bot_disabled_reason` para o fluxo real (Fase 1): suprime o reason `"meeting_scheduled"` quando `meeting_management_enabled` é `False` — `decision_engine.decide()` cai automaticamente no branch padrão `BOT_DISABLED_DECISION` (ignore), sem precisar de branch novo. |
| `backend-crm/services/ai_orchestrator/orchestrator.py::enrich_context_bundle` | Mesma condição aplicada ao bloco "B6" da Fase 4 (paridade Playground) — ver correção abaixo, a versão inicial deste ponto tinha um bug. |
| `frontend-crm/src/types/agente.ts` | Novo campo `meeting_management_enabled: boolean` em `AgentConfig` e `DEFAULT_AGENT_CONFIG` (`true`). |
| `frontend-crm/src/services/api.ts` | Mapeamento explícito campo-a-campo em `getConfig`/`saveConfig` (perto de `scheduling_offer_style`). |
| `frontend-crm/src/components/agente/CamadaApresentacao.tsx` | Nova seção "Gestão pós-confirmação" — `EditCard` + modal de 2 opções ("Bot continua disponível" / "Desativar bot e aguardar handoff manual"), mesmo padrão de `ModalSchedulingOfferStyle`. |
| `backend-crm/tests/test_calendar_busy_slots.py` | 2 testes novos em `EnrichContextBundleBotDisabledTest` (não propaga o reason especial quando desligado; propaga quando ligado explicitamente). |
| `backend-crm/tests/test_meeting_management_gate.py` | Novo arquivo, 4 testes — gate de `inbound_handler.py` (skip quando desligado, passa quando ligado, passa por default quando o perfil não tem o campo ainda, e outros `bot_disabled_reason` continuam bloqueados independente do toggle). |

### Correção adicional: bug revelado pelo teste ao vivo do Cenário P2

A primeira versão do bloco "B6" em `enrich_context_bundle` só propagava `bundle.metadata["bot_disabled"]` **dentro** da condição que incluía `meeting_management_enabled` — ou seja, quando o toggle estava desligado, `metadata.bot_disabled` não era setado de forma alguma. Resultado observado ao testar ao vivo no Playground: em vez do bot ficar mudo, `decision_engine.decide()` não encontrava `metadata.bot_disabled=True` e caía na pipeline normal Mãe/Filha — o bot respondia normalmente ao pedido de cancelamento ("Entendi, vamos cancelar a sessão...", "Você gostaria de remarcar para outro dia?"), o oposto do comportamento esperado (e mais permissivo que o handoff manual pretendido).

**Causa raiz:** confundir "suprimir o reason especial `meeting_scheduled`" com "não marcar como desativado". O padrão correto (já usado em `routes/executor.py` desde o início) é: `bot_disabled=True` propaga sempre que o lead está de fato desativado por este motivo — só o `bot_disabled_reason` (o valor `"meeting_scheduled"` especificamente) é que depende do toggle.

**Correção:** `enrich_context_bundle` agora sempre seta `bundle.metadata["bot_disabled"] = True` quando `lead.bot_disabled` e `lead.bot_disabled_reason == "meeting_scheduled"`; o `bot_disabled_reason` no metadata só recebe `"meeting_scheduled"` quando `meeting_management_enabled` é `True` — caso contrário fica `None`, fazendo `decide()` cair em `BOT_DISABLED_DECISION` (ignore), igual ao fluxo real.

Decisão deliberada de não alterar: `docs/architecture/admin-agents-contract.md`/`AdminAgents.tsx` (o contrato só lista campos que afetam estágio/categoria do Kanban — `handoff_policy`, `requires_handoff` e `briefing_enabled` também não estão lá, mesmo precedente); `decision_engine.py::decide()` e `meeting_scheduler.py` (nenhuma mudança necessária — o gate em `executor.py`/`enrich_context_bundle` já resolve, suprimindo o reason antes de chegar ao `decide()`).

### Commits Fase 5

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `329fc05` | Toggle de conta `meeting_management_enabled` — backend-core, 3 gates no backend-crm, UI no frontend-crm, testes |
| 2 | `7a09f62` | Correção do bug em `enrich_context_bundle` revelado pelo teste ao vivo do Cenário P2 |

### Relatório da Fase 5 — o que mudou na prática

**Antes:** o comportamento das Fases 1–4 (bot reabre e gerencia cancelamento/reagendamento após confirmar reunião) era fixo para todas as contas — não havia como o usuário optar por manter o bot totalmente mudo após confirmar (handoff manual puro).

**Agora:** em "Configuração do Agente → Apresentação → Gestão pós-confirmação", o usuário escolhe entre as duas opções. Por padrão (contas existentes e novas) o comportamento continua igual ao das Fases 1–4 — nada muda até o usuário desligar explicitamente. Quando desligado, um pedido de cancelamento/remarcação do lead após a reunião confirmada não chega mais à IA — o bot fica mudo para esse lead, exatamente como qualquer outra desativação manual, e só volta a responder se o operador reativar pelo "Reativar bot" no card do lead. Esse comportamento (silêncio total quando desligado) só passou a funcionar de verdade depois da correção do bug acima — a primeira versão deixava o bot responder normalmente no Playground.

**Para validar:** `npx tsc --noEmit` sem erros no frontend-crm. 6 testes automatizados novos passando (`test_calendar_busy_slots.py` + `test_meeting_management_gate.py`), mais os 8 testes pré-existentes de `backend-executors/tests/test_meeting_management.py` confirmando que nenhuma mudança foi necessária em `decide()`. Suítes completas de `backend-crm` (147 testes) e `backend-executors` (113 testes) sem regressão — mesmas falhas pré-existentes de antes desta fase, confirmadas via `git stash`/`git stash pop`. Cenário P2 validado ao vivo via Playground (chrome-devtools MCP) com os 3 serviços backend reiniciados para captar a migração — revelou e permitiu corrigir o bug descrito acima; lead/appointments de teste (#294, #295) removidos e o toggle revertido para "Bot continua disponível" ao final.

## Ajustes Possíveis Pós-Implementação

- Pedido de handoff humano explícito durante a janela `meeting_scheduled`-disabled não escala para humano — fica para iteração futura.
- Appointment fora da janela de 30 dias de `calendar_busy_slots` não é localizado.
- Mudança de categoria do lead (Kanban) não é tocada por este fluxo — território do M2.
- Gap de autenticação pré-existente em `routes/appointments.py` (`create_appointment`/`update_appointment`/`mark_canceled` sem `Depends(require_crm_access)`) não é corrigido aqui.
- **Achado não corrigido (fora de escopo):** `services/followup_state.py::_cancel_pending_jobs_for_lead` também usa `UPDATE jobs SET status = 'cancelled'`, o mesmo valor fora do `CHECK` constraint que causava o erro 500 corrigido na Fase 3. Isso sugere que `POST /leads/{id}/followup/pause` e `/followup/cancel` podem estar falhando silenciosamente em produção ao tentar cancelar jobs pendentes — não verificado nem corrigido aqui, pois é código de follow-up fora do escopo do M1; vale uma investigação dedicada.
