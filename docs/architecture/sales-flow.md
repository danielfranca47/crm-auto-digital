# Camada 7 — Fluxo de Venda

## Visão geral

O Fluxo de Venda (Camada 7) é um builder visual que permite configurar **blocos tipados por fase** do pipeline de vendas. Em vez de depender exclusivamente do LLM para decidir como agir em cada etapa, o usuário pode pré-programar comportamentos determinísticos: injectar orientações no prompt, enviar mídias automáticas, avançar fases, disparar webhooks ou configurar espera.

O Fluxo de Venda opera **como uma camada que corre antes do prompt filho** no `decision_engine.py`. Seus resultados (orientações injectadas, mídias, system_actions) são compostos no `DecisionOutput` juntamente com o resultado do LLM.

**Onde é configurado:** tela do Agente → aba "Fluxo de Venda" (componente `CamadaFluxoVenda.tsx`).

**Onde é armazenado:** campo `sales_flow` em `ai_profiles` — JSON com estrutura `{phases: [{id, blocks[]}]}`.

**Onde é executado:** `backend-executors/app/services/decision_engine.py` → `_evaluate_sales_flow_phases()`.

---

## Fases (p0–p5)

| Phase ID | Nome | `effective_route_to` | Sempre ativo? |
|---|---|---|---|
| `p0` | Recepção | `recepcao` | Sim |
| `p1` | Qualificação | `qualification` | Sim |
| `p2` | Apresentação | `apresentation` | Sim |
| `p3a` | Pré-Agendamento | `pre_agendamento` | Só `agenda` |
| `p3b` | Agendamento | `agendamento` | Só `agenda` |
| `p4` | Follow Up | `followup` / `follow-up` | Não para `direto` |
| `p5` | Fechamento | `closing` | Sim |

O mapeamento `effective_route_to → phase_id` está em `_ROUTE_TO_PHASE_ID` dentro de `_evaluate_sales_flow_phases()`.

---

## Pipeline por tipo de agente

O builder adapta a UI e o executor filtra os blocos com base no `agent_mode` do AI Profile.

| Grupo (normalizado) | `agent_mode` equivalente | Fases ativas |
|---|---|---|
| `consultivo` | `consultivo` | p0 → p1 → p2 → p4 → p5 |
| `direto` | `direto`, `closer` | p0 → p1 → p2 → p5 |
| `agenda` | `agenda`, `sdr_scheduler` | p0 → p1 → p2 → p3a → p3b → p4 → p5 |

**No builder (frontend):**
- Fases p3a/p3b são renderizadas apenas para agentes do grupo `agenda`
- Fases inativas para o agent_mode atual ficam com opacidade reduzida e badge "Não ativo neste agente"

**No executor (backend):**
- `_evaluate_sales_flow_phases()` recebe `effective_route_to` da decisão da LLM Mãe e processa apenas os blocos da fase correspondente — não há filtragem explícita por agent_mode no backend, pois rotas inativas simplesmente nunca chegam ao engine

---

## Tipos de bloco

### Triggers (activam a avaliação de blocos de ação)

| `typeId` | Nome | Comportamento em runtime |
|---|---|---|
| `kw_trigger` | Palavra-chave | Activa se a mensagem do lead contém a(s) keyword(s) definidas |
| `phase_trigger` | Entrada na fase | Activa sempre que a fase for a rota resolvida (sem condição de mensagem) |
| `no_reply_trigger` | Sem resposta | Activa quando o lead não respondeu por N unidades de tempo (`wait_value` + `wait_unit`) |
| `intent_trigger` | Intenção detectada | Activa se o intent da mensagem bate com o campo `intent` (ex: `"pergunta_preco"`) |

### Ações (executadas quando o trigger bate)

| `typeId` | Nome | Comportamento em runtime |
|---|---|---|
| `orientacao` | Orientação ao LLM | Texto injectado como instrução adicional no prompt filho da fase |
| `mensagem` | Mensagem fixa | Texto enviado como `system_actions[{type: "send_message", content}]` |
| `midia` | Mídia | Item de `knowledge_media` enviado como `pre_send_media` antes da mensagem |
| `avancar_fase` | Avançar fase | Dispara `system_actions[{type: "advance_phase", target_phase}]` → move lead no Kanban |
| `webhook` | Webhook | Destinado a disparar chamada HTTP externa (execução futura) |

### Lógica

| `typeId` | Nome | Comportamento em runtime |
|---|---|---|
| `condicao` | Condição (bifurcação) | Avaliação de condição com ramos `branch_yes` / `branch_no` (execução futura) |
| `espera` | Espera inteligente | Agenda próxima avaliação após delay (`wait_value` + `wait_unit`) |

> **Nota:** `webhook`, `condicao` e `espera` têm infraestrutura de dados mas a execução em runtime ainda não está implementada no `decision_engine.py`. São blocos reservados para implementação futura.

---

## Fluxo de execução (backend)

```
decision_engine.decide(context)
  → LLM Mãe → route_to (ex: "apresentation")
  → _evaluate_sales_flow_phases(context, effective_route_to, message_text)
      → _ROUTE_TO_PHASE_ID["apresentation"] → "p2"
      → itera sobre phases[] do sales_flow do AI Profile
      → para a fase "p2": itera sobre blocks[]
          → avalia trigger de cada bloco (kw, phase, no_reply, intent)
          → se trigger bate:
              orientacao  → adiciona a prompt_injections[]
              mensagem    → adiciona a system_actions[{type:"send_message"}]
              midia       → adiciona a pre_send_media[]
              avancar_fase → adiciona a system_actions[{type:"advance_phase"}]
      → retorna {prompt_injections, pre_send_media, system_actions}
  → injeta prompt_injections no prompt filho
  → LLM Filha → ChildResult
  → compose_decision_output(...)
      → DecisionOutput.pre_send_media = [sales_flow_media] + [media_from_child]
      → DecisionOutput.system_actions = [...]
```

**Resultado em `DecisionOutput`:**
- `pre_send_media` — lista de dicts com `{media_type, url, caption, ...}` a enviar antes do texto
- `system_actions` — lista de dicts com `{type, ...}` a executar pelo executor do CRM

---

## Dispatch de system_actions (executor CRM)

Após receber o `DecisionOutput`, o `backend-crm/routes/executor.py` chama `_dispatch_system_actions()`:

```python
_PHASE_ID_TO_CATEGORY = {
    "p1":  "qualification",
    "p2":  "apresentation",
    "p3a": "apresentation",
    "p3b": "apresentation",
    "p4":  "followup",
    "p5":  "closing",
}
```

| `action.type` | O que faz |
|---|---|
| `send_message` | Cria job `whatsapp.send.local` com o texto do campo `content` |
| `advance_phase` | Resolve `target_phase` via `_PHASE_ID_TO_CATEGORY` → chama `apply_suggested_category()` |

---

## Armazenamento

O Fluxo de Venda é salvo no campo `sales_flow` da tabela `ai_profiles` (backend-core), como JSON:

```json
{
  "phases": [
    {
      "id": "p0",
      "blocks": []
    },
    {
      "id": "p2",
      "blocks": [
        {
          "id": "uuid",
          "typeId": "orientacao",
          "content": "Apresente a oferta principal no início da conversa.",
          "priority": "high"
        }
      ]
    }
  ]
}
```

O campo é lido pelo orchestrator do CRM e inserido no `ContextBundle` via `enrich_context_bundle()`, chegando ao executor no `context.ai_profile.sales_flow`.

---

## Arquivos críticos

| Arquivo | Responsabilidade |
|---|---|
| `frontend-crm/src/types/agente.ts` | Tipos TypeScript: `SalesFlowPhaseId`, `SalesFlowBlock`, `SalesFlowPhaseData`, `SALES_FLOW_PHASES_BY_AGENT_MODE` |
| `frontend-crm/src/components/agente/CamadaFluxoVenda.tsx` | Builder visual: renderização de fases, blocos, formulários de configuração |
| `backend-executors/app/services/decision_engine.py` | `_evaluate_sales_flow_phases()` — avaliação de triggers, coleta de orientações/mídia/system_actions |
| `backend-crm/routes/executor.py` | `_dispatch_system_actions()`, `_dispatch_sales_flow_media()`, `_PHASE_ID_TO_CATEGORY` |
| `backend-core/app/models/ai_profile.py` | Campo `sales_flow` na tabela `ai_profiles` |
| `backend-crm/services/ai_orchestrator/orchestrator.py` | `enrich_context_bundle()` — inclui `sales_flow` no ContextBundle |
