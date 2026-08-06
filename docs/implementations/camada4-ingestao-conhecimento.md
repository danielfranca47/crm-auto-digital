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

### Fase 2 — Backend: fundação da ingestão *(planeada)*

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

### Fase 3 — Backend: classificação por LLM *(planeada)*

**Objetivo:** o job classifica os textos extraídos nas categorias do template e grava `knowledge_items` com `source_type='ai_extracted'`, reportando `covered`/`uncovered`/`skipped_existing`.

| Arquivo | O que muda |
|---|---|
| `backend-crm/services/knowledge_ingest/classifier.py` (novo) | gpt-4o-mini, JSON por categoria, truncagem 15k/fonte e 60k total |
| `backend-crm/services/knowledge_ingest/ingest_worker.py` | Classifica + INSERT; dispara meta-prompter se cobrir `objections_faq` (extrair `_trigger_meta_prompter_for_knowledge` para módulo compartilhado) |

### Fase 4 — Frontend: passo "Importar materiais" *(planeada)*

**Objetivo:** UI de envio de fontes com descrição, polling do job, resumo do que a IA preencheu; wizard segue só com as pendentes.

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/services/api.ts` | `ingestKnowledge()` + `getKnowledgeIngestStatus()`; tipo `source_type` += `'ai_extracted'` |
| `frontend-crm/src/components/agente/KnowledgeIngestPanel.tsx` (novo) | Componente compartilhado wizard/painel |
| `frontend-crm/src/components/agente/CamadaConhecimentoWizard.tsx` | Passo "Importar materiais (opcional)"; categorias pendentes derivadas de `filledKeys` |
| `frontend-crm/src/components/agente/CamadaConhecimento.tsx` | Botão "Importar materiais" (modal); badge "IA" em itens `ai_extracted` |

---

## Checks de Validação

### Cenário P1 — Pular o wizard inteiro (Fase 1)
- [ ] Conta com base de conhecimento vazia → abrir Camada 4 → wizard aparece
- [ ] No passo 0, clicar "Preencher depois" → cai no painel normal com score "Não funcional" e categorias com botão "Preencher"
- [ ] Recarregar a página com base ainda vazia → wizard **não** reaparece

### Cenário P2 — Pular categoria crítica (Fase 1)
- [ ] Entrar no wizard, avançar até uma categoria crítica
- [ ] Botão "Pular esta etapa" visível e funcional → avança sem salvar
- [ ] StepDone mostra contadores coerentes (ex.: 0/N críticas)

### Cenário P3 — Link "Preencher depois" nos passos intermédios (Fase 1)
- [ ] Num passo de categoria qualquer, clicar "Preencher depois →" no cabeçalho → sai do wizard para o painel normal

*(Checks das Fases 2–4 serão adicionados quando cada fase for implementada.)*

---

## Ajustes Possíveis Pós-Implementação

- Preview aprovável antes de gravar itens da IA (draft + `POST /ingest/{job_id}/apply`)
- `service_pricing_table` extraída para o formato `structured_v1` (Fase 3 grava texto livre, suportado)
- Limite de lotes de ingestão por dia por plano (entitlements)
- Sites JS-heavy: scraper não renderiza JS — headless browser fora do escopo
- PDF escaneado sem camada de texto: reportado como `sem_texto_extraivel`; orientação é enviar como imagem (vision faz OCR)
