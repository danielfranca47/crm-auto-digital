# Agente 01 · Robusto — SDR de Alto Ticket

> Nome e etapas: página **Tipos de Agentes** (`/agentes-info`, `frontend-crm/src/pages/TiposAgentes.tsx`).
> Preset: `AGENT_PRESETS.a1` em `frontend-crm/src/types/agente.ts`.
> Prompts das LLMs: [`docs/prompts_llms.md`](../../prompts_llms.md). Fases comuns:
> [`pipeline-phases.md`](../pipeline-phases.md) e [`sales-flow.md`](../sales-flow.md).

**Para quem (página):** imóveis, advocacia, clínicas estéticas, consultorias B2B — ciclo longo, alto
ticket. Qualifica a fundo antes de acionar o humano; o humano apresenta e fecha.

---

## Configuração

| Campo | Valor do preset | Efeito |
|---|---|---|
| `template_key` | `sdr_padrao` | `agent_type` = `agent_1` (`backend-crm/services/agent_type.py::map_template_key_to_agent_type`); está em `_SCHEDULING_AGENT_TEMPLATES` → closing desligado para o bot |
| `agent_mode` | `sdr_scheduler` | normalizado para `agenda` — ou para `consultivo` se `human_in_loop`/`requires_handoff` estiver ligado (ver abaixo) |
| `presentation_variant` | `scheduler` (por omissão de `agenda`/`consultivo`) | `decision_engine._resolve_presentation_variant` |
| `qualification_required_fields` | sugestão ao criar: `service_interest`, `availability_window` | editável; vazio = nenhum obrigatório (`backend-core/app/api/ai_profiles.py::_DEFAULT_QUAL_FIELDS`) |

### Normalização do modo — duas leituras diferentes

| Onde | `sdr_scheduler` vira… |
|---|---|
| `backend-executors` — `decision_engine._compute_system_agent_mode` (o que decide o comportamento da IA) | `consultivo` se `human_in_loop` ou `requires_handoff` (perfil, playbook ou metadata) estiver ligado; senão `agenda` |
| `backend-crm` — `orchestrator._normalize_agent_mode_for_bundle` (o que vai no ContextBundle) | sempre `agenda` |

Com esses campos ligados, as duas camadas discordam do modo. Fases ativas por modo: `agenda` →
p0 → p1 → p2 → p3a → p3b → p4 → p5; `consultivo` → p0 → p1 → p2 → p4 → p5 (sem pré-agendamento e
agendamento).

---

## Etapas da página → o que o sistema faz

| Etapa (página) | Quem | No sistema |
|---|---|---|
| Inbound: Entrada do Lead — Dor Declarada | bot | p0; `origin_inbound_opener`; origem inbound = qualquer `leads.origin` ≠ `"outbound"` |
| Inbound: Filtro 1 — Validação de Fit | bot | p1; `qualification_fields` (`question`, `passive_hint`, `qualify_if`, `disqualify_if`, `mode`, `group: f1`) |
| Outbound: Prospecção Ativa — Fit Presumido | bot | `origin_outbound_opener`; `leads.origin = "outbound"` |
| Outbound: Filtro 2 — Investigação de Dor | bot | p1; campos com `group: f2` |
| Outbound: Filtro 1 — Reforço de Fit | bot | p1 |
| Filtro 3 — Poder, Prioridade, Preço, Timing | bot | 4Ps em `qualification_state.py::compute_4p_scores` (`decision_role`, `urgency`, `budget_or_price_acceptance`, `availability_window`); gate `qualification_score_threshold` em `qualification_guardrails.py` |
| Agendamento + Handoff para Humano | bot + humano | p3a/p3b (modo `agenda`); dossiê `briefing_service.py` (`briefing_enabled`, `briefing_lead_time` 120 min, para `operator_whatsapp`); lembretes |
| Apresentação Comercial | humano | bot desligado ao confirmar a marcação; temperatura registada no `FollowUpTransitionModal` |
| Follow-up Pós-Apresentação por Temperatura | bot | variante `sdr_scheduler` (`routes/leads.py`, máx. 4 tentativas); `buying_signal_keywords` notifica |
| Fechamento | humano | `_enforce_scheduling_agent_no_closing` redireciona `closing` do bot |
| Pós-Venda / Onboarding | bot + humano | webhook de pagamento → `client-list` + boas-vindas (`routes/webhooks.py`) |

---

## Comportamento próprio deste agente

- **Closing nunca é do bot.** `_enforce_scheduling_agent_no_closing` (`decision_engine.py`) troca `closing`
  pela categoria atual (se já em agendamento) ou por `apresentation`.
- **Guardrails de modo** (`decision_engine._apply_mode_guardrails`):
  - `consultivo`: `outcome="won"` é anulado; ir para closing vira handoff ("vou te encaminhar para um
    especialista humano…").
  - `agenda`: se faltam `availability_window` ou `location_preference` (quando obrigatórios), closing volta
    a `qualification` (`guardrail_agenda_missing_booking`).
- **Bot desliga ao entrar em closing** quando há reunião marcada ou o modo é `agenda`
  (`lead_category_policy.apply_closing_bot_disable_side_effect`).
- **Lembretes:** sem `appointment_reminder_offsets`, 24h e 1h antes (`jobs_service._REMINDER_DEFAULTS_FALLBACK`).
- **Follow-up automático por inatividade** (`followup_auto_trigger_enabled`): elegível como `agent_1` →
  variante `sdr_scheduler` (`followup_state.resolve_auto_inactivity_variant`).
- **Temperatura pós-reunião** (`FollowUpTransitionModal.tsx`): Quente / Morno / Frio / Perdido.

---

## Prometido na página vs. código

| Promessa | Estado |
|---|---|
| Filtros 1, 2 e 3 com score dos 4Ps | ✅ (score só pontua as 4 chaves clássicas — campos personalizados não contam; `docs/plans/qualificacao-score-generalizado-melhorias-futuras.md`) |
| Calendário integrado, confirmação automática | ✅ Google Calendar (agenda de marcações + sync); ❌ Calendly — o ecrã oferece a opção, mas não há código no backend |
| Dossiê automático com 4Ps e canal | ✅ `briefing_service.py` |
| Lembretes 24h e 1h | ✅ padrão do template |
| Follow-up por temperatura | ✅ temperaturas no modal, variante `sdr_scheduler` |
| Sinal de compra notifica o vendedor | ✅ `buying_signal_keywords` |
| Sequência multicanal WhatsApp → e-mail → LinkedIn | ❓ não encontrado no código do agente |
| Reativação de "Perdido" em 30–60 dias | ❓ não encontrado |
| Pós-venda: formulário de onboarding, NPS | ❓ não encontrado (só boas-vindas do webhook de pagamento) |

---

## Ficheiros críticos

`backend-executors/app/services/decision_engine.py` (`_compute_system_agent_mode`, `_apply_mode_guardrails`,
`_enforce_scheduling_agent_no_closing`) · `backend-crm/services/qualification_state.py` ·
`backend-crm/services/qualification_guardrails.py` · `backend-crm/services/briefing_service.py` ·
`backend-crm/services/jobs_service.py` · `backend-crm/routes/leads.py` (variantes de follow-up) ·
`backend-crm/services/followup_state.py` · `backend-crm/services/lead_category_policy.py` ·
`frontend-crm/src/components/FollowUpTransitionModal.tsx`.
