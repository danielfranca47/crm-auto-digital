# Fix: Loop Infinito de Jobs whatsapp.followup.tick

**Branch:** `etapa-8-6-desabilitar-bot-lead`
**Status:** Em andamento

---

## Motivação

O reconciliador de follow-up criava novos jobs `whatsapp.followup.tick` a cada 60 segundos para leads cujo job anterior havia falhado com `retryable: false`. O resultado era um loop infinito que:

- Gerava ~2 jobs/minuto por lead preso (19.000+ entradas na `followup_reconcile_guard` só para os leads 52 e 27)
- Mantinha o executor ocupado processando falhas previsíveis, atrasando jobs reais (ex.: job 295, inbound de mensagem real)
- Escalaria com múltiplos usuários: N leads presos × M usuários = N×M jobs/minuto de desperdício

---

## Problemas Identificados (estado anterior)

1. **Guard deletado em qualquer falha:** `followup_reconciler.py:222-234` — quando o guard apontava para um job com `status = failed`, o guard era deletado incondicionalmente, permitindo que um novo job fosse criado. Não havia distinção entre falha retryable (transitória) e non-retryable (definitiva).

2. **Mensagem de erro mascarada:** `backend-executors/app/clients/crm_client.py:83-88` — qualquer HTTP 400 do endpoint de contexto é convertido para a string genérica `"Payload do job incompleto para montar contexto"`. O erro real (ex.: `"Conexão WhatsApp atual do usuário está inativa"`) fica escondido em `response_body`.

3. **Job 295 (inbound.n8n) preso:** criado com delay de humanização de 2 min (`scheduled_at=14:10:25`), nunca processado porque o executor estava saturado com o loop dos followup.tick.

---

## Abordagem

Circuit breaker com cooldown de 24h para falhas non-retryable:

```
Reconciliador encontra lead com next_followup_at vencido
  → Guard existe com job failed
    ├─ retryable = true → comportamento atual (delete guard, re-enqueue)
    └─ retryable = false → circuit breaker:
         delete guard
         UPDATE leads SET next_followup_at = agora + 24h
         INSERT prospection_log action='followup_circuit_breaker'
         log + skip (não cria novo job)
```

Após o circuit breaker:
- O lead sai da janela elegível por 24h
- Em 24h, se WhatsApp estiver reconectado, o job será criado normalmente
- Se ainda falhar, outro cooldown de 24h é aplicado (auto-throttle)

---

## Plano de Implementação

### Fase 1 — Circuit Breaker no Reconciliador

**Objetivo:** parar o loop de re-enqueue para jobs non-retryable

| Arquivo | O que muda |
|---|---|
| `backend-crm/services/followup_reconciler.py` | Busca `j.error` no guard query; aplica cooldown quando `retryable: false` |

**Antes (linha 211-234):**
```python
existing_guard = cur.execute(
    """
    SELECT g.id AS guard_id, g.job_id, j.status AS job_status
      FROM followup_reconcile_guard g
 LEFT JOIN jobs j ON j.id = g.job_id
     WHERE g.lead_id = ? AND g.due_at = ?
     LIMIT 1
    """,
    (lead_id, due_at),
).fetchone()

if existing_guard and str(existing_guard["job_status"] or "").lower() == "failed":
    cur.execute("DELETE FROM followup_reconcile_guard WHERE id = ?", (existing_guard["guard_id"],))
    logger.info("followup.reconcile_release_failed_guard ...")
```

**Depois:**
- Query também retorna `j.error AS job_error`
- Se `retryable: false` → aplica cooldown de 24h e `continue`
- Se `retryable: true` ou não determinado → comportamento anterior (delete + re-enqueue)

---

## Checks de Validação

### Cenário P1 — Loop para imediatamente após o fix

- [ ] Deploy do fix
- [ ] Aguardar 2 ciclos do reconciliador (≈ 2 min)
- [ ] Confirmar: nenhum novo job `whatsapp.followup.tick` criado para leads 52 e 27
- [ ] Confirmar: `prospection_logs` tem action `followup_circuit_breaker` para os dois leads
- [ ] Confirmar: `next_followup_at` dos leads 52 e 27 foi atualizado para ~24h no futuro

### Cenário P2 — Job 295 é processado após o loop parar

- [ ] Após P1 confirmado, verificar status do job 295
- [ ] Confirmar: job 295 tem `attempts >= 1` (foi pego pelo executor)

### Cenário P3 — Retry normal após 24h (simulação)

- [ ] Atualizar manualmente `next_followup_at` de um lead para `datetime.utcnow()` no banco
- [ ] Aguardar 1 ciclo do reconciliador
- [ ] Confirmar: novo job criado normalmente
- [ ] Confirmar: se job falhar com retryable=false novamente → novo cooldown de 24h aplicado

---

## Ajustes Possíveis Pós-Implementação

- **Cooldown configurável:** hoje hardcoded em 24h. Pode ser exposto como env var `FOLLOWUP_CIRCUIT_BREAKER_COOLDOWN_HOURS`.
- **UI de alerta:** o campo `prospection_logs.action = 'followup_circuit_breaker'` poderia ser exibido no card do lead como aviso de "follow-up pausado".
- **Erro real visível:** o `crm_client.py` no executors poderia incluir `response_body` no erro armazenado para facilitar debug.
