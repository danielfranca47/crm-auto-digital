# Motor de Follow-Up — Roadmap MVP

> **Status: SUBSTANCIALMENTE IMPLEMENTADO**
> Motor funcional, circuit breaker, controle manual (pause/resume/cancel), cart recovery e Central de Follow-up concluídos.
> Etapa 6 (endpoint de contexto para modal) pendente e sujeita a reavaliação.
> Etapas 4 e 5 foram resolvidas por caminho diferente do planeado — ver notas abaixo.

---

## O que já existe e funciona

### Motor e infraestrutura

- Transição assistida para follow-up: `POST /api/leads/start-followup` ✅
- Persistência de `followup_contract` no lead ✅
- Worker e execução baseada em `jobs` ✅
- Retry/backoff/polling/claim em jobs ✅
- LLM Filha de follow-up no decision engine ✅
- Reconciliador periódico como asyncio loop no lifespan do backend-crm ✅
- Colunas espelho `followup_status` e `next_followup_at` na tabela `leads` ✅
- Índice sobre `(followup_status, next_followup_at, bot_disabled, user_id)` ✅
- Configurações no AI Profile: `followup_max_attempts`, `followup_first_offset`, `followup_cadence` ✅
- Playbook `hybrid_scheduler` com regras próprias em `ai_playbooks/__init__.py` ✅

### Controlo manual

- **Pause manual:** `POST /api/leads/{id}/followup/pause` → status `manually_paused`, cancela jobs pendentes via `_cancel_pending_jobs_for_lead()` ✅
- **Resume manual:** `POST /api/leads/{id}/followup/resume` → recalcula `next_followup_at = now + cadence[attempts]` a partir da posição atual ✅
- **Cancel manual:** `POST /api/leads/{id}/followup/cancel` → status `closed`, stop_reason `manual_cancel`, cancela jobs pendentes ✅

### Circuit breaker (correção de loop de jobs)

Implementado em `followup_reconciler.py` para resolver o problema de saturação de jobs quando o `backend-executors` ficava parado e reiniciava com backlog acumulado.

**Comportamento:**
- Job com `retryable=False` no campo `error.details.retryable`: aplica cooldown de 24h — atualiza `next_followup_at = now + 24h`, limpa o guard e regista `followup_circuit_breaker` nos logs
- Job com `retryable=True` (ou sem campo): liberta o guard e re-enfileira normalmente no próximo ciclo do reconciliador

### Cart recovery automático (Agent 2)

`start_cart_recovery_followup()` em `followup_state.py` — iniciado automaticamente quando o bot envia link de pagamento.

- Variante: `cart_recovery`
- Cadência: 2h (1ª tentativa), 24h (2ª), 48h (3ª)
- Max attempts: 3
- Não inicia se já existe contrato ativo

### Job type de pré-geração

`whatsapp.followup.pregenerate` (TYPE_WHATSAPP_FOLLOWUP_PREGENERATE) — criado após cada tick enviado e no `start-followup`. Pré-aquece a próxima mensagem para que o tick seguinte execute mais rapidamente.

---

## Etapas concluídas do roadmap original

### Etapa 0 — Contrato operacional canônico ✅

Campos sempre presentes: `status`, `attempts`, `max_attempts`, `next_followup_at`, `last_followup_at`, `stop_reason`, `followup_variant`, `version`.

---

### Etapa 1 — Base de consulta indexada ✅

Colunas `followup_status` e `next_followup_at` espelham o contrato JSON. Índice sobre as quatro colunas de varredura.

---

### Etapa 2 — Idempotência do reconciliador ✅

`followup_reconcile_guard` garante que o mesmo (lead_id, due_at) nunca gera dois jobs. Circuit breaker adicionado como extensão desta etapa.

---

### Etapa 3 — Stop conditions ✅

Stop reasons canônicos implementados:
| Constante | Quando ocorre |
|---|---|
| `inbound_reply` | Lead respondeu — bot para automaticamente |
| `deal_closed` | Lead movido para `client-list` |
| `explicit_rejection` | Lead movido para `prospect-refused` ou `disqualified` |
| `handoff_human` | Handoff ativado ou `bot_disabled=1` durante tick |
| `max_attempts_reached` | Número máximo de tentativas atingido |
| `manual_cancel` | Operador cancelou manualmente via UI |

---

### Etapas 4 e 5 — UX de feedback e visualização do plano

> **Não implementadas no card do Kanban como planeado. Resolvidas por caminho diferente.**

O plano previa estados visuais no `LeadCard` e um bloco de visualização de cadência no card.  
O que foi construído em alternativa:

**`FollowUpCenter.tsx` — página dedicada** ✅
- Lista todos os leads em follow-up não encerrado
- Stats bar em tempo real: ativos, quentes ativos, envio em < 2h, pausados hoje
- Temperatura por lead: `hot`, `warm`, `cold`, `cart_recovery`, `lost`
- AttemptDots: visualização `attempts/max` com pontos coloridos
- Notificação proeminente para leads com `status=paused` (responderam — ação necessária)
- Ações por lead: pausar / retomar / cancelar
- Filtragem e pesquisa

**`FollowUpEdit.tsx` — página de detalhe por lead** ✅
- Countdown ao vivo até ao próximo envio (actualizado ao segundo)
- Mapa visual da sequência: tentativas concluídas / atual / futuras com labels descritivos
- Variante da cadência visível
- Upload de mídia

**API de suporte:**
- `GET /api/leads/followups/active` — lista paginada para a Central
- `GET /api/leads/followups/stats` — métricas do stats bar

---

## Etapa pendente (sujeita a reavaliação)

### Etapa 6 — Endpoint de contexto para o modal ❌

**Rota proposta:** `GET /api/leads/{lead_id}/followup-transition-context`

**Propósito:** entregar ao modal de transição um resumo calculado pelo backend (tipo de agente, qualificação pendente, opções padrão), evitando que o frontend recalcule lógica de negócio.

**Resposta proposta:**
```json
{
  "lead_id": 123,
  "from_category": "apresentation",
  "to_category": "follow-up",
  "agent_type": "agent_1",
  "followup_defaults": {
    "meeting_or_session_happened_options": ["yes", "no_show", "canceled", "needs_reschedule"],
    "followup_goal_options": ["confirm_interest", "reschedule_meeting", "recover_negotiation"]
  },
  "qualification_pending": {
    "has_pending": true,
    "pending_fields": ["location_preference", "budget_or_price_acceptance"],
    "severity": "low"
  }
}
```

**Regra de UX:** complemento de qualificação no modal é opcional. `start-followup` permanece como dono da transição.

---

## Estados do followup_contract

| Status | Descrição |
|---|---|
| `active` | A correr — reconciliador processa quando `next_followup_at <= now` |
| `scheduled` | Agendado (alias de active em alguns contextos) |
| `paused` | Auto-pausado por resposta inbound do lead |
| `manually_paused` | Pausado manualmente pelo operador; pode ser retomado |
| `closed` | Encerrado (max_attempts, deal_closed, rejection ou manual_cancel) |

---

## Arquivos críticos

| Arquivo | Responsabilidade |
|---|---|
| `backend-crm/services/followup_state.py` | Máquina de estado: start, stop, pause, resume, cancel, progress, cart_recovery |
| `backend-crm/services/followup_reconciler.py` | Varredura de vencidos, guard de idempotência, circuit breaker, janela de horário |
| `backend-crm/routes/leads.py` | Endpoints: `start-followup`, `pause`, `resume`, `cancel`, `followups/active`, `followups/stats` |
| `frontend-crm/src/pages/FollowUpCenter.tsx` | Central de Follow-up: lista, stats, ações, notificações |
| `frontend-crm/src/pages/FollowUpEdit.tsx` | Detalhe por lead: countdown, mapa de sequência, mídia |
| `frontend-crm/src/components/FollowUpTransitionModal.tsx` | Modal de transição `apresentation → follow-up` |
