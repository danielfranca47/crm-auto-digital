# Agente 02 · Direto — Vendedor Autônomo

> Nome e etapas: página **Tipos de Agentes** (`/agentes-info`, `frontend-crm/src/pages/TiposAgentes.tsx`).
> Preset: `AGENT_PRESETS.a2` em `frontend-crm/src/types/agente.ts`.
> Prompts das LLMs: [`docs/prompts_llms.md`](../../prompts_llms.md). Fases comuns:
> [`pipeline-phases.md`](../pipeline-phases.md) e [`sales-flow.md`](../sales-flow.md).

**Para quem (página):** infoprodutos, e-commerce, pedidos de lojas físicas, cursos e assinaturas — low
ticket. 100% automatizado: qualifica, apresenta e fecha sem humano.

---

## Configuração

| Campo | Valor do preset | Efeito |
|---|---|---|
| `template_key` | `closer_agressivo` | `agent_type` = `agent_2` (`agent_type.py::map_template_key_to_agent_type`: qualquer `closer*`) |
| `agent_mode` | `direto` (`closer` também normaliza para `direto`) | fases p0 → p1 → p2 → p5 — sem pré-agendamento, agendamento nem follow-up p4 |
| `presentation_variant` | `sales`, sempre | forçado pelo backend-core em `_upsert_ai_profile` para `direto`/`closer` ([`agents.md`](../agents.md), invariante) |
| `qualification_required_fields` | sugestão ao criar: `service_interest`, `price_acceptance` | editável; vazio = nenhum obrigatório |

---

## Etapas da página → o que o sistema faz

| Etapa (página) | Quem | No sistema |
|---|---|---|
| Inbound: Entrada — Dor Implícita no Clique | bot | p0; `origin_inbound_opener` |
| Inbound: Qualificação de Fit — 1 a 2 Perguntas | bot | p1; campos obrigatórios do perfil |
| Outbound: Abordagem com Foco na Dor | bot | `origin_outbound_opener`; `leads.origin = "outbound"` |
| Outbound: Confirma a Dor — 1 Pergunta | bot | p1 |
| Pitch — Apresentação pelo Bot | bot | p2, Filha de apresentação com variante `sales`; `offer_pack` (`_build_offer_pack_summary`, `anchor_price`, `guarantee_text`); mídias por blocos `midia` do Fluxo de Venda e da Base de Conhecimento (categorias como `pitch_script`, `social_proof`, `commercial_objections`, `guarantee_policy`) |
| Oferta + Link de Pagamento | bot | p5, Filha de closing (`_build_child_prompt_closing`) + blocos `orientacao` de p5; sinal `signals_structured.checkout_sent` |
| Follow-up de Carrinho Abandonado | bot | `followup_state.start_cart_recovery_followup`: 2h / 24h / 48h, máx. 3, variante `cart_recovery` |
| Confirmação + Upsell + Onboarding | bot | webhook `POST /webhooks/payment/{gateway}` → lead em `client-list` + boas-vindas |

---

## Comportamento próprio deste agente

- **Só avança para closing com preço e intenção.** `_apply_mode_guardrails` (modo `direto`): sem
  `price_acceptance` = sim **e** `intent_level` médio/alto, closing volta a `qualification`
  (`guardrail_direto_pullback`).
- **Um turno, uma ação** (prompt de apresentação `sales`): ou CONFIRMAR (sem link, `checkout_sent=false`)
  ou ENVIAR LINK (com link, `checkout_sent=true`, sem pedir licença no mesmo turno).
- **O bot continua ativo em closing.** `lead_category_policy.apply_closing_bot_disable_side_effect` só
  desliga o bot com reunião marcada, modo `agenda` ou `outcome="won"`; para `direto`/`sales`, não.
- **Arranque do carrinho abandonado:** em `routes/executor.py`, quando o bot envia uma mensagem que contém
  `http` a um lead `agent_2` sem follow-up ativo. É o texto da mensagem que dispara, não o sinal
  `checkout_sent`: qualquer link (por exemplo, o site da loja) arranca a recuperação.
- **Sem follow-up por inatividade:** `agent_2` não é elegível (`resolve_auto_inactivity_variant` só
  mapeia `agent_1` e `agent_3`). Nem há variante de follow-up manual para `agent_2` em `routes/leads.py`.
- **Gateways de pagamento reconhecidos:** `hotmart`, `kiwify`, `stripe` (`webhooks._normalize_payment_payload`).

---

## Prometido na página vs. código

| Promessa | Estado |
|---|---|
| Qualificação de fit em 1–2 perguntas | ✅ depende dos campos obrigatórios configurados |
| Pitch com prova social, FAQ de objeções, mídia | ✅ via Base de Conhecimento e Fluxo de Venda |
| Preço âncora e garantia | ✅ `anchor_price`, `guarantee_text` |
| Link de pagamento | ⚠️ a regra "URL real" está só no prompt, e os prompts contradizem-se: o bloco de validação exige URL real, a apresentação aceita "real ou placeholder" (`decision_engine.py`); sem validação em código (`docs/plans/motor-llm-otimizacoes.md` M5) |
| Integração Hotmart, Stripe, PagSeguro | ⚠️ Hotmart e Stripe sim, Kiwify também; PagSeguro não |
| Carrinho abandonado 2h / 24h / 48h | ✅ (arranque por "http" na mensagem, ver acima) |
| Sem resposta → reativação em 30 dias | ❓ não encontrado |
| Upsell imediato, NPS em 7 dias, entrega automática | ❓ não encontrado (só boas-vindas do webhook de pagamento) |
| Pagamento confirmado move o lead | ✅ webhook → `client-list`; a Mãe não consegue emitir `client-list` como rota (`docs/plans/fluxo-vendas-melhorias-futuras.md` M11) |

---

## Ficheiros críticos

`backend-executors/app/services/decision_engine.py` (`_apply_mode_guardrails`, Filha de apresentação
`sales`, `_build_child_prompt_closing`, `_build_validation_block`) · `backend-crm/routes/executor.py`
(arranque do carrinho abandonado) · `backend-crm/services/followup_state.py` ·
`backend-crm/routes/webhooks.py` (pagamento) · `backend-crm/services/lead_category_policy.py` ·
`backend-crm/services/ai_playbooks/__init__.py` (estratégia de recuperação).
