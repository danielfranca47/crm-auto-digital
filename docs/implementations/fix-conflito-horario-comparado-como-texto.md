# Sessões seguidas recusadas: horários comparados como texto (e o 409 que derruba o envio)

**Branch:** `worktree-fix+conflito-horario-comparado-como-texto` (pedida como `fix/conflito-horario-comparado-como-texto`)
**Status:** Em andamento
**Autonomia:** manual
**Origem:** bateria PROD07 do agente Sensi Vitae (26/10/2026), cenário `p-val-17h` — investigação em
`.claude/agentes/sensi-vitae/README.md`, secção "PROD07" (bug A).
**Plano de execução:** [`docs/plans/plano-sprint-2026-10-26-agenda-sensi-vitae.md`](../plans/plano-sprint-2026-10-26-agenda-sensi-vitae.md) — P1

---

## Motivação

Uma sessão que começa exatamente quando outra acaba é recusada como "conflito". Em PROD07
(`p-val-17h`) o cliente aceitou quinta às 16h com a Val, havia um evento do Google quinta 15h–16h,
e o Playground rebentou com erro 502 — o cliente ficou sem resposta. No WhatsApp real o mesmo
caso derruba o processo que envia as mensagens (ver problema 3). Para uma conta com sessões
seguidas (Val/Daniel) isto bloqueia a agenda.

## Causa confirmada (investigação de 26/10/2026, só leitura de código e produção)

1. **Comparação de datas como texto na rota que grava.**
   `backend-crm/routes/appointments.py::_check_conflict` (linhas 63–92) faz
   `a.start_at < ? AND a.end_at > ?` com texto. Em produção (`/data/crm.db`, 26/10) a tabela
   `appointments` tem **três formatos**:

   | Origem | `start_at`/`end_at` gravado | Linhas |
   |---|---|---|
   | CRM e Playground (`_create_appointment_row`, `payload.start_at.isoformat()`) | `…T16:00:00+00:00` | 6 |
   | Google, evento com hora (`google_calendar_sync.py:43`, grava o `dateTime` cru) | `…T16:00:00Z` | 1 |
   | Google, dia inteiro (grava o `date` cru) | `2026-10-30` (só data) | 1 |

   `"…16:00:00Z" > "…16:00:00+00:00"` é verdadeiro (`Z` > `+` na tabela de caracteres) → a sessão
   das 16h "colide" com o evento que acaba às 16h → HTTP 409.
   O executor (`backend-executors/app/services/meeting_scheduler.py::_has_conflict`, linha 425)
   compara como datas e **não** vê conflito, por isso segue para gravar e é o CRM que recusa.
   No verão o erro piora: a Google devolve `dateTime` com `+01:00` para Lisboa, e a comparação de
   texto passa a errar por uma hora inteira (não só no limite).

2. **Todos os sítios que comparam datas como texto** (levantamento completo):

   | Sítio | O que faz | Efeito do erro |
   |---|---|---|
   | `routes/appointments.py:76-81` `_check_conflict` | conflito ao criar/remarcar (rotas públicas e internas do executor) | **409 falso** (este bug) |
   | `routes/appointments.py:120-125` `list_appointments` | filtro do intervalo da Agenda | evento no limite do intervalo pode faltar ou sobrar na Agenda |
   | `routes/appointments.py:165` `google_sync` | mesmo filtro na resposta da sincronização | idem |
   | `services/ai_orchestrator/orchestrator.py:743-744` `_load_calendar_busy_slots` | ocupados dados à IA e ao executor | ocupado no limite da janela pode faltar |
   | `services/google_calendar_sync.py:76,83` | apaga os eventos do Google que já não existem | evento de dia inteiro no 1.º dia da janela (`2026-10-30` < `2026-10-30T…`) nunca é apagado |
   | `services/appointment_outcomes.py:15-34` `_check_conflict` | conflito ao remarcar pelo resultado da sessão | mesmo 409 falso (só mesmo lead) |

   Já comparam bem (com `datetime()` do SQLite, que entende `Z`, `+00:00` e só-data):
   `routes/leads.py:342-343`, `routes/leads.py:386-389`, `services/followup_reconciler.py:612`,
   `database.py:974`. Do lado do executor tudo é lido com `datetime.fromisoformat` (correto):
   `meeting_scheduler._has_conflict`, `requested_slot.find_requested_slot`,
   `decision_engine._format_busy_slots_block`. Lembretes e briefing recebem o `datetime` já
   convertido (`_create_appointment_row` → `schedule_appointment_reminder_jobs`) — não afetados.

3. **O 409 ao criar a marcação não é tratado.**
   `meeting_scheduler.handle_meeting_scheduled` (linhas 805–813) chama
   `client.create_lead_appointment(...)` sem `try`. O caminho de remarcar (linhas 909–924) já
   trata o 409 e devolve a mensagem de conflito; o de criar não.
   - **Playground:** a exceção sobe em `/internal/playground/decide` → o backend-crm devolve 502
     (`routes/playground.py::_call_executors_decide`, ~linha 473–483).
   - **WhatsApp real:** `app/runners/whatsapp.py:793` chama `handle_meeting_scheduled` fora de
     qualquer `try`, e `app/workers/whatsapp_worker.py:94` chama `execute_job` também sem `try`
     → a exceção **termina o processo do worker**. A resposta ao cliente ainda não tinha sido
     enviada (o envio é depois, linhas ~1033+), o job fica "em curso" até o lease (300 s)
     expirar e é repetido — a IA volta a decidir, volta a dar 409, volta a cair. Até lá o worker
     de todas as contas fica parado/a reiniciar. (Comportamento deduzido do código; não houve
     ainda nenhum caso real em produção para observar nos logs.)

4. **Achado lateral (provável, não observado):** a marcação criada pelo agente é enviada para o
   Google (`gcal_push`, `routes/appointments.py:258`) e fica com `google_event_id`, mas com
   `user_id` NULL. A sincronização procura `google_event_id = ? AND user_id = ?`
   (`google_calendar_sync.py:50`) → não encontra → importa uma **cópia** como evento do Google
   (`lead_id` NULL, formato `Z`). Essa cópia não é reconhecida como "do mesmo lead"
   (`_has_conflict(..., exclude_lead_id=...)`) e pode bloquear uma remarcação do próprio cliente
   para um horário que se sobreponha ao atual (ex.: passar 30 min para a frente). Em produção ainda
   não há nenhuma marcação real criada depois do Google ligado, por isso não há duplicado hoje.

## Área do sistema

- `backend-crm/routes/appointments.py` (`_check_conflict`, `list_appointments`, `google_sync`)
- `backend-crm/services/ai_orchestrator/orchestrator.py` (`_load_calendar_busy_slots` — **ler
  `docs/architecture/playground-parity.md` antes**)
- `backend-crm/services/google_calendar_sync.py` (filtro de apagar, formato gravado, duplicado)
- `backend-crm/services/appointment_outcomes.py` (`_check_conflict`)
- `backend-executors/app/services/meeting_scheduler.py` (`handle_meeting_scheduled` — 409 ao criar)
- `backend-executors/app/runners/whatsapp.py` (proteção para uma falha do CRM não derrubar o worker)
- Docs: `docs/architecture/agenda.md`, `docs/architecture/google-calendar.md`

## Opções de solução

| # | Opção | Prós | Contras |
|---|---|---|---|
| 1 | **Comparar com `datetime()`/`julianday()` do SQLite em todas as queries da tabela** (como `leads.py` já faz) | Resolve os 3 formatos sem mexer nos dados; pequeno; igual ao padrão que já existe | Não indexável (irrelevante com o volume atual) |
| 2 | Normalizar o que se grava (tudo em UTC com o mesmo formato) + migração das linhas antigas | Dados limpos | Mexe em dados de produção; cada novo sítio que grave tem de lembrar a regra; não resolve sozinho as queries |
| 3 | Só tratar o 409 no executor | Tira o 502/queda do worker | Sessões seguidas continuam recusadas |

**Recomendada:** 1 + tratar o 409 (Fase 2) + guardar o `dateTime` do Google já convertido para UTC
na sincronização (só para eventos novos/atualizados — não migra linhas antigas). A comparação com
`datetime()` é a correção; a conversão na gravação só reduz o risco de alguém voltar a comparar
como texto no futuro.

## Proposta de fases (a confirmar no Plan Mode)

- **Fase 1 — Comparar como datas:** os 6 sítios da tabela acima passam a `datetime(coluna) < datetime(?)`
  (`appointment_outcomes` também); a sincronização do Google grava `dateTime` em UTC. Testes com os
  3 formatos e o caso "começa quando o outro acaba".
- **Fase 2 — 409 ao criar não rebenta:** `handle_meeting_scheduled` apanha o 409 como já faz a
  remarcação (mensagem de conflito, sem desligar o bot); `runners/whatsapp.py` protege a chamada para
  que qualquer outra falha do CRM ao gravar seja registada e não termine o worker.
- **Fase 3 — Sem cópia do próprio evento:** a sincronização reconhece eventos cujo `google_event_id`
  já pertence a uma marcação do CRM (de um lead do mesmo utilizador) e não os importa de novo.

## Riscos

- `_load_calendar_busy_slots` alimenta o Playground e o WhatsApp real — mudança na query é
  automaticamente igual nos dois (é a função partilhada), mas confirmar com os testes de paridade.
- Fase 2 toca `backend-executors/app/runners/` → categoria "envio real" (sobe sempre ao utilizador).
- Não toca em instruções da IA.
- A margem entre sessões (`feat-margem-entre-sessoes.md`) mexe nas mesmas funções de conflito —
  **tem de vir depois desta**.

## Como validar

- Testes unitários: conflito com `Z` vs `+00:00` vs só-data; sessão que começa no fim de outra = livre;
  sobreposição real = 409.
- Bancada local: `python simular.py p-seguidas A1` (setup no próprio cenário: evento ocupado amanhã
  15–16h na agenda local) → 16h aceite e gravado.
- Produção (depois do deploy): `python simular.py p-seguidas A1 --prod` com um evento ocupado no
  Google da Ayde amanhã 15–16h; `python simular.py p-val-17h A1 --prod` → sem 502.
- Regressão: `python simular.py pos-marcacao A1 --prod` (remarcação recusada por evento real continua
  recusada).

---

## Plano aprovado (26/10/2026)

Opção 1 da tabela acima + tratar o 409 ao criar + gravar o `dateTime` do Google em UTC. Sem migração
de dados e sem coluna nova. Toca no envio real do WhatsApp (Fase 2) → **só junta a `main` com o "sim"
explícito do utilizador**.

### Fase 1 — Comparar como datas (backend-crm)

**Objetivo:** todas as queries da tabela `appointments` comparam horários como datas, não como texto.

| Arquivo | O que muda |
|---|---|
| `backend-crm/routes/appointments.py` | `_check_conflict`, `list_appointments` e `google_sync` usam `datetime(coluna) < datetime(?)`; `ORDER BY datetime(a.start_at)` |
| `backend-crm/services/appointment_outcomes.py` | `_check_conflict` idem |
| `backend-crm/services/ai_orchestrator/orchestrator.py` | `_load_calendar_busy_slots` idem (função partilhada Playground ↔ WhatsApp real — nenhum campo novo no `ContextBundle`) |
| `backend-crm/services/google_calendar_sync.py` | `DELETE` dos eventos que saíram do Google com `datetime()`; novo `_to_utc_iso()` grava `dateTime` como `…+00:00` |
| `backend-crm/tests/test_appointments_conflict_by_professional.py` | 16h depois de evento `Z` 15–16h = livre; sobreposição real = 409; `+01:00` do verão; dia inteiro ocupado; `appointment_outcomes._check_conflict` |
| `backend-crm/tests/test_calendar_busy_slots.py` | evento já acabado gravado com `+01:00` não aparece como ocupado |
| `backend-crm/tests/test_google_calendar_sync.py` | gravação em UTC; dia inteiro no 1.º dia da janela é apagado quando sai do Google |
| `docs/architecture/agenda.md`, `docs/architecture/google-calendar.md` | formatos guardados e regra "comparar sempre com `datetime()`" |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `436bc73` | Comparação por datas nos 6 sítios + Google gravado em UTC + testes + docs |

### Relatório da Fase 1 — o que mudou na prática

**Antes:** a agenda comparava horários como se fossem palavras; um evento do Google que acabava às
16h "colidia" com uma sessão às 16h, e no verão o erro chegava a uma hora inteira.
**Agora:** os horários são comparados como horas de verdade, seja qual for a forma como foram
guardados; sessões seguidas passam, sobreposições reais continuam recusadas.
**Para validar:** Cenários P1, P2 e P3 (bancada local) e, depois do deploy, C1.

### Fase 2 — 409 ao criar não rebenta (backend-executors)

**Objetivo:** um conflito (ou outra falha do CRM) ao gravar a marcação nunca deixa o cliente sem
resposta nem derruba o worker.

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/meeting_scheduler.py` | `handle_meeting_scheduled`: `try` à volta de `create_lead_appointment` — 409 → mensagem de conflito, bot não desligado, sem evento `created`; outra falha → log e segue |
| `backend-executors/app/runners/whatsapp.py` | exceção nos handlers de marcação vira `_fail_job` retryable (`meeting_persist_failure`) — não termina o worker e não envia nada |
| `backend-executors/tests/test_meeting_scheduled_events.py`, `tests/test_followup_tick_runner.py` | 409 → mensagem de conflito, bot ligado, sem evento; 500 → sobe; runner reagenda sem enviar |
| `docs/architecture/agenda.md` | resposta do CRM ao criar |

**Decisão (diferente do plano inicial):** uma falha do CRM que **não** é 409 já não "segue sem
marcação" — isso faria o bot dizer "está marcado" sem nada gravado. Agora sobe para o runner, que
reagenda o job (nada foi enviado ainda). No Playground essa falha continua a dar 502 (honesto).

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `4582177` | 409 ao criar tratado como conflito; runner reagenda o job noutras falhas |

### Relatório da Fase 2 — o que mudou na prática

**Antes:** se o CRM recusasse gravar a marcação, o Playground dava erro 502 e, no WhatsApp real, o
processo que envia as mensagens de todas as contas parava e repetia o mesmo erro.
**Agora:** um horário recusado por estar ocupado recebe a mensagem normal de "esse horário acabou de
ficar indisponível"; qualquer outra falha faz o sistema tentar de novo mais tarde, sem enviar ao
cliente uma confirmação falsa e sem parar as outras contas.
**Para validar:** Cenário T1 (testes automáticos) — o 409 real deixou de acontecer com a Fase 1, por
isso não há conversa da bancada que o provoque.

### Fase 3 — Sem cópia do próprio evento (backend-crm)

**Objetivo:** a sincronização do Google não reimporta como "evento do Google" uma marcação que o
próprio CRM enviou para lá.

| Arquivo | O que muda |
|---|---|
| `backend-crm/services/google_calendar_sync.py` | antes de inserir, reconhece `google_event_id` de marcação do CRM de um lead do mesmo utilizador; apaga cópia `source='google'` antiga |
| `backend-crm/tests/test_google_calendar_sync.py` | sem cópia; lead de outro utilizador continua a importar |
| `docs/architecture/google-calendar.md` | algoritmo do sync |

### Commits Fase 3

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `7704c50` | Sync salta eventos que já são marcações do CRM |

### Relatório da Fase 3 — o que mudou na prática

**Antes:** cada marcação feita pelo agente voltava do Google como um "evento do Google" duplicado,
que podia impedir o próprio cliente de remarcar para um horário próximo.
**Agora:** a sincronização reconhece a marcação do próprio CRM e não a duplica.
**Para validar:** Cenário T1 (só dá para ver com o Google ligado — na bancada local não há Google).

---

## Checks de Validação

### Cenário T1 — Testes automáticos
- [x] backend-crm: testes novos falham no código antigo (6) e passam com a correção; suite completa verde
- **Validado em:** 26/10/2026 — 267 testes passaram
- [x] backend-executors: testes da Fase 2 + suite completa
- **Validado em:** 26/10/2026 — 403 passaram; 2 falhas em `test_recepcao_sales_flow_pending.py` que já existiam (só importa `decision_engine`, não tocado por esta branch)
- [x] backend-crm: teste da Fase 3
- **Validado em:** 26/10/2026 — suite completa 269 passaram

### Cenário P1 — Bancada local: sessões seguidas (`p-seguidas`)
- [x] Setup: evento Google **ocupado** amanhã 15:00–16:00, gravado com `Z`, na base local da bancada
- [x] `python simular.py p-seguidas A1` → 16h aceite e gravado (evento `created`), sem 502
- **Validado em:** 26/10/2026 — bancada com o código da branch; evento `Z` 27/10 15–16h inserido depois
  da limpeza da agenda (invólucro no scratchpad, o `simular.py` não tem setup de ocupados); 16h aceite e
  gravado ao lado do evento (`tentativas/20261026-1206-A1-ocupado-p-seguidas.md`)

### Cenário P2 — Bancada local: limite das 17h da Val (`p-val-17h`)
- [x] `python simular.py p-val-17h A1` → conversa termina sem 502
- **Validado em:** 26/10/2026 — com evento `Z` qui 29/10 15–16h; 17h recusada (fora do horário), 16h
  proposta e aceite, sem 502 (`tentativas/20261026-1208-A1-ocupado-p-val-17h.md`). **Achado à parte:** a
  confirmação final não gravou a marcação — a Filha não devolveu a data (`none_child_no_candidate` →
  `missing_start_at`); não é conflito, ver "Ajustes Possíveis"

### Cenário P3 — Regressão: remarcação contra evento real (`pos-marcacao`)
- [x] `python simular.py pos-marcacao A1` → remarcação para horário ocupado continua recusada
- **Validado em:** 26/10/2026 — com evento `Z` qui 29/10 15–16h; "quinta às 15h" recusada ("Esse horário
  já está ocupado") (`tentativas/20261026-1211-A1-ocupado-pos-marcacao.md`). **Achado à parte:** no mesmo
  turno a marcação foi remarcada para 16h15 sem o cliente aceitar (e contra o limite das 16h da Val) —
  ver "Ajustes Possíveis"

### Cenário C1 — Produção (depois do deploy, só após o "sim" ao merge)
- [x] Evento ocupado no Google da Ayde amanhã 15–16h; `python simular.py p-seguidas A1 --prod` → 16h aceite
- **Validado em:** 26/10/2026 — 16h de ter 27/10 aceite e gravada (`tentativas/20261026-1231-PROD-A1-p-seguidas.md`).
  O evento criado pela utilizadora já foi importado como `+00:00` (sincronização nova ativa) — por isso este
  cenário sozinho não distingue código novo de antigo; a prova é o `p-val-17h` abaixo
- [x] `python simular.py p-val-17h A1 --prod` → sem 502
- **Validado em:** 26/10/2026 — 16h de qui 29/10 aceite e **gravada** ao lado do evento `Teste CRM — ocupado`
  gravado com `Z` (15–16h, o caso exato do PROD07, que dava 409 → 502) (`tentativas/20261026-1232-PROD-A1-p-val-17h.md`)
- [x] `python simular.py pos-marcacao A1 --prod` → remarcação recusada continua recusada
- **Validado em:** 26/10/2026 — "quinta às 15h" recusada como ocupada, com alternativas 16h/sex 11h
  (`tentativas/20261026-1234-PROD-A1-pos-marcacao.md`). Ressalva: a marcação inicial (ter 14h) não foi gravada
  (mesmo achado "Confirmação sem gravar" de "Ajustes Possíveis"), por isso a recusa veio da resposta da IA com
  os ocupados, não de uma remarcação real no CRM
- Nota de deploy (26/10): backend-crm em produção às 12:19 UTC; backend-executors e worker com o build a falhar
  pela avaria do Railway "Slow build snapshot uploads in EU West" — os cenários C1 correram com o CRM novo e o
  executor ainda antigo (a Fase 2 só atua quando o CRM devolve 409, que estes cenários já não provocam)

---

## Ajustes Possíveis Pós-Implementação

- **Confirmação sem gravar (visto em `p-val-17h`, 26/10):** no turno "Sim, pode confirmar" a Mãe marca
  `meeting_scheduled=true` com rota `pre-agendamento`, a Filha escreve "Experiência Agendada" mas não
  devolve `meeting_datetime_candidate` → nada gravado e o cliente acredita que está marcado. Não é desta
  branch; provavelmente da família de `fix-confirmacao-grava-proposta-antiga.md` /
  `fix-agendamento-le-fluxo-de-venda.md`.
- **Remarcação para a contraproposta sem aceite (visto em `pos-marcacao`, 26/10):** ao recusar
  "quinta 15h" o agente remarcou logo para a sua própria sugestão (16h15) antes de o cliente responder, e
  16h15 viola o limite de início das 16h da Val. Já acontecia com o código antigo (como texto, 16h15 também
  não colidia).
- Linhas antigas do Google com `Z`/`+01:00` continuam assim até o evento ser sincronizado de novo — sem
  efeito, as queries usam `datetime()`.
