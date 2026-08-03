# Fix: instrução "confirm_exact" falha quando a agenda está vazia

**Branch:** `main`
**Status:** Em andamento

---

## Motivação

O usuário testou no Playground (produção) um agente com `scheduling_offer_style: "confirm_exact"`
esperando que o bot confirmasse direto horários livres (16h/17h) em vez de sempre oferecer
alternativas. O bot recusou os dois horários como "já ocupados" e ofereceu sempre as mesmas
duas alternativas (15h/18h).

Hipótese inicial (compromisso residual de teste anterior no Playground bloqueando a agenda)
foi descartada — o print da Agenda real do usuário mostra "Nenhum evento agendado" para o dia
em questão. A causa raiz está no código de montagem do prompt, não em dado sujo.

---

## Problemas Identificados (estado anterior)

1. **Bloco "HORÁRIOS JÁ OCUPADOS" desaparece quando a agenda está vazia**
   (`backend-executors/app/services/decision_engine.py:3486-3490`) — `_format_busy_slots_block()`
   retorna `""` quando `busy_slots` está vazio, e o ternário que monta `_busy_block` usa essa
   string vazia para omitir a seção inteira do prompt (cabeçalho incluído).

2. **Instrução `confirm_exact` fica sem âncora** (`decision_engine.py:3496-3512`) — a regra diz
   ao modelo para "verificar o horário pedido contra HORÁRIOS JÁ OCUPADOS **acima**", mas quando
   a agenda está livre essa seção não existe no prompt. Sem uma afirmação positiva de "está tudo
   livre", o modelo tende a recusar horários "redondos" (16h, 17h) por cautela — o oposto do que
   a regra pede.

Confirmado que não há bug em: persistência de `scheduling_offer_style` (valor `"confirm_exact"`
presente e correto no export do AI Profile), nem na query `_load_calendar_busy_slots`
(`backend-crm/services/ai_orchestrator/orchestrator.py:600-627`).

---

## Abordagem

```
Prompt de agendamento (confirm_exact) → monta _busy_block
  ├─ há compromissos → lista "HORÁRIOS JÁ OCUPADOS: ..." (comportamento já correto)
  └─ agenda vazia → ANTES: bloco some do prompt
                     DEPOIS: bloco explícito "HORÁRIOS JÁ OCUPADOS: nenhum compromisso
                     encontrado — a agenda está livre no período consultado."
```

---

## Plano de Implementação

### Fase 1 — Declarar agenda vazia explicitamente no prompt

**Objetivo:** dar ao modelo uma afirmação positiva de agenda livre, em vez de silêncio, quando
não há nenhum compromisso.

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/decision_engine.py` | `_busy_block`: fallback explícito em vez de string vazia quando `_busy_lines` está vazio |
| `backend-executors/tests/test_scheduling_offer_style.py` | Novo teste: `confirm_exact` + calendário vazio → prompt contém a frase de agenda livre |

```python
# ANTES
_busy_block = (
    f"HORÁRIOS JÁ OCUPADOS (compromissos reais já marcados — NÃO proponha nem confirme "
    f"horário que sobreponha estes intervalos):\n{_busy_lines}\n\n"
    if _busy_lines else ""
)

# DEPOIS
_busy_block = (
    f"HORÁRIOS JÁ OCUPADOS (compromissos reais já marcados — NÃO proponha nem confirme "
    f"horário que sobreponha estes intervalos):\n{_busy_lines}\n\n"
    if _busy_lines
    else "HORÁRIOS JÁ OCUPADOS: nenhum compromisso encontrado — a agenda está livre no "
    "período consultado.\n\n"
)
```

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `1db9383` | fix: declarar agenda vazia explicitamente no prompt de confirm_exact |

**Detalhes do commit `1db9383`:**
- `backend-executors/app/services/decision_engine.py` — `_busy_block` passa a declarar
  explicitamente "nenhum compromisso encontrado — a agenda está livre no período consultado"
  em vez de virar string vazia quando não há compromissos
- `backend-executors/tests/test_scheduling_offer_style.py` — novo teste
  `test_confirm_exact_with_empty_calendar_states_agenda_is_free`
- `backend-executors/tests/test_agendamento_busy_slots_prompt.py` — os dois testes que
  verificavam a omissão do bloco (`test_agendamento_prompt_omits_busy_block_when_empty` e
  `..._when_absent`) foram atualizados para `test_agendamento_prompt_states_agenda_free_when_*`,
  já que a omissão era exatamente a causa raiz do bug

---

### Relatório da Fase 1 — o que mudou na prática

**Antes:** quando a agenda do profissional estava totalmente livre (nenhum compromisso
marcado), o prompt enviado ao modelo simplesmente não mencionava nada sobre disponibilidade
de horário — a seção "HORÁRIOS JÁ OCUPADOS" sumia por completo. Sem essa afirmação positiva,
o bot tendia a recusar horários "redondos" (16h, 17h) por cautela, mesmo com
`scheduling_offer_style: confirm_exact` configurado para confirmar direto quando disponível.

**Agora:** quando a agenda está vazia, o prompt inclui a frase explícita "nenhum compromisso
encontrado — a agenda está livre no período consultado", dando ao bot uma base clara para
confirmar o horário pedido diretamente, sem inventar conflitos.

**Para validar:** Cenário P1 (Playground) e Cenário C1 (pytest), abaixo.

---

## Checks de Validação

### Cenário P1 — Playground, confirm_exact, agenda vazia
- [ ] No Playground, usar um AI Profile com `scheduling_offer_style: confirm_exact` e um lead
  sandbox sem nenhum appointment.
- [ ] Pedir um horário dentro da disponibilidade (ex.: "consigo às 15h?").
- [ ] Confirmar: o bot confirma diretamente, sem oferecer alternativas nem dizer que está ocupado.

### Cenário C1 — Teste automatizado (pytest)
- [x] `pytest backend-executors/tests/test_scheduling_offer_style.py` passa, incluindo o novo caso.
- **Validado em:** 03/08/2026 — 4 testes passaram (`test_scheduling_offer_style.py`), mais os
  2 testes atualizados em `test_agendamento_busy_slots_prompt.py`. Confirmado também que as
  2 falhas pré-existentes em `test_guardrails_by_mode.py` e `test_qualification_contract.py`
  já existiam no `main` antes desta mudança (não relacionadas a este fix).

### Cenário C2 — Testes automatizados da Fase 2 (pytest)
- [x] `backend-crm`: `test_internal_appointments_routes.py` (9 testes) + suíte de appointments
  existente (`test_appointments_route_auth.py`, `test_update_appointment_route.py`,
  `test_appointments_conflict_by_professional.py`) — 29 testes, todos passando.
- [x] `backend-executors`: `test_crm_client_appointment_urls.py` (3 testes) — todos passando.
- **Validado em:** 03/08/2026 — confirmado também via `git stash` que as falhas pré-existentes
  ao rodar a suíte completa (18 em backend-crm, 21 em backend-executors) já existiam no `main`
  antes da Fase 2, em áreas não relacionadas (qualificação, follow-up, webhook de grupo).

### Cenário P2 — Cancelamento/reagendamento real (Playground)
- [ ] Após confirmar um horário (P1), pedir para reagendar ou cancelar.
- [ ] Confirmar: sem erro 500; appointment atualizado/cancelado reflete na Agenda.

---

## Fase 2 — Diagnóstico + Correção: 401/500 ao confirmar/cancelar/reagendar (03/08/2026)

### Problema identificado

Ao validar o Cenário P1 no Playground local, o fix da Fase 1 funcionou — o modelo decidiu
confirmar o horário diretamente. Mas a criação real do appointment quebrou com 500. O log
mostrou a causa exata:

```
POST http://localhost:8000/api/appointments "HTTP/1.1 401 Unauthorized"
app.clients.crm_client.CRMClientError: CRM service token inválido ou sem permissão
```

Causa raiz (via `git log`): o commit `6aebb6f` ("fix: exigir autenticação e escopo por tenant
em `/api/appointments`", 15/07/2026) — correção de segurança legítima — travou 6 rotas de
`backend-crm/routes/appointments.py` atrás de `require_crm_access` (exige JWT real de
usuário). Só que `backend-executors/app/clients/crm_client.py` chama 3 dessas rotas
(`create_lead_appointment`, `cancel_appointment`, `reschedule_appointment` — usadas por
`services/meeting_scheduler.py`, tanto no Playground quanto no WhatsApp real via
`app/runners/whatsapp.py:793-796`, sem try/except) enviando só `X-Service-Token`, nunca um
JWT. Desde 15/07/2026, toda confirmação/cancelamento/reagendamento de reunião pelo bot falha
ao tentar gravar o appointment de verdade no CRM.

### Correção

Rotas internas novas (mesmo padrão de `_require_service_token` já usado em
`/internal/logs/meeting-scheduled`), com a lógica de criação/atualização extraída das rotas
públicas para ser reutilizada sem duplicação:

| Arquivo | Mudança |
|---|---|
| `backend-crm/routes/appointments.py` | Extrai `_create_appointment_row` e `_update_appointment_row` (lógica sem checagem de JWT); rotas públicas viram wrappers finos que resolvem o dono e delegam |
| `backend-crm/routes/executor.py` | 3 novas rotas: `POST /api/internal/appointments`, `PUT /api/internal/appointments/{id}`, `POST /api/internal/appointments/{id}/cancel` — todas `Depends(_require_service_token)` |
| `backend-executors/app/clients/crm_client.py` | `create_lead_appointment`, `cancel_appointment`, `reschedule_appointment` apontam para `/api/internal/appointments...` em vez de `/api/appointments...` |
| `backend-crm/tests/test_internal_appointments_routes.py` (novo) | 9 testes: sucesso e 404 das 3 rotas internas + `_require_service_token` |
| `backend-executors/tests/test_crm_client_appointment_urls.py` (novo) | 3 testes travando a URL usada por cada função do client |

As rotas públicas `/api/appointments` mantêm exatamente o mesmo comportamento e autenticação
para usuários reais — só a lógica interna foi extraída para reuso, não alterada.

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | _(preenchido após o commit)_ | fix: rotear criação/cancelamento/reagendamento de appointment do executor por rota interna com service token |

### Relatório da Fase 2 — o que mudou na prática

**Antes:** sempre que o bot confirmava, cancelava ou reagendava uma reunião — no Playground ou
no WhatsApp real — a criação/alteração do compromisso no CRM falhava com erro (401 → 500),
mesmo que a IA tivesse decidido corretamente confirmar o horário. Isso valia desde 15/07/2026
(commit de segurança que travou as rotas públicas sem prever chamadas internas do executor).

**Agora:** o backend-executors usa rotas internas dedicadas (protegidas por token de serviço,
não por JWT de usuário) para criar/cancelar/reagendar appointments, replicando o mesmo modelo
de confiança já usado em outras rotas internas do sistema. As rotas públicas usadas pelo
frontend continuam exigindo login normal — nada muda para o usuário na Agenda.

**Para validar:** Cenário C1 (pytest, já validado), e os Cenários P1/P2 (Playground local),
abaixo.

---

## Ajustes Possíveis Pós-Implementação

- Foi observada uma anomalia no trace do teste original (`mother_route=qualification,
  effective=apresentation` para uma pergunta de agendamento no segundo turno). Não foi
  investigada nesta fase por estar fora do escopo pedido pelo usuário — candidato a
  follow-up futuro caso volte a se manifestar.
