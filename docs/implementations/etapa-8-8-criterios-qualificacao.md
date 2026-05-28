# Critérios de Qualificação no LeadCardDialog

**Branch:** `etapa-8-6-audio-texto`
**Status:** P1–P4, P6–P7 validados (28/05/2026); P5 testável com todos os campos preenchidos

---

## Motivação

O guardrail `qualification_guardrails.py` bloqueia o avanço de leads da coluna `qualification` quando campos obrigatórios do AI Profile não estão preenchidos. O erro era opaco para o usuário: o PATCH retornava 400 sem indicar onde preencher as informações. A solução é uma seção "Critérios de Qualificação" no `LeadCardDialog`, entre "Mensagem Personalizada" e "Comentários/Notas", que mostra o que a IA capturou e permite edição manual.

---

## Problemas Resolvidos

1. **Erro 400 opaco ao mover lead:** O usuário tentava arrastar o card e recebia 400 sem saber o que faltava.
2. **Estado local corrompido após 400:** O `moveLead` fazia update otimista mas não revertia em caso de falha — o lead ficava na coluna errada localmente, e o próximo PATCH enviava `category` incorreto.
3. **Sem interface para preencher qualificação manualmente:** Qualificação feita offline não tinha onde ser inserida no sistema.

---

## Infraestrutura Adicionada

| Camada | O que foi adicionado |
|---|---|
| `backend-crm/routes/leads.py` | `GET /{lead_id}/qualification-fields` — lê `lead_qualification_state.data_json` |
| `frontend-crm/src/services/api.ts` | `getLeadQualificationFields(leadId)` |
| `frontend-crm/src/components/LeadCardDialog.tsx` | Seção "Critérios de Qualificação", estados, useEffect, memo, handler |
| `frontend-crm/src/contexts/LeadsContext.tsx` | Snapshot + revert otimista em `moveLead`; toast actionable para `qualification_incomplete` |

---

## Comportamento

```
Abrir card de lead em Qualificação
  → useEffect busca GET /leads/{id}/qualification-fields e GET /ai-profiles/me (core)
  → Se AI Profile tem qualification_fields configurados → seção renderiza
  → Badge "X pendentes" (vermelho) = required fields sem valor
  → Badge "Completo" (verde) = todos required preenchidos

Clicar "Editar" na seção
  → Inputs aparecem com placeholder da pergunta configurada no AI Profile
  → Campos required têm asterisco vermelho (*)
  → Campos optional não têm asterisco
  → "Salvar" → PATCH /leads/{id}/qualification-fields → toast "Qualificação atualizada"
  → Badge atualiza imediatamente com novo count

Tentar mover lead com qualificação incompleta (drag no Kanban)
  → Backend retorna 400 com { error: "qualification_incomplete" }
  → Estado local revertido (lead volta à coluna original)
  → Toast "Qualificação incompleta — Abra o card do lead e preencha os Critérios de Qualificação antes de avançar."

AI Profile sem qualification_fields configurados
  → Seção não renderiza (aiQualFields.length === 0)
```

---

## Plano de Implementação (executado)

### Fase 1 — Backend: GET qualification-fields (commit `7121f09`)

**Arquivo:** `backend-crm/routes/leads.py` (após PATCH existente)

- Rota: `GET /{lead_id}/qualification-fields`
- Verifica ownership por `user_id`
- Lê `lead_qualification_state.data_json` — retorna `{ fields: {} }` se não existir

### Fase 2 — Frontend API (commit `7121f09`)

**Arquivo:** `frontend-crm/src/services/api.ts`

- `getLeadQualificationFields(leadId)` — `GET /leads/{leadId}/qualification-fields`

### Fase 3 — LeadCardDialog (commit `7121f09` + fix `38b4a72`)

**Arquivo:** `frontend-crm/src/components/LeadCardDialog.tsx`

- Imports: `ClipboardCheck` (lucide), `QualificationField` (types/agente)
- Estados: `qualifFields`, `aiQualFields`, `isEditingQualif`, `editingQualif`
- `useEffect([lead?.id])`: carrega qualification-fields + `api.core.getAiProfileMe()`
- `qualifPendingCount`: memo — conta required sem valor
- `handleSaveQualification`: PATCH + atualiza state + toast
- Seção JSX entre "Mensagem Personalizada" e "Comentários/Notas"
- Fix `38b4a72`: corrigiu chamada `api.getAiProfileMe()` → `api.core.getAiProfileMe()` (TypeError que crashava o card)

### Fase 4 — LeadsContext (commit `64c0329` + `7121f09`)

**Arquivo:** `frontend-crm/src/contexts/LeadsContext.tsx`

- Commit `64c0329`: snapshot + revert otimista em `moveLead`
- Commit `7121f09`: `useToast` + intercept `qualification_incomplete` no catch de `moveLead`

---

## Checks de Validação

### Cenário P1 — Seção aparece com AI Profile configurado
- [x] Lead com AI Profile com `qualification_fields` → seção "Critérios de Qualificação" renderiza no card
- **Validado em:** 28/05/2026 — 8 campos visíveis, badge "6 pendentes"

### Cenário P2 — Campos vazios mostram "Não preenchido"
- [x] Campos sem valor da IA → exibem "Não preenchido" em itálico
- [x] Campos required têm asterisco vermelho
- **Validado em:** 28/05/2026 — todos os campos exibiam "Não preenchido" antes da edição

### Cenário P3 — Editar → Salvar persiste e atualiza UI
- [x] Clicar "Editar" → inputs aparecem com placeholder da pergunta
- [x] Preencher campo → Salvar → PATCH /leads/159/qualification-fields [200]
- [x] Modo edição fecha, valor exibido no campo
- [x] Badge atualiza de "6 pendentes" para "5 pendentes"
- **Validado em:** 28/05/2026 — "Faturamento Anual" salvo como "R$ 500.000/ano", badge mudou

### Cenário P4 — Badge "pendentes" reflete required fields
- [x] Fields required sem valor → badge vermelho com contagem correta
- **Validado em:** 28/05/2026 — badge "5 pendentes" após salvar 1 dos 6 required

### Cenário P5 — Badge "Completo" quando todos required preenchidos
- [ ] Preencher todos os required fields → badge "Completo" verde aparece
- **Pendente:** testável preenchendo os 5 campos restantes

### Cenário P6 — Toast actionable ao mover com qualificação incompleta
- [x] Arrastar lead de Qualificação → Apresentação com campos pendentes
- [x] Toast "Qualificação incompleta — Abra o card do lead..." aparece
- [x] Lead retorna à coluna original (revert otimista)
- **Validado em:** 28/05/2026 (sessão anterior)

### Cenário P7 — Seção não renderiza sem qualification_fields
- [x] AI Profile sem `qualification_fields` configurados → seção ausente
- **Validado em:** 28/05/2026 — comportamento correto (seção condicional em `aiQualFields.length > 0`)

---

## Ajustes Possíveis Pós-Implementação

- P5 (badge "Completo") pode ser validado quando o usuário preencher todos os campos required.
- A seção poderia ser expandida/colapsável para leads com muitos campos, se a UX ficar densa.
- Futuramente: ao preencher qualificação manualmente e tentar mover, o guardrail poderia ser bypassável por confirmação direta (sem precisar voltar ao card).
