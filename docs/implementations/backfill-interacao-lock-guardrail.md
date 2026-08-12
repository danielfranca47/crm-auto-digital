# Lock/transação dedicada no guardrail 409 do backfill de interação passada

**Branch:** `feat/backfill-interacao-passada`
**Status:** Em andamento

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`docs/implementations/backfill-interacao-passada.md` (feature já graduada —
ver [`docs/architecture/pipeline-phases.md`](../architecture/pipeline-phases.md#backfill-manual-de-interação-passada-bypass-de-saudação-forçada)).

O endpoint `POST /api/leads/{lead_id}/interactions/backfill`
(`backend-crm/routes/leads.py`) só aceita backfill em leads sem nenhuma
mensagem — o guardrail faz `SELECT COUNT(*) FROM messages WHERE lead_id = ?`
e recusa com `409` se `> 0`. Esse SELECT e os `INSERT`s subsequentes não
correm dentro de uma transação/lock dedicada, então duas chamadas concorrentes
ao mesmo `lead_id` (ex.: dois cliques rápidos no botão "Salvar" do
`LeadCardDialog`, ou uma mensagem real chegando via WhatsApp no exato momento
do backfill) podem ambas passar pelo `SELECT COUNT(*) == 0` antes de qualquer
uma inserir — resultando em histórico duplicado ou intercalado de forma
inconsistente.

Risco foi aceito conscientemente na implementação original dado o caso de uso
(lead ainda não contactado de verdade, operação manual e pontual), mas o
utilizador decidiu que vale a pena endereçar.

---

## Problemas Identificados (estado anterior)

1. **Corrida entre `SELECT COUNT(*)` e `INSERT` sem lock:**
   `backend-crm/routes/leads.py`, endpoint de backfill — nada impede duas
   requisições concorrentes de passarem ambas pelo guardrail antes de
   qualquer uma escrever em `messages`.

---

## Abordagem

O `backend-crm` já tem um padrão estabelecido e usado 8x noutros pontos
sensíveis a corrida (ex.: `claim_job_internal` em `routes/executor.py`,
`fetch_next_job` em `services/jobs_service.py`, `followup_reconciler.py`):
abrir a conexão com `with get_connection() as conn:` e, logo a seguir,
`cur.execute("BEGIN IMMEDIATE")` antes de qualquer leitura que condicione uma
escrita. `BEGIN IMMEDIATE` adquire o lock de escrita (`RESERVED`)
imediatamente — uma segunda transação concorrente que tente o mesmo `BEGIN
IMMEDIATE` no mesmo banco fica bloqueada (até o timeout padrão do
`sqlite3.connect`, 5s) em vez de conseguir ler o estado antigo. Reaplicar
esse mesmo padrão já usado no projeto resolve a corrida sem introduzir
mecanismo novo (descartada a alternativa de `UNIQUE`/constraint dedicada —
desnecessária havendo já um padrão de transação explícita testado no mesmo
arquivo/projeto).

```
Endpoint recebe POST /interactions/backfill
  → _require_lead_for_user() (fora da transação — leitura simples)
  → BEGIN IMMEDIATE (adquire lock de escrita)
  → SELECT COUNT(*) FROM messages WHERE lead_id = ?
       ├─ > 0 → rollback + 409 (mesmo comportamento de hoje, agora atômico)
       └─ == 0 → INSERTs (messages + prospection_logs) → COMMIT
```

Se duas requisições concorrentes chegarem para o mesmo lead, a segunda só
consegue seu próprio `BEGIN IMMEDIATE` depois que a primeira commitar (ou
fizer rollback) — nesse momento, o `SELECT COUNT(*)` dela já vê as mensagens
gravadas pela primeira e cai corretamente no `409`, em vez de gravar por
cima. Sem mudança de contrato: request/response do endpoint continuam
idênticos — correção é puramente de concorrência interna.

---

## Plano de Implementação

### Fase 1 — Transação atômica no guardrail 409

**Objetivo:** eliminar a janela de corrida entre o `SELECT COUNT(*)` e os
`INSERT`s do backfill.

| Arquivo | O que muda |
|---|---|
| `backend-crm/routes/leads.py` | `backfill_lead_interactions`: troca `conn = get_connection()` + `try/except/finally: conn.close()` por `with get_connection() as conn:`; adiciona `cur.execute("BEGIN IMMEDIATE")` antes do `SELECT COUNT(*)`; `conn.rollback()` explícito nos pontos de saída antecipada (409 e exceção) |

```python
# ANTES
conn = get_connection()
try:
    _require_lead_for_user(conn, lead_id, current_user.id)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM messages WHERE lead_id = ?", (lead_id,))
    if cur.fetchone()[0] > 0:
        raise HTTPException(status_code=409, detail="...")
    ...
    conn.commit()
    return {...}
except HTTPException:
    conn.rollback()
    raise
except Exception as e:
    conn.rollback()
    raise HTTPException(status_code=500, detail=str(e))
finally:
    conn.close()

# DEPOIS
with get_connection() as conn:
    _require_lead_for_user(conn, lead_id, current_user.id)
    cur = conn.cursor()
    cur.execute("BEGIN IMMEDIATE")
    try:
        cur.execute("SELECT COUNT(*) FROM messages WHERE lead_id = ?", (lead_id,))
        if cur.fetchone()[0] > 0:
            raise HTTPException(status_code=409, detail="...")
        ...
        conn.commit()
        return {...}
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
```
