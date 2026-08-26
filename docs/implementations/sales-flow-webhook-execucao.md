# Executar em runtime o bloco `webhook` do Fluxo de Venda

**Branch:** `feat/sales-flow-webhook-execucao`
**Status:** Em andamento

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

---

## Checks de Validação

### Cenário P1 — Playground: webhook dispara simulado, sem HTTP real
- [ ] Configurar bloco `webhook` de teste num gatilho fácil de disparar
- [ ] Testar via chat do Playground
- [ ] Confirmar: bolha "🌐 Webhook (simulado): ..." aparece com URL/nota corretas
- [ ] Confirmar: nenhuma chamada HTTP real sai (não precisa de rede para passar)

### Cenário P2 — WhatsApp real / worker dedicado: job disparado e completo
- [ ] Subir os 4 processos (core, crm, executors com o novo
      `sales_flow_webhook_worker`, frontend) a partir desta worktree
- [ ] Apontar o bloco de teste para um endpoint HTTP local controlado (echo
      server local, não versionado)
- [ ] Confirmar: job criado (`sales_flow.webhook.dispatch`) → worker pega →
      POST chega no echo server com o payload esperado → job `completed`

### Cenário P3 — Retry em falha
- [ ] Apontar o bloco para porta fechada/URL inválida
- [ ] Confirmar: job falha, `attempts` incrementa, reagenda com backoff
- [ ] Confirmar: após esgotar `JOB_MAX_ATTEMPTS=3`, job fica `failed`

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
