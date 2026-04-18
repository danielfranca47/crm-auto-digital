# Histórico: correções para erro ao acionar follow-up com qualificação incompleta

**Data:** 2026-04-18  
**Branch:** `test-frontend`  
**Commits:** `7998ec2`, `3804d92`

---

## Contexto

Ao mover um card de **Apresentação → Follow-up** no Kanban, o modal "Iniciar follow-up assistido" é exibido. O operador preenche os campos (sessão aconteceu, resultado, observação) e clica em **Salvar e iniciar follow-up**.

O sistema estava retornando `400 qualification_incomplete` mesmo após a interação ser preenchida corretamente, bloqueando a transição.

---

## Sintoma original

```
POST http://localhost:8000/api/leads/start-followup
Status: 400 Bad Request

{
  "detail": {
    "error": "qualification_incomplete",
    "missing_fields": ["custom_precos_de_massagens"],
    "message": "Não é possível iniciar follow-up: qualification incompleta"
  }
}
```

O frontend apenas exibia um toast de erro e fechava o fluxo. O operador não tinha como preencher os dados faltantes sem sair do modal.

**Causa raiz:** o lead foi qualificado por ligação telefônica — a IA nunca extraiu os campos de qualificação via chat, portanto `lead_qualification_state.data_json` estava incompleto ou zerado.

---

## Tentativa 1 — Campos de qualificação no modal (commit `7998ec2`)

### O que foi feito

**Backend (`backend-crm/routes/leads.py`):**
- Quando `can_advance_from_qualification` retorna `False`, o backend passa a buscar o AI Profile do usuário via `fetch_core_ai_profile`
- Cruza os `missing_fields` (chaves) com os metadados de `qualification_fields` do AI Profile
- Devolve `missing_fields_detail: [{key, label, question}]` no corpo do 400 para que o frontend saiba como exibir os campos com labels legíveis
- Nova rota `PATCH /api/leads/{lead_id}/qualification-fields` que recebe `{"fields": {key: value}}` e chama `upsert_qualification_state` para persistir os valores e recalcular o score 4P

**Frontend (`frontend-crm/src/components/FollowUpTransitionModal.tsx`):**
- Ao capturar `qualification_incomplete`, o modal permanece aberto e exibe inputs para os campos faltantes
- `canSubmit` passa a exigir que todos os `missingFields` estejam preenchidos
- No segundo submit: chama `PATCH qualification-fields` primeiro, depois repete `POST start-followup`

**Frontend (`frontend-crm/src/services/api.ts`):**
- Novo método `patchLeadQualificationFields(leadId, fields)`

**Backend (`backend-crm/models.py`):**
- Novo modelo `QualificationPatchPayload(fields: Dict[str, Any])`

### Problema remanescente

Em um segundo teste, o campo exibido foi **`score_0_of_12_below_threshold_6`** — um sentinel interno da guardrail, não um campo real. O sentinel indica que o score 4P do lead está abaixo do limiar (0/12 < 6), mas não é preenchível.

O frontend tratava o sentinel como campo normal, exibia um input com o próprio nome como label/placeholder, e o operador não conseguia habilitar o botão (ou, se habilitava, o PATCH salvava `{"score_0_of_12_below_threshold_6": "..."}` no `data_json`, valor que não afeta o cálculo do score). O `start-followup` continuava falhando silenciosamente — **nenhuma chamada de rede aparecia no DevTools** além das rotas de polling.

---

## Tentativa 2 — Tratar sentinel de score separadamente (commit `3804d92`)

### Raiz do segundo problema

`can_advance_from_qualification` em `services/qualification_guardrails.py` realiza duas verificações em sequência:

1. **Campos obrigatórios ausentes** — retorna os campos faltantes como lista de chaves reais  
2. **Score 4P mínimo** (só avalia se a verificação 1 passou) — retorna o sentinel `score_{atual}_of_12_below_threshold_{limiar}` se `qualification_total_score < threshold`

O sentinel nunca deve ser exposto como campo preenchível. O score é recalculado automaticamente por `upsert_qualification_state` ao salvar os campos 4P reais (`decision_role`, `urgency`, `budget_or_price_acceptance`, `availability_window`).

### O que foi feito

**Backend (`backend-crm/routes/leads.py`):**
- Separa `missing_fields` em dois grupos:
  - `_real_missing`: chaves sem `_below_threshold_` → campos reais ausentes
  - `_score_failure`: chaves com `_below_threshold_` → falha de pontuação
- Para `_score_failure`, popula `missing_fields_detail` com os campos do AI Profile que têm `mode=required` ou `mode=optional` (i.e., os campos que o operador deve preencher para que o score suba)
- Fallback: se o AI Profile não tiver `qualification_fields` configurados, usa os 4 campos 4P padrão: `decision_role`, `urgency`, `budget_or_price_acceptance`, `availability_window`
- Adiciona `score_failure: true` no corpo do 400

**Frontend (`frontend-crm/src/components/FollowUpTransitionModal.tsx`):**
- Estado `scoreFailure` para diferenciar os dois casos na UI
- Mensagem diferenciada quando `score_failure=true`: *"A qualificação deste lead está incompleta (pontuação insuficiente). Preencha os dados abaixo para continuar:"*
- `resetState` limpa `scoreFailure`

### Fluxo final após correção

```
1. Operador preenche os campos do modal e clica em "Salvar e iniciar follow-up"
   ↓
2. POST /api/leads/start-followup
   ├─ Se 200 OK → lead movido para follow-up ✓
   └─ Se 400 qualification_incomplete
      ├─ missing_fields_detail = campos reais OU campos 4P (score failure)
      ├─ score_failure = true/false
      └─ Modal permanece aberto com inputs para os campos pendentes
         ↓
3. Operador preenche os campos de qualificação exibidos
   ↓
4. Botão habilitado → clica novamente
   ↓
5. PATCH /api/leads/{id}/qualification-fields
   → upsert_qualification_state → salva data_json + recalcula score 4P
   ↓
6. POST /api/leads/start-followup (segunda tentativa)
   ├─ Se 200 OK → lead movido para follow-up ✓
   └─ Se ainda 400 → repete o passo 2 (exibe novos campos pendentes)
```

---

## Tentativa 3 — Corrigir campos exibidos no score failure (commit seguinte)

### Sintoma

Após a Tentativa 2, o modal passou a exibir os campos de qualificação corretos (sem o sentinel). Porém ao preencher os campos e clicar "Salvar e iniciar follow-up", **nada mais acontecia** — o modal ficava aberto com os campos resetados e vazios.

### Causa raiz

O fluxo era um **loop infinito silencioso**:

1. 1º submit → `POST /start-followup` → `400 score_failure` → modal exibe campos custom do AI Profile (ex: "Quer agendar", "Disponibilidade", "Preços de massagens")
2. Operador preenche os campos → `PATCH /qualification-fields` salva os valores
3. `upsert_qualification_state` chama `compute_4p_scores()` — que **só lê** `decision_role`, `urgency`, `budget_or_price_acceptance`, `availability_window`
4. Campos custom ignorados → score permanece 0 → 2º `POST /start-followup` ainda falha com o mesmo sentinel
5. Catch block: `setMissingFields(...)` + `setQualificationValues({})` → modal fica aberto com campos vazios
6. Do ponto de vista do operador: "nada acontece"

A origem estava na lógica do branch `_score_failure` em `routes/leads.py`: quando o AI Profile tem `qualification_fields` configurados com `mode=required/optional` (campos de negócio custom), esses campos eram exibidos ao operador. Mas `compute_4p_scores()` é hardcoded para ler apenas os 4 campos 4P — campos custom nunca afetam o score.

### O que foi feito

**Backend (`backend-crm/routes/leads.py`):**
- Substituída a lógica do branch `_score_failure` que exibia campos custom do AI Profile
- Agora **sempre exibe os 4 campos 4P reais** com perguntas orientativas:
  - `decision_role` — "Papel na decisão de compra"
  - `urgency` — "Urgência / necessidade"
  - `budget_or_price_acceptance` — "Orçamento / aceitação de preço"
  - `availability_window` — "Janela de disponibilidade"
- Com qualquer texto não-vazio preenchido nesses campos, o score mínimo é ≥8 (cada campo não-negativo pontua 2), acima do threshold padrão de 6

### Fluxo corrigido

```
1. Operador preenche o modal e clica "Salvar e iniciar follow-up"
   ↓
2. POST /api/leads/start-followup
   ├─ Se 200 OK → lead movido para follow-up ✓
   └─ Se 400 qualification_incomplete
      ├─ score_failure=false → missing_fields_detail = campos reais ausentes
      └─ score_failure=true  → missing_fields_detail = 4 campos 4P com perguntas orientativas
         ↓
3. Operador preenche os 4 campos 4P
   ↓
4. Botão habilitado → clica novamente
   ↓
5. PATCH /api/leads/{id}/qualification-fields
   → upsert_qualification_state → salva data_json + recalcula score 4P (agora ≥8)
   ↓
6. POST /api/leads/start-followup (2ª tentativa)
   └─ 200 OK → lead movido para follow-up ✓
```

---

## Arquivos modificados

| Arquivo | Mudança |
|---|---|
| `backend-crm/models.py` | `QualificationPatchPayload` |
| `backend-crm/routes/leads.py` | 400 enriquecido com `missing_fields_detail` / `score_failure`; rota `PATCH /{lead_id}/qualification-fields`; branch `_score_failure` corrigido para sempre exibir campos 4P |
| `frontend-crm/src/services/api.ts` | `patchLeadQualificationFields` |
| `frontend-crm/src/components/FollowUpTransitionModal.tsx` | etapa de qualificação + diferenciação score vs. campos |

---

## Observações para manutenção futura

- O sentinel `score_X_of_12_below_threshold_Y` **nunca deve ser exposto como campo preenchível** na UI. Sempre filtrá-lo por `_below_threshold_` antes de montar `missing_fields_detail`.
- `compute_4p_scores()` é hardcoded para ler apenas `decision_role`, `urgency`, `budget_or_price_acceptance`, `availability_window`. **Campos custom do AI Profile não afetam o score 4P**, independentemente de seu `mode`. Portanto, a falha de score só pode ser resolvida preenchendo os 4 campos 4P — não campos de negócio custom.
- `upsert_qualification_state` recalcula o score 4P automaticamente ao persistir — não é necessário chamar `compute_4p_scores` manualmente.
- A rota `PATCH /api/leads/{id}/qualification-fields` é pública (auth obrigatória, mas sem service token). Ela só deve receber os valores extraídos do operador e não deve sobrescrever campos já existentes com strings vazias — o `merge_data` em `qualification_state.py` já garante isso (valores vazios não substituem valores preenchidos).
- Para leads qualificados por ligação ou presencialmente (fora do chat), este é o fluxo correto de entrada de dados de qualificação.
