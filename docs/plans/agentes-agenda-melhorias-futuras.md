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

---

## M3 — Confirmação de agendamento sem garantia de que o lead confirmou de fato

**Prioridade: BAIXA** (monitorar frequência em uso real antes de agir — sem caso confirmado de impacto em produção ainda)

**Contexto:** identificado na sessão de testes manuais de 19/06/2026 das implementações
`fix-compound-follow-through-recepcao.md` e `feat-playground-appointment-tag.md`.

**Estado actual:** a criação do appointment (`meeting_scheduler.handle_meeting_scheduled()`)
depende inteiramente de `mother_decision.signals.meeting_scheduled`, decidido pela LLM Mãe a
cada turno, sem nenhum estado persistido entre mensagens (ex.: "proposta enviada, esperando
confirmação"). O prompt da Mãe já instrui que `meeting_scheduled=true` só deve ser emitido
quando a mensagem do lead contém confirmação explícita ("fica combinado", "perfeito",
"fechado", etc.) — mas isto é só instrução de prompt, sem trava de código. Em teste manual
real (não mockado), a Mãe marcou `meeting_scheduled=true` já na 1ª mensagem do lead, que era
um pedido inicial ("gostaria de agendar... amanhã às 15h"), sem qualquer confirmação prévia.

Adicionalmente, o "recibo de reserva estruturado" (Fix P8, `decision_engine.py:2599-2621`,
que devolve ✅ Reservada / Experiência / Horário / Dia / Profissional ao lead) só existe na
filha de **apresentação** (`presentation_variant=scheduler`) — a filha de **agendamento**
(usada por `hybrid_scheduler`/`sdr_padrao` nas fases pré-agendamento→agendamento) não tem essa
mesma estrutura obrigatória, ficando a resposta (proposta vs. confirmação) ao critério livre
do modelo a cada turno.

**Risco prático:** o sistema pode criar/bloquear um appointment real (e desabilitar o bot)
baseado numa interpretação de intenção da Mãe, sem o lead ter de fato dito "sim, confirmado" —
isto já é o comportamento de produção hoje (`runners/whatsapp.py:756` usa a mesma função e
critério), não foi introduzido pelas duas implementações citadas acima, só ficou visível por
elas exercitarem mais esse caminho.

**O que precisaria ser construído (se o padrão se confirmar frequente):**
- Separar "proposta de horário" de "confirmação de horário" como dois sinais distintos (não
  um único booleano `meeting_scheduled` decidido isoladamente por turno)
- Possivelmente: só permitir a criação do appointment quando `effective_route_to` também
  indicar uma resposta de confirmação real (não quando a filha que respondeu foi a de
  recepção, por exemplo)
- Estender o "recibo de reserva obrigatório" (Fix P8) também à filha de agendamento, para
  paridade de comportamento entre apresentação e agendamento
- Exigir que a filha de agendamento sempre pergunte/aguarde confirmação explícita antes de a
  Mãe poder marcar `meeting_scheduled=true` no turno seguinte

**Decisão já tomada pelo utilizador:** não corrigir agora — manter como está e só revisitar
se este padrão se mostrar frequente em uso real (não é um problema teórico a perseguir
preventivamente).

**Evidência adicional (teste via browser, 20/06/2026):** reproduzido visualmente no Playground
— a filha de agendamento respondeu "Infelizmente, a sessão para amanhã às 12h já está ocupada...
Que tal às 10h ou 14h?" no mesmo turno em que o backend já tinha criado o appointment para as
12h e desativado o bot (`meeting_scheduled=true` da Mãe). Ou seja, o lead recebe uma mensagem
que parece negociar um novo horário, mas o sistema já considerou o agendamento original como
confirmado e encerrado. Reforça a M3 acima — não corrigido, só documentado.

---

## M4 — `next_action_hint` da Mãe pode receber valor fora do enum (ValidationError silencioso)

**Prioridade: BAIXA** (falha transitória, mitigada pelo retry de `llm_service.py`; sem padrão de frequência observado)

**Contexto:** identificado durante a mesma sessão de testes via browser (20/06/2026).

**Estado actual:** `MotherDecision.next_action_hint` (`orchestrator_models.py`) é um `Literal["reply",
"ask_qualification", "handoff", "ignore", "greet"]`. Em um teste real, a Mãe retornou
`next_action_hint="confirmar"` — valor fora do enum — causando `pydantic.ValidationError` na
validação do payload (`decide()`, stage `mother_validate`). O erro é capturado pelo `except
Exception` genérico de `decide()` e cai no fallback `llm_failure_first_message_suppressed`
(mensagem vazia, sem nenhum aviso visível ao operador no Playground além do trace com todos os
campos `null`). Uma nova tentativa (reenviar a mesma intenção) teve sucesso normalmente — o
modelo não repetiu o valor inválido.

**Risco prático:** baixo impacto unitário (o lead só não recebe resposta nesse turno específico
e precisa reenviar/aguardar retry), mas é uma classe de erro silenciosa — não há log de nível
`ERROR`/alerta, só um `WARNING` (`event=llm_orchestrator_error`) que só fica visível se houver
logger configurado (no Playground, só passa a existir após a mudança feita em
`playground_internal.py` durante a sessão de testes de `feat-playground-appointment-tag.md`).

**O que precisaria ser construído (se a frequência justificar):**
- Tornar `next_action_hint` mais tolerante (ex.: normalizar sinônimos como "confirmar" →
  "reply" antes da validação Pydantic) em vez de falhar a decisão inteira por um campo
  opcional/informativo
- Ou: capturar especificamente `pydantic.ValidationError` em `decide()` e tentar uma 2ª chamada
  à Mãe automaticamente (padrão já usado em `qualification` com `validation_errors`), em vez de
  cair direto no fallback genérico de falha de LLM

**Decisão:** não corrigir agora — registar para o caso de se tornar um padrão recorrente.
