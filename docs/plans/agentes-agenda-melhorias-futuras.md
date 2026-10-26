# Agentes de Agenda — Melhorias Futuras (multi-profissional e closing seletivo)

> Contexto: identificado na sessão de testes manuais locais de 19/06/2026 das
> implementações `disponibilidade-real-agendamento-ia.md` e
> `desativar-closing-hibrido-agendador.md`. Ambos os itens abaixo foram
> deliberadamente deixados fora do escopo dessas implementações por decisão
> explícita do utilizador — registados aqui para retomar quando fizer sentido.

---

## M1 — Suporte a múltiplos profissionais/agendas por conta

**Prioridade: MÉDIA** (pedido confirmado pelo utilizador em 03/10/2026, ver
[`feat-workflows-por-gatilho.md`](../implementations/feat-workflows-por-gatilho.md) — entra depois
da fase 1 dos workflows por gatilho e das tags; vale para todos os planos)

**Estado actual:** o sistema assume **um único profissional/agenda por conta**, para todos os planos (Start e Growth). Isto está hardcoded implicitamente em dois mecanismos:

1. `calendar_busy_slots` (`backend-crm/services/ai_orchestrator/orchestrator.py`, `_load_calendar_busy_slots()`) — carrega todos os appointments do `user_id`, sem distinguir profissional.
2. `_check_conflict` (`backend-crm/routes/appointments.py` e `routes/leads.py`, duas implementações paralelas) — bloqueia conflito por `user_id` inteiro, não por profissional individual.

**O que precisaria mudar:** introduzir uma dimensão `professional_id` (ou equivalente) em:
- Tabela `appointments` (nova coluna, FK para uma futura tabela de profissionais)
- `calendar_busy_slots` — filtrar por profissional, não só por conta
- `_check_conflict` (ambas implementações) — mesmo ajuste
- AI Profile — cada agente precisaria de saber a qual profissional está associado
- UI da Agenda — selector de profissional, ou vista combinada com indicação visual de qual profissional cada evento pertence

- Cadastro de profissionais (nome, especialidades, janela de disponibilidade de cada um) — hoje não existe: só há a "Bio do Profissional" (texto único) e várias "Tabelas de Serviços e Preços" com título por profissional; a disponibilidade é uma só por conta
- A IA precisa de saber qual profissional o cliente escolheu (ou atribuir um livre) antes de confirmar o horário

**Decisão do utilizador (03/10/2026):** a plataforma é multinicho e tem de comportar
negócios com um ou vários profissionais. Quando a conta declara que trabalha com mais
de um profissional, cada um tem **agenda separada** (a IA só oferece um profissional
quando ele está livre); com um só profissional, o comportamento atual mantém-se. O
profissional da sessão fica disponível nas mensagens como variável do contato (ver
implementação acima).

**Disponível em todos os planos** (decisão do utilizador, 03/10/2026) — substitui a
decisão de 19/06/2026 que reservava vários profissionais para Scale/Enterprise.

**Dependência:** `docs/implementations/fix-disponibilidade-campo-duplo-sentido.md` —
o campo de disponibilidade do profissional está hoje misturado com a janela de
resposta do agente; separar primeiro.

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

## M4 — `next_action_hint` da Mãe pode receber valor fora do enum (ValidationError)

**Prioridade: ALTA** (era BAIXA; frequência medida em 25/10/2026 — ver "Medição" abaixo)

**Medição (25/10/2026, configuração do agente Sensi Vitae no Playground local, ~90 turnos):**
com OpenAI, 4 falhas de validação (~4% dos turnos) — 3× a Mãe devolveu `route_to="apresentacao"`
(fase em português, fora do `Literal`) e 1× a Filha omitiu `confidence` em `ChildResult`
(`stage=child_validate`, "Field required"). Com `llm_provider=openrouter` +
`meta-llama/llama-3.3-70b-instruct` a Mãe devolveu `"apresentação"` logo na 1ª mensagem em
2 de 2 tentativas — o lead recebia "Vou te conectar com alguém do time" e, com
`handoff_policy=disable_bot`, o bot ficava desligado para ele. O padrão é sempre o mesmo: um
campo com valor quase-certo (sinónimo, acento, campo opcional em falta) derruba a decisão
inteira. Relacionado: [`motor-llm-otimizacoes.md`](motor-llm-otimizacoes.md) M2 (Structured
Outputs) resolveria a causa no caminho OpenAI; normalizar sinónimos/defaults antes da validação
resolve nos dois provedores.

**Contexto:** identificado durante a mesma sessão de testes via browser (20/06/2026).

**Estado actual:** `MotherDecision.next_action_hint` (`orchestrator_models.py`) é um `Literal["reply",
"ask_qualification", "handoff", "ignore", "greet"]`. Em um teste real, a Mãe retornou
`next_action_hint="confirmar"` — valor fora do enum — causando `pydantic.ValidationError` na
validação do payload (`decide()`, stage `mother_validate`). O erro é capturado pelo `except
Exception` genérico de `decide()`. Uma nova tentativa (reenviar a mesma intenção) teve sucesso
normalmente — o modelo não repetiu o valor inválido.

**Risco de silêncio total já corrigido:** este era um dos dois gatilhos conhecidos do fallback
`llm_failure_first_message_suppressed` (mensagem vazia, sem handoff, sem aviso ao operador,
quando a falha acontecia nos primeiros turnos da conversa) — resolvido em
`docs/implementations/fix-handoff-silencio-primeira-mensagem.md`. Hoje, quando esse
`ValidationError` acontece, o lead recebe a mensagem de handoff normal e o time é
notificado/o bot é pausado conforme a política configurada, em vez de silêncio.

**O que ainda seria uma melhoria futura (se a frequência justificar):**
- Tornar `next_action_hint` mais tolerante (ex.: normalizar sinônimos como "confirmar" →
  "reply" antes da validação Pydantic) em vez de falhar a decisão inteira por um campo
  opcional/informativo
- Ou: capturar especificamente `pydantic.ValidationError` em `decide()` e tentar uma 2ª chamada
  à Mãe automaticamente (padrão já usado em `qualification` com `validation_errors`), em vez de
  cair no fallback genérico de falha de LLM (que agora já é seguro, mas ainda desperdiça o turno)

**Decisão:** não corrigir agora — o risco grave (silêncio) já foi eliminado; a tolerância de
enum em si só vale a pena se o padrão se tornar recorrente.

---

## M5 — App não tem error boundary (risco estrutural, não específico da Agenda)

**Prioridade: MÉDIA** (sem incidente activo, mas qualquer excepção futura não tratada num
render continua a derrubar a árvore React inteira, sem fallback amigável)

**Contexto:** observado durante a graduação de `fix-crash-criar-compromisso-agenda.md`
(04/08/2026) — o crash corrigido nessa implementação (tela branca ao criar compromisso)
só foi visível de forma tão disruptiva porque o `frontend-crm` não tem nenhum React error
boundary a nível de app.

**Estado actual:** qualquer excepção não capturada durante o render desmonta a árvore React
inteira — o utilizador perde a tela sem nenhuma mensagem de erro, só recarregando a página
consegue voltar a usar a aplicação. Isto não é específico da Agenda — é um risco estrutural
de todo o `frontend-crm`.

**O que precisaria existir:** um error boundary a nível de app (ou por secção principal —
Agenda, Kanban, etc.) com um fallback amigável ("algo correu mal, recarregar") em vez de
tela branca.

---

## M6 — Guards defensivos redundantes após o fix de `setLeadNextAction`

**Prioridade: BAIXA** (cosmético, sem risco — os guards são inofensivos)

**Contexto:** observado durante a graduação de `fix-set-lead-next-action-ausente.md`
(04/08/2026).

**Estado actual:** `LeadCardDialog.tsx`, `ScheduleAppointmentDialog.tsx` e
`ProspectionCardDialog.tsx` protegem a chamada a `setLeadNextAction` com o fallback
`(leadsCtx as any)?.setLeadNextAction ?? (() => {})`. Esse fallback deixou de ser
necessário depois de `setLeadNextAction` passar a existir sempre em `LeadsContext.tsx`
— mas não foi removido por não ser necessário para a correcção do bug original.

**O que precisaria existir:** remover o fallback `?? (() => {})` nos 3 arquivos, chamando
`setLeadNextAction` directamente a partir de `useLeads()`.

---

## M7 — Anomalia de trace em pergunta de agendamento (mother_route inconsistente)

**Prioridade: BAIXA** (observada uma única vez, sem padrão confirmado)

**Contexto:** observado durante a validação de `fix-confirm-exact-agenda-vazia.md`
(03/08/2026).

**Estado actual:** o trace de uma sessão de teste mostrou `mother_route=qualification` com
`effective=apresentation` para uma pergunta de agendamento no segundo turno — inconsistência
entre a rota decidida pela Mãe e a rota efectivamente usada. Não foi investigada por estar
fora do escopo pedido na altura.

**O que precisaria existir:** reproduzir o caso e investigar `compose_decision_output()`
(`decision_engine.py`) para entender por que `effective_route_to` divergiu de
`mother_route` nesse turno específico.

---

## M8 — Badge de "próxima ação" no Kanban/Prospecção sem conversão de fuso

**Prioridade: BAIXA** (edge case de exibição, não investigado)

**Contexto:** observado durante a implementação de `fix-crash-criar-compromisso-agenda.md`
(04/08/2026), correlato ao trabalho de fuso horário de `feat-dual-fuso-agenda.md` (ver
`docs/architecture/agenda.md`, secção "Fuso Horário na Agenda").

**Estado actual:** `KanbanBoard.tsx`/`ProspectionCardDialog.tsx` constroem o badge de
"próxima acção" a partir de `new Date(result.startTime)`, sem passar pelos utilitários de
`useBusinessTimezone()`/`src/lib/timezone.ts` já usados no resto da Agenda — o badge pode
não mostrar a data/hora exacta dependendo de onde é exibido.

**O que precisaria existir:** aplicar `AppointmentTimeLabel`/`toBusinessTimezoneDate` ao
badge, consistente com o resto da Agenda.

---

## M9 — Toggle "Objetivo do Agendamento" afeta o Agente 01 além do Agente 03 (doc incompleta)

**Prioridade: BAIXA** (observação para manter atenção — sem reclamação de usuário reportada;
não investigar nem aplicar até haver sinal real de impacto)

**Contexto:** identificado em conversa durante a graduação de
`fix-presentation-variant-agente-direto.md` (21/08/2026), ao discutir se `presentation_variant`
deveria ser 100% implícito nos 3 presets de agente em vez de exposto como configuração separada.

**Estado atual:** o toggle "Objetivo do Agendamento" (`appointment_mode`, Camada 5 ·
Apresentação) tem dois efeitos distintos em `decision_engine.py`, mas só um está documentado
em `docs/architecture/agents.md`:
1. Bloco de aquecimento/MODO COMERCIAL (`decision_engine.py:2651-2654`) — de fato restrito a
   `template_key="hybrid_scheduler"` (Agente 03), como a doc descreve.
2. Instrução geral sales/scheduler que define o tom da fase de Apresentação
   (`decision_engine.py:3022-3024`) — **sem essa restrição**, roda para qualquer agente que
   passe pela Apresentação, incluindo o Agente 01 (`sdr_padrao`). Se "Compromisso Comercial"
   for marcado num Agente 01, o bot passa a tentar fechar oferta + enviar link de checkout
   durante a apresentação — fora do design pretendido do Agente 01 (qualificar a fundo e
   escalar para humano, não fechar sozinho).

**Decisão do usuário (21/08/2026):** não investigar nem corrigir agora — só manter registado.
Revisitar se surgir reclamação ou sinal real de impacto em produção.

---

## M10 — Handoff não é uma rota formal da Mãe (queixa de saúde/pedido de humano dependem de texto livre)

**Prioridade: MÉDIA** (guardrail crítico de segurança — nenhuma reclamação de produção ainda,
mas o roteiro de teste do agente demo reproduziu a falha em 100% das rodadas)

**Contexto:** identificado na rodada de testes do Playground do agente demo "Lara"
(`docs/marketing/comercial/agente-demo.md`, "🧪 ROTEIRO DE TESTE"), Cenários 5 (queixa de saúde)
e 6 (pedido de falar com humano), 02/07/2026. O registo completo das 30+ execuções foi removido
de `docs/implementations/sessao-teste-corrente.md` após a maior parte dos achados terem sido
corrigidos ou confirmados resolvidos por trabalho posterior — este item é o único que continuava
sem correção nem rastreamento em nenhum lugar.

**Estado actual:** o schema `MotherDecision.route_to` só aceita
`qualification|apresentation|pre-agendamento|agendamento|follow-up|closing` — nunca `handoff`.
A intenção de handoff só pode ser sinalizada por um campo separado (`next_action_hint="handoff"`),
e as regras estruturais de roteamento escritas no código (as "PRIORIDADE 0" a "PRIORIDADE 4" do
prompt da Mãe) nunca mencionam quando esse campo deveria virar `"handoff"` para queixa de saúde
ou pedido explícito de falar com humano — a decisão depende inteiramente de a Mãe "lembrar"
uma instrução em texto livre (`custom_instructions`) no meio de uma lista de prioridades
estruturadas que não fala nada sobre handoff.

**Evidência do teste (Cenário 5 — queixa de saúde, "Sinto uma dor muito forte nas costas"):**
em 30/30 execuções (5 rodadas isoladas + 4 execuções em conversa contínua realista) o guardrail
"nunca dar conselho médico" se manteve — mas o handoff explícito nunca disparou de forma
deliberada. Em algumas execuções o bot chegou a sugerir implicitamente que o serviço trataria
a dor ("já ajudei várias pessoas... resultados têm sido positivos"), o que é uma forma sutil de
conselho de saúde/tratamento — pior do que apenas não fazer handoff.

**Mitigação já aplicada (não é solução estrutural):** reforço de texto no topo de
`custom_instructions` de uma conta de teste específica (`autodigital157@gmail.com`, AI Profile
"Lara"), instruindo a IA a tratar queixa de saúde ou pedido de humano como handoff imediato,
sem continuar a conversa. Isso é por perfil individual — não corrige o gap estrutural para
nenhuma outra conta.

**O que precisaria ser construído:**
- Adicionar uma prioridade explícita e determinística no prompt da Mãe — algo como
  "PRIORIDADE -1 (vence todas as outras): queixa de saúde específica OU pedido explícito de
  falar com humano → `next_action_hint=handoff`" — em vez de depender só da IA inferir isso de
  texto livre em `custom_instructions`
- Avaliar se faz sentido tornar `"handoff"` um valor aceito também em `route_to` (não só em
  `next_action_hint`), para reduzir ambiguidade entre os dois campos

**Decisão:** não corrigir agora — aguardando decisão do utilizador sobre prioridade. Revisitar
antes de qualquer venda real do agente demo "Lara" (`agente-demo.md`), já que o próprio doc de
marketing assume que os guardrails de saúde/handoff cobrem o maior risco de reputação do nicho.

---

## M11 — Ler mais formatos de hora no turno da confirmação

**Prioridade: MÉDIA**

**Contexto:** deixado de fora de `fix-confirmacao-grava-proposta-antiga.md` (graduado em
26/10/2026). Ver `docs/architecture/agenda.md`, "Turno da confirmação".

**Estado actual:** `meeting_proposal.py` lê as horas com o `_TIME_RE` de `requested_slot.py`
("11h", "14h30", "15:00"). Horas por extenso ("ao meio-dia", "às onze", "às três da tarde") não
são lidas: nesse caso não há proposta lida e a conferência do candidato não actua (o
comportamento fica como antes da correção — decide a Filha).

**O que precisaria existir:** reconhecer as formas por extenso mais comuns em PT-PT/PT-BR na
leitura de horas partilhada (`requested_slot` + `meeting_proposal`), com testes de não-regressão
para durações ("uma hora") e intervalos ("das onze às cinco").

---

## M12 — Perguntas da conferência da marcação no tom da conta

**Prioridade: MÉDIA**

**Contexto:** deixado de fora de `fix-confirmacao-grava-proposta-antiga.md` (graduado em
26/10/2026).

**Estado actual:** quando `_apply_meeting_confirmation_guard` bloqueia a gravação, a resposta ao
cliente é um texto fixo do código (`meeting_proposal.ask_which_text` / `ask_duration_text`):
"Só para confirmar: prefere X ou Y?" e "Para fechar a marcação de X: que serviço e que duração
prefere (20, 30, 45, 60 ou 90 min)?". Sem o tom de voz da conta, com o profissional sem artigo
("com Val") e, em tabelas grandes, uma lista de durações longa. Só aparece quando a Filha ignora
o bloco e confirma na mesma (1 vez em 6 corridas na bancada).

**O que precisaria existir:** gerar a pergunta no tom da conta (ex.: chamada curta à IA como a de
`meeting_scheduler._generate_conflict_message`, com o texto fixo como fallback) e agrupar as
durações por serviço quando a tabela tiver muitas.

---

## M13 — Dados obrigatórios antes de gravar configuráveis no AI profile

**Prioridade: MÉDIA**

**Contexto:** deixado de fora de `fix-confirmacao-grava-proposta-antiga.md` (graduado em
26/10/2026).

**Estado actual:** com `meeting_scheduled=true`, o código só exige a duração (quando a tabela de
serviços tem várias e ninguém a disse — `meeting_proposal.missing_duration`). O resto do que a
conta quer saber antes de marcar (nome do cliente, tipo de serviço, profissional) só existe em
texto livre nas instruções personalizadas, e o bloco "MARCAÇÃO JÁ GRAVADA" vence essas
instruções.

**O que precisaria existir:** campo no AI profile com os dados exigidos antes de gravar (lista
fixa: nome, serviço, duração, profissional); o bloco e a conferência passam a pedir o que faltar.
Mexe na estrutura da BD (backend-core), nos ecrãs do agente e em
`docs/architecture/admin-agents-contract.md` — sobe ao utilizador.

---

## M14 — "Pode ser" com duas opções em aberto grava a que a IA escolher

**Prioridade: ALTA**

**Contexto:** visto na bancada Sensi Vitae durante `fix-remarcacao-grava-contraproposta.md`
(graduado em 26/10/2026), cenário `p-aceita-2a`. A Lara ofereceu "quinta às 16h ou sexta às 11h", o
cliente respondeu "Pode ser sim, marca aí!", e ficou gravada quinta às 16h. A Lara ainda perguntou
"Posso confirmar?".

**Estado actual:** `meeting_proposal.reconcile_confirmation`, com a aceitação `ambiguous`, deixa
passar o candidato da Filha quando ele é uma das opções (`action: ok`). Só bloqueia e pergunta "qual
prefere?" quando o candidato não é nenhuma delas. O cliente pode aparecer à hora errada.

**O que construir:** com aceitação `ambiguous`, não gravar nunca e perguntar qual opção, mesmo que o
candidato seja uma delas (o bloco "O LEAD CONFIRMOU, MAS HÁ MAIS DE UMA OPÇÃO EM ABERTO" já pede
isto à Filha). Confirmar antes que as opções lidas são mesmo alternativas, e não, por exemplo, a
sessão antiga repetida no texto.

---

## M15 — Conflito no último segundo numa marcação nova manda duas mensagens

**Prioridade: MÉDIA**

**Contexto:** deixado de fora de `fix-remarcacao-grava-contraproposta.md` (graduado em 26/10/2026),
que resolveu o mesmo problema na remarcação.

**Estado actual:** quando o CRM recusa a criação com 409 (horário ocupado entre a leitura da agenda e
a gravação), `meeting_scheduler.handle_meeting_scheduled` devolve a mensagem de conflito e o runner
(e o Playground) envia-a **além** da resposta da Filha, que já dava a marcação como feita. O cliente
recebe "Experiência Agendada" e logo a seguir "o horário ficou indisponível".

**O que construir:** como em `handle_meeting_cancel_or_reschedule`, substituir `decision.message_text`
pela mensagem de conflito e devolver `None` — ver `docs/architecture/agenda.md`, "Conflito de horário
no reagendamento".

---

## M16 — Hora local também nos turnos que não cumprimentam

**Prioridade: BAIXA**

**Contexto:** deixado de fora de `fix-saudacao-hora-local.md` (graduado em 26/10/2026) por minimalismo.

**Estado actual:** a linha "AGORA (hora local do negócio)" (`_local_time_fact_line` em `decision_engine.py`)
só entra na receção e nos prompts que mandam cumprimentar. Nos outros turnos a Filha só tem a tabela de dias
(sem horas), por isso não sabe se "ainda hoje" ou "amanhã de manhã" fazem sentido à hora a que responde.

**O que construir:** injetar a mesma linha (sem a instrução de cumprimento) nos prompts de apresentação,
pré-agendamento, agendamento e gestão pós-marcação; medir antes e depois na bancada (ex.: "ainda hoje" às 19h55).

---

## M17 — Abertura do dono com o período escrito à mão

**Prioridade: BAIXA**

**Contexto:** deixado de fora de `fix-saudacao-hora-local.md` (graduado em 26/10/2026).

**Estado actual:** a abertura (`origin_inbound_opener`) é texto livre. Se o dono escrever literalmente
"Boa tarde!", a IA pode copiá-lo mesmo de manhã, apesar da linha AGORA que lhe diz o período certo.

**O que construir:** opções a avaliar — variável `{{saudacao}}` na abertura, substituída pelo cumprimento
calculado; ou um aviso no ecrã do AI Profile quando a abertura contém um período fixo.

---

## M18 — IA vê os ocupados de outros já alargados pela margem

**Prioridade: BAIXA**

**Contexto:** deixado de fora de `feat-margem-entre-sessoes.md` (graduado em 26/10/2026) — trade-off consciente.

**Estado actual:** com `session_buffer_minutes > 0`, `_apply_session_buffer` (`orchestrator.py`) alarga os
ocupados de outros leads e do Google antes de chegarem ao executor, por isso o bloco "HORÁRIOS JÁ OCUPADOS" e o
facto do horário pedido mostram, por exemplo, "15:00 até 16:15" para uma sessão das 15h às 16h. Nos testes de
26/10 a IA não citou esses horários ao cliente.

**Gatilho:** só vale a pena se a IA começar a dizer ao cliente horários "estranhos" (ex.: "está ocupado até às 16h15").

**O que construir:** mandar o horário real e a margem em campos separados no slot (ex.: `start_at`/`end_at`
reais + `buffer_minutes`) e aplicar a margem dentro de `_has_conflict`, mostrando à IA o horário real.

---

## M19 — Textos da IA na agenda vistos nos testes da margem

**Prioridade: BAIXA**

**Contexto:** observado nos testes de `feat-margem-entre-sessoes.md` (bancada local e Playground de produção,
26/10/2026) — não causado pela margem (repete-se com margem 0).

**O que foi visto:**
1. Na remarcação recusada, a IA escreveu "a sua sessão de terça-feira às 14h mantém-se até me dizer" quando a
   sessão gravada era às 13h30 — usa o horário pedido em vez do gravado (parente de
   `cancelamento-reagendamento-melhorias-futuras.md` M5).
2. Quando o horário pedido só colide por causa da margem, a IA diz "já está ocupado" — não é falso para o
   cliente, mas o motivo real é o intervalo de preparação.
3. Em 1 de 5 corridas do `pos-marcacao`, a IA respondeu a "Afinal preciso de remarcar para quinta às 15h" como
   marcação nova ("Como se chama?") e devolveu `meeting_reschedule_requested=false` — nada foi remarcado.

**O que construir:** medir cada um na bancada (`.claude/agentes/sensi-vitae/`, 5x por cenário) antes de decidir;
para (1), passar à Filha de gestão pós-marcação o horário gravado como facto; para (3), avaliar um guardrail
que reconheça "remarcar/mudar para <dia> às <hora>" quando há marcação futura.
