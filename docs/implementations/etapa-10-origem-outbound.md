# etapa-10 — Ciclo de Vida do `origin`: Confirmação de Prospecção Outbound

**Branch:** `etapa-9-planos-limites`
**Status:** Fase 3 concluída — aguarda validação

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
- [ ] Lead com `origin='Manual'` ou `origin=''` existe
- [ ] Job `whatsapp.send.local` completa com `status=completed`
- [ ] `SELECT origin FROM leads WHERE id=?` retorna `'outbound'`
- [ ] Lead com `origin='whatsapp_inbound'` NÃO é sobrescrito

#### Cenário E2 — Idempotência (lead já outbound)
- [ ] Lead com `origin='outbound'` já existente
- [ ] Novo job completa
- [ ] `origin` permanece `'outbound'` (UPDATE não actua por cause da condição)

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
- [ ] `PATCH /api/leads/{id}` com `{ "origin": "outbound", "prospection_context": "Liguei e agendamos reunião" }`
- [ ] `leads.origin` atualizado para `'outbound'`
- [ ] `prospection_logs` tem registo `action='manual_outbound'`, `notes='Liguei...'`
- [ ] Campo `prospection_context` NÃO aparece como coluna em `leads` (não deve dar erro SQL)

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
- [ ] Lead com `origin=''` ou `'Manual'` na coluna "À Prospectar"
- [ ] Arrastar para "Qualificação" → modal abre com pergunta "Já prospectou?"
- [ ] Lead com `origin='outbound'` → move directo sem modal

#### Cenário E5 — Confirmação de prospecção manual
- [ ] Clicar "Sim" → campo de contexto aparece (step 2)
- [ ] Preencher contexto (mín. 10 chars) → Confirmar
- [ ] Lead move para "Qualificação", `origin='outbound'`, `prospection_logs` tem registo
- [ ] Botão desabilitado se texto < 10 chars

#### Cenário E6 — Aguardar inbound
- [ ] Clicar "Não, a aguardar resposta" → lead move para "Qualificação" sem alterar `origin`
- [ ] Fechar modal com [X] → lead NÃO move

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
