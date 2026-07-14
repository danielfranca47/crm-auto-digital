# Nome do lead: companyName deixa de ser obrigatório sozinho

**Branch:** `main`
**Status:** Em andamento

---

## Motivação

`leads.companyName` é `NOT NULL` no banco (`backend-crm/database.py:873`) e obrigatório na validação Pydantic (`backend-crm/models.py:9`). Isso força os 5 pontos de criação de lead do sistema a inventar placeholders quando não sabem o nome da empresa: `"WhatsApp inbound"` (inbound WhatsApp), `"Sem nome"` (planilha/Maps), `"Empresa Teste"` (playground).

Causa raiz do problema: `backend-executors/app/services/decision_engine.py` monta o contexto do prompt da IA com `_safe_get(lead, "contactName", "companyName", "name")` (9 ocorrências, ex. linha 1464). Quando `contactName` é `NULL` (comum em leads inbound sem nome capturado), o fallback cai em `companyName` — que pode ser literalmente `"WhatsApp inbound"`, vazando para o comportamento da IA como se fosse um nome real.

Comportamento desejado: `companyName` deixa de ser obrigatório sozinho. Nova regra: pelo menos um entre `companyName` e `contactName` deve estar preenchido. Os 5 pontos de criação param de fabricar nomes falsos, gravando `NULL` quando realmente não sabem.

Decisões de produto:
- **Formulário manual (`NewLeadModal`)**: regra OR explícita — telefone sempre obrigatório, Empresa OU Nome do contato.
- **Prioridade de exibição** quando só um dos dois existe: nome do contato primeiro (`contactName || companyName`).

---

## Problemas Identificados (estado anterior)

1. **`companyName TEXT NOT NULL`** — `backend-crm/database.py:873`.
2. **`Lead.companyName: str` obrigatório sem default** — `backend-crm/models.py:9`.
3. **Placeholder `"WhatsApp inbound"`** — `backend-crm/services/whatsapp_inbound/guardrail.py:28`.
4. **Placeholder `"Sem nome"`** — `backend-crm/automations/assistente_ia/processor.py:123` (spreadsheet import / Maps).
5. **Placeholder fixo `"Empresa Teste"`** — `backend-crm/routes/playground.py:231`.
6. **`LeadsContext.tsx:83`** (frontend) força `companyName: raw.companyName || 'Empresa sem nome'`, mascarando qualquer fallback `companyName || contactName` já existente em outros componentes.
7. **`NewLeadModal.tsx`** exige ambos `companyName` e `contactName` preenchidos (não "pelo menos um").
8. Vários pontos de exibição (`LeadCard.tsx:122`, `KanbanBoard.tsx:121,459`, `SearchAutocomplete.tsx:39`, `ProspectionCard.tsx:85`, `FollowUpCenter.tsx`) concatenam ou buscam em `lead.companyName` sem tratar `null`.

---

## Abordagem

```
Criação de lead (5 pontos de entrada) → não sabe nome da empresa?
  → grava NULL em vez de inventar placeholder
  → banco garante (CHECK) que companyName OU contactName está preenchido
  → API (Pydantic) valida o mesmo na criação manual
  → frontend exibe contactName || companyName || "Lead sem nome"
```

Migração de banco: SQLite não suporta `ALTER COLUMN`. Segue o precedente já existente em `_migrate_appointments_lead_nullable()` (`database.py:566-616`) — rebuild de tabela com `CREATE TABLE ... _new` → `INSERT ... SELECT` → `DROP` → `RENAME`. `leads` tem 7 tabelas filhas com `ON DELETE CASCADE` e `PRAGMA foreign_keys = ON` ativo por padrão — a migração desliga `PRAGMA foreign_keys` durante o rebuild para não disparar cascade no `DROP TABLE leads`.

---

## Plano de Implementação

### Fase 1 — Migração de banco: rebuild de `leads` com CHECK constraint

**Objetivo:** `companyName` aceita `NULL`, com CHECK garantindo `companyName` OU `contactName` preenchido.

| Arquivo | O que muda |
|---|---|
| `backend-crm/database.py` | Nova função `_migrate_leads_company_or_contact()`; chamada em `init_db()` |

```python
# ANTES
companyName TEXT NOT NULL,

# DEPOIS
companyName TEXT,
...
CHECK (TRIM(COALESCE(companyName,'')) != '' OR TRIM(COALESCE(contactName,'')) != '')
```

### Fase 2 — Pydantic: `Lead.companyName` opcional + validação cruzada

**Objetivo:** `POST /api/leads` aceita omitir `companyName`, mas recusa se nem `companyName` nem `contactName` vierem.

| Arquivo | O que muda |
|---|---|
| `backend-crm/models.py` | `Lead.companyName: Optional[str] = None` + `model_validator` cruzado |

### Fase 3 — Os 5 pontos de criação de lead param de inventar placeholder

**Objetivo:** nenhum ponto de criação grava texto fabricado quando não sabe o nome.

| Arquivo | O que muda |
|---|---|
| `backend-crm/services/whatsapp_inbound/guardrail.py` | remove placeholder `"WhatsApp inbound"`; fallback final = telefone |
| `backend-crm/automations/assistente_ia/processor.py` | remove placeholder `"Sem nome"` |
| `backend-crm/routes/playground.py` | `companyName=NULL`, `contactName="Lead de Teste"` |
| `backend-crm/routes/leads.py` (`criar_lead`, `atualizar_lead_parcial`) | `try/except sqlite3.IntegrityError` → 400 |

### Fase 4 — Frontend: tipos (`crm.ts`)

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/types/crm.ts` | `Lead.companyName`/`contactName` → `string \| null` |

### Fase 5 — Frontend: `LeadsContext.tsx` para de forçar placeholder

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/contexts/LeadsContext.tsx` | remove `|| 'Empresa sem nome'`, usa `??` |

### Fase 6 — Frontend: `NewLeadModal.tsx` (regra OR explícita)

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/components/NewLeadModal.tsx` | telefone obrigatório + (empresa OU contato); remove `required` fixo |

### Fase 7 — Frontend: pontos de exibição sem fallback

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/utils/leadDisplayName.ts` (novo) | helper `contactName \|\| companyName \|\| "Lead sem nome"` |
| `LeadCard.tsx`, `KanbanBoard.tsx`, `SearchAutocomplete.tsx`, `ProspectionCard.tsx`, `FollowUpCenter.tsx` | usam o helper |

### Fase 8 — Regressão ponta a ponta

Sem código novo — suíte de testes + roteiro manual completo.

---

## Checks de Validação

### Cenário C1 — Migração de banco preserva dados e aplica CHECK
- [ ] Rodar suíte `test_leads_company_or_contact_migration.py`
- [ ] `INSERT (companyName, contactName) VALUES (NULL, NULL)` falha
- [ ] `INSERT (companyName, contactName) VALUES (NULL, 'Ana')` funciona

### Cenário C2 — WhatsApp inbound sem nome usa telefone como fallback
- [ ] Simular webhook UazAPI sem `senderName` e sem nome anterior
- [ ] Confirmar lead criado com `contactName = telefone`, `companyName = NULL`

### Cenário P1 — Novo Lead manual só com contato
- [ ] Abrir "Novo Lead", preencher telefone + nome do contato, deixar empresa vazia
- [ ] Salvar com sucesso, aparece no Kanban só com o nome do contato

### Cenário P2 — Novo Lead manual só com empresa
- [ ] Preencher telefone + empresa, deixar nome do contato vazio
- [ ] Salvar com sucesso

### Cenário P3 — Novo Lead sem nenhum dos dois é bloqueado
- [ ] Preencher só telefone, tentar salvar
- [ ] Botão permanece desabilitado / mensagem de erro visível

### Cenário C3 — Exibição sem "null"/"undefined"
- [ ] Kanban, busca, DragOverlay, FollowUp Center com leads só-empresa/só-contato/ambos
- [ ] Nenhum lugar mostra `"null"` ou `"undefined"`

---

## Ajustes Possíveis Pós-Implementação

- Migrar os demais pontos que já fazem `companyName || contactName` (`LeadCardDialog.tsx`, `ProspectConfirmModal.tsx`, `Dashboard.tsx`, `FollowUpEdit.tsx`) para o helper `leadDisplayName`, por consistência (cosmético, fora do escopo mínimo).
- `find_existing_lead()` em `processor.py:148` tem comparação morta com `"Sem nome"` que pode ser simplificada (`if companyName:`), não obrigatório.
