# Corrigir bug de concorrência "database is locked" na fila de jobs

**Branch:** `fix/concorrencia-database-locked-fila-jobs`
**Status:** Em andamento
**Sprint:** `docs/plans/plano-sprint-2026-09-12.md` (item P1)
**Origem:** `docs/plans/jobs-conclusao-database-locked-melhorias-futuras.md` (M1) ·
`docs/plans/followup-auto-trigger-melhorias-futuras.md` (M2) ·
`docs/plans/cancelamento-reagendamento-melhorias-futuras.md` (M5)

---

## Motivação

Várias funções da fila de jobs (`backend-crm`) abrem uma nova conexão SQLite
(`create_job()` → `get_connection()`) **enquanto uma conexão externa ainda
segura um lock de escrita** (`BEGIN IMMEDIATE` não commitado). Sem
`journal_mode=WAL` nem `busy_timeout`, a conexão nova falha na hora com
`sqlite3.OperationalError: database is locked` — e como as duas conexões
estão no mesmo thread/request, a externa nunca teria como liberar o lock
enquanto a interna espera (autodeadlock, não só contenção passageira).

Confirmado por leitura direta do código na auditoria de 12/09/2026.
Documentado em três planos (M1/M2/M5 acima). Risco real já confirmado ao
vivo: atraso de resposta ao lead + envio de **segunda resposta duplicada**
(M1); follow-up automático "preso" sem ninguém perceber (M2); pausar/cancelar
follow-up pela UI provavelmente falha sempre que há job pendente (M5 — o
`CHECK` da tabela é inequívoco, ainda não confirmado ao vivo).

Comportamento desejado: nenhuma dessas situações falha mais — conclusão de
job/reenfileiramento e progressão de follow-up não colidem entre conexões, e
o cancelamento de jobs pendentes de follow-up usa um valor de status aceite
pela tabela.

---

## Área do sistema

`backend-crm` — fila de jobs (`services/jobs_service.py`, `database.py`),
follow-up automático (`services/followup_state.py`) e conclusão de jobs
(`routes/executor.py`, `routes/leads.py`).

---

## Problemas Identificados (estado anterior)

1. **`database.py` sem WAL/busy_timeout:** `get_connection()` (linha ~37-45)
   não habilitava `journal_mode=WAL` (comentado) nem configurava
   `busy_timeout` — qualquer colisão entre 2 conexões falhava imediatamente
   em vez de esperar.
2. **`complete_job_internal()` cria jobs dentro do próprio `BEGIN IMMEDIATE`:**
   `routes/executor.py:920-1015` abre `BEGIN IMMEDIATE` e, antes do commit,
   chama 3 funções que hoje abrem conexão nova via `create_job()`:
   `_schedule_preagendamento_checkin()` (linha ~510), `_dispatch_sales_flow_media()`
   (linha ~240) e `_dispatch_system_actions()` (linha ~276 — ações
   `send_message`, `send_media`, `webhook`, `requeue_pending_message`).
   Achado desta auditoria: o M1 original só documentou `requeue_pending_message`
   (único caso que apareceu no teste ao vivo que originou o M1) — mas as
   outras 4 ações/funções têm exatamente o mesmo bug, mesma causa raiz.
3. **`progress_followup_after_auto_send()` cria job antes do commit do
   chamador:** `services/followup_state.py:340` chama `create_job()` no
   branch de progresso normal — os 2 call sites reais
   (`routes/executor.py::mark_outbound_sent`, `routes/leads.py::send_followup_now`)
   nunca commitam antes de chamar a função. Mesmo padrão já corrigido na
   função irmã `start_followup_for_inactivity()`, mas nunca replicado aqui.
4. **`_cancel_pending_jobs_for_lead()` usa status fora do CHECK constraint:**
   `services/followup_state.py:579-604` faz `UPDATE jobs SET status='cancelled'`,
   valor que o `CHECK` da tabela `jobs` (`database.py:142`, só aceita
   `pending/in_progress/completed/failed`) não aceita — `IntegrityError` ao
   tentar pausar/cancelar follow-up com job pendente.

---

## Abordagem

Fase 1 é defesa em profundidade (ajuda contenção genuína entre conexões
diferentes). Fases 2-4 são a correção estrutural real: nenhuma função deve
abrir conexão nova enquanto ainda está dentro de uma transação própria não
commitada — ou a criação do job é **coletada e devolvida** para o chamador
criar depois do seu próprio commit, ou (nos casos já com esse padrão
estabelecido) o `create_job()` simplesmente muda de posição para depois do
commit.

```
complete_job_internal() [Fase 2]
  BEGIN IMMEDIATE
  ... side-effects de estado (categoria, contadores) via conn ...
  _schedule_preagendamento_checkin() → devolve spec (não cria)
  _dispatch_sales_flow_media()       → devolve specs (não cria)
  _dispatch_system_actions()         → devolve specs (não cria)
  conn.commit()
  [fora do bloco de conexão] → create_job(**spec) para cada spec coletada

mark_outbound_sent() / send_followup_now() [Fase 3]
  BEGIN IMMEDIATE / transação própria
  progress = progress_followup_after_auto_send(conn, ...)  → não cria job
  conn.commit()
  if progress["reason"] == "progressed": create_job(TYPE_WHATSAPP_FOLLOWUP_PREGENERATE, ...)

_cancel_pending_jobs_for_lead() [Fase 4]
  UPDATE jobs SET status='completed', result='{"skipped": true, ...}' ← em vez de status='cancelled'
```

---

## Plano de Implementação

### Fase 1 — WAL + busy_timeout

**Objetivo:** dar margem de espera real a colisões entre conexões diferentes.

| Arquivo | O que muda |
|---|---|
| `backend-crm/database.py` | `get_connection()` habilita `PRAGMA journal_mode=WAL` e `PRAGMA busy_timeout=5000` |

### Fase 2 — `complete_job_internal` não cria job dentro do próprio `BEGIN IMMEDIATE`

**Objetivo:** eliminar o autodeadlock nas 4 ações/funções que criam job durante a transação de conclusão de job inbound.

| Arquivo | O que muda |
|---|---|
| `backend-crm/routes/executor.py` | `_schedule_preagendamento_checkin`, `_dispatch_sales_flow_media`, `_dispatch_system_actions` passam a devolver specs de job em vez de chamar `create_job()`; `complete_job_internal` cria os jobs coletados depois do `conn.commit()` |
| `backend-crm/tests/test_dispatch_requeue_pending_message.py` | testes existentes passam a checar o valor de retorno; teste novo com 2 conexões reais provando ausência de deadlock |

### Fase 3 — `progress_followup_after_auto_send` não cria job antes do commit do chamador

**Objetivo:** replicar o padrão já usado em `start_followup_for_inactivity()`.

| Arquivo | O que muda |
|---|---|
| `backend-crm/services/followup_state.py` | remove `create_job()` de dentro da função + import não usado |
| `backend-crm/routes/executor.py` | `mark_outbound_sent` cria o job depois do commit |
| `backend-crm/routes/leads.py` | `send_followup_now` cria o job depois do commit |
| `backend-crm/tests/test_followup_state.py` | teste novo cobrindo o branch "progride sem fechar" (hoje sem cobertura) |

### Fase 4 — `_cancel_pending_jobs_for_lead` usa status aceito pelo CHECK

**Objetivo:** replicar o padrão já usado em `cancel_pending_appointment_jobs()`.

| Arquivo | O que muda |
|---|---|
| `backend-crm/services/followup_state.py` | `status='cancelled'` → `status='completed'` + `result={"skipped": true, ...}` |

---

## Checks de Validação

### Cenário A1 — WAL + busy_timeout ativos (Fase 1)
- [x] Script com 2 conexões reais confirma `journal_mode=wal` e `busy_timeout=5000`
- **Validado em:** 13/09/2026 — `journal_mode=wal`, `busy_timeout=5000` confirmados
- [x] Confirmar: conexão B espera (não falha na hora) quando colide com lock da conexão A
- **Validado em:** 13/09/2026 — conexão B esperou ~0.86s e escreveu com sucesso (sem WAL/busy_timeout falharia na hora)

### Cenário A2 — sem deadlock ao completar job inbound com ações que criam job (Fase 2)
- [x] Teste com 2 conexões reais (não mockadas): `BEGIN IMMEDIATE` aberto + `_dispatch_system_actions`/`_dispatch_sales_flow_media` com ação que cria job
- **Validado em:** 13/09/2026 — `tests/test_dispatch_requeue_pending_message.py::NoDeadlockWithRealSeparateConnectionsTest`
- [x] Confirmar: nenhuma tentativa de abrir conexão nova durante a transação; jobs são criados só depois do commit
- **Validado em:** 13/09/2026 — chamada com o lock aberto retornou em <1s (não esperou busy_timeout); `create_job()` criou o job normalmente só depois do `commit()`

### Cenário A3 — follow-up progride sem travar (Fase 3)
- [x] Teste unitário cobrindo o branch "progride sem fechar" de `progress_followup_after_auto_send`
- **Validado em:** 13/09/2026 — `tests/test_followup_state.py::test_auto_send_progresses_without_reaching_max_attempts`
- [x] Confirmar: função não abre conexão nova; job de pré-geração é criado pelo chamador depois do commit
- **Validado em:** 13/09/2026 — schema de teste sem tabela `jobs` de propósito; teste passa sem tentar criar job internamente (a criação agora é responsabilidade do chamador)

### Cenário C1 — pausar follow-up com job pendente (Fase 4)
- [x] Cobertura por teste unitário (setup + ação + confirmação, com CHECK constraint real replicado no schema de teste)
- **Validado em:** 13/09/2026 — `tests/test_followup_state.py::test_pause_with_pending_job_completes_job_instead_of_integrity_error`
- [ ] Confirmar ao vivo pela UI: pausar um follow-up ativo com job pendente pela Central de Follow-ups / `LeadCardDialog` retorna sucesso (não 500)
- **Pendente:** o MCP chrome-devtools não conectou nesta sessão (timeout) — ver relatório da Fase 4 abaixo para o prompt de retomada

---

## Ajustes Possíveis Pós-Implementação

- Nenhum trade-off consciente identificado — as 4 fases são correções diretas de bugs confirmados, sem meio-termo.

---

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `780ae88` | WAL + busy_timeout=5000 em `database.py::get_connection()` |

**Detalhes do commit `780ae88`:**
- `backend-crm/database.py` — `get_connection()` passa a rodar `PRAGMA journal_mode=WAL` (antes comentado) e `PRAGMA busy_timeout=5000` a cada conexão aberta.

### Relatório da Fase 1 — o que mudou na prática

**Antes:** quando duas conexões diferentes ao banco tentavam escrever quase ao mesmo tempo, a segunda falhava imediatamente com "database is locked", em vez de esperar a primeira terminar.
**Agora:** a segunda conexão espera até 5 segundos antes de desistir — o suficiente para a maioria das colisões reais (ex.: o webhook do WhatsApp processando ao mesmo tempo que o robô de follow-up faz uma verificação periódica) se resolverem sozinhas.
**Para validar:** Cenário A1, abaixo (já validado via script nesta sessão — ver nota).

**Nota:** validei o Cenário A1 eu mesmo via script Python (2 conexões reais, uma segurando o lock por 1s enquanto a outra tenta escrever) antes de commitar — confirmado `journal_mode=wal`, `busy_timeout=5000`, e a segunda conexão esperou ~0.86s e conseguiu escrever em vez de falhar na hora. Não é um cenário testável pela UI (é uma condição de corrida entre conexões, não uma ação clicável) — por isso a validação foi automatizada em vez de via browser.

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `71fc3b9` | `complete_job_internal` não cria mais job dentro do próprio `BEGIN IMMEDIATE` |

**Detalhes do commit `71fc3b9`:**
- `backend-crm/routes/executor.py` — `_dispatch_system_actions()` (ações `send_message`, `send_media`, `webhook`, `requeue_pending_message`), `_dispatch_sales_flow_media()` e `_schedule_preagendamento_checkin()` (renomeada para `_build_preagendamento_checkin_job()`) passam a devolver specs de job em vez de chamar `create_job()` diretamente. `complete_job_internal()` acumula as specs num `pending_jobs` e só cria os jobs de fato depois do próprio `conn.commit()`.
- `backend-crm/tests/test_dispatch_requeue_pending_message.py` — testes existentes passam a checar o valor de retorno (a tabela `jobs` não é mais tocada por essas funções); teste novo (`NoDeadlockWithRealSeparateConnectionsTest`) com 2 conexões SQLite reais provando ausência de deadlock.

### Relatório da Fase 2 — o que mudou na prática

**Antes:** quando o robô, ao terminar de responder um lead pelo WhatsApp, precisava fazer alguma ação extra (mandar uma segunda mensagem, mandar uma mídia, chamar um webhook configurado no fluxo de vendas, ou reprocessar uma pergunta que ficou pendente), o sistema tentava preparar essa ação extra *durante* a própria finalização — e isso podia travar com "database is locked", atrasando a resposta ao lead e, em alguns casos, fazendo o sistema reenviar a mesma resposta duas vezes.
**Agora:** o sistema primeiro termina de finalizar tudo, e só depois prepara essas ações extras — nunca mais na mesma respiração. Isso vale para as 4 situações que tinham esse problema (não só a que já tinha aparecido num teste anterior: mandar mensagem, mandar mídia, chamar webhook, e reprocessar pergunta pendente), e também para o lembrete de check-in de pré-agendamento.
**Para validar:** Cenário A2, acima (já validado nesta sessão via teste automatizado — não é um cenário clicável na UI, é uma condição de corrida de banco de dados).

### Commits Fase 3

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `fb3176b` | `progress_followup_after_auto_send` não cria mais job antes do commit do chamador |

**Detalhes do commit `fb3176b`:**
- `backend-crm/services/followup_state.py` — remove `create_job()` de dentro de `progress_followup_after_auto_send()` (branch "progride sem fechar") + import não usado.
- `backend-crm/routes/executor.py` — `mark_outbound_sent` captura o retorno da função e cria o job de pré-geração depois do próprio `conn.commit()`, só quando `reason == "progressed"`.
- `backend-crm/routes/leads.py` — `send_followup_now` move a mesma criação de job para depois do commit (antes nunca criava o job — esse era o próprio bug: o follow-up progredia mas a próxima mensagem nunca era pré-gerada).
- `backend-crm/tests/test_followup_state.py` — teste novo cobrindo o branch "progride sem fechar" (o único teste existente do branch de auto-send batia direto no branch `max_attempts_reached`, que retorna antes de chegar no `create_job()` — por isso nunca pegou este bug).

### Relatório da Fase 3 — o que mudou na prática

**Antes:** quando um follow-up automático avançava para a próxima tentativa (ex.: primeira mensagem não teve resposta, hora de mandar a segunda), o sistema tentava preparar essa próxima mensagem *durante* a própria atualização do estado do follow-up — o que podia travar com "database is locked". Quando travava, a transação era desfeita: o estado voltava a "não avançou", mas silenciosamente — sem erro visível para ninguém, o follow-up simplesmente ficava parado.
**Agora:** o sistema primeiro termina de atualizar o estado do follow-up, e só depois — já com tudo salvo — prepara a próxima mensagem. As duas coisas nunca mais competem pelo mesmo lock. Além disso, corrigi um bug relacionado: o botão "enviar follow-up agora" (`send_followup_now`) nunca tinha preparado a próxima mensagem automaticamente depois de um envio manual — agora também faz isso.
**Para validar:** Cenário A3, acima (já validado nesta sessão via teste automatizado — não é um cenário clicável na UI, é uma condição de corrida de banco de dados).

### Commits Fase 4

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `dd53465` | `_cancel_pending_jobs_for_lead` usa status aceito pelo CHECK da tabela `jobs` |

**Detalhes do commit `dd53465`:**
- `backend-crm/services/followup_state.py` — `UPDATE jobs SET status='cancelled'` (fora do `CHECK`) passa a usar `status='completed'` + `result={"skipped": true, "reason": "followup_paused_or_cancelled"}`, mesmo padrão já usado em `jobs_service.py::cancel_pending_appointment_jobs`.
- `backend-crm/tests/test_followup_state.py` — schema de teste passa a incluir `jobs` (com o mesmo `CHECK` real) e `followup_reconcile_guard`; teste novo prova que pausar follow-up com job pendente não quebra mais com `IntegrityError`.

### Relatório da Fase 4 — o que mudou na prática

**Antes:** ao pausar ou cancelar um follow-up que tinha uma próxima mensagem já agendada, o sistema tentava marcar esse job pendente como "cancelado" — só que esse valor não existe na lista de status que o banco aceita para jobs, e a tentativa quebrava a operação inteira. O operador recebia um erro (não um "sucesso falso", como a suspeita inicial de outra auditoria sugeria) sempre que tentasse pausar/cancelar um follow-up com mensagem pendente.
**Agora:** o job pendente é marcado como "concluído, mas pulado" em vez de "cancelado" — valor que o banco aceita — e pausar/cancelar o follow-up funciona normalmente.
**Para validar:** Cenário C1, abaixo — a parte de banco de dados já está validada por teste automatizado; falta confirmar ao vivo pelo botão de pausar follow-up na UI, o que não consegui fazer nesta sessão porque o MCP do chrome-devtools não conectou (timeout de conexão).

**Quer que eu tente de novo agora, ou prefere testar você mesmo (aqui ou numa conversa nova)?** Se preferir retomar depois, pode colar:

> Lê `docs/implementations/fix-concorrencia-database-locked-fila-jobs.md`, secção "Fase 4", e executa o teste do Cenário C1 (pausar um follow-up ativo com job pendente pela Central de Follow-ups / `LeadCardDialog` e confirmar que retorna sucesso, não 500).
