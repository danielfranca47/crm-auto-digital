# Camada 7 — Fluxo de Venda

## Visão geral

O Fluxo de Venda (Camada 7) é um builder visual que permite configurar **blocos tipados por fase** do pipeline de vendas. Em vez de depender exclusivamente do LLM para decidir como agir em cada etapa, o usuário pode pré-programar comportamentos determinísticos: injectar orientações no prompt, enviar mídias automáticas, avançar fases, disparar webhooks ou configurar espera.

O Fluxo de Venda opera **como uma camada que corre antes do prompt filho** no `decision_engine.py`. Seus resultados (orientações injectadas, mídias, system_actions) são compostos no `DecisionOutput` juntamente com o resultado do LLM.

**Onde é configurado:** tela do Agente → aba "Fluxo de Venda" (componente `CamadaFluxoVenda.tsx`).

**Onde é armazenado:** campo `sales_flow` em `ai_profiles` — JSON com estrutura `{phases: [{id, blocks[]}]}`.

**Onde é executado:** `backend-executors/app/services/decision_engine.py` → `_evaluate_sales_flow_phases()`.

**Disponibilidade:** o Fluxo de Venda está disponível para qualquer agente, independente de `response_style` (`active` ou `passive`) — o único controlo de on/off é `sales_flow.enabled`. Em modo passivo, o prompt de qualificação tem uma regra absoluta de "zero perguntas abertas" (inferência silenciosa); blocos `orientacao` configurados com instruções que façam perguntas directas podem contradizer essa regra, já que são injectados com prioridade alta. É responsabilidade de quem configura o Fluxo de Venda manter os blocos coerentes com o `response_style` do agente — não há validação automática disso.

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
| `kw_trigger` | Palavra-chave | Activa se a mensagem do lead contém a(s) keyword(s) definidas. Suporta `fire_once` (ver abaixo). |
| `phase_trigger` | Entrada na fase | Activa **uma única vez por lead** — na primeira mensagem que chega à fase. Rastreado por `leads.phases_triggered` (JSON array de phase IDs disparados). Quando dispara, injeta contexto no `prompt_injections` e emite `mark_phase_triggered`. |
| `no_reply_trigger` | Sem resposta | Placeholder de UI. Não avaliado em runtime. |
| `intent_trigger` | Intenção detectada | A LLM Mãe recebe secção `[DETECÇÃO DE INTENÇÃO]` condicional se a fase **atual** do lead ou a **fase seguinte** (dado o pipeline do `agent_mode`, ver tabela acima) tiver blocos deste tipo. Retorna `detected_intents: list[str]`. O bloco dispara se `intent_label in detected_intents`. Suporta `fire_once` (ver abaixo). |

> **Janela de detecção de 1 fase à frente:** `_collect_intent_triggers_for_lead_phase()` mostra à mãe os `intent_trigger` da fase salva em `lead.category` **e** da fase seguinte na sequência de `_SALES_FLOW_PHASE_SEQUENCE_BY_AGENT_MODE` (`decision_engine.py`, espelha a tabela de pipeline acima). Isso é necessário porque a transição de fase só é decidida pela própria mãe nesse turno — sem essa antecipação, um `intent_trigger` configurado como o sinal de entrada numa fase (ex.: "cliente aceitou a oferta") nunca teria como disparar na mensagem que efetivamente o causa. A avaliação de disparo em si (`_evaluate_sales_flow_phases`) continua olhando só a fase escolhida pelo `effective_route_to` da mãe nesse turno — a antecipação afeta apenas o que é mostrado à mãe, não quais blocos podem executar.
>
> **Consistência `reason` ↔ `detected_intents`:** `generate_mother_route()` usa JSON solto (`text.format.type="json_object"`), sem schema reforçado pela API — a mãe pode reconhecer a intenção em prosa livre no campo `reason` sem replicá-la em `detected_intents`. O bloco `[DETECÇÃO DE INTENÇÃO]` (fim do prompt, mais perto da geração) inclui uma instrução explícita exigindo essa consistência. Se `detected_intents` continuar inconsistente com `reason` em produção, revisar esse reforço antes de mexer no motor de avaliação — o bug historicamente esteve na confiabilidade do prompt, não em `_evaluate_sales_flow_phases`.

### Flag especial de bloco: `qual_opener`

Blocos do tipo `orientacao` na fase p1 podem ter o flag `qual_opener: true`. Identifica o bloco como **abertura de qualificação** — uma instrução que pede permissão ao lead antes das perguntas de qualificação.

**Comportamento em runtime:** detectado em `_build_child_prompt_qualification()` e injectado no prompt apenas quando `asked_questions_json` está vazio (primeira mensagem da fase de qualificação) e `qualification_fields` tem pelo menos 1 campo ativo. Não repete em turnos seguintes.

**No frontend:** na fase p1 do builder (`CamadaFluxoVenda.tsx`), quando `qualification_fields` tem campos ativos:
- Se não existe bloco `qual_opener` → banner "Sem instrução de abertura configurada" com botão "+ Adicionar abertura"
- Se existe → `QualOpenerCard` com label "Abertura de Qualificação", badge "automática · 1ª mensagem", botões "Editar" e "Remover"

**Texto padrão gerado:** "Antes de fazer as primeiras perguntas de qualificação, pede permissão ao lead de forma natural, sem repetir saudações já feitas: algo como 'Posso te fazer algumas perguntas rápidas para perceber como podemos ajudar melhor?' — adapta ao tom de voz e ao contexto da conversa."

### Ações (executadas quando o trigger bate)

| `typeId` | Nome | Comportamento em runtime |
|---|---|---|
| `orientacao` | Orientação ao LLM | Texto injectado como instrução adicional no prompt filho da fase |
| `mensagem` | Mensagem fixa | Texto enviado como `system_actions[{type: "send_message", content}]` |
| `midia` | Mídia | Enviado como `system_actions[{type: "send_media", media_url, media_type}]`, na sequência configurada entre outros blocos. |
| `avancar_fase` | Avançar fase | Dispara `system_actions[{type: "advance_phase", target_phase}]` → move lead no Kanban |
| `webhook` | Webhook | Destinado a disparar chamada HTTP externa (execução futura) |

> Quando `phase_trigger` dispara, blocos `mensagem` e `midia` subsequentes também adicionam o conteúdo enviado a `prompt_injections`, para que o LLM filho saiba o que foi enviado automaticamente e possa complementar sem repetir.

### Lógica

| `typeId` | Nome | Comportamento em runtime |
|---|---|---|
| `condicao` | Condição (bifurcação) | Avaliação de condição com ramos `branch_yes` / `branch_no` (execução futura) |
| `espera` | Espera inteligente | Agenda próxima avaliação após delay (`wait_value` + `wait_unit`) |

> **Nota:** `webhook`, `condicao` e `espera` têm infraestrutura de dados mas a execução em runtime ainda não está implementada no `decision_engine.py`. São blocos reservados para implementação futura.

---

## Flags opcionais em blocos de trigger

### `fire_once` (`kw_trigger`, `intent_trigger`)

Quando `fire_once: true`, o bloco dispara apenas **uma vez por lead**:
- Ao disparar, emite `{type: "mark_trigger_fired", block_id}` nos `system_actions`
- CRM (playground e executor) faz append do `block_id` em `leads.triggers_fired` (JSON array)
- Em disparos seguintes: `already_fired = block_id ∈ triggers_fired` → `fired = False`

**DB:** coluna `leads.triggers_fired TEXT NULL` (adicionada em `backend-crm/database.py` via `ensure_column`).

### `suppress_llm_response` (`kw_trigger`, `intent_trigger`, `phase_trigger`)

Quando `suppress_llm_response: true` e o trigger dispara:
- As ações automáticas (`mensagem`, `midia`) são executadas normalmente
- O `decision_engine` força `next_action = "ignore"` e `message_text = ""`
- **Playground:** frontend omite o turno da LLM; exibe apenas os `auto_items`
- **WhatsApp real:** runner despacha `_send_actions` sincronamente, completa job com `skipped_suppress_llm` (sem enviar mensagem LLM)

---

## Fluxo de execução (backend)

### Modelo sequencial de trigger (`_evaluate_sales_flow_phases`)

Os blocos de uma fase são avaliados em sequência. Um flag `last_trigger_active` propaga a decisão do último trigger para os blocos de ação seguintes:

```
last_trigger_active = True   # default: ações sem trigger explícito sempre disparam

para cada block em fase.blocks:
    se block é trigger (kw/phase/intent/no_reply):
        fired = avaliar_trigger(block, context)
        last_trigger_active = fired
        se fired e block.suppress_llm_response:
            result["suppress_llm_response"] = True
    se block é ação (orientacao/mensagem/midia/avancar_fase):
        se last_trigger_active:
            executar_ação(block, result)
```

**Avaliação por tipo de trigger:**

| Trigger | Condição de `fired = True` |
|---|---|
| `phase_trigger` | `is_phase_entry = True` — derivado de `lead.category != effective_route_to` **E** `phase_id ∉ leads.phases_triggered` |
| `kw_trigger` | Keyword match na mensagem + `fire_once` check (`block_id ∉ leads.triggers_fired` se `fire_once=True`) |
| `intent_trigger` | `intent_label in detected_intents` (da LLM Mãe) + `fire_once` check |
| `no_reply_trigger` | Nunca (placeholder) |

**Destino das ações:**

| Ação | Destino |
|---|---|
| `orientacao` | `result["prompt_injections"]` → injectado no prompt filho |
| `mensagem` | `result["system_actions"][{type:"send_message", content}]` |
| `midia` | `result["system_actions"][{type:"send_media", media_url, media_type}]` |
| `avancar_fase` | `result["system_actions"][{type:"advance_phase", target_phase}]` |

**Contexto para o LLM filho (quando `phase_trigger` dispara):**

O engine adiciona um preamble a `prompt_injections` seguido das mensagens/mídias automáticas enviadas. O LLM filho recebe o contexto do que foi enviado e deve complementar — não repetir.

**Supressão da LLM (`suppress_llm_response`):**

Se `result["suppress_llm_response"] = True`, `compose_decision_output()` força `next_action = "ignore"` e `message_text = ""`. As `system_actions` são preservadas e despachadas normalmente.

### Ordem de exibição / envio

| Cenário | Ordem |
|---|---|
| `phase_trigger` disparou | Auto-mensagens → LLM |
| `kw_trigger` ou `intent_trigger` disparou (sem `suppress_llm_response`) | LLM → Auto-mensagens |
| `suppress_llm_response = True` | Apenas auto-mensagens (LLM omitido) |
| Nenhum trigger activo | Apenas LLM |

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
| `send_media` | Cria job `whatsapp.send.local` com `media_url` e `media_type` |
| `advance_phase` | Resolve `target_phase` via `_PHASE_ID_TO_CATEGORY` → chama `apply_suggested_category()` |
| `mark_phase_triggered` | Append do `phase_id` em `leads.phases_triggered` |
| `mark_trigger_fired` | Append do `block_id` em `leads.triggers_fired` |

---

## WhatsApp real — runner (`whatsapp.py`)

Após `decision_engine.decide()`, o runner classifica as `system_actions` em dois grupos:

```python
_send_actions  = [a for a in system_actions if a["type"] in ("send_message", "send_media")]
_state_actions = [a for a in system_actions if a["type"] not in ("send_message", "send_media")]
```

- **`_send_actions`** são despachados sincronamente via `_send_sales_flow_action()` (chamada directa à API do WhatsApp), antes ou depois da mensagem LLM consoante `phase_trigger_fired`.
- **`_state_actions`** são passados ao CRM no `result_payload["system_actions"]` para persistência (executor.py os processa via `_dispatch_system_actions()`).

Comportamento especial quando `suppress_llm_response=True`:
- `_send_actions` são despachados normalmente (sem mensagem LLM)
- Job completa com `outbound_status = "skipped_suppress_llm"`

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

**Colunas adicionais em `leads` (backend-crm):**

| Coluna | Tipo | Descrição |
|---|---|---|
| `phases_triggered` | `TEXT NULL` | JSON array de phase IDs disparados por este lead (ex: `["p2", "p3a"]`) |
| `triggers_fired` | `TEXT NULL` | JSON array de block IDs disparados com `fire_once` (ex: `["uuid1", "uuid2"]`) |

Ambas adicionadas via `ensure_column()` em `backend-crm/database.py`.

---

## Arquivos críticos

| Arquivo | Responsabilidade |
|---|---|
| `frontend-crm/src/types/agente.ts` | Tipos TypeScript: `SalesFlowPhaseId`, `SalesFlowBlock`, `SalesFlowPhaseData`, `SALES_FLOW_PHASES_BY_AGENT_MODE` |
| `frontend-crm/src/components/agente/CamadaFluxoVenda.tsx` | Builder visual: renderização de fases, blocos, formulários de configuração |
| `backend-executors/app/services/decision_engine.py` | `_evaluate_sales_flow_phases()` — avaliação de triggers, coleta de orientações/mídia/system_actions; `_collect_intent_triggers_for_lead_phase()` — seleciona quais `intent_trigger` mostrar à mãe (fase atual + seguinte) |
| `backend-crm/routes/executor.py` | `_dispatch_system_actions()`, `_dispatch_sales_flow_media()`, `_PHASE_ID_TO_CATEGORY` |
| `backend-core/app/models/ai_profile.py` | Campo `sales_flow` na tabela `ai_profiles` |
| `backend-crm/services/ai_orchestrator/orchestrator.py` | `enrich_context_bundle()` — inclui `sales_flow` no ContextBundle |
