# etapa-10 — Ciclo de Vida do `origin`: Confirmação de Prospecção Outbound

**Branch:** `etapa-9-planos-limites`
**Status:** Todas as fases validadas — pronto para graduação

---

## Motivação

O campo `origin` de um lead era definido na criação e nunca atualizado automaticamente. O objetivo é torná-lo um estado operacional real:

- Lead criado (manual, Maps, inbound) → `origin` neutro (`'Manual'` ou vazio)
- Job `whatsapp.send.local` confirmado → `origin = 'outbound'` automático
- Drag Kanban "to-prospect" → "qualification" → modal pergunta se já prospectou; se sim: `origin = 'outbound'` + log no histórico

---

## Plano de Implementação

### Fase 1 — Backend: `_handle_whatsapp_report` seta `origin='outbound'`

| Arquivo | O que muda |
|---|---|
| `backend-crm/services/jobs_service.py` | Dentro de `_handle_whatsapp_report`, após `apply_suggested_category()`, UPDATE lead `origin='outbound'` se ainda neutro |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `1a5527c` | fix(jobs): setar origin=outbound ao confirmar job whatsapp.send.local |

### Checks Fase 1

#### Cenário E1 — Job WhatsApp confirma outbound
- [x] Lead com `origin='Manual'` ou `origin=''` existe
- [x] Job `whatsapp.send.local` completa com `status=completed`
- [x] `SELECT origin FROM leads WHERE id=?` retorna `'outbound'`
- [x] Lead com `origin='whatsapp_inbound'` NÃO é sobrescrito
- **Validado em:** 05/06/2026 — leads 201 (origin='') e 203 (origin='Manual') actualizados para 'outbound'; lead 204 (origin='whatsapp_inbound') não foi alterado

#### Cenário E2 — Idempotência (lead já outbound)
- [x] Lead com `origin='outbound'` já existente
- [x] Novo job completa
- [x] `origin` permanece `'outbound'` (UPDATE não actua por cause da condição)
- **Validado em:** 05/06/2026 — lead 202 (origin='outbound') permaneceu 'outbound' após novo job completado

---

### Fase 2 — Backend: PATCH `/leads/{id}` aceita `prospection_context`

| Arquivo | O que muda |
|---|---|
| `backend-crm/models.py` | `LeadUpdate` recebe campo `prospection_context: Optional[str] = None` |
| `backend-crm/routes/leads.py` | Handler PATCH: pop `prospection_context` antes do loop de campos; após UPDATE, inserir em `prospection_logs` se presente |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `a9c4bea` | feat(leads): PATCH aceita prospection_context e escreve em prospection_logs |

### Checks Fase 2

#### Cenário E3 — PATCH com prospection_context
- [x] `PATCH /api/leads/{id}` com `{ "origin": "outbound", "prospection_context": "Liguei e agendamos reunião" }`
- [x] `leads.origin` atualizado para `'outbound'`
- [x] `prospection_logs` tem registo `action='manual_outbound'`, `notes='Liguei...'`
- [x] Campo `prospection_context` NÃO aparece como coluna em `leads` (não deve dar erro SQL)
- **Validado em:** 05/06/2026 — lead 205: origin='outbound', log id=23715 action='manual_outbound' com notas correctas
- **Bug corrigido:** `routes/leads.py` linha 909 — INSERT em `prospection_logs` usava `created_at` mas coluna chama-se `createdAt`; corrigido removendo a coluna do INSERT (usa DEFAULT)

---

### Fase 3 — Frontend: Modal de confirmação no Kanban

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/components/ProspectConfirmModal.tsx` | Novo: modal de 2 passos (sim/não → contexto) |
| `frontend-crm/src/components/KanbanBoard.tsx` | Interceptar drag "to-prospect" → "qualification" se origin neutro; abrir modal |

### Commits Fase 3

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `11657b3` | feat(kanban): modal de confirmação de prospecção ao mover to-prospect → qualification |

### Checks Fase 3

#### Cenário E4 — Modal abre na transição correcta
- [x] Lead com `origin=''` ou `'Manual'` na coluna "À Prospectar"
- [x] Arrastar para "Qualificação" → modal abre com pergunta "Já prospectou?"
- [x] Lead com `origin='outbound'` → move directo sem modal
- **Validado em:** 05/06/2026 — leads 206 (origin='') e 207 (origin='Manual') abriram modal; lead 205 (origin='outbound') moveu directamente sem modal

#### Cenário E5 — Confirmação de prospecção manual
- [x] Clicar "Sim" → campo de contexto aparece (step 2)
- [x] Preencher contexto (mín. 10 chars) → Confirmar
- [x] Lead move para "Qualificação", `origin='outbound'`, `prospection_logs` tem registo
- [x] Botão desabilitado se texto < 10 chars
- **Validado em:** 05/06/2026 — lead 206: category='qualification', origin='outbound'; log id=23726 action='manual_outbound'; aviso "Mínimo de 10 caracteres." confirado; botão disabled com texto curto

#### Cenário E6 — Aguardar inbound
- [x] Clicar "Não, a aguardar resposta" → lead move para "Qualificação" sem alterar `origin`
- [x] Fechar modal com [X] → lead NÃO move
- **Validado em:** 05/06/2026 — lead 207 "Não": category='qualification', origin='Manual' (não alterado); lead 208 [X]: category='to-prospect', origin='' (não moveu)

---

---

### Fix associado — `model='outbound'` em `_persist_whatsapp_message`

**Commit:** `958b88a`

Durante o diagnóstico detectou-se que mensagens enfileiradas via job `whatsapp.send.local` eram persistidas com `model='manual'` em vez de `model='outbound'`. O orchestrator verifica `model == 'outbound'` para calcular `outbound_present` e decidir o fluxo de resposta — com `'manual'` a verificação falhava silenciosamente, fazendo o bot tratar o lead como contato frio mesmo tendo já sido prospectado.

**Corrigido em:** `backend-crm/services/jobs_service.py` — `_persist_whatsapp_message`.

**Teste:** `backend-crm/tests/test_whatsapp_outbound_message_model.py` — 6 casos:
- `model='outbound'` é persistido em `_persist_whatsapp_message`
- `_handle_whatsapp_report` seta `origin='outbound'` para leads neutros (`''` ou `'Manual'`)
- `origin='whatsapp_inbound'` nunca é sobrescrito
- `origin='outbound'` já existente é idempotente
- Job com `status=failed` não altera `origin`

---

## Notas de risco

- `origin='whatsapp_inbound'` nunca é sobrescrito — a condição `OR origin = 'Manual'` não cobre esse valor
- orchestrator não precisa de alteração — `'outbound'` já cai no caminho `_is_outbound = True`
