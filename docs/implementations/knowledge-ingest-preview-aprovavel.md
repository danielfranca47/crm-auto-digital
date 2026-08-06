# Ingestão de conhecimento — preview aprovável antes de gravar

**Branch:** `feat/ajuste-configuracao-ai-profile`
**Status:** Em andamento

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`docs/implementations/camada4-ingestao-conhecimento.md`.

Hoje, quando o worker de ingestão (`backend-crm/services/knowledge_ingest/ingest_worker.py`)
classifica os textos extraídos, ele já grava os itens `ai_extracted` diretamente em
`knowledge_items` (função `_insert_ai_item`) — sem passo de revisão humana antes da gravação.
Isso é seguro porque nunca sobrescreve categoria já preenchida pelo utilizador, mas significa que
conteúdo mal classificado ou impreciso só é corrigido depois de já estar ativo na base (visível ao
agente).

A ideia é introduzir um estado intermédio "draft": o job termina com os itens propostos mas ainda
não gravados, e o utilizador aprova (grava) ou descarta cada um antes de entrar na base — via um
novo endpoint `POST /ingest/{job_id}/apply`.

---

## Problemas Identificados (estado anterior)

1. **Gravação direta sem revisão:** `ingest_worker.py:_process_ingest_job` chama `_insert_ai_item`
   assim que a classificação retorna conteúdo para uma categoria — não há passo de confirmação.
2. **Sem endpoint de apply/descarte:** `routes/knowledge_ingest.py` só tem `POST /ingest` e
   `GET /ingest/{job_id}` — não existe rota para aprovar ou descartar itens propostos.

---

## Abordagem

Não gravar nada em `knowledge_items` até o apply. O job termina com os itens propostos guardados
só em `jobs.result` (JSON) — não na tabela. Isso evita ter que auditar os 6 arquivos que hoje leem
`knowledge_items` diretamente (`ingest_worker.py`, `routes/knowledge.py`, `routes/executor.py`,
`services/ai_orchestrator/orchestrator.py`, `routes/qualification.py`, `database.py`): um item
"draft" simplesmente não existe na tabela ainda, então nenhum desses call sites corre risco de
mostrar conteúdo não aprovado ao agente.

```
POST /ingest → job criado (pending)
  → worker: extrai fontes → classifica → NÃO grava
    → jobs.result = { proposed: [{category,label,content,preview}], uncovered, skipped_existing, sources }
GET /ingest/{id} → frontend mostra os "proposed" para revisão (conteúdo completo, não só preview)
  ├─ utilizador aprova algumas categorias
  └─ utilizador descarta as demais (= simplesmente não marca; nada foi escrito, não precisa limpeza)
POST /ingest/{id}/apply { approved: [key,...] }
  → grava via _insert_ai_item só as categorias aprovadas
  → move essas categorias de "proposed" para "applied" dentro de jobs.result (idempotente —
    reaplicar as mesmas keys não duplica)
  → se aplicou "objections_faq", dispara trigger_meta_prompter_for_knowledge (agora aqui, já que é
    aqui que a gravação de fato acontece)
```

---

## Plano de Implementação

### Fase 1 — Backend: job propõe em vez de gravar + endpoint de apply

**Objetivo:** o worker para de gravar direto; um novo endpoint aplica as categorias aprovadas.

| Arquivo | O que muda |
|---|---|
| `backend-crm/services/knowledge_ingest/ingest_worker.py` | `_process_ingest_job` para de chamar `_insert_ai_item` inline; monta `proposed` (content completo + preview) em vez de `covered`; remove o disparo do meta_prompter daqui. Nova função pública `apply_ingest_review(job_id, user_id, approved_keys)`. |
| `backend-crm/routes/knowledge_ingest.py` | Nova rota `POST /api/knowledge/ingest/{job_id}/apply`; `_sanitize_result` passa a preservar `proposed[].content` (só `sources[].text` é removido do payload de polling). |

```python
# ANTES (ingest_worker.py:_process_ingest_job)
label = cat.get("label") or key
item_id = _insert_ai_item(user_id, label, key, entry["content"])
covered.append({"category": key, "item_id": item_id, "preview": entry["content"][:_PREVIEW_CHARS]})
...
if any(c["category"] == "objections_faq" for c in covered):
    trigger_meta_prompter_for_knowledge(user_id)

# DEPOIS
label = cat.get("label") or key
proposed.append({
    "category": key, "label": label,
    "content": entry["content"],
    "preview": entry["content"][:_PREVIEW_CHARS],
})
# nada é gravado; meta_prompter só dispara em apply_ingest_review()
```

`apply_ingest_review(job_id, user_id, approved_keys)`:
- Valida `job.type == TYPE_KNOWLEDGE_INGEST`, `job.user_id == user_id`, `job.status == 'completed'`.
- Para cada key em `approved_keys` presente em `result.proposed` e ainda não em `result.applied`:
  reconfirma `_existing_categories` (proteção contra corrida com edição manual concorrente feita
  entre o fim do job e o apply); se ainda livre, insere via `_insert_ai_item`, move a entrada de
  `proposed` para `applied` (com `item_id`).
- Persiste `jobs.result` atualizado (`UPDATE jobs SET result = ...`, mesmo padrão já usado em
  `process_pending_knowledge_ingest_jobs`).
- Dispara `trigger_meta_prompter_for_knowledge` se `objections_faq` foi aplicado nesta chamada.
- Retorna `{applied: [...], already_applied: [...], now_existing: [...]}`.

### Fase 2 — Frontend: passo de revisão antes de aplicar

**Objetivo:** o painel de importação mostra as propostas e só grava o que o utilizador aprovar.

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/services/api.ts` | `KnowledgeIngestStatus.result` troca `covered` por `proposed`/`applied` (com `content` completo em `proposed`); nova função `applyKnowledgeIngest(jobId, approved)`. |
| `frontend-crm/src/components/agente/KnowledgeIngestPanel.tsx` | Nova fase `'review'` entre `'processing'` e `'done'` — lista os itens `proposed` com conteúdo completo e checkbox (default marcado), botão "Aplicar selecionadas". Se `proposed` vier vazio, pula direto para `'done'`. |

Sem mudança na assinatura de `onFinished(coveredKeys)` — passa a receber as keys efetivamente
aplicadas, então `CamadaConhecimento.tsx` e `CamadaConhecimentoWizard.tsx` não precisam mudar.

---

## Checks de Validação

### Cenário C1 — Job propõe sem gravar (Fase 1)
- [ ] Criar um lote via `POST /api/knowledge/ingest` com ao menos uma fonte válida
- [ ] Aguardar o worker (loop de 10s) completar o job
- [ ] `GET /ingest/{id}` mostra `result.proposed` preenchido e `result.applied` vazio
- [ ] Confirmar que `knowledge_items` **não** recebeu nenhuma linha nova ainda

### Cenário C2 — Apply grava e é idempotente (Fase 1)
- [ ] Chamar `POST /ingest/{id}/apply` com uma categoria de `proposed`
- [ ] Confirmar que o item foi criado em `knowledge_items` (`source_type='ai_extracted'`)
- [ ] Repetir a mesma chamada com a mesma key — confirmar que não duplica (retorna em `already_applied`)

### Cenário P1 — Revisão no painel (Fase 2)
- [ ] Abrir "Importar materiais" (wizard ou painel normal), enviar um lote
- [ ] Após o processamento, confirmar que aparece a lista de propostas com conteúdo completo (não só preview)
- [ ] Desmarcar uma categoria, aplicar as demais
- [ ] Confirmar que só as categorias marcadas aparecem na base de conhecimento depois

---

## Ajustes Possíveis Pós-Implementação

- Reabrir o painel para retomar uma revisão pendente de um job `completed` anterior (hoje, se o
  utilizador fechar o painel sem revisar, as propostas ficam "perdidas" — nada foi escrito, mas
  também não há como retomar a revisão sem reprocessar o lote).
- Edição do conteúdo proposto antes de aprovar (hoje é só aprovar/descartar, sem editar o texto).
