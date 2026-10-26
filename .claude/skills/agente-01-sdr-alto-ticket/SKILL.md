---
name: agente-01-sdr-alto-ticket
description: Especialista no Agente 01 · Robusto — SDR de Alto Ticket (+ Follow-up Pós-Apresentação) do Orion CRM (preset template_key=sdr_padrao, agent_mode=sdr_scheduler). Traz as etapas da página Tipos de Agentes (Filtro 1 Fit, Filtro 2 Dor, Filtro 3 4Ps Poder/Prioridade/Preço/Timing, Agendamento + Handoff com dossiê, Follow-up por temperatura), os critérios de sucesso, a biblioteca de cenários inbound/outbound, os campos que pesam e o que a página promete face ao que o código faz. Normalmente acionada pela skill diagnosticar-agente quando o processo do cliente é de alto ticket (imóveis, advocacia, clínicas, consultorias B2B, ciclo longo, o humano fecha); use também quando o utilizador pedir diretamente para diagnosticar ou testar a qualificação, o score, o agendamento com o vendedor, o dossiê ou o follow-up pós-apresentação do Agente 01 de uma conta.
---

# Agente 01 · Robusto — SDR de Alto Ticket

Faz parte do fluxo da skill `diagnosticar-agente`: as regras fixas, a bancada, a triagem e as entregas
estão lá. Os nomes das etapas são os da página Tipos de Agentes (`/agentes-info`, código em
`frontend-crm/src/pages/TiposAgentes.tsx`). Usa-os assim no README, nos relatórios e nos itens de plans.

**Promessa da página:** qualifica a fundo antes de acionar o humano. A jornada difere conforme a origem
do lead (inbound entra pela dor declarada, outbound pelo perfil presumido) e, a partir do Filtro 3, o
caminho é o mesmo.

## Etapas da página → o que o sistema faz → o que medir

| Etapa (página) | Quem | No sistema | Critério de sucesso (⚠ = crítico) |
|---|---|---|---|
| **Inbound:** Entrada do Lead — Dor Declarada | bot | p0; `origin_inbound_opener`; tom de `tone_of_voice` | boas-vindas em tom consultivo; usa a dor já dita (formulário ou 1.ª mensagem) sem voltar a perguntar |
| **Inbound:** Filtro 1 — Validação de Fit | bot | p1, `qualification_fields` (`question`, `qualify_if`, `disqualify_if`) | 2–3 perguntas de perfil; ⚠ sem fit, encerra com educação ou manda para nurture, sem insistir |
| **Outbound:** Prospecção Ativa — Fit Presumido | bot | `origin_outbound_opener`; leads com `origin=outbound` | abordagem com os dados do lead (setor, cargo, empresa) |
| **Outbound:** Filtro 2 — Investigação de Dor | bot | p1 (perguntas abertas) | perguntas de escavação; se a dor não bate certo com a oferta, encerra |
| **Outbound:** Filtro 1 — Reforço de Fit | bot | p1 | confirma o fit de forma natural; descarte tardio de quem falha |
| **Filtro 3 — Poder, Prioridade, Preço, Timing** | bot | campos dos 4Ps (no código: `decision_role`, `urgency`, `budget_or_price_acceptance`, `availability_window`) + `qualification_score_threshold` | uma pergunta por turno; ⚠ não volta a perguntar o que já foi dito; abaixo do score vai para nurture e acima avança para o agendamento (`qualification_advance_blocked` no trace) |
| **Agendamento + Handoff para Humano** | bot + humano | p3a/p3b; Google Calendar; dossiê (`briefing_service.py`, `briefing_enabled`); lembretes 24h e 1h (padrão do template) | ⚠ reunião gravada no dia e na hora aceites; dossiê com nome, empresa, dor, 4Ps e canal |
| **Apresentação Comercial** | humano | bot pausado depois da marcação; temperatura registada no `FollowUpTransitionModal` | ⚠ o bot não intervém durante a fase humana |
| **Follow-up Pós-Apresentação por Temperatura** | bot | `followup_state.py` (Quente / Morno / Frio / Perdido), `buying_signal_keywords` | cadência e tom de cada temperatura; sinal de compra notifica o vendedor; no outbound frio reconecta com a dor despertada |
| **Fechamento** | humano | closing desativado para o bot em `sdr_padrao` | ⚠ o bot não tenta fechar |
| **Pós-Venda / Onboarding** | bot + humano | webhook de pagamento → `client-list` + boas-vindas | boas-vindas personalizada |

## Biblioteca de cenários (adaptar à conta)

| Cenário | Persona | Esperado |
|---|---|---|
| `p-<real>` | uma por conversa de referência | o roteiro observado |
| `p-in-fit-ok` | inbound, com perfil certo, responde a tudo | F1 → F3 → reunião + dossiê |
| `p-in-sem-fit` | inbound, porte ou setor fora | encerra com educação ou vai para nurture |
| `p-tudo-de-uma-vez` | dá setor, verba, prazo e quem decide na 1.ª mensagem | não volta a perguntar; avança |
| `p-preco-cedo` | "quanto custa?" antes do F3 | resposta da conta (faixa / "depende") e continua sem entrar em loop |
| `p-nao-decide` | "tenho de falar com o meu sócio" | trata o Poder; propõe a reunião com quem decide |
| `p-score-baixo` | sem verba nem prazo | nurture, sem agendar |
| `p-out-frio` | outbound, desconfiado | F2 desperta a dor sem vender; descarta se não houver dor |
| `p-agenda` | aprovado, pede horário específico | gravado no horário aceite (usar `--resumo`) |
| `p-quer-humano` | "quero falar com uma pessoa" | handoff conforme `handoff_policy` |

O follow-up por temperatura testa-se no Playground, avançando o tempo com `POST /api/playground/leads/{lead_id}/skip-wait`.

## Campos que mais pesam

`qualification_fields` (os 3 filtros) · `qualification_required_fields` · `qualification_score_threshold` ·
`qualification_extraction_tolerance` · `response_style` + bloco `qual_opener` em p1 ·
`origin_inbound_opener` / `origin_outbound_opener` · `briefing_enabled` · `appointment_reminder_offsets` ·
`scheduling_offer_style` · `followup_cadence` · `buying_signal_keywords` · `handoff_policy` · `identity_mode`.

## Prometido na página vs. código (confirmar antes de concluir)

| Promessa | Estado conhecido |
|---|---|
| Lembretes 24h e 1h | ✅ padrão de `sdr_padrao` (`jobs_service._REMINDER_DEFAULTS_FALLBACK`) |
| Dossiê automático com os 4Ps | ✅ `briefing_service.py` |
| Score de fit / 4Ps | ⚠️ o score só pontua as 4 chaves clássicas; os campos personalizados não contam (`docs/plans/qualificacao-score-generalizado-melhorias-futuras.md`) |
| Sequência multicanal WhatsApp → e-mail → LinkedIn | ❓ não confirmado no código |
| Calendly | ❌ sem código no backend (só Google Calendar) |
| NPS automático, formulário de onboarding | ❓ não encontrado no código |
| Reativação de "Perdido" em 30–60 dias | ❓ confirmar em `followup_state.py` |

Uma promessa da página que o código não cumpre é um **achado de produto**. Regista-a como item de
`docs/discovery/` (se não se sabe se vale construir) ou de plans. Não tentes compensá-la com
configuração.

## Exemplo trabalhado

Ainda não há nenhum. Quando o primeiro diagnóstico do Agente 01 terminar, regista aqui a pasta da
bancada.
