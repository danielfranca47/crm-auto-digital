# Os 3 agentes do Orion

Um doc por agente da página **Tipos de Agentes** (`/agentes-info`, `frontend-crm/src/pages/TiposAgentes.tsx`),
com o que o sistema faz em cada etapa da página e o que a página promete sem o código cumprir.

| Doc | Agente | Preset (`template_key` + `agent_mode`) |
|---|---|---|
| [agente-01-sdr-alto-ticket.md](agente-01-sdr-alto-ticket.md) | 01 · Robusto — SDR de Alto Ticket | `sdr_padrao` + `sdr_scheduler` |
| [agente-02-vendedor-autonomo.md](agente-02-vendedor-autonomo.md) | 02 · Direto — Vendedor Autônomo | `closer_agressivo` + `direto` |
| [agente-03-assistente-comercial.md](agente-03-assistente-comercial.md) | 03 · Híbrido — Assistente Comercial | `hybrid_scheduler` + `agenda` |

Uma combinação que não corresponde a nenhum preset (`getActivePreset` devolve `null`) é uma combinação
personalizada e o comportamento deixa de ser o descrito na página.

## Diferenças entre os 3

| | Agente 01 | Agente 02 | Agente 03 |
|---|---|---|---|
| `agent_type` | `agent_1` | `agent_2` | `agent_3` |
| Modo normalizado | `agenda` (ou `consultivo` com `human_in_loop`/`requires_handoff`) | `direto` | `agenda` |
| Fases | p0 → p1 → p2 → p3a → p3b → p4 → p5 | p0 → p1 → p2 → p5 | p0 → p1 → p2 → p3a → p3b → p4 → p5 |
| Apresentação | `scheduler` | `sales` (forçado) | `scheduler`, ou `sales` com `appointment_mode=commercial` |
| Closing pelo bot | não | sim, bot continua ativo | não |
| Lembretes por omissão | 24h e 1h | — | 24h e 2h |
| Follow-up | `sdr_scheduler` (máx. 4), por temperatura | `cart_recovery` 2h/24h/48h (máx. 3) | `hybrid_scheduler` (máx. 3), por resultado da sessão |
| Follow-up por inatividade | sim | não | sim |
| Campos obrigatórios sugeridos ao criar | `service_interest`, `availability_window` | `service_interest`, `price_acceptance` | `service_interest`, `availability_window` |

## Manter atualizado

Quando mudar a página Tipos de Agentes, `AGENT_PRESETS` ou o comportamento de um agente no código: atualizar
o doc do agente (estado atual, sem histórico) e as skills `.claude/skills/agente-0X-*` que apontam para ele.
