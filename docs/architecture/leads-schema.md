# Lead — Schema de Nome (companyName / contactName)

## Regra central

`leads.companyName` e `leads.contactName` são ambos opcionais, mas **nunca os dois vazios ao mesmo tempo**. Pelo menos um deve estar preenchido.

## Onde a regra é garantida (3 camadas)

1. **Banco** (`backend-crm/database.py`) — CHECK constraint na tabela `leads`:
   ```sql
   companyName TEXT,   -- nullable (era NOT NULL)
   contactName TEXT,
   CHECK (TRIM(COALESCE(companyName,'')) != '' OR TRIM(COALESCE(contactName,'')) != '')
   ```
   Migração idempotente via `_migrate_leads_company_or_contact()`, chamada em `init_db()`. SQLite não suporta `ALTER COLUMN` — a migração faz rebuild de tabela (`CREATE ... _new` → `INSERT ... SELECT` → `DROP` → `RENAME`), desligando `PRAGMA foreign_keys` durante o rebuild (7 tabelas filhas com `ON DELETE CASCADE`).

2. **API** (`backend-crm/models.py`) — `Lead.companyName: Optional[str] = None`, com `model_validator(mode="after")` que recusa (`ValueError` → 422) quando os dois vêm vazios ou só espaço.

3. **Frontend** (`frontend-crm/src/components/NewLeadModal.tsx`) — telefone sempre obrigatório; Nome **OU** Empresa (botão "Salvar Lead" fica desabilitado e mostra dica visual até um dos dois ser preenchido).

`routes/leads.py` (`criar_lead` e `atualizar_lead_parcial`) captura `sqlite3.IntegrityError` da violação do CHECK e devolve `400` com mensagem clara (`"Informe ao menos o nome da empresa ou o nome do contato"`), em vez de deixar vazar um `500` com o erro cru do SQLite — relevante principalmente num `PATCH` parcial que zere o único nome que o lead tinha.

## Pontos de criação de lead e fallback quando o nome não é conhecido

| Ponto | Arquivo | `companyName` desconhecido | `contactName` desconhecido |
|---|---|---|---|
| Manual (formulário) | `NewLeadModal.tsx` | `NULL` | `NULL` (mas exige pelo menos um dos dois) |
| WhatsApp inbound | `services/whatsapp_inbound/guardrail.py` (`find_or_create_lead_by_phone`) | `NULL` | telefone normalizado (`phone_norm`) |
| Planilha / Google Maps | `automations/assistente_ia/processor.py` (`map_row_to_lead`) | `NULL` | `NULL` (linha sem nenhum nome viola o CHECK; erro é reportado por linha, batch continua) |
| Playground (sandbox) | `routes/playground.py` (`_create_sandbox_lead`) | `NULL` | `"Lead de Teste"` (fixo) |

Nenhum ponto de criação inventa nome de empresa fabricado para contornar a obrigatoriedade (removidos: `"WhatsApp inbound"`, `"Sem nome"`, `"Empresa Teste"`).

## Exibição (frontend)

Prioridade: nome do contato primeiro. Helper compartilhado:

```ts
// frontend-crm/src/utils/leadDisplayName.ts
leadDisplayName(lead) // "Empresa - Contato" se ambos existirem; senão o que existir; "Lead sem nome" se nenhum
```

Usado em: `LeadCard.tsx`, `KanbanBoard.tsx` (busca + `DragOverlay`), `SearchAutocomplete.tsx`, `components/prospection/ProspectionCard.tsx`, `pages/FollowUpCenter.tsx` (6 pontos: banner de autopausado, header do painel de detalhe, modal de confirmação, avatar de iniciais, label da linha, filtro de busca).

## `wa_display_name` — nome de exibição do WhatsApp (pushName)

Campo separado de `contactName`/`companyName`, nullable, gravado só na **criação** do lead via `find_or_create_lead_by_phone()` (`services/whatsapp_inbound/guardrail.py`). Extraído do payload bruto da UazAPI por `routes/webhooks.py::_resolve_wa_display_name()` — chave exata não confirmada contra um payload real (tenta variações prováveis de `chat`/`message`/`data`; loga quando nenhuma bate).

**Por que separado de `contactName`:** `contactName` é o nome que o operador edita no card do lead — se `wa_display_name` sobrescrevesse esse campo, uma correção manual do operador seria perdida no próximo inbound. Mantendo os dois campos distintos, o operador sempre tem a palavra final.

**Uso no prompt da IA:** `backend-executors/app/services/decision_engine.py` resolve o "nome do lead" com `_safe_get(lead, "contactName", "companyName", "wa_display_name", "name")` — ou seja, `wa_display_name` só é usado como fallback automático quando o CRM não tem `contactName` nem `companyName` preenchidos. Não requer nenhuma configuração do operador.

Também exposto como variável de template `{{lead.nome_whatsapp}}` (`automations/assistente_ia/variable_resolver.py`), distinta de `{{lead.nome}}` (que resolve para `contactName`), para uso explícito em campos de template e blocos do Fluxo de Venda.

**Duas fontes de dados distintas no frontend, comportamento diferente:**
- **Via `LeadsContext.tsx`** (`mapRawLead`, usado pelo Kanban/Prospecção) — normaliza `companyName`/`contactName` de `null` (API) para `''` antes de expor como `Lead`. Por isso `Lead.companyName`/`contactName` em `types/crm.ts` permanecem tipados como `string` simples (nunca `null`), consistente com os demais campos do tipo (`phone`, `email`, `origin`, `observations`).
- **Fora de `LeadsContext`** (ex.: `FollowUpCenter.tsx`, via `api.followUps.listActive()`) — recebe `companyName`/`contactName` crus da API, sem essa normalização. `companyName` **pode ser `null` de verdade em runtime** aqui, mesmo que o tipo declarado (`FollowUpLead` em `services/api.ts`) diga `string`. Qualquer novo ponto de leitura de leads fora do `LeadsContext` deve tratar esse campo como potencialmente nulo (usar `leadDisplayName()` ou `?? ''`).
