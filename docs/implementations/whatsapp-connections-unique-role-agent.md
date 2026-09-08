# Constraint de banco: 1 conexão `role='agent'` viva por usuário

**Branch:** `fix/whatsapp-connections-unique-role-agent`
**Status:** Em andamento

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
limpar direito), não uma garantia de schema. O objetivo desta implementação
é fechar a lacuna em dois níveis: uma constraint no banco (impede a
duplicata de existir) e um `ORDER BY` defensivo no código (garante
resolução correta mesmo se a constraint falhar por algum motivo).

---

## Problemas Identificados (estado anterior)

1. **Sem constraint de unicidade `(user_id, role='agent')`:** só existe
   `UniqueConstraint("instance_id")` (`backend-core/app/models/whatsapp_connection.py:12`).
   Nada no schema impede duas linhas `role='agent'` para o mesmo `user_id`.
2. **`get_connection_for_user()` sem `ORDER BY`:**
   `backend-core/app/services/whatsapp_connections.py:23-27` — `.filter(...).first()`
   sem ordenação. Se existirem 2 linhas `role='agent'` para o mesmo usuário,
   qual delas é devolvida não é garantido.

---

## Abordagem

```
CREATE UNIQUE INDEX ... ON whatsapp_connections(user_id) WHERE role = 'agent'
  ├─ role='agent'   → no máx. 1 linha viva por user_id (constraint aplicada)
  └─ role='monitor' → fora do índice parcial, continua N por user_id (1 por colaborador)

get_connection_for_user()
  └─ .order_by(id.desc()).first() → mesmo numa duplicata que escape a constraint
     (ex.: banco antigo sem o índice ainda), resolve sempre para a mais recente
```

Diagnóstico prévio confirmou que os dois únicos pontos de escrita
(`upsert_connection()` / `upsert_connection_optional_token()`,
`whatsapp_connections.py:58-145`) sempre resolvem a linha existente por
`instance_id` primeiro — só inserem linha nova quando não há `instance_id`
igual — então o índice parcial não deveria rejeitar nenhum fluxo legítimo
hoje.

**Verificação de produção (antes de qualquer código):** query direta via
`railway ssh -s backend-core` no SQLite de produção
(`DATABASE_URL=sqlite:////data/core.db`, confirmado via `railway variables`)
— `SELECT user_id, COUNT(*) FROM whatsapp_connections WHERE role='agent'
GROUP BY user_id HAVING COUNT(*) > 1`. Resultado: **0 duplicatas** (3 linhas
no total, todas `role='agent'`, uma por usuário) — produção está limpa,
seguro criar o índice.

**Decisão de segurança:** a criação do índice roda em todo startup do
`backend-core` em produção. Para não travar o app caso surja alguma
duplicata não prevista no futuro (ex.: um bug reintroduzido), a criação do
índice fica dentro de um `try/except` com log de warning — consistente com
a filosofia dos demais `ensure_*` de nunca derrubar o startup por uma
migração auxiliar.

---

## Plano de Implementação

### Fase 1 — Índice único parcial + defesa no código

**Objetivo:** impedir duplicata `role='agent'` por usuário no schema, e
tornar `get_connection_for_user()` determinístico mesmo sem a constraint.

| Arquivo | O que muda |
|---|---|
| `backend-core/app/db.py` | Nova função `ensure_whatsapp_connections_unique_agent_index()` |
| `backend-core/app/main.py` | Chama a nova função em `on_startup()`, após `ensure_whatsapp_connections_columns()` |
| `backend-core/app/services/whatsapp_connections.py` | `get_connection_for_user()` — adiciona `.order_by(id.desc())` |

```python
# ANTES (whatsapp_connections.py)
def get_connection_for_user(db: Session, user_id: int) -> Optional[models.WhatsappConnection]:
    return (
        db.query(models.WhatsappConnection)
        .filter(models.WhatsappConnection.user_id == user_id, models.WhatsappConnection.role == "agent")
        .first()
    )

# DEPOIS
def get_connection_for_user(db: Session, user_id: int) -> Optional[models.WhatsappConnection]:
    return (
        db.query(models.WhatsappConnection)
        .filter(models.WhatsappConnection.user_id == user_id, models.WhatsappConnection.role == "agent")
        .order_by(models.WhatsappConnection.id.desc())
        .first()
    )
```

```python
# db.py — nova função (mesmo padrão de ensure_whatsapp_connections_columns)
def ensure_whatsapp_connections_unique_agent_index() -> None:
    """Garante no máx. 1 conexão role='agent' viva por usuário — índice único
    parcial (role='monitor' fica fora, continua N por usuário). Sintaxe
    idêntica em SQLite/Postgres, não precisa branch por dialect. Em try/except
    para nunca derrubar o startup caso surja alguma duplicata inesperada."""
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_whatsapp_connections_user_agent "
                    "ON whatsapp_connections(user_id) WHERE role = 'agent'"
                )
            )
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning(
            "Não foi possível criar uq_whatsapp_connections_user_agent (pode haver duplicata role='agent'): %s",
            exc,
        )
```

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | (a preencher após o commit) | Índice único parcial `role='agent'` + `ORDER BY` defensivo |

### Relatório da Fase 1 — o que mudou na prática

**Antes:** nada no banco impedia duas conexões WhatsApp "de agente"
(`role='agent'`) para o mesmo usuário ao mesmo tempo — e se isso acontecesse,
o sistema podia escolher qualquer uma das duas para enviar mensagens, sem
garantia de ser a mais recente.
**Agora:** o banco passa a impedir fisicamente uma 2ª conexão de agente por
usuário (conexões de monitoramento de colaborador continuam sem limite).
Como reforço extra, mesmo que uma duplicata escape por algum motivo, o
sistema sempre escolhe a conexão mais recente.
**Para validar:** Cenários C1, C2 e C3, acima — todos já testados e
validados nesta mesma sessão (ambiente local), sem necessidade de teste via
browser por não haver interface envolvida.

---

## Checks de Validação

### Cenário C1 — Constraint impede duplicata
- [x] Com o backend-core local rodando (índice já criado no startup), tentar
      inserir manualmente uma 2ª linha `role='agent'` para o mesmo `user_id`
      (`instance_id` diferente) direto no banco — confirmar que a constraint
      rejeita (erro de unique constraint)
- [x] Confirmar que inserir uma 2ª linha `role='monitor'` para o mesmo
      `user_id` continua funcionando normalmente
- **Validado em:** 08/09/2026 — script local via `sqlite3` direto no
  `core.db`: 2ª linha `role='agent'` rejeitada com
  `UNIQUE constraint failed: whatsapp_connections.user_id`; 2 linhas
  `role='monitor'` inseridas sem erro.

### Cenário C2 — Resolução correta com `ORDER BY`
- [x] Confirmar que `get_connection_for_user()` devolve a linha de maior
      `id` quando existir mais de uma correspondência (via script local
      isolado — em produção a constraint já impede o cenário, isto valida
      a defesa em profundidade isoladamente)
- **Validado em:** 08/09/2026 — simulado um banco legado (índice removido
  temporariamente + 2 linhas `role='agent'` forçadas para o mesmo
  `user_id`, ids 1 e 2); `get_connection_for_user()` devolveu a linha
  `id=2` (a mais recente). Índice recriado e dados de teste removidos logo
  em seguida.

### Cenário C3 — Startup não quebra
- [x] Reiniciar o backend-core localmente 2x seguidas e confirmar que a
      criação do índice é idempotente (sem erro, sem duplicar índice)
- **Validado em:** 08/09/2026 — 3 startups consecutivos locais, todos com
  `Application startup complete` sem erro na criação do índice (2º e 3º
  startup são no-op via `CREATE UNIQUE INDEX IF NOT EXISTS`).

---

## Ajustes Possíveis Pós-Implementação

- Nenhuma limpeza de dados necessária — produção já confirmada sem
  duplicatas antes desta implementação.
