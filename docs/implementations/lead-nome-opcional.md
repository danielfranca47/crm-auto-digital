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

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `a135ccc` | backend: migração de banco (companyName nullable + CHECK companyName/contactName) |

**Detalhes do commit `a135ccc`:**
- `backend-crm/database.py` — nova função `_migrate_leads_company_or_contact()`, chamada em `init_db()` logo após os `ensure_column` de `leads`. Rebuild de tabela (SQLite não suporta `ALTER COLUMN`), com `PRAGMA foreign_keys = OFF` durante o rebuild (leads tem 7 tabelas filhas com `ON DELETE CASCADE`), checagem de contagem de linhas antes do `DROP TABLE`, e recriação dos 5 índices + a UNIQUE existente.
- `backend-crm/tests/test_leads_company_or_contact_migration.py` — novo: `init_db()` fresco cria `companyName` nullable com CHECK ativo; idempotência (`init_db()` duas vezes); migração a partir de um schema antigo preserva todas as linhas e valores.

### Relatório da Fase 1 — o que mudou na prática

**Antes:** o banco recusava salvar um lead sem nome de empresa, mesmo que o nome do contato já estivesse preenchido — por isso o sistema inventava nomes falsos como `"WhatsApp inbound"` ou `"Sem nome"` só para conseguir gravar.

**Agora:** o banco aceita um lead com só o nome da empresa, só o nome do contato, ou os dois — mas recusa (com erro) se nenhum dos dois vier preenchido. A migração roda automaticamente na próxima subida do servidor `backend-crm` e preserva todos os leads já existentes sem alterar nenhum dado.

**Para validar:** ainda não há cenário manual nesta fase — a mudança é só de banco, os pontos que criam leads (Fase 3) e o formulário (Fase 6) ainda vão continuar preenchendo `companyName` com placeholder até essas fases seguintes serem implementadas. Validação automatizada: os 3 testes novos e a suíte completa de 129 testes já rodaram sem regressão (os 13 erros pré-existentes na suíte — `on_startup`/Pydantic mock/coluna `origin` em teste isolado — já falhavam antes desta mudança, confirmado via `git stash`).

### Fase 2 — Pydantic: `Lead.companyName` opcional + validação cruzada

**Objetivo:** `POST /api/leads` aceita omitir `companyName`, mas recusa se nem `companyName` nem `contactName` vierem.

| Arquivo | O que muda |
|---|---|
| `backend-crm/models.py` | `Lead.companyName: Optional[str] = None` + `model_validator` cruzado |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 2 | `1a552b8` | backend: `Lead.companyName` opcional + `model_validator` exigindo companyName OU contactName |

**Detalhes do commit:**
- `backend-crm/models.py` — `companyName: Optional[str] = None` (era `str` obrigatório); novo `model_validator(mode="after")` que recusa (`ValueError`) quando `companyName` e `contactName` estão ambos vazios/só espaço.
- `backend-crm/tests/test_lead_model_validation.py` — novo: cobre os dois campos ausentes (falha), ambos só espaço (falha), só empresa (ok), só contato (ok), ambos preenchidos (ok).

### Relatório da Fase 2 — o que mudou na prática

**Antes:** `POST /api/leads` recusava (erro 422) qualquer requisição sem `companyName`, mesmo com `contactName` preenchido — a validação Pydantic barrava antes mesmo de chegar no banco.

**Agora:** a API aceita criar um lead só com `companyName`, só com `contactName`, ou os dois — e recusa (422) apenas quando nenhum dos dois vem preenchido (ou vêm só com espaços).

**Para validar:** mudança só no schema de validação da API — ainda não afeta o formulário manual (`NewLeadModal`, Fase 6) nem os outros pontos de criação (Fase 3). Validação automatizada: 5/5 testes novos passaram; suíte completa rodada sem regressão nova (os erros pré-existentes de `on_startup`/encoding de console continuam os mesmos, não relacionados a este código).

### Fase 3 — Os 5 pontos de criação de lead param de inventar placeholder

**Objetivo:** nenhum ponto de criação grava texto fabricado quando não sabe o nome.

| Arquivo | O que muda |
|---|---|
| `backend-crm/services/whatsapp_inbound/guardrail.py` | remove placeholder `"WhatsApp inbound"`; fallback final = telefone |
| `backend-crm/automations/assistente_ia/processor.py` | remove placeholder `"Sem nome"` |
| `backend-crm/routes/playground.py` | `companyName=NULL`, `contactName="Lead de Teste"` |
| `backend-crm/routes/leads.py` (`criar_lead`, `atualizar_lead_parcial`) | `try/except sqlite3.IntegrityError` → 400 |

**Status:** só o item `guardrail.py` (Cenário C2) foi implementado até agora — ver commit abaixo. Os outros 3 itens (`processor.py`, `playground.py`, `routes/leads.py`) continuam pendentes.

### Commits Fase 3 (parcial — WhatsApp inbound)

| # | Commit | O que foi implementado |
|---|---|---|
| 4 | `<preencher>` | backend: `guardrail.py` para de inventar `"WhatsApp inbound"`, contactName cai para o telefone quando não há nome |

**Detalhes do commit:**
- `backend-crm/services/whatsapp_inbound/guardrail.py` — `contact_name` ganha um 4º fallback (`phone_norm`) quando `contact_name`/`sender_name`/`name` não vêm no payload; `company` deixa de ter fallback fixo (`"WhatsApp inbound"` removido), fica `None` quando o payload não informa.
- `backend-crm/tests/test_inbound_guardrail.py` — schema de teste isolado passa a espelhar a migração real (`companyName` nullable + CHECK, em vez do `NOT NULL` hardcoded); novo teste `test_new_lead_without_name_falls_back_to_phone` cobre payload vazio → `companyName IS NULL`, `contactName = telefone`.

### Relatório da Fase 3 (parcial) — o que mudou na prática

**Antes:** todo lead criado automaticamente por uma mensagem de WhatsApp, sem nome de remetente disponível no payload (o caso comum, já que nenhum código lê `pushName`/`senderName` da UazAPI), nascia com `companyName = "WhatsApp inbound"` — um texto fabricado que podia vazar para o prompt da IA como se fosse o nome real da empresa.

**Agora:** esse mesmo lead nasce com `companyName = NULL` e `contactName = <telefone>` — a IA não recebe mais um nome de empresa inventado, e o CHECK do banco (Fase 1) continua satisfeito porque `contactName` sempre tem pelo menos o telefone.

**Para validar:** automatizado — 6/6 testes em `test_inbound_guardrail.py` passaram (5 antigos + 1 novo); suíte completa sem regressão nova. Não testado ao vivo com um webhook real da UazAPI nesta rodada (ver Cenário C2 abaixo).

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

### Commits Fase 6

| # | Commit | O que foi implementado |
|---|---|---|
| 3 | `ce48785` | frontend: `NewLeadModal` exige telefone + (empresa OU contato) em vez dos 3 campos |

**Detalhes do commit:**
- `frontend-crm/src/components/NewLeadModal.tsx` — remove `required` dos campos "Nome" e "Empresa"; novo `canSubmit = phone && (contactName || companyName)` controla o botão "Salvar Lead" e o guard do submit; dica visual ("Preencha ao menos o Nome ou a Empresa") aparece quando os dois estão vazios; ao chamar `api.createLead` diretamente (sem `onSave`), envia `companyName`/`contactName` com `.trim() || null` em vez de string vazia.
- `frontend-crm/src/services/api.ts` — `createLead({ companyName })` passa a aceitar `string | null | undefined` (era `string` obrigatório), refletindo que o backend não exige mais o campo.
- `frontend-crm/src/contexts/LeadsContext.tsx` — `addLead` (usado pelo fluxo padrão do Kanban, `onSave` do modal) passa a normalizar `companyName`/`contactName` com `.trim() || null` em vez de mandar string vazia, mesmo comportamento do caminho direto do modal.

### Relatório da Fase 6 — o que mudou na prática

**Antes:** o formulário "Novo Lead" travava o botão "Salvar" e a validação HTML5 (`required`) enquanto Nome e Empresa não estivessem os dois preenchidos — mesmo já sendo possível salvar só um dos dois no backend (Fases 1 e 2).

**Agora:** o formulário exige telefone sempre, e Nome OU Empresa (pelo menos um). É possível cadastrar um lead manual só com o nome da empresa, só com o nome do contato, ou os dois — mas não com nenhum dos dois (botão continua desabilitado e aparece uma dica). Isso cobre o caso de leads vindos do Google Maps, onde o nome do responsável ainda não é conhecido no momento do cadastro manual.

**Para validar:** testado ao vivo no navegador em 2026-07-29 (ver Checks abaixo). Durante o teste, criar um lead só-com-contato expôs que a Fase 6 sozinha não bastava — o card no Kanban mostrava "Empresa sem nome - Ana QA" (placeholder da Fase 5 ainda ativo) e a busca (`KanbanBoard.tsx` filterLeads) faria `.toLowerCase()` em `companyName` sem tratar `null`. Isso puxou a Fase 5 e parte da Fase 7 para o mesmo commit de validação — ver abaixo.

### Fase 5 (concluída) + Fase 7 (parcial) — corrigidas junto da validação da Fase 6

| Arquivo | O que mudou |
|---|---|
| `frontend-crm/src/contexts/LeadsContext.tsx` | `companyName: raw.companyName \|\| ''` (era `\|\| 'Empresa sem nome'`) |
| `frontend-crm/src/utils/leadDisplayName.ts` (novo) | helper `companyName + contactName` com prioridade `contactName \|\| companyName`, fallback `"Lead sem nome"` |
| `LeadCard.tsx` | título do card usa `leadDisplayName(lead)` |
| `KanbanBoard.tsx` | `DragOverlay` usa `leadDisplayName`; filtro de busca (`filterLeads`) passa a tratar `companyName`/`contactName` nulos/vazios (`(lead.companyName \|\| '').toLowerCase()`) |
| `SearchAutocomplete.tsx` | sugestão de busca usa `leadDisplayName`; comparação do termo tratada com `\|\| ''` |

**Pendente (não corrigido nesta rodada):** `ProspectionCard.tsx` e `FollowUpCenter.tsx` ainda não usam o helper — continuam exibindo só `companyName`/`contactName` isolado sem fallback. Como não fazem parte do fluxo de criação manual testado aqui, ficam para uma fase futura se o mesmo sintoma aparecer lá.

### Fase 8 — Regressão ponta a ponta

Sem código novo — suíte de testes + roteiro manual completo.

---

## Gaps conhecidos (por que ficaram em aberto)

Dois pontos do "Problemas Identificados" (item 3 e parte do item 8) ainda não foram corrigidos porque nenhum dos dois faz parte do fluxo testado nesta rodada (cadastro manual via `NewLeadModal` + exibição no Kanban). São bugs reais, só que em telas/fluxos diferentes — ficam documentados aqui para não se perderem.

### Cenário C2 — Lead criado via WhatsApp inbound

Quando alguém manda mensagem no WhatsApp e ainda não existe lead com aquele telefone, o sistema cria um automaticamente em `backend-crm/services/whatsapp_inbound/guardrail.py:28` (antes da correção):

```python
company = payload.get("company") or "WhatsApp inbound"
```

Ou seja: se não veio nome de empresa nenhum (o normal — WhatsApp não manda "empresa"), o sistema **inventava** o texto literal `"WhatsApp inbound"` como se fosse o nome real da empresa do lead — o mesmo tipo de placeholder falso que as Fases 1/2 eliminaram em outros pontos, só que aqui a troca nunca tinha sido feita.

**Por que importa:** esse texto fabricado vaza para o contexto que a IA usa para conversar com o lead (`backend-executors/.../decision_engine.py`, via `_safe_get(lead, "contactName", "companyName", "name")`) — a IA pode "achar" que o nome da empresa é `"WhatsApp inbound"` e citar isso na conversa.

**Causa raiz confirmada:** nenhum caminho do código hoje extrai o nome do remetente do payload real da UazAPI — `routes/webhooks.py` nunca lê campos como `pushName`/`senderName` do webhook. Por isso `payload.get("contact_name")`, `payload.get("sender_name")` e `payload.get("name")` em `guardrail.py` nunca eram preenchidos na prática: todo lead inbound nascia com `contactName = NULL` e `companyName = "WhatsApp inbound"`.

**Por que ficou em aberto até agora:** exigia simular um webhook de WhatsApp chegando (não dá pra testar clicando no navegador como o cadastro manual).

**Atualização:** corrigido — ver Fase 3 (parcial) e Cenário C2 abaixo. Ainda falta validar com um webhook real da UazAPI (só testado por unit test simulando o payload).

### FollowUp Center — tela de acompanhamento de follow-up

Essa é uma tela diferente do Kanban que foi testado. Ela tem 6 lugares que leem `lead.companyName` direto, sem o tratamento null-safe já aplicado no Kanban (`FollowUpCenter.tsx`, linhas 162, 290, 449, 509, 513, 706). Se um lead só tem `contactName` (o caso que a Fase 6 passou a permitir), essas linhas mostram um espaço em branco ou um avatar com "?" no lugar do nome — não quebra a tela, mas fica visualmente incompleto.

**Por que ficou em aberto:** essa tela não faz parte do cadastro manual — só afetaria um lead sem empresa depois que ele entrasse em follow-up, cenário não exercitado nesta sessão. Preferimos não alterar 6 pontos de código sem confirmar visualmente o problema primeiro, em vez de corrigir "no escuro". Fica para uma fase futura se o mesmo sintoma aparecer lá.

---

## Checks de Validação

### Cenário C1 — Migração de banco preserva dados e aplica CHECK
- [x] Rodar suíte `test_leads_company_or_contact_migration.py`
- [x] `INSERT (companyName, contactName) VALUES (NULL, NULL)` falha
- [x] `INSERT (companyName, contactName) VALUES (NULL, 'Ana')` funciona
- **Validado em:** 2026-07-10 — 3/3 testes passaram (fresh init_db, idempotência, preservação de dados na migração a partir do schema antigo); suíte completa (129 testes) rodada sem regressão nova.

### Cenário C2 — WhatsApp inbound sem nome usa telefone como fallback
- [x] Simular webhook UazAPI sem `senderName` e sem nome anterior
- [x] Confirmar lead criado com `contactName = telefone`, `companyName = NULL`
- **Validado em:** 2026-07-29 — automatizado via `test_new_lead_without_name_falls_back_to_phone` (payload vazio simulando ausência de nome). **Não** testado com um webhook real da UazAPI chegando ponta a ponta — pendente se quiser essa validação adicional.

### Cenário P1 — Novo Lead manual só com contato
- [x] Abrir "Novo Lead", preencher telefone + nome do contato, deixar empresa vazia
- [x] Salvar com sucesso, aparece no Kanban só com o nome do contato
- **Validado em:** 2026-07-29 — testado ao vivo (Chrome DevTools MCP) na conta `autodigital157@gmail.com`. Lead "Ana QA" criado (`POST /api/leads` → 200, `companyName: null`, `contactName: "Ana QA"`), card no Kanban mostra "Ana QA" (sem "Empresa sem nome").

### Cenário P2 — Novo Lead manual só com empresa
- [x] Preencher telefone + empresa, deixar nome do contato vazio
- [x] Salvar com sucesso
- **Validado em:** 2026-07-29 — lead "Padaria Teste QA" criado (`POST /api/leads` → 200, `companyName: "Padaria Teste QA"`, `contactName: null`), aparece corretamente no Kanban.

### Cenário P3 — Novo Lead sem nenhum dos dois é bloqueado
- [x] Preencher só telefone, tentar salvar
- [x] Botão permanece desabilitado / mensagem de erro visível
- **Validado em:** 2026-07-29 — com Nome e Empresa vazios, "Salvar Lead" aparece `disabled` e a dica "Preencha ao menos o Nome ou a Empresa." é exibida.

### Cenário C3 — Exibição sem "null"/"undefined"
- [x] Kanban, busca, DragOverlay com leads só-empresa/só-contato/ambos
- [ ] FollowUp Center (não coberto nesta rodada — ver Fase 7 parcial acima)
- [x] Nenhum lugar mostra `"null"` ou `"undefined"`
- **Validado em:** 2026-07-29 — após o fix de `LeadsContext.tsx`/`leadDisplayName`, cards e sugestões de busca mostram só o nome disponível; busca por "padaria" filtra corretamente sem erro no console.

---

## Ajustes Possíveis Pós-Implementação

- Migrar os demais pontos que já fazem `companyName || contactName` (`LeadCardDialog.tsx`, `ProspectConfirmModal.tsx`, `Dashboard.tsx`, `FollowUpEdit.tsx`) para o helper `leadDisplayName`, por consistência (cosmético, fora do escopo mínimo).
- `find_existing_lead()` em `processor.py:148` tem comparação morta com `"Sem nome"` que pode ser simplificada (`if companyName:`), não obrigatório.
