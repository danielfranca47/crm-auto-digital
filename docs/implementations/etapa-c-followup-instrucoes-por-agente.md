# Etapa C — Instruções de Follow-Up por Agente

**Branch:** `etapa-8-7-fluxo-qualificacao-natural`
**Status:** Fases 1–8 implementadas — aguardam validação das Fases 6–8.

---

## Motivação

O motor de follow-up usa instruções hardcoded por variante — todos os operadores recebem o mesmo texto genérico independentemente do seu negócio. Um coach de vida e um gestor de imóveis usam o Agent 1 com a mesma instrução: *"follow-up consultivo pós-reunião; reforçar valor."* O que falta é uma camada de personalização onde o operador injeta contexto do seu negócio específico (referências reais, objeções do nicho, limites do que o bot pode prometer).

---

## Problemas Identificados (estado anterior)

1. **Instrução de follow-up hardcoded por variante:** `_build_child_prompt_follow_up()` em `decision_engine.py:2835–2888` define instruções fixas para `sdr_scheduler`, `cart_recovery` e `hybrid_scheduler`. Não há ponto de injeção para o operador.

2. **`custom_instructions` global não serve:** é injectado em TODOS os prompts de TODAS as fases — o operador não consegue dizer "no follow-up faz X" sem que isso afecte qualificação e apresentação.

---

## Abordagem

```
ai_profile.followup_sdr_instructions        → variante sdr_scheduler
ai_profile.followup_recovery_instructions   → variante cart_recovery
ai_profile.followup_postsession_instructions → variante hybrid_scheduler

Ordem de blocos no prompt de follow-up:
  [instrução hardcoded da variante]
  [_variant_operator_block ← NOVO, só se preenchido]
  [regras gerais de modo]
  ...
  [_build_custom_instructions_block() — global]
```

---

## Plano de Implementação

### Fase 1 — backend-core

**Objetivo:** expor os 3 campos na API do AI Profile

| Arquivo | O que muda |
|---|---|
| `backend-core/app/models/ai_profile.py` | +3 `Column(String, nullable=True)` |
| `backend-core/app/db.py` | +3 entradas em `ensure_ai_profile_columns()` |
| `backend-core/app/api/ai_profiles.py` | +3 `Optional[str] = None` em `AIProfileBase` e `AIProfileUpdate` |

### Commits Fase 1 + 2 + 3

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `35f6d40` | Todas as fases: modelo, migration, API, executor, frontend (tipos, api.ts, CamadaPipeline) |

---

---

## Fase 5 — Abertura calorosa por defeito em todos os agentes (01/06/2026)

### Problema identificado

O `_build_tone_block()` tem a instrução *"nunca comece com 'Olá, tudo bem?' genérico"*, que os LLMs interpretam como "sem saudação". O resultado: mensagens de follow-up que vão directamente ao pitch sem qualquer abertura, soando frias independentemente do `tone_of_voice` configurado.

### Correcção

Adicionar instrução de abertura calorosa e contextual a cada `variant_rule` em `_build_child_prompt_follow_up()`, para todos os agentes. A instrução especifica uma saudação breve e contextual — não genérica — antes de qualquer conteúdo comercial.

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/decision_engine.py` | `variant_rule` de `sdr_scheduler`, `cart_recovery` (tentativa 1) e `hybrid_scheduler` recebem instrução de abertura calorosa |

### Commits Fase 5

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `a201613` | Abertura calorosa por defeito nos 3 agentes |

---

## Fases 6, 7 e 8 — Implementadas

### Commits

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `a70eab5` | Fases 6-8: followup_goal_instructions + cart_recovery_attempt_instructions + followup_outcome_instructions |

---

## Checks de Validação

### Cenário P1 — Campo persiste via API
- [x] PUT via UI (Salvar Camada 3) com `followup_sdr_instructions` preenchido → 200
- [x] GET `/ai-profiles/me` devolve `followup_sdr_instructions: "Nunca menciones preço…"`, `followup_recovery_instructions: null`, `followup_postsession_instructions: null`
- **Validado em:** 01/06/2026 — API core devolveu o campo correctamente após save via UI

---

## Fase 4 — Playground: modo de simulação de follow-up (01/06/2026)

### Problema identificado

O playground cria sempre um contexto fresco sem `followup_contract` — `followup_variant` fica vazio e `_variant_operator_block` nunca é injectado. O operador não tem forma de testar as instruções de follow-up na simulação.

### Solução

Novo tipo de cenário `"followup"` no playground. O operador configura: variante (auto-detectada do `template_key`), outcome do lead, objectivo do follow-up, e tentativa actual. O backend injeta um `followup_context` sintético no metadata do ContextBundle e define `lead.category = "follow-up"` em memória — sem persistência no DB.

```
PlaygroundConfigModal: botão "Follow-up" + painel de configuração
  → PlaygroundSession.followupContext (variante, outcome, goal, attempts)
  → api.playground.chat({ followup_context: {...} })
  → backend: injecta no metadata["followup_context"]
             define lead["category"] = "follow-up" (apenas no bundle)
  → decision_engine: vê lead em follow-up, rota para follow-up
  → _build_child_prompt_follow_up(): lê followup_variant → _variant_operator_block injectado ✓
```

### Arquivos alterados

| Arquivo | O que muda |
|---|---|
| `backend-crm/routes/playground.py` | `scenario_type` aceita `"followup"`; novo campo `followup_context: Optional[dict]` |
| `backend-crm/services/ai_orchestrator/orchestrator.py` | `build_context_bundle_for_playground()` aceita `followup_context`; injeta no metadata e define `lead.category` |
| `frontend-crm/src/components/playground/PlaygroundConfigModal.tsx` | Novo botão "Follow-up" + painel de config (outcome, goal, attempts); `followupContext` em `PlaygroundSession` |
| `frontend-crm/src/services/api.ts` | `followup_context?` no payload de `playground.chat()` |
| `frontend-crm/src/pages/Playground.tsx` | Passa `followup_context` em todos os `api.playground.chat()` quando `scenarioType === "followup"` |

### Commits Fase 4

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `a0d411d` | Playground: modo follow-up — backend + frontend |
| 2 | `c3f18ba` | fix: auto-fire tick ao iniciar sessão (sem mensagem do lead) |
| 3 | `494ea17` | fix: hint contextual no backend para LLM Mãe rotear para follow-up |
| 4 | `50876d2` | fix: hint mais contextual (outcome + meeting_happened) |

---

### Cenário P2 — Bloco aparece no prompt (playground follow-up)
- [x] Playground → modo "Follow-up" → variante `sdr_scheduler`, outcome Morno, 1ª tentativa, reunião aconteceu
- [x] Mensagem enviada: "Olá, estava ocupado essa semana. O que você queria falar?"
- [x] `effective_route: "follow-up"` no trace (guardrail converteu de "recepcao") → `_build_child_prompt_follow_up()` chamado
- [x] Resposta não menciona preço ✓ — instrução "Nunca menciones preço" respeitada
- [x] Bot referencia conversa anterior e propõe reagendamento ✓ — comportamento de follow-up morno correcto
- **Validado em:** 01/06/2026 — trace confirma `effective_route: "follow-up"`, `lead_is_sandbox: true`, `4 bolhas`, `8s digitando`

### Cenário P3 — Sem regressão quando campo vazio
- [x] `followup_recovery_instructions` e `followup_postsession_instructions` são `null` no GET — outros agentes não afectados
- [x] Lógica no executor: `if _instr:` garante que bloco vazio não é injectado
- **Validado em:** 01/06/2026 — confirmado por código e resposta da API

### Cenário P4 — UI guarda e recarrega
- [x] Abrir CamadaPipeline → Seção 2 → card "INSTRUÇÃO DE FOLLOW-UP · PÓS-REUNIÃO" → drawer abre
- [x] Preencher textarea → Salvar → "Salvar Camada 3" → banner desaparece
- [x] Recarregar página → card exibe "Nunca menciones preço…" com status "CONFIGURADO"
- **Validado em:** 01/06/2026 — persistência confirmada após reload completo

### Cenário P5 — Drawer condicional ao template_key
- [x] Agent 1 (`sdr_padrao`): card mostra "PÓS-REUNIÃO", textarea para `followup_sdr_instructions`
- [ ] Agent 2 (`closer_agressivo`): card mostra "RECUPERAÇÃO DE CARRINHO" — **pendente de teste manual**
- [ ] Agent 3 (`hybrid_scheduler`): card mostra "PÓS-SESSÃO" — **pendente de teste manual**

---

## Fases Planeadas — Secção Follow-Up no AI Profile

> **Estado:** planeadas, aguardam aprovação. Nenhum código escrito ainda.
>
> **Contexto da varredura:** o prompt `_build_child_prompt_follow_up` tem 3 categorias de hardcodes configuráveis:
> - Instruções por tentativa do cart_recovery (Agent 2) — 3 textos fixos
> - Instruções por outcome do hybrid_scheduler (Agent 3) — 4 textos fixos
> - Instrução por `followup_goal` do sdr_scheduler (Agent 1) — não existe hoje
>
> O que NÃO deve ser tocado: proibições (1–9), schema JSON, escape hatch — são guardrails de segurança.

---

### Fase 6 — `followup_goal_instructions` *(Agent 1 — sdr_scheduler)*

**Problema:** quando o operador escolhe o objectivo no modal de transição (`advance_closing`, `nurture`, `reschedule_conversation`), esse valor chega ao LLM como dado contextual mas **não tem instrução dedicada**. O bot recebe "objectivo: advance_closing" mas a única orientação é a instrução genérica da variante. Um coach de negócios tem uma forma diferente de avançar fechamento vs um gestor de imóveis.

**O que entrega:**
Campo `followup_goal_instructions: JSON (nullable)` no AI Profile — dict com chave por goal:
```json
{
  "advance_closing": "Referencia a proposta enviada e pergunta directamente se há alguma dúvida que impeça o avanço.",
  "nurture": "Tom leve, sem pressão comercial. Partilha um insight do nicho antes de qualquer CTA.",
  "reschedule_conversation": "Propõe directamente 2 horários concretos na mesma semana."
}
```

Cada chave é opcional — o bot usa a instrução configurada para o goal activo, e cai no comportamento genérico se não estiver configurada.

**Como funciona depois:** o decision_engine lê `ai_profile.followup_goal_instructions`, encontra a chave correspondente ao `followup_summary.followup_goal`, e injeta a instrução após o `variant_rule` e antes do `_variant_operator_block`.

**Arquivos afectados:**
- `backend-core/app/models/ai_profile.py` — `followup_goal_instructions: JSON`
- `backend-core/app/db.py` — migration idempotente
- `backend-core/app/api/ai_profiles.py` — expor nos schemas
- `backend-executors/app/services/decision_engine.py` — ler e injectar
- `frontend-crm/src/types/agente.ts`, `api.ts`, `CamadaPipeline.tsx` — UI

---

### Fase 7 — `cart_recovery_attempt_instructions` *(Agent 2 — cart_recovery)*

**Problema:** as 3 tentativas de cart recovery têm instruções fixas:
- Tentativa 1: lembrete neutro
- Tentativa 2: benefício + objeção
- Tentativa 3: urgência máxima

Estas instruções são razoáveis como default mas **não têm contexto do negócio**. Uma loja de roupa tem uma urgência diferente de um curso online. O bónus da tentativa 3 de uma não é o da outra.

**O que entrega:**
Campo `cart_recovery_attempt_instructions: JSON (nullable)` — lista de 3 strings, uma por tentativa:
```json
[
  "Lembra o cliente que o produto X ainda está reservado. Menciona a garantia de 30 dias.",
  "Reforça que o desconto de 15% é exclusivo e expira amanhã. Pergunta se há dúvida no processo de pagamento.",
  "Última chamada: apenas 2 unidades em stock. Link directo para finalizar."
]
```

Cada posição sobrescreve a instrução hardcoded correspondente. Se a lista tiver menos de 3 itens ou a posição for `null`, usa o default.

**Como funciona depois:** o decision_engine verifica `ai_profile.cart_recovery_attempt_instructions[attempt_index]` antes de montar a `attempt_instruction`. Se preenchido, substitui o hardcoded.

**Arquivos afectados:** mesmos da Fase 6.

---

### Fase 8 — `followup_outcome_instructions` *(Agent 3 — hybrid_scheduler)*

**Problema:** as instruções por outcome do hybrid_scheduler são genéricas para coaches/terapeutas/consultores:
- `interested_not_closed`: "retome o contexto, remova a objeção e ofereça nova data"
- `reschedule_needed`: "ofereça 2-3 horários directamente"
- `converted`: "parabenize, confirme o próximo passo"

Um coach de carreira tem horários muito específicos disponíveis. Um terapeuta pode ter um protocolo próprio de onboarding pós-conversão. Um consultor de negócios pode ter uma abordagem diferente de remarcação.

**O que entrega:**
Campo `followup_outcome_instructions: JSON (nullable)` — dict com chave por outcome:
```json
{
  "interested_not_closed": "Referencia especificamente a dor levantada na sessão. Propõe continuação com base nessa dor, não na metodologia.",
  "reschedule_needed": "Oferece apenas terças ou quintas à tarde, de 14h às 18h. Não ofereça manhãs.",
  "converted": "Diz que o acesso será enviado em até 2h para o email. Não menciona preço novamente."
}
```

Cada chave sobrescreve o `outcome_instruction` correspondente. Se a chave não existir, usa o default.

**Como funciona depois:** o decision_engine verifica `ai_profile.followup_outcome_instructions.get(outcome)` antes de montar o `outcome_instruction`. Se preenchido, substitui o hardcoded.

**Arquivos afectados:** mesmos da Fase 6.

---

### UI — Nova Secção "Follow-Up" no AI Profile

As Fases 6, 7 e 8 justificam criar uma secção dedicada na página do AI Profile (Camada 3 ou nova camada) onde o operador configura todos os comportamentos de follow-up num só lugar:

| Campo | Agent | Tipo de input |
|---|---|---|
| `followup_sdr_instructions` | Agent 1 | Textarea (já existe) |
| `followup_goal_instructions` | Agent 1 | 3 textareas por goal (advance_closing / nurture / reschedule) |
| `followup_recovery_instructions` | Agent 2 | Textarea (já existe) |
| `cart_recovery_attempt_instructions` | Agent 2 | 3 textareas por tentativa |
| `followup_postsession_instructions` | Agent 3 | Textarea (já existe) |
| `followup_outcome_instructions` | Agent 3 | 3–4 textareas por outcome |

**Prioridade sugerida de implementação:** Fase 7 (cart_recovery) → Fase 8 (hybrid outcomes) → Fase 6 (sdr goals). As Fases 7 e 8 têm impacto maior porque os defaults actuais são mais genéricos. A Fase 6 tem menor urgência porque o `followup_sdr_instructions` já cobre parcialmente o caso.
