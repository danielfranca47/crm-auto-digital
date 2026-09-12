# Corrigir bug de concorrência "database is locked" na fila de jobs

**Status:** Aguardando Plan Mode
**Sprint:** `docs/plans/plano-sprint-2026-09-12.md` (item P1)
**Origem:** `docs/plans/jobs-conclusao-database-locked-melhorias-futuras.md` (M1) ·
`docs/plans/followup-auto-trigger-melhorias-futuras.md` (M2) ·
`docs/plans/cancelamento-reagendamento-melhorias-futuras.md` (M5)

---

## Motivação

Três pontos diferentes da fila de jobs sofrem do mesmo padrão de bug de concorrência do
SQLite: uma função abre uma nova conexão e tenta escrever enquanto outra conexão ainda
segura um bloqueio de escrita numa transação em andamento, ou usa um valor de status que
a tabela não aceita. Confirmado por leitura direta do código na auditoria de 12/09/2026
que os 3 casos continuam sem correção — incluindo um caso já com risco confirmado de
enviar uma segunda resposta duplicada a um lead real.

Comportamento actual:
- `complete_job_internal()` (`backend-crm/routes/executor.py`) abre `BEGIN IMMEDIATE` e,
  dentro dessa transação, despacha `requeue_pending_message`, que chama `create_job()`
  numa conexão SQLite nova — colide com o lock ainda aberto.
- `progress_followup_after_auto_send()` (`backend-crm/services/followup_state.py:340`)
  chama `create_job()` antes do `conn.commit()` dos chamadores
  (`executor.py`, `leads.py`) — mesmo padrão de bug, já corrigido em função irmã
  (`start_followup_for_inactivity()`) mas não aqui.
- `_cancel_pending_jobs_for_lead()` (`backend-crm/services/followup_state.py:595`) faz
  `UPDATE jobs SET status='cancelled'`, valor que o `CHECK` da tabela `jobs`
  (`backend-crm/database.py:142`) não aceita — falha silenciosa (`IntegrityError`).
- `database.py:44` — `PRAGMA journal_mode=WAL` continua comentado, sem `busy_timeout`
  configurado, o que faz colisões de conexão falharem imediatamente em vez de esperar.

Comportamento desejado: nenhuma das três situações falha mais — conclusão/reenfileiramento
e progressão de follow-up não colidem entre conexões, e o cancelamento de jobs pendentes
de follow-up usa um valor de status aceite pela tabela.

Risco concreto já confirmado: atraso de resposta ao lead, envio de segunda resposta
duplicada a um lead real, e falha silenciosa de pausar/cancelar follow-up (operador vê
"sucesso" na tela, mas o job pendente continua agendado e dispara mesmo assim).

---

## Área do sistema

`backend-crm` — fila de jobs (`services/jobs_service.py`, `database.py`), follow-up
automático (`services/followup_state.py`) e conclusão de jobs (`routes/executor.py`).

---

## Próximo passo

Este arquivo ainda não passou pelo **Passo 0 (Diagnóstico em Plan Mode)** de
`_guia-documentar-implementacao.md`. Para iniciar: entrar em Plan Mode usando o
contexto acima como ponto de partida, responder as 3 perguntas do Passo 0, e só depois
de aprovado seguir para a criação de branch + worktree (Passo 1).
