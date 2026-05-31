# Evolução do Decision Contract (backward compatible)

> **Status: CONCLUÍDO** — Todos os itens foram implementados: campos opcionais em `MotherDecision`, normalização de `agent_mode`, dual-read de `meeting_scheduled`, `FILHA FOLLOW-UP` e `FILHA CLOSING` especializadas, campos de observabilidade no `decision_trace`. Arquivo mantido como registro histórico.

## Contexto

O contrato atual da LLM Mãe tem 4 campos obrigatórios. Esta proposta adiciona campos opcionais sem quebrar o legado, usando dual-read para compatibilidade.

---

## Contrato atual (MotherDecision)

Campos obrigatórios mantidos:
- `route_to` — `qualification|apresentation|follow-up|closing`
- `perceived_category` — mesmos valores + null
- `confidence` — 0..1
- `reason` — string

---

## Campos novos propostos (opcionais na LLM Mãe)

| Campo | Tipo | Descrição |
|---|---|---|
| `agent_mode` | `consultivo\|agenda\|direto` | Modo normalizado retornado pela Mãe |
| `signals.meeting_scheduled` | bool | Sinal de reunião agendada |
| `signals.intent_level` | `low\|medium\|high` | Nível de intenção percebido |
| `signals.urgency_level` | `low\|medium\|high` | Nível de urgência |
| `signals.price_acceptance` | `no\|unsure\|yes` | Aceitação de preço |
| `objective` | string curta | Objetivo da resposta atual |
| `next_action_hint` | `reply\|ask_qualification\|handoff\|ignore` | Sugestão de próxima ação |

---

## Normalização de agent_mode no executor

| Valor recebido | Normalizado para |
|---|---|
| `consultivo` | `consultivo` |
| `agenda` | `agenda` |
| `direto` | `direto` |
| `closer` | `direto` |
| `sdr_scheduler` | `agenda` (ou `consultivo` com `human_in_loop`/`requires_handoff`) |

---

## Regra dual-read de `meeting_scheduled`

Para compatibilidade com o contrato legado:
1. Primeiro lê `mother_decision.signals.meeting_scheduled` (bool, novo)
2. Se ausente: fallback para substring `meeting_scheduled` em `mother_decision.reason` (legado)

Valor final publicado em `decision_trace.meeting_scheduled`.

---

## Campos adicionados ao `decision_trace` (observabilidade)

- `agent_mode_normalized`
- `mother_objective`
- `next_action_hint`
- `mother_signals` (resumo)

---

## Filhas especializadas a criar

- `FILHA FOLLOW-UP` dedicada para `route_to=follow-up` (separada da genérica)
- `FILHA CLOSING` dedicada para `route_to=closing`
- Fallback para prompt genérico em caso de erro de construção de prompt

---

## Regras de automação de meeting scheduler

| agent_mode | Comportamento |
|---|---|
| `consultivo` | Não dispara criação automática de appointment (fluxo com human-in-loop/handoff) |
| `agenda` | Pode disparar automação quando `decision_trace.meeting_scheduled=true` |
| `direto` | Não participa da automação de agendamento |

---

## Regra de guardrail para escalada closing (modo agenda)

- Bloqueio de escalada para `closing` ocorre para SDR legacy (`agent_mode=sdr_scheduler`) e agenda com indicadores de handoff/human-in-loop
- `agenda` sem esses indicadores pode seguir para `closing` sem bloqueio automático

---

## Arquivos a modificar

| Arquivo | O que mudar |
|---|---|
| `backend-executors/app/services/orchestrator_models.py` | Expandir `MotherDecision` com campos opcionais |
| `backend-executors/app/services/decision_engine.py` | Dual-read de signals, prompt das Filhas especializadas |
| `backend-executors/app/services/meeting_scheduler.py` | Consumir primeiro sinal estruturado, fallback para reason legado |
