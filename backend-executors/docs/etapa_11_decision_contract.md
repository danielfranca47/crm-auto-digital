# Etapa 11 — Decision Contract incremental (compatível)

## Contrato antigo (Mãe)
Campos obrigatórios mantidos:
- `route_to`
- `perceived_category`
- `confidence`
- `reason`

## Contrato novo (Mãe) — opcional na Etapa 11
Campos adicionados sem quebrar legado:
- `agent_mode`: `consultivo|agenda|direto`
- `signals` (objeto), com suporte mínimo para:
  - `meeting_scheduled` (bool)
  - `intent_level` (`low|medium|high`)
  - `urgency_level` (`low|medium|high`)
  - `price_acceptance` (`no|unsure|yes`)
- `objective` (string curta)
- `next_action_hint` (`reply|ask_qualification|handoff|ignore`)

## Mapeamento `agent_mode_normalized`
Normalização aplicada no executor:
- `consultivo` -> `consultivo`
- `agenda` -> `agenda`
- `direto` -> `direto`
- `closer` -> `direto`
- `sdr_scheduler` -> `agenda` (ou `consultivo` quando houver indicadores `human_in_loop`/`requires_handoff` no contexto)

## Regra dual-read de `meeting_scheduled`
Implementado comportamento incremental:
1. Primeiro lê `mother_decision.signals.meeting_scheduled` quando bool.
2. Se ausente, fallback legado para substring `meeting_scheduled` em `mother_decision.reason`.

O valor final é publicado em `decision_trace.meeting_scheduled`.

## Observabilidade adicionada em `decision_trace`
- `agent_mode_normalized`
- `mother_objective`
- `next_action_hint`
- `mother_signals` (resumo)

## Filhas especializadas adicionadas
- `FILHA FOLLOW-UP` para `route_to=follow-up`
- `FILHA CLOSING` para `route_to=closing`

Com fallback para prompt genérico em caso de erro de construção de prompt.


## Regras de automação de meeting scheduler
- `consultivo`: **não dispara** criação automática de appointment nesta etapa (fluxo com human-in-loop/handoff).
- `agenda`: pode disparar automação quando `decision_trace.meeting_scheduled=true`.
- `direto`: não participa da automação de agendamento por padrão.


## Regra de guardrail para escalada closing (agenda)
- Bloqueio de escalada para `closing` ocorre para contexto legado SDR (`agent_mode=sdr_scheduler`) e para agenda com indicadores de handoff/human-in-loop.
- `agenda` sem esses indicadores é tratada como agenda autônoma e pode seguir para `closing` sem bloqueio automático.
