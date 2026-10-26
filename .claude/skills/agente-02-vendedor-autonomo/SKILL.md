---
name: agente-02-vendedor-autonomo
description: Especialista no Agente 02 · Direto — Vendedor Autônomo (Low Ticket) do Orion CRM (preset template_key=closer_agressivo, agent_mode=direto). Traz as etapas da página Tipos de Agentes (Entrada / Qualificação de Fit em 1–2 perguntas, Abordagem e Confirmação da Dor no outbound, Pitch, Oferta + Link de Pagamento, Follow-up de Carrinho Abandonado 2h/24h/48h, Confirmação + Upsell + Onboarding), os critérios de sucesso, a biblioteca de cenários, os campos que pesam e o que a página promete face ao que o código faz. Normalmente acionada pela skill diagnosticar-agente quando o processo do cliente é de venda 100% pelo bot (infoprodutos, e-commerce, cursos, assinaturas, low ticket); use também quando o utilizador pedir diretamente para diagnosticar ou testar o pitch, o link de pagamento, as objeções ou o carrinho abandonado do Agente 02 de uma conta.
---

# Agente 02 · Direto — Vendedor Autônomo

Faz parte do fluxo da skill `diagnosticar-agente`: as regras fixas, a bancada, a triagem e as entregas
estão lá. Os nomes das etapas são os da página Tipos de Agentes (`/agentes-info`).

**Promessa da página:** 100% automatizado, qualifica, apresenta e fecha sem intervenção humana. O
inbound e o outbound só diferem na velocidade da qualificação e no tom da abordagem.

## Etapas da página → o que o sistema faz → o que medir

| Etapa (página) | Quem | No sistema | Critério de sucesso (⚠ = crítico) |
|---|---|---|---|
| **Inbound:** Entrada — Dor Implícita no Clique | bot | p0; `origin_inbound_opener` | boas-vindas curta, com referência ao que o lead clicou |
| **Inbound:** Qualificação de Fit — 1 a 2 Perguntas | bot | p1; padrão `service_interest` + `price_acceptance` | no máximo 2 perguntas; ⚠ quem já quer comprar não é travado pela qualificação |
| **Outbound:** Abordagem com Foco na Dor | bot | `origin_outbound_opener` | abre pelo problema antes do produto |
| **Outbound:** Confirma a Dor — 1 Pergunta | bot | p1 | uma única pergunta; "não" → encerra ou nurture |
| **Pitch — Apresentação pelo Bot** | bot | p2, `presentation_variant=sales`, `offer_pack`, blocos `midia` do Fluxo de Venda, Base de Conhecimento (FAQ de objeções) | solução → 3 benefícios → prova social → oferta; responde às objeções com os factos da conta; no outbound espelha a dor confirmada |
| **Oferta + Link de Pagamento** | bot | p5 (blocos `orientacao` chegam aqui); `signals_structured.checkout_sent`; `anchor_price`; `guarantee_text` | ⚠ o link enviado é o **URL real** da conta; ⚠ preço, âncora e garantia iguais aos da conta, sem descontos inventados; não pede licença e envia no mesmo turno |
| **Follow-up de Carrinho Abandonado** | bot | `start_cart_recovery_followup()`: 2h / 24h / 48h, máx. 3 | 3 mensagens com abordagens diferentes; ⚠ para quando o pagamento entra |
| **Confirmação + Upsell + Onboarding** | bot | webhook de pagamento → `client-list` + boas-vindas | confirmação e entrega; depois de "já paguei", não volta a vender |

## Biblioteca de cenários (adaptar à conta)

| Cenário | Persona | Esperado |
|---|---|---|
| `p-<real>` | uma por conversa de referência | o roteiro observado |
| `p-compra-rapida` | "quero comprar, como pago?" na 1.ª mensagem | link logo, com qualificação mínima |
| `p-objecao-preco` | acha caro e pede desconto | âncora, garantia ou parcelas da conta; nada inventado |
| `p-objecao-confianca` | "é seguro?", "tem garantia?" | factos da conta e depois volta à oferta |
| `p-vou-pensar` | indeciso | resposta de indecisão; o carrinho abandonado começa depois do link |
| `p-duvida-produto` | pergunta técnica a meio da oferta | responde pela Base de Conhecimento e retoma |
| `p-pagou` | "já paguei" | não reenvia a oferta |
| `p-recusa` | "não tenho interesse" | encerra com educação |
| `p-out-dor` | outbound, confirma a dor | pitch espelha a dor |
| `p-out-sem-dor` | outbound, "não é o meu caso" | encerra ou nurture |

Para testar o carrinho abandonado: envia o link e avança o tempo com
`POST /api/playground/leads/{lead_id}/skip-wait`. O `--resumo` conta os links por conversa.

## Campos que mais pesam

`offer_pack` (produtos, preços, `anchor_price`, `guarantee_text`, links) · blocos `midia` e
`orientacao` em p2 e p5 · `qualification_required_fields` (campos a mais travam a venda) ·
`buying_signal_keywords` · `payment_gateway` / webhook de pagamento ·
`origin_inbound_opener` / `origin_outbound_opener` · `handoff_policy` · `identity_mode`.

## Prometido na página vs. código (confirmar antes de concluir)

| Promessa | Estado conhecido |
|---|---|
| Carrinho abandonado 2h / 24h / 48h | ✅ `followup_state.start_cart_recovery_followup` (estratégia hardcoded em `ai_playbooks`) |
| Link de pagamento com o URL real | ⚠️ "`checkout_sent` com URL" está só no prompt, sem validação em código (`docs/plans/motor-llm-otimizacoes.md` M5) |
| Pagamento confirmado → cliente | ✅ webhook move o lead para `client-list`; ⚠️ a Mãe não consegue emitir `client-list` (`fluxo-vendas-melhorias-futuras.md` M11) |
| Integração Hotmart, Stripe, PagSeguro | ❓ confirmar os gateways suportados em `routes/webhooks.py` |
| Upsell imediato, NPS em 7 dias, entrega automática | ❓ não encontrado no código |
| Sem resposta → reativação em 30 dias | ❓ confirmar |
| Filha de fecho especializada | ⚠️ closing usa o prompt genérico `_build_child_prompt` |

Uma promessa da página que o código não cumpre é um **achado de produto**. Vai para `docs/discovery/`
ou plans; não se compensa com configuração.

## Exemplo trabalhado

Ainda não há nenhum. Quando o primeiro diagnóstico do Agente 02 terminar, regista aqui a pasta da
bancada.
