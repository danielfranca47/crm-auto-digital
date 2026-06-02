# Emails de Subscrição — Confirmações e Job de Expiração

**Branch:** `etapa-9-planos-limites`
**Status:** Em andamento

---

## Motivação

O sistema de subscriptions está funcional (etapa-9), mas nenhum evento de subscription envia email ao cliente. Um utilizador que paga via Kiwify, recebe um trial ou regista a sua própria conta nunca é notificado. Além disso, subscriptions expiradas não são canceladas automaticamente — sem um job diário, o DB acumula entradas `active` que deveriam estar `expired`.

---

## Problemas Identificados

1. **Sem email pós-pagamento Kiwify:** `_activate_subscription()` em `webhooks_kiwify.py:99` — commit sem notificação.
2. **Sem email de renovação:** `_renew_subscription()` em `webhooks_kiwify.py:126` — idem.
3. **Sem email de cancelamento:** `_cancel_subscription()` em `webhooks_kiwify.py:149` — idem.
4. **Sem email ao atribuir trial/plano:** `admin_assign_plan()` em `admin.py:348` — idem.
5. **Sem email no auto-registo:** `POST /auth/register` em `auth.py:91` — utilizador cria conta e não recebe nada.
6. **Bug menor:** sujeito do email de reset diz "AutoDigital CRM" (`auth.py:167`) em vez de "Digital Pro".
7. **Sem job de expiração:** subscriptions com `current_period_end < now` permanecem `status = "active"` indefinidamente.

---

## Abordagem

```
Fase 1 — Event-driven (sem infraestrutura nova):
  Kiwify order_approved   → _activate_subscription() → email "Plano activado"
  Kiwify sub_renewed      → _renew_subscription()    → email "Plano renovado"
  Kiwify cancelled        → _cancel_subscription()   → email "Subscrição cancelada"
  Admin atribui plano     → admin_assign_plan()       → email "Plano activado" ou "Trial iniciado"
  POST /auth/register     → register()               → email "Bem-vindo ao Digital Pro"

Fase 2 — Job agendado (APScheduler):
  Diariamente às 09:00 UTC:
    → Subscriptions expiradas (current_period_end < now, status=active) → status="expired" + email
    → Subscriptions a expirar em ≤3 dias (expiry_warning_sent=False)    → aviso + marcar sent=True
```

Emails são sempre **não-bloqueantes** (try/except) — falha de SMTP não afecta a lógica de negócio.

---

## Plano de Implementação

### Fase 1 — Templates + chamadas event-driven

**Objetivo:** todos os eventos de subscription notificam o cliente por email.

| Arquivo | O que muda |
|---|---|
| `backend-core/app/services/email_service.py` | 7 novos templates (activação, trial, renovação, cancelamento, registo, aviso expiração, expirado) |
| `backend-core/app/api/webhooks_kiwify.py` | Email após activate/renew/cancel (try/except) |
| `backend-core/app/api/admin.py` | Email após assign_plan: trial → render_trial_started, senão → render_subscription_activated |
| `backend-core/app/api/auth.py` | Email welcome no register + corrigir sujeito do reset |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `7c828d7` | Templates de email + chamadas event-driven em todos os endpoints de subscription |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `82f324e` | expiry_warning_sent no modelo, APScheduler, job diário, cron endpoint |

### Fase 2 — Job de expiração automática

**Objetivo:** subscriptions expiradas passam para `"expired"` e o cliente é avisado 3 dias antes.

| Arquivo | O que muda |
|---|---|
| `backend-core/app/models/subscription.py` | Novo campo `expiry_warning_sent` (Boolean, default False) |
| `backend-core/app/db.py` | `ensure_subscription_columns()` — adicionar `expiry_warning_sent` |
| `backend-core/requirements.txt` | Adicionar `apscheduler>=3.10` |
| `backend-core/app/jobs/__init__.py` | Novo (vazio) |
| `backend-core/app/jobs/subscription_jobs.py` | Novo — lógica do job diário |
| `backend-core/app/api/cron.py` | Novo — `POST /admin/cron/daily` para trigger manual |
| `backend-core/app/api/__init__.py` | Registar cron router |
| `backend-core/app/main.py` | Iniciar/parar BackgroundScheduler no lifespan |

---

## Checks de Validação

### E1 — Email após pagamento Kiwify
- [ ] Usar webhook test do Kiwify (order_approved com email de utilizador existente)
- [ ] Confirmar que email "Plano activado" chega com nome do plano e data de expiração

### E2 — Email ao atribuir trial pelo admin
- [ ] Admin abre painel → "Plano" → selecciona plan + marca trial → confirma
- [ ] Utilizador recebe email "Trial iniciado — tens X dias para experimentar"

### E3 — Email ao auto-registar
- [ ] Criar conta em `/register`
- [ ] Confirmar que email "Bem-vindo ao Digital Pro" chega (diferente do welcome com senha temporária)

### E4 — Job de expiração (trigger manual)
- [ ] Criar subscription com `current_period_end = now - 1 hora` no DB
- [ ] Chamar `POST /admin/cron/daily` (admin token)
- [ ] Confirmar que subscription passa para `"expired"` e email é enviado

### E5 — Aviso antecipado (3 dias antes)
- [ ] Criar subscription com `current_period_end = now + 2 dias`
- [ ] Executar job via `POST /admin/cron/daily`
- [ ] Confirmar email de aviso chega e `expiry_warning_sent = True` no DB
- [ ] Executar job novamente — confirmar que email NÃO é re-enviado

---

## Ajustes Possíveis Pós-Implementação

- Emails de confirmação de mudança de senha (change-password) ficaram fora de escopo — micro-melhoria futura.
- O job corre a 09:00 UTC; ajustar fuso se necessário via cron trigger.
- O status `"expired"` é novo — se houver queries que usam `status != "active"` ou `status == "cancelled"` é preciso rever.
