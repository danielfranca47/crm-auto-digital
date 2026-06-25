# AI Profile — Documentação de Campos

> Atualizado em: 2026-03-27

---

## Histórico de mudanças de UI

| Data | Evento |
|---|---|
| 2026-03-21 | Diagnóstico inicial — 23 campos no modelo, 20 com UI em `AiProfile.tsx` |
| 2026-03-25 | Atualização anterior (Etapa 8 — follow-up) |
| **2026-03-27** | **Migração para `AgenteConfiguracao.tsx` — novo UX unificado com todos os campos** |

---

## Situação atual da UI (2026-03-27)

A página de configuração do agente passou por uma refatoração de UX. O arquivo `AiProfile.tsx` (UX ruim, todos os campos em cards empilhados) foi **substituído como rota ativa** pelo novo `AgenteConfiguracao.tsx` (UX com drawers/modais, badges de status, organização em camadas).

### Rota ativa
```
/ai-profile  →  AgenteConfiguracao.tsx  (novo UX)
```

`AiProfile.tsx` permanece no código como referência, mas **não está mais acessível via rota**.

### Arquitetura da nova UI

```
AgenteConfiguracao.tsx  (página principal — orquestra tudo)
  ├── CamadaIdentidade.tsx      (① Identidade)
  ├── CamadaQualificacao.tsx    (② Qualificação)
  ├── CamadaPipeline.tsx        (③ Pipeline)
  ├── CamadaConhecimento.tsx    (④ Conhecimento — base de knowledge)
  ├── CamadaApresentacao.tsx    (⑤ Apresentação — condicional: agendadores)
  ├── CamadaOferta.tsx          (⑥ Oferta — condicional: direto/closer)
  └── ConexaoNumero.tsx         (Conexão — WhatsApp)
```

O estado global (`AgentConfig`) vive em `AgenteConfiguracao.tsx` e é passado via props para cada subcomponente. Cada subcomponente recebe `config + onUpdate(partial)` — **nenhum subcomponente chama a API diretamente** (exceto `CamadaConhecimento` que gerencia seu próprio CRUD de knowledge items).

---

## Onde cada campo é armazenado no backend

O `AgentConfig` do frontend mapeia para dois destinos no backend-core:

| Destino | Campos |
|---|---|
| **Colunas diretas de `ai_profiles`** | `name`, `brand_name`, `tone_of_voice`, `agent_mode`, `identity_mode`, `template_key`, `handoff_policy`, `requires_handoff`, `human_in_loop`, `timezone`, `custom_instructions`, `niche`, `target_audience`, `offer_description`, `goals`, `payment_gateway` |
| **JSON `offer_pack`** (coluna única) | Todos os demais — ver tabela completa abaixo |

**Por que `offer_pack`?** O modelo `ai_profiles` no backend-core tem um campo JSON livre chamado `offer_pack`. Campos que não têm coluna dedicada são serializados ali. Isso permite adicionar novos campos no frontend sem alterar o schema do banco.

---

## Contagem de campos (pós-refatoração)

| Camada/grupo | Campos no `AgentConfig` | Armazenamento |
|---|---|---|
| Identidade base | 11 | Colunas diretas |
| Contexto de abertura | 5 | `offer_pack` |
| Qualificação contexto | 6 | Colunas diretas + `offer_pack` |
| Qualificação avançada | 3 | `offer_pack` |
| Pipeline/comportamento | 12 | `offer_pack` |
| Follow-up avançado | 4 | `offer_pack` |
| Apresentação/agendamento | 7 | `offer_pack` |
| Oferta e pagamento | 8 | `offer_pack` (mídia/detalhes) + colunas diretas (`payment_gateway`, `payment_webhook_url`, `payment_webhook_secret`) |
| **Total** | **~56** | — |

---

## Campos completos — Tabela

### Camada 1 — Identidade

| Campo | UI | Armazenamento | Status no pipeline |
|---|---|---|---|
| `name` | ✅ Input · Drawer | Coluna direta | Metadado |
| `brand_name` | ✅ Input · Drawer | Coluna direta | Metadado |
| `niche` | ✅ Input · Drawer | Coluna direta | Metadado |
| `timezone` | ✅ Select · Drawer | Coluna direta | Metadado (não usado em lógica) |
| `tone_of_voice` | ✅ Input · Drawer | Coluna direta | Metadado — ver nota¹ |
| `goals` | ✅ Textarea · Drawer | Coluna direta | Metadado / futuro |
| `template_key` | ✅ Modal radio | Coluna direta | **Ativo** — seleciona playbook |
| `identity_mode` | ✅ Modal radio | Coluna direta | Parcial — registrado no HandoffLog |
| `agent_mode` | ✅ Modal radio | Coluna direta | **Ativo** — altera parâmetros do orquestrador |
| `handoff_policy` | ✅ Select · Drawer (condicional²) | Coluna direta | Futuro |
| `handoff_custom_text` | ✅ Textarea · Drawer (condicional²) | `offer_pack` | Futuro |
| `requires_handoff` | (interno, não exibido na nova UI) | Coluna direta | Parcial |
| `human_in_loop` | (interno, não exibido na nova UI) | Coluna direta | Parcial |
| `custom_instructions` | ✅ Textarea · Modal (regenerável) | Coluna direta | Metadado / futuro |

> ¹ **Nota `tone_of_voice`:** existe no perfil mas o LLM recebe `tone` via `processor.py` (Assistente IA), que não lê este campo. Desconexão conhecida.
> ² **Condicional:** só visível quando `identity_mode ≠ 'virtual_assistant'`.

### Camada 1 — Contexto de abertura (novos em 2026-03-27)

| Campo | UI | Armazenamento | Status |
|---|---|---|---|
| `origin_inbound_opener` | ✅ Textarea · Drawer | `offer_pack` | Metadado / futuro |
| `origin_outbound_opener` | ✅ Textarea · Drawer | `offer_pack` | Metadado / futuro |
| `warming_social_proof` | ✅ Textarea · Drawer | `offer_pack` | Metadado / futuro |
| `warming_session_preview` | ✅ Textarea · Drawer | `offer_pack` | Metadado / futuro |

### Camada 2 — Qualificação (contexto de negócio)

| Campo | UI | Armazenamento | Status |
|---|---|---|---|
| `offer_description` | ✅ Textarea · Drawer | Coluna direta | Metadado |
| `target_audience` | ✅ Textarea · Drawer | Coluna direta | Metadado |
| `ticket_range` | ✅ Select · Drawer | `offer_pack` | Metadado |
| `main_pain` | ✅ Textarea · Drawer | `offer_pack` | Metadado |
| `main_objection` | ✅ Textarea · Drawer | `offer_pack` | Metadado |
| `f1_questions` | ✅ Lista editável · Modal | `offer_pack` | Metadado / futuro |
| `f2_questions` | ✅ Lista editável · Modal | `offer_pack` | Metadado / futuro |
| `f3_questions` | ✅ Lista editável · Modal | `offer_pack` | Metadado / futuro |

### Camada 2 — Qualificação avançada (novos em 2026-03-27)

| Campo | UI | Armazenamento | Status |
|---|---|---|---|
| `qualification_score_threshold` | ✅ Slider 0–12 · Drawer | `offer_pack` | Metadado / futuro |
| `nurture_vs_discard_rule` | ✅ Toggle inline | `offer_pack` | Metadado / futuro |
| `buying_signal_keywords` | ✅ Tag input · Modal (condicional³) | `offer_pack` | Metadado / futuro |

> ³ **Condicional:** visível apenas quando `agent_mode ∈ {sdr_scheduler, agenda}` ou `template_key ∈ {sdr_padrao, hybrid_scheduler}`.

### Camada 3 — Pipeline e comportamento

| Campo | UI | Armazenamento | Status |
|---|---|---|---|
| `media_fallback` | ✅ Select · Drawer | `offer_pack` | Metadado / futuro |
| `media_fallback_msg` | ✅ Textarea · Drawer | `offer_pack` | Metadado / futuro |
| `opt_out_keywords` | ✅ Tag input · Modal | `offer_pack` | **Ativo** — detectado no guardrail de inbound |
| `opt_out_disable` | ✅ Toggle · Modal | `offer_pack` | Metadado / futuro |
| `opt_out_notify` | ✅ Toggle · Modal | `offer_pack` | Metadado / futuro |
| `opt_out_confirm` | ✅ Toggle · Modal | `offer_pack` | Metadado / futuro |
| `opt_out_confirm_msg` | ✅ Textarea · Modal | `offer_pack` | Metadado / futuro |
| `lgpd_mode` | ✅ Radio · Modal | `offer_pack` | Metadado / futuro |
| `lgpd_msg` | ✅ Textarea · Modal | `offer_pack` | Metadado / futuro |
| `reactivation_mode` | ✅ Radio · Modal | `offer_pack` | Metadado / futuro |
| `reactivation_msg` | ✅ Textarea · Modal | `offer_pack` | Metadado / futuro |
| `interval_min` | ✅ Slider · Drawer | `offer_pack` | Metadado / futuro |
| `interval_max` | ✅ Slider · Drawer | `offer_pack` | Metadado / futuro |
| `daily_limit` | ✅ Slider · Drawer | `offer_pack` | Metadado / futuro |

### Camada 3 — Follow-up avançado (novos em 2026-03-27)

| Campo | UI | Armazenamento | Status |
|---|---|---|---|
| `followup_max_attempts` | ✅ Slider 1–10 · Drawer | `offer_pack` | Metadado / futuro |
| `followup_first_offset` | ✅ Slider em minutos · Drawer | `offer_pack` | Metadado / futuro |
| `followup_cadence` | ✅ Input texto (ex: `60,1440,4320`) · Drawer | `offer_pack` | Metadado / futuro |
| `followup_allowed_hours` | ✅ Input texto (`HH:MM-HH:MM`) · Drawer | `offer_pack` | Metadado / futuro |

### Camada 4 — Base de conhecimento

Gerenciada separadamente via `api.crm` (não faz parte do `AgentConfig`).

| Operação | Endpoint | Arquivo de UI |
|---|---|---|
| Listar | `GET /knowledge` | `CamadaConhecimento.tsx` |
| Criar (texto) | `POST /knowledge/manual` | `CamadaConhecimento.tsx` |
| Criar (arquivo) | `POST /knowledge/upload` | `CamadaConhecimento.tsx` |
| Editar | `PUT /knowledge/:id` | `CamadaConhecimento.tsx` |
| Remover | `DELETE /knowledge/:id` | `CamadaConhecimento.tsx` |

### Camada 5 — Apresentação e agendamento (novos em 2026-03-27)

Visível apenas quando `agent_mode ∉ {direto, closer}`.

| Campo | UI | Armazenamento | Status |
|---|---|---|---|
| `appointment_reminder_h1` | ✅ Slider · Drawer | `offer_pack` | Metadado / futuro |
| `appointment_reminder_h2` | ✅ Slider · Drawer | `offer_pack` | Metadado / futuro |
| `briefing_enabled` | ✅ Toggle · Drawer | `offer_pack` | Metadado / futuro |
| `briefing_channel` | ✅ Select · Drawer (condicional) | `offer_pack` | Metadado / futuro |
| `briefing_lead_time` | ✅ Slider · Drawer (condicional) | `offer_pack` | Metadado / futuro |
| `operator_whatsapp` | ✅ Input tel · Drawer (condicional) | `offer_pack` | Metadado / futuro |
| `calendar_integration` | ✅ Radio · Modal | `offer_pack` | Metadado / futuro |

### Camada 6 — Oferta e pagamento (novos em 2026-03-27)

Visível apenas quando `agent_mode ∈ {direto, closer}`.

| Campo | UI | Armazenamento | Status |
|---|---|---|---|
| `offer_media_url` | ✅ Input URL · Drawer | `offer_pack.media_url` | Metadado / futuro |
| `offer_media_type` | ✅ Select · Drawer | `offer_pack.media_type` | Metadado / futuro |
| `offer_anchor_price` | ✅ Input · Drawer | `offer_pack.anchor_price` | Metadado / futuro |
| `offer_guarantee_text` | ✅ Textarea · Drawer | `offer_pack.guarantee_text` | Metadado / futuro |
| `offer_upsell_message` | ✅ Textarea · Drawer | `offer_pack.upsell_message` | Metadado / futuro |
| `payment_gateway` | ✅ Radio · Modal | Coluna direta | Metadado / futuro |
| `payment_webhook_url` | ✅ Read-only + copy | Coluna direta (gerado pelo servidor) | Metadado / futuro |
| `payment_webhook_secret` | ✅ Password + reveal + regenerar | Coluna direta (gerado pelo servidor) | Metadado / futuro |

> **Nota `payment_webhook_url` e `payment_webhook_secret`:** são gerados pelo backend ao primeiro `PUT /ai-profiles/me` com `payment_gateway` preenchido, ou via `POST /ai-profiles/me/regenerate-webhook-secret`. O frontend não os envia no save — apenas lê e exibe.

---

## Fluxo de dados (atualizado)

```
Frontend (AgenteConfiguracao.tsx)
  └─► api.agente.getConfig()
        └─► GET /ai-profiles/me  →  backend-core
              └─► retorna perfil completo (colunas diretas + offer_pack)
                    └─► api.ts mapeia para AgentConfig flat

  └─► api.agente.saveConfig(config)
        └─► PUT /ai-profiles/me  →  backend-core
              ├─ campos diretos: name, brand_name, agent_mode, ...
              └─ offer_pack: { ticket_range, f1_questions, opt_out_keywords, ... }

Frontend (CamadaConhecimento.tsx) — independente
  └─► api.crm.getKnowledgeList()   →  GET  /knowledge
  └─► api.crm.createKnowledgeManual()  →  POST /knowledge/manual
  └─► api.crm.uploadKnowledgeFile()    →  POST /knowledge/upload
  └─► api.crm.updateKnowledge()        →  PUT  /knowledge/:id
  └─► api.crm.deleteKnowledge()        →  DELETE /knowledge/:id

Webhook inbound WhatsApp
  └─► backend-crm / core_client.py
        └─► GET /ai-profiles/resolve?user_id=X  →  backend-core
              └─► orchestrator.py
                    ├─ _normalize_agent_mode_for_bundle()  ← usa: agent_mode, template_key
                    ├─ _resolve_presentation_contract()    ← usa: presentation_variant, hybrid_flow_style, offer_pack
                    └─ apply_mode_overrides()              ← usa: agent_mode normalizado
                          └─► ContextBundle → Playbook → LLM
```

---

## Campos ativos no pipeline de IA

De todos os ~56 campos do `AgentConfig`, apenas estes afetam ativamente o comportamento do bot hoje:

| Campo | Efeito real |
|---|---|
| `template_key` | Seleciona qual playbook é carregado em `services/ai_playbooks/` |
| `agent_mode` | Define `max_chars`, `qualification_depth`, `cta_every_turn`, `must_handoff_on_high_intent` no orquestrador |
| `presentation_variant` | Resolvido internamente no orquestrador (não editável na UI) |
| `opt_out_keywords` | Verificados no guardrail de inbound antes do LLM |

Os demais campos são **metadados configurados e salvos**, mas ainda não consumidos ativamente pelo pipeline de IA — estão preparados para implementação futura de features como follow-up automático, dossiê pré-reunião, lembretes, guardrail de score, etc.

---

## Arquivos de referência

| Arquivo | Responsabilidade |
|---|---|
| [frontend-crm/src/pages/AgenteConfiguracao.tsx](../frontend-crm/src/pages/AgenteConfiguracao.tsx) | Página principal de configuração (rota `/ai-profile`) — orquestra todas as camadas |
| [frontend-crm/src/pages/AiProfile.tsx](../frontend-crm/src/pages/AiProfile.tsx) | Página antiga — mantida como referência, sem rota ativa |
| [frontend-crm/src/components/agente/CamadaIdentidade.tsx](../frontend-crm/src/components/agente/CamadaIdentidade.tsx) | UI da Camada 1 |
| [frontend-crm/src/components/agente/CamadaQualificacao.tsx](../frontend-crm/src/components/agente/CamadaQualificacao.tsx) | UI da Camada 2 |
| [frontend-crm/src/components/agente/CamadaPipeline.tsx](../frontend-crm/src/components/agente/CamadaPipeline.tsx) | UI da Camada 3 |
| [frontend-crm/src/components/agente/CamadaConhecimento.tsx](../frontend-crm/src/components/agente/CamadaConhecimento.tsx) | UI da Camada 4 — CRUD de knowledge items |
| [frontend-crm/src/components/agente/CamadaApresentacao.tsx](../frontend-crm/src/components/agente/CamadaApresentacao.tsx) | UI da Camada 5 — agendamento (condicional) |
| [frontend-crm/src/components/agente/CamadaOferta.tsx](../frontend-crm/src/components/agente/CamadaOferta.tsx) | UI da Camada 6 — oferta e pagamento (condicional) |
| [frontend-crm/src/components/agente/ConexaoNumero.tsx](../frontend-crm/src/components/agente/ConexaoNumero.tsx) | UI de conexão WhatsApp |
| [frontend-crm/src/types/agente.ts](../frontend-crm/src/types/agente.ts) | Tipos `AgentConfig`, `DEFAULT_AGENT_CONFIG` e todos os labels |
| [frontend-crm/src/services/api.ts](../frontend-crm/src/services/api.ts) | `api.agente.getConfig()` e `api.agente.saveConfig()` — mapeamento frontend↔backend |
| [backend-core/app/models/ai_profile.py](../backend-core/app/models/ai_profile.py) | Model SQLAlchemy |
| [backend-core/app/api/ai_profiles.py](../backend-core/app/api/ai_profiles.py) | Endpoints REST |
| [backend-crm/services/ai_orchestrator/orchestrator.py](../backend-crm/services/ai_orchestrator/orchestrator.py) | Consumo real dos campos no pipeline |
