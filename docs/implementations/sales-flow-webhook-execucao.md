# Executar em runtime o bloco `webhook` do Fluxo de Venda

**Branch:** `feat/sales-flow-webhook-execucao`
**Status:** Em andamento — P1, P2 e P3 validados (26/08/2026), pendente: Cenário C1 (WhatsApp real, combinado com `feat/sales-flow-espera-pausa`)

---

## Motivação

O builder visual do Fluxo de Venda (Camada 7, `CamadaFluxoVenda.tsx`) já permite
configurar um bloco de ação `webhook` (chamar uma URL externa quando um trigger
dispara) — com UI completa (`url`, `method`, `note`) e persistência em
`sales_flow.phases[].blocks[]`. O motor de decisão (`decision_engine.py`) já
"decide" disparar esse bloco e emite um `system_action` correspondente, mas
nenhum dos dois pontos de dispatch (WhatsApp real em `backend-crm/routes/executor.py`,
Playground em `backend-crm/routes/playground.py`) trata esse tipo de ação — ela
cai numa cadeia de `elif` sem `else`, é silenciosamente ignorada, e o webhook
nunca é chamado de verdade.

Este item era, junto com `espera` e `condicao`, parte do escopo original de
`sales-flow-webhook-condicao-espera-runtime.md`. `condicao` já foi resolvido em
`fix-fluxo-vendas-ramificacao.md`. `espera` foi implementado em
`feat/sales-flow-espera-pausa` (ainda não graduado — falta só o Cenário C1,
WhatsApp real, que o usuário pediu para validar junto com este `webhook`).
Este arquivo cobre exclusivamente o `webhook`; o placeholder original foi
removido (`git rm`) por estar totalmente substituído pelos dois novos arquivos.

---

## Problemas Identificados (estado anterior)

1. **`webhook` sem execução real (WhatsApp):** `backend-crm/routes/executor.py`,
   `_dispatch_system_actions()` — não existe `elif atype == "webhook"`. O
   usuário configura a URL na UI, o motor de decisão emite o `system_action`,
   e nada acontece.
2. **`webhook` sem tratamento no Playground:** mesmo problema em
   `backend-crm/routes/playground.py` — sem sinal nenhum de que o bloco
   disparou durante um teste.
3. **`system_action` sem `block_id`/`phase_id`:** `decision_engine.py:892-900`
   emite `{"type": "webhook", "url", "method", "note"}` sem identificar qual
   bloco/fase originou a chamada — diferente do padrão já usado por
   `sales_flow_pause_set` (que inclui os dois campos), dificultando
   rastreabilidade em log/payload de job.

---

## Abordagem

```
Bloco `webhook` dispara (decision_engine.py)
  → system_action { type: "webhook", url, method, note, block_id, phase_id }

WhatsApp real (executor.py, _dispatch_system_actions)
  → monta payload (lead_id, phone, name, email, note, block_id, phase_id, triggered_at)
  → create_job(TYPE_SALES_FLOW_WEBHOOK)   # INSERT rápido, não bloqueia
       ↓
  backend-executors/app/workers/sales_flow_webhook_worker.py (novo, clona email_worker.py)
       ↓
  backend-executors/app/runners/sales_flow_webhook.py (novo, clona runners/email.py)
       → httpx.request(method, url, json=payload, timeout=10s)
       ├─ 2xx → complete_job
       └─ erro/timeout/5xx/429 → fail_job(retryable=True) → backoff → até 3 tentativas
          4xx específico → fail_job(retryable=False)

Playground (playground.py)
  → NUNCA dispara HTTP real (mesmo princípio de send_message no sandbox)
  → adiciona auto_item tipo "text" já suportado pelo frontend:
    "🌐 Webhook (simulado): POST https://... — <note>"
```

**Decisão de arquitetura:** clonar o padrão leve de `email` (job dedicado +
worker/runner próprios, usando só `crm_client.claim_job/get_job/complete_job/fail_job`
genéricos), não o padrão pesado de `whatsapp` (acoplado ao pipeline de geração
de resposta via LLM). `webhook` é uma chamada de I/O externa independente do
LLM — mesmo formato estrutural que `email`.

---

## Plano de Implementação

### Fase 1 — Execução real (WhatsApp) + simulação (Playground) + worker dedicado

**Objetivo:** o bloco `webhook` passa a disparar de verdade no WhatsApp real
(via job assíncrono com retry) e a dar sinal visível no Playground sem efeitos
colaterais reais.

| Arquivo | O que muda |
|---|---|
| `backend-crm/services/jobs_service.py` | novo `TYPE_SALES_FLOW_WEBHOOK = "sales_flow.webhook.dispatch"` |
| `backend-crm/routes/executor.py` | novo `elif atype == "webhook"` em `_dispatch_system_actions`: monta payload + `create_job` |
| `backend-crm/routes/playground.py` | novo `elif atype == "webhook"`: `auto_item` simulado, sem chamada HTTP real |
| `backend-executors/app/services/decision_engine.py` | `system_action` de `webhook` passa a incluir `block_id`/`phase_id` |
| `backend-executors/app/runners/sales_flow_webhook.py` | novo runner (clona `runners/email.py`) |
| `backend-executors/app/workers/sales_flow_webhook_worker.py` | novo worker (clona `workers/email_worker.py`) |
| `backend-executors/Procfile` | nova linha `sales_flow_webhook_worker: python -m app.workers.sales_flow_webhook_worker` |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `7b70dcf` | job dedicado + dispatch real (executor.py) + simulação (playground.py) + worker/runner + docs |
| 2 | `2105249` | registro do hash do commit 1 no arquivo |
| 3 | `75ecf8d` | fix: coluna correta do nome do lead no payload (`contactName`/`companyName`, não `name`) — encontrado durante validação do P2 |

---

## Checks de Validação

Ambiente: worktree isolada `feat/sales-flow-webhook-execucao` (nasceu de
`main`, banco vazio) — conta de teste registrada do zero (mesmas credenciais
de `_conta-teste-local.md`, ids internos diferentes por ser um banco novo),
assinatura `crm_internal` inserida manualmente (sem checkout de pagamento
local), AI Profile com `sales_flow.enabled=true` e um bloco `webhook` de
teste (`kw_trigger "testewebhook"` → `webhook` apontando para um echo server
local `127.0.0.1:8899`). Testado via chamadas diretas à API (`/api/playground/chat`
e `_dispatch_system_actions` invocado diretamente) — não via browser/Playground
UI visual desta vez, a pedido explícito de agilidade no teste automatizado.

### Cenário P1 — Playground: webhook dispara simulado, sem HTTP real
- [x] Configurar bloco `webhook` de teste num gatilho fácil de disparar
- [x] Testar via chat do Playground (`POST /api/playground/chat`)
- [x] Confirmar: bolha "🌐 Webhook (simulado): POST http://127.0.0.1:8899/hook — teste webhook fase1" aparece com URL/nota corretas
- [x] Confirmar: nenhuma chamada HTTP real sai (echo server permaneceu sem nenhuma requisição)
- **Validado em:** 26/08/2026

### Cenário P2 — WhatsApp real / worker dedicado: job disparado e completo
- [x] Subir os processos (core, crm, executors + novo `sales_flow_webhook_worker`) a partir desta worktree
- [x] Apontar o bloco de teste para um endpoint HTTP local controlado (echo server local, não versionado)
- [x] Confirmar: job criado (`sales_flow.webhook.dispatch`) → worker pega → POST chega no echo server (`HTTP/1.0 200 OK`) → job `completed` (`{"status": "sent", "lead_id": 1, "status_code": 200}`)
- **Validado em:** 26/08/2026 — encontrado e corrigido bug real neste passo (coluna `name` inexistente em `leads`, commit `75ecf8d`)

### Cenário P3 — Retry em falha
- [x] Apontar o bloco para porta fechada (127.0.0.1:8898, sem listener)
- [x] Confirmar: job falha, `attempts` incrementa, reagenda com backoff (tentativa 1 → 60s → tentativa 2 → 180s → tentativa 3, batendo exatamente com `JOB_BACKOFF_SECONDS={1:60, 2:180}`)
- [x] Confirmar: após esgotar `JOB_MAX_ATTEMPTS=3`, job fica `failed` com `error` detalhado
- **Validado em:** 26/08/2026 — ciclo completo observado nos logs (10:12:56 → 10:14:09 → 10:17:32, `status=failed attempts=3`)

### Cenário C1 — WhatsApp real (combinado com `espera`)
- [ ] Validar `webhook` + Cenário C1 de `feat/sales-flow-espera-pausa` juntos,
      em uma conta de teste real no WhatsApp
- **Combinado a pedido do usuário** — ver `docs/implementations/sales-flow-espera-pausa.md`

---

## Ajustes Possíveis Pós-Implementação

- Sem suporte a headers customizados/autenticação (a UI não tem esses campos
  hoje) — se necessário no futuro, exigirá novo campo no builder + no payload
  do job.
- Payload fixo (`lead_id`, `phone`, `name`, `email`, `note`, `block_id`,
  `phase_id`, `triggered_at`) — sem mapeamento de campos customizável pelo
  usuário; suficiente para o escopo atual do builder.
