# Motor de Follow-Up — Roadmap MVP

## Estado atual (o que já existe)

- Transição assistida para follow-up: `POST /api/leads/start-followup` ✅
- Persistência de `followup_contract` no lead ✅
- Worker e execução baseada em `jobs` ✅
- Retry/backoff/polling/claim em jobs ✅
- LLM Filha de follow-up no decision engine ✅
- Reconciliador periódico como asyncio loop no lifespan do backend-crm ✅

> **Regra:** toda etapa nova deve integrar com esses componentes, não recriá-los.

---

## Etapas pendentes de implementação

### Etapa 0 — Contrato operacional canônico

**Objetivo:** padronizar o `followup_contract` para suportar scheduler, rastreabilidade e exibição no card.

**O que fazer:**
- Garantir que todos os campos obrigatórios estejam sempre presentes: `status`, `attempts`, `max_attempts`, `next_followup_at`, `last_followup_at`, `stop_reason`, `followup_variant`, `version`
- Compatibilidade de leitura com contratos anteriores

**Critério de aceite:** todo lead iniciado em follow-up sai do endpoint com contrato completo.

---

### Etapa 1 — Base de consulta indexada para vencimentos

**Objetivo:** consulta eficiente e segura de follow-ups vencidos.

**O que fazer:**
- Adicionar colunas operacionais no `lead` como espelho do contrato: `followup_status`, `next_followup_at`
- Criar índice para varredura periódica (`followup_status`, `next_followup_at`, `bot_disabled`, `user_id`)
- Sincronizar escrita entre `followup_contract` (JSON) e colunas espelho

**Critério de aceite:** query de vencidos retorna somente `status=active` e `next_followup_at <= now`, sem parsing pesado de JSON.

---

### Etapa 2 — Validar idempotência do reconciliador

**Objetivo:** confirmar que o reconciliador (já em execução) não gera jobs duplicados sob carga.

**O que validar:**
- Sem geração duplicada de job para o mesmo lead/vencimento
- Execuções concorrentes permanecem idempotentes (via `followup_reconcile_guard`)
- Logs operacionais registram detecção e enqueue

---

### Etapa 3 — Stop conditions e interrupção por inbound

**Objetivo:** impedir conflitos de automação durante conversa ativa.

**O que fazer:**
- Garantir fonte única de stop conditions: `inbound_reply`, `deal_closed`, `explicit_rejection`, `handoff_human`, `max_attempts_reached`
- Após envio automático: `attempts++`, recalcular `next_followup_at` ou encerrar
- `stop_reason` e `status` auditáveis

**Critério de aceite:** nenhuma mensagem automática é enviada para lead já interrompido/encerrado.

---

### Etapa 4 — Estados visíveis de UX no card do lead

**Objetivo:** feedback imediato ao operador após transição.

**Estados propostos:**
- `solicitacao_recebida` — logo após fechar o modal
- `plano_em_preparacao` — durante processamento
- `followup_ativo` — quando reconciliador criou o primeiro job

**Arquivos afetados:**
- `frontend-crm/src/components/LeadCard.tsx` ou `LeadCardDialog.tsx`
- `backend-crm/routes/leads.py` — retornar estado visual no response do start-followup

---

### Etapa 5 — Visualização do plano no card do lead

**Objetivo:** exibir prévia útil da cadência planejada.

**O que exibir:**
- Status do follow-up
- Próxima ação prevista
- Próxima data (`next_followup_at`)
- Tentativas (`attempts/max_attempts`)
- Resumo da cadência (calculado por regras do `followup_contract`, sem nova IA)

---

### Etapa 6 — Contrato de contexto para o modal (endpoint de leitura)

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

### Etapa futura — Planejador inteligente (planner)

Módulo opcional e desacoplado do scheduler MVP:
- Analisa contexto ampliado do lead
- Recomenda progressão de follow-up
- Sugere materiais/argumentos
- Alimenta contexto adicional da LLM Filha

**Motor MVP deve funcionar integralmente sem o planner.**

---

## Configurações a expor (atualmente hardcoded)

| Configuração | Localização atual | Campo proposto no AI Profile |
|---|---|---|
| Primeiro offset de follow-up (30min / 2h) | `backend-crm/routes/leads.py` | `followup_first_offset_minutes` |
| Max attempts (4 / 3) | `backend-crm/routes/leads.py` | `followup_max_attempts` |
| Intervalos entre tentativas | `backend-crm/services/followup_state.py` | `followup_intervals_hours` |

---

## Playbook específico para Agent 3 (hybrid_scheduler)

**Problema atual:** `template_key = hybrid_scheduler` cai no fallback `sdr_padrao` em `backend-crm/services/ai_playbooks/__init__.py`.

**O que criar:** playbook `hybrid_scheduler` com regras de agendamento, remarcação e sessões específicas do Agent 3.
