# Fila de jobs — "database is locked" ao completar job com requeue

> Contexto: bug descoberto durante a validação ao vivo em WhatsApp real de
> `feat/sales-flow-espera-pausa` e `feat/sales-flow-webhook-execucao` (26/08/2026)
> — não tem relação com nenhuma das duas implementações, é uma falha
> pré-existente na fila de jobs que só apareceu porque a mensagem de teste caiu
> num caminho específico (reprocessamento de saudação composta).

## M1 — Conexão SQLite aninhada trava ao completar job com `requeue_pending_message`

**Prioridade: MÉDIA**

`complete_job_internal()` (`backend-crm/routes/executor.py`) abre uma transação
`BEGIN IMMEDIATE` na sua própria conexão e, **dentro dela**, chama
`_dispatch_system_actions()` — que, para o `system_action` `requeue_pending_message`,
chama `create_job()` (`services/jobs_service.py`). `create_job()` abre uma
**nova conexão SQLite própria** (`get_connection()`) e tenta escrever, enquanto
a conexão externa ainda segura o lock exclusivo da transação em andamento.

Sem `PRAGMA journal_mode=WAL` (está comentado em `database.py::get_connection()`)
e sem `busy_timeout` configurado, a segunda conexão falha **imediatamente** com
`sqlite3.OperationalError: database is locked` em vez de esperar a primeira
liberar o lock.

**Impacto confirmado ao vivo:** o runner de WhatsApp real
(`backend-executors/app/runners/whatsapp.py`) trata a falha de conclusão como
erro retryable e reagenda — o sistema se recupera sozinho na 2ª tentativa
(confirmado nesta sessão). Mas:
- Atrasa a resposta ao lead em até 60s (backoff da 1ª tentativa)
- Como a mensagem de resposta já tinha sido enviada por `_send_actions`/
  `core_send` **antes** do 500 (esse é o caso comum — a mensagem sai, só a
  marcação de "completed" falha), o retry reprocessa a mesma mensagem de
  entrada do zero, chama o LLM de novo e pode enviar uma **segunda resposta
  duplicada** ao lead. Isso aconteceu de fato durante o teste real desta sessão.

**Correção proposta:** mover a criação do job de requeue para **fora** da
transação `BEGIN IMMEDIATE` de `complete_job_internal` — coletar as
`system_actions` que precisam de nova conexão (como `requeue_pending_message`)
e executá-las **depois** do commit da transação principal, não durante.

Correção complementar (reduz, não elimina, o risco de colisões parecidas em
qualquer outro ponto do sistema): habilitar `PRAGMA journal_mode=WAL` (já
comentado, só descomentar) + configurar um `busy_timeout` razoável em
`get_connection()`.
