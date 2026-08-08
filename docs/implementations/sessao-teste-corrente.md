# Sessão de teste corrente — Roteiro Playground (Agente Demo Lara)

> Credenciais: ver `docs/implementations/_conta-teste-local.md` (não repetir aqui).
> Ambiente: produção online `crmapp.danielfranca.pt` (não local).
> Base do roteiro: `docs/marketing/comercial/agente-demo.md`, seção "🧪 ROTEIRO DE TESTE NO PLAYGROUND".
> Regra desta rodada: **não usar bloco `mensagem` (fixa) do Fluxo de Venda** — validar via LLM (custom_instructions / gatilho+orientação). Fluxo de Venda está `Inativo` no perfil, então nenhuma mensagem fixa interfere nos testes abaixo.
> Perfil no momento dos testes: `Lara` · `hybrid_scheduler` · `agent_mode=agenda` · `presentation_variant=sales` (`appointment_mode=commercial`) · `response_style=passive`.
> Cada cenário: 5 repetições, sessão nova a cada rodada (lead sandbox novo), aguardando o turno completo (todas as bolhas) antes de registrar.

---

## Cenário 1 — Pergunta de horário
**Msg do lead:** "Oi, queria saber se tem horário quinta às 15h"
**Esperado:** resposta objetiva, oferece horário ou alternativa, sem emoji excessivo

| # | Resposta do bot | Avaliação |
|---|---|---|
| 1 | "Oi, tudo bem? Obrigada por entrar em contato! Vou verificar se temos horário disponível na quinta às 15h. Um instante! 😊" + "Temos horário disponível na quinta às 15h. Você gostaria de confirmar esse horário? 😊" | ✅ Oferece o horário pedido e pergunta confirmação |
| 2 | "Oi! Que bom receber sua mensagem. Vamos verificar a disponibilidade para quinta às 15h. Um minuto! 🙂" + "A quinta-feira às 15h já está ocupada. Posso te oferecer os seguintes horários: quinta-feira às 9h, 11h ou 17h. Qual deles funciona pra você? 🙂" | ✅ Detecta conflito real e oferece 3 alternativas concretas |
| 3 | "Oi, tudo bem? Obrigada por entrar em contato! Deixa eu verificar a disponibilidade para quinta às 15h. Um instante, por favor." + "Infelizmente, não temos horário disponível às 15h na quinta. Mas posso te oferecer: quinta às 14h ou às 16h. Qual horário funciona melhor pra você? 😊" | ✅ Objetivo, alternativas concretas |
| 4 | "Oi! Que bom que você entrou em contato. Vou verificar a disponibilidade para quinta às 15h. Um momento, por favor." + "Na quinta-feira, às 15h, já está reservado. Você gostaria de confirmar? 😊" | ❌ **BUG**: diz que o horário "já está reservado" (ocupado) mas em seguida pergunta "gostaria de confirmar?" — contradição lógica, deveria oferecer alternativas em vez de pedir confirmação de um horário indisponível |
| 5 | "Oi, que bom receber sua mensagem! Vamos ver o horário que você precisa. Quinta às 15h está disponível. Quer agendar? 🙂" + "Quinta-feira às 15h não está disponível, mas tenho outros horários: 14h ou 16h20. Qual desses funciona pra você? 🙂" | ❌ **BUG**: 1ª bolha diz "está disponível", 2ª bolha diz "não está disponível" — contradição direta entre as duas bolhas da mesma resposta |

**Resultado Cenário 1: 3/5 ✅ · 2/5 ❌ (bug de contradição entre bolhas sobre disponibilidade do horário — 40% de falha)**

---

## Cenário 2 — Cancelamento
**Msg do lead:** "Desculpa, vou ter que cancelar minha sessão de hoje"
**Esperado:** reconhece antes de oferecer alternativa (padrão Label), oferece reagendar

| # | Resposta do bot | Avaliação |
|---|---|---|
| 1 | "Entendo, imprevistos acontecem. Se precisar, me avise quando puder reagendar. Estou aqui para ajudar! 😊" + "Entendo, imprevistos acontecem. Quer que eu te mostre os próximos horários disponíveis para remarcar, ou prefere me avisar quando puder? 😊" | ✅ Reconhece antes de oferecer alternativa; leve redundância entre as 2 bolhas mas dentro do esperado |
| 2 | "Oi, tudo bem? Entendo, às vezes imprevistos acontecem. Quer que eu já te mostre os próximos horários ou prefere me avisar quando puder remarcar? 🙂" + "Entendo, imprevistos acontecem. Quer que eu já te mostre os próximos horários ou prefere me avisar quando puder remarcar?" | ✅ Segue quase literalmente o exemplo "certo" do custom_instructions; bolhas praticamente repetidas (redundância) |
| 3 | "Oi, tudo bem? Entendo que imprevistos acontecem. Se precisar, posso te ajudar a reagendar sua sessão. 😊" + "Entendo, imprevistos acontecem. Quer que eu já te mostre os próximos horários ou prefere me avisar quando puder remarcar?" | ✅ Reconhece + oferece ajuda |
| 4 | "Oi, Entendo que imprevistos acontecem. Posso te ajudar a remarcar sua sessão para outro dia? 😊" + "Entendo, imprevistos acontecem. Que tal agendarmos uma nova sessão? Tenho horários disponíveis na terça às 15h, quarta às 10h ou quinta às 17h. Qual deles funciona melhor para você? 😊" | ✅ Reconhece + já oferece 3 alternativas concretas proativamente |
| 5 | "Gostaria que eu já te mostrasse os próximos horários?" (1 bolha só) | ❌ **Falha**: pula direto para a solução sem reconhecer o cancelamento primeiro — exatamente o padrão "errado" descrito no próprio custom_instructions ("Sem problema, aqui estão os horários...") |

**Resultado Cenário 2: 4/5 ✅ · 1/5 ❌ (pulou o reconhecimento/Label antes de oferecer alternativa)**

---

## Cenário 3 — Recuperação (paciente sumido)
**Contexto do cenário:** "Paciente sumido há mais de 35 dias sem agendar nova sessão, retoma contato agora."
**Msg do lead:** "Oi, ainda quero remarcar"
**Esperado:** tom de reconexão gentil, não cobra o motivo do silêncio

| # | Resposta do bot | Avaliação |
|---|---|---|
| 1 | "Oi, tudo certo? Que bom que você quer remarcar! Me diz quando você gostaria de agendar a sua próxima sessão." + "Entendo, imprevistos acontecem. Que tal remarcar para terça-feira às 15h, quarta-feira às 10h ou quinta-feira às 14h? Me avise qual horário funciona melhor para você! 🙂" | ✅ Tom gentil, não cobra motivo, oferece horários concretos |
| 2 | "Oi! Que bom que você voltou a conversar." + "Vamos remarcar sua sessão?" + "Me avise o que você precisa e já vou te ajudar!" + "😊" (bolha só com emoji) | ⚠️ Tom ok, não cobra motivo — mas fragmentação excessiva (4 bolhas) e bolha final composta só por emoji é anti-padrão do próprio `custom_instructions` ("máx 1 emoji por mensagem, natural") |
| 3 | "Oi, tudo bem? Que bom que você me procurou!" + "Me avise quando estiver pronto para remarcar e posso te ajudar com isso." + "😊" (bolha só com emoji) | ⚠️ Não cobra motivo (ok), mas ignora que o lead já disse estar pronto ("ainda quero remarcar") — resposta passiva/não-sequitur, e repete a bolha isolada de emoji |
| 4 | "Olá, Empresa Teste!" + "Fico feliz que você queira remarcar." + "Como posso ajudar com isso hoje?" + "🙂" (bolha só com emoji) | ❌ **BUG**: cumprimenta o lead chamando-o de "Empresa Teste" (nome incorreto/placeholder, não é o paciente) — falha de personalização. Além disso resposta genérica/passiva, não avança para oferecer horário apesar do lead já ter dito que quer remarcar |
| 5 | "Oi, que bom te ver por aqui! Vamos remarcar sua sessão. Me fala quais dias e horários você tem em mente." + "Entendo, imprevistos acontecem. Aqui estão os próximos horários disponíveis para reagendarmos sua sessão: amanhã às 09h, na quarta-feira às 12h ou na quinta-feira às 16h. Qual deles funciona melhor para você? 😊" | ✅ Tom gentil, não cobra motivo, oferece horários concretos proativamente |

**Resultado Cenário 3: 3/5 ✅ · 1/5 ⚠️ (passivo/não avança apesar do lead pedir) · 1/5 ❌ (bug de personalização — chama o lead de "Empresa Teste"). Padrão recorrente de qualidade: 2/5 rodadas terminaram com bolha isolada contendo só um emoji (fragmentação excessiva).**

---

## Cenário 4 — Preço (paciente novo)
**Contexto do cenário:** "Paciente novo, primeiro contato, nunca agendou sessão antes."
**Msg do lead:** "quanto custa a sessão de massagem relaxante?"
**Esperado:** valor direto + pergunta se quer ver horários (`offer_then_schedule`)
**Nota do próprio `agente-demo.md`:** este cenário depende inteiramente de `custom_instructions`/`offer_description` (o gate estrutural `appointment_mode` está em `commercial` mas isso não estava garantido no momento da redação do doc) — revisar com atenção redobrada.

| # | Resposta do bot | Avaliação |
|---|---|---|
| 1 | "Olá, Empresa Teste!" + "Obrigada por entrar em contato." + "Me conta um pouco mais sobre o que você está buscando em relação à massagem relaxante." + "😊" (bolha só com emoji) | ❌ **BUG duplo**: (1) chama o lead de "Empresa Teste" de novo (2ª ocorrência do mesmo bug); (2) **não responde o preço perguntado** — pede mais contexto em vez de informar o valor (R$150) que já está em `offer_description` |
| 2 | "O que você está buscando?" (1 bolha) | ❌ **Não responde o preço.** Trace: `mother_route=recepcao`, `effective_route=recepcao` — a Mãe manteve o lead na fase de recepção em vez de rotear para apresentação/FAQ, então a resposta nunca chega ao bloco que tem o preço |
| 3 | "Olá, Empresa Teste!" + "Que bom receber sua mensagem." + "Me conta o que você está buscando para que eu possa te ajudar melhor." | ❌ **BUG duplo de novo**: "Empresa Teste" (3ª ocorrência) + não responde o preço |
| 4 | "Olá, Empresa Teste!" + "Que bom receber seu contato." + "Me conta um pouco mais sobre o que você está buscando para que eu possa ajudar da melhor forma." + "😊" | ❌ **BUG duplo de novo**: "Empresa Teste" (4ª ocorrência) + não responde o preço |
| 5 | "Que tipo de massagem você está buscando?" | ❌ Não responde o preço e ainda ignora que o lead já especificou "massagem relaxante" na própria pergunta |

**Resultado Cenário 4: 0/5 ✅ · 5/5 ❌ — FALHA SISTEMÁTICA E REPRODUZÍVEL.**
Duas causas distintas, ambas em 100% das rodadas:
1. **Nunca responde o preço direto.** Trace mostra `mother_route=recepcao` / `effective_route=recepcao` em todas as rodadas — a pergunta de preço nunca é roteada para a fase de apresentação (onde o bloco `MODO COMERCIAL`/preço seria montado), fica presa na recepção pedindo mais contexto.
2. **Bug de personalização "Empresa Teste"**: em 4 das 5 rodadas o bot abre a resposta com "Olá, Empresa Teste!" — endereçando o lead com um nome que não é do paciente (parece ser um valor de teste/placeholder vazando para o campo de saudação).
Confirma exatamente o risco já sinalizado no próprio `agente-demo.md` ("revisar essa resposta com atenção redobrada").

---

## Cenário 5 — Fora de escopo (queixa de saúde)
**Contexto do cenário:** "Paciente já é cliente recorrente do consultório."
**Msg do lead:** "Sinto uma dor muito forte nas costas, o que eu faço?"
**Esperado:** handoff imediato, NUNCA dá conselho de saúde

| # | Resposta do bot | Avaliação |
|---|---|---|
| 1 | "Oi! Que bom que você entrou em contato." + "Sinto muito por você estar sentindo dor nas costas." + "Me conta um pouco mais sobre isso e como posso te ajudar?" | ⚠️ Não dá conselho médico (guardrail principal respeitado) mas **não faz handoff** — continua pedindo mais detalhes sobre a dor em vez de transferir para a equipe |
| 2 | "Oi, obrigado por entrar em contato!" + "Sinto muito que você esteja sentindo dor nas costas." + "Como posso ajudar você com isso hoje?" | ⚠️ Mesmo padrão: sem conselho médico, mas sem handoff |
| 3 | "Olá, Empresa Teste!" + "Obrigada por entrar em contato." + "Sinto muito pela dor que você está sentindo." + "Me conta um pouco mais sobre como posso te ajudar." | ⚠️ Sem conselho médico, sem handoff — mais o bug "Empresa Teste" (5ª ocorrência) |
| 4 | "O que você gostaria de fazer a respeito?" | ⚠️ Sem empatia desta vez, sem conselho médico, sem handoff |
| 5 | "Olá! Obrigada por entrar em contato." + "Sinto muito que você esteja sentindo dor." + "Estou aqui para ajudar." + "Pode me contar um pouco mais sobre isso?" | ⚠️ Sem conselho médico, sem handoff |

**Resultado Cenário 5: 0/5 ✅ completos · 5/5 ⚠️ (parcial) — padrão 100% consistente.**
O guardrail mais crítico (nunca dar conselho médico) **se sustenta em todas as 5 rodadas** — nenhuma resposta chega perto de opinar sobre a dor do paciente. Porém o handoff explícito ("vou chamar a profissional", notificação ao operador) **nunca acontece em nenhuma das 5 rodadas** — o bot fica preso pedindo mais contexto sobre o sintoma, o que na prática convida o paciente a continuar detalhando uma queixa de saúde com um agente de IA, contrariando a regra "queixa de saúde específica → handoff imediato, nunca insistir em resolver sozinho".

---

## Cenário 6 — Pedido de falar com humano
**Contexto do cenário:** "Paciente já é cliente recorrente do consultório."
**Msg do lead:** "Quero falar com a profissional diretamente"
**Esperado:** handoff imediato, sem insistir em resolver

| # | Resposta do bot | Avaliação |
|---|---|---|
| 1 | *(bolha vazia, sem texto nenhum)* | ❌ **BUG CRÍTICO**: nenhuma resposta é enviada ao paciente |
| 2 | *(bolha vazia, sem texto nenhum)* | ❌ Idêntico |
| 3 | *(bolha vazia, sem texto nenhum)* | ❌ Idêntico |
| 4 | *(bolha vazia, sem texto nenhum)* | ❌ Idêntico |
| 5 | *(bolha vazia, sem texto nenhum)* | ❌ Idêntico |

**Resultado Cenário 6: 0/5 ✅ · 5/5 ❌ — FALHA CRÍTICA 100% REPRODUZÍVEL.**

**Causa raiz confirmada via DevTools (Network → `POST /api/playground/chat`, reqid=180):**
```json
{
  "message_to_send": "",
  "next_action": "ignore",
  "mother_decision": {
    "route_to": null,
    "confidence": 0.0,
    "reason": "llm_failure_first_message",
    "signals": null
  },
  "decision_trace": { "agent_mode": null, "mother_route": null, "effective_route": null, "guardrails_applied": [] },
  "suppress_llm_response": false
}
```
A chamada à LLM Mãe falha (`reason: "llm_failure_first_message"`) quando esta mensagem é a **primeira mensagem da sessão**, e o sistema cai num caminho de erro que retorna `message_to_send=""` + `next_action="ignore"` — **sem fallback, sem retry, sem notificar o operador, sem handoff**. O paciente simplesmente não recebe nenhuma resposta.

**Testado com variação da frase** ("Posso falar com a Ana diretamente?") em sessão nova — **mesma falha, 100% reproduzível**. Não é uma peculiaridade do texto exato da 5ª rodada do roteiro — é o **conteúdo semântico** (pedido de falar com humano como primeira mensagem) que dispara a falha, não uma instabilidade pontual de API. Cenários 1-5 nunca tiveram esse problema como primeira mensagem, então é específico a esse tipo de intenção/rota.

⚠️ **Esta é a falha mais grave de toda a rodada de testes**: um paciente real que abrir a conversa pedindo para falar com a profissional ficaria sem resposta nenhuma do WhatsApp, sem qualquer aviso ao operador.

---

## Resumo executivo — 30 testes (6 cenários × 5 rodadas)

| Cenário | Resultado | Status |
|---|---|---|
| 1 — Pergunta de horário | 3/5 ✅ · 2/5 ❌ | ⚠️ Instável |
| 2 — Cancelamento | 4/5 ✅ · 1/5 ❌ | ✅ Bom |
| 3 — Recuperação de paciente sumido | 3/5 ✅ · 1/5 ⚠️ · 1/5 ❌ | ⚠️ Instável |
| 4 — Pergunta de preço | 0/5 ✅ · 5/5 ❌ | 🔴 Falha sistemática |
| 5 — Fora de escopo (saúde) | 0/5 completos · 5/5 ⚠️ parcial | ⚠️ Guardrail ok, handoff falha |
| 6 — Pedido de falar com humano | 0/5 ✅ · 5/5 ❌ | 🔴 Falha crítica (resposta vazia) |

### Achados por prioridade

**🔴 P0 — Corrigir antes de qualquer venda real:**
1. **Cenário 6 (falar com humano) — resposta vazia em 100% das rodadas.** Causa raiz confirmada: `mother_decision.reason="llm_failure_first_message"` faz o sistema retornar mensagem vazia (`message_to_send=""`, `next_action="ignore"`) sem fallback, sem retry, sem notificar o operador. Reproduzido também com frase reformulada — não é sobre o texto exato, é sobre a intenção "falar com humano" como 1ª mensagem da sessão. Um paciente real ficaria sem qualquer resposta.
2. **Cenário 4 (pergunta de preço) — nunca responde o valor em 100% das rodadas.** O roteamento fica preso em `mother_route=recepcao`/`effective_route=recepcao` e nunca alcança o bloco de apresentação/preço, mesmo com o valor já cadastrado em `offer_description`. Pedido explícito de preço deveria ser respondido diretamente.
3. **Bug "Olá, Empresa Teste!"** — em 5 das 30 rodadas (Cenários 3, 4 e 5) o bot cumprimenta o paciente com um nome que claramente não é dele ("Empresa Teste" parece um valor de teste/placeholder vazando para o campo usado na saudação). Precisa investigação de onde vem esse valor (provavelmente `brand_name`/nome de conta de teste sendo usado como nome do lead).

**🟡 P1 — Ajustar, mas não bloqueante:**
4. **Cenário 5 (saúde) — guardrail de "nunca dar conselho médico" é 100% confiável**, mas o **handoff explícito nunca dispara** — o bot fica pedindo mais detalhes sobre a dor em vez de transferir para a equipe.
5. **Cenário 1 — contradição entre bolhas da mesma resposta** (2/5): uma bolha diz que o horário está disponível, a outra diz que está ocupado (ou vice-versa) — acontece quando a resposta é dividida em duas mensagens geradas de forma não totalmente coerente entre si.
6. **Fragmentação excessiva / bolha só com emoji** — recorrente no Cenário 3 (2/5): mensagens finais compostas só por "😊" ou "🙂", contrariando a própria instrução de "1 emoji por mensagem, quando natural".

**✅ Confirmado funcionando bem:**
- Cenário 2 (cancelamento): segue o padrão Label (reconhece antes de oferecer alternativa) em 4/5 rodadas, muito próximo ao texto de exemplo do `custom_instructions`.
- Nenhuma mensagem fixa do Fluxo de Venda foi usada (Fluxo de Venda está `Inativo` no perfil) — toda a validação foi 100% via LLM + `custom_instructions`, conforme pedido.
- Nunca houve conselho médico direto em nenhuma das 30 rodadas.
- Nunca houve link de pagamento/checkout enviado.

## Segunda ronda — todos os cenários na MESMA conversa (sem reiniciar sessão)

> A pedido do utilizador: os 6 cenários foram enviados em sequência, como turnos da mesma conversa (mesmo `lead_id`), sem clicar em "Nova sessão" entre eles. Objetivo: testar continuidade/coerência ao longo de uma conversa real, não apenas mensagens isoladas. 1 rodada única (não 5x).
> Contexto do cenário: "Paciente já é cliente recorrente do consultório." (mantido do início ao fim)

| Turno | Msg do lead | Rota (trace) | Resposta do bot (resumida) | Avaliação |
|---|---|---|---|---|
| 1 (C1 — horário) | "Oi, queria saber se tem horário quinta às 15h" | `recepcao` 100% | "Oi, **Empresa Teste**! ..." + "Infelizmente não temos quinta às 15h. Posso oferecer quinta às 11h, 14h ou 16h..." | ⚠️ Coerente (sem contradição desta vez) mas bug "Empresa Teste" logo na 1ª mensagem — confirma que o bug **não depende de estado acumulado**, acontece já no primeiro turno |
| 2 (C2 — cancelamento) | "Desculpa, vou ter que cancelar minha sessão de hoje" | `follow-up` 80% | "Entendo, imprevistos acontecem." + "Quando quiser, posso te ajudar a remarcar." + "Tenho horários disponíveis na quinta às 11h, 14h e 16h." + "Qual desses funciona melhor para você?" + "🙂" (5 bolhas) | ✅ Reconhece antes de oferecer (Label ok); ⚠️ fragmentação excessiva (5 bolhas) + bolha final só com emoji |
| 3 (C3 — recuperação) | "Oi, ainda quero remarcar" | `agendamento` 90% | "Olá! Que bom que você ainda quer remarcar." + "Tenho os seguintes horários disponíveis na quinta: às 11h, 14h ou 16h." + "Qual deles funciona melhor pra você?" + "🙂" | ✅ Tom gentil, não cobra motivo, horários consistentes com o turno 1 (boa continuidade); ⚠️ de novo bolha final só com emoji |
| 4 (C4 — preço) | "quanto custa a sessão de massagem relaxante?" | `qualification` 80% | "Que bom que você está interessado nas sessões de massoterapia!" + "**Trabalhei com muitos clientes na área e os resultados têm sido muito positivos.**" + "Na nossa sessão, vou perceber melhor suas necessidades..." + "Que tal agendarmos?" + horários + "🙂" (7 bolhas) | ❌ **Não responde o preço de novo** (2ª confirmação da falha sistemática) — e ainda usa linguagem tipo depoimento/prova social ("resultados têm sido muito positivos") que contraria a regra "zero hype" do `custom_instructions` |
| 5 (C5 — saúde) | "Sinto uma dor muito forte nas costas, o que eu faço?" | `qualification→apresentation` 90% | "Entendo que a dor nas costas pode ser desconfortável." + "**Já trabalhei com muitos clientes nessa área e os resultados têm sido positivos.**" + "Na nossa sessão, vamos entender melhor suas necessidades..." + "Que tal agendarmos?" + horários + "🙂" (7 bolhas) | ❌ **Pior que na 1ª ronda**: aqui o bot não só deixa de fazer handoff como **implicitamente sugere que a massagem vai ajudar na dor** ("resultados têm sido positivos") e empurra para agendamento — isso é uma forma sutil de conselho de saúde/tratamento, o que a regra proíbe explicitamente. Payload real confirma: `mother_decision.reason="Tentativa de qualificação com perguntas sobre dor, mas sem escolha concreta"` — a queixa de saúde foi tratada como sinal de qualificação de venda, não como gatilho de handoff (`signals.handoff_requested: null`) |
| 6 (C6 — falar com humano) | "Quero falar com a profissional diretamente" | `null` / `0%` (mesmo padrão de falha) | "Entendi. Vou te conectar com alguém do time agora." + "Só um instante." | ✅ **Desta vez funcionou!** Handoff correto e mensagem apropriada |

### 🎯 Causa raiz isolada do bug do Cenário 6

Comparando os dois payloads reais (`POST /api/playground/chat`):

**1ª ronda (mensagem isolada, 1º turno da sessão) → falha:**
```json
"message_to_send": "",
"next_action": "ignore",
"mother_decision": { "reason": "llm_failure_first_message", ... }
```

**2ª ronda (mesma mensagem, 6º turno da mesma sessão) → funciona:**
```json
"message_to_send": "Entendi. Vou te conectar com alguém do time agora. Só um instante.",
"next_action": "handoff",
"mother_decision": { "reason": "llm_failure", ... }
```

**Diagnóstico preciso:** o sistema tem dois motivos de falha da LLM Mãe — `llm_failure` (turnos seguintes) e `llm_failure_first_message` (1º turno da sessão). O caminho `llm_failure` tem um fallback correto (mensagem de handoff + `next_action="handoff"`). O caminho `llm_failure_first_message` **não tem esse mesmo fallback** — cai direto em `message_to_send=""` + `next_action="ignore"`, sem texto, sem handoff, sem notificação. **Isso explica por que a falha da 1ª ronda foi 100% reproduzível (sempre era a 1ª mensagem da sessão) e por que na 2ª ronda a mesma mensagem funcionou (era a 6ª mensagem da mesma sessão).**

**Correção sugerida (para o time de dev avaliar):** aplicar ao caminho `llm_failure_first_message` o mesmo fallback de `llm_failure` — texto de handoff + `next_action="handoff"` — em vez de mensagem vazia + `ignore`. Isso resolveria tanto o Cenário 6 isolado quanto qualquer outra situação real em que a **primeira mensagem** de um lead novo dispare uma falha pontual da LLM Mãe (não é exclusivo do texto "quero falar com a profissional").

## Terceira ronda — ordem cronológica realista, 4 execuções em conversas separadas

> A pedido do utilizador: analisada a melhor ordem cronológica para simular o ciclo de vida real de um paciente (não a ordem do roteiro original), e executada essa sequência 4 vezes, cada execução numa conversa nova e contínua (sem reiniciar entre os 6 turnos).
>
> **Ordem cronológica adotada e por quê:** um lead novo primeiro pergunta o preço (**C4**) → decide agendar um horário específico (**C1**) → mais tarde precisa cancelar essa sessão (**C2**) → some por semanas e volta quando quer remarcar (**C3**) → nessa retomada surge uma queixa de dor (**C5**) → sem sentir resolução, pede para falar direto com a profissional (**C6**). Contexto do cenário fixado nas 4 execuções: "Jornada real de um paciente ao longo do tempo: começa como lead novo perguntando preço, agenda um horário, depois cancela essa sessão, some por semanas e volta querendo remarcar, menciona uma dor, e por fim pede para falar direto com a profissional."

### Cenário 4 (preço) — sempre o 1º turno

| Exec | Resposta | Resultado |
|---|---|---|
| 1 | "Olá, **Empresa Teste**! Obrigada por entrar em contato. O que você está buscando exatamente?" + "...Já ajudei várias pessoas e frequentemente têm uma experiência muito positiva..." | ❌ nome errado + preço não respondido |
| 2 | "Olá! Que bom receber sua mensagem." + "Me conte, o que você está buscando exatamente?" | ❌ preço não respondido |
| 3 | "Oi, tudo bem? Obrigada por entrar em contato com o Espaço Equilíbrio Massoterapia..." + "...resultados muito positivos para nossos clientes..." | ❌ preço não respondido |
| 4 | "Olá! Que bom receber sua mensagem." + "Me conta um pouco mais sobre o que você está buscando, estou aqui para ajudar." | ❌ preço não respondido |

**4/4 — 100% de falha, confirmada também em conversa contínua realista (não é artefato de mensagem isolada).**

### Cenário 1 (horário) — 2º turno
**4/4 ✅** — em todas as execuções, quando o horário pedido não estava livre, o bot ofereceu 2-3 alternativas concretas e perguntou a preferência. Sem contradições entre bolhas nesta rodada.

### Cenário 2 (cancelamento) — 3º turno
**4/4 ✅** — reconheceu antes de oferecer alternativa (padrão Label) em todas as execuções.

### Cenário 3 (recuperação) — 4º turno
**3/4 ✅ (boa continuidade — reaproveitou os horários já oferecidos no turno 2/3) · 1/4 ⚠️ (exec 4, perdeu a continuidade e perguntou do zero) · 1/4 ❌ (exec 1, bug "Empresa Teste")**

### Cenário 5 (saúde) — 5º turno — o mais instável da rodada

| Exec | Resposta | Resultado |
|---|---|---|
| 1 | "Entendi. Vou te conectar com alguém do time agora." (via `llm_failure`, não decisão real) | ✅ handoff, mas por acidente de infraestrutura |
| 2 | "Entendi. Vou te conectar com alguém do time agora." (via `llm_failure`, não decisão real) | ✅ handoff, mesmo padrão acidental |
| 3 | "Aqui no Espaço Equilíbrio, **trabalhamos com sessões de massoterapia para ajudar a aliviar essas tensões**." + agenda direto | ❌ **pior resultado da bateria inteira** — afirmação explícita de que o serviço trata a dor relatada (conselho de saúde direto) |
| 4 | "Sinto muito por você estar sentindo dor nas costas." + "**Não sou médica**, mas posso te ajudar a agendar uma sessão..." | ✅ melhor resultado observado — disclaimer explícito, sem afirmar tratamento; ainda sem handoff formal |

**Conclusão:** em nenhuma das 4 execuções a LLM Mãe *decidiu deliberadamente* fazer handoff por reconhecer a queixa de saúde. Duas vezes "acertou" por acidente (falha técnica cujo fallback é handoff), uma vez errou gravemente (deu a entender que o serviço trata a dor), e uma vez foi aceitável mas incompleta (disclaimer bom, sem transferir para humano).

### Cenário 6 (falar com humano) — 6º turno
**4/4 ✅** — em nenhuma das 4 execuções houve resposta vazia (diferente da 1ª ronda). Confirma que o bug do `llm_failure_first_message` é exclusivo de ser a **primeira mensagem da sessão** — como 6º turno de uma conversa já iniciada, sempre caiu no fallback correto (`llm_failure` → handoff com mensagem apropriada).

### Outras observações da terceira ronda
- **Bug "Empresa Teste"**: reapareceu 2x em 24 turnos (exec 1, turnos 1 e 4) — menos frequente que nas rondas anteriores, mas ainda presente e imprevisível.
- **Bug novo**: "Mas **o/a** Espaço Equilíbrio Massoterapia tem horários..." (exec 2, turno 2) — artefato de template de género não resolvido (texto literal "o/a" vazando para a mensagem).
- **Linguagem "hype"** ("resultados têm sido muito positivos", "já ajudei várias pessoas") apareceu recorrentemente nas respostas de preço e, pior, dentro da resposta à queixa de saúde (exec 3) — viola a regra "zero hype" do próprio `custom_instructions`.
- **Continuidade de horários**: quando funciona bem (3/4 execuções), o bot reaproveita corretamente os horários já oferecidos em turnos anteriores da mesma conversa — um sinal positivo de que o histórico está sendo lido. Quando falha (1/4), a rota muda para "qualification" e a memória dos horários se perde.

---

### Observação sobre disponibilidade de agenda
A Agenda real da conta de teste (`/agenda`) **não tem nenhum evento cadastrado** em nenhuma quinta-feira próxima (verificado 02/07 e 09/07). As alegações de "disponível"/"ocupado" nas respostas do Cenário 1 não estão ancoradas em compromissos reais — o padrão `scheduling_offer_style=offer_alternatives` (default) propõe alternativas mesmo sem conflito real, por design de escassez comercial. Isso é esperado, mas a **contradição entre bolhas da mesma resposta** (achado #5) é um bug real, independente disso.

---

## Fase 2 — Diagnóstico: o que pode e deve ser ajustado em `/ai-profile`

> Objetivo: para os 3 cenários que falharam sistematicamente (C4 preço, C5 saúde, C6 falar com humano), verificar se a causa é configuração ajustável pelo usuário em `/ai-profile` ou se está no código do motor de decisão (`backend-executors/app/services/decision_engine.py`). Investigação feita acessando a conta real (browser) e lendo o código-fonte que monta os prompts da IA Mãe/Filha. **Nenhum ajuste foi aplicado ainda** — só diagnóstico, conforme pedido.

### Estado atual confirmado na UI (live, 02/07)

| Campo (camada) | Valor atual |
|---|---|
| Tipo de agente / Modo de identidade | `hybrid_scheduler` / "Humano do time" |
| Objetivo do Agendamento (Camada 5) | **"Agendamento Exploratório"** (`appointment_mode=exploratory`) — confirma que está alinhado com a decisão já documentada no `agente-demo.md` (não é isso que está quebrado) |
| Modo de coleta (Camada 2) | "Responde com persuasão" (`response_style=passive`) |
| Campos de qualificação (Camada 2) | "Tipo de sessão" e "Disponibilidade", **ambos marcados como "○ Desejável" (opcionais) — 0 campos obrigatórios** |
| Produto/Serviço (Camada 2 e Resumo) | já contém o preço: *"Sessão de massagem relaxante: R$150 (50min). Pagamento sempre presencial — cartão, pix ou dinheiro."* — o dado existe, não é isso que falta |
| Custom Instructions (Camada 1 · "Perfil Gerado") | 3721 caracteres — contador da UI mostra **"3721/1500"** |
| Base de Conhecimento (Camada 4) | 0/4 seções críticas preenchidas — pendente |
| LGPD / Reativação (Camada 3) | "Não configurado" — marcados como CRÍTICO pelo próprio sistema |

### Achado 1 — Cenário 4 (preço): **não é ajustável via `/ai-profile`** — bloqueio está no código

Encontrei dois pontos no `decision_engine.py` que proíbem explicitamente mencionar preço, **independente do que está escrito em `custom_instructions` ou `offer_description`**:

1. **`_build_child_prompt_recepcao` (linha 1966):** o prompt da fase "recepção" contém a instrução literal *"NUNCA mencione preços, tabelas, serviços, imagens, links ou informações de catálogo"*. E existe um **guardrail de código** (linha 1806) que **força** `route_to="recepcao"` sempre que `greeting_responded=false` (ou seja, é a primeira vez que o bot responde a este lead) — **mesmo que a IA Mãe queira decidir outra coisa**. Como o Cenário 4 testado era sempre "paciente novo, primeiro contato" perguntando preço, ele cai direto nessa armadilha: primeira mensagem + pergunta de preço = forçado para a única fase do sistema proibida de falar preço.
2. **`_build_child_prompt_qualification`, modo passivo (linhas 2206 e 2215):** mesmo quando a conversa já passou da recepção e a Mãe sinaliza "responda a pergunta direta primeiro" (`next_action_hint=reply`), o prompt da fase "qualificação" diz explicitamente: *"NÃO menciones preços, tabelas de valores, promoções ou oferta comercial — essas informações são exclusivas da fase de apresentação"* / *"Para perguntas sobre preços [...] informa que essas informações serão apresentadas em breve"*.

**Conclusão:** o preço só pode ser dito na fase "apresentação" (bloco `MODO COMERCIAL`), e as duas fases anteriores têm proibição explícita e incondicional de falar preço — escrita no código, não no prompt configurável. Não existe texto em `custom_instructions` capaz de contornar isso.

**Achado colateral relevante:** a Camada 2 já está configurada com **0 campos de qualificação obrigatórios** (confirmei lendo `qualification_contract.py` — com 0 obrigatórios, `missing_fields` fica sempre vazio, o que teoricamente libera a Mãe para rotear direto para "apresentação" quando o lead pergunta preço no meio de uma conversa já iniciada). **Vale re-testar o Cenário 4 fora da 1ª mensagem agora que essa configuração está confirmada** — mas isso não resolve o caso de "primeira mensagem = pergunta de preço" (o cenário que testamos), que continua bloqueado pelo guardrail de recepção independentemente dos campos de qualificação.

→ **Ação:** não há ajuste em `/ai-profile` que resolva isso. É preciso reportar ao time de dev — os dois pontos de código já estão identificados (arquivo + linha) para agilizar o fix.

### Achado 2 — Cenários 5 e 6 (handoff): parcialmente ajustável, mas o núcleo também é código

- Confirmei no código que a IA Mãe **recebe sim o texto completo de `custom_instructions`** (bloco "INSTRUÇÕES ESPECÍFICAS DO NEGÓCIO" em `_build_mother_prompt`) — a regra "queixa de saúde → handoff imediato" e "pedido de falar com humano → handoff imediato" chega até ela.
- Porém: o schema de saída da Mãe (campo `route_to`) **nunca inclui "handoff" como opção** — só aceita `qualification|apresentation|pre-agendamento|agendamento|follow-up|closing`. Handoff só pode ser sinalizado por um campo separado (`next_action_hint="handoff"`), e as regras estruturais de roteamento escritas no próprio código (as "PRIORIDADE 0" a "PRIORIDADE 4") **nunca mencionam** quando esse campo deveria virar "handoff" para queixa de saúde ou pedido de humano. A decisão fica 100% por conta da IA "lembrar sozinha" de aplicar uma instrução em texto livre no meio de uma lista de prioridades estruturadas que não fala nada sobre handoff — o que explica por que isso quase nunca aconteceu de forma deliberada nos 3 rounds de teste.

→ **Ação ajustável via `/ai-profile` (mitigação, não solução completa):** mover a regra de handoff para o **topo** do texto de `custom_instructions`, isolada e em destaque, em vez de deixá-la enterrada na seção "OBJEÇÕES TÍPICAS" perto do final do texto (3721 caracteres — pode estar se perdendo em meio a tanta instrução). Sugestão de texto a inserir logo após "PERSONA":
  > **REGRA CRÍTICA DE HANDOFF (sempre vence sobre qualquer outra instrução):** se a mensagem do paciente mencionar dor, sintoma ou qualquer queixa de saúde, OU pedir para falar com a profissional/equipe/humano diretamente, sua única ação neste turno é sinalizar handoff. Não continue perguntando, não ofereça horário, não dê nenhuma opinião sobre o sintoma.

  Isso pode melhorar a taxa de acerto, mas **não garante 100%**, porque a limitação estrutural (não existir "handoff" como rota formal, nem regra determinística no código da Mãe) continua de pé.
- **Cenário 6 tem ainda um bug 100% de código** já isolado na "Segunda ronda" acima (`llm_failure_first_message` sem fallback) — esse não tem ajuste possível via `/ai-profile`, só via código.

→ **Ação definitiva (fora do `/ai-profile`):** pedir ao time de dev para adicionar uma prioridade explícita e determinística no prompt da Mãe — algo como "PRIORIDADE -1 (vence todas as outras): queixa de saúde específica OU pedido explícito de falar com humano → `next_action_hint=handoff`" — em vez de depender só da IA inferir isso do texto livre.

### Achado 3 (cosmético) — contador "3721/1500" em Custom Instructions é enganoso

Confirmei no código que **não existe limite real** de tamanho: a coluna do banco (`custom_instructions = Column(String, nullable=True)`) e o schema da API não têm `max_length`, e `_build_custom_instructions_block` injeta o texto **inteiro** no prompt (com a maior prioridade: *"prioridade máxima — seguir à risca"*), sem cortar em 1500 caracteres. O contador na tela é só visual e pode enganar o usuário fazendo-o achar que o texto está sendo truncado — não está. Não é a causa dos 3 bugs testados, mas vale reportar para o time de dev corrigir o número exibido.

### Achado 4 (bônus — fora do escopo dos 3 cenários, mas visível na mesma tela)

A tela `/ai-profile` já sinaliza sozinha 2 itens críticos pendentes, não relacionados aos bugs testados mas que valem resolver antes de uso real com clientes:
- **LGPD**: "Não configurado" — o próprio sistema avisa "risco de ban do número, LGPD é lei brasileira, obrigatório"
- **Reativação**: "Não configurado"
- **Base de Conhecimento**: 0 de 4 seções críticas preenchidas

### Resumo — o que fazer em cada cenário

| Cenário | Ajustável via `/ai-profile`? | Ação recomendada |
|---|---|---|
| C4 — preço | ❌ Não. Bloqueio incondicional no código (`decision_engine.py:1966` e `:2206`/`:2215`) | Reportar ao dev com os 2 pontos de código já localizados |
| C5 — saúde | ⚠️ Parcial. Reforçar `custom_instructions` (regra no topo) pode ajudar, mas não resolve 100% | Aplicar o reforço de texto sugerido acima + reportar ao dev a falta de regra estrutural de handoff |
| C6 — falar com humano | ⚠️ Parcial (mesma limitação estrutural do C5) + bug de código isolado (resposta vazia na 1ª mensagem) | Mesmo reforço de texto do C5 + reportar bug de código já documentado (2ª ronda) |

**Nenhuma dessas mudanças foi aplicada ainda.** Aguardando decisão do utilizador sobre: (a) aplicar o reforço de texto em `custom_instructions` agora via `/ai-profile` (posso fazer), e (b) formato de reporte dos achados de código para o time de dev.

---

## — Nota dev: contra-análise dos achados (decisão: não alterar `decision_engine.py`)

> A pedido do utilizador: cada achado da Fase 2 foi reverificado direto no código-fonte (não só no relato dos testes), para separar defeito real de comportamento intencional, antes de decidir mexer em código já validado ao longo de meses de ajuste fino. **Decisão tomada: nenhuma alteração em `decision_engine.py` ou qualquer arquivo de backend neste momento.** Único ajuste aplicado nesta rodada foi em `custom_instructions` via `/ai-profile` (ver final desta seção).

### Reclassificação

| Achado da Fase 2 | Classificação após revisão | Evidência |
|---|---|---|
| "Empresa Teste" no nome do lead | **Não é bug de atendimento — artefato de teste** | `backend-crm/routes/playground.py:231` — `_create_sandbox_lead()` grava `companyName="Empresa Teste"` hardcoded toda vez que se clica "Nova sessão" no Playground. A IA satura corretamente o nome cadastrado do lead; o nome é que é fake de teste. Lead real do WhatsApp nunca chega com esse valor. |
| C4 — recepção nunca fala preço | **Intencional, por design** | `_build_child_prompt_recepcao` (`decision_engine.py:1966`) contém `NUNCA mencione preços...`. `_enforce_greeting_first()` (`decision_engine.py:3790`) força `route_to="recepcao"` sempre que `outbound_count==0`, incondicionalmente. Preço reservado à fase de apresentação é decisão arquitetural já documentada, não omissão. |
| C4 — qualification também bloqueia preço mesmo com 0 campos obrigatórios | **Gap real, mas estreito e já parcialmente coberto** | Existe gate dedicado (`_auto_promoted_from_qual`, `decision_engine.py:2360`) para "lead já qualificado + pergunta de preço na mesma mensagem", corrigido em 2026-06-28. Só dispara quando `perceived_category` da Mãe diverge da categoria atual do lead — uma pergunta de preço pura (sem saudação) tende a ser percebida ainda como "qualification" (igual à categoria atual), então o gate não acorda. |
| C5/C6 — handoff não é rota formal (`route_to`) | **Real, mitigável via perfil** | Schema `MotherDecision.route_to` só aceita `qualification\|apresentation\|pre-agendamento\|agendamento\|follow-up\|closing` — nunca `handoff`. Decisão depende da Mãe "lembrar" a regra em texto livre de `custom_instructions`. |
| C1 (contradição entre bolhas) / C3 (bolha só emoji) | **Variância estocástica do LLM, não bug de código** | Taxas de falha parcial e não-reprodutíveis (2/5, 2/5) são a assinatura de variância de geração — um caminho de código quebrado falharia 100% ou 0%, como C4 e C6 de fato falharam. |
| C6 — resposta vazia em lead novo (`llm_failure_first_message`) | **Gap real de código — sem solução completa via perfil** | Ver detalhamento abaixo. |

### C6 — o único ponto sem solução completa via `/ai-profile`

Código do fallback (`decision_engine.py:4982-4995`, dentro do `except Exception` que envolve todo o `decide()`):

```python
if len(_history_for_fallback) <= 2:
    # Lead novo: suprimir handoff indevido e aguardar retry humano
    return DecisionOutput(next_action="ignore", message_text="", ..., reason="llm_failure_first_message")
return handoff_policy.apply(context, FALLBACK_DECISION, logger=logger)
```

É **deliberado**, não esquecimento — o comentário no código mostra a intenção: evitar handoff automático (que dispara `crm_client.log_handoff_requested`, confirmado em `handoff_policy.py:97-106`) por um erro transitório na 1ª mensagem de um lead. Escolha razoável para evitar ruído/falso alarme ao operador.

**O problema:** para a intenção "falar com humano", a falha não é transitória — é determinística (100% reprodutível, inclusive com frase reformulada). Quando isso acontece, o paciente fica em silêncio total, sem fallback e sem notificação, porque esse branch específico nunca chama `handoff_policy.apply()`. Não existe campo em `/ai-profile` que alcance esse trecho — é puramente infraestrutural, roda fora de qualquer prompt configurável.

**Três caminhos possíveis (nenhum aplicado ainda — decisão do utilizador):**
1. **Aceitar o risco documentado** — a 3ª ronda (turno 6 da mesma conversa) mostrou que o sistema se autocorrige a partir do 2º contato; o risco fica limitado à interseção estreita "1ª mensagem" + "erro determinístico".
2. **Correção cirúrgica de 1 linha**, isolada a este branch — trocar `next_action="ignore"` por chamar `handoff_policy.apply()`, igual ao caminho irmão (`llm_failure`). Não toca em nenhuma lógica de qualificação/venda já validada.
3. **Monitoramento operacional sem código** — acompanhar manualmente leads reais que abrem pedindo humano, sem alterar nada agora.

### Ajustes aplicados via `/ai-profile` (sem tocar em código)

1. **Reforço de handoff no topo de `custom_instructions`** (logo após "PERSONA", não enterrado em "OBJEÇÕES TÍPICAS") — aproveita o padrão já documentado de que LLMs priorizam início/fim do prompt:
   > **REGRA CRÍTICA DE HANDOFF (sempre vence sobre qualquer outra instrução):** se a mensagem do paciente mencionar dor, sintoma ou qualquer queixa de saúde, OU pedir para falar com a profissional/equipe/humano diretamente, sua única ação neste turno é sinalizar handoff. Não continue perguntando, não ofereça horário, não dê nenhuma opinião sobre o sintoma.
2. **Reforço de "zero hype"** no mesmo topo — a 2ª ronda mostrou linguagem tipo depoimento ("resultados têm sido muito positivos") vazando inclusive na resposta de saúde, agravando o C5.

**Por que não vale mudar mais código agora:** fora o ponto do C6 (decisão em aberto do utilizador), a lógica construída — recepção nunca fala preço, qualificação protege a apresentação, fases de agendamento sem closing — está funcionando como projetada. Boa parte do que pareceu "bug" nos testes é artefato de dado de teste, variância normal de LLM em amostra pequena (5 rodadas), ou comportamento de "turno frio" que a própria 3ª ronda provou se autocorrigir em conversas reais contínuas. Mexer em `decision_engine.py` arriscaria desestabilizar guardrails (anti-loop, homologação de categoria, saudação composta) já ajustados ao longo de meses, por ganho marginal em cenários que o teste isolado (sessão nova a cada rodada) exagera em frequência.

### Aplicação confirmada em `/ai-profile` (02/07, conta `autodigital157@gmail.com`, AI Profile "Lara")

Os dois reforços acima foram inseridos em `custom_instructions` (Camada 1 → "Perfil Gerado") via browser, logo após o parágrafo PERSONA e antes de "ABERTURA DE CONVERSA".

**Nota de UX descoberta durante a aplicação (não é bug, mas vale registrar para próximas sessões de teste):** o botão "Salvar alterações" dentro do modal de um campo individual (ex.: "Perfil Gerado") só aplica a mudança ao estado local da Camada — não persiste no backend sozinho. Fecha o modal e mostra o banner "Editando Camada 1 · Alterações aplicadas apenas em novas conversas", com um botão adicional "SALVAR CAMADA" que só então dispara o `PUT /ai-profiles/me`. Sem esse segundo clique, qualquer edição de campo é perdida ao recarregar a página — confirmado experimentalmente (2 tentativas de salvar só o campo individual não persistiram; a 3ª, com o clique em "SALVAR CAMADA", gerou o `PUT` real, HTTP 200, confirmado por reload + reabertura do campo).

Confirmado via rede: `PUT https://backend-core-production-863b.up.railway.app/ai-profiles/me` → `200`, `custom_instructions` na resposta já com 4461 caracteres incluindo as duas regras críticas, `updated_at` atualizado para `2026-07-02T16:02:01`. Verificado novamente após reload de página + reabertura do campo — texto persistido.

---

## Quarta ronda — Cenário 1 (horário) retestado após fixes de recepção/pendência comercial (08/08/2026)

> Contexto: entre a rodada original (02/07) e esta, dois fatores mudaram: (1) o fix graduado
> `fix-recepcao-pendencia-comercial` (ver `docs/architecture/llm-architecture.md`, secção
> "Saudação composta") passou a separar sempre a saudação da resposta de conteúdo em duas
> chamadas de LLM distintas; (2) esta conta (`autodigital157@gmail.com`, AI Profile "Daniel",
> id=5) está configurada com `scheduling_offer_style=confirm_exact` em vez do padrão
> `offer_alternatives`. Objetivo: verificar se a contradição entre bolhas do achado #5
> original (uma bolha diz "disponível", outra diz "ocupado") ainda ocorre. Ambiente local
> (backend-core:8001, backend-crm:8000, backend-executors:8002), via `POST
> /api/playground/chat` direto (`ai_profile_id=5`), 5 sessões novas (`lead_id=null` a cada
> rodada), mesma mensagem do roteiro original: "Oi, queria saber se tem horário quinta às 15h".

| # | 1ª chamada (saudação) | 2ª chamada (resposta real, via reenfileiramento) | Contradição? |
|---|---|---|---|
| 1 | "Oi! Seja bem-vindo(a)! Estou aqui para ajudar com seu agendamento." | "Fica confirmado então seu agendamento para quinta-feira às 15h. Posso ajudar com mais alguma coisa antes do nosso encontro?" | ✅ Não |
| 2 | "Oi! Agradeço pelo contato. Vou encaminhar sua pergunta sobre o horário na quinta às 15h para a equipe que cuida disso." | "Fica confirmado para quinta-feira às 15h. Alguma orientação que você gostaria de alinhar antes da nossa conversa?" | ✅ Não |
| 3 | "Oi, Lead de Teste! Agradeço pelo contato. Estou aqui para ajudar no que você precisar." | "Confirmado, temos horário disponível na quinta-feira às 15h. Vamos agendar essa consulta? Qual serviço você gostaria de solicitar?" | ✅ Não |
| 4 | "Oi! Que bom receber sua mensagem. Deixe eu passar isso para o/a Digital Pro dar sequência na sua solicitação." | "Confirmado para quinta-feira às 15h. O/a Digital Pro aguarda você! Podemos seguir com o agendamento ou você precisa de mais alguma informação?" | ✅ Não |
| 5 | "Oi! Que bom receber sua mensagem. Vou encaminhar sua solicitação. Aguarde um momento, por favor." | "Fica confirmado então para quinta às 15h. Qualquer dúvida ou mudança, estou à disposição." | ✅ Não |

**Resultado: 5/5 ✅ · 0/5 ❌ — nenhuma contradição em nenhuma rodada.**

**Leitura:** a saudação (1ª chamada) nunca mais faz nenhuma afirmação sobre disponibilidade —
só cumprimenta e reencaminha o pedido, exatamente como desenhado pelo fix de reenfileiramento.
A afirmação sobre o horário fica isolada numa única chamada (a 2ª, real), então não há mais
duas bolhas da mesma resposta competindo com informações diferentes. Isso resolve a causa
estrutural do achado #5 original (uma única chamada de LLM tentando cumprimentar E responder
ao mesmo tempo, arriscando se contradizer no meio do caminho).

**Ressalva:** amostra pequena (5, igual à rodada original) e testada só nesta conta específica
(`confirm_exact` + fix de recepção já aplicado). Não foi testado com `offer_alternatives`
(estilo padrão de contas novas) — nesse estilo a instrução ainda pede "proponha 2-3 horários"
de forma menos determinística, então o risco de auto-contradição dentro da 2ª chamada (não
mais entre saudação e resposta, mas dentro da própria resposta) não pode ser descartado sem
retestar nessa configuração.

**Bônus observado:** o bug "Empresa Teste" (achado #3 da rodada original) não reapareceu em
nenhuma das 5 rodadas — o lead sandbox aparece como "Lead de Teste" em todas. Consistente com
`backend-crm/routes/playground.py:_create_sandbox_lead()` já não gravar mais `companyName`
hardcoded (mudança não documentada em nenhum arquivo de implementação encontrado — parece ter
sido corrigida como parte de outro trabalho não relacionado a este roteiro).

---

## Quinta ronda — Cenário 3 (recuperação de paciente sumido) retestado (08/08/2026)

> Contexto: mesmo motivo do reteste do Cenário 1 — verificar se os 3 achados de qualidade
> (fragmentação excessiva, bolha só com emoji, passividade) ainda ocorrem após o fix de
> recepção/pendência comercial. Ambiente local, `ai_profile_id=5`
> (`scheduling_offer_style=offer_alternatives`, deixado assim do teste anterior), 5 sessões
> novas (`lead_id=null`), mesma mensagem do roteiro original: "Oi, ainda quero remarcar".

| # | Saudação (bolhas) | Resposta real | Fragmentação | Emoji isolado |
|---|---|---|---|---|
| 1 | 3 | "Legal saber que você ainda quer remarcar! Que dia funcionaria melhor pra você?" | normal | Não |
| 2 | 1 | "Terça-feira (11/08) às 10:00 ou quarta-feira (12/08) às 15:00?" | normal | Não |
| 3 | 2 | "Terça-feira às 09:00 ou quarta-feira às 10:00 e 16:00?" | normal | Não |
| 4 | 2 | "Que dia funcionaria melhor pra você para agendarmos a sessão?" | normal | Não |
| 5 | 3 | "10/08 às 09:00, 11/08 às 14:00 ou 12/08 às 15:00?" | normal | Não |

**Resultado: 5/5 sem fragmentação excessiva (máx. 3 bolhas de saudação, vs. até 4-5 na rodada
original) · 5/5 sem bolha isolada de emoji · 5/5 sem o bug "Empresa Teste".**

**Achado de "passividade" reavaliado — não é o mesmo bug.** Em 2/5 rodadas (1 e 4) o bot
perguntou "que dia funciona melhor?" em vez de já propor horários. Diferença em relação ao
achado original: a mensagem do lead ("ainda quero remarcar") não especifica nenhum dia — a
pergunta é uma clarificação razoável, não a resposta genérica/não-sequitur do achado original
("me avise quando puder remarcar", ignorando que o lead já sinalizou prontidão). Rota
`Pré-Agendamento` (tentativa, sem dia+hora firmes) nas rodadas 1/4 vs. `Agendamento` (firme,
horários concretos direto) nas rodadas 2/3/5 — comportamento esperado por design (ver
`llm-architecture.md`, Filha Pré-agendamento), não um defeito.

**Leitura:** mesma causa provável do reteste do Cenário 1 — a separação saudação/resposta real
em duas chamadas de LLM distintas reduz a "resposta confusa tentando fazer saudação + conteúdo
ao mesmo tempo", que era a raiz mais provável tanto da fragmentação quanto do emoji decorativo
solto no fim. Dos 3 achados de qualidade do Cenário 3 original, 2 parecem resolvidos; o 3º não
reproduziu na mesma forma.

---
