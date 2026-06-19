# IA consulta disponibilidade real de agenda antes de propor/confirmar horário

**Branch:** `main`
**Status:** Em andamento

---

## Motivação

No Playground, ao testar um agente `hybrid_scheduler`, a IA respondeu "Infelizmente,
não temos disponibilidade amanhã às 10h... posso te oferecer 9h ou 11h" — uma frase
inteiramente inventada: a Filha de agendamento (`_build_child_prompt_agendamento`)
só recebe o campo de texto livre `ai_profile.availability_schedule` como dica geral,
sem nenhum dado real de quais horários já estão ocupados.

Investigação revelou uma segunda falha, mais grave: depois que a IA "confirma" um
horário (`meeting_scheduled=true`), `meeting_scheduler.py::handle_meeting_scheduled()`
cria o appointment direto, sem checar conflito com outros leads do mesmo
profissional. A única checagem que já existia (`has_future_meeting`, via
`client.list_appointments(lead_id=...)`) está **quebrada em produção**: o endpoint
`GET /api/appointments` exige JWT de usuário (`require_crm_access`), mas
`crm_client.py` só envia `X-Service-Token` — a chamada recebe 401, é engolida por
um `except Exception: appointments = []`, e o sistema sempre assume "sem conflito".

---

## Problemas Identificados (estado anterior)

1. **IA inventa disponibilidade:** `_build_child_prompt_agendamento` (decision_engine.py)
   não recebe nenhum dado real de agenda — só `availability_schedule` (texto livre).
2. **Checagem de duplicado quebrada:** `meeting_scheduler.py:384-391` chama
   `client.list_appointments(lead_id=...)` contra um endpoint que exige JWT de
   usuário; `crm_client.py` só autentica via `X-Service-Token` → 401 → engolido
   por `except Exception: appointments = []` → falso negativo sempre.
3. **Sem checagem de conflito real:** nenhuma verificação existe hoje (nem
   quebrada) contra **outros leads** do mesmo profissional no horário proposto.
4. **`_check_conflict` em `appointments.py` é escopado por `lead_id`, não por
   profissional:** mesmo a criação manual via UI permite dois leads marcados na
   mesma hora sem aviso.

---

## Abordagem

```
backend-crm (orchestrator.py) — Fase 1
  enrich_context_bundle() carrega calendar_busy_slots (appointments reais do
  profissional, próximos 30 dias) quando agent_mode == "agenda"
        ↓ (mesmo ContextBundle, paridade automática Playground + WhatsApp real)
backend-executors (decision_engine.py) — Fase 2
  _build_child_prompt_agendamento injeta os horários ocupados no prompt da Filha
        ↓ (só no caminho real, via runners/whatsapp.py)
backend-executors (meeting_scheduler.py + whatsapp.py) — Fase 3
  handle_meeting_scheduled() checa conflito contra calendar_busy_slots antes de
  criar o appointment; se colidir, não cria e devolve mensagem de correção,
  enviada via core_client.send_whatsapp_message()
        ↓
backend-crm (appointments.py) — Fase 3.5
  _check_conflict() passa a bloquear por profissional inteiro (não só lead) —
  defesa real contra race condition + corrige bug também na criação manual via UI
```

**Confirmado:** o Playground nunca chama `handle_meeting_scheduled` (`playground_internal.py`
só chama `decision_engine.decide()`) — desenho correto (sandbox não cria
appointments reais), não uma quebra de paridade a corrigir.

---

## Plano de Implementação

### Fase 1 — `calendar_busy_slots` no ContextBundle

| Arquivo | O que muda |
|---|---|
| `backend-crm/services/ai_orchestrator/orchestrator.py` | Novo campo `calendar_busy_slots` em `ContextBundle`; nova `_load_calendar_busy_slots()`; populado em `enrich_context_bundle()` quando `agent_mode == "agenda"` |

### Fase 2 — Injetar horários ocupados no prompt da Filha

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/decision_engine.py` | `_build_child_prompt_agendamento()` injeta bloco "HORÁRIOS JÁ OCUPADOS" antes de `_avail_block` |

### Fase 3 — Conflito bloqueia criação + correção automática

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/meeting_scheduler.py` | Nova `_has_conflict()`; checagem de duplicado por lead migrada para `calendar_busy_slots` local (corrige bug do 401); nova checagem de conflito por profissional antes de criar; retorna mensagem de correção em vez de `None` quando bloqueia |
| `backend-executors/app/runners/whatsapp.py` | Envia a mensagem de correção (se houver) via `core_client.send_whatsapp_message()` |

### Fase 3.5 — Corrigir `_check_conflict` para escopo por profissional

| Arquivo | O que muda |
|---|---|
| `backend-crm/routes/appointments.py` | `_check_conflict()` passa a considerar todos os appointments do `user_id`, não só do mesmo `lead_id` |

### Fase 4 — Documentação

| Arquivo | O que muda |
|---|---|
| `docs/architecture/agenda.md` | Documentar `_check_conflict` por profissional + mecanismo `calendar_busy_slots` |

### Commits

| # | Fase | Commit | O que foi implementado |
|---|---|---|---|
| 1 | 1 | `0eb1682` | feat: calendar_busy_slots no ContextBundle |
| 2 | 2 | `8ccae5b` | feat: injetar horários ocupados no prompt de agendamento |
| 3 | 3 | `8cedbe5` | feat: bloquear conflito + mensagem de correção automática |
| 4 | 3.5 | _(pendente)_ | fix: _check_conflict por profissional, não só por lead |
| 5 | 4 | _(pendente)_ | docs: atualizar agenda.md |

---

## Checks de Validação

### Cenário P1 — IA não inventa disponibilidade (Playground)
- [ ] Agente `hybrid_scheduler` com um appointment já existente no horário X
- [ ] Lead pede esse mesmo horário X → IA recusa com base em dados reais (não inventa)

### Cenário C1 — Conflito real bloqueia criação + correção (WhatsApp real)
- [ ] Dois leads pedem o mesmo horário em sequência
- [ ] Segundo lead recebe mensagem de correção automática; appointment não é duplicado

### Cenário C2 — Bloqueio manual na UI
- [ ] Tentar criar dois appointments do mesmo profissional, mesmo horário, leads diferentes → 409

### Cenário C3 — Suite de testes sem regressão
- [ ] `pytest backend-executors/tests` — sem novas falhas além das pré-existentes
- [ ] Testes de `backend-crm/scripts/` relacionados a appointments sem regressão

---

## Ajustes Possíveis Pós-Implementação

- Mensagem de correção é texto fixo (MVP); poderia ser gerada pela LLM no tom do
  agente numa fase futura.
- Suporte a múltiplos profissionais por conta (Scale/Enterprise) exigirá revisar
  `_check_conflict` e `calendar_busy_slots` para incluir `professional_id`.
