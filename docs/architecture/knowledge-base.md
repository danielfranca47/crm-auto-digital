# Base de Conhecimento (Knowledge Items)

Cobre a estrutura de `knowledge_items` (backend-crm), como o conteúdo chega ao LLM, o caso
especial de categorias com múltiplos itens (`service_pricing_table`), o wizard de onboarding e a
ingestão de materiais por IA.

---

## Modelo de dados

**Tabelas:** `knowledge_items` (`user_id, category, title, content_text, source_type,
active_in_funnel`), `knowledge_item_media` (`item_id, media_url, media_type`).

`source_type` — `'manual'` (digitado na UI), `'file'` (upload avulso via `routes/knowledge.py`) ou
`'ai_extracted'` (criado pela ingestão por IA, ver secção própria abaixo). O CHECK da coluna foi
migrado por recriação de tabela para admitir `'ai_extracted'`
(`ensure_knowledge_source_type_ai_extracted` em `backend-crm/database.py`).

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

---

## Wizard de onboarding (`CamadaConhecimentoWizard.tsx`)

Guia o preenchimento da base numa conta nova, categoria a categoria. Nenhuma categoria é
obrigatória: todos os passos (críticas e recomendadas) têm botão de pular ("Pular esta etapa" /
"Pular por agora"), e há sempre uma saída "Preencher depois →" (link no topo em qualquer passo,
botão dedicado no passo 0) que leva direto ao painel normal — cada categoria continua editável a
qualquer momento fora do wizard.

**Dispensa persistente:** ao sair do wizard (`onExit`) ou completar (`onComplete`),
`CamadaConhecimento.tsx` grava `kb_wizard_dismissed_${userId}` no `localStorage` (`userId` vindo de
`api.auth.me()`). Uma conta com base vazia não volta a ver o wizard depois de dispensado, mesmo
recarregando a página.

---

## Ingestão de materiais por IA

Fluxo alternativo ao preenchimento manual: o utilizador envia um lote de materiais (PDF, imagem,
planilha, texto e/ou URLs de site) com uma descrição livre por fonte, e a IA extrai o texto e
preenche sozinha as categorias que os materiais cobrirem — nunca sobrescrevendo categoria já
preenchida pelo utilizador. Disponível como passo "Importar materiais (opcional)" no wizard (as
categorias cobertas pela IA saem do fluxo passo-a-passo, que segue só com as pendentes) e como
botão "✦ Importar materiais" no painel normal a qualquer momento. Itens criados por esta via têm
`source_type='ai_extracted'` e badge "✦ IA" na UI (editáveis como qualquer outro item).

```
UI (fontes + descrições) → POST /api/knowledge/ingest (multipart: files + meta JSON)
  → job knowledge.ingest.internal (fila `jobs`, worker interno assíncrono no lifespan do app)
    → extractors.py: texto por fonte (PDF/imagem/planilha/txt/URL)
    → classifier.py: gpt-4o-mini → {categoria: conteúdo | null}
    → INSERT knowledge_items (source_type='ai_extracted', só em categorias sem item do utilizador)
  → GET /api/knowledge/ingest/{job_id} (polling do frontend a cada 3s)
  → resumo: covered (categoria+item_id+preview) / uncovered / skipped_existing
```

**Rotas:** `backend-crm/routes/knowledge_ingest.py` — `POST /api/knowledge/ingest` valida e aceita
o lote (rejeita por fonte com motivo: `extensao_nao_suportada`, `arquivo_muito_grande`,
`url_vazia`, etc.), cria o job e retorna `{job_id, accepted, rejected}`; `GET
/api/knowledge/ingest/{job_id}` devolve status/result para polling (texto integral das fontes
omitido do payload — `_sanitize_result`). Limites: 6 fontes/lote, arquivo ≤10MB, imagem ≤5MB, 1 job
`pending`/`in_progress` por utilizador por vez (409 se já houver um em andamento).

**Extração por tipo** (`backend-crm/services/knowledge_ingest/extractors.py`,
`extract_source()`, 15k chars máx/fonte):
- **PDF** → `pypdf` (camada de texto). PDF escaneado sem camada de texto retorna
  `status="failed", reason="sem_texto_extraivel"` — orientação é reenviar como imagem (o caminho de
  imagem faz OCR via vision).
- **Imagem** (`.jpg/.jpeg/.png/.webp`) → `gpt-4o-mini` vision (`data:` URI base64, `detail="high"`)
  — extrai texto e descreve elementos visuais relevantes. Requer `OPENAI_API_KEY`.
- **`.txt/.csv/.xlsx`** → `extract_text_from_table_file()`, compartilhada com `routes/knowledge.py`.
- **URL** → scraper `httpx` + `BeautifulSoup` (home + até 4 páginas internas cujo link contenha
  palavras-chave como "sobre", "servico", "preco", "contato", "faq"). Não renderiza JavaScript —
  sites que dependem de JS para o conteúdo principal não são suportados (fora do escopo; exigiria
  headless browser).

**Classificação** (`backend-crm/services/knowledge_ingest/classifier.py`, `classify_sources()`):
`gpt-4o-mini`, `response_format=json_object`, `temperature=0`, timeout 120s, 60k chars totais.
Prompt inclui contexto do negócio (nicho/público/oferta) + categorias do template (key/label/
description) + fontes numeradas com a descrição do utilizador. Valida as keys retornadas contra a
lista enviada e descarta conteúdo com menos de 20 caracteres. Grava sempre texto livre — mesmo para
`service_pricing_table` (a categoria `allowMultiple` aceita texto livre normalmente, ver secção
acima; extração direta para `structured_v1` é melhoria futura).

**Worker** (`backend-crm/services/knowledge_ingest/ingest_worker.py`,
`process_pending_knowledge_ingest_jobs()`): loop assíncrono no lifespan de `app.py`
(`_knowledge_ingest_worker_loop`, intervalo 10s, mesmo padrão de `spy_media_worker.py`). CAS
`pending→in_progress`, retry até 3 tentativas. Pipeline: extrai todas as fontes → classifica as
extraídas com sucesso → para cada categoria coberta sem item existente do utilizador, insere via
`_insert_ai_item` (`source_type='ai_extracted'`) → se cobriu `objections_faq`, dispara
`trigger_meta_prompter_for_knowledge()` (`backend-crm/services/meta_prompter_trigger.py`,
compartilhado com a rota de edição manual). Resultado final nunca inclui o texto integral das
fontes (fica leve para polling/auditoria).

**Nunca sobrescreve:** uma categoria que já tem item do utilizador (de qualquer `source_type`) só
entra em `skipped_existing` — reingestão só preenche buracos, nunca substitui conteúdo existente.
