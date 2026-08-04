# Paridade de Contexto: Playground ↔ WhatsApp Real

> **Leia antes de alterar qualquer um destes arquivos:**
> - `backend-crm/routes/playground.py`
> - `backend-crm/services/whatsapp_inbound/inbound_handler.py`
> - `backend-crm/routes/executor.py`
> - `backend-crm/services/ai_orchestrator/orchestrator.py`

O playground simula o agente real WhatsApp. Para isso, **ambos os caminhos devem montar um `ContextBundle` estruturalmente equivalente** antes de chamar o decision engine ou o LLM.

---

## Fluxos de Contexto

### Playground (simulação)

```
routes/playground.py
  → orchestrator.build_context_bundle_for_playground(user_id, ai_profile, lead_id, ...)
      → ContextBundle base (knowledge_items, knowledge_media, training_examples, qualification_state, ...)
      → enrich_context_bundle(bundle, user_id)   ← PONTO DE CONVERGÊNCIA
  → decide_next_action(bundle)
  → llm.generate_response(bundle)
```

### WhatsApp Real — Caminho Executor (produção)

```
services/whatsapp_inbound/inbound_handler.py
  → build_context_bundle_from_inbound(event)    ← bundle base
  → [enfileira job → routes/executor.py]
      → build_context_bundle_from_inbound(event)
      → enrich_context_bundle(bundle, user_id)   ← PONTO DE CONVERGÊNCIA
      → decide_next_action(bundle)
      → llm.generate_response(bundle)
```

### WhatsApp Real — Caminho Local (desativado por padrão)

```
services/whatsapp_inbound/inbound_handler.py
  → build_context_bundle_from_inbound(event)
  → decide_next_action(bundle)    ← ⚠️ SEM enrich_context_bundle
```

> **Ativo somente quando** `CRM_DISABLE_LOCAL_ORCHESTRATOR=false` (padrão é `True`, ou seja, desativado).
> Se este caminho for reativado, deve receber chamada a `enrich_context_bundle` antes de `decide_next_action`.

---

## Função Central: `enrich_context_bundle`

**Localização:** `backend-crm/services/ai_orchestrator/orchestrator.py`

```python
def enrich_context_bundle(bundle: ContextBundle, user_id: int) -> ContextBundle:
```

Esta é a **única fonte de enriquecimento**. Qualquer campo novo que afete o comportamento do LLM deve ser adicionado aqui — nunca diretamente nos builders individuais.

### O que ela faz

| Tag | Campo no bundle | Origem |
|-----|----------------|--------|
| B1  | `knowledge_items` | Filtrado por `active_in_funnel = 1` em `_load_knowledge_items()` |
| B2  | `knowledge_items["business_info"]` | `_load_business_info(user_id)` |
| B3  | `generated_prompt_parts` | Elevado de `ai_profile["generated_prompt_parts"]` para raiz do bundle |
| B4  | `lead_detected_language` | Elevado de `lead["detected_language"]`, fallback `"all"` |
| B5  | `calendar_busy_slots` | `_load_calendar_busy_slots(user_id)` — só quando `ai_profile.agent_mode == "agenda"` e o bundle ainda não o tem. Ver [`agenda.md`](agenda.md) |
| B6  | `metadata["bot_disabled"]` / `metadata["bot_disabled_reason"]` | Propaga quando `lead.bot_disabled` e `lead.bot_disabled_reason == "meeting_scheduled"`. `bot_disabled` propaga sempre nesse caso; o reason só recebe `"meeting_scheduled"` quando `ai_profile.meeting_management_enabled` é `True` — senão fica `None`, levando `decide()` a tratar como desactivado padrão (ignore). Outros motivos de `bot_disabled` (ex.: `handoff_requested`) **não** são propagados aqui, propositalmente — `routes/executor.py` faz essa propagação para o fluxo real de forma equivalente (ver `agents.md`, secção "Gestão pós-confirmação") |

---

## ContextBundle — Campos e Origem

| Campo | Playground | Executor (real) | Via `enrich_context_bundle` |
|-------|-----------|-----------------|----------------------------|
| `ai_profile` | Parâmetro direto | `fetch_core_ai_profile_resolve()` | Não |
| `playbook` | `get_playbook()` + `apply_mode_overrides()` | Idem | Não |
| `lead` | `_load_lead()` | `_load_lead()` | Não |
| `history` | `get_recent_history()` | `get_recent_history()` | Não |
| `qualification_state` | `get_qualification_state()` no builder | Carregado no executor pós-bundle | Não |
| `training_examples` | `_load_training_examples()` no builder | `_load_training_examples()` no executor pós-bundle | Não |
| `knowledge_items` | `_load_knowledge_items()` no builder | — (não carregado no builder) | **Sim (B1 + B2)** |
| `knowledge_media` | `_load_knowledge_media()` no builder | — | Não |
| `business_info` | — | — | **Sim (B2, injetado em knowledge_items)** |
| `generated_prompt_parts` | — | — | **Sim (B3)** |
| `lead_detected_language` | — | — | **Sim (B4)** |
| `calendar_busy_slots` | — | — | **Sim (B5)** |
| `metadata.bot_disabled`/`bot_disabled_reason` | — | `routes/executor.py` seta diretamente (fora de `enrich_context_bundle`) | **Sim no Playground (B6, só para `reason="meeting_scheduled"`)** |

---

## Regras para Novas Implementações

### Ao adicionar um novo campo ao ContextBundle que afeta o LLM:

1. **Adicione o campo em `enrich_context_bundle()`** — isso garante que ambos os caminhos recebem o campo automaticamente.
2. Não adicione o campo diretamente no builder do playground nem no executor sem passar por `enrich_context_bundle`.
3. Se o campo for operacional (ex.: metadado de canal, message_id) e não afetar o prompt, pode ser adicionado no builder específico.

### Checklist ao alterar o playground

- [ ] A alteração afeta o comportamento do LLM (tom, contexto, filtros)?
- [ ] Se sim: foi adicionada via `enrich_context_bundle()` ou já existia em ambos os builders?
- [ ] O mesmo comportamento aconteceria no executor (`routes/executor.py`)?

### Checklist ao alterar o agente real (inbound_handler / executor)

- [ ] A alteração afeta o contexto passado ao `decide_next_action` ou ao LLM?
- [ ] Se sim: foi adicionada via `enrich_context_bundle()` ou está espelhada no builder do playground?
- [ ] Rodar o playground com o mesmo lead para confirmar comportamento equivalente.

---

## Modo Follow-Up no Playground

O playground suporta um terceiro tipo de cenário (`scenario_type = "followup"`) que simula um tick automático de follow-up sem precisar de um lead real com `followup_contract`.

### Como funciona

O operador configura no `PlaygroundConfigModal`:
- **Variante** — auto-detectada do `template_key` (`sdr_scheduler`, `cart_recovery`, `hybrid_scheduler`)
- **Outcome** — como o lead saiu da reunião (hot/warm/cold/lost ou outcomes do hybrid)
- **Goal** — objectivo do follow-up (advance_closing, nurture, reschedule_conversation)
- **Tentativa** — qual tentativa simular (1, 2 ou 3)
- **Reunião aconteceu** — bool

O payload enviado inclui `followup_context` com estes campos. O backend (`build_context_bundle_for_playground()` em `orchestrator.py`) injeta o contexto sintético em `metadata["followup_context"]` e define `lead.category = "follow-up"` **apenas em memória** — sem persistir no DB.

O tick dispara automaticamente ao abrir a sessão (sem mensagem do lead), simulando o comportamento real do reconciliador.

### Paridade com o fluxo real

| Comportamento | Real | Playground (followup) |
|---|---|---|
| Disparar tick | Reconciliador detecta `next_followup_at <= now` | Auto-fire ao iniciar sessão |
| `followup_context` | Vem do `followup_contract` do lead | Injectado sinteticamente via `followup_context` |
| `lead.category` | Persistido no DB como `"follow-up"` | Definido em memória no bundle |
| Mensagem do lead | Não existe — o bot envia proactivamente | Hint de tick injectado como `effective_message` |

**Ficheiros chave:**
- `backend-crm/routes/playground.py` — `scenario_type: "followup"`, campo `followup_context`, hint de tick
- `backend-crm/services/ai_orchestrator/orchestrator.py` — `build_context_bundle_for_playground()` aceita `followup_context`
- `frontend-crm/src/components/playground/PlaygroundConfigModal.tsx` — botão "Follow-up" + painel de configuração
- `frontend-crm/src/pages/Playground.tsx` — auto-fire via `useEffect` ao iniciar sessão followup

---

## Arquivos Críticos

| Arquivo | Responsabilidade |
|---------|-----------------|
| `backend-crm/services/ai_orchestrator/orchestrator.py` | `enrich_context_bundle`, builders do ContextBundle |
| `backend-crm/services/whatsapp_inbound/inbound_handler.py` | Recebe webhook, monta bundle base, enfileira ou decide |
| `backend-crm/routes/executor.py` | Consome fila, chama `enrich_context_bundle`, decide e envia |
| `backend-crm/routes/playground.py` | Endpoint de simulação |

---

## Paridade de Humanização Comportamental

Além da paridade de contexto LLM, o playground expõe campos de preview que simulam o comportamento temporal do agente no WhatsApp real.

### Campos na resposta do playground (`PlaygroundChatResponse`)

| Campo | Descrição | Equivalente real |
|-------|-----------|-----------------|
| `simulated_delay_seconds` | Delay antes de responder (sorteado entre min/max do AI Profile) | `scheduled_at` do job em `inbound_handler.py` |
| `typing_seconds` | Duração do "Digitando..." exibido no WhatsApp | Campo `delay` enviado à UazAPI via `whatsapp_send.py` |
| `auto_items` | Lista ordenada de itens automáticos: `{type:"text", content, source, source_label}` ou `{type:"media", media_url, media_type}` — do Fluxo de Venda (`_send_actions`) **ou** de uma pergunta comercial pendente extraída pela Filha Recepção (`requeue_pending_message` — ver "Saudação composta" em [`llm-architecture.md`](llm-architecture.md)). `source` distingue a origem de cada item de texto: `"sales_flow"` (bloco `send_message` configurado), `"child_llm"` (resposta real da Filha decidida pela Mãe no turno reenfileirado — `source_label` traz o nome da fase, ex. "Agendamento") ou `"fallback"` (decisão caiu em `llm_failure` — `source_label="Handoff (erro de decisão)"`). Frontend usa isso para rotular e colorir a bolha corretamente em vez de assumir sempre "Fluxo de Venda" | `_send_actions` despachados pelo runner via `_send_sales_flow_action()`; para `requeue_pending_message`, um novo job real processado pelo worker no ciclo seguinte |
| `phase_trigger_fired` | `bool` — quando `True`, frontend exibe `auto_items` **antes** da resposta LLM | Runner envia `_send_actions` antes da mensagem LLM quando `phase_trigger` disparou |
| `suppress_llm_response` | `bool` — quando `True`, frontend omite o turno da LLM por completo (sem bolha vazia) | Runner completa job com `skipped_suppress_llm` sem enviar mensagem LLM |
| `message_parts` | `List[str]` — como a resposta LLM seria dividida em bolhas por pontuação | Executor chama `_split_message_by_punctuation()` e envia cada parte com delay próprio |
| `audio_previews` | `List[str]` — URLs dos `myaudio`/`ptt` da base de conhecimento que seriam enviados como voz | Executor envia `pre_send_media` com `type=myaudio` e `delay_ms=3000` antes de cada um |

### Fórmula do typing indicator

```
delay_ms = min(max(len(text) * 40, 1000), 8000)  # 40ms/char, entre 1s e 8s
```

Implementada em:
- `backend-crm/services/humanization.py` → `compute_typing_ms()` (usado pelo playground)
- `backend-executors/app/runners/whatsapp.py` → inline antes de `core_client.send_whatsapp_message()` (mesmo cálculo, serviços separados)

O campo `delay` é propagado via:
```
executor → POST /whatsapp/send (backend-core) → uazapi_client.send_text(delay_ms=...) → UazAPI
```
