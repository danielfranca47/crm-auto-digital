# Classificar o processo do cliente nos 3 agentes do Orion

Fonte de verdade dos nomes e das etapas: a página **Tipos de Agentes**
(`https://crmapp.danielfranca.pt/agentes-info`, código em `frontend-crm/src/pages/TiposAgentes.tsx`).
Os presets que ligam cada agente à configuração estão em `AGENT_PRESETS`
(`frontend-crm/src/types/agente.ts`). Usa sempre estes nomes ao falar com o utilizador e nos documentos.
O que o sistema faz em cada agente (fases, fecho, lembretes, follow-up) está em
[`docs/architecture/agentes/README.md`](../../../../docs/architecture/agentes/README.md); aqui ficam só os
critérios para classificar. Se a página mudar, relê-a e atualiza esta referência.

## Os 3 agentes

| Agente (skill) | Para quem (página) | Preset no código | Fim de uma conversa bem-sucedida |
|---|---|---|---|
| **Agente 01 · Robusto — SDR de Alto Ticket** (`agente-01-sdr-alto-ticket`) | imóveis, advocacia, clínicas estéticas, consultorias B2B; ciclo longo, alto ticket | `template_key=sdr_padrao`, `agent_mode=sdr_scheduler` | lead aprovado nos Filtros 1–3 → **reunião agendada + Handoff com dossiê**; o humano apresenta e fecha |
| **Agente 02 · Direto — Vendedor Autônomo** (`agente-02-vendedor-autonomo`) | infoprodutos, e-commerce, pedidos de lojas físicas, cursos e assinaturas; low ticket | `template_key=closer_agressivo`, `agent_mode=direto` | **link de pagamento enviado e pago**, sem humano |
| **Agente 03 · Híbrido — Assistente Comercial com Agendamento Inteligente** (`agente-03-assistente-comercial`) | coaches, terapeutas, personal trainers, consultores solo, serviços por hora | `template_key=hybrid_scheduler`, `agent_mode=agenda` | **sessão agendada** com o profissional + briefing; não apresenta nem fecha |

O quiz da página resume a escolha em 3 perguntas, e é assim que se classificam as conversas:

| Pergunta do quiz | Agente 01 | Agente 02 | Agente 03 |
|---|---|---|---|
| Ticket médio | acima de R$ 2.000, contratos longos | abaixo de R$ 500 | cobra por sessão ou hora (R$ 200–2.000) |
| Quem apresenta e fecha? | o dono ou o time de vendas, pessoalmente | ninguém: "o produto vende-se sozinho" | o profissional, só na sessão agendada |
| Tipo de negócio | imobiliária, advocacia, clínica, consultoria | e-commerce, loja, infoproduto, curso | coach, terapeuta, personal, mentor |

## Segunda dimensão: inbound ou outbound

A página divide cada jornada em **Inbound** (o lead veio até ti e tem dor) e **Outbound** (foste tu ao
lead e o fit é presumido). As duas convergem numa etapa comum: Filtro 3 no Agente 01, Pitch no
Agente 02 e Aprofunda a Dor no Agente 03. Para cada conversa de referência, regista a origem. A
saudação automática de anúncio ou um formulário indicam inbound; um primeiro contacto da empresa indica
outbound. No código, a origem decide-se por `leads.origin`: só `"outbound"` exato conta como outbound
(`_classify_lead_origin`), e as aberturas vêm de `origin_inbound_opener` / `origin_outbound_opener`.
Se as conversas forem todas inbound, os cenários outbound são opcionais; diz-lo no README.

## Sinais nas conversas (evidência por conversa)

| Sinal | 01 SDR Alto Ticket | 02 Vendedor Autônomo | 03 Assistente Comercial |
|---|---|---|---|
| Perguntas de perfil: setor, porte, faturamento (Filtro 1 — Fit) | **forte** | fraco (1–2 perguntas) | médio (2–3 de contexto) |
| Perguntas de Poder, Prioridade, Preço e Timing (Filtro 3 — 4Ps) | **forte** | — | fraco |
| Acaba em reunião com o vendedor ou o dono | **forte** | — | — |
| Acaba em sessão ou consulta com o profissional | fraco | — | **forte** |
| Pitch completo + preço âncora + link de pagamento na conversa | — | **forte** | — |
| "Cliente parecido conseguiu X", explicação de como é a sessão (Aquecimento) | fraco | médio (prova social) | **forte** |
| Lembretes antes do encontro, "já cheguei" | médio | — | **forte** |
| Lembrete de pagamento ("o seu pedido ainda está reservado") | — | **forte** | — |

Decide pelo **fim** das conversas que correram bem (última coluna da tabela dos agentes). O quiz e os
sinais desempatam. Se as conversas acabam de formas diferentes, regista a proporção e escolhe o agente
do caso dominante.

## Cruzar com a configuração

Lê do snapshot `template_key` e `agent_mode` e vê se a combinação corresponde a um preset (lógica de
`getActivePreset`). Se não corresponder a nenhum, é uma **combinação personalizada**: regista-a, porque
o comportamento deixa de ser o descrito na página. Lê também `presentation_variant`,
`appointment_mode`, `identity_mode` (Assistente Virtual / Humano do Time / Clone),
`qualification_required_fields` e as fases do `sales_flow` que têm blocos.

| Situação | Consequência (dizer assim ao utilizador) | Recomendação |
|---|---|---|
| Processo e preset batem certo | — | segue para a skill do agente |
| Processo do Agente 03, configurado como 02 | o agente tenta vender por link e nunca marca a sessão | mudar para o preset do Agente 03 |
| Processo do Agente 02, configurado como 01 ou 03 | os presets 01/03 desligam o fecho pelo bot (o fecho é do humano), por isso o link nunca sai | mudar para o preset do Agente 02 |
| Processo do Agente 01, configurado como 02 | o bot empurra a venda cedo e queima um lead de alto ticket que precisava dos 3 filtros e do humano | mudar para o preset do Agente 01 |
| Processo do Agente 01, configurado como 03 | marca sem os filtros de Poder, Prioridade, Preço e Timing; o vendedor recebe leads por qualificar | mudar para o preset do Agente 01, ou ativar os 4Ps e o score no 03 |
| Combinação personalizada | comportamento fora da página | explicar o que cada campo muda e propor o preset mais próximo |
| Blocos em fases que o agente não usa | configuração morta, que nunca é avaliada | registar |

Mudar de agente é uma decisão grande, porque muda as etapas e os campos obrigatórios. Explica-a com a
evidência e pede o "sim".

## Saída (no README da bancada)

```
## Agente identificado
- Processo real: Agente 0X — <nome da página> (<n> de <m> conversas); origem: inbound <n> / outbound <m>
- Evidência: <conversa A termina em "...">; quiz: ticket <...>, quem fecha <...>, negócio <...>
- Configurado: template_key=<...>, agent_mode=<...> → <preset Agente 0X | combinação personalizada>
- Bate certo? <sim | não — consequência em linguagem simples>
- Skill do agente usada: agente-0X-...
```
