# IA mãe classifica estágio do lead monitorado

**Branch:** `feat/monitoramento-colaborador-classificacao-ia`
**Status:** Em andamento

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`monitoramento-colaborador-whatsapp.md` (base do monitoramento de WhatsApp de
colaborador — ver [`docs/architecture/collab-monitor.md`](../architecture/collab-monitor.md)).

Hoje, todo lead criado pelo monitoramento de colaborador nasce na categoria
fixa `"monitoring"` (coluna "Monitorado" do Kanban) e nunca sai dali
automaticamente. O utilizador quer que a IA leia a conversa do colaborador
com o lead e identifique o estágio real (qualificação, apresentação,
fechamento, etc.) — o mesmo tipo de classificação que já existe para o
pipeline do agente (`suggested_category` em `decision_engine.py`) —
posicionando o lead monitorado na coluna correspondente do Kanban.

**Decisões de produto validadas com o utilizador:**
- **Destino:** mover o card para a coluna real do Kanban (não ficar só com
  selo em "Monitorado", misturando com leads do bot).
- **Gatilho:** reclassificar a cada mensagem **inbound** do lead (não a cada
  mensagem do colaborador/`from_me`).
- **Guardrail:** basear-se no comportamento já validado da LLM mãe (ver
  "Abordagem" abaixo para a adaptação necessária).

---

## Problemas Identificados (estado anterior)

1. **Sem classificação de estágio:** `services/collab_monitor/monitor_inbound_handler.py::handle_monitor_inbound()`
   (linhas 111-158) grava a mensagem e retorna — nunca chama
   `orchestrator`/`decision_engine`/guardrails, por design (isolamento total
   do pipeline de IA real). Não existe nenhum caminho que leia a conversa e
   sugira estágio para leads `category='monitoring'`.
2. **Coluna fixa:** lead nasce em `find_or_create_monitor_lead()`
   (linha 78-96 do mesmo arquivo) sempre com `category='monitoring'` e nunca
   é atualizado depois — confirmado também em `docs/architecture/collab-monitor.md`
   (seção "Fora do escopo desta base").

---

## Abordagem

### Por que não reaproveitar `decision_engine.py` (LLM mãe) diretamente

O guardrail de categoria da mãe (`backend-executors/app/services/decision_engine.py`)
tem duas camadas:

1. **Camada de prompt** (linhas ~2160-2193): postura conservadora — só
   sugere categoria quando há sinal explícito no texto, senão retorna
   `null`. Não depende de nenhum estado estruturado — é só técnica de
   prompt, então **transfere 1:1** para o novo classificador.
2. **Camada de código** (`apply_mother_category_guardrails`,
   `services/qualification_guardrails.py`): bloqueia avanço com base em
   `qualification_state` (campos como `service_interest`, `urgency` etc.)
   que só existem porque o **próprio bot** pergunta e extrai esses campos
   turno a turno. No monitoramento não há bot perguntando nada — é um
   humano escrevendo livremente — então esse estado nunca é populado para
   leads monitorados. Reaproveitar essa camada exigiria construir um
   extrator de qualificação paralelo para conversas humanas — fora do
   escopo deste pedido.

**Conclusão:** reaproveitar a técnica de prompt (null quando incerto, nunca
inventar categoria) + adicionar 1 guardrail estrutural novo, possível sem o
estado que falta: **nunca mover o lead para trás no funil** (ordem
`qualification < apresentation < follow-up < closing < client-list`;
`prospect-refused`/`disqualified` são saídas, permitidas a qualquer
momento). O colaborador sempre pode corrigir manualmente pelo Kanban.

### Padrões existentes reaproveitados

- **Análise via 1 chamada LLM, JSON estruturado:**
  `services/spy_agent/module_sales_pipeline.py` — mesmo estilo (system
  prompt + `response_format=json_object`), hoje aplicado agregado/1x ao
  Agente Espião. O módulo novo usa o mesmo formato, por lead/mensagem, com
  enum de categoria restrito ao Kanban real.
- **Processamento assíncrono sem tocar no pipeline de IA:** padrão de job
  interno já usado por `spy.media.process`
  (`services/spy_agent/spy_media_worker.py::process_pending_spy_media_jobs()`
  + `services/jobs_service.py::create_job()` + loop registrado no
  `lifespan` de `app.py`). Preferido a `BackgroundTasks` do FastAPI: job
  pendente sobrevive a restart do processo, e já tem retry/backoff testado.
- **Log de auditoria:** `services/lead_category_policy.py::_disable_bot_for_category_entry()`
  grava em `prospection_logs` — novo módulo usa o mesmo padrão
  (`action='collab_monitor_category_changed'`).

### Fluxo resultante

```
Mensagem inbound do lead monitorado (handle_monitor_inbound)
  → salva em `messages` (como hoje)
  → cria job "collab_monitor.classify.local" (create_job)

Worker interno (process_pending_collab_monitor_classify_jobs, loop no app.py)
  → carrega histórico de mensagens do lead
  → 1 chamada LLM (classifier.py): suggested_category | null
      ├─ null → nada muda
      ├─ retrocesso no funil → ignora (guardrail)
      ├─ prospect-refused/disqualified → sempre aplica (saída)
      └─ avanço válido → UPDATE leads.category + log em prospection_logs
```

### Por que atualizar a categoria direto no banco

`routes/leads.py` (linha 946) bloqueia avanço `qualification →
apresentation/follow-up/closing` se `qualification_incomplete` — checagem
baseada no `qualification_state` que não existe para leads monitorados.
Como o lead nasce em `category='monitoring'` (não `qualification`), essa
regra nem chegaria a disparar na prática, mas para não acoplar o worker a
uma rota HTTP pensada para o fluxo real, ele atualiza `leads.category`
diretamente via `sqlite3.Connection` (mesmo padrão usado em todo o
`backend-crm`).

---

## Plano de Implementação

### Fase 1 — Backend: classificação assíncrona + movimentação de categoria

**Objetivo:** lead monitorado passa a ser reclassificado e movido de coluna
automaticamente a cada mensagem inbound.

| Arquivo | O que muda |
|---|---|
| `backend-crm/services/jobs_service.py` | Nova constante `TYPE_COLLAB_MONITOR_CLASSIFY = "collab_monitor.classify.local"` |
| `backend-crm/services/collab_monitor/monitor_inbound_handler.py` | Em `handle_monitor_inbound()`, após salvar mensagem inbound (não `from_me`) com texto: enfileira job de classificação |
| `backend-crm/services/collab_monitor/classifier.py` (novo) | 1 chamada LLM (`gpt-4o-mini`, JSON), enum restrito, postura "null se incerto" |
| `backend-crm/services/collab_monitor/classify_worker.py` (novo) | `process_pending_collab_monitor_classify_jobs()` — lease, classifica, aplica guardrail de não-retrocesso, atualiza categoria, loga |
| `backend-crm/app.py` | Novo `_collab_monitor_classify_worker_loop()` registrado no `lifespan` |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `7632fb7` | Job de classificação assíncrona + guardrail de não-retrocesso + movimentação de categoria + log de auditoria |

**Detalhes do commit `7632fb7`:**
- `services/jobs_service.py` — novo tipo de job `collab_monitor.classify.local`
- `services/collab_monitor/monitor_inbound_handler.py` — enfileira o job a cada mensagem inbound do lead (não do colaborador)
- `services/collab_monitor/classifier.py` (novo) — 1 chamada LLM read-only, enum restrito, postura "null se incerto"
- `services/collab_monitor/classify_worker.py` (novo) — lease do job, guardrail de não-retrocesso no funil, `UPDATE leads.category`, log em `prospection_logs`
- `app.py` — registra `_collab_monitor_classify_worker_loop` no `lifespan`
- `scripts/test_collab_monitor_classify_flow.py` (novo) — script de validação ponta a ponta (Cenários C1/C2), com o classificador mockado para determinismo

### Relatório da Fase 1 — o que mudou na prática

**Antes:** todo lead do monitoramento de colaborador ficava para sempre na coluna "Monitorado" do Kanban, mesmo depois de a conversa evoluir para proposta, negociação ou fechamento.

**Agora:** a cada mensagem que o lead monitorado manda, o sistema lê a conversa (IA, sem responder nem enviar nada) e, se houver sinal claro de avanço de estágio, move o card sozinho para a coluna real (Qualificação, Apresentação, Follow-up, Fechamento, Cliente, Recusado ou Desqualificado). Nunca move o card para trás por engano — uma mensagem ambígua depois de já estar em "Fechamento", por exemplo, é ignorada.

**Para validar:** Cenário C1 e C2, abaixo — já rodados com o script `scripts/test_collab_monitor_classify_flow.py` (classificador mockado, valida o mecanismo). O julgamento real da IA sobre uma conversa de verdade fica para um teste manual/ao vivo (não coberto por este script).

### Fase 2 — Frontend: badge "Monitorado" persistente no card

**Objetivo:** card continua identificável como monitorado mesmo fora da
coluna "Monitorado".

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/components/LeadCard.tsx` | Badge quando `lead.collab_monitor_instance_id` não for nulo |

---

## Checks de Validação

### Cenário C1 — Avanço de estágio ponta a ponta
- [x] Simular payloads inbound chamando `handle_monitor_inbound()` diretamente representando uma conversa que evolui de contato inicial até fechamento
- [x] Rodar `process_pending_collab_monitor_classify_jobs()` após cada mensagem
- [x] Confirmar no banco (`leads.category`, `prospection_logs`) que o lead avançou estágio a estágio, sem pular etapas de forma inconsistente
- **Validado em:** 08/09/2026 — `scripts/test_collab_monitor_classify_flow.py`, classificador mockado (determinístico): `monitoring → qualification → apresentation → closing`, 1 log de auditoria por avanço. Confirma o mecanismo; não substitui teste manual com LLM real.

### Cenário C2 — Guardrail de retrocesso
- [x] Levar o lead até `closing`
- [x] Enviar mensagem ambígua que levaria a LLM a sugerir estágio anterior
- [x] Confirmar que o worker não regride a categoria
- **Validado em:** 08/09/2026 — mesmo script; classificador mockado para sugerir `qualification` com o lead já em `closing` — categoria permaneceu `closing`, nenhum log novo criado.

### Cenário P1 — Visual no Kanban
- [ ] Após C1, abrir o Kanban (`frontend-crm`) via browser
- [ ] Confirmar que o card aparece na coluna correspondente com a badge "Monitorado" visível

---

## Ajustes Possíveis Pós-Implementação

- **Custo de LLM por mensagem inbound:** 1 chamada `gpt-4o-mini` por
  mensagem do lead monitorado, sem debounce — decisão consciente do
  utilizador ("a cada mensagem inbound"). Se o volume crescer, considerar
  debounce (ex.: só reclassificar se passou X minutos desde a última).
- **Tratamento de mídia:** mensagens sem texto continuam ignoradas (mesma
  limitação de `handle_monitor_inbound` hoje) — fora do escopo desta
  iteração.
