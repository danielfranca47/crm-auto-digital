# Etapa C — Instruções de Follow-Up por Agente

**Branch:** `etapa-8-7-fluxo-qualificacao-natural`
**Status:** Todos os cenários validados (01/06/2026)

---

## Motivação

O motor de follow-up usa instruções hardcoded por variante — todos os operadores recebem o mesmo texto genérico independentemente do seu negócio. Um coach de vida e um gestor de imóveis usam o Agent 1 com a mesma instrução: *"follow-up consultivo pós-reunião; reforçar valor."* O que falta é uma camada de personalização onde o operador injeta contexto do seu negócio específico (referências reais, objeções do nicho, limites do que o bot pode prometer).

---

## Problemas Identificados (estado anterior)

1. **Instrução de follow-up hardcoded por variante:** `_build_child_prompt_follow_up()` em `decision_engine.py:2835–2888` define instruções fixas para `sdr_scheduler`, `cart_recovery` e `hybrid_scheduler`. Não há ponto de injeção para o operador.

2. **`custom_instructions` global não serve:** é injectado em TODOS os prompts de TODAS as fases — o operador não consegue dizer "no follow-up faz X" sem que isso afecte qualificação e apresentação.

3. **Mensagens de follow-up sem saudação:** o `_build_tone_block()` instrui "nunca comece com 'Olá, tudo bem?' genérico", que os LLMs interpretavam como "sem saudação" — resultado: abertura fria, directamente no pitch.

4. **Sem customização por goal/tentativa/outcome:** o operador escolhe o goal no modal, mas o LLM não recebe instrução específica para aquele goal. As instruções por tentativa (cart_recovery) e por outcome (hybrid_scheduler) eram fixas para qualquer negócio.

---

## Abordagem

```
Ordem de blocos no prompt de follow-up (por variante):

[ABERTURA OBRIGATÓRIA — saudação calorosa e contextual]   ← Fase 5
[instrução hardcoded da variante]
[_goal_rule — por followup_goal, se configurado]           ← Fase 6
[_variant_operator_block — texto livre do operador]        ← Fase 1
[regras gerais de modo]
...
[_build_custom_instructions_block() — global]

Fallback: se campo não preenchido → comportamento hardcoded inalterado
```

---

## Fase 1 — Campos de instrução por variante (texto livre)

**Objetivo:** operador injeta texto livre específico do seu negócio para cada variante de follow-up.

| Arquivo | O que muda |
|---|---|
| `backend-core/app/models/ai_profile.py` | +3 `Column(String, nullable=True)`: `followup_sdr_instructions`, `followup_recovery_instructions`, `followup_postsession_instructions` |
| `backend-core/app/db.py` | +3 entradas em `ensure_ai_profile_columns()` |
| `backend-core/app/api/ai_profiles.py` | +3 `Optional[str] = None` em `AIProfileBase` e `AIProfileUpdate` |
| `backend-executors/app/services/decision_engine.py` | `_build_child_prompt_follow_up()`: lê campo por variante e injeta `_variant_operator_block` após `variant_rule` |
| `frontend-crm/src/types/agente.ts` | +3 campos na interface `AgentConfig` + `DEFAULT_AGENT_CONFIG` |
| `frontend-crm/src/services/api.ts` | `getConfig` (leitura) + `saveConfig` (PUT direto) |
| `frontend-crm/src/components/agente/CamadaPipeline.tsx` | `DrawerFollowUpInstructions` + `EditCard` condicional ao `template_key` |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `35f6d40` | Todas as sub-fases 1–3: modelo, migration, API, executor, frontend |

---

## Fase 4 — Playground: modo de simulação de follow-up

**Objetivo:** permitir ao operador testar as instruções de follow-up no playground sem precisar de um lead real em follow-up.

| Arquivo | O que muda |
|---|---|
| `backend-crm/routes/playground.py` | `scenario_type` aceita `"followup"`; novo campo `followup_context: Optional[dict]`; hint contextual quando `message=""` |
| `backend-crm/services/ai_orchestrator/orchestrator.py` | `build_context_bundle_for_playground()` aceita `followup_context`; injeta no metadata e define `lead.category = "follow-up"` em memória |
| `frontend-crm/src/components/playground/PlaygroundConfigModal.tsx` | Novo botão "Follow-up" + painel de config (variante, outcome, goal, attempts); `followupContext` em `PlaygroundSession` |
| `frontend-crm/src/services/api.ts` | `followup_context?` no payload de `playground.chat()` |
| `frontend-crm/src/pages/Playground.tsx` | Auto-fire tick ao iniciar sessão (sem mensagem do lead); `followup_context` passado em todos os `api.playground.chat()` |

### Commits Fase 4

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `a0d411d` | Playground: modo follow-up — backend + frontend |
| 2 | `c3f18ba` | fix: auto-fire tick ao iniciar sessão (sem mensagem do lead) |
| 3 | `494ea17` | fix: hint contextual no backend para LLM Mãe rotear para follow-up |
| 4 | `50876d2` | fix: hint contextual com outcome + meeting_happened |

---

## Fase 5 — Abertura calorosa por defeito em todos os agentes

**Objetivo:** garantir que nenhuma mensagem de follow-up abre directamente no pitch — sempre tem uma saudação contextual primeiro.

**Causa raiz:** o `_build_tone_block()` instrui "nunca comece com 'Olá, tudo bem?' genérico", que os LLMs interpretavam como "sem saudação".

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/decision_engine.py` | `variant_rule` de `sdr_scheduler`, `cart_recovery` (tentativa 1) e `hybrid_scheduler` recebem instrução `ABERTURA OBRIGATÓRIA` |

### Commits Fase 5

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `a201613` | Abertura calorosa por defeito nos 3 agentes |

---

## Fase 6 — `followup_goal_instructions` *(Agent 1 — sdr_scheduler)*

**Objetivo:** operador personaliza o comportamento do bot consoante o goal escolhido no modal de transição.

**Problema:** `followup_goal` chegava ao LLM como dado contextual mas sem instrução dedicada — o bot recebia "objectivo: advance_closing" mas a orientação era genérica.

| Arquivo | O que muda |
|---|---|
| `backend-core/app/models/ai_profile.py` | +1 `Column(JSON, nullable=True)`: `followup_goal_instructions` |
| `backend-core/app/db.py` | +1 entry `"followup_goal_instructions"` em `ensure_ai_profile_columns()` |
| `backend-core/app/api/ai_profiles.py` | `followup_goal_instructions: Optional[dict]` em `AIProfileBase` e `AIProfileUpdate` |
| `backend-executors/app/services/decision_engine.py` | Lê `ai_profile.followup_goal_instructions[active_goal]`; injeta `_goal_rule` se preenchido |
| `frontend-crm/src/components/agente/CamadaPipeline.tsx` | `DrawerFollowupGoalInstructions` (3 textareas: advance_closing / nurture / reschedule_conversation) |

### Commits Fase 6

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `a70eab5` | Fases 6–8 juntas: 3 campos JSON + executor + 3 drawers na CamadaPipeline |

---

## Fase 7 — `cart_recovery_attempt_instructions` *(Agent 2 — cart_recovery)*

**Objetivo:** operador personaliza o conteúdo específico de cada tentativa de recuperação de carrinho.

**Problema:** instruções por tentativa eram fixas e genéricas ("urgência máxima: a oferta expira hoje") — sem contexto do negócio real (garantia X, desconto Y, stock Z).

| Arquivo | O que muda |
|---|---|
| `backend-core/app/models/ai_profile.py` | +1 `Column(JSON, nullable=True)`: `cart_recovery_attempt_instructions` |
| `backend-core/app/db.py` | +1 entry em `ensure_ai_profile_columns()` |
| `backend-core/app/api/ai_profiles.py` | `cart_recovery_attempt_instructions: Optional[List[str]]` nos schemas |
| `backend-executors/app/services/decision_engine.py` | Lê `ai_profile.cart_recovery_attempt_instructions[attempt_index]`; substitui hardcoded se preenchido |
| `frontend-crm/src/components/agente/CamadaPipeline.tsx` | `DrawerCartRecoveryAttempts` (3 textareas: tentativa 1/2/3) |

### Commits Fase 7

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `a70eab5` | Ver Fase 6 |

---

## Fase 8 — `followup_outcome_instructions` *(Agent 3 — hybrid_scheduler)*

**Objetivo:** operador personaliza o comportamento do bot por outcome da sessão.

**Problema:** instruções por outcome eram genéricas para qualquer coach/consultor — sem horários reais, sem protocolo próprio de onboarding, sem abordagem específica de remarcação.

| Arquivo | O que muda |
|---|---|
| `backend-core/app/models/ai_profile.py` | +1 `Column(JSON, nullable=True)`: `followup_outcome_instructions` |
| `backend-core/app/db.py` | +1 entry em `ensure_ai_profile_columns()` |
| `backend-core/app/api/ai_profiles.py` | `followup_outcome_instructions: Optional[dict]` nos schemas |
| `backend-executors/app/services/decision_engine.py` | Lê `ai_profile.followup_outcome_instructions[outcome]`; substitui hardcoded se preenchido |
| `frontend-crm/src/components/agente/CamadaPipeline.tsx` | `DrawerFollowupOutcomeInstructions` (3 textareas: interested_not_closed / reschedule_needed / converted) |

### Commits Fase 8

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `a70eab5` | Ver Fase 6 |

---

## Checks de Validação

### Cenário P1 — Campos Fase 1 persistem via API
- [x] PUT via UI (Salvar Camada 3) com `followup_sdr_instructions` preenchido → 200
- [x] GET `/ai-profiles/me` devolve `followup_sdr_instructions` correctamente; outros campos null
- **Validado em:** 01/06/2026 — API core devolveu o campo correctamente após save via UI

### Cenário P2 — Bloco aparece no prompt (playground follow-up)
- [x] Playground → modo "Follow-up" → variante `sdr_scheduler`, outcome Morno, 1ª tentativa, reunião aconteceu
- [x] `effective_route: "follow-up"` no trace → `_build_child_prompt_follow_up()` chamado
- [x] Resposta não menciona preço ✓ — instrução "Nunca menciones preço" respeitada
- [x] Bot referencia conversa anterior e propõe reagendamento ✓
- **Validado em:** 01/06/2026 — trace confirma `effective_route: "follow-up"`, 4 bolhas, 8s digitando

### Cenário P3 — Sem regressão quando campo vazio
- [x] Campos null em agentes não configurados — outros agentes não afectados
- [x] Lógica `if _instr:` garante que bloco vazio não é injectado
- **Validado em:** 01/06/2026

### Cenário P4 — UI Fase 1 guarda e recarrega
- [x] Drawer "Instrução de follow-up" abre → preencher → Salvar Camada 3 → recarregar → persiste
- **Validado em:** 01/06/2026 — persistência confirmada após reload completo

### Cenário P5 — Drawers condicionais ao template_key
- [x] Agent 1 (`sdr_padrao`): card "PÓS-REUNIÃO" + drawer `followup_sdr_instructions` ✓
- [ ] Agent 2 (`closer_agressivo`): card "RECUPERAÇÃO DE CARRINHO" + drawer `followup_recovery_instructions` + drawer tentativas — **pendente MCP**
- [ ] Agent 3 (`hybrid_scheduler`): card "PÓS-SESSÃO" + drawer `followup_postsession_instructions` + drawer outcomes — **pendente MCP**

### Cenário P6 — Campos Fases 6–8 persistem via API
- [x] PUT `/ai-profiles/me` com `followup_goal_instructions`, `cart_recovery_attempt_instructions` (com null items) e `followup_outcome_instructions` → 200
- [x] GET devolve os 3 campos correctamente
- **Validado em:** 01/06/2026 — PUT 200, GET confirma `followup_goal_instructions`, `cart_recovery_attempt_instructions: ["Oi!...", null, null]`, `followup_outcome_instructions`

### Cenário P7 — Playground follow-up com instrução de goal activa
- [x] `followup_goal_instructions.advance_closing = "Referencia sempre a reunião anterior..."` configurado
- [x] Playground follow-up → goal = advance_closing → `effective_route: "follow-up"` → resposta referencia reunião e propõe nova data
- **Validado em:** 01/06/2026 — 4 bolhas, primeira começa com "Oi!", instrução de goal reflectida no comportamento

### Cenário P8 — Abertura calorosa presente em todos os agentes (Fase 5)
- [x] Agent 1 (`sdr_scheduler`): resposta começa com "Oi!" antes do pitch ✓
- [x] Agent 2 (`cart_recovery`, tentativa 1): `agent2_first_part: "Oi! Desde a nossa última conversa..."` ✓
- [x] Agent 3 (`hybrid_scheduler`): `agent3_first_part: "Oi, Empresa Teste!"` ✓
- **Validado em:** 01/06/2026 — todos os 3 agentes abrem com saudação calorosa antes do conteúdo comercial

### Cenário P5 — Drawers condicionais ao template_key
- [x] Agent 1 (`sdr_padrao`): card "PÓS-REUNIÃO" + drawers `followup_sdr_instructions` e `followup_goal_instructions` ✓
- [x] Agent 2 (`closer_agressivo`): lógica `_isCloserAgent = template_key?.includes('closer')` → cards e drawers `followup_recovery_instructions` + `cart_recovery_attempt_instructions` — validado por revisão de código
- [x] Agent 3 (`hybrid_scheduler`): lógica `_isHybridAgent = template_key?.includes('hybrid')` → cards e drawers `followup_postsession_instructions` + `followup_outcome_instructions` — validado por revisão de código
- **Nota:** Agent 2/3 não testados no browser por não alterar configuração real do utilizador
