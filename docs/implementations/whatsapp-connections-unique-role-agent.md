# Constraint de banco: 1 conexão `role='agent'` viva por usuário

**Branch:** A definir (`feat/<slug>` ou `fix/<slug>`, decidido no Plan Mode)
**Status:** Aguardando Plan Mode

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`docs/implementations/uazapi-instancias-fantasmas.md`.

Naquela implementação diagnosticamos que `get_connection_for_user()`
(`backend-core/app/services/whatsapp_connections.py`) — usada por `GET
/whatsapp-connections/resolve-by-user`, consumida pelo `backend-executors`
para decidir de qual instância o agente real envia mensagem — faz
`.filter(user_id, role='agent').first()` **sem `ORDER BY`**. Com múltiplas
linhas `role='agent'` para o mesmo usuário, não havia garantia de resolver
para a mais recente.

A correção da Causa 1 (reinit apagando a instância antiga, ver
[`whatsapp-connection.md`](../architecture/whatsapp-connection.md#apagar-instância--limpeza-de-fantasmas))
já garante, **na prática**, que só sobra 1 linha `role='agent'` viva por
usuário — mas isso é uma garantia comportamental (depende do código sempre
limpar direito), não uma garantia de schema. Deliberadamente não
adicionamos uma constraint rígida naquela implementação porque:
- Havia risco de quebrar em cima de linhas duplicadas que já existiam em
  produção antes da correção (hoje resolvido — o painel foi zerado).
- Não era o foco da correção imediata.

## O que investigar/fazer (Plan Mode)

- Confirmar que produção está de facto sem duplicatas `role='agent'` hoje
  (query direta antes de qualquer migration).
- Desenhar a constraint (`UNIQUE(user_id, role)` só aplicável a
  `role='agent'` — `role='monitor'` continua N por usuário, um por
  colaborador) — provavelmente um índice único parcial, não uma
  `UniqueConstraint` simples na tabela toda.
- Migration idempotente seguindo o padrão do projeto
  (`ensure_whatsapp_connections_*` em `backend-core/app/db.py`).
- Considerar também adicionar `.order_by(id.desc())` em
  `get_connection_for_user()` como defesa em profundidade independente da
  constraint.
