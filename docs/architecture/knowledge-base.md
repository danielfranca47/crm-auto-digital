# Base de Conhecimento (Knowledge Items)

Cobre a estrutura de `knowledge_items` (backend-crm), como o conteúdo chega ao LLM, e o caso
especial de categorias com múltiplos itens (`service_pricing_table`).

---

## Modelo de dados

**Tabelas:** `knowledge_items` (`user_id, category, title, content_text, status`),
`knowledge_item_media` (`item_id, media_url, media_type`).

Existem ~30 categorias guiadas (configuradas em `frontend-crm/src/types/agente.ts`,
`KnowledgeCategory`). Por padrão, cada categoria admite **um** item activo por conta — a UI
(`CamadaConhecimento.tsx`) e o backend tratam a categoria como um card único, editável.

## Categorias com múltiplos itens (`allowMultiple`)

`KnowledgeCategory.allowMultiple?: boolean` — quando `true`, a categoria admite **vários** itens
activos simultaneamente, cada um com o seu próprio `title`. Hoje só `service_pricing_table`
("Tabela de Serviços e Preços") tem esta flag — pensado para profissionais com várias tabelas
(ex.: "Ana — Hipnoterapia", "Fernanda — Estética"), sem exigir agendas/calendários separados por
profissional (isso continua sendo uma [limitação conhecida do MVP](agenda.md), fora do escopo).

### Formato do conteúdo — `structured_v1` vs. texto livre

`content_text` de um item `service_pricing_table` pode ser:
- **JSON estruturado** (`{"format": "structured_v1", "rows": [{name, duration_minutes, price, description?}]}`)
- **Texto livre legado** — qualquer conteúdo anterior a este formato; continua funcionando sem
  conversão forçada (a UI detecta e abre em modo "Texto livre" automaticamente)

`frontend-crm/src/components/agente/ServicePricingTables.tsx`:
- `parseServicePricingContent()` / `serializeServicePricingRows()` — parse/serialize do JSON
- `GuidedMultiTableSection` — lista de tabelas da categoria (criar/editar/remover/pausar
  individualmente via toggle "No funil")
- `ModalServiceTable` — editor com toggle "Tabela estruturada" (linhas por nome/duração/preço/
  descrição) vs. "Texto livre" (itens legados abrem neste modo)

`CamadaConhecimento.tsx` agrupa itens por categoria (`itemsGroupedByCategory`) e renderiza
`GuidedMultiTableSection` para categorias `allowMultiple`; as ~30 categorias normais continuam
com o card único de sempre.

## Agregação para o LLM — `backend-crm/services/ai_orchestrator/orchestrator.py`

`_load_knowledge_items()`: para a maioria das categorias, carrega só o item mais recente (como
sempre). Para categorias em `_MULTI_ITEM_CATEGORIES = {"service_pricing_table"}`, agrega **todos**
os itens activos — cada um vira um bloco de texto com o título como cabeçalho
(`_render_service_pricing_block()`, com parsing do JSON `structured_v1` + fallback para texto
bruto quando não é JSON).

O `ContextBundle` resultante (`knowledge_items["service_pricing_table"]`) pode conter múltiplas
tabelas concatenadas — usado no bloco "MODO COMERCIAL" da fase de apresentação (ver
[`pipeline-phases.md`](pipeline-phases.md#estágio-de-aquecimento-e-appointment_mode-só-hybrid_scheduler)).

## Instrução ao LLM — `backend-executors/app/services/decision_engine.py`

Os dois blocos que já liam `service_pricing_table` (qualificação em modo comercial e filha de
agendamento) ganharam instrução extra: quando há mais de uma tabela, identificar primeiro **qual**
tabela o lead está a pedir, e só depois a linha certa dentro dela. Sem isso, a IA aplicaria a
duração/preço errados quando o profissional tem mais de um serviço cadastrado.

## Compatibilidade com itens legados

Nenhum item anterior a esta funcionalidade precisa de migração — um item de texto livre antigo
continua a ser lido, agregado (se a categoria virou `allowMultiple`) e editável exactamente como
antes. A UI só ativa o modo "Tabela estruturada" quando o conteúdo já é JSON `structured_v1`.
