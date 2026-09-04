# Separar canal de aquisição x direção (inbound/outbound) do lead + corrigir classificação

**Branch:** `feat/lead-origem-canal-aquisicao`
**Status:** Em andamento

---

## Motivação

O campo `leads.origin` está sobrecarregado com dois significados diferentes: (1) o canal de
marketing/aquisição do lead (Facebook Ads, Website, Indicação...) e (2) a direção da conversa
(inbound = o lead procurou primeiro / outbound = a empresa abordou primeiro), usada por
`services/ai_orchestrator/orchestrator.py` para escolher qual opener
(`origin_inbound_opener`/`origin_outbound_opener` do AI Profile) calibra o tom do primeiro
contato da IA.

Ao investigar como separar isso, foi encontrado um bug já ativo em produção: a classificação de
direção hoje é uma whitelist frágil, e o valor real gravado para todo lead que chega
organicamente pelo WhatsApp (o caso mais comum de todos) não bate nela — ou seja, quase todo
lead inbound real está sendo tratado pela IA como se tivesse sido abordado a frio. Ver
"Problemas Identificados" abaixo.

---

## Problemas Identificados (estado anterior)

1. **Whitelist de direção não cobre o valor real de inbound via WhatsApp:**
   `backend-crm/services/ai_orchestrator/orchestrator.py:290` e `:369` — `_is_outbound =
   _lead_origin_raw.lower() not in ("whatsapp", "inbound", "manual", "planilha", "")`. O valor
   real gravado por `services/whatsapp_inbound/guardrail.py:47`
   (`find_or_create_lead_by_phone`, chamada pelo webhook toda vez que um número novo manda a
   primeira mensagem) é `'whatsapp_inbound'`, que não bate nessa lista — classificado como
   outbound por engano.

2. **Mesmo bug para leads do formulário do site:** `backend-crm/routes/public.py:202-203` grava
   `origin="Formulário Website"`, que também não bate na whitelist — outro caso real de inbound
   classificado errado.

3. **Campo `origin` sobrecarregado no formulário manual de criação:**
   `frontend-crm/src/components/NewLeadModal.tsx` (campo "Origem", texto livre, default
   `"Manual"`) mistura canal de marketing e direção no mesmo input — se o utilizador digitar
   "Facebook Ads", o lead é classificado como outbound por não bater na whitelist.

4. **Mesmo problema na edição de lead existente:** `frontend-crm/src/components/
   LeadCardDialog.tsx:821-840`, campo "Fonte do Lead" — texto livre que permite sobrescrever
   silenciosamente o valor técnico (`whatsapp_inbound`/`outbound`) de um lead já classificado
   corretamente.

Levantamento de todos os valores reais de `origin` no sistema confirmou que **o único valor
gravado deliberadamente para sinalizar prospecção fria é o literal `"outbound"`**, escrito em
dois lugares (`ProspectConfirmModal.tsx:59-62` e `agent-local/app/crm_client.py:log_outbound()`,
ambos via `PATCH /api/leads/{id}`). Todo o resto (`whatsapp_inbound`, `Formulário Website`,
`Manual`, `Planilha` — fluxo ativo de import via `automations/assistente_ia/processor.py` — e
qualquer canal de marketing futuro) representa um lead que chegou primeiro.

---

## Abordagem

```
leads.origin (antes) → usado para DUAS coisas: canal de marketing + direção IA
leads.origin (depois) → só direção: "outbound" (explícito) ou qualquer outro valor = inbound
leads.acquisition_channel (novo) → só canal de marketing, texto livre, não lido pela IA

Classificação de direção:
  origin.strip().lower() == "outbound"  → outbound
  qualquer outro valor                  → inbound (default seguro)
```

---

## Plano de Implementação

### Fase 1 — Corrigir classificação de direção em `orchestrator.py`

**Objetivo:** trocar a blacklist frágil por um check positivo único, corrigindo os bugs #1 e #2.

| Arquivo | O que muda |
|---|---|
| `backend-crm/services/ai_orchestrator/orchestrator.py` | Extrai `_classify_lead_origin()` e substitui as 2 ocorrências duplicadas (linhas 289-303 e 368-388) |
| `backend-crm/tests/test_lead_origin_classification.py` (novo) | Teste unitário puro cobrindo os casos reais (`whatsapp_inbound`, `Formulário Website`, `Manual`, `Planilha`, `outbound`, canais livres) |

```python
# ANTES
_lead_origin_raw = lead_data.get("origin") or ""
_is_outbound = _lead_origin_raw.lower() not in ("whatsapp", "inbound", "manual", "planilha", "")

# DEPOIS
_is_outbound, _lead_origin, _lead_origin_label = _classify_lead_origin(lead_data.get("origin"))
```

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `bd3448e` | fix: corrigir classificação inbound/outbound de leads na IA |

**Detalhes do commit `bd3448e`:**
- `backend-crm/services/ai_orchestrator/orchestrator.py` — nova função `_classify_lead_origin()`; substitui as 2 ocorrências duplicadas da whitelist antiga
- `backend-crm/tests/test_lead_origin_classification.py` — novo arquivo, 8 testes cobrindo os valores reais de `origin`
- `docs/implementations/lead-origem-canal-aquisicao.md` — arquivo criado com o plano completo

### Relatório da Fase 1 — o que mudou na prática

**Antes:** quase todo lead que chegava sozinho pelo WhatsApp (ou pelo formulário do site) era
tratado internamente pela IA como se tivesse sido abordado a frio — usava o texto de abertura
errado (`origin_outbound_opener` em vez de `origin_inbound_opener`) e um rótulo de contexto
invertido no prompt.

**Agora:** só um lead com `origin` gravado exatamente como `"outbound"` (o valor que o
`ProspectConfirmModal` ou o agent-local gravam quando uma prospecção fria é confirmada) é tratado
como outbound. Qualquer outro valor — incluindo o caso real de todo lead que chega pelo WhatsApp
— é tratado corretamente como inbound.

**Para validar:** esta fase é coberta pelo teste automatizado (`python -m unittest
backend-crm.tests.test_lead_origin_classification`, já rodado e passando — 8/8 casos, incluindo
os dois bugs reais). Rodei também a suíte completa de `backend-crm/tests` (208 testes) para
garantir zero regressão; as 18 falhas pré-existentes que apareceram são um problema conhecido de
ambiente Windows (arquivo de banco temporário não libera lock a tempo do `tearDown` apagar a
pasta) — confirmei rodando os mesmos testes na pasta principal (sem esta mudança) e o resultado é
idêntico, ou seja, não têm relação com esta fase. Não há cenário de UI/playground para este fix
(é lógica interna de classificação), então não se aplica teste via browser aqui.

### Fase 2 — Nova coluna `acquisition_channel` + models + rotas

**Objetivo:** dar ao canal de marketing um lugar próprio, sem tocar na lógica de IA.

| Arquivo | O que muda |
|---|---|
| `backend-crm/database.py` | `ensure_column(conn, "leads", "acquisition_channel", "acquisition_channel TEXT NULL")` |
| `backend-crm/models.py` | Novo campo `acquisition_channel: Optional[str] = None` em `Lead` e `LeadUpdate`; docstring de `origin` reescrito |
| `backend-crm/routes/leads.py` | POST `criar_lead`: coluna nova no INSERT + fallback manual. PATCH: nenhuma mudança (já é genérico) |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `c5dd46c` | feat: adicionar acquisition_channel como coluna própria do lead |

**Detalhes do commit `c5dd46c`:**
- `backend-crm/database.py` — `ensure_column` para `leads.acquisition_channel` (TEXT NULL)
- `backend-crm/models.py` — campo novo em `Lead` e `LeadUpdate`; docstring de `origin` reescrito
- `backend-crm/routes/leads.py` — POST inclui a coluna no INSERT + fallback manual; PATCH não precisou de mudança (já é genérico)

### Relatório da Fase 2 — o que mudou na prática

**Antes:** não havia lugar para guardar o canal de marketing (Facebook Ads, Indicação...) sem
misturar com o campo técnico que a IA usa para saber se abordou o lead primeiro.

**Agora:** existe uma coluna própria (`acquisition_channel`) no banco, aceita pelo backend tanto
na criação quanto na edição de um lead, totalmente separada de `origin` — e não é lida por
nenhuma lógica de IA.

**Para validar:** confirmei via script direto que a coluna é criada corretamente e que os
modelos (`Lead`/`LeadUpdate`) aceitam o campo. Também encontrei (mas não mexi, está fora do
escopo desta implementação) um bug pré-existente e não relacionado: `_migrate_leads_company_or_
contact()` em `database.py` reconstrói a tabela `leads` com uma lista fixa de colunas na
*primeira* vez que um banco totalmente novo é inicializado, e essa lista já não incluía várias
colunas adicionadas depois via `ensure_column` (`wa_display_name`, `sales_flow_wait`,
`branches_selected`, `knowledge_categories_shown`, e agora também `acquisition_channel`) — só
afeta bancos novos do zero (dev local/CI), nunca produção, porque lá essa migração já rodou faz
tempo e fica marcada como concluída. Não afeta esta implementação porque a validação real
(Fase 3, via browser) usa o banco já existente. Vale um fix à parte no futuro se for
incomodar testes locais.

O teste ponta-a-ponta de verdade (criar/editar lead via API real) fica coberto pelos Cenários
C1-C4 da Fase 3, já que abrir o navegador e testar a UI exercita as mesmas rotas. Não criei teste
automatizado dedicado para esta fase — seguindo o plano, que reservou isso para a validação
manual da Fase 3.

### Fase 3 — Frontend

**Objetivo:** `origin` vira seleção controlada (Inbound/Outbound); canal de aquisição vira campo novo, sempre livre.

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/types/crm.ts` | `acquisition_channel` em `Lead` e `NewLeadForm` |
| `frontend-crm/src/lib/lead-origin.ts` (novo) | `LEAD_DIRECTION_OPTIONS` + `formatLeadOriginLabel()` |
| `frontend-crm/src/services/api.ts` | `acquisition_channel` em `createLead`/`updateLead` |
| `frontend-crm/src/contexts/LeadsContext.tsx` | `mapRawLead()` e `addLead()` — sem isto o campo não chega à tela (caminho real de criação/reload) |
| `frontend-crm/src/components/NewLeadModal.tsx` | Campo "Origem" vira `<Select>` (só visível/obrigatório quando categoria ≠ "À Prospectar"); novo campo "Canal de aquisição" |
| `frontend-crm/src/components/LeadCardDialog.tsx` | Mesmo tratamento na edição de lead existente — corrige o bug #4 |
| `frontend-crm/src/components/KanbanBoard.tsx` | Busca inclui `acquisition_channel`; label de origem no drag usa `formatLeadOriginLabel` |

### Commits Fase 3

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `5bd3cdd` | feat: separar direção (inbound/outbound) de canal de aquisição no frontend |

**Detalhes do commit `5bd3cdd`:**
- `frontend-crm/src/types/crm.ts` — `acquisition_channel` em `Lead`/`NewLeadForm`
- `frontend-crm/src/lib/lead-origin.ts` (novo) — `LEAD_DIRECTION_OPTIONS` + `formatLeadOriginLabel()`
- `frontend-crm/src/services/api.ts` — `acquisition_channel` em `createLead`/`updateLead`
- `frontend-crm/src/contexts/LeadsContext.tsx` — `mapRawLead()`/`addLead()` incluem o campo (caminho real de criação/reload)
- `frontend-crm/src/components/NewLeadModal.tsx` — "Origem" vira Select condicional (Inbound/Outbound); novo campo "Canal de aquisição"
- `frontend-crm/src/components/LeadCardDialog.tsx` — mesmo tratamento na edição de lead existente
- `frontend-crm/src/components/KanbanBoard.tsx` — busca inclui `acquisition_channel`; label de direção usa `formatLeadOriginLabel`

### Relatório da Fase 3 — o que mudou na prática

**Antes:** o campo "Origem" era texto livre tanto na criação quanto na edição de um lead — dava
para digitar um canal de marketing ali e acabar classificando o lead errado para a IA, ou editar
um lead existente e sobrescrever à toa o valor técnico gravado pelo sistema.

**Agora:** "Origem" virou uma escolha fechada (Inbound/Outbound), só perguntada quando o lead não
está mais em "À Prospectar" (nessa categoria, quem pergunta depois é o fluxo já existente de
confirmar prospecção no Kanban). Um campo novo e sempre livre, "Canal de aquisição", guarda o
canal de marketing sem interferir em nada da IA.

**Para validar:** rodei `tsc --noEmit` e `npm run build` no frontend-crm — compilam limpos, sem
nenhum erro nos arquivos desta fase (os erros de tipo/lint que apareceram no projeto são
pré-existentes, em arquivos não tocados por esta implementação). A validação funcional de
verdade — criar lead, escolher direção, editar lead existente sem corromper `origin`, buscar por
canal — precisa dos Cenários C1 a C6 abaixo, via browser.

### Fase 4 — Docs

| Arquivo | O que muda |
|---|---|
| `docs/architecture/pipeline-phases.md` | Linha da tabela sobre `lead_origin` reescrita; nota sobre `acquisition_channel` |

---

## Checks de Validação

### Cenário C1 — Lead novo "À Prospectar" não pergunta direção
- [ ] Criar lead com categoria "À Prospectar"
- [ ] Confirmar: Select de direção não aparece
- [ ] Confirmar via API/tela: `origin` gravado como `"Manual"`

### Cenário C2 — Lead novo em categoria avançada exige direção
- [ ] Criar lead com categoria "Em Andamento" (ou outra ≠ "À Prospectar")
- [ ] Confirmar: Select de direção aparece e bloqueia o submit sem escolha
- [ ] Escolher "Outbound" → confirmar `origin="outbound"` gravado

### Cenário C3 — Canal de aquisição persiste após reload
- [ ] Preencher "Canal de aquisição" na criação de um lead
- [ ] Recarregar a página (força `reloadAllLeads` + `mapRawLead`)
- [ ] Confirmar: valor continua visível no card/dialog

### Cenário C4 — Edição não corrompe direção técnica (bug original)
- [ ] Abrir um lead com `origin="whatsapp_inbound"` no `LeadCardDialog`
- [ ] Editar só as Observações (não mexer no Select de direção), salvar
- [ ] Confirmar via API/tela: `origin` permanece `"whatsapp_inbound"` intacto

### Cenário C5 — Busca no Kanban por canal de aquisição
- [ ] Buscar por um termo presente só em `acquisition_channel` de um lead
- [ ] Confirmar: lead aparece no resultado filtrado

### Cenário C6 — Fluxo de confirmação de prospecção continua intacto
- [ ] Arrastar um card "À Prospectar" → "Qualificação" com `origin` vazio/"Manual"
- [ ] Confirmar: `ProspectConfirmModal` ainda dispara normalmente

**Teste automatizado (Fase 1):** `python -m unittest backend-crm/tests/test_lead_origin_classification.py` — cobre a classificação de direção isoladamente, sem depender de UI.

---

## Ajustes Possíveis Pós-Implementação

- Import via planilha (`automations/assistente_ia/processor.py`) não recebe `acquisition_channel`
  nesta rodada — fica só acessível via criação/edição manual e API direta.
- Label amigável de `origin` no modo leitura (`formatLeadOriginLabel`) só cobre `Manual`/
  `outbound`; valores técnicos como `whatsapp_inbound`/`Formulário Website`/`Planilha` continuam
  exibidos crus — pode virar um mapa de labels mais completo no futuro, se fizer sentido para o
  operador.
