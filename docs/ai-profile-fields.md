# AI Profile — Documentação de Campos

> Atualizado em: 2026-06-28

---

## Situação atual da UI

### Rota ativa

```
/ai-profile  →  frontend-crm/src/pages/AiProfile.tsx
```

Não existe (e nunca existiu como rota ativa) um arquivo `AgenteConfiguracao.tsx`. `AiProfile.tsx`
é e sempre foi a página real — qualquer doc anterior que afirme o contrário estava errada.

### Painéis (abas) e componentes

```
AiProfile.tsx  (página principal — orquestra tudo, guarda PanelId ativo)
  ├── overview          → PainelResumo (inline em AiProfile.tsx)
  ├── c1  · Identidade   → CamadaIdentidade.tsx
  ├── c2  · Qualificação → CamadaQualificacao.tsx
  ├── c3  · Pipeline     → CamadaPipeline.tsx
  ├── c4  · Conhecimento → CamadaConhecimento.tsx (+ CamadaConhecimentoWizard.tsx)
  ├── c5  · Apresentação → CamadaApresentacao.tsx   (condicional: agent_mode ∉ {direto, closer})
  ├── c6  · Oferta       → CamadaOferta.tsx         (condicional: agent_mode ∈ {direto, closer})
  ├── fluxo · Fluxo de Venda → CamadaFluxoVenda.tsx
  ├── followup · Follow-up  → CamadaFollowup.tsx
  └── conexao            → ConexaoNumero.tsx
```

`c5`/`c6` são mutuamente exclusivos — só uma das duas abas aparece, dependendo de `agent_mode`.

O estado global (`AgentConfig`) vive em `AiProfile.tsx` e é passado via props para cada
subcomponente (`config` + `onUpdate(partial)`). Nenhum subcomponente chama a API diretamente,
exceto `CamadaConhecimento` (CRUD próprio de knowledge items) e `ConexaoNumero` (gerencia
conexão WhatsApp via API própria).

### Salvamento e feedback visual

Um único `handleSave()` (`AiProfile.tsx`) é compartilhado por todos os painéis — chama
`api.agente.saveConfig(config)` com o objeto `config` completo (não por campo). Qualquer
modal/drawer de um painel (ex.: `ModalAppointmentMode` em `CamadaApresentacao.tsx`) só altera
o estado local via `onUpdate(partial)`; a persistência real só ocorre quando o utilizador
clica no botão "Salvar"/"Salvar <Painel>" do banner "Editando..." (`isDirty=true`).

Feedback via toast (`useToast` de `@/hooks/use-toast`, mesmo padrão usado em outras ~27 telas
do app): sucesso dispara `toast({ title: "Configuração salva" })`; falha dispara
`toast({ title: "Erro ao salvar", variant: "destructive" })`. O state `error` (separado) é
usado **só** para a falha de carregamento inicial (`GET` na montagem do componente) — esse
caso bloqueia a tela inteira porque genuinamente não há config para mostrar; falha de
salvamento não bloqueia mais a tela (corrigido em 2026-06-28 — antes, qualquer erro de rede no
save substituía toda a tela de configuração por um bloco de erro sem retry).

---

## Onde cada campo é armazenado no backend

O model `AIProfile` (`backend-core/app/models/ai_profile.py`) tem ~55 colunas diretas mais uma
coluna JSON livre chamada `offer_pack`, onde o frontend serializa campos "extras". A divisão
entre os dois destinos é decidida pelo frontend (`frontend-crm/src/services/api.ts`), não pelo
schema do backend — por isso nem sempre bate com a intuição (ver discrepâncias abaixo).

**Campos que vão dentro do JSON `offer_pack`** (confirmado em `api.ts: saveConfig()`):

```
handoff_custom_text, origin_inbound_opener, origin_outbound_opener,
warming_social_proof, warming_session_preview,
ticket_range, main_pain, main_objection, f1_questions, f2_questions, f3_questions,
qualification_score_threshold, buying_signal_keywords, qualification_required_fields,
media_fallback, media_fallback_msg, opt_out_keywords, opt_out_disable, opt_out_notify,
opt_out_confirm, opt_out_confirm_msg, lgpd_mode, lgpd_msg, reactivation_mode, reactivation_msg,
daily_limit, interval_min, interval_max,
calendar_integration,
media_url (← offer_media_url), media_type (← offer_media_type), anchor_price (← offer_anchor_price),
guarantee_text (← offer_guarantee_text), upsell_message (← offer_upsell_message)
```

Todos os demais campos de `AgentConfig` são colunas diretas em `ai_profiles`.

### Discrepâncias conhecidas (vale a pena saber antes de tocar nesses campos)

| Campo | O que acontece |
|---|---|
| `nurture_vs_discard_rule` | Frontend tipa como `boolean` (`AgentConfig`), mas a coluna no backend é `String` (`"nurture"` / `"discard"`, default `"discard"`) e o schema Pydantic em `ai_profiles.py` espera `Optional[str]`. O frontend envia um `true`/`false` JS direto nesse campo — não há conversão boolean↔string visível em `api.ts`. Verificar antes de confiar neste campo em lógica de negócio nova. |
| `qualification_required_fields` | Campo legado (pré-`qualification_fields`). É escrito **nas duas formas** — como coluna direta e dentro de `offer_pack` — simultaneamente, por compatibilidade durante a transição. |
| `calendar_integration` | Tem coluna própria em `ai_profiles` (`server_default="none"`), mas o frontend só lê/escreve via `offer_pack.calendar_integration`. A coluna direta parece ser um resquício não usado pelo fluxo atual. |
| `availability_schedule` | Escrito por **duas UIs diferentes com formatos diferentes**: em Camada 3 · Pipeline (`CamadaPipeline.tsx`) é editado via drawer estruturado dia-a-dia e serializado como JSON (`parseCustomSchedule`/`serializeCustomSchedule`); em Camada 5 · Apresentação (`CamadaApresentacao.tsx`) é editado como texto livre num textarea ("Seg-Sex: 14h, 16h..."). As duas escrevem no mesmo campo string — a última gravação vence. Não investigado a fundo se isso é intencional (conceitos diferentes que acabaram compartilhando o nome do campo) ou um bug de sobreposição. |
| `payment_webhook_url` | Não é uma coluna — é uma `@property` computada no model (`payment_webhook_url()`), montada a partir de `payment_gateway` + `payment_webhook_secret` + `CRM_PUBLIC_BASE_URL`. |

---

## Campos por camada

### Camada 1 — Identidade (`CamadaIdentidade.tsx`)

| Campo | Armazenamento | Observação |
|---|---|---|
| `name` | Coluna direta | |
| `brand_name` | Coluna direta | |
| `niche` | Coluna direta | Apesar do nome sugerir "Qualificação", é editado aqui |
| `goals` | Coluna direta | Editado aqui, não em Qualificação |
| `tone_of_voice` | Coluna direta | LLM recebe `tone` via `processor.py` (Assistente IA), que não lê este campo — desconexão conhecida |
| `timezone` | Coluna direta | Metadado, não usado em lógica |
| `template_key` | Coluna direta | **Ativo** — seleciona playbook em `services/ai_playbooks/` |
| `identity_mode` | Coluna direta | Parcial — registrado no HandoffLog |
| `agent_mode` | Coluna direta | **Ativo** — altera parâmetros do orquestrador (`max_chars`, `qualification_depth`, etc.) |
| `response_style` | Coluna direta | |
| `handoff_policy` | Coluna direta (condicional¹) | |
| `handoff_custom_text` | `offer_pack` (condicional¹) | |
| `requires_handoff` | Coluna direta (interno, não exibido) | |
| `human_in_loop` | Coluna direta (interno, não exibido) | |
| `custom_instructions` | Coluna direta | Editável via modal regenerável por IA |
| `origin_inbound_opener` | `offer_pack` | |
| `origin_outbound_opener` | `offer_pack` | |
| `warming_social_proof` | `offer_pack` | |
| `warming_session_preview` | `offer_pack` | |
| `custom_variables` | Coluna direta (JSON) | Editor de variáveis personalizadas — também aparece em Pipeline e Oferta (componente reutilizado) |

> ¹ **Condicional:** só visível quando `identity_mode ≠ 'virtual_assistant'`.

### Camada 2 — Qualificação (`CamadaQualificacao.tsx`)

| Campo | Armazenamento | Observação |
|---|---|---|
| `offer_description` | Coluna direta | |
| `target_audience` | Coluna direta | |
| `ticket_range` | `offer_pack` | |
| `main_pain` | `offer_pack` | |
| `main_objection` | `offer_pack` | |
| `f1_questions` / `f2_questions` / `f3_questions` | `offer_pack` | Listas editáveis em modal — usadas só no fluxo SDR |
| `qualification_fields` | Coluna direta (JSON) | Contrato unificado (substitui f1/f2/f3 + `qualification_required_fields` conceitualmente) — campo por campo com `mode: required\|optional\|off` |
| `qualification_required_fields` | Coluna direta + `offer_pack` (duplicado) | Legado — derivado de `qualification_fields` ao salvar; ver discrepância acima |
| `qualification_score_threshold` | `offer_pack` | Slider 0–12 |
| `buying_signal_keywords` | `offer_pack` | Tag input · modal (condicional²) |

> ² **Condicional:** visível apenas quando `agent_mode ∈ {sdr_scheduler, agenda}` ou
> `template_key ∈ {sdr_padrao, hybrid_scheduler}`.

### Camada 3 — Pipeline (`CamadaPipeline.tsx`)

| Campo | Armazenamento | Observação |
|---|---|---|
| `media_fallback` / `media_fallback_msg` | `offer_pack` | |
| `opt_out_keywords` | `offer_pack` | **Ativo** — verificado no guardrail de inbound antes do LLM |
| `opt_out_disable` / `opt_out_notify` / `opt_out_confirm` / `opt_out_confirm_msg` | `offer_pack` | |
| `lgpd_mode` / `lgpd_msg` | `offer_pack` | |
| `reactivation_mode` / `reactivation_msg` | `offer_pack` | |
| `daily_limit` / `interval_min` / `interval_max` | `offer_pack` | |
| `first_reply_delay_min_seconds` / `first_reply_delay_max_seconds` | Coluna direta | |
| `reply_delay_min_seconds` / `reply_delay_max_seconds` | Coluna direta | |
| `multi_message_buffer_seconds` | Coluna direta | |
| `audio_transcription_enabled` | Coluna direta | |
| `availability_mode` / `availability_schedule` | Coluna direta | Drawer "Horário de trabalho" — ver discrepância de `availability_schedule` acima |
| `custom_variables` | Coluna direta (JSON) | Componente reutilizado (ver Camada 1) |

### Camada 4 — Conhecimento (`CamadaConhecimento.tsx`)

Gerenciada separadamente via `api.crm` — não faz parte do payload de `AgentConfig` (com exceção
de `niche`, `target_audience`, `offer_description`, lidos apenas como preview de contexto,
read-only).

| Operação | Endpoint |
|---|---|
| Listar | `GET /knowledge` |
| Criar (texto) | `POST /knowledge/manual` |
| Criar (arquivo) | `POST /knowledge/upload` |
| Editar | `PUT /knowledge/:id` |
| Remover | `DELETE /knowledge/:id` |

### Camada 5 — Apresentação (`CamadaApresentacao.tsx`, condicional: `agent_mode ∉ {direto, closer}`)

| Campo | Armazenamento | Observação |
|---|---|---|
| `briefing_enabled` / `briefing_channel` / `briefing_lead_time` | Coluna direta | |
| `operator_whatsapp` | Coluna direta | |
| `appointment_mode` | Coluna direta | `"exploratory"` (padrão) ou `"commercial"`; ao salvar, `presentation_variant` é atualizado em conjunto (`commercial→sales`, `exploratory→scheduler`) — controla também o bloco "MODO COMERCIAL" da filha de apresentação (`decision_engine.py`). Corrigido em 2026-06-27: até então a UI gravava o valor dentro de `offer_pack` (nunca lido pelo decision engine), tornando o toggle um no-op |
| `calendar_integration` | `offer_pack` — ver discrepância acima | |
| `scheduling_offer_style` | Coluna direta | |
| `meeting_management_enabled` | Coluna direta | |
| `availability_schedule` | Coluna direta | Editado aqui como texto livre — ver discrepância acima |
| `default_session_duration_minutes` | Coluna direta | Card "Duração da sessão" (slider 15–180 min) — usada pela IA ao confirmar agendamento quando não há tabela de serviços com duração mais específica; ver [`agenda.md`](architecture/agenda.md#duração-da-sessão-fixa-vs-por-serviço) |

### Camada 6 — Oferta (`CamadaOferta.tsx`, condicional: `agent_mode ∈ {direto, closer}`)

| Campo | Armazenamento | Observação |
|---|---|---|
| `offer_media_url` / `offer_media_type` | `offer_pack.media_url` / `offer_pack.media_type` | |
| `offer_anchor_price` | `offer_pack.anchor_price` | |
| `offer_guarantee_text` | `offer_pack.guarantee_text` | |
| `offer_upsell_message` | `offer_pack.upsell_message` | |
| `payment_gateway` | Coluna direta | |
| `payment_webhook_url` | `@property` computada (não é coluna) | Read-only + copy — backend gera a partir de `payment_gateway` + `payment_webhook_secret` |
| `payment_webhook_secret` | Coluna direta (gerada pelo servidor) | Password + reveal + regenerar via `POST /ai-profiles/me/regenerate-webhook-secret` |
| `custom_variables` | Coluna direta (JSON) | Componente reutilizado (ver Camada 1) |

> O frontend não envia `payment_webhook_url`/`payment_webhook_secret` no save — apenas lê e exibe.

### Fluxo de Venda (`CamadaFluxoVenda.tsx`)

| Campo | Armazenamento | Observação |
|---|---|---|
| `sales_flow` | Coluna direta (JSON) | Estrutura de fases/blocos do fluxo de venda — schema completo documentado em [`docs/architecture/sales-flow.md`](architecture/sales-flow.md) |

A camada também lê (sem editar) `agent_mode` e `qualification_fields` para contextualizar as
regras exibidas.

### Follow-up (`CamadaFollowup.tsx`)

Camada dedicada desde 2026-06-25 (M3 do roadmap de follow-up — ver
[`docs/architecture/followup.md`](architecture/followup.md) para a arquitetura completa do
motor de follow-up).

| Campo | Armazenamento | Observação |
|---|---|---|
| `followup_max_attempts` | Coluna direta | |
| `followup_first_offset` | Coluna direta | |
| `followup_cadence` | Coluna direta (JSON) | UI usa string `"60,1440,4320"`, convertida para array de minutos ao salvar |
| `followup_allowed_hours` | Coluna direta | |
| `followup_auto_trigger_enabled` / `followup_auto_trigger_inactivity_days` | Coluna direta | **Ativo** — dispara follow-up automático por inatividade |
| `followup_checkin_auto_trigger_enabled` / `followup_checkin_inactivity_days` | Coluna direta | **Ativo** — dispara check-in automático de cliente inativo |
| `followup_checkin_instructions` | Coluna direta | |
| `followup_sdr_instructions` / `followup_recovery_instructions` / `followup_postsession_instructions` | Coluna direta | |
| `followup_goal_instructions` | Coluna direta (JSON) | |
| `cart_recovery_attempt_instructions` | Coluna direta (JSON, tupla de 3) | |
| `followup_outcome_instructions` | Coluna direta (JSON) | |
| `nurture_vs_discard_rule` | Coluna direta | Movido de Qualificação para aqui no M3 — ver discrepância de tipo acima |
| `appointment_reminder_h1` / `appointment_reminder_h2` | Derivado de `appointment_reminder_offsets` (coluna direta, JSON, em minutos negativos) | Movido de Apresentação para aqui — UI condicional, só aparece quando `isScheduleMode` (`agent_mode ∉ {direto, closer}`). Envia lembrete fixo ao **lead**, distinto do Dossiê pré-reunião (que vai ao operador e continua em Camada 5) |

Os campos `followup_h1`/`followup_h2`/`followup_h3` existiram até 2026-06-25 e foram removidos:
nunca foram lidos por nenhum código de backend (gravavam em `offer_pack` sem consumidor).

### Conexão (`ConexaoNumero.tsx`)

Não referencia campos de `AgentConfig` — gerencia a conexão WhatsApp (instância UazAPI) via API
própria do backend-core.

---

## Fluxo de dados

```
Frontend (AiProfile.tsx)
  └─► api.agente.getConfig()
        └─► GET /ai-profiles/me  →  backend-core
              └─► retorna perfil completo (colunas diretas + offer_pack)
                    └─► api.ts mapeia para AgentConfig flat

  └─► api.agente.saveConfig(config)
        └─► PUT /ai-profiles/me  →  backend-core
              ├─ campos diretos: name, brand_name, agent_mode, followup_*, sales_flow, ...
              └─ offer_pack: { ticket_range, f1_questions, opt_out_keywords, ... }

Frontend (CamadaConhecimento.tsx) — independente
  └─► api.crm.getKnowledgeList()       →  GET    /knowledge
  └─► api.crm.createKnowledgeManual()  →  POST   /knowledge/manual
  └─► api.crm.uploadKnowledgeFile()    →  POST   /knowledge/upload
  └─► api.crm.updateKnowledge()        →  PUT    /knowledge/:id
  └─► api.crm.deleteKnowledge()        →  DELETE /knowledge/:id

Webhook inbound WhatsApp
  └─► backend-crm / core_client.py
        └─► GET /ai-profiles/resolve?user_id=X  →  backend-core
              └─► orchestrator.py
                    ├─ _normalize_agent_mode_for_bundle()  ← usa: agent_mode, template_key
                    ├─ _resolve_presentation_contract()    ← usa: presentation_variant, hybrid_flow_style, offer_pack
                    ├─ _build_qualification_context()      ← usa: qualification_fields (ou qualification_required_fields)
                    └─ apply_mode_overrides()              ← usa: agent_mode normalizado

Reconciliador de follow-up (services/followup_reconciler.py) — fora do fluxo de mensagem
  └─► lê followup_auto_trigger_*, followup_checkin_*, followup_cadence, sales_flow
        → arquitetura completa em docs/architecture/followup.md
```

---

## Campos ativos no pipeline de IA

Confirmados via leitura direta de `orchestrator.py`:

| Campo | Efeito real |
|---|---|
| `template_key` | Seleciona qual playbook é carregado em `services/ai_playbooks/` |
| `agent_mode` | Define `max_chars`, `qualification_depth`, `cta_every_turn`, `must_handoff_on_high_intent` no orquestrador |
| `presentation_variant` (+ `hybrid_flow_style`) | Resolve a variante de apresentação (`sales` / `scheduler` / `hybrid`) |
| `qualification_fields` (ou `qualification_required_fields` como fallback legado) | Monta o contexto de qualificação injetado no prompt |
| `opt_out_keywords` | Verificado no guardrail de inbound antes do LLM |
| `sales_flow` | Se presente, injeta as regras de fluxo de venda configuradas |

Os campos de follow-up automático (`followup_auto_trigger_*`, `followup_checkin_*`) são
consumidos fora do orquestrador, pelo reconciliador de follow-up — ver
[`docs/architecture/followup.md`](architecture/followup.md).

Os demais campos são metadados configurados e salvos, mas ainda não consumidos ativamente pelo
pipeline de IA.

---

## Arquivos de referência

| Arquivo | Responsabilidade |
|---|---|
| [frontend-crm/src/pages/AiProfile.tsx](../frontend-crm/src/pages/AiProfile.tsx) | Página principal de configuração (rota `/ai-profile`) — orquestra todas as camadas |
| [frontend-crm/src/components/agente/CamadaIdentidade.tsx](../frontend-crm/src/components/agente/CamadaIdentidade.tsx) | UI da Camada 1 |
| [frontend-crm/src/components/agente/CamadaQualificacao.tsx](../frontend-crm/src/components/agente/CamadaQualificacao.tsx) | UI da Camada 2 |
| [frontend-crm/src/components/agente/CamadaPipeline.tsx](../frontend-crm/src/components/agente/CamadaPipeline.tsx) | UI da Camada 3 |
| [frontend-crm/src/components/agente/CamadaConhecimento.tsx](../frontend-crm/src/components/agente/CamadaConhecimento.tsx) | UI da Camada 4 — CRUD de knowledge items |
| [frontend-crm/src/components/agente/CamadaApresentacao.tsx](../frontend-crm/src/components/agente/CamadaApresentacao.tsx) | UI da Camada 5 — agendamento (condicional) |
| [frontend-crm/src/components/agente/CamadaOferta.tsx](../frontend-crm/src/components/agente/CamadaOferta.tsx) | UI da Camada 6 — oferta e pagamento (condicional) |
| [frontend-crm/src/components/agente/CamadaFluxoVenda.tsx](../frontend-crm/src/components/agente/CamadaFluxoVenda.tsx) | UI do Fluxo de Venda |
| [frontend-crm/src/components/agente/CamadaFollowup.tsx](../frontend-crm/src/components/agente/CamadaFollowup.tsx) | UI da camada dedicada de Follow-up |
| [frontend-crm/src/components/agente/ConexaoNumero.tsx](../frontend-crm/src/components/agente/ConexaoNumero.tsx) | UI de conexão WhatsApp |
| [frontend-crm/src/types/agente.ts](../frontend-crm/src/types/agente.ts) | Tipos `AgentConfig`, `OfferPackExtra`, `DEFAULT_AGENT_CONFIG` |
| [frontend-crm/src/services/api.ts](../frontend-crm/src/services/api.ts) | `api.agente.getConfig()` e `api.agente.saveConfig()` — mapeamento frontend↔backend |
| [backend-core/app/models/ai_profile.py](../backend-core/app/models/ai_profile.py) | Model SQLAlchemy |
| [backend-core/app/api/ai_profiles.py](../backend-core/app/api/ai_profiles.py) | Endpoints REST |
| [backend-crm/services/ai_orchestrator/orchestrator.py](../backend-crm/services/ai_orchestrator/orchestrator.py) | Consumo real dos campos no pipeline de mensagens |
| [backend-crm/services/followup_reconciler.py](../backend-crm/services/followup_reconciler.py) | Consumo dos campos de follow-up automático |
