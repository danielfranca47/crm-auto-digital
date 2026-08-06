# Camada 4 · Conhecimento — destravar wizard + ingestão de materiais por IA

**Branch:** `feat/ajuste-configuracao-ai-profile`
**Status:** Em andamento

---

## Motivação

O wizard de onboarding da Camada 4 (Base de conhecimento) tem dois problemas reportados pelo utilizador:

1. **Só aceita texto digitado** — não há como fornecer URL de website, PDF, imagens ou planilhas como fonte de conhecimento.
2. **Obriga o preenchimento** — categorias críticas não têm botão de pular e não há como sair do wizard para preencher depois, o que atrasa a produção quando o utilizador não tem a informação em mãos.

Visão desejada: um agente de ingestão onde o utilizador envia arquivos/URLs com uma descrição livre ("isso é minha tabela de preços"), a IA extrai o texto e preenche sozinha as categorias que conseguir; o wizard segue apenas com as categorias pendentes, cada uma com opção de pular; e é possível pular todo o procedimento.

---

## Problemas Identificados (estado anterior)

1. **Pular bloqueado em críticas:** `CamadaConhecimentoWizard.tsx:425` — `onSkip={!isCriticalStep ? ... : undefined}`; categorias críticas não têm botão de pular.
2. **Sem saída do wizard:** nenhum caminho de "preencher depois" — o único fim é completar/pular todas as etapas até o StepDone.
3. **Dispensa não persiste:** `wizardDismissed` é `useState` efêmero (`CamadaConhecimento.tsx:1014`) — recarregar a página com base vazia reexibe o wizard.
4. **Bug latente em `kb_dismissed_sections_*`:** o `uid` vem de `items[0].user_id` (`CamadaConhecimento.tsx:1125`), que não existe com base vazia.
5. **Sem ingestão de materiais:** upload só extrai texto de `.txt/.csv/.xlsx` (`routes/knowledge.py`); PDF é aceito apenas como mídia enviada ao lead (texto nunca lido); sem URL, sem OCR, sem preenchimento automático por IA.

---

## Abordagem

```
Fase 1 (frontend) — destravar: pular críticas, sair do wizard, persistir dispensa
Fase 2 (backend)  — fundação da ingestão: rota multipart + job interno + extratores por tipo
                    (PDF→pypdf, imagem→vision gpt-4o-mini, csv/xlsx/txt→pandas, URL→scraper slim)
Fase 3 (backend)  — classificador LLM: textos extraídos → JSON por categoria → INSERT
                    knowledge_items com source_type='ai_extracted' (nunca sobrescreve existentes)
Fase 4 (frontend) — passo "Importar materiais" no wizard + botão no painel; polling do job;
                    resumo cobertas/pendentes; wizard segue só com as pendentes
```

Fluxo da ingestão (Fases 2–4):

```
UI (fontes + descrições) → POST /api/knowledge/ingest (multipart)
  → job knowledge.ingest.internal (fila jobs, worker interno asyncio no lifespan)
    → extractors.py: texto por fonte
    → classifier.py: gpt-4o-mini → {categoria: conteúdo | null}
    → INSERT knowledge_items (source_type='ai_extracted', só categorias sem item)
  → GET /api/knowledge/ingest/{job_id} (polling 3s)
  → resumo: covered / uncovered / skipped_existing
```

Decisões registadas:
- **Dispensa do wizard em localStorage** (`kb_wizard_dismissed_${userId}` via `api.auth.me()`), não em coluna: consistente com o precedente `kb_dismissed_sections_*` e evita tocar `ai_profiles` (que obrigaria atualizar o contrato AdminAgents).
- **Worker interno** (padrão `spy_media_worker.py` + loop no lifespan de `app.py`), não fila de agente externo: ingestão não depende de agente local.
- **Migração do CHECK de `source_type`** por recriação de tabela (precedente `appointments`, `PRAGMA foreign_keys=OFF/ON`) para admitir `'ai_extracted'`.
- **gpt-4o-mini** para classificação/vision: já é o modelo usado no projeto (spy media), barato, `response_format=json_object`, `temperature=0`.
- **Nunca sobrescrever** item existente do utilizador — re-ingestão só preenche buracos.

---

## Plano de Implementação

### Fase 1 — Destravar o wizard

**Objetivo:** pular categorias críticas, sair do wizard em qualquer passo ("Preencher depois"), e não reexibir o wizard a cada visita.

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/components/agente/CamadaConhecimentoWizard.tsx` | `onSkip` passado sempre (críticas: "Pular esta etapa"); novo prop `onExit`; link "Preencher depois →" junto à barra de progresso + botão secundário no passo 0 |
| `frontend-crm/src/components/agente/CamadaConhecimento.tsx` | `load()` busca também `api.auth.me()` e guarda `userId`; `wizardDismissed` lido/persistido em localStorage `kb_wizard_dismissed_${userId}`; `onExit`/`onComplete` persistem; `kb_dismissed_sections_*` passa a usar o mesmo `userId` (corrige bug com base vazia) |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `11f8626` | Pular em todas as categorias, saída "Preencher depois", dispensa persistida |

**Detalhes do commit `11f8626`:**
- `CamadaConhecimentoWizard.tsx` — botão de pular passado a todos os passos de categoria (críticas: "Pular esta etapa", recomendadas: "Pular por agora"); novo prop `onExit`; link "Preencher depois →" ao lado do contador de passos (todos os passos exceto conclusão); botão secundário "Preencher depois" no passo 0
- `CamadaConhecimento.tsx` — `load()` busca `api.auth.me()` em paralelo e guarda `userId` (fallback: `items[0].user_id`); `wizardDismissed` lido de `localStorage kb_wizard_dismissed_${userId}` no load e gravado em `dismissWizard()` (chamado por `onExit` e `onComplete`); `kb_dismissed_sections_*` migrado para o mesmo `userId`

### Relatório da Fase 1 — o que mudou na prática

**Antes:** o wizard da Base de conhecimento obrigava a preencher todas as categorias críticas (sem botão de pular) e não tinha nenhuma saída — a única forma de chegar ao painel era completar o fluxo. Se saísse da página com a base vazia, o wizard recomeçava.
**Agora:** todas as etapas têm botão de pular, e há "Preencher depois" em qualquer passo (botão no primeiro passo e link no topo nos demais) que leva direto ao painel normal, onde cada categoria pode ser preenchida a qualquer momento. A escolha de "preencher depois" fica memorizada no navegador — o wizard não volta a aparecer.
**Para validar:** Cenários P1, P2 e P3 (secção "Checks de Validação").

---

### Fase 2 — Backend: fundação da ingestão

**Objetivo:** aceitar lote de fontes (PDF/imagem/planilha/txt/URL + descrição), enfileirar job interno e extrair texto de cada fonte — ainda sem LLM classificador.

| Arquivo | O que muda |
|---|---|
| `backend-crm/database.py` | Migração `ensure_knowledge_source_type_ai_extracted` (recriação com CHECK ampliado) |
| `backend-crm/models.py` | `KnowledgeItemOut.source_type` += `"ai_extracted"` |
| `backend-crm/services/jobs_service.py` | `TYPE_KNOWLEDGE_INGEST = "knowledge.ingest.internal"` |
| `backend-crm/services/knowledge_ingest/extractors.py` (novo) | Extração por tipo de fonte |
| `backend-crm/services/knowledge_ingest/ingest_worker.py` (novo) | Worker interno (padrão spy_media_worker) |
| `backend-crm/routes/knowledge_ingest.py` (novo) | `POST /api/knowledge/ingest` + `GET /api/knowledge/ingest/{job_id}` |
| `backend-crm/app.py` | Router + loop do worker no lifespan |
| `backend-crm/requirements.txt` | `+ pypdf` |

Limites: arquivo ≤10MB, imagem ≤5MB, 6 fontes/lote, 1 job ativo por user (409).

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `ddbfe15` | Migração do CHECK + extratores por tipo + worker interno + rotas de ingestão |

**Detalhes do commit `ddbfe15`:**
- `database.py` — `ensure_knowledge_source_type_ai_extracted`: recria `knowledge_items` com CHECK `('manual','file','ai_extracted')` (PRAGMA foreign_keys OFF/ON, idempotente); chamada no `init_db`
- `models.py` — `KnowledgeItemOut.source_type` aceita `"ai_extracted"`
- `services/jobs_service.py` — tipo `knowledge.ingest.internal`
- `services/knowledge_ingest/extractors.py` — `extract_source()`: PDF→pypdf, imagem→gpt-4o-mini vision (base64), txt/csv/xlsx→pandas (compartilhado com `routes/knowledge.py` via `extract_text_from_table_file`), URL→scraper httpx+bs4 (home + até 4 páginas internas relevantes); 15k chars máx/fonte
- `services/knowledge_ingest/ingest_worker.py` — `process_pending_knowledge_ingest_jobs()`: CAS pending→in_progress, retry até 3, grava `result` `phase="extracted"`
- `routes/knowledge_ingest.py` — POST multipart (`files` + `meta` JSON) com validação/rejeição por fonte e 409 para lote concorrente; GET de status com texto integral omitido do polling
- `app.py` — router registrado antes de `knowledge` + `_knowledge_ingest_worker_loop` (10s)

### Relatório da Fase 2 — o que mudou na prática

**Antes:** o backend só sabia extrair texto de arquivos .txt/.csv/.xlsx, num endpoint que criava um item avulso; PDF, imagem e URL de site não tinham como virar texto de conhecimento.
**Agora:** existe uma "esteira de ingestão": o frontend pode enviar um lote de até 6 fontes (PDF, imagem, planilha, txt e/ou URLs de site), cada uma com uma descrição livre, e um trabalhador em segundo plano extrai o texto de todas — PDF pela camada de texto, imagem por leitura de IA (OCR), site por navegação automática nas páginas relevantes. O resultado fica consultável por uma rota de status. Ainda não preenche as categorias sozinho — isso é a Fase 3 (classificador).
**Para validar:** Cenários B1 e B2, abaixo.

### Cenário B1 — Lote com txt + URL + extensão inválida (Fase 2)
- [x] POST `/api/knowledge/ingest` com um `.txt` de preços, uma URL e um `.docx` → responde `job_id`, `accepted: 2` e `rejected` com motivo `extensao_nao_suportada`
- [x] GET `/api/knowledge/ingest/{job_id}` após o worker rodar → `status: completed`, `result.sources[*].chars > 0` nas duas fontes aceitas
- [x] GET com id de job de outro tipo → 404
- **Validado em:** 06/08/2026 — job 481: txt extraiu 222 chars, https://example.com extraiu 172 chars, docx rejeitado no POST.

### Cenário B2 — Migração do banco sem perda (Fase 2)
- [x] Backup criado antes (`database/crm.db.bak-pre-ai-extracted`)
- [x] Após migração: contagens e conteúdo de `knowledge_items` (16) e `knowledge_item_media` (3) idênticos ao backup, `PRAGMA integrity_check` ok, INSERT com `source_type='ai_extracted'` aceito, segunda execução da migração é no-op
- **Validado em:** 06/08/2026 — comparação linha a linha real vs backup: idênticos.

### Cenário B3 — PDF e imagem reais (Fase 2, pendente de material)
- [ ] POST com um PDF com camada de texto → fonte `extracted` com `chars > 0`
- [ ] POST com uma imagem (foto de tabela de preços) → fonte `extracted` via vision (requer `OPENAI_API_KEY`)
- [ ] PDF escaneado sem texto → fonte `failed` com `reason: sem_texto_extraivel` e job ainda `completed`

### Fase 3 — Backend: classificação por LLM

**Objetivo:** o job classifica os textos extraídos nas categorias do template e grava `knowledge_items` com `source_type='ai_extracted'`, reportando `covered`/`uncovered`/`skipped_existing`.

| Arquivo | O que muda |
|---|---|
| `backend-crm/services/knowledge_ingest/classifier.py` (novo) | gpt-4o-mini, JSON por categoria, truncagem 15k/fonte e 60k total |
| `backend-crm/services/knowledge_ingest/ingest_worker.py` | Classifica + INSERT; dispara meta-prompter se cobrir `objections_faq` |
| `backend-crm/services/meta_prompter_trigger.py` (novo) | `trigger_meta_prompter_for_knowledge` extraído de `routes/knowledge.py` para uso compartilhado rota + worker |
| `backend-crm/routes/knowledge.py` | Importa o trigger do módulo compartilhado (remove duplicação) |

### Commits Fase 3

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `1a0ba53` | Classificador gpt-4o-mini + gravação de itens `ai_extracted` + result covered/uncovered/skipped |

**Detalhes do commit `1a0ba53`:**
- `classifier.py` — `classify_sources()`: prompt com contexto do negócio + categorias (key/label/description) + fontes numeradas com a descrição do usuário; system prompt proíbe inventar dados; `response_format=json_object`, `temperature=0`, timeout 120s, 60k chars máx; valida keys contra a lista enviada e descarta conteúdo <20 chars
- `ingest_worker.py` — pipeline completo: extrai → classifica → INSERT `ai_extracted` só em categoria sem item do usuário (nunca sobrescreve) → meta-prompter se cobrir `objections_faq` → result `{phase:"done", sources, covered:[{category,item_id,preview}], uncovered, skipped_existing}` sem texto integral
- `meta_prompter_trigger.py` — gatilho compartilhado entre a rota de edição manual e o worker

### Relatório da Fase 3 — o que mudou na prática

**Antes:** a esteira de ingestão só extraía o texto dos materiais e guardava o resultado no job — nada aparecia na base de conhecimento.
**Agora:** depois de extrair, a IA lê os textos e preenche sozinha as categorias da base que os materiais cobrem, gravando cada uma como item normal (marcado como criado por IA, editável como qualquer outro). Categorias que o usuário já preencheu nunca são sobrescritas. O resultado do lote diz o que foi preenchido, o que ficou pendente e o que foi pulado por já existir.
**Para validar:** Cenários B4 e B5 (já validados) e B6, abaixo.

### Cenário B4 — Lote classifica e grava (Fase 3)
- [x] POST com txt de preços + categorias `service_pricing_table` e `transformation_stories` → `covered` contém `service_pricing_table` com `item_id` e preview; `uncovered` contém `transformation_stories`
- [x] Item gravado com `source_type='ai_extracted'`, título = label da categoria, valores preservados (acentuação correta confirmada por codepoints no banco)
- **Validado em:** 06/08/2026 — job 482, item 22 criado para o user de teste.

### Cenário B5 — Nunca sobrescreve item existente (Fase 3)
- [x] Segundo lote na mesma categoria → `covered: []`, `skipped_existing: ['service_pricing_table']`, contagem de itens da categoria permanece 1
- **Validado em:** 06/08/2026 — job 483.

### Cenário B6 — Conteúdo ingerido chega ao agente (Fase 3)
*(Movido para a secção da Fase 4, onde foi parcialmente validado — ver abaixo.)*

### Fase 4 — Frontend: passo "Importar materiais"

**Objetivo:** UI de envio de fontes com descrição, polling do job, resumo do que a IA preencheu; wizard segue só com as pendentes.

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/services/api.ts` | `ingestKnowledge()` + `getKnowledgeIngestStatus()`; tipo `source_type` += `'ai_extracted'` |
| `frontend-crm/src/components/agente/KnowledgeIngestPanel.tsx` (novo) | Componente compartilhado wizard/painel |
| `frontend-crm/src/components/agente/CamadaConhecimentoWizard.tsx` | Passo "Importar materiais (opcional)"; categorias pendentes derivadas de `filledKeys` |
| `frontend-crm/src/components/agente/CamadaConhecimento.tsx` | Botão "Importar materiais" (modal); badge "IA" em itens `ai_extracted`; fix `onExit` recarrega itens |

### Commits Fase 4

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `b8f3644` | Panel de ingestão + passo no wizard + botão/badge no painel + client API |

**Detalhes do commit `b8f3644`:**
- `KnowledgeIngestPanel.tsx` — lote de arquivos e URLs com descrição por fonte, validação client-side (extensão/tamanho/duplicado), polling 3s até 5min, resumo final (preenchidas com preview / pendentes / já existentes / fontes com falha em linguagem amigável)
- `CamadaConhecimentoWizard.tsx` — passo "Importar materiais (opcional)" entre contexto e categorias; ao concluir, `wizardCats` congela só as pendentes (as cobertas pela IA saem do fluxo e contam no StepDone); "Preencher manualmente →" mantém o fluxo completo
- `CamadaConhecimento.tsx` — botão "✦ Importar materiais" no cabeçalho das seções guiadas (modal com o mesmo panel + `load()` ao concluir); badge "✦ IA" em `GuidedSectionCard` para itens `ai_extracted`; **fix descoberto no teste**: `onExit` do wizard não recarregava os itens — sair do wizard logo após a ingestão mostrava o painel desatualizado
- `api.ts` — `ingestKnowledge(files, meta)` multipart + `getKnowledgeIngestStatus(jobId)` + tipos

### Relatório da Fase 4 — o que mudou na prática

**Antes:** a esteira de ingestão só existia por API — nenhuma tela permitia enviar materiais.
**Agora:** no primeiro acesso à Camada 4, depois de confirmar o contexto, aparece o passo "Importar materiais": você adiciona PDF, imagem, planilha, texto e/ou o link do site, descreve cada um ("minha tabela de preços"), e a IA preenche as seções que os materiais cobrirem — o passo a passo continua apenas com as pendentes, cada uma com opção de pular. O mesmo importador fica disponível a qualquer momento pelo botão "✦ Importar materiais" no painel da Camada 4, e os itens criados pela IA aparecem com o selo "✦ IA" (editáveis como qualquer outro).
**Para validar:** Cenários F1 e F2 (validados) e B3/B6 (pendentes), abaixo.

### Cenário F1 — Jornada completa no wizard (Fase 4)
- [x] Wizard → contexto → passo "Importar materiais" com panel de fontes
- [x] Upload de `.txt` com bio + preview de sessão + preços e descrição livre → "Processar com IA" → tela de progresso → resumo: 3 preenchidas (Bio do Profissional, Preview da Sessão, Tabela de Serviços e Preços com valores exatos) e 13 pendentes
- [x] "Continuar →" → wizard segue só com as pendentes ("Seção crítica 1 de 2", total de passos caiu de 16 para 13)
- **Validado em:** 06/08/2026 — ao vivo via browser (MCP chrome-devtools).

### Cenário F2 — Painel: botão de importar + badge IA (Fase 4)
- [x] Botão "✦ Importar materiais" visível no cabeçalho das seções guiadas
- [x] Cards "Bio do Profissional" e "Preview da Sessão" com badge "✦ IA" e conteúdo correto; tabela de preços cadastrada na seção multi-tabela; score subiu para "Funcional básico"
- **Validado em:** 06/08/2026 — ao vivo via browser.

### Cenário B6 — Conteúdo ingerido chega ao agente *(parcialmente validado)*
- [x] Itens `ai_extracted` entram no ContextBundle — confirmado executando `_load_knowledge_items(15)`: as 3 categorias ingeridas presentes, incluindo a tabela de preços renderizada
- [ ] Resposta do playground usa os valores ingeridos — **não conclusivo no teste**: o material de teste (massoterapia) contradiz o nicho do AI Profile da conta de teste (advocacia/automação — "Digital Pro"), e o agente corretamente priorizou o perfil ("não oferecemos sessões de massagem"). Validar com materiais coerentes com o nicho real do perfil.
- **Registrado em:** 06/08/2026. Os 3 itens de teste incoerentes foram removidos da conta de teste após o registro.

---

## Checks de Validação

### Cenário P1 — Pular o wizard inteiro (Fase 1)
- [x] Conta com base de conhecimento vazia → abrir Camada 4 → wizard aparece
- [x] No passo 0, clicar "Preencher depois" → cai no painel normal com score "Não funcional" e categorias com botão "Preencher"
- [x] Recarregar a página com base ainda vazia → wizard **não** reaparece
- **Validado em:** 06/08/2026 — testado ao vivo via browser (MCP chrome-devtools) na conta de teste (user_id 15). Base zerada removendo os 2 itens pré-existentes (categoria service_pricing_table) para poder exercitar o estado vazio.

### Cenário P2 — Pular categoria crítica (Fase 1)
- [x] Entrar no wizard, avançar até uma categoria crítica
- [x] Botão "Pular esta etapa" visível e funcional → avança sem salvar
- [x] StepDone mostra contadores coerentes (ex.: 0/N críticas)
- **Validado em:** 06/08/2026 — em "Seção crítica 1 de 5" (Bio do Profissional), clicado "Pular esta etapa" sem preencher a textarea; avançou para "Seção crítica 2 de 5" (Histórias de Transformação) sem erro e sem salvar item.

### Cenário P3 — Link "Preencher depois" nos passos intermédios (Fase 1)
- [x] Num passo de categoria qualquer, clicar "Preencher depois →" no cabeçalho → sai do wizard para o painel normal
- **Validado em:** 06/08/2026 — clicado em "Seção crítica 2 de 5"; caiu direto no painel normal (score "Não funcional", categorias com "Preencher →").

*(Checks das Fases 2–4 serão adicionados quando cada fase for implementada.)*

---

## Ajustes Possíveis Pós-Implementação

- Preview aprovável antes de gravar itens da IA (draft + `POST /ingest/{job_id}/apply`)
- `service_pricing_table` extraída para o formato `structured_v1` (Fase 3 grava texto livre, suportado)
- Limite de lotes de ingestão por dia por plano (entitlements)
- Sites JS-heavy: scraper não renderiza JS — headless browser fora do escopo
- PDF escaneado sem camada de texto: reportado como `sem_texto_extraivel`; orientação é enviar como imagem (vision faz OCR)
