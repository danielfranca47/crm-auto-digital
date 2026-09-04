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

### Fase 2 — Nova coluna `acquisition_channel` + models + rotas

**Objetivo:** dar ao canal de marketing um lugar próprio, sem tocar na lógica de IA.

| Arquivo | O que muda |
|---|---|
| `backend-crm/database.py` | `ensure_column(conn, "leads", "acquisition_channel", "acquisition_channel TEXT NULL")` |
| `backend-crm/models.py` | Novo campo `acquisition_channel: Optional[str] = None` em `Lead` e `LeadUpdate`; docstring de `origin` reescrito |
| `backend-crm/routes/leads.py` | POST `criar_lead`: coluna nova no INSERT + fallback manual. PATCH: nenhuma mudança (já é genérico) |

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
