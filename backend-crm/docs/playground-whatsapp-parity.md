# Paridade de Contexto: Playground ↔ WhatsApp Real

> **Leia este documento antes de alterar qualquer um destes arquivos:**
> - `routes/playground.py`
> - `services/whatsapp_inbound/inbound_handler.py`
> - `routes/executor.py`
> - `services/ai_orchestrator/orchestrator.py`

O objetivo do playground é simular o agente real WhatsApp. Para isso, **ambos os caminhos devem montar um `ContextBundle` estruturalmente equivalente** antes de chamar o decision engine (`decide_next_action`) ou o LLM.

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
  → build_context_bundle_from_inbound(event)    ← bundle base (sem knowledge_items, sem enriquecimento)
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

**Localização:** `services/ai_orchestrator/orchestrator.py`

```python
def enrich_context_bundle(bundle: ContextBundle, user_id: int) -> ContextBundle:
```

Esta é a **única fonte de enriquecimento**. Qualquer campo novo que afete o comportamento do LLM deve ser adicionado aqui — nunca diretamente nos builders individuais.

### O que ela faz hoje

| Tag | Campo no bundle | Origem |
|-----|----------------|--------|
| B1  | `knowledge_items` | Filtrado por `active_in_funnel = 1` em `_load_knowledge_items()` |
| B2  | `knowledge_items["business_info"]` | `_load_business_info(user_id)` — espelho de executor.py |
| B3  | `generated_prompt_parts` | Elevado de `ai_profile["generated_prompt_parts"]` para raiz do bundle |
| B4  | `lead_detected_language` | Elevado de `lead["detected_language"]`, fallback `"all"` |

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
| `knowledge_media` | `_load_knowledge_media()` no builder | — (não carregado no builder) | Não (carregado no builder do playground) |
| `business_info` | — | — | **Sim (B2, injetado em knowledge_items)** |
| `generated_prompt_parts` | — | — | **Sim (B3)** |
| `lead_detected_language` | — | — | **Sim (B4)** |

> **Divergência estrutural aceitável:** `ai_profile`, `training_examples` e `qualification_state` chegam
> por caminhos diferentes (parâmetro vs. API vs. SQL), mas o conteúdo final que chega ao prompt é equivalente.

---

## Regras para Novas Implementações

### Ao adicionar um novo campo ao ContextBundle que afeta o LLM:

1. **Adicione o campo em `enrich_context_bundle()`** — isso garante que ambos os caminhos recebem o campo automaticamente.
2. Não adicione o campo diretamente no builder do playground (`build_context_bundle_for_playground`) nem no executor sem passar por `enrich_context_bundle`.
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

## Arquivos Críticos

| Arquivo | Responsabilidade |
|---------|-----------------|
| `services/ai_orchestrator/orchestrator.py` | `enrich_context_bundle`, `build_context_bundle_for_playground`, `build_context_bundle_from_inbound`, `ContextBundle` |
| `services/whatsapp_inbound/inbound_handler.py` | Recebe webhook, monta bundle base, enfileira ou decide localmente |
| `routes/executor.py` | Consome fila, chama `enrich_context_bundle`, decide e envia |
| `routes/playground.py` | Endpoint de simulação, usa `build_context_bundle_for_playground` |

---

## Histórico de Paridade

| Commit | O que convergiu |
|--------|----------------|
| `115fdf5` | Introduziu `enrich_context_bundle` unificando B1–B4 entre playground e executor |
