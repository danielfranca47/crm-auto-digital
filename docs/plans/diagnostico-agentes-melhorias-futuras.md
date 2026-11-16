# Diagnóstico de agentes — melhorias futuras

Itens deixados de fora da implementação `feat-documentacao-diagnostico-agentes.md` (graduada em
16/11/2026). Triagem: o utilizador pediu para não decidir item a item — todos ficam com
`Prioridade: por definir`, para a revisão com `/statusplans`.

## M1 — Follow-up de carrinho abandonado arranca com qualquer link
**Prioridade: por definir**
**Estado atual:** `routes/executor.py` arranca o carrinho abandonado quando a resposta contém "http".
**O que construir:** usar o sinal `checkout_sent` ou o domínio do checkout configurado.

## M2 — Prompts contraditórios sobre o link de pagamento
**Prioridade: por definir**
**Estado atual:** em `decision_engine.py`, a validação exige "URL real" e a apresentação aceita "real ou
placeholder". Relacionado com `motor-llm-otimizacoes.md` M5.
**O que construir:** uma regra única sobre o link de pagamento nas duas Filhas.

## M3 — Modo do Agente 01 lido de duas formas
**Prioridade: por definir**
**Estado atual:** o executor passa `sdr_scheduler` a `consultivo` com `human_in_loop`/`requires_handoff`;
o orquestrador do CRM não faz essa normalização.
**O que construir:** uma só normalização do modo, partilhada pelos dois serviços.

## M4 — Promessas da página Tipos de Agentes sem código
**Prioridade: por definir**
**Estado atual:** a página promete Calendly, PagSeguro, multicanal, upsell, NPS e renovação de pacote, que
o código não faz (ver "prometido vs. código" em `docs/architecture/agentes/`).
**O que construir:** decidir se a página muda ou se cada promessa vira item de produto (candidato a
`docs/discovery/`).

## M5 — Onboarding sem conversas de referência
**Prioridade: por definir**
**Estado atual:** as skills `diagnosticar-agente` e `configuracao-personalizada` partem de conversas reais,
prints ou de um prompt do comportamento desejado.
**O que construir:** um modo de entrevista ao dono do negócio que gere o comportamento esperado e os
cenários da bancada (candidato a `docs/discovery/`).
