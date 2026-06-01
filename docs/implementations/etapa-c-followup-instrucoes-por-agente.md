# Etapa C — Instruções de Follow-Up por Agente

**Branch:** `etapa-8-7-fluxo-qualificacao-natural`
**Status:** Em andamento — Fase 4 adicionada (playground follow-up)

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
| 1 | *(pendente)* | Playground: modo follow-up — backend + frontend |

---

### Cenário P2 — Bloco aparece no prompt (lead real em follow-up)
- [ ] Lead real na coluna follow-up com `followup_contract` activo
- [ ] `followup_sdr_instructions` configurado no AI Profile
- [ ] Tick automático enviado → confirmar que a mensagem reflecte a instrução do operador
- **Nota:** playground não testável para este cenário — não tem `followup_contract`, logo `followup_variant` fica vazio e o bloco não é injectado (comportamento correcto). Validação natural quando um lead real atingir o follow-up.

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
