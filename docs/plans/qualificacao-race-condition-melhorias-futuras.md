# Qualificação — TOCTOU restante fora do `upsert_qualification_state()`

> Contexto: item deixado de fora da graduação de
> `docs/implementations/fix-qualificacao-race-condition-e-refresh.md` (14/08/2026),
> que corrigiu o lost-update em `upsert_qualification_state()` — ver
> [`docs/architecture/pipeline-phases.md`](../architecture/pipeline-phases.md#qualification).

---

## M1 — TOCTOU em `increment_attempt()`

**Prioridade: MÉDIA**

`increment_attempt()` (`backend-crm/services/qualification_state.py`) tem o
mesmo padrão de bug corrigido em `upsert_qualification_state()`: lê o contador
de tentativas de um campo, soma 1 em Python, grava — sem que leitura e
escrita estejam dentro da mesma transação atômica. Duas mensagens do mesmo
lead chegando muito próximas no tempo podem causar lost-update no contador.

**Impacto (menor que o bug já corrigido):** afeta só a contagem de tentativas
(limite de 3 perguntas por campo — ver "Persistência em `lead_qualification_state`"
em `pipeline-phases.md`), não perde nenhuma resposta do lead. Na pior hipótese,
o bot pergunta a mesma coisa uma vez a mais do que o limite configurado antes
de desistir.

**Correcção proposta:** mesmo padrão já aplicado a `upsert_qualification_state()`
— mover a leitura do contador para dentro da transação `BEGIN IMMEDIATE` da
escrita.
