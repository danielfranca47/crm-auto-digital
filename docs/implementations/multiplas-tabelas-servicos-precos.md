# Múltiplas tabelas de serviços/preços na Base de Conhecimento

**Branch:** `main`
**Status:** Em andamento

---

## Motivação

A categoria de conhecimento "Tabela de Serviços e Preços" (`service_pricing_table`)
hoje só permite **um** item de texto livre por conta. O utilizador quer organizar o
catálogo por profissional/tipo de serviço (ex.: "Ana — Hipnoterapia", "Fernanda —
Estética", cada um com suas próprias linhas) e quer um editor estruturado por linha
(nome, duração, preço, descrição) em vez de uma caixa de texto livre única.

Confirmado com o utilizador (AskUserQuestion) que:
- Não é necessário separar agendas/disponibilidade por profissional — continua tudo
  na mesma conta/calendário. "Ana"/"Fernanda" são apenas rótulos de organização do
  catálogo, não uma feature de múltiplos profissionais com calendários próprios
  (essa é uma limitação maior já documentada em `docs/architecture/agenda.md`,
  secção "Limitação conhecida (MVP)", e está fora de escopo aqui).
- O editor desejado é estruturado por linha (campos próprios), não texto livre.

---

## Problemas Identificados (estado anterior)

1. **UI rígida 1:1:** `frontend-crm/src/components/agente/CamadaConhecimento.tsx` —
   `itemByCategory: Map<string, KnowledgeItem>` mapeia cada categoria guiada para no
   máximo um item; não há forma de criar uma segunda "tabela" pela UI.
2. **Backend colapsa para 1 item por categoria:** `_load_knowledge_items()`
   (`backend-crm/services/ai_orchestrator/orchestrator.py`) só carrega o
   primeiro/mais recente item de cada categoria — se dois itens fossem criados com a
   mesma categoria (via API direta), o segundo seria silenciosamente ignorado no
   `ContextBundle`.
3. **Sem editor estruturado:** o conteúdo de `service_pricing_table` é uma única
   caixa de texto livre (`ModalGuided`) — sem campos próprios para nome, duração,
   preço e descrição.

---

## Abordagem

Reaproveitar a infraestrutura existente, sem migração de banco:

```
Cada "tabela" = um knowledge_item com category='service_pricing_table'
  title = nome da tabela (ex.: "Ana — Hipnoterapia")
  content_text = JSON {"format": "structured_v1", "rows": [...]}  (ou texto livre legado)

_load_knowledge_items() (backend-crm)
  → para service_pricing_table, agrega TODOS os itens activos (não só o primeiro)
  → renderiza cada um como bloco de texto com o título como cabeçalho
  → demais ~30 categorias continuam exactamente como hoje (sem agregação)

decision_engine.py (backend-executors)
  → já injeta o valor string de knowledge_items["service_pricing_table"] no prompt
  → só ganha uma instrução extra: pode haver mais de uma tabela, identificar a
    tabela certa antes da linha certa

CamadaConhecimento.tsx (frontend-crm)
  → categorias com allowMultiple=true renderizam lista de tabelas (não 1 card)
  → editor com toggle "Tabela estruturada" (linhas nome/duração/preço/descrição)
    vs. "Texto livre" (itens legados continuam editáveis como texto)
```

---

## Plano de Implementação

### Fase 1 — Backend: múltiplas tabelas agregadas para o LLM

**Objetivo:** permitir que múltiplos itens da categoria `service_pricing_table`
sejam todos lidos e enxergados pela IA, cada um identificado pelo seu título.

| Arquivo | O que muda |
|---|---|
| `backend-crm/services/ai_orchestrator/orchestrator.py` | `_load_knowledge_items()`: nova constante `_MULTI_ITEM_CATEGORIES = {"service_pricing_table"}`; para categorias nessa lista, agregar todos os itens activos em vez de só o primeiro; nova função `_render_service_pricing_block()` com parsing JSON `structured_v1` + fallback texto bruto |
| `backend-executors/app/services/decision_engine.py` | Ajuste textual nos dois blocos que já leem `service_pricing_table` (qualificação modo comercial e filha de agendamento): instrução para identificar a tabela certa antes da linha certa, quando houver mais de uma |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|

---

### Fase 2 — Frontend: editor estruturado e lista de múltiplas tabelas

**Objetivo:** permitir criar, editar e remover múltiplas tabelas pela UI, com
editor estruturado por linha.

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/types/agente.ts` | `KnowledgeCategory` ganha `allowMultiple?: boolean`; `CAT_SERVICE_PRICING_TABLE` ganha `allowMultiple: true` |
| `frontend-crm/src/components/agente/ServicePricingTables.tsx` (novo) | Tipos + parse/serialize do JSON estruturado; componentes `GuidedMultiTableSection` (lista de tabelas) e `ModalServiceTable` (editor com toggle estruturado/texto livre) |
| `frontend-crm/src/components/agente/CamadaConhecimento.tsx` | Agrupar items por categoria; renderizar `GuidedMultiTableSection` para categorias `allowMultiple` |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|

---

## Checks de Validação

### Cenário P1 — Backend agrega múltiplas tabelas (sem UI nova)
- [x] Criar 2 itens via `POST /api/knowledge` com `category='service_pricing_table'`,
  títulos diferentes — um em JSON `structured_v1`, outro em texto livre legado
- [x] Playground: lead pede serviço de uma tabela específica → IA usa a duração certa
  dessa tabela
- **Validado em:** 27/06/2026 — conta de teste (`autodigital157@gmail.com`, AI Profile
  id=5). Criados via API: item id=21 (legado, texto livre, já existente da Fase 2 da
  feature de duração: "Sessão avulsa - 30min: R$120" / "Sessão estendida de massagem -
  90min: R$220") e item id=22 (`structured_v1`, título "Ana — Hipnoterapia", 1 linha:
  "Sessão de hipnoterapia", 50min, 40€).
  - Lead #304: "quero marcar a sessão de hipnoterapia da Ana para amanhã" → IA ofereceu
    10:30/15:30 mencionando "sessão de hipnoterapia com a Ana" e
    `signals_structured.meeting_duration_minutes=50`. Confirmado "10h30" →
    `GET /api/appointments/lead/304`: `start_at=10:30Z`, `end_at=11:20Z` — **50 min**,
    igual à linha estruturada da Ana (não 30/90 da tabela legada, não 60 do default).
  - Lead #305 (novo, sem mencionar Ana): "quero marcar a sessão avulsa para amanhã" →
    IA respondeu "sessão avulsa de 30 minutos" e `signals_structured.meeting_duration_minutes=30`
    — identificou corretamente a linha da tabela legada, não a da Ana.
  - Confirma que `_load_knowledge_items()` agrega as duas tabelas (uma JSON
    estruturada, uma texto livre legado) e a IA distingue corretamente qual delas o
    lead está pedindo em ambos os sentidos.

### Cenário P2 — UI cria/edita/remove múltiplas tabelas
- [ ] Criar 2 tabelas estruturadas via UI com nomes diferentes
- [ ] Editar uma linha de uma tabela
- [ ] Remover uma tabela
- **Pendente**

### Cenário P3 — Item legado (texto livre) continua editável
- [ ] Abrir para edição um item de `service_pricing_table` criado antes desta feature
  (texto livre, não JSON) → deve abrir em modo "Texto livre", sem forçar conversão
- **Pendente**

---

## Ajustes Possíveis Pós-Implementação

- Resolução de duração continua via leitura de texto pela IA (não há lookup
  determinístico linha→duração no backend) — manter assim é proporcional ao escopo
  pedido; uma extração determinística seria um passo futuro, não solicitado agora.
- `CamadaConhecimentoWizard.tsx` (onboarding) continua criando a primeira tabela em
  texto livre genérico — não foi alterado, fora do escopo desta feature.
