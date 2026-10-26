# Agente 03 · Híbrido — Assistente Comercial com Agendamento Inteligente

> Nome e etapas: página **Tipos de Agentes** (`/agentes-info`, `frontend-crm/src/pages/TiposAgentes.tsx`).
> Preset: `AGENT_PRESETS.a3` em `frontend-crm/src/types/agente.ts`.
> Prompts das LLMs: [`docs/prompts_llms.md`](../../prompts_llms.md). Fases comuns:
> [`pipeline-phases.md`](../pipeline-phases.md), [`sales-flow.md`](../sales-flow.md); agenda:
> [`agenda.md`](../agenda.md).

**Para quem (página):** coaches, terapeutas, personal trainers, consultores solo, serviços por hora.
Recepcionista comercial: qualifica, agenda e entrega o lead preparado ao profissional; não apresenta nem
fecha, e trata do follow-up depois da sessão.

---

## Configuração

| Campo | Valor do preset | Efeito |
|---|---|---|
| `template_key` | `hybrid_scheduler` | `agent_type` = `agent_3`; está em `_SCHEDULING_AGENT_TEMPLATES` → closing desligado para o bot; playbook de follow-up `hybrid_scheduler_followup` (`agent_type.FOLLOWUP_PLAYBOOK_MAP`) |
| `agent_mode` | `agenda` | fases p0 → p1 → p2 → p3a → p3b → p4 → p5 |
| `presentation_variant` | `scheduler`, ou `sales` com `appointment_mode=commercial` (o frontend deriva-o) | `decision_engine._resolve_presentation_variant` |
| `appointment_mode` | `exploratory` (omissão) ou `commercial` | só tem efeito com `hybrid_scheduler`: `commercial` apresenta serviços e preços e procura compromisso antes de agendar |
| `qualification_required_fields` | sugestão ao criar: `service_interest`, `availability_window` | editável; vazio = nenhum obrigatório |

---

## Etapas da página → o que o sistema faz

| Etapa (página) | Quem | No sistema |
|---|---|---|
| Inbound: Entrada — Interesse Ativo Demonstrado | bot | p0; `origin_inbound_opener`; `identity_mode` (assistente do profissional) |
| Inbound: Confirma que é o Público Certo | bot | p1; campos obrigatórios / `qualification_fields` |
| Outbound: Prospecção com Tom Pessoal | bot | `origin_outbound_opener`; `leads.origin = "outbound"` |
| Outbound: Desperta a Dor / Valida o Fit | bot | p1 |
| Aprofunda a Dor + Coleta Contexto | bot | p1/p2; a conversa entra no dossiê |
| Aquecimento — Ancora Valor | bot | p2; estágio de aquecimento (só `hybrid_scheduler`, ver [`pipeline-phases.md`](../pipeline-phases.md)); prova social e conhecimento da Base de Conhecimento; mídias por blocos `midia`/gatilhos de intenção do Fluxo de Venda |
| Agendamento Automático | bot | p3a/p3b; ver "Agenda" abaixo; lembretes; dossiê ao profissional (`briefing_service.py`) |
| Você Faz a Sessão | humano | bot desligado depois da marcação (`bot_disabled_reason = meeting_scheduled`); só responde a cancelar/remarcar (`_decide_post_meeting_management`) |
| Follow-up Pós-Sessão | bot | variante `hybrid_scheduler` (máx. 3); resultado no `FollowUpTransitionModal` |
| Retenção e Renovação de Pacote | bot + humano | só o check-in de cliente inativo (`client_checkin`, [`followup.md`](../followup.md)) |

---

## Agenda (o que o código decide, não a IA)

- **Horário livre e dentro do expediente:** `requested_slot.py` e `professional_hours.py` decidem e passam
  o veredicto à Filha como facto. Os horários de cada profissional são lidos de texto livre
  (`custom_instructions`; o campo próprio `professional_availability` já é lido pelo código, mas ainda não
  existe no AI profile — `fix-disponibilidade-campo-duplo-sentido`).
- **Data certa:** `meeting_date_guard.py` confere a data gravada contra o dia pedido; a tabela de dias vai
  no prompt (`_calendar_lookup_table_pt`).
- **Ocupados:** `orchestrator._load_calendar_busy_slots` (marcações do CRM + Google sincronizado ao montar o
  contexto); conflitos comparados como datas.
- **Estilo:** `scheduling_offer_style` — `offer_alternatives` (propõe 2–3 horários mesmo sem conflito) ou
  `confirm_exact` (confirma o pedido quando está livre).
- **Agenda única por conta:** vários profissionais partilham os conflitos de horário.

## Outros comportamentos

- **Closing nunca é do bot** (`_enforce_scheduling_agent_no_closing`).
- **Lembretes:** sem `appointment_reminder_offsets`, 24h e 2h antes (`jobs_service._REMINDER_DEFAULTS_BY_TEMPLATE`).
- **Follow-up por inatividade** (`followup_auto_trigger_enabled`): elegível como `agent_3`, variante
  `hybrid_scheduler`.
- **Resultado da sessão** (`FollowUpTransitionModal.tsx`): "Interessado, mas ainda não fechou", "Precisa
  reagendar", "Perdido".

---

## Prometido na página vs. código

| Promessa | Estado |
|---|---|
| Calendário em tempo real — Google Calendar | ✅ sync automática antes de propor horários |
| Calendário em tempo real — Calendly | ❌ o ecrã oferece a opção; sem código no backend |
| Confirmação dupla WhatsApp + e-mail | ❌ só WhatsApp (nenhum envio de e-mail no fluxo de marcação) |
| Lembretes 24h e 2h | ✅ padrão do template |
| Briefing ao profissional | ✅ `briefing_service.py` |
| Resultado Fechou / Não fechou / Reagendar | ⚠️ o modal tem "Não fechou", "Reagendar" e "Perdido"; "Fechou" não é uma opção do modal |
| Aquecimento com prova social e preview da sessão | ✅ estágio de aquecimento + Base de Conhecimento |
| Agendamento recorrente, materiais pré-sessão, renovação de pacote | ❓ não encontrado (só `client_checkin`) |

---

## Limites medidos

Diagnóstico de uma conta real deste agente (26/10/2026), estado em
`docs/plans/plano-sprint-2026-10-26-agenda-sensi-vitae.md` e `docs/implementations/`: datas, horários livres
recusados, conflitos por texto e Google sem permissão já corrigidos; pendentes à data — confirmação que grava
uma proposta antiga, saudação sem a hora local, p3a/p3b sem os blocos do Fluxo de Venda, margem entre sessões,
remarcação que grava a contraproposta, campo de disponibilidade com duplo sentido.

---

## Ficheiros críticos

`backend-executors/app/services/decision_engine.py` (Filhas de pré-agendamento e agendamento, aquecimento,
`_enforce_scheduling_agent_no_closing`, `_decide_post_meeting_management`) ·
`backend-executors/app/services/{requested_slot,professional_hours,meeting_date_guard,meeting_scheduler}.py` ·
`backend-crm/services/ai_orchestrator/orchestrator.py` · `backend-crm/routes/appointments.py` ·
`backend-crm/services/google_calendar_sync.py` · `backend-crm/services/briefing_service.py` ·
`backend-crm/services/jobs_service.py` · `backend-crm/services/followup_state.py`.
