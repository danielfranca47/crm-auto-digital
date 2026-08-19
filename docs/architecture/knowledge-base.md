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

## Dedup de categorias narrativas (evitar repetição entre turnos)

`_apres_knowledge_parts`/`standard_knowledge_block` (fase apresentação) e
`followup_knowledge_block` (fase follow-up), em `decision_engine.py`, injetam o conteúdo cru de
algumas categorias diretamente no prompt da filha. A maioria é **reativa** — condicionada a "usar
APENAS quando/se o lead perguntar X" (`objections_faq`, `service_faq`, `guarantee_policy`,
`service_pricing_table`, `commercial_objections`, `service_differentials`, `active_promotion`,
`payment_policy`, `pre_commitment_faq`) — fica sempre disponível, sem dedup, porque o lead pode
perguntar por aquilo a qualquer momento da conversa.

Três categorias são **narrativas** — informação para contar proativamente uma vez, não para
responder sob demanda: `social_proof`, `pitch_script`, `product_details` (só as duas primeiras
existem hoje na fase follow-up). Confiar apenas na instrução "usar quando fizer sentido" reinjetada
todo turno se mostrou insuficiente (mesma classe de problema do Fluxo de Venda sem estado) — o
conteúdo repetia em turnos consecutivos mesmo sem o lead pedir de novo.

**Mecanismo** (`_evaluate_narrative_knowledge_dedup()`, mesmo arquivo): lê
`leads.knowledge_categories_shown` (coluna `TEXT NULL`, JSON array de categorias já mostradas —
mesmo padrão de `leads.triggers_fired`). Categoria narrativa com conteúdo configurado e ainda não
mostrada → entra no prompt normalmente. Já mostrada → omitida por completo (supressão silenciosa,
sem nota de "já disse isso" — o histórico da conversa já está no prompt). Função pura, chamada 2x
por turno: uma vez dentro do prompt builder (decide o que incluir) e outra dentro de
`compose_decision_output()` (emite `system_actions[{type: "mark_knowledge_shown", categories:
[...]}]` para as categorias novas do turno — mesmo padrão de `mark_trigger_fired`, persistido em
`backend-crm/routes/playground.py` e `routes/executor.py`).

`social_proof` tem dois caminhos de injeção mutuamente exclusivos no mesmo turno —
`commercial_injection` (fase apresentação, ativo só quando `_auto_promoted_from_qual=True`, ver
[`pipeline-phases.md`](pipeline-phases.md#estágio-de-aquecimento-e-appointment_mode-só-hybrid_scheduler))
e o bloco on-demand (`_apres_knowledge_parts`, ativo quando `commercial_injection` está vazio) — os
dois consultam o mesmo estado de dedup, então o resultado é o mesmo independente de qual caminho
disparou no turno de estreia.

**Limitação conhecida:** a categoria é marcada como "mostrada" no momento em que fica disponível no
prompt (porque tinha conteúdo e ainda não estava em `knowledge_categories_shown`), não no momento
em que a LLM efetivamente a cita na resposta — se a filha optar por não usar o conteúdo no turno em
que foi oferecido, ele não volta a aparecer depois. Dedup é por categoria, não por conteúdo (editar
o texto de uma categoria já mostrada não a "desmarca" para leads que já a viram) e não há reset
automático em reengajamento.

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
planilha, texto e/ou URLs de site) com uma descrição livre por fonte, a IA extrai o texto e propõe
o conteúdo por categoria — e só entra na base depois de o utilizador revisar e aprovar. Nunca
sobrescreve categoria já preenchida pelo utilizador. Disponível como passo "Importar materiais
(opcional)" no wizard (as categorias aplicadas saem do fluxo passo-a-passo, que segue só com as
pendentes) e como botão "✦ Importar materiais" no painel normal a qualquer momento. Itens criados
por esta via têm `source_type='ai_extracted'` e badge "✦ IA" na UI (editáveis como qualquer outro
item).

```
UI (fontes + descrições) → POST /api/knowledge/ingest (multipart: files + meta JSON)
  → job knowledge.ingest.internal (fila `jobs`, worker interno assíncrono no lifespan do app)
    → extractors.py: texto por fonte (PDF/imagem/planilha/txt/URL)
    → classifier.py: gpt-4o-mini → {categoria: conteúdo | null}
    → jobs.result = proposed (categoria+label+conteúdo completo+preview) — nada gravado ainda
  → GET /api/knowledge/ingest/{job_id} (polling do frontend a cada 3s)
  → UI mostra "Revise antes de gravar": cada proposta com conteúdo em <textarea> editável e
    checkbox (marcado por padrão); utilizador corrige o texto e/ou desmarca o que não quer gravar
  → POST /api/knowledge/ingest/{job_id}/apply { approved: [key,...], edited_content: {key: texto} }
    → INSERT knowledge_items só para as categorias aprovadas (source_type='ai_extracted'), usando
      o texto editado (fallback pro original do classificador se vazio)
    → move as categorias aplicadas de proposed → applied em jobs.result (idempotente)
  → resumo final: applied (categoria+item_id+preview) / descartadas (proposed não aprovadas) /
    uncovered / skipped_existing
```

**Rotas:** `backend-crm/routes/knowledge_ingest.py`:
- `POST /api/knowledge/ingest` — valida e aceita o lote (rejeita por fonte com motivo:
  `extensao_nao_suportada`, `arquivo_muito_grande`, `url_vazia`, etc.), cria o job e retorna
  `{job_id, accepted, rejected}`. Limites: 6 fontes/lote, arquivo ≤10MB, imagem ≤5MB, 1 job
  `pending`/`in_progress` por utilizador por vez (409 se já houver um em andamento).
- `GET /api/knowledge/ingest/pending` — declarada antes de `GET /{job_id}` para não colidir com o
  path param. Devolve o último job `completed` do utilizador cujo `apply` nunca foi chamado
  (`result.proposed` ainda não vazio) via `find_pending_review_job_id()`, ou `{"job_id": null}` se
  não houver nenhum. Usada por `KnowledgeIngestPanel.tsx` ao montar (ver secção "Retomar revisão
  pendente" abaixo).
- `GET /api/knowledge/ingest/{job_id}` — devolve status/result para polling (texto integral das
  fontes omitido do payload via `_sanitize_result`; o conteúdo completo de `proposed` é preservado
  — é o que a UI usa na revisão).
- `POST /api/knowledge/ingest/{job_id}/apply` — body `{"approved": [category_key,...],
  "edited_content": {category_key: texto}}`, chama `apply_ingest_review()`. `edited_content` é
  opcional — permite gravar uma correção feita na tela de revisão em vez do texto original do
  classificador (ver "Edição inline" abaixo). 404 se o job não existir/não pertencer ao
  utilizador, 409 se ainda não estiver `completed`.

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
lista enviada e descarta conteúdo com menos de 20 caracteres.

**`service_pricing_table` nasce estruturada:** quando essa categoria está entre as enviadas, o
prompt ganha uma regra extra pedindo `"rows"` (lista de `{nome, duracaoMinutos, preco,
descricao?}`) em vez de `"content"` livre para essa key especificamente. `_serialize_pricing_rows()`
normaliza a resposta do LLM para o mesmo JSON `structured_v1` que
`ServicePricingTables.tsx:serializeServicePricingRows()` produz no frontend (linha sem `nome` é
filtrada, `duracaoMinutos` só aceito se numérico, `descricao` omitida do objeto se vazia) — o item
criado por `_insert_ai_item()` já abre em modo "Tabela estruturada" na UI, sem conversão manual.
Se o LLM ignorar a regra e devolver `"content"` (texto livre) em vez de `"rows"`, cai no caminho
normal de texto livre (mesmo comportamento de antes, sem regressão). As demais categorias
continuam sempre em texto livre.

**Worker** (`backend-crm/services/knowledge_ingest/ingest_worker.py`,
`process_pending_knowledge_ingest_jobs()`): loop assíncrono no lifespan de `app.py`
(`_knowledge_ingest_worker_loop`, intervalo 10s, mesmo padrão de `spy_media_worker.py`). CAS
`pending→in_progress`, retry até 3 tentativas. Pipeline: extrai todas as fontes → classifica as
extraídas com sucesso → para cada categoria coberta sem item existente do utilizador, monta uma
entrada em `proposed` (categoria+label+conteúdo completo+preview) — **nada é gravado em
`knowledge_items` neste passo**.

**Revisão e apply** (`apply_ingest_review()`, mesmo módulo): chamada pela rota de apply, recebe as
`approved_keys` do utilizador e opcionalmente `edited_content` (categoria → texto). Para cada key
ainda em `proposed` e não em `applied`: reconfirma `_existing_categories()` (protege contra uma
categoria ter sido preenchida manualmente entre o fim do job e o apply), insere via
`_insert_ai_item()` (`source_type='ai_extracted'`) com o conteúdo final = `edited_content[key]` se
presente e não-vazio após `strip()`, senão o texto original do classificador (guarda contra gravar
um item em branco por um campo limpo sem querer), move a entrada de `proposed` para `applied` em
`jobs.result` (persistido via `UPDATE jobs`) — o `preview` em `applied` reflete o conteúdo
efetivamente gravado. Reaplicar uma key já aplicada é no-op — volta em `already_applied`, sem
duplicar o item. Se `objections_faq` foi aplicado nesta chamada, dispara
`trigger_meta_prompter_for_knowledge()` (`backend-crm/services/meta_prompter_trigger.py`,
compartilhado com a rota de edição manual).

**Edição inline na revisão:** `KnowledgeIngestPanel.tsx`, fase `'review'`, renderiza o conteúdo de
cada proposta num `<textarea>` editável (fora do `<label>` do checkbox, para não disparar o toggle
nativo do browser ao clicar no campo). `confirmApply()` monta `edited_content` só para as
categorias marcadas como aprovadas e envia junto do `POST /apply` — o texto no momento do clique
em "Gravar" é o que é persistido, permitindo corrigir um valor errado (ex.: preço mal extraído)
sem precisar editar depois já dentro da base de conhecimento.

Ao final da chamada, `result["proposed"]` é sempre esvaziado — todo o lote apresentado nessa leva
foi decidido (aplicado, já aplicado, colidiu com `now_existing`, ou descartado por desmarcação).
Chamar `/apply` com `approved=[]` (botão "Continuar sem gravar") também conta como revisão
concluída. Isso é o que permite `find_pending_review_job_id()` diferenciar "ainda não revisado" de
"revisado, nada aprovado".

**Nunca sobrescreve:** uma categoria que já tem item do utilizador (de qualquer `source_type`) só
entra em `skipped_existing` — reingestão só preenche buracos, nunca substitui conteúdo existente. O
mesmo vale no apply: se a categoria ganhou um item entre o fim do job e a aprovação, o apply
ignora-a silenciosamente (não sobrescreve).

**Retomar revisão pendente ao reabrir o painel:** `KnowledgeIngestPanel.tsx` é desmontado toda vez
que o modal "Importar materiais" fecha, o que zeraria o estado local. Para não perder uma revisão
não concluída, o painel monta na fase `'checking'` e consulta `GET /api/knowledge/ingest/pending`
antes de decidir a fase inicial: se houver um job `completed` do utilizador com `apply` nunca
chamado (`result.proposed` não vazio), o painel carrega esse `status`/`result` direto na fase
`'review'` — sem reprocessar o lote. Caso contrário (ou falha transitória na consulta), segue para
`'edit'` normalmente. Uma vez que o utilizador conclui a revisão (mesmo sem aprovar nada), o job
some da lista de pendências — reabrir o painel depois disso volta para `'edit'` limpo.
