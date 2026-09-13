# Cancelamento/Reagendamento de Reunião — Melhorias Futuras

> Contexto: identificado durante a implementação e graduação de
> `docs/implementations/etapa-followup-cancelamento-reagendamento.md` (M1 — Ação
> real de cancelamento/reagendamento de compromisso, incluindo o toggle de conta
> `meeting_management_enabled`). Itens deixados deliberadamente fora do escopo
> dessa implementação — registados aqui para retomar quando fizer sentido.

---

## M1 — Pedido de atendimento humano não é encaminhado na janela pós-confirmação

**Prioridade: BAIXA** (sem caso de uso reportado em produção; gap teórico)

**Estado actual:** quando `bot_disabled_reason="meeting_scheduled"` e o toggle `meeting_management_enabled` está ligado, `decision_engine._decide_post_meeting_management()` só sabe classificar a mensagem do lead em três baldes: cancelamento, reagendamento, ou "nenhum dos dois" (resposta mínima). Não existe detecção de pedido explícito de atendimento humano ("quero falar com uma pessoa", "chama o atendente") dentro dessa janela específica — esse pedido cai no balde "nenhum dos dois" e recebe a resposta mínima padrão, em vez de ser escalado.

**Risco concreto:** um lead que pede para cancelar a reunião e, na mesma janela, insiste em falar com um humano por algum motivo (ex.: reclamação, pedido fora do escopo de cancelar/remarcar) não é encaminhado — o `handoff_policy`/`fast_path.try_fast_handoff()` não são chamados a partir deste caminho dedicado.

**O que precisaria existir (a confirmar em Plan Mode na implementação):** detectar esse sinal dentro de (ou antes de) `_decide_post_meeting_management()` e rotear para `handoff_policy.apply()`, reaproveitando a mesma lógica de `identity_mode`/`handoff_custom_text` já usada no resto do pipeline.

---

## M2 — Reuniões marcadas para mais de 30 dias no futuro não são localizadas para cancelar/remarcar

**Prioridade: BAIXA** (limitação rara na prática — maioria das reuniões é marcada para os próximos dias/semanas)

**Estado actual:** `handle_meeting_cancel_or_reschedule()` (`backend-executors/app/services/meeting_scheduler.py`) localiza o appointment do lead filtrando `context["calendar_busy_slots"]` — que só cobre uma janela de `CALENDAR_CONFLICT_WINDOW_DAYS = 30` dias a partir de agora (mesma janela usada para checagem de conflito de horário, ver `docs/architecture/agenda.md`).

**Risco concreto:** se a reunião confirmada estiver marcada para mais de 30 dias no futuro, um pedido de cancelamento/reagendamento via IA não encontra o appointment — a função retorna sem fazer nada, silenciosamente (sem erro visível ao lead nem ao operador).

**O que precisaria existir:** uma busca dedicada por `lead_id` (sem depender da janela de conflito geral, que existe por outro motivo — verificar disponibilidade do profissional), ou aumentar a janela especificamente para este caso.

---

## M3 — Cancelamento/reagendamento via IA não move o card do lead no Kanban

**Prioridade: BAIXA** (decisão deliberada de escopo, não um bug)

**Estado actual:** `_decide_post_meeting_management()` nunca define `suggested_category` — cancelar ou reagendar uma reunião via IA não move o lead entre colunas do quadro visual de vendas.

**Decisão já tomada:** fora de escopo do M1 — território do M2 do plano original (`docs/plans/followup-proativo-e-cancelamento-agenda.md`, item de disparo automático de follow-up), que ainda está pendente de implementação. Revisitar apenas se, ao implementar esse M2, fizer sentido também mover a categoria neste fluxo.
