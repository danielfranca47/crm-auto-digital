# Fix: Fluxo de Venda — gating sequencial de gatilhos + orientações críticas persistentes

**Branch:** `fix-fluxo-vendas-sequencial`
**Status:** Em andamento

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

### Fase 2 — Backend: `is_phase_entry` correto nas chamadas de construção de prompt

**Objetivo:** eliminar a inconsistência entre o que o prompt afirma (default `True`) e o que realmente foi despachado (`is_phase_entry` calculado corretamente).

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/decision_engine.py` | Threading do `is_phase_entry` real para as 4 chamadas de `_build_child_prompt_*` |

### Fase 3 — Backend + Frontend: migrar regra de agendamento hardcoded para bloco editável

**Objetivo:** dar ao utilizador controlo total sobre a instrução de "reconhecimento de interesse de agendamento" — editável/removível, com padrão pré-preenchido.

Escopo: só agentes com recursos de agendamento (`agent_1`/SDR e `agent_3`/Híbrido — grupo normalizado `agenda`). Para `direto`/`consultivo` (`agent_2`/Closer e Consultivo), sem mudança nesta iteração.

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/decision_engine.py` | `_build_child_prompt_apresentation`: para `agent_mode_normalized == 'agenda'`, usar bloco `booking_signal_opener` da fase p2 se configurado; fallback hardcoded só se p2 nunca foi configurada |
| `frontend-crm/src/components/agente/CamadaFluxoVenda.tsx` | Novo card `booking_signal_opener` na fase p2 (padrão `qual_opener`), visível só quando `agentGroup === 'agenda'` |
| `frontend-crm/src/types/agente.ts` | Novo flag `booking_signal_opener?: boolean` em `SalesFlowBlock` |

### Fase 4 — Frontend: funil visual resumido no card do Kanban

**Objetivo:** mostrar, de forma compacta, por onde o lead já passou no Fluxo de Venda.

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/types/crm.ts` | `phases_triggered?: string[]` em `interface Lead` |
| `frontend-crm/src/components/LeadCard.tsx` | Breadcrumb compacto de fases (concluída/atual/futura) |
| `frontend-crm/src/contexts/LeadsContext.tsx` (ou `KanbanBoard.tsx`) | Busca `agent_mode` uma única vez para derivar a sequência de fases |

---

## Checks de Validação

### Cenário P1 — Gatilho posterior não salta na frente (pytest)
- [ ] `detected_intents` inclui a label do 2º `intent_trigger` mas não a do 1º (que ainda não está em `triggers_fired`)
- [ ] Confirmar: 2º gatilho não dispara (bloqueado), `system_actions`/`prompt_injections` do 2º grupo ausentes

### Cenário P2 — Orientação crítica persiste entre turnos (pytest)
- [ ] Turno 1: `phase_trigger` dispara, orientação crítica aparece em `prompt_injections`
- [ ] Turno 2 (sem `is_phase_entry`, sem o gatilho seguinte satisfeito): orientação crítica continua em `prompt_injections`
- [ ] Turno 3 (gatilho seguinte satisfeito/persistido): orientação crítica desaparece

### Cenário P3 — `is_phase_entry` correto no prompt (pytest)
- [ ] Turno 2+ da mesma fase: prompt não repete "ATENÇÃO: mensagens enviadas automaticamente"

### Cenário P4 — Bloco `booking_signal_opener` editável (builder)
- [ ] Fase p2, `agent_mode` do grupo `agenda`: card com texto padrão aparece
- [ ] Editar texto → salva
- [ ] Remover bloco → backend deixa de aplicar reconhecimento automático de agendamento

### Cenário C1 — WhatsApp real: bot não pergunta disponibilidade antes da tabela ser aceita
- [ ] Reproduzir a conversa do relato original (perguntar algo não relacionado após a saudação de entrada)
- [ ] Confirmar: bot não pergunta dia/horário antes do lead aceitar a tabela

### Cenário C2 — Funil no Kanban (browser MCP)
- [ ] Abrir Kanban com lead em fase intermediária do Fluxo de Venda
- [ ] Confirmar: breadcrumb mostra fase atual + fases concluídas de forma compacta

---

## Ajustes Possíveis Pós-Implementação

- `triggers_fired`/`phases_triggered` detalhados (não só a fase) poderiam aparecer no modal do lead (`LeadCardDialog`), não só no card resumido do Kanban.
- A instrução hardcoded de "reconhecimento de interesse de agendamento" para `direto`/`consultivo` ficou fora de escopo — pode valer revisão futura se também gerar comportamento indesejado nesses modos.
- `kw_trigger` sem `fire_once` não participa do encadeamento sequencial — se necessário no futuro, exigiria decidir se passa a registar satisfação persistida mesmo sem `fire_once` (mudaria semântica de reforço atual).
