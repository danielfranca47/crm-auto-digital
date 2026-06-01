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
- [x] PUT via UI (Salvar Camada 3) com `followup_sdr_instructions` preenchido → 200
- [x] GET `/ai-profiles/me` devolve `followup_sdr_instructions: "Nunca menciones preço…"`, `followup_recovery_instructions: null`, `followup_postsession_instructions: null`
- **Validado em:** 01/06/2026 — API core devolveu o campo correctamente após save via UI

### Cenário P2 — Bloco aparece no prompt (playground)
- [ ] Configurar `followup_sdr_instructions = "Nunca menciones preço."` no AI Profile
- [ ] Iniciar follow-up com um lead Agent 1
- [ ] Usar playground no tick de follow-up
- [ ] Confirmar: resposta reflecte a instrução do operador
- **Pendente:** requer lead em follow-up activo para testar via playground

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
