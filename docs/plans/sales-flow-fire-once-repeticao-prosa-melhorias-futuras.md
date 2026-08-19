# Fluxo de Venda — nota de "ação já cumprida" para triggers `fire_once` (ideia arquivada)

> Contexto: bug relatado pelo utilizador (repetição de "posso enviar a tabela de preços?"
> mesmo após o `intent_trigger` `fire_once` já ter disparado e enviado a mídia) foi
> **resolvido via configuração** — reestruturação do AI Profile "Daniel" movendo o roteiro
> de apresentação do `custom_instructions` para blocos `phase_trigger`/`intent_trigger`/
> `orientacao` no próprio Fluxo de Venda (Camada 7), validado em testes reais no Playground
> (19/08/2026 — pergunta fora do roteiro 1-2 turnos após a tabela já enviada não repetiu
> mais o pedido de permissão). Ver [`docs/architecture/sales-flow.md`](../architecture/sales-flow.md).

---

## M1 — Nota de "ação já cumprida" quando um trigger `fire_once` é reavaliado

**Prioridade: BAIXA** (mitigação preventiva, não bug ativo — o caso relatado já está resolvido)

`_evaluate_sales_flow_phases()` (`backend-executors/app/services/decision_engine.py:~322-540`)
deduplica corretamente a **execução** de blocos `fire_once` (via `leads.triggers_fired`,
confirmado por teste real: a mídia nunca foi reenviada) — mas quando um bloco já disparado
é reavaliado, não deixa nenhum rastro no prompt da LLM filha avisando que aquela ação já foi
cumprida. Isso pode fazer a LLM repetir em prosa um pedido (ex.: "posso enviar a tabela?")
mesmo sem reenviar a ação real, **se** o `custom_instructions` do operador tiver um roteiro
fixo numerado competindo com o Fluxo de Venda em vez de delegar a sequência a ele.

**Por que não é urgente:** a causa raiz mais comum (roteiro fixo duplicado em
`custom_instructions` em vez de estruturado no Fluxo de Venda) tem solução por configuração,
sem código — orientar o operador a mover o roteiro para blocos `orientacao`/`intent_trigger`
resolve o problema na maioria dos casos, e já foi validado num caso real.

**Correção proposta (se voltar a aparecer sem essa causa configurável):** adicionar uma nota
em `result["prompt_injections"]` quando `fired=False` por já estar em `triggers_fired`
(branches `kw_trigger` ~L401-403 e `intent_trigger` ~L422-425), avisando a LLM filha que
aquele pedido/ação já foi cumprido antes nesta conversa — sem impedir que ela volte a falar
do assunto se o lead perguntar de novo por conta própria. Escopo a decidir quando for
retomado: aplicar só a `intent_trigger` ou também a `kw_trigger`; incluir também um filtro em
`_collect_intent_triggers_for_lead_phase()` (~L569-615) para parar de mostrar à IA Mãe um
`intent_trigger` já disparado (reduz ruído de prompt, não afeta o dedup real de ação).
