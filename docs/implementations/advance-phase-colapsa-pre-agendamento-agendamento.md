# `advance_phase` colapsa p3a/p3b em "apresentation" (categoria nunca vira pre-agendamento/agendamento)

**Branch:** `fix/advance-phase-colapsa-pre-agendamento-agendamento`
**Status:** Em andamento

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`unificar-transicoes-fase-sales-flow.md`.

Durante a investigação dessa implementação, foi encontrado `_PHASE_ID_TO_CATEGORY`,
duplicado identicamente em `backend-crm/routes/executor.py:266` e
`backend-crm/routes/playground.py:194`:

```python
_PHASE_ID_TO_CATEGORY = {
    "p1":  "qualification",
    "p2":  "apresentation",
    "p3a": "apresentation",
    "p3b": "apresentation",
    "p4":  "followup",
    "p5":  "closing",
}
```

Usado pela ação `advance_phase` do Fluxo de Venda (builder `CamadaFluxoVenda.tsx`,
tipo de ação num bloco de fase): quando esse bloco é configurado nas fases **p3a
(pré-agendamento)** ou **p3b (agendamento)**, a categoria persistida do lead
(`leads.category`) é sempre movida para `"apresentation"` — nunca para
`"pre-agendamento"`/`"agendamento"`. Ou seja, um operador que configure
"avançar de fase" dentro de p3a/p3b no builder nunca vê o lead realmente mover
para essas colunas do Kanban via essa ação — ele fica preso (ou volta) para
`apresentation`.

Isso é inconsistente com `_CATEGORY_TO_PHASE_ID` (`decision_engine.py:1112`,
local a `_collect_intent_triggers_for_lead_phase`), que mapeia p3a→`pre_agendamento`
e p3b→`agendamento` corretamente, sem colapsar — ou seja, já existe no
código uma tradução correta para o mesmo conceito, só que numa direção/lugar
diferente de `_PHASE_ID_TO_CATEGORY`.

---

## Diagnóstico (Plan Mode)

### 1. O bug é observável na prática, ou só risco teórico?

Consultada diretamente a base local `backend-core/core.db` (`ai_profiles.sales_flow`).
Existem 2 perfis com `agent_mode` do grupo `agenda` (`sdr_scheduler`/`sdr_padrao`
e `agenda`/`hybrid_scheduler`) com fases `p3a`/`p3b` presentes no JSON, mas
**nenhum bloco `avancar_fase` configurado nelas ainda** (`blocks: []`).

**Conclusão:** risco teórico, ainda não acionado — nenhum utilizador real foi
afetado até agora, mas qualquer configuração futura desse tipo cairia no bug.

### 2. É só trocar os 2 valores, ou há razão deliberada para o colapso?

Investigados os guardrails de `template_key`/`_SCHEDULING_AGENT_TEMPLATES` em
`decision_engine.py` (linhas ~4695-5175):

- `_STAGE_ORDER`/`_ALLOWED_ADVANCE` (`decision_engine.py:4695-4701`) já usam
  `"pre-agendamento"`/`"agendamento"` (com hífen) como categorias válidas de
  primeira classe.
- O guardrail da linha 5084 (`suggested_category in {"pre-agendamento",
  "agendamento"} and template_key not in _SCHEDULING_AGENT_TEMPLATES` →
  rebaixa para `"apresentation"`) atua sobre `suggested_category` calculada
  **dentro do `decide()` do decision_engine** (backend-executors) — caminho
  totalmente separado de `_PHASE_ID_TO_CATEGORY`, que só é consultado em
  `backend-crm` ao despachar a `system_action` `advance_phase`. Não há
  interação entre os dois.
- `LEAD_CATEGORIES_SET` (`backend-crm/services/jobs_service.py:101-116`) já
  inclui `"pre-agendamento"` e `"agendamento"` como categorias válidas,
  aceites por `apply_suggested_category()` (usada pelo executor real) — a
  troca não introduz um valor desconhecido ao resto do sistema.
- As fases p3a/p3b só são renderizadas no builder e só existem na sequência
  do `agent_mode` para o grupo `agenda`
  (`_SALES_FLOW_PHASE_SEQUENCE_BY_AGENT_MODE`), grupo que corresponde
  exatamente aos `template_key` em `_SCHEDULING_AGENT_TEMPLATES`
  (`sdr_padrao`, `hybrid_scheduler`) — logo o guardrail da linha 5084 nunca
  rebaixaria uma categoria vinda de um perfil que legitimamente configurou
  blocos em p3a/p3b.

**Conclusão:** não há razão deliberada para o colapso — é um bug de
digitação/cópia. A correção é só trocar os 2 valores no dicionário, em ambos
os arquivos (mantendo-os idênticos, como já são hoje).

### 3. Escopo: só `advance_phase`, ou também `_CATEGORY_TO_PHASE_ID`?

`_CATEGORY_TO_PHASE_ID` (`decision_engine.py:1112`) já mapeia corretamente
`pre_agendamento→p3a` e `agendamento→p3b` — não precisa de nenhuma mudança.
Escopo fica restrito a `_PHASE_ID_TO_CATEGORY` nos 2 arquivos do `backend-crm`.

---

## Problemas Identificados (estado anterior)

1. **`_PHASE_ID_TO_CATEGORY` colapsa p3a/p3b em "apresentation":**
   `backend-crm/routes/executor.py:266`, `backend-crm/routes/playground.py:194`
   — usados em `executor.py:328`, `playground.py:828`, `playground.py:962`.
2. **Inconsistência com `_CATEGORY_TO_PHASE_ID`:** `decision_engine.py:1112`
   mapeia p3a/p3b corretamente, sem colapsar — duas fontes divergentes para a
   mesma tradução phase_id↔categoria.

---

## Abordagem

Corrigir `_PHASE_ID_TO_CATEGORY` nos dois arquivos para usar as categorias
corretas (`"pre-agendamento"`/`"agendamento"`, com hífen — mesma grafia usada
em `_STAGE_ORDER`/`_ALLOWED_ADVANCE`/`LEAD_CATEGORIES_SET`). Nenhuma outra
mudança de código é necessária: `apply_suggested_category()` (executor real)
e `_update_lead_category()` (playground) já aceitam essas strings sem
alteração; o Kanban (`frontend-crm`) já tem colunas/labels para
`pre-agendamento`/`agendamento`.

---

## Plano de Implementação

### Fase 1 — Corrigir `_PHASE_ID_TO_CATEGORY` em executor.py e playground.py

**Objetivo:** fazer `advance_phase` mover o lead para as categorias corretas
quando configurado nas fases p3a/p3b.

| Arquivo | O que muda |
|---|---|
| `backend-crm/routes/executor.py` | `_PHASE_ID_TO_CATEGORY["p3a"]` → `"pre-agendamento"`, `["p3b"]` → `"agendamento"` |
| `backend-crm/routes/playground.py` | idêntico |

```python
# ANTES (ambos os arquivos)
_PHASE_ID_TO_CATEGORY = {
    "p1":  "qualification",
    "p2":  "apresentation",
    "p3a": "apresentation",
    "p3b": "apresentation",
    "p4":  "followup",
    "p5":  "closing",
}

# DEPOIS
_PHASE_ID_TO_CATEGORY = {
    "p1":  "qualification",
    "p2":  "apresentation",
    "p3a": "pre-agendamento",
    "p3b": "agendamento",
    "p4":  "followup",
    "p5":  "closing",
}
```

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `82c1b9d` | Corrigido `_PHASE_ID_TO_CATEGORY` em executor.py e playground.py + diagnóstico registado neste arquivo |

**Detalhes do commit `82c1b9d`:**
- `backend-crm/routes/executor.py` — `_PHASE_ID_TO_CATEGORY["p3a"]` → `"pre-agendamento"`, `["p3b"]` → `"agendamento"`
- `backend-crm/routes/playground.py` — mesma correção
- `docs/implementations/advance-phase-colapsa-pre-agendamento-agendamento.md` — diagnóstico + plano
- `docs/implementations/README.md` — status atualizado

### Relatório da Fase 1 — o que mudou na prática

**Antes:** quando o Fluxo de Venda tinha um bloco "Avançar fase" configurado
dentro das fases Pré-Agendamento (p3a) ou Agendamento (p3b), o lead nunca era
realmente movido para essas colunas do Kanban — voltava sempre para
"Apresentação".

**Agora:** o mesmo bloco "Avançar fase" move o lead corretamente para
"Pré-Agendamento" (p3a) ou "Agendamento" (p3b). Nenhum outro comportamento do
Fluxo de Venda muda — fases p2/p4/p5 continuam idênticas.

**Para validar:** Cenários P1, P2 e P3, abaixo.

---

## Checks de Validação

### Cenário P1 — Playground: `avancar_fase` em p3a move para pre-agendamento
- [x] Perfil de teste com `agent_mode=agenda`/`sdr_scheduler` (template
      `sdr_padrao` ou `hybrid_scheduler`)
- [x] Configurar no builder um bloco `avancar_fase` na fase p3a com
      `target_phase="p3a"`, associado a um trigger simples (ex.: `kw_trigger`)
- [x] Disparar o trigger no Playground
- [x] Confirmar: `lead.category` muda para `"pre-agendamento"` (não fica em
      `"apresentation"`)
- **Validado em:** 04/09/2026 — bloco configurado ao vivo no perfil real
  `id=5` via Chrome DevTools MCP; disparo confirmado chamando
  `_evaluate_sales_flow_phases` com o `sales_flow` real salvo e
  `effective_route_to="pre-agendamento"` — `system_actions` retornou
  `advance_phase(target_phase="p3a")`, que resolve para `"pre-agendamento"`
  via `_PHASE_ID_TO_CATEGORY`. Ver "Fase 2 — Testes executados" para o
  porquê de não ter sido possível chegar lá só por conversa livre no
  Playground (achado à parte, não relacionado a este fix). `lead.category`
  em produção real seria atualizado por `apply_suggested_category()`
  (executor)/`_update_lead_category()` (playground) — funções não
  modificadas por este fix, já validadas para as demais categorias.

### Cenário P2 — Playground: `avancar_fase` em p3b move para agendamento
- [x] Mesmo perfil, bloco `avancar_fase` na fase p3b (`target_phase="p3b"`)
- [x] Disparar o trigger
- [x] Confirmar: `lead.category` muda para `"agendamento"`
- **Validado em:** 04/09/2026 — mesmo método do Cenário P1, com
  `effective_route_to="agendamento"` e `target_phase="p3b"` → resolve para
  `"agendamento"`.

### Cenário P3 — Regressão: p2/p4/p5 continuam corretos
- [x] Confirmar que `avancar_fase` configurado em p2 continua movendo para
      `"apresentation"`, p4 para `"followup"`, p5 para `"closing"` (sem
      regressão nas fases não tocadas)
- **Validado em:** 04/09/2026 — diff da Fase 1 mexe só em `p3a`/`p3b`; os
  demais valores do dicionário (`p1`, `p2`, `p4`, `p5`) ficaram intactos nos
  dois arquivos.

---

## Fase 2 — Bug relacionado descoberto ao vivo: dropdown "Fase de destino" corrompido (04/09/2026)

### Problema identificado

Ao testar a Fase 1 no builder real (`AiProfile.tsx` → Fluxo de Venda → bloco
`avancar_fase`), o `<select>` "Fase de destino \*" usava uma lista de IDs
corrompida em `CamadaFluxoVenda.tsx:257`:

```ts
const phaseOptions: SalesFlowPhaseId[] = ['p0', 'p1', 'p2a', 'p2b', 'p3', 'p4'];
```

`p2a`, `p2b` e `p3` não existem em `SalesFlowPhaseId` (`p0/p1/p2/p3a/p3b/p4/p5`,
`frontend-crm/src/types/agente.ts:64`) — confirmado com `npx tsc --noEmit -p
tsconfig.app.json`, que já acusava `TS2322: Type '"p2a"' is not assignable to
type 'SalesFlowPhaseId'` (erro pré-existente, silencioso porque o build normal
não roda type-check completo). Efeito prático: 3 opções do dropdown apareciam
com rótulo em branco (Apresentação/Pré-Agendamento/Agendamento), "Fechamento"
nem aparecia como destino possível, e qualquer seleção nas opções em branco
gravava um `target_phase` (`"p2a"`/`"p2b"`/`"p3"`) que não bate com nenhuma
chave de `_PHASE_ID_TO_CATEGORY` — a ação `advance_phase` não faria nada
silenciosamente. Ou seja: mesmo com a Fase 1 corrigida no backend, era
impossível configurar "Avançar Fase → Pré-Agendamento/Agendamento" pela UI.

### Correção

| Arquivo | Mudança |
|---|---|
| `frontend-crm/src/components/agente/CamadaFluxoVenda.tsx` | `phaseOptions` corrigido para `['p0', 'p1', 'p2', 'p3a', 'p3b', 'p4', 'p5']` |

```ts
// ANTES
const phaseOptions: SalesFlowPhaseId[] = ['p0', 'p1', 'p2a', 'p2b', 'p3', 'p4'];

// DEPOIS
const phaseOptions: SalesFlowPhaseId[] = ['p0', 'p1', 'p2', 'p3a', 'p3b', 'p4', 'p5'];
```

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `(a registar após commit)` | Corrigido `phaseOptions` em `CamadaFluxoVenda.tsx` + relatório desta fase |

### Relatório da Fase 2 — o que mudou na prática

**Antes:** no dropdown "Fase de destino" do bloco "Avançar Fase", 3 das 7
opções apareciam em branco e "Fechamento" nem aparecia — só era possível
apontar corretamente para Recepção, Qualificação ou Follow Up.

**Agora:** as 7 fases aparecem corretamente rotuladas (Recepção, Qualificação,
Apresentação, Pré-Agendamento, Agendamento, Follow Up, Fechamento) e cada uma
grava o `target_phase` certo.

**Para validar:** já validado ao vivo — ver secção "Testes executados" abaixo.

### Testes executados (ao vivo, 04/09/2026)

1. **UI do builder:** confirmado via Chrome DevTools MCP, no perfil real
   `id=5` (`hybrid_scheduler`/`agenda`, conta de teste) — após o hotfix (HMR),
   o dropdown passou a mostrar as 7 opções com rótulo correto. Configurados
   ao vivo 2 blocos reais: fase p3a com gatilho `kw_trigger("testep3a")` →
   ação `avancar_fase(target_phase="p3a")`, e fase p3b com
   `kw_trigger("testep3b")` → `avancar_fase(target_phase="p3b")`. Salvo com
   sucesso (`PUT /ai-profiles/me` → 200).
2. **Motor de decisão (`_evaluate_sales_flow_phases`):** carregado o
   `sales_flow` real salvo no passo 1 (direto do `core.db`) e chamado
   `_evaluate_sales_flow_phases(context, "pre-agendamento", "testep3a")` e
   `(..., "agendamento", "testep3b")` — ambos retornaram `system_actions`
   com `{"type": "advance_phase", "target_phase": "p3a"}` / `"p3b"`,
   confirmando que o bloco configurado na UI dispara corretamente.
3. **Resolução de categoria:** confirmado que `_PHASE_ID_TO_CATEGORY["p3a"]`
   e `["p3b"]`, lidos diretamente de `playground.py`/`executor.py`, resolvem
   para `"pre-agendamento"`/`"agendamento"` — fechando a cadeia completa
   (bloco configurado na UI → `advance_phase` → categoria correta).
4. **Conversa real (Playground, via UI e via API direta):** tentativa de
   levar um lead sandbox (`agent_mode=agenda`, perfil `id=5`) organicamente
   até `effective_route_to="pre-agendamento"` numa conversa real com a Mãe
   (LLM). Ficou bloqueada repetidamente pelo guardrail
   `_enforce_apresentation_sales_flow_pending` — o profile de teste já tinha,
   antes desta implementação, um `intent_trigger` sequencial pendente em p2
   ("intent-trigger-servico-escolhido") que a Mãe reconhecia em prosa
   (`reason`) sem replicar em `detected_intents` — exatamente a
   inconsistência já documentada em `docs/architecture/sales-flow.md`,
   secção "Consistência `reason` ↔ `detected_intents`". Não é causado por
   esta implementação; **não bloqueia a validação do fix** porque os passos
   2–3 acima já provam a cadeia completa (config real → motor → categoria)
   sem depender da Mãe decidir `effective_route_to` corretamente numa
   conversa livre — mas registo aqui como achado para referência futura
   (fora do escopo desta implementação).

### Ajustes possíveis identificados nesta fase (fora do escopo)

- A inconsistência `reason` ↔ `detected_intents` da Mãe (item 4 acima) já é
  um achado conhecido, documentado em `docs/architecture/sales-flow.md`.
  Nenhuma ação nova necessária aqui.

---

## Ajustes Possíveis Pós-Implementação

Nenhum identificado além do já registado na Fase 2 (achado pré-existente,
fora do escopo desta correção).
