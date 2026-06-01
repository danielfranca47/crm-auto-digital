# Etapa C — Instruções de Follow-Up por Agente

**Branch:** `etapa-8-7-fluxo-qualificacao-natural`
**Status:** Em andamento

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
- [ ] PUT `/ai-profiles/me` com `followup_sdr_instructions: "teste"` → 200
- [ ] GET `/ai-profiles/me` devolve `followup_sdr_instructions: "teste"`

### Cenário P2 — Bloco aparece no prompt (playground)
- [ ] Configurar `followup_sdr_instructions = "Nunca menciones preço."` no AI Profile
- [ ] Iniciar follow-up com um lead Agent 1
- [ ] Usar playground no tick de follow-up
- [ ] Confirmar: resposta reflecte a instrução do operador

### Cenário P3 — Sem regressão quando campo vazio
- [ ] Lead com campo não preenchido → comportamento idêntico ao actual
- [ ] Confirmar: `_variant_operator_block` ausente no prompt

### Cenário P4 — UI guarda e recarrega
- [ ] Abrir CamadaPipeline → secção Follow-Up → drawer "Instrução de follow-up"
- [ ] Preencher → Salvar → recarregar página → campo persiste

### Cenário P5 — Drawer condicional ao template_key
- [ ] Agent 1: aparece textarea para `followup_sdr_instructions`
- [ ] Agent 2: aparece textarea para `followup_recovery_instructions`
- [ ] Agent 3: aparece textarea para `followup_postsession_instructions`
