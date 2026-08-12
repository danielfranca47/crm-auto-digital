# Lock/transação dedicada no guardrail 409 do backfill de interação passada

**Branch:** *(a definir ao iniciar)*
**Status:** Aguardando Plan Mode

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

## Abordagem (rascunho — a confirmar em Plan Mode)

Avaliar em Plan Mode qual mecanismo é mais adequado dado que `backend-crm`
usa SQLite raw sem ORM (`get_connection()`, sem pool de transações
compartilhado):
- Transação explícita (`BEGIN IMMEDIATE`) envolvendo o `SELECT COUNT(*)` e os
  `INSERT`s no mesmo endpoint, para serializar escritas concorrentes no mesmo
  `lead_id`.
- Alternativa mais simples: `UNIQUE`/constraint a nível de aplicação ou
  verificação atômica via `INSERT ... WHERE NOT EXISTS`.

**Notas:**
- Este rascunho **não substitui o Passo 0 (Plan Mode) obrigatório** de
  `_guia-documentar-implementacao.md` — validar em Plan Mode: se SQLite em
  modo `WAL`/`journal_mode` atual já mitiga parte do risco, se vale a pena um
  lock em nível de aplicação (ex.: por `lead_id`) em vez de transação SQL, e
  se o custo de complexidade se justifica dado que o caso de uso é uma ação
  manual e pontual do operador (não um caminho de alto tráfego).
