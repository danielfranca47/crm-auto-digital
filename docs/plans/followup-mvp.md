# Motor de Follow-Up — Roadmap MVP

> **Status: PARCIALMENTE IMPLEMENTADO**
> Motor funcional e configurações concluídos. Etapas de UX (4–6) pendentes.
> **Pendências sujeitas a reavaliação** — decidir se ainda são necessárias antes de implementar.

## O que já existe e funciona

- Transição assistida para follow-up: `POST /api/leads/start-followup` ✅
- Persistência de `followup_contract` no lead ✅
- Worker e execução baseada em `jobs` ✅
- Retry/backoff/polling/claim em jobs ✅
- LLM Filha de follow-up no decision engine ✅
- Reconciliador periódico como asyncio loop no lifespan do backend-crm ✅
- Colunas espelho `followup_status` e `next_followup_at` na tabela `leads` ✅
- Índice sobre `(followup_status, next_followup_at, bot_disabled, user_id)` ✅
- Configurações expostas no AI Profile: `followup_max_attempts`, `followup_first_offset`, `followup_cadence` ✅
- Playbook `hybrid_scheduler` com regras próprias em `ai_playbooks/__init__.py` ✅

> **Regra:** toda etapa nova deve integrar com esses componentes, não recriá-los.

---

## Etapas concluídas

### Etapa 0 — Contrato operacional canônico ✅

Campos obrigatórios sempre presentes: `status`, `attempts`, `max_attempts`, `next_followup_at`, `last_followup_at`, `stop_reason`, `followup_variant`, `version`. Compatibilidade de leitura com contratos anteriores garantida.

---

### Etapa 1 — Base de consulta indexada para vencimentos ✅

Colunas `followup_status` e `next_followup_at` adicionadas como espelho do contrato JSON.
Índice criado para varredura periódica eficiente.

---

### Etapa 2 — Idempotência do reconciliador ✅

Reconciliador não gera jobs duplicados sob carga. Execuções concorrentes protegidas via `followup_reconcile_guard`. Cobertura de testes presente.

---

### Etapa 3 — Stop conditions e interrupção por inbound ✅

Stop conditions: `inbound_reply`, `deal_closed`, `explicit_rejection`, `handoff_human`, `max_attempts_reached`.
Após envio automático: `attempts++`, recálculo de `next_followup_at` ou encerramento. `stop_reason` auditável.

---

## Etapas pendentes (sujeitas a reavaliação)

> As etapas abaixo foram planejadas mas não implementadas. Avaliar se ainda fazem sentido no contexto atual do produto antes de prosseguir.

### Etapa 4 — Estados visíveis de UX no card do lead ❌

**Objetivo:** feedback imediato ao operador após transição.

**Estados propostos:**
- `solicitacao_recebida` — logo após fechar o modal
- `plano_em_preparacao` — durante processamento
- `followup_ativo` — quando reconciliador criou o primeiro job

**Arquivos afetados:**
- `frontend-crm/src/components/LeadCard.tsx` ou `LeadCardDialog.tsx`
- `backend-crm/routes/leads.py` — retornar estado visual no response do start-followup

---

### Etapa 5 — Visualização do plano no card do lead ❌

**Objetivo:** exibir prévia útil da cadência planejada.

**O que exibir:**
- Status do follow-up
- Próxima ação prevista
- Próxima data (`next_followup_at`)
- Tentativas (`attempts/max_attempts`)
- Resumo da cadência (calculado por regras do `followup_contract`, sem nova IA)

---

### Etapa 6 — Contrato de contexto para o modal (endpoint de leitura) ❌

**Rota proposta:** `GET /api/leads/{lead_id}/followup-transition-context`

**Propósito:** entregar ao modal um resumo calculado pelo backend (agent_type, qualificação pendente, opções padrão), evitando recálculo de regras no frontend.

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

**Regra de UX:** complemento de qualificação no modal é opcional — não obrigatório. `start-followup` permanece como dono da transição.

---

### Etapa futura — Planejador inteligente (planner) ❌

Módulo opcional e desacoplado do scheduler MVP:
- Analisa contexto ampliado do lead
- Recomenda progressão de follow-up
- Sugere materiais/argumentos
- Alimenta contexto adicional da LLM Filha

**Motor MVP deve funcionar integralmente sem o planner.**
