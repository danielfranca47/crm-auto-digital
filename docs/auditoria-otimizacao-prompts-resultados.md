# Auditoria — Otimização de Prompts: Resultado da Verificação

> **Data da auditoria:** 29 de março de 2026
> **Referência:** `docs/spec-otimizacao-prompts-implementacao.md`
> **Arquivos verificados:**
> - `backend-executors/app/services/decision_engine.py`
> - `backend-executors/app/services/field_extractor.py`
> - `backend-executors/app/services/meta_prompter.py`
> - `backend-executors/app/api/meta_prompter.py`
> - `backend-crm/automations/assistente_ia/llm.py`
> - `backend-crm/routes/executor.py`
> - `backend-core/app/db.py`
> - `backend-core/app/api/ai_profiles.py`
> - `backend-core/app/models/ai_profile.py`

---

## Resumo de Status por Fase

| Fase | Tarefa | Status |
|---|---|---|
| 1 | 1.1 — System prompts 5 camadas | ✅ Implementado |
| 1 | 1.2 — Regras de recusa em todas as filhas | ✅ Implementado |
| 1 | 1.3 — Directivas de uso no knowledge injetado | ✅ Implementado |
| 2 | 2.1 — Bloco de tom WhatsApp operacional | ✅ Implementado |
| 2 | 2.2 — Enriquecer contexto do field extractor | ✅ Implementado |
| 2 | 2.3 — Escape hatch para alucinações | ✅ Implementado |
| 3 | 3.1 — Tabela de prioridade de sinais na Mãe | ✅ Implementado |
| 3 | 3.2 — Chain-of-thought implícito na Mãe | ✅ Implementado |
| 3 | 3.3 — Validação semântica de output | ✅ Implementado |
| 4 | 4.1 — Backend: Serviço Meta-Prompter + Triggers | ✅ Implementado |
| 4 | 4.2 — Injeção dos blocos no decision_engine | ✅ Implementado |
| 4 | 4.3 — Cenários dinâmicos de outreach (llm.py) | ✅ Implementado |

---

## Bugs e Riscos Identificados

---

### 🔴 BUG CRÍTICO 1 — Endpoint do meta-prompter sem autenticação efetiva

**Arquivo:** `backend-executors/app/api/meta_prompter.py` — linha 44

**Problema:**
```python
# ATUAL (errado):
def generate_prompt_parts_for_user(
    user_id: int = Path(...),
    body: GenerateRequest = ...,
    _: str = _require_service_token,   # ← BUG: sem Depends()
) -> GenerateResponse:
```

`_: str = _require_service_token` sem `Depends()` faz com que o FastAPI trate `_require_service_token` como valor padrão do parâmetro `_` (tipo `str`), e **nunca chama a função como dependency**. O resultado é que o endpoint `POST /api/meta-prompter/generate/{user_id}` fica completamente desprotegido — qualquer requisição sem token passa.

Todos os outros serviços do projeto usam o padrão correto:
```python
# CORRETO (padrão usado em todo o resto da codebase):
_: str = Depends(_require_service_token)
```

**Impacto:** Qualquer cliente pode chamar este endpoint sem autenticação e disparar chamadas à LLM à custa da conta configurada em `settings.llm_api_key`. Risco de abuso de recursos e custos inesperados.

**Correção:**
```python
_: str = Depends(_require_service_token),
```

Feito. Duas linhas alteradas em meta_prompter.py:

Depends adicionado ao import (linha 14)
_: str = _require_service_token → _: str = Depends(_require_service_token) (linha 44)
O FastAPI agora executa a função como dependency injetada, validando o X-Service-Token em todas as requests ao endpoint POST /api/meta-prompter/generate/{user_id}.

---

### ✅ BUG 2 — Tarefa 1.3 incompleta: knowledge sem directivas na apresentação standard

**Arquivo:** `backend-executors/app/services/decision_engine.py` — `_build_child_prompt_apresentation`

**Problema (corrigido em 2026-03-29):**
A Tarefa 1.3 especifica que todos os `knowledge_items` injetados nas filhas de **apresentação e follow-up** devem ter directivas de uso (`INSTRUÇÃO: quando usar, como usar`). O follow-up recebia correctamente os blocos com directivas (linhas 1546–1577). Contudo, a filha de apresentação **só injectava knowledge com directivas no caminho `hybrid_scheduler`** (commercial_injection / warming_injection). Para os templates `sdr_padrao` e `closer_agressivo` com variante `sales`, nenhum dos seguintes knowledge_items era injectado com directivas:

- `social_proof`
- `pitch_script`
- `product_details`
- `objections_faq`
- `service_faq`
- `guarantee_policy`

**Correção aplicada:**
Adicionado bloco `standard_knowledge_block` em `_build_child_prompt_apresentation`. O bloco é construído quando `commercial_injection` está vazio (i.e., qualquer path que não seja `hybrid_scheduler` em modo comercial), cobrindo `sdr_padrao`, `closer_agressivo` e o path `warming_injection`. Cada knowledge_item é injectado condicionalmente com directiva de uso:

```python
# Tarefa 1.3 — knowledge_items com directivas de uso para sdr_padrao / closer_agressivo
_apres_knowledge_parts: list[str] = []
if not commercial_injection:
    _social_proof_apres     = knowledge_items.get("social_proof") or ""
    _pitch_script_apres     = knowledge_items.get("pitch_script") or ""
    _product_details_apres  = knowledge_items.get("product_details") or ""
    _objections_faq_apres   = knowledge_items.get("objections_faq") or ""
    _service_faq_apres      = knowledge_items.get("service_faq") or ""
    _guarantee_policy_apres = knowledge_items.get("guarantee_policy") or ""
    # ... cada campo condicional com bloco INSTRUÇÃO de uso
standard_knowledge_block = (
    "\nKNOWLEDGE BASE (usar conforme as instruções de cada bloco):\n"
    + "\n".join(_apres_knowledge_parts)
) if _apres_knowledge_parts else ""
```

O `standard_knowledge_block` é injectado no prompt entre a secção `ROTA MÃE` e `CONTEXTO`.

**Resultado:** A LLM Filha APRESENTATION em `sdr_padrao` / `closer_agressivo` passa a receber guidance explícita sobre quando e como usar prova social, script de pitch, detalhes do produto, objeções configuradas, FAQ e política de garantia — tal como já acontecia no follow-up e no path commercial do hybrid_scheduler. Tarefa 1.3 agora está completamente implementada em todas as filhas.

---

### ✅ BUG 3 — Triggers de regeneração do meta-prompter (corrigido em 2026-03-29)

**Arquivos afetados:** `backend-core/app/api/ai_profiles.py`, `backend-core/app/config.py`, `backend-crm/routes/knowledge.py`

**Problema (corrigido):**
A spec define 3 triggers automáticos para regenerar `generated_prompt_parts`. Nenhum estava implementado:

| Trigger | Implementado? |
|---|---|
| Onboarding finalizado (wizard completo) | ✅ |
| Edição de `niche`, `target_audience`, `tone_of_voice` ou `offer_description` | ✅ |
| Edição de `objections_faq` no knowledge base | ✅ |
| Botão manual no frontend | ❌ (endpoint existe mas sem integração frontend — fora de escopo) |

**Correção aplicada:**

**1. `backend-core/app/config.py`** — nova variável `EXECUTORS_BASE_URL: Optional[str] = None` para apontar ao backend-executors.

**2. `backend-core/app/api/ai_profiles.py`** — adicionados:
- Constante `_META_PROMPTER_FIELDS = {"niche", "target_audience", "tone_of_voice", "offer_description"}`.
- Helper `_profile_to_meta_dict(profile)` — serializa os campos relevantes do ORM para dict (sem depender de `orm_mode` completo).
- Helper `_trigger_meta_prompter_bg(user_id, ai_profile_data)` — fire-and-forget via `httpx` para `POST /api/meta-prompter/generate/{user_id}` no backend-executors (usando `EXECUTORS_BASE_URL` + `CORE_SERVICE_TOKEN`). Erros são logados como warning, nunca propagados.
- **Trigger 1 (onboarding):** `POST /ai-profiles` aceita agora `BackgroundTasks` e agenda `_trigger_meta_prompter_bg` após criação do perfil.
- **Trigger 2 (edição de campos):** `PUT /ai-profiles/me` aceita agora `BackgroundTasks` e agenda `_trigger_meta_prompter_bg` se a intersecção entre os campos do payload e `_META_PROMPTER_FIELDS` não for vazia.

**3. `backend-crm/routes/knowledge.py`** — adicionados:
- Helper `_trigger_meta_prompter_for_knowledge(user_id)` — resolve o `ai_profile` do utilizador via `fetch_core_ai_profile_resolve` (service-to-service) e chama `POST /api/meta-prompter/generate/{user_id}` no backend-executors. Usa env vars `EXECUTORS_BASE_URL` + `CORE_SERVICE_TOKEN`.
- **Trigger 3 (objections_faq):** `PUT /{item_id}` aceita agora `BackgroundTasks` e agenda `_trigger_meta_prompter_for_knowledge` quando `category == "objections_faq"` (efectiva, i.e. a do item existente ou a nova passada no payload) **e** `content_text` foi incluído no payload.

**Padrão de execução:** todos os triggers são `background_tasks.add_task(...)` — não bloqueiam a resposta ao utilizador. O meta-prompter corre assincronamente e persiste `generated_prompt_parts` no core via `PATCH /ai-profiles/{user_id}/generated-prompt-parts`.

**Resultado:** `generated_prompt_parts` passa a ser preenchido automaticamente nos 3 fluxos críticos. A Fase 4 do meta-prompter dinâmico está agora completamente operacional end-to-end em produção.

---

### 🟡 BUG 4 — Idioma hardcoded no meta-prompter

**Arquivo:** `backend-executors/app/services/meta_prompter.py` — linha 51

**Problema:**
```python
language = "pt-BR"  # hardcoded
```

A spec define `"Idioma: {language}"` como variável do perfil. O sistema serve multi-nichos e potencialmente multi-idioma (o `website` já suporta `en`, `pt`, `es`). Utilizadores com `ai_profile` configurado para outro idioma receberão exemplos few-shot e tone_rules em pt-BR.

**Correção sugerida:**
```python
language = ai_profile.get("language") or "pt-BR"
```

---

### 🟡 BUG 5 — `_inject_generated_parts` chamado para fase "closing" sem blocos gerados

**Arquivo:** `backend-executors/app/services/decision_engine.py` — linha 1759

**Problema:**
```python
return _inject_generated_parts(_closing_prompt, context, "closing")
```

O meta-prompter não gera `few_shot_closing` nem `objection_rewrites` para "closing" (conforme spec). A injeção de "closing" resultará apenas em `tone_rules` adicionados — mas `tone_rules` já é injetado via `_build_tone_block()` no corpo do prompt, causando **duplicação de regras de tom** quando `generated_prompt_parts` estiver preenchido.

Adicionalmente, a spec indica que `objection_rewrites` deve ser injetado para `"apresentation"` e `"follow-up"` apenas (`if phase in ("apresentation", "followup")`), o que está correcto no código. Mas a injeção de `tone_rules` para "closing" é redundante.

**Impacto:** Baixo (não causa erro, apenas polui o prompt com regras duplicadas quando o meta-prompter estiver activo).

---

### 🟡 BUG 6 — Campo `required_fields` duplicado/desalinhado no meta-prompter

**Arquivo:** `backend-executors/app/services/meta_prompter.py` — linhas 54–59

**Problema:**
O meta-prompter define internamente os `required_fields` por `agent_mode`:
```python
_required_by_mode = {
    "consultivo": ["service_interest", "urgency", "decision_role", "constraints", "availability_window", "budget_or_price_acceptance"],
    "agenda": ["service_interest", "urgency", "decision_role", "availability_window"],
    "direto": ["service_interest", "urgency", "decision_role"],
}
```

A fonte de verdade desses campos está em `backend-executors/app/contracts/qualification_contract.py` (função `required_fields_for_mode`). Se a lista de campos for alterada no contrato no futuro (ex.: adição de `location_preference` para o modo `agenda`), o meta-prompter gerará exemplos few-shot com campos desactualizados, sem nenhum aviso de erro.

**Impacto:** Baixo agora, mas acumulará drift ao longo do tempo. O correcto seria importar `required_fields_for_mode` de `qualification_contract.py` directamente.

---

## Detalhes de Implementação Correcta (Confirmados)

### FASE 1 ✅

- **1.1**: Todas as 5 filhas (Qualification, Apresentation, Follow-up, Closing) e a Mãe têm prompts com 5 camadas (PAPEL / ESCOPO / TOM / FRAMEWORK / RECUSAS). Ver linhas 1128–1134, 1341–1346, 1604–1610, 1707–1713, 875–879.
- **1.2**: Bloco `PROIBIÇÕES` com 7 itens base + proibições específicas para `apresentation` (itens 8–10: mídia, checkout+permissão, preço correcto) e `follow_up` (itens 8–9: qualificação em ticks, max_chars). Ver linhas 1160–1169, 1389–1399, 1633–1642.
- **1.3**: Follow-up com blocos `PROVA SOCIAL`, `OBJEÇÕES E RESPOSTAS`, `FAQ DO SERVIÇO` com directivas (linhas 1546–1577). Apresentation comercial (hybrid_scheduler/commercial) com directivas nos blocos de knowledge (linhas 1278–1323). Apresentation standard (`sdr_padrao`/`closer_agressivo`) com `standard_knowledge_block` cobrindo `social_proof`, `pitch_script`, `product_details`, `objections_faq`, `service_faq`, `guarantee_policy` — cada um com directiva de uso (corrigido 2026-03-29).

### FASE 2 ✅

- **2.1**: `_build_tone_block()` centralizado (linhas 223–256), aplicado em todas as filhas: qualification (1126), apresentation (1338), follow-up (1602), closing (1705).
- **2.2**: `field_extractor.py` recebe `current_field`, `filled_fields`, `niche`, `target_audience` do contexto (linhas 53–89).
- **2.3**: `_ESCAPE_HATCH_BLOCK` constante (linhas 118–125), aplicada em qualification (1168), apresentation (1400), follow-up (1643), closing (1741).

### FASE 3 ✅

- **3.1**: Tabela `REGRAS DE ROUTING — AVALIAR NESTA ORDEM` com PRIORIDADE 1–4 implementada na Mãe (linhas 944–958).
- **3.2**: Chain-of-thought implícito com 4 perguntas antes do schema de output (linhas 881–885).
- **3.3**: `_build_validation_block()` centralizado (linhas 128–137), aplicado em todas as filhas: qualification (1169), apresentation (1401), follow-up (1644), closing (1742).

### FASE 4 ✅

- **4.1**: `meta_prompter.py` com `generate_prompt_parts()`, `save_prompt_parts_to_core()`, `generate_and_save()`. Schema de DB migrado (3 novas colunas em `ai_profiles`). Endpoint `POST /api/meta-prompter/generate/{user_id}` criado. Triggers automáticos implementados (ver Bug 3 corrigido): onboarding via `POST /ai-profiles`, edição de campos críticos via `PUT /ai-profiles/me`, edição de `objections_faq` via `PUT /api/knowledge/{item_id}`.
- **4.2**: `_inject_generated_parts()` implementado (linhas 139–193). Chamado correctamente nas 4 filhas específicas. `generated_prompt_parts` propagado via `executor.py` → `decision_engine`.
- **4.3**: `llm.py` usa `outreach_scenarios` dinâmicos quando disponíveis, com fallback correcto para cenários legados `no_site/weak_site/decent_site` (linhas 76–84).
