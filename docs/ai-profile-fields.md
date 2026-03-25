# AI Profile — Documentação de Campos

> Atualizado em: 2026-03-25

---

## Contagem de campos

| Grupo | Campos | UI? |
|-------|--------|-----|
| Identidade/comportamento (pré-Etapa 8) | 19 | 16 com UI · 3 backend-only |
| Follow-up (Etapa 8) | 4 | 4 com UI |
| **Total** | **23** | **20 com UI · 3 sem UI** |

**Os 3 sem UI** (existem no modelo mas não no formulário):
`presentation_variant`, `hybrid_flow_style`, `offer_pack`

**Os 2 omitidos no diagnóstico** que existem no modelo e na UI:
`name` (nome do agente) e `timezone` (fuso horário)

---

> Gerado em: 2026-03-21
> Referência: `frontend-crm/src/pages/AiProfile.tsx`, `backend-core/app/models/ai_profile.py`, `backend-crm/services/ai_orchestrator/orchestrator.py`

---

## Visão geral

O `ai_profile` é um registro único por usuário (1:1) armazenado no `backend-core`. Ele é buscado pelo `backend-crm` via `core_client.py` e injetado no `ContextBundle` passado ao orquestrador de IA. A maioria dos campos descritivos é armazenada mas **não consumida ativamente** na geração de respostas — o perfil funciona como configuração de template, não como instrução direta ao LLM.

---

## Campos — Tabela completa

| Campo | Tipo | Frontend | Backend-core | Backend-crm (lógica ativa) | Status |
|---|---|---|---|---|---|
| `template_key` | string | ✅ Dropdown obrigatório | ✅ NOT NULL | ✅ Seleciona o playbook | **Ativo** |
| `agent_mode` | enum | ✅ Select | ✅ nullable | ✅ Normalizado no orquestrador, infere `presentation_variant` | **Ativo** |
| `presentation_variant` | enum | ❌ Não exibido | ✅ nullable | ✅ Resolvido em `_resolve_presentation_contract()` | **Ativo (backend-only)** |
| `hybrid_flow_style` | enum | ❌ Não exibido | ✅ nullable | ✅ Passado no ContextBundle | **Ativo (backend-only)** |
| `offer_pack` | JSON | ❌ Não exibido | ✅ nullable | ✅ Parseado e passado ao playbook | **Ativo (backend-only)** |
| `requires_handoff` | boolean | ✅ Toggle | ✅ nullable | ✅ Controla visibilidade de campos no form | **Parcialmente ativo** |
| `human_in_loop` | boolean | ✅ Toggle | ✅ nullable | ✅ Controla visibilidade de campos no form | **Parcialmente ativo** |
| `identity_mode` | enum | ✅ Select (condicional) | ✅ nullable | ⚠️ Apenas logado em `HandoffRequestedLog` | **Metadado / futuro** |
| `handoff_policy` | enum | ✅ Select (condicional) | ✅ nullable | ❌ Não aplicado ativamente no pipeline | **Metadado / futuro** |
| `handoff_custom_text` | string | ✅ Textarea (condicional) | ✅ nullable | ❌ Não utilizado | **Metadado / futuro** |
| `name` | string | ✅ Input obrigatório | ✅ NOT NULL | ❌ Não consumido na lógica | **Metadado** |
| `brand_name` | string | ✅ Input obrigatório | ✅ NOT NULL | ❌ Não consumido na lógica | **Metadado** |
| `tone_of_voice` | string | ✅ Select/Input | ✅ NOT NULL | ❌ Não consumido na lógica de LLM | **Metadado** |
| `niche` | string | ✅ Input | ✅ NOT NULL | ❌ Não consumido na lógica | **Metadado** |
| `target_audience` | string | ✅ Input | ✅ NOT NULL | ❌ Não consumido na lógica | **Metadado** |
| `offer_description` | string | ✅ Textarea | ✅ NOT NULL | ❌ Não consumido na lógica | **Metadado** |
| `goals` | string | ✅ Textarea | ✅ NOT NULL | ❌ Não consumido na lógica | **Metadado** |
| `custom_instructions` | string | ✅ Textarea | ✅ nullable | ❌ Não consumido na lógica | **Metadado / futuro** |
| `timezone` | string | ✅ Select | ✅ nullable, default UTC | ❌ Não consumido na lógica | **Metadado** |

---

## Campos ativos (afetam comportamento do bot)

### `template_key`
- **Frontend:** dropdown com 4 templates pré-definidos (`sdr_padrao`, `consultor_especialista`, `closer_agressivo`, `hybrid_scheduler`)
- **Uso:** seleciona qual playbook será carregado em `services/ai_playbooks/`
- **Fallback:** se `agent_mode` não está definido, o orquestrador infere o modo a partir do `template_key`

### `agent_mode`
- **Valores válidos:** `consultivo`, `agenda`, `direto`, `sdr_scheduler` (legacy → mapeado para `agenda`), `closer` (legacy → mapeado para `direto`)
- **Uso em `orchestrator.py`:** normalizado em `_normalize_agent_mode_for_bundle()` e aplicado via `apply_mode_overrides()`:
  - `consultivo` → `max_chars=700`, `qualification_depth="high"`, `max_questions_per_turn=1`, `must_handoff_on_high_intent=True`
  - `agenda` → `max_chars=350`, `qualification_depth="medium"`, campos obrigatórios de captação
  - `direto` → `max_chars=300`, `qualification_depth="low"`, `cta_every_turn=True`

### `presentation_variant` / `hybrid_flow_style` / `offer_pack`
- **Não exibidos no frontend** — configurados apenas via backend ou futuro painel avançado
- **Uso:** resolvidos em `_resolve_presentation_contract()`. Se `presentation_variant` não está definido no perfil, é inferido do `agent_mode` (`direto` → `sales`, `agenda`/`consultivo` → `scheduler`)
- **`offer_pack`:** JSON com regras avançadas de oferta, parseado pelo orquestrador

---

## Campos parcialmente ativos (afetam UI, não o pipeline de IA)

### `requires_handoff` / `human_in_loop`
- Controlam a visibilidade dos campos de handoff no formulário frontend
- **Não aplicados** como guardrails no fluxo de resposta do bot atualmente

### `identity_mode`
- **Valores:** `virtual_assistant`, `human_agent`, `user_clone`
- Registrado em `HandoffRequestedLog` quando ocorre um handoff
- **Não altera** o comportamento da resposta gerada

### `handoff_policy` / `handoff_custom_text`
- Configurados e salvos, mas **não consumidos** no pipeline de inbound atual
- Preparados para implementação futura de handoff automático

---

## Campos metadado (salvos, não consumidos pelo bot)

Esses campos são armazenados no perfil e retornados pelo `GET /ai-profiles/me`, mas o `backend-crm` não os usa ativamente na geração de respostas:

| Campo | Observação |
|---|---|
| `name` | Nome do agente — exibido apenas no frontend |
| `brand_name` | Nome da empresa — não injetado no prompt LLM |
| `tone_of_voice` | Tom de voz — **o `tone` usado pelo LLM vem de outro parâmetro** (UI do Assistente IA), não deste campo |
| `niche` | Nicho de negócio — metadado |
| `target_audience` | Público-alvo — metadado |
| `offer_description` | Descrição da oferta — metadado (não injeta no playbook) |
| `goals` | Prioridades operacionais — metadado |
| `custom_instructions` | Instruções customizadas — campo reservado para uso futuro no prompt |
| `timezone` | Fuso horário — armazenado mas não utilizado em agendamentos ou lógica de horário |

> **Nota sobre `tone_of_voice`:** o campo existe no perfil mas o `llm.py` recebe `tone` como parâmetro vindo do `processor.py` (Assistente IA), que por sua vez não lê `ai_profile.tone_of_voice`. Há desconexão entre a configuração e o uso real.

---

## Fluxo de dados resumido

```
Frontend (AiProfile.tsx)
  └─► POST/PUT /ai-profiles  →  backend-core (salva em ai_profiles table)

Webhook inbound WhatsApp
  └─► backend-crm/core_client.py
        └─► GET /ai-profiles/resolve?user_id=X  →  backend-core
              └─► orchestrator.py
                    ├─ _normalize_agent_mode_for_bundle()  ← usa: agent_mode, template_key
                    ├─ _resolve_presentation_contract()    ← usa: presentation_variant, hybrid_flow_style, offer_pack
                    └─ apply_mode_overrides()              ← usa: agent_mode normalizado
                          └─► ContextBundle → Playbook → LLM
```

---

## Arquivos de referência

| Arquivo | Responsabilidade |
|---|---|
| [frontend-crm/src/pages/AiProfile.tsx](../frontend-crm/src/pages/AiProfile.tsx) | Formulário de configuração do perfil |
| [frontend-crm/src/services/api.ts](../frontend-crm/src/services/api.ts) | Tipo `AiProfilePayload` e chamadas HTTP |
| [backend-core/app/models/ai_profile.py](../backend-core/app/models/ai_profile.py) | Model SQLAlchemy |
| [backend-core/app/api/ai_profiles.py](../backend-core/app/api/ai_profiles.py) | Endpoints REST + enums de validação |
| [backend-crm/core_client.py](../backend-crm/core_client.py) | `fetch_core_ai_profile()` e `fetch_core_ai_profile_resolve()` |
| [backend-crm/services/ai_orchestrator/orchestrator.py](../backend-crm/services/ai_orchestrator/orchestrator.py) | Consumo real dos campos no pipeline |
