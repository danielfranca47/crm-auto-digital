# Lembrete de reunião gerado por IA (tom + nicho + pedido de confirmação)

**Branch:** `main`
**Status:** Em andamento

---

## Motivação

O lembrete automático de compromisso (`whatsapp.appointment.reminder`) é hoje um
template Python fixo (`backend-executors/app/runners/whatsapp.py:
_execute_appointment_reminder_pipeline`): sempre o mesmo texto, sem IA, sem ler
`tone_of_voice`/`custom_instructions`, e sem pedir confirmação ao lead — só avisa.

Num agente multi-nicho (ex.: demo de massoterapia), isso tem dois problemas:
1. Não pede confirmação de presença — só informa.
2. Mesmo trocando para IA, o vocabulário ainda sairia errado: quando a própria IA
   fecha o agendamento, o título do compromisso é hardcoded como `"Reunião
   agendada"` (`meeting_scheduler.py:574`), sem noção de nicho. Para uma
   massoterapeuta deveria ser "sessão", não "reunião".

---

## Problemas Identificados (estado anterior)

1. **Sem IA no lembrete** (`whatsapp.py:486-530`) — `reminder_text` é um f-string
   fixo, nunca chama `llm_service`.
2. **Título do compromisso genérico e fixo** (`meeting_scheduler.py:574`) —
   `"Reunião agendada"` sempre, sem ler `niche`/`offer_description` do AI Profile.
3. **`context` já tem tudo que falta e está sendo ignorado** — `ai_profile`
   completo (niche, tone_of_voice, custom_instructions, brand_name,
   offer_description) já chega em `_execute_appointment_reminder_pipeline` via
   `context.get("ai_profile")` (carregado genericamente para todo job em
   `backend-crm/routes/executor.py:439-440`), mas a função não usa nada disso.

---

## Abordagem

```
Job whatsapp.appointment.reminder dispara
  → _execute_appointment_reminder_pipeline(context já tem ai_profile completo)
       → meeting_scheduler.generate_appointment_reminder_message(ai_profile, lead, title, time_str)
            → monta prompt com tom + nicho + nome do lead (ou instrução de omitir)
            → instrui: se título for genérico, troca por termo do nicho
            → instrui: pedir confirmação de presença
            → llm_service.generate_appointment_reminder_message(prompt)  [texto puro, sem JSON]
       ├─ sucesso → usa texto gerado
       └─ falha/timeout/sem texto → cai no template fixo atual (nunca deixa de enviar)
```

Padrão reutilizado: `meeting_scheduler._generate_conflict_message` (já existe,
mesma forma — prompt com tom/brand/identity_mode, chamada a `llm_service`, nunca
propaga excepção, fallback fixo no caller). `llm_service.generate_conflict_message`
é a única das 4 funções de `llm_service.py` que não força JSON — por isso ganhou
uma irmã nova (`generate_appointment_reminder_message`) em vez de reusar o
schema `ChildResult` (pensado para routing de categoria, overkill aqui).

**Simplificação deliberada:** todo lembrete (1º mais distante, 2º mais próximo)
pede confirmação — não há lógica diferente por proximidade nesta fase, para não
precisar adicionar metadado novo ao payload do job. **Fora de escopo:** corrigir
o título na origem (`meeting_scheduler.py:574`) — maior blast radius (Kanban,
dossiê, agenda do operador), fica para uma melhoria futura separada.

---

## Plano de Implementação

### Fase 1 — IA no lembrete com fallback fixo

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/llm_service.py` | Nova função `generate_appointment_reminder_message(prompt)` — irmã de `generate_conflict_message`, texto puro sem JSON |
| `backend-executors/app/services/meeting_scheduler.py` | Nova função pública `generate_appointment_reminder_message(ai_profile, lead, *, appointment_title, time_str, logger)` — monta prompt com tom/nicho/nome, chama `llm_service`, nunca propaga excepção |
| `backend-executors/app/runners/whatsapp.py` | `_execute_appointment_reminder_pipeline` passa a chamar a função acima antes de montar o `reminder_text` fixo; usa o resultado da IA ou cai no fallback |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `4389192` | `generate_appointment_reminder_message` em `llm_service.py` e `meeting_scheduler.py`; conecta em `whatsapp.py:_execute_appointment_reminder_pipeline` com fallback para o template fixo |

---

## Checks de Validação — Fase 1

### Cenário P1 — Lembrete usa tom/nicho do AI Profile
- [ ] Configurar AI Profile de teste com `niche` específico (ex.: massoterapia) e `tone_of_voice` customizado
- [ ] Disparar um lembrete (offset próximo) e inspecionar o texto enviado
- [ ] Confirmar: não repete "reunião" genérica, usa termo do nicho; pede confirmação
- **Pendente**

### Cenário P2 — Lead sem nome não gera placeholder
- [ ] Lead de teste sem `contactName`/`name`
- [ ] Confirmar: mensagem não inventa nome nem usa "Cliente" genérico
- **Pendente**

### Cenário P3 — Fallback funciona se a IA falhar
- [ ] Simular falha (ex.: API key inválida/ausente temporariamente)
- [ ] Confirmar: lembrete ainda é enviado, com o template fixo de sempre
- **Pendente**

---

## Fase 2 — Retry com backoff específico antes do fallback fixo

### Motivação

Hoje, se a geração via IA falha (Fase 1), o sistema cai direto no template fixo
no **mesmo job/tentativa** — sem dar à IA uma segunda chance. O utilizador pediu
mais resiliência: tentar gerar via IA várias vezes, espaçadas no tempo, antes de
aceitar o template fixo como resultado final.

**Decisões confirmadas com o utilizador (AskUserQuestion):**
- Espaçamento: um único intervalo de 15 min antes da penúltima tentativa; a
  última tentativa vem logo depois (gap curto), não mais 15 min de espera.
- Esgotadas as tentativas, o template fixo **ainda é enviado** — nunca deixamos
  de mandar o lembrete, só perdemos a personalização por IA nessa mensagem.

### Problema técnico identificado durante o desenho

Um `sleep(15 min)` dentro do job travaria o worker inteiro — `whatsapp_worker.py`
roda um `while True` sequencial, sem concorrência (`app/runners/whatsapp.py`,
loop em `main()`), processando um job por vez. Qualquer mensagem ou follow-up
de **qualquer outro lead** ficaria parada atrás desse sleep. Logo, o retry
precisa de usar a fila de jobs existente (re-agendamento via `scheduled_at`),
não espera bloqueante.

A fila de jobs (`backend-crm/services/jobs_service.py` +
`backend-crm/routes/executor.py`) já tem retry com backoff — mas é **global**:
`JOB_MAX_ATTEMPTS = 3` e `JOB_BACKOFF_SECONDS = {1: 60, 2: 180}`
(`jobs_service.py:25-26`), usado por todo tipo de job. Em vez de mudar esse
comportamento para todos os jobs (mensagens, follow-ups, prospecção...), vou
adicionar um *override* por tipo de job, mantendo o default global intocado
para os demais.

`attempts` incrementa no momento do `claim` (`routes/executor.py:721`,
`attempts=attempts + 1`), então o valor de `attempt` recebido em
`_execute_appointment_reminder_pipeline` já é o número da tentativa atual
(1, 2, 3...).

### Abordagem

```
attempt 1 (imediata) → IA falha → retryable → scheduled_at = +60s   → attempt 2
attempt 2            → IA falha → retryable → scheduled_at = +180s  → attempt 3
attempt 3            → IA falha → retryable → scheduled_at = +900s  → attempt 4  (15 min)
attempt 4            → IA falha → retryable → scheduled_at = +60s   → attempt 5
attempt 5            → IA falha → ÚLTIMA tentativa → usa template fixo, ENVIA, job completa
```

Em qualquer tentativa em que a IA tiver sucesso, envia o texto gerado e o job
completa normalmente — o retry só continua enquanto a IA falhar E ainda houver
tentativas disponíveis.

### Plano de Implementação

| Arquivo | O que muda |
|---|---|
| `backend-crm/services/jobs_service.py` | Novas constantes `APPOINTMENT_REMINDER_MAX_ATTEMPTS = 5` e `APPOINTMENT_REMINDER_BACKOFF_SECONDS = {1: 60, 2: 180, 3: 900, 4: 60}`; dicts de override por tipo (`_JOB_TYPE_MAX_ATTEMPTS`, `_JOB_TYPE_BACKOFF_SECONDS`) mapeando `TYPE_WHATSAPP_APPOINTMENT_REMINDER` para os valores acima |
| `backend-crm/routes/executor.py` | `_compute_backoff_seconds(attempts, job_type=None)` passa a consultar o override antes do default global; `fail_job_internal` passa `job_type=row["type"]` e usa `_max_attempts_for(job_type)` em vez de `JOB_MAX_ATTEMPTS` fixo; `get_next_job_internal` usa `max(JOB_MAX_ATTEMPTS, *overrides aplicáveis)` no bind do filtro `attempts < ?` (filtro é defensivo/redundante — a aplicação real do limite já é feita em `fail_job_internal`; usar o máximo evita excluir tentativas 4/5 do lembrete sem afrouxar a regra real para os outros tipos) |
| `backend-executors/app/runners/whatsapp.py` | `_execute_appointment_reminder_pipeline`: se a IA falhar e `attempt` for `None` ou `>= APPOINTMENT_REMINDER_MAX_ATTEMPTS` (5) → usa o template fixo e **envia** (não chama `_fail_job`). Se a IA falhar e ainda houver tentativas → `_fail_job(..., retryable=True)`, sem enviar nada nesta execução — o job volta para a fila |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `8f5ea57` | `max_attempts_for`/`backoff_schedule_for` por tipo de job em `jobs_service.py`; aplicados em `fail_job_internal`/`get_next_job_internal`; `whatsapp.py` retry-com-fallback-na-última-tentativa |

---

## Checks de Validação — Fase 2

### Cenário R1 — Retry agenda corretamente (schedule via job real, ponta a ponta)
- [x] Script de verificação ponta a ponta contra um banco real (schema completo via `database.init_db()` em diretório temporário, mesmo padrão dos testes existentes): cria um job `whatsapp.appointment.reminder` de verdade, chama `claim_job_internal`/`fail_job_internal` (as rotas reais, não mocks) 5 vezes em sequência
- [x] Confirmado: `scheduled_at` fica a 60s/180s/900s/60s no futuro após cada uma das 4 primeiras falhas; após a 5ª, job vira `failed` definitivo (na prática nunca acontece — `whatsapp.py` intercepta antes e envia o fallback fixo)
- [x] Controle: repetido o mesmo ciclo para `whatsapp.followup.tick` (sem override) — continua exatamente 60s/180s/falha definitiva na 3ª, confirmando que outros tipos de job não foram afetados
- **Validado em:** 26/06/2026

### Cenário R2 — Última tentativa sempre envia
- [x] Smoke test direto (`whatsapp._execute_appointment_reminder_pipeline` com IA mockada para falhar) confirma: tentativas 1-4 chamam `_fail_job` (retryable, não envia nada); tentativa 5 não chama `_fail_job`, envia o template fixo. `attempt=None` também trata como última tentativa (mais seguro)
- **Validado em:** 26/06/2026

### Cenário R3 — Outros tipos de job não foram afetados
- [x] Smoke test direto: `max_attempts_for("whatsapp.appointment.reminder")` → 5 / `backoff_schedule_for(...)` → `{1:60,2:180,3:900,4:60}`; `max_attempts_for("whatsapp.followup.tick")`, tipo desconhecido e `None` → todos caem no default global (3 / `{1:60,2:180}`)
- [x] Suite `tests/` de `backend-crm` (147 testes) e `backend-executors` (31 testes relevantes) sem regressão — mesmos 18 erros pré-existentes em `backend-crm` antes e depois da mudança (confirmado via `git stash`)
- **Validado em:** 26/06/2026

---

## Fase 3 — Título do compromisso gerado por IA na origem

### Motivação

`meeting_scheduler.py:574` grava sempre `"Reunião agendada"` quando a própria
IA fecha o agendamento — sem noção de nicho. Esse título não fica só no
lembrete: é lido também pelo Dossiê pré-reunião (`briefing_service.py:92`,
`appointment.get("title") or "Reunião"`) e por vários componentes do frontend
que o operador vê (`KanbanBoard.tsx`, `LeadCardDialog.tsx`,
`ScheduleAppointmentDialog.tsx`, `ScheduleView.tsx`). Corrigir na origem
beneficia todos esses lugares de uma vez, não só o lembrete.

**Decisão confirmada com o utilizador (AskUserQuestion):** entre 3 abordagens
— (a) nova chamada de IA isolada, (b) aproveitar a IA que já responde ao lead
na fase de apresentação/agendamento (zero latência extra, mas toca um prompt
grande e crítico usado por todos os agentes), (c) mapeamento simples por
palavra-chave — o utilizador escolheu **(a)**, aceitando ~1-2s extra no
momento da confirmação do agendamento em troca de não tocar em nada existente.

### Abordagem

Mesmo padrão já usado duas vezes nesta implementação
(`_generate_conflict_message`, `generate_appointment_reminder_message`): uma
função isolada que nunca propaga excepção, com fallback fixo no caller.

```
handle_meeting_scheduled() confirma o agendamento
  → is_playground? → título fixo "[Playground] Reunião agendada" (sem IA — simulação interna)
  → senão → meeting_scheduler.generate_appointment_title(ai_profile, logger=logger)
       → monta prompt curto pedindo 2-4 palavras adequadas ao nicho
       → llm_service.generate_appointment_title_message(prompt)  [texto puro, sem JSON]
       ├─ sucesso → usa o título gerado
       └─ falha/timeout/vazio → fallback "Reunião agendada" (comportamento atual, nunca quebra o agendamento)
```

### Plano de Implementação

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/llm_service.py` | Nova função `generate_appointment_title_message(prompt)` — mesma forma de `generate_conflict_message`/`generate_appointment_reminder_message` |
| `backend-executors/app/services/meeting_scheduler.py` | Nova função `generate_appointment_title(ai_profile, *, logger=None) -> Optional[str]` — prompt usa `niche`, `offer_description`, `tone_of_voice`/`brand_name`; pede título curto (2-4 palavras); nunca propaga excepção |
| `backend-executors/app/services/meeting_scheduler.py` (linha ~574, em `handle_meeting_scheduled`) | Playground continua fixo; caso real chama `generate_appointment_title(...)` com fallback `or "Reunião agendada"` |

### Commits Fase 3

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | _(preenchido após o commit)_ | |

### Checks de Validação — Fase 3

- [ ] **T1:** Agendar compromisso de teste com `niche` específico (ex.: massoterapia) e confirmar que o título não é "Reunião agendada" genérica
- [ ] **T2:** Confirmar que Dossiê pré-reunião e Kanban exibem o novo título (herdam automaticamente, sem mudança nesses arquivos)
- [ ] **T3:** Forçar falha da IA e confirmar fallback "Reunião agendada" — agendamento nunca falha por causa disso
- [ ] **T4:** Confirmar que o Playground continua com título fixo, sem chamar IA extra

---

## Fase 4 — Diferenciar tom entre lembrete distante (early) e final

### Motivação

Hoje todo lembrete pede confirmação da mesma forma, seja o 1º (mais distante,
ex. 48h antes) seja o 2º (mais próximo, ex. 2h antes) — simplificação
deliberada da Fase 1. Um aviso mais leve no distante e um pedido de
confirmação mais direto no final é mais natural.

### Abordagem

```
schedule_appointment_reminder_jobs() cria um job por offset configurado
  → para cada offset: reminder_kind = "final" se abs(offset) == min(abs(o) para todo offset da lista)
                       senão "early"
  → inclui "reminder_kind" no payload do job

_execute_appointment_reminder_pipeline (whatsapp.py)
  → lê payload.get("reminder_kind", "final")  [default seguro]
  → passa para generate_appointment_reminder_message(..., reminder_kind=reminder_kind)
       → early: instrução de aviso mais leve, sem soar urgente
       → final: instrução de pedido de confirmação mais direto (não há mais tempo de remarcar)
```

`min(abs(o) para todo offset)` identifica o offset mais próximo do compromisso
de forma robusta, independente da ordem ou de quantos offsets existirem (hoje
são 2 — `appointment_reminder_h1`/`h2` — mas a lógica não assume exatamente 2).

### Plano de Implementação

| Arquivo | O que muda |
|---|---|
| `backend-crm/services/jobs_service.py` | `schedule_appointment_reminder_jobs`: calcula `reminder_kind` por offset e inclui no payload de cada job criado |
| `backend-executors/app/runners/whatsapp.py` | `_execute_appointment_reminder_pipeline`: lê `reminder_kind` do payload, passa para `generate_appointment_reminder_message` |
| `backend-executors/app/services/meeting_scheduler.py` | `generate_appointment_reminder_message` ganha parâmetro `reminder_kind: str = "final"`; prompt ajusta a instrução de confirmação conforme o valor |

### Commits Fase 4

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | _(preenchido após o commit)_ | |

### Checks de Validação — Fase 4

- [ ] **T5:** Configurar 2 lembretes (48h e 2h) e confirmar nos payloads dos jobs criados: `reminder_kind="early"` para o de 48h, `"final"` para o de 2h
- [ ] **T6:** Inspecionar o prompt montado (ou testar com IA real) e confirmar que "early" é mais leve/informal e "final" pede confirmação mais direta
- [ ] **T7:** Com apenas 1 offset configurado, confirmar que recebe `reminder_kind="final"` (trivialmente o mínimo de uma lista de 1)

---

## Ajustes Possíveis Pós-Implementação

Nenhum identificado além do que já está coberto pelas Fases 3 e 4 acima.
