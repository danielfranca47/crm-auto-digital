# Agentes de Agenda — Melhorias Futuras (multi-profissional e closing seletivo)

> Contexto: identificado na sessão de testes manuais locais de 19/06/2026 das
> implementações `disponibilidade-real-agendamento-ia.md` e
> `desativar-closing-hibrido-agendador.md`. Ambos os itens abaixo foram
> deliberadamente deixados fora do escopo dessas implementações por decisão
> explícita do utilizador — registados aqui para retomar quando fizer sentido.

---

## M1 — Suporte a múltiplos profissionais/agendas por conta

**Prioridade: BAIXA** (sem demanda comercial confirmada ainda — depende dos planos Scale/Enterprise)

**Estado actual:** o sistema assume **um único profissional/agenda por conta**, para todos os planos (Start e Growth). Isto está hardcoded implicitamente em dois mecanismos:

1. `calendar_busy_slots` (`backend-crm/services/ai_orchestrator/orchestrator.py`, `_load_calendar_busy_slots()`) — carrega todos os appointments do `user_id`, sem distinguir profissional.
2. `_check_conflict` (`backend-crm/routes/appointments.py` e `routes/leads.py`, duas implementações paralelas) — bloqueia conflito por `user_id` inteiro, não por profissional individual.

**O que precisaria mudar:** introduzir uma dimensão `professional_id` (ou equivalente) em:
- Tabela `appointments` (nova coluna, FK para uma futura tabela de profissionais)
- `calendar_busy_slots` — filtrar por profissional, não só por conta
- `_check_conflict` (ambas implementações) — mesmo ajuste
- AI Profile — cada agente precisaria de saber a qual profissional está associado
- UI da Agenda — selector de profissional, ou vista combinada com indicação visual de qual profissional cada evento pertence

**Decisão já tomada pelo utilizador (não reabrir sem novo contexto):** "por enquanto nos planos start e growth será apenas 1 profissional por conta. futuramente nos planos maiores scale e enterprise iremos implementar uma nova feature para gerenciar mais de uma agenda para outros profissionais em uma conta corporativa."

**Relação com `scale-enterprise-roadmap.md`:** este item é complementar ao roadmap de multi-instância WhatsApp já documentado nesse arquivo (que cobre `max_instances`) — multi-profissional é uma dimensão diferente (agenda/calendário), não substitui nem depende da multi-instância.

---

## M2 — Reativar "closing" para agentes de agendamento em cenários específicos

**Prioridade: BAIXA** (melhoria futura explicitamente deferida, sem caso de uso urgente reportado)

**Estado actual:** `_enforce_scheduling_agent_no_closing()` em `backend-executors/app/services/decision_engine.py` impede que `sdr_padrao` e `hybrid_scheduler` (`_SCHEDULING_AGENT_TEMPLATES`) cheguem à categoria `"closing"` — qualquer decisão da LLM Mãe que apontasse para `closing` é redirecionada para a categoria actual (se já em agendamento/pré-agendamento) ou `apresentation`. Ver `docs/architecture/pipeline-phases.md`, secção "Agentes de agendamento — 'Closing' desativado por design".

**Motivação original do bloqueio:** confirmar um horário de sessão recorrente não é uma venda fechada — a Mãe interpretava "confirmação = fechamento" e silenciava o bot via `guardrail_sdr_escalate_closing`, mesmo sem handoff real.

**O que o utilizador já indicou como direcção futura:** "Talvez depois eu considere ativar quando se tratar de uma negociação de pacotes ou packs ou plano de recorrência em uma campanha de follow up."

**O que precisaria ser construído:**
- Um sinal diferenciado entre "confirmação de sessão única" (deve continuar bloqueado) e "negociação de pacote/plano de recorrência" (deveria poder chegar a closing) — hoje a Mãe não distingue os dois casos
- Provavelmente um novo campo de sinal estruturado em `MotherDecision.signals` (ex.: `offer_item_name`/`price_acceptance` já existem parcialmente — avaliar se servem ou se é preciso um sinal novo, ex.: `package_negotiation: bool`)
- Ajustar `_enforce_scheduling_agent_no_closing()` para permitir `closing` apenas quando esse sinal estiver presente, mantendo o bloqueio para o caso comum (confirmação de sessão)
- Provavelmente ligado a campanhas de follow-up especificamente (o utilizador mencionou "campanha de follow up") — avaliar se o gatilho deve vir do `followup_state`/`followup_reconciler` em vez do fluxo de mensagem normal

**Risco a não esquecer:** reativar `closing` sem o sinal diferenciado correto reintroduz o bug original (bot mudo ao confirmar uma sessão simples) — qualquer implementação aqui precisa do teste de regressão `test_scheduling_agent_no_closing.py` a continuar verde.
