# Múltiplas tabelas de serviços/preços na Base de Conhecimento

**Branch:** `main`
**Status:** Todos os cenários validados (P1–P3 via Playground/browser)

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
| 1 | `661f543` | `_load_knowledge_items()` agrega múltiplas tabelas + instruções de prompt sobre identificar a tabela certa |

**Detalhes do commit `661f543`:**
- `backend-crm/services/ai_orchestrator/orchestrator.py` — `_MULTI_ITEM_CATEGORIES`,
  `_render_service_pricing_block()`, `_load_knowledge_items()` agora agrega todos os
  itens activos de `service_pricing_table`
- `backend-executors/app/services/decision_engine.py` — instruções actualizadas nos
  blocos de qualificação comercial e agendamento

### Relatório da Fase 1 — o que mudou na prática

**Antes:** se o profissional criasse uma segunda tabela de serviços (mesma categoria),
ela era silenciosamente ignorada — só a IA via a tabela mais recente.

**Agora:** todas as tabelas activas da categoria são lidas e enviadas à IA, cada uma
identificada pelo seu título. A IA identifica primeiro a qual tabela o lead se refere
(quando há mais de uma) e depois a linha certa dentro dela. Itens antigos (texto livre)
continuam funcionando exactamente como antes — só ganham um cabeçalho com o título.

**Para validar:** Cenário P1 abaixo (já validado via API + Playground).

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
| 1 | `9429e5a` | `allowMultiple` no tipo + `ServicePricingTables.tsx` (novo) + integração em `CamadaConhecimento.tsx` |

**Detalhes do commit `9429e5a`:**
- `frontend-crm/src/types/agente.ts` — `KnowledgeCategory.allowMultiple`;
  `CAT_SERVICE_PRICING_TABLE` marcada `allowMultiple: true`
- `frontend-crm/src/components/agente/ServicePricingTables.tsx` (novo) —
  `parseServicePricingContent()`/`serializeServicePricingRows()` (JSON
  `structured_v1`); `GuidedMultiTableSection` (lista de tabelas); `ModalServiceTable`
  (editor com toggle "Tabela estruturada" / "Texto livre")
- `frontend-crm/src/components/agente/CamadaConhecimento.tsx` — agrupamento por
  categoria (`itemsGroupedByCategory`); branch para `allowMultiple` no render;
  exporta `ModalBase`/`PhaseTag`/`FunnelToggle` para reuso

### Relatório da Fase 2 — o que mudou na prática

**Antes:** a categoria "Tabela de Serviços e Preços" só permitia um item de texto
livre por conta, editado numa única caixa de texto — sem forma de organizar por
profissional/tipo de serviço nem de preencher campos separados (nome, duração,
preço, descrição).

**Agora:** em "Configurar Agente → Conhecimento → Tabela de Serviços e Preços", o
profissional pode cadastrar **várias tabelas nomeadas** (ex.: "Ana — Hipnoterapia",
"Fernanda — Estética"), cada uma com **linhas estruturadas** (nome, duração em
minutos, preço, descrição opcional) preenchidas em campos próprios, em vez de texto
livre. Tabelas antigas continuam funcionando exactamente como antes — abrem em modo
"Texto livre" automaticamente, sem conversão forçada. Cada tabela pode ser pausada
("No funil") ou removida individualmente, sem afectar as outras.

**Para validar:** Cenários P2 e P3 abaixo (já validados via browser).

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
  - **Repetido ao vivo no browser** (Playground real, não só API): lead #306 — "Oi,
    quero marcar a sessão de hipnoterapia da Ana para amanhã" → bot ofereceu
    11h20/15h30 → "Pode ser às 11h20 mesmo, fica confirmado" → "A sessão de
    hipnoterapia com a Ana está confirmada para amanhã, dia 28/06, às 11h20."
    Conferido visualmente na tela de **Agenda** (vista Semanal): o compromisso
    aparece no dia 28/06 com bloco de ~50 min, adjacente ao compromisso do lead
    #304 (mesma duração) — confirma visualmente, na UI real do produto, que a
    duração foi aplicada corretamente a partir da tabela da Ana.

### Cenário P2 — UI cria/edita/remove múltiplas tabelas
- [x] Criar 2 tabelas estruturadas via UI com nomes diferentes
- [x] Editar uma linha de uma tabela
- [x] Remover uma tabela
- **Validado em:** 27/06/2026 — via browser (chrome-devtools MCP), conta de teste,
  Camada 4 · Conhecimento → "Tabela de Serviços e Preços":
  - **Criar:** "+ Adicionar tabela" → "Fernanda — Estética" com 1 serviço (Limpeza de
    pele, 50min, R$150) → card passou de "2" para "3 tabelas cadastradas", preview
    "1 serviço · 50 min" calculado corretamente a partir do JSON estruturado salvo.
  - **Editar (adicionar linha):** abri "Ana — Hipnoterapia" para edição → modal abriu
    em modo "Tabela estruturada" já preenchido (round-trip do JSON: nome, duração,
    preço, descrição todos corretos) → adicionei 2ª linha ("Sessão de hipnoterapia em
    dupla", 90min, 70€) → salvei → card atualizou para "2 serviços · 50–90 min".
    Confirmado fim-a-fim via Playground (lead #307): "quero marcar a sessão de
    hipnoterapia em dupla da Ana" → IA ofereceu horário e confirmou → 
    `GET /api/appointments/lead/307`: `15:30Z`–`17:00Z` = **90 min**, exatamente a
    linha nova adicionada pela UI.
  - **Remover:** "✕" na tabela "Fernanda — Estética" → `window.confirm` tratado via
    `handle_dialog` → card voltou para "2 tabelas cadastradas".
  - **Pausar/reativar (extra, não no plano original mas mesmo mecanismo testado):**
    toggle "No funil" → "Pausado" aplicado individualmente à tabela da Fernanda sem
    afetar as outras duas.

### Cenário P3 — Item legado (texto livre) continua editável
- [x] Abrir para edição um item de `service_pricing_table` criado antes desta feature
  (texto livre, não JSON) → deve abrir em modo "Texto livre", sem forçar conversão
- **Validado em:** 27/06/2026 — "EDITAR" no item legado "Tabela de Serviços e Preços"
  (id=21, criado na Fase 2 da feature de duração, antes desta feature) abriu o modal
  com "TEXTO LIVRE" como modo activo e o conteúdo original intacto na textarea — sem
  nenhuma tentativa de conversão ou parsing forçado para linhas estruturadas. Fechado
  sem salvar (Cancelar) para não alterar o item original.

---

## Ajustes Possíveis Pós-Implementação

- Resolução de duração continua via leitura de texto pela IA (não há lookup
  determinístico linha→duração no backend) — manter assim é proporcional ao escopo
  pedido; uma extração determinística seria um passo futuro, não solicitado agora.
- `CamadaConhecimentoWizard.tsx` (onboarding) continua criando a primeira tabela em
  texto livre genérico — não foi alterado, fora do escopo desta feature.
