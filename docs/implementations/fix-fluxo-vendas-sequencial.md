# Fix: Fluxo de Venda — gating sequencial de gatilhos + orientações críticas persistentes

**Branch:** `fix-fluxo-vendas-sequencial`
**Status:** Todos os cenários validados (21/08/2026)

---

## Motivação

O agente "Daniel" (Sensi Vitae, `agent_mode: agenda`) tem, na fase p2 (Apresentação) do Fluxo de Venda, uma sequência desenhada assim: apresentar-se → pedir permissão para enviar a tabela de preços → **[crítico] não perguntar disponibilidade antes de o lead aceitar ver a tabela** → (gatilho: lead aceita tabela) → enviar imagens da tabela → perguntar qual serviço interessou → (gatilho: lead indica serviço) → perguntar disponibilidade.

No WhatsApp real, o bot perguntou "que dia e horário você gostaria de agendar" **antes** de o lead sequer ter aceitado ver a tabela — violando a instrução crítica configurada. O utilizador notou, ao olhar o builder visual (que já agrupa os blocos por gatilho com indentação), que o sistema deveria impedir estruturalmente que uma ação "mais à frente" na sequência dispare antes de o gatilho anterior já ter disparado — hoje isso não é garantido pelo motor.

Causa raiz identificada: `_evaluate_sales_flow_phases()` avalia os blocos com uma única flag rolante (`last_trigger_active`) que só reflete se o **último** gatilho visto disparou **neste turno** — sem verificar se gatilhos **anteriores** na sequência já foram satisfeitos antes. Orientações `priority: critical` também só permanecem ativas enquanto essa flag estiver `True` na posição em que aparecem, o que na prática as faz desaparecer do prompt depois do turno de entrada da fase.

---

## Problemas Identificados (estado anterior)

1. **Sem trava sequencial entre gatilhos (`decision_engine.py:405-460`):** um `intent_trigger` mais à frente na fase pode disparar no mesmo turno (ou antes) que um `intent_trigger` anterior, dependendo apenas de `detected_intents` (classificação livre da LLM Mãe naquele turno) — não há verificação de que o gatilho anterior já foi satisfeito.

2. **Orientações críticas não persistem entre turnos (`decision_engine.py:460, 486-494`):** uma `orientacao` com `priority: critical` só é reinjectada no prompt quando `last_trigger_active` está `True` na sua posição — isso depende do `phase_trigger` (que dispara uma única vez por lead) ou de gatilhos anteriores terem acabado de disparar neste turno específico. Nos turnos seguintes da mesma fase, a instrução crítica some do prompt.

3. **`is_phase_entry` com default inconsistente entre chamadas (`decision_engine.py:2180, 2506, 3110, 3443` vs `4639-4642`):** as chamadas que constroem o prompt filho não passam `is_phase_entry`, usando o default `True` sempre — tratando todo turno como "entrada na fase" para fins de prompt, enquanto a chamada real de despacho de `system_actions` (linha 4639) usa o valor correto. Isso faz o prompt reapresentar conteúdo de entrada ("ATENÇÃO: mensagens enviadas automaticamente...") como se fosse novo em todo turno.

4. **Instrução de "reconhecimento de interesse de agendamento" hardcoded e não editável (`decision_engine.py:3050-3054`):** dentro de `_build_child_prompt_apresentation`, aplicada incondicionalmente a qualquer `agent_mode`, compete com a instrução crítica do utilizador e não pode ser editada/removida pelo builder.

5. **Sem visibilidade do progresso do Fluxo de Venda no Kanban:** `leads.phases_triggered` e `leads.triggers_fired` já são persistidos no backend-crm mas nunca chegam ao frontend.

---

## Abordagem

```
_evaluate_sales_flow_phases() por fase, por turno:
  para cada gatilho (kw_trigger/intent_trigger com fire_once=True, ou phase_trigger):
    ├─ algum gatilho ANTERIOR na fase (mesmo critério) ainda não satisfeito (persistido)?
    │     → bloqueado: fired=False, independente de detected_intents/keywords deste turno
    └─ senão → avaliação normal (como hoje)

  orientação com priority=critical:
    ├─ disparou neste turno (via last_trigger_active) → injecta (como hoje)
    └─ NÃO disparou, mas o gatilho seguinte na sequência ainda não está satisfeito (persistido)
          → injecta mesmo assim, como guarda permanente ("standing guard")
```

Pesquisa aplicada ao diagnóstico:
- **Anthropic (context engineering para agentes):** guardrails multi-turn confiáveis devem ser **estado explícito, recomputado a cada turno** — não texto injetado uma vez esperando que "persista" na memória do modelo. Base para o fix #2 (standing guard).
- **ManyChat** (inspiração citada pelo utilizador): o fluxo fica **parado num passo** (wait for reply / bloco condicional) até a condição sobre a resposta real do lead ser cumprida, só então avança. Base para o fix #1 (gating sequencial).

---

## Plano de Implementação

### Fase 1 — Backend: gating sequencial + orientações críticas persistentes

**Objetivo:** corrigir o bug relatado — impedir que gatilhos mais à frente disparem antes dos anteriores, e manter instruções críticas ativas até a condição que guardam ser satisfeita.

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/decision_engine.py` | `_evaluate_sales_flow_phases()`: nova checagem de pré-requisitos sequenciais antes de avaliar `kw_trigger`/`intent_trigger`/`phase_trigger`; segunda passagem para orientações `critical` não cobertas pelo disparo do turno |
| `backend-executors/tests/test_sales_flow_intent_trigger_phase_entry.py` | Novos testes: gatilho posterior bloqueado sem o anterior satisfeito; orientação crítica persiste em turnos seguintes até o próximo gatilho disparar |

Escopo deliberado: só gatilhos `fire_once=True` (e `phase_trigger`, inerentemente único) participam do encadeamento sequencial — um `kw_trigger` sem `fire_once` não tem registo persistido de "já disparou" e mantém o comportamento atual.

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `28a5f1b` | Gating sequencial de gatilhos + orientações críticas como guarda permanente |

**Detalhes do commit `28a5f1b`:**
- `backend-executors/app/services/decision_engine.py` — `_evaluate_sales_flow_phases()`: carrega `phases_triggered` do lead (além do já existente `triggers_fired`); novo helper `_trigger_persisted_satisfied()`; nova variável `_prereqs_satisfied` que bloqueia (`fired=False`) qualquer gatilho sequencial (`phase_trigger` ou `kw_trigger`/`intent_trigger` com `fire_once=True`) enquanto o gatilho sequencial anterior da fase não estiver satisfeito; segunda passagem no fim da função reinjecta orientações `priority: critical` como guarda permanente enquanto o próximo gatilho sequencial não disparar
- `backend-executors/tests/test_sales_flow_intent_trigger_phase_entry.py` — `test_later_intent_trigger_blocked_until_earlier_one_fires` e `test_critical_orientation_persists_until_next_trigger_fires`, reproduzindo o cenário exato do agente "Daniel" (Sensi Vitae)
- `docs/architecture/sales-flow.md` — seção "Modelo sequencial de trigger" reescrita com os dois novos mecanismos

### Relatório da Fase 1 — o que mudou na prática

**Antes:** um gatilho mais à frente na sequência do Fluxo de Venda (ex.: "cliente indicou o serviço") podia disparar antes de um gatilho anterior (ex.: "cliente aceitou ver a tabela") — bastava a IA Mãe classificar a intenção naquele turno. E uma instrução marcada como "crítica" (ex.: "não pergunte disponibilidade ainda") só valia no turno em que apareceu pela primeira vez — nos turnos seguintes da mesma fase, o bot deixava de "lembrar" dela.

**Agora:** um gatilho só pode disparar depois de todos os gatilhos anteriores da mesma fase (com "disparar uma vez" ativado) já terem disparado — não há mais como "pular etapas". E uma instrução crítica permanece ativa em todo turno da fase até a condição que ela guarda ser realmente cumprida, não só no primeiro turno.

**Para validar:** Cenários P1 e P2 (pytest, já confirmados abaixo) e Cenário C1 (WhatsApp real).

> **Nota de numeração:** o teste ao vivo da Fase 1 revelou um problema mais urgente (Mãe pulando a fase inteira num salto de rota), documentado como **Fase 2** na secção "Fase 2 — Diagnóstico + Correção" abaixo — já implementada e commitada antes das fases seguintes deste plano original. As fases abaixo foram renumeradas de Fase 2/3/4 para **Fase 3/4/5** para não colidir.

### Fase 3 — Backend: `is_phase_entry` correto nas chamadas de construção de prompt

**Objetivo:** eliminar a inconsistência entre o que o prompt afirma (default `True`) e o que realmente foi despachado (`is_phase_entry` calculado corretamente).

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/decision_engine.py` | Threading do `is_phase_entry` real para as 4 chamadas de `_build_child_prompt_*` |

### Fase 4 — Backend + Frontend: migrar regra de agendamento hardcoded para bloco editável

**Objetivo:** dar ao utilizador controlo total sobre a instrução de "reconhecimento de interesse de agendamento" — editável/removível, com padrão pré-preenchido.

Escopo: só agentes com recursos de agendamento (`agent_1`/SDR e `agent_3`/Híbrido — grupo normalizado `agenda`). Para `direto`/`consultivo` (`agent_2`/Closer e Consultivo), sem mudança nesta iteração.

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/decision_engine.py` | `_build_child_prompt_apresentation`: para `agent_mode_normalized == 'agenda'`, usar bloco `booking_signal_opener` da fase p2 se configurado; fallback hardcoded só se p2 nunca foi configurada |
| `frontend-crm/src/components/agente/CamadaFluxoVenda.tsx` | Novo card `booking_signal_opener` na fase p2 (padrão `qual_opener`), visível só quando `agentGroup === 'agenda'` |
| `frontend-crm/src/types/agente.ts` | Novo flag `booking_signal_opener?: boolean` em `SalesFlowBlock` |

### Commits Fase 4

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `f9900ed` | Bloco `booking_signal_opener` editável/removível (backend + frontend) |

**Detalhes:**
- `backend-executors/app/services/decision_engine.py` — `_build_child_prompt_apresentation`: nova variável `_booking_signal_block` computada antes do prompt; para `agent_mode_normalized == 'agenda'` com `sales_flow.enabled` e fase p2 com blocos configurados, usa o bloco `booking_signal_opener` (se presente) ou string vazia (se ausente — utilizador removeu deliberadamente); mantém o texto hardcoded original em todos os outros casos (sem sales_flow, p2 vazia, ou `direto`/`consultivo`)
- `frontend-crm/src/components/agente/CamadaFluxoVenda.tsx` — generalizados `QualOpenerBanner`/`QualOpenerCard` (hardcoded para p1) em `OpenerBanner`/`OpenerCard` (parametrizados por título/descrição/label/badge/cor), reutilizados tanto pelo `qual_opener` (p1) existente quanto pelo novo `booking_signal_opener` (p2, só quando `agentGroup === 'agenda'`); novas funções `addBookingSignalOpener`/`removeBookingSignalOpener`/`editBookingSignalOpener`; banner distingue "sem configuração" (p2 vazia, ainda usa fallback) de "desativado" (p2 customizada, sem o bloco)
- `frontend-crm/src/types/agente.ts` — novo campo `booking_signal_opener?: boolean` em `SalesFlowBlock`
- `backend-executors/tests/test_sales_flow_intent_trigger_phase_entry.py` — 5 novos testes cobrindo fallback (sem sales_flow / p2 vazia), supressão (p2 configurada sem o bloco), uso do texto customizado, e não-migração para `direto`

### Relatório da Fase 4 — o que mudou na prática

**Antes:** a instrução "se o lead já escolheu um serviço ou perguntou sobre horários, reconheça o interesse e pergunte o dia/horário" estava fixa no código — nenhum agente conseguia editá-la ou desativá-la, mesmo configurando o Fluxo de Venda com a sua própria sequência.

**Agora:** assim que uma conta com agente de agendamento (SDR ou Híbrido) configura a fase de Apresentação no Fluxo de Venda, essa instrução para de ser aplicada automaticamente — o utilizador precisa adicioná-la explicitamente (com um botão "+ Adicionar instrução"), podendo editar o texto ou removê-la de vez. Testado ao vivo: com o perfil "Daniel", depois de configurar a fase p2, a frase genérica "podemos agendar sua sessão" que aparecia em quase toda resposta desapareceu; ao adicionar o bloco com um texto customizado ("ofereça agendar direto sem enrolar") e o lead perguntar sobre horários, o bot respondeu exatamente nesse tom, oferecendo dias disponíveis diretamente.

**Para validar:** Cenário P4 (abaixo, builder) + teste ao vivo via Playground (ver nota).

### Fase 5 — Frontend: funil visual resumido no card do Kanban

**Objetivo:** mostrar, de forma compacta, por onde o lead já passou no Fluxo de Venda.

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/types/crm.ts` | `phasesTriggered?: string[]` em `interface Lead` |
| `frontend-crm/src/contexts/LeadsContext.tsx` | `mapRawLead()` parseia `raw.phases_triggered` (JSON string) para `phasesTriggered: string[]` |
| `frontend-crm/src/types/agente.ts` | Nova constante `SALES_FLOW_PHASE_COLORS` (extraída de `CamadaFluxoVenda.tsx`, agora partilhada) |
| `frontend-crm/src/components/KanbanBoard.tsx` | Reaproveita o `useEffect` que já buscava `agent_mode` (para `profileAgentType`) para também derivar `phaseSequence` via `SALES_FLOW_PHASES_BY_AGENT_MODE`; passa a prop a `KanbanColumn` |
| `frontend-crm/src/components/KanbanColumn.tsx` | Repassa `phaseSequence` a cada `LeadCard` |
| `frontend-crm/src/components/LeadCard.tsx` | Novo componente `SalesFlowFunnel` — breadcrumb compacto (bolinhas coloridas por fase); concluída/atual via `phasesTriggered` + posição na sequência, futura apagada |

### Commits Fase 5

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `<preencher após commit>` | Funil visual no card do Kanban + fix de bug pré-existente (`api` não importado em `KanbanBoard.tsx`) |

**Detalhes:**
- `frontend-crm/src/components/KanbanBoard.tsx` — **bug pré-existente encontrado e corrigido**: o arquivo usava `api.core.getAiProfileMe()` em dois lugares (`profileAgentType`/`resolveAgentTypeForLead`) mas nunca importava `api` de `@/services/api` — `ReferenceError: api is not defined`, capturado silenciosamente pelo `try/catch` (sem log), fazendo o fallback de `agent_type` a nível de conta nunca funcionar. Descoberto ao debugar por que `phaseSequence` ficava sempre vazio. Corrigido com o import em falta — beneficia tanto o funil novo quanto o `profileAgentType`/`resolveAgentTypeForLead` já existentes.
- Mesmo arquivo — novo estado `phaseSequence`, populado no mesmo `useEffect` que já buscava o perfil (sem chamada de API extra), usando a mesma normalização de `agent_mode` já usada em `CamadaFluxoVenda.tsx` (`sdr_scheduler`→agenda, `closer`→direto)
- `frontend-crm/src/types/agente.ts` — `SALES_FLOW_PHASE_COLORS` extraída de `CamadaFluxoVenda.tsx` (`PHASE_COLORS` local vira alias) para ser partilhada com `LeadCard.tsx`
- `frontend-crm/src/components/LeadCard.tsx` — `SalesFlowFunnel`: mapeia `lead.category` → `phase_id` (espelha `_ROUTE_TO_PHASE_ID` do backend), marca fases concluídas via `phasesTriggered` (∈ conjunto) ou por posição anterior à fase atual na sequência; fase atual com bolinha maior + anel; futuras apagadas (opacity baixa)
- `frontend-crm/src/contexts/LeadsContext.tsx` — `mapRawLead()` ganha parsing de `phasesTriggered`, mesmo padrão do já existente `followupContract` (JSON string → array, tolerante a erro)

### Relatório da Fase 5 — o que mudou na prática

**Antes:** não havia nenhuma forma de ver, olhando o quadro Kanban, por onde um lead já tinha passado dentro do Fluxo de Venda — só a coluna (fase) atual.

**Agora:** cada card do Kanban mostra uma fileira compacta de bolinhas — uma por fase do funil configurado para o tipo de agente da conta — com a fase já concluída preenchida, a fase atual destacada (maior, com contorno), e as fases futuras apagadas. Passar o cursor sobre uma bolinha mostra o nome da fase.

**Para validar:** Cenário C2 (abaixo, browser MCP).

**Nota lateral:** ao investigar por que o funil não aparecia, encontrei e corrigi um bug pré-existente e não relacionado ao Fluxo de Venda — `KanbanBoard.tsx` chamava `api.core.getAiProfileMe()` sem nunca ter importado `api`, silenciosamente quebrando o fallback de `agent_type` a nível de conta (usado quando um lead individual não tem `agent_type` próprio).

### Commits Fase 3

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `9693e1f` | `is_phase_entry` real threaded para os 4 builders de prompt filho |

**Detalhes:**
- `backend-executors/app/services/decision_engine.py` — novo helper `_compute_is_phase_entry()` (reutiliza `_load_triggered_phases_set()` da Fase 2); `_ROUTE_TO_PHASE_ID` consolidado a nível de módulo (estava duplicado em `_evaluate_sales_flow_phases()` e `compose_decision_output()`); `_build_child_prompt_recepcao/qualification/apresentation/follow_up` ganham parâmetro `is_phase_entry: bool = True` (default preserva compatibilidade com chamadas existentes em testes); `decide()` calcula `_is_phase_entry_for_prompt` uma vez antes do dispatch de rota e passa explicitamente às 4 chamadas; `compose_decision_output()` passa a usar o mesmo helper em vez do cálculo inline duplicado
- `backend-executors/tests/test_sales_flow_intent_trigger_phase_entry.py` — `test_is_phase_entry_threaded_correctly_to_apresentation_prompt`

### Relatório da Fase 3 — o que mudou na prática

**Antes:** o prompt enviado à IA filha dizia sempre "ATENÇÃO: as mensagens abaixo foram enviadas automaticamente" e repetia o conteúdo de abertura da fase em todo turno — mesmo em turnos onde nada tinha sido enviado automaticamente naquele momento. Isso não causava o bug relatado diretamente (a Fase 2 resolve isso de forma mais explícita), mas confundia o histórico que a IA via.

**Agora:** essa mensagem só aparece no turno real de entrada na fase — nos turnos seguintes, o prompt reflete com precisão o que já aconteceu.

**Para validar:** Cenário P3 (pytest, já confirmado acima).

---

## Checks de Validação

### Cenário P1 — Gatilho posterior não salta na frente (pytest)
- [x] `detected_intents` inclui a label do 2º `intent_trigger` mas não a do 1º (que ainda não está em `triggers_fired`)
- [x] Confirmar: 2º gatilho não dispara (bloqueado), `system_actions`/`prompt_injections` do 2º grupo ausentes
- **Validado em:** 21/08/2026 — `test_later_intent_trigger_blocked_until_earlier_one_fires`; confirmado que falha sem o fix (`mark_trigger_fired` disparava e `ask-availability` era injectado) e passa com ele.

### Cenário P2 — Orientação crítica persiste entre turnos (pytest)
- [x] Turno 1: `phase_trigger` dispara, orientação crítica aparece em `prompt_injections`
- [x] Turno 2 (sem `is_phase_entry`, sem o gatilho seguinte satisfeito): orientação crítica continua em `prompt_injections`
- [x] Turno 3 (gatilho seguinte satisfeito/persistido): orientação crítica desaparece
- **Validado em:** 21/08/2026 — `test_critical_orientation_persists_until_next_trigger_fires`; confirmado que o turno 2 falha sem o fix (instrução sumia) e passa com ele.

### Cenário P3 — `is_phase_entry` correto no prompt (pytest)
- [x] Turno 2+ da mesma fase: prompt não repete "ATENÇÃO: mensagens enviadas automaticamente"
- **Validado em:** 21/08/2026 — `test_is_phase_entry_threaded_correctly_to_apresentation_prompt`: chamando `_build_child_prompt_apresentation` com `is_phase_entry=True` vs `False`, o texto só aparece no primeiro caso.

### Cenário P4 — Bloco `booking_signal_opener` editável (builder)
- [x] Fase p2, `agent_mode` do grupo `agenda`: card com texto padrão aparece
- [x] Editar texto → salva
- [x] Remover bloco → backend deixa de aplicar reconhecimento automático de agendamento
- **Validado em:** 21/08/2026 — via browser (chrome-devtools MCP) no perfil "Daniel" (fase p2 já customizada, 11 blocos, sem `booking_signal_opener`): banner mostrou corretamente "Reconhecimento de interesse de agendamento **desativado**" (distinção correta de "sem configuração"). Cliquei "+ Adicionar instrução" → card apareceu com texto padrão; editei para "Se o lead perguntar por horários, ofereça agendar direto sem enrolar." → salvei → `SALVAR FLUXO DE VENDA` → confirmado na base de dados local (`core.db`, `ai_profiles.id=5`) que o bloco persistiu com `booking_signal_opener: true` e o texto editado.
- **Teste ao vivo adicional (Playground):** nova sessão, "Quero saber sobre massagens" → resposta de apresentação **sem** menção a agendamento (confirma que o texto hardcoded parou de ser injectado). "Que horas vocês têm disponível essa semana?" → bot respondeu "temos horários disponíveis... terça e quinta-feira... Qual desses dias você prefere?" — exatamente no tom do texto customizado ("ofereça agendar direto sem enrolar").

### Cenário C1 — WhatsApp real: bot não pergunta disponibilidade antes da tabela ser aceita
- [x] Reproduzir a conversa do relato original (perguntar algo não relacionado após a saudação de entrada)
- [x] Confirmar: bot não pergunta dia/horário antes do lead aceitar a tabela
- **Validado em:** 21/08/2026 — via Playground (não WhatsApp real; ver nota de escopo abaixo), importando o export `ai-agent-Daniel-2026-08-21.json` (mesmo `sales_flow` do relato) para a conta de teste local (`_conta-teste-local.md`), com os 3 backends a correr localmente (core/crm/executors) já com o fix da Fase 1.
  - Turno 1 (saudação + "já abriste o teu espaço?"): apresentação inicial + pede permissão para tabela — sem pedir disponibilidade. ✅
  - Turno 2 (pergunta não relacionada, "não ias ter espaço em Olhão?"): bot responde à pergunta e volta a oferecer a tabela — **sem perguntar dia/horário** (o bug original). Continha a frase "Assim, podemos agendar sua sessão" — menção *não interrogativa* a agendamento, atribuída à instrução hardcoded ainda não migrada (Fase 4), não a uma regressão do gating.
  - Turno 3 ("Sim, pode enviar a tabela"): as 3 imagens da tabela só foram despachadas **agora** (não nos turnos 1-2) + bot pergunta qual serviço interessou — confirma que o `intent_trigger` "aceitar tabela" só disparou neste turno, como configurado.
  - Turno 4 ("Gostei da relaxante"): **só agora** o bot pergunta "Que dia funcionaria melhor pra você para agendar a massagem relaxante?" — a pergunta de disponibilidade (bloco final da sequência) só apareceu depois de todos os gatilhos anteriores terem disparado, na ordem correta.
  - **Nota de escopo:** o Cenário C1 original pedia "WhatsApp real"; o teste foi feito via Playground (mesmo motor de decisão, `decision_engine.py`, usado pelos dois caminhos — ver `docs/architecture/playground-parity.md`). Considerado equivalente para validar esta fase; reteste no WhatsApp real fica a critério do utilizador.

### Cenário C2 — Funil no Kanban (browser MCP)
- [x] Abrir Kanban com lead em fase intermediária do Fluxo de Venda
- [x] Confirmar: breadcrumb mostra fase atual + fases concluídas de forma compacta
- **Validado em:** 21/08/2026 — via chrome-devtools MCP, conta "Daniel" (agent_mode agenda). Lead "França" (`category: "qualification"`, `phases_triggered: null`): funil mostrou a bolinha da fase "Recepção" preenchida (concluída por posição — antes da atual) e "Qualificação" destacada como atual (maior, com contorno), fases seguintes (Apresentação → Fechamento) apagadas. Leads em "À Prospectar" (`category: "to-prospect"`, fora da sequência do Fluxo de Venda) mostraram todas as bolinhas apagadas, sem nenhuma marcada como atual — comportamento correto.

---

## Fase 2 — Diagnóstico + Correção: Mãe pula a fase inteira (21/08/2026)

### Problema identificado

A pedido do utilizador, testei novamente via Playground — desta vez respondendo apenas **"ok"** no lugar de "Sim, pode enviar a tabela", no ponto em que o bot oferece a tabela de preços.

Resultado: o bot respondeu diretamente **"Que dia funcionaria melhor pra você para agendar sua sessão de massagem?"** — sem nunca ter enviado a tabela nem perguntado qual serviço interessou. O trace do Playground confirmou: `mother_route: "pre-agendamento"`, `effective_route: "pre-agendamento"`.

Causa raiz: a **Mãe** (LLM de roteamento) decidiu sozinha, num único turno, `route_to: "pre-agendamento"` — interpretando o "ok" ambíguo como sinal suficiente para pular direto para a fase de agendamento. Como `_evaluate_sales_flow_phases()` só avalia os blocos da fase para onde a rota efetiva aponta **neste turno**, a fase p2 inteira — incluindo a instrução crítica e toda a sequência de gatilhos corrigida na Fase 1 — **nunca chegou a ser avaliada**. A Fase 1 só resolve o encadeamento **dentro** de uma fase; não impede a Mãe de **pular a fase inteira** num salto de rota.

O utilizador propôs a correção certa: assim como existe um guardrail (`_enforce_qualification_route_when_missing`) que impede avançar de "qualification" enquanto há campos obrigatórios pendentes, o mesmo padrão deveria existir para "apresentation" enquanto houver gatilhos sequenciais pendentes no Fluxo de Venda.

**Descoberta adicional durante a implementação:** a primeira versão do guardrail usava `lead.category == "apresentation"` como condição de ativação — e não disparou no reteste. Investigação direta na base de dados local (`crm.db`) mostrou que `leads.category` tinha ficado em `"qualification"`, mesmo com `phases_triggered` já contendo `"p2"` (ou seja, o `phase_trigger` da fase já tinha disparado). A Mãe gera conteúdo de "apresentation" via `route_to` num turno sem que a categoria persistida do lead necessariamente acompanhe (esse campo depende de `perceived_category` + `apply_mother_category_guardrails`, um mecanismo separado). `leads.phases_triggered` mostrou-se o sinal mais confiável de que a fase p2 foi de facto iniciada.

### Correção

| Arquivo | Mudança |
|---|---|
| `backend-executors/app/services/decision_engine.py` | Nova função `_enforce_apresentation_sales_flow_pending()` — espelha `_enforce_qualification_route_when_missing()`; força `mother_decision.route_to = "apresentation"` quando a fase p2 tem gatilhos sequenciais (`kw_trigger`/`intent_trigger` com `fire_once`) ainda não satisfeitos e a Mãe tenta saltar para um estágio seguinte (`_ALLOWED_ADVANCE["apresentation"]`). Chamada em `decide()` logo após `_enforce_scheduling_agent_no_closing`. Condição de ativação usa `"p2" in phases_triggered` OU `lead.category == "apresentation"` (não só a categoria, pelo motivo acima) |
| `backend-executors/app/services/decision_engine.py` | Pequeno refactor de apoio: extraídas `_load_triggers_fired_set()`, `_load_triggered_phases_set()` e `_is_sequential_trigger_block()` — reutilizadas por `_evaluate_sales_flow_phases()` (Fase 1) e pelo novo guardrail, eliminando parsing JSON duplicado |
| `backend-executors/tests/test_sales_flow_intent_trigger_phase_entry.py` | 6 novos testes: guardrail bloqueia salto para pre-agendamento/closing/follow-up com gatilho pendente; permite o salto quando todos os gatilhos já dispararam; ignora outras categorias; não interfere sem Fluxo de Venda configurado; usa `phases_triggered` quando `lead.category` está desatualizada |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `1769f30` | Guardrail de transição de fase + refactor de apoio + testes |

### Relatório da Fase 2 — o que mudou na prática

**Antes:** mesmo com a Fase 1 a funcionar corretamente, uma mensagem ambígua do lead (como "ok") podia levar a Mãe a decidir sozinha pular a fase de Apresentação inteira, indo direto para "vamos agendar" — sem nunca ter enviado a tabela de preços nem perguntado qual serviço interessava. Todo o cuidado da Fase 1 ficava sem efeito nesse caso, porque a fase nunca chegava a ser avaliada.

**Agora:** se a fase de Apresentação tem etapas configuradas no Fluxo de Venda que ainda não aconteceram para aquele lead (ex.: "cliente aceitou a tabela"), a Mãe é impedida de sair dessa fase — mesmo que ela própria "ache" que já é hora de agendar. Testei ao vivo repetindo a mesma conversa com "ok": agora o bot volta a confirmar o envio da tabela em vez de perguntar disponibilidade, e só avança de verdade depois de a tabela ser aceite e o serviço escolhido.

**Para validar:** Cenário C1 reexecutado ao vivo via Playground com "ok" (ver abaixo) — mais os novos testes pytest.

### Cenário C3 — "ok" ambíguo não pula a fase de apresentação (novo)
- [x] Repetir a conversa até o ponto de oferta da tabela
- [x] Responder apenas "ok" (em vez de uma aceitação explícita)
- [x] Confirmar: bot não pergunta disponibilidade; volta a confirmar o envio da tabela
- [x] Confirmar no trace: `mother_route`/`effective_route` = "apresentation" (não "pre-agendamento")
- **Validado em:** 21/08/2026 — via Playground, lead sandbox #492. Trace confirmou `mother_route: "apresentation"`, `effective_route: "apresentation"`. Turno seguinte ("sim pode enviar") disparou a mídia e a pergunta de qual serviço normalmente, confirmando que o fluxo continua íntegro depois do guardrail atuar.

---

## Ajustes Possíveis Pós-Implementação

- `triggers_fired`/`phases_triggered` detalhados (não só a fase) poderiam aparecer no modal do lead (`LeadCardDialog`), não só no card resumido do Kanban.
- A instrução hardcoded de "reconhecimento de interesse de agendamento" para `direto`/`consultivo` ficou fora de escopo — pode valer revisão futura se também gerar comportamento indesejado nesses modos.
- `kw_trigger` sem `fire_once` não participa do encadeamento sequencial — se necessário no futuro, exigiria decidir se passa a registar satisfação persistida mesmo sem `fire_once` (mudaria semântica de reforço atual).
