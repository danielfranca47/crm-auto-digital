# Ingestão de conhecimento — limite de lotes por dia/plano

**Branch:** *(a definir)*
**Status:** Aguardando Plan Mode

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`docs/implementations/camada4-ingestao-conhecimento.md`.

Hoje o único limite em `POST /api/knowledge/ingest` (`backend-crm/routes/knowledge_ingest.py`) é
estrutural — 6 fontes por lote, 1 job ativo por utilizador por vez (409 se já houver um em
andamento) — não há limite de **quantos lotes por dia** um utilizador pode disparar. Cada lote
pode envolver várias chamadas a `gpt-4o-mini` (vision por imagem + classificação), custando
dinheiro sem controle por plano.

O padrão já existe no sistema para o Playground (`backend-crm/services/plan_gates.py`,
`check_playground_limit()` — lê `entitlements["limits"]["playground_monthly_limit"]`, conta uso em
`playground_usage_monthly`, levanta 402/403 se excedido — ver
`docs/architecture/plans-limits.md`). A ideia é replicar esse padrão para a ingestão: um novo
campo de limite nos planos (ex.: `knowledge_ingest_daily_limit`), uma tabela de uso (ou reaproveitar
`jobs` filtrando por tipo + data), e um gate em `create_ingest_batch()` antes de aceitar o lote.

---

## Problemas Identificados (estado anterior)

1. **Sem gate de plano:** `routes/knowledge_ingest.py:create_ingest_batch()` não chama nenhuma
   função de `plan_gates.py` antes de criar o job.
2. **Sem campo de limite nos planos:** `entitlements["limits"]` não tem uma entrada equivalente a
   `knowledge_ingest_daily_limit` ainda.

---

## Próximos passos

Este arquivo nasce como stub — a implementação real só começa depois do diagnóstico normal
(Plan Mode) ser feito e aprovado pelo utilizador, seguindo
`docs/implementations/_guia-documentar-implementacao.md`.
