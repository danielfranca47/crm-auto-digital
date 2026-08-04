# Fix: pedido comercial pendente na saudação de 1º contato

**Branch:** `fix/recepcao-handoff-comercial`
**Status:** Em andamento

---

## Motivação

No 1º contato de um lead (`outbound_count==0`), o sistema força `route_to="recepcao"` — a Filha Recepção só cumprimenta, nunca trata pedido comercial. Já existia um mecanismo de "saudação composta" para o caso em que a 1ª mensagem mistura saudação + pedido comercial (ex.: "Olá, boa tarde, gostaria de agendar para hoje às 17:30"), mas depende de a Mãe (LLM) detectar isso corretamente em meio a ~7 prioridades concorrentes no mesmo prompt.

Em testes reais no Playground, esse mecanismo falha com frequência: a Mãe não seta o sinal, a Filha Recepção improvisa uma promessa vazia ("olá, vou verificar") que nunca é cumprida, e o pedido do lead se perde — sem nenhum estado registrado como pendente.

Causa raiz: detecção 100% dependente de LLM, sem guardrail determinístico, e o código tem uma classe de bug já documentada (gate cego à rota promovida por override em-turno).

---

## Problemas Identificados (estado anterior)

1. **Detecção não-determinística:** `backend-executors/app/services/decision_engine.py:1821-1837` — a Mãe precisa setar `compound_follow_through` (ou divergir `perceived_category`) para o mecanismo disparar; sem garantia de código.
2. **Filha Recepção improvisa promessa vazia:** `_build_child_prompt_recepcao` (`decision_engine.py:1911-1980`) não tem trava contra frases como "vou verificar" quando vê um pedido comercial que está proibida de tratar.
3. **Nenhum estado de pendência registrado:** quando o mecanismo não dispara, o pedido do lead desaparece — só seria resgatado se o lead repetir a pergunta.
4. **Restrito a `route_to` conhecido pela Mãe:** o mecanismo atual só cobre o que a Mãe classifica corretamente; não generaliza a perguntas fora do padrão de agendamento (ex.: "horário de funcionamento?").
5. **Bug de gate já documentado:** `docs/architecture/llm-architecture.md`, seção "Saudação composta" — código que checa `mother_decision.route_to` literal, cego à rota promovida via `route_for_child` no mesmo turno (já corrigido uma vez em 2026-06-28 para um caso irmão).

---

## Abordagem

```
1º contato do lead → route_to="recepcao" (forçado por código)
  → Filha Recepção gera saudação
     └─ extrai literalmente qualquer trecho não-social em pending_commercial_text
  → decision_engine anexa system_action "requeue_pending_message" (se houver pendência)
  → consumidor (WhatsApp real ou Playground) reenfileira essa pendência
     ├─ WhatsApp real: novo job whatsapp.inbound.n8n (mesmo type, worker processa normal)
     └─ Playground: 2ª chamada síncrona a decide(), na mesma request
  → pendência percorre o pipeline NORMAL no próximo ciclo (Mãe decide de verdade,
    sem overrides) → rota comercial correta trata o pedido
```

Mecanismo antigo de override em-turno (`compound_follow_through`) é removido por completo — o novo caminho é estritamente mais geral e elimina a classe de bug do gate cego, não só a instância corrigida antes.

---

## Plano de Implementação

### Fase 1 — Schema + prompt da Filha Recepção (backend-executors)

**Objetivo:** a Filha Recepção passa a extrair e reportar qualquer pedido comercial embutido na mensagem, sem tratá-lo.

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/orchestrator_models.py` | `ChildResult` ganha `pending_commercial_text: Optional[str] = None` |
| `backend-executors/app/services/decision_engine.py` | `_build_child_prompt_recepcao`: nova instrução de extração + campo no JSON de retorno |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `7994a20` | `ChildResult.pending_commercial_text` + instrução de extração no prompt da Filha Recepção + testes |

### Fase 2 — Novo `system_action` + remoção do mecanismo antigo (backend-executors)

**Objetivo:** o pipeline sinaliza a pendência via `system_actions`, e o override em-turno antigo deixa de existir.

| Arquivo | O que muda |
|---|---|
| `decision_engine.py` | `compose_decision_output`: append de `{"type":"requeue_pending_message","message_text":...}` quando `effective_route_to=="recepcao"` e há pendência |
| `decision_engine.py` | Remove bloco 4418-4464 (override `compound_follow_through`/fallback `perceived_category` + chamada LLM dedicada) |
| `decision_engine.py` | Remove bloco `_greeting_prefix`/`_compound_greeting_text` (~4787-4792) |
| `decision_engine.py` (`_build_mother_prompt`) | Remove subseção "SAUDAÇÃO COMPOSTA" da PRIORIDADE 0 (~1821-1837) |
| `orchestrator_models.py` | Remove `compound_follow_through` de `MotherDecision` |
| `backend-executors/tests/test_compound_follow_through_routing.py` | Removido — substituído por novos testes do comportamento atual |
| `docs/architecture/llm-architecture.md` | Reescreve seção "Saudação composta" refletindo o novo mecanismo |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `3e3bb33` | `requeue_pending_message` + remoção completa do mecanismo antigo (código, testes, docs) |

### Fase 3 — Consumo no WhatsApp real (backend-crm)

**Objetivo:** a pendência vira um novo job real, processado pelo worker normalmente.

| Arquivo | O que muda |
|---|---|
| `backend-crm/routes/executor.py` | `_dispatch_system_actions` ganha `elif atype == "requeue_pending_message"`: monta payload via `build_job_payload` (reaproveita `instance_id`/`provider`/`phone` do job original) e chama `create_job(job_type=TYPE_WHATSAPP_INBOUND, ...)` |
| `backend-crm/routes/executor.py` | Chamador (`complete_job_internal`) passa `instance_id`/`provider`/`source_message_id` do `job_payload` original |

### Commits Fase 3

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `6f3778f` | Consumo de `requeue_pending_message` no WhatsApp real (novo job) + testes |

### Fase 4 — Consumo no Playground (backend-crm)

**Objetivo:** paridade — o operador testando no Playground vê o mesmo comportamento de 2 mensagens que veria no WhatsApp real.

| Arquivo | O que muda |
|---|---|
| `backend-crm/routes/playground.py` | Captura `requeue_pending_message` no loop de `system_actions`; após persistir a mensagem outbound da 1ª decisão, dispara 2ª chamada síncrona a `_call_executors_decide()` com bundle novo; anexa resultado como 2ª bolha |
| `docs/architecture/playground-parity.md` | Nota sobre 2ª bolha vinda de `requeue_pending_message` |

**Decisão:** sem teste sintético de endpoint para esta fase — `playground_chat` não tem precedente de teste end-to-end no repo (exigiria mockar auth, DB, `httpx` para o executor, AI Profile), e a lógica nova reaproveita helpers já cobertos indiretamente pelas Fases 1-3 (`_call_executors_decide`, `_insert_message`, `_update_lead_category`). Validação real fica a cargo dos Cenários P1-P4 abaixo, ao vivo.

`backend-crm/docs/playground-whatsapp-parity.md` (citado no CLAUDE.md) não existe no repositório — drift de documentação pré-existente, fora do escopo deste fix.

### Commits Fase 4

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `6c9a394` | 2ª chamada síncrona no Playground + docs de paridade |

---

### Fase 5 — Reforço do prompt da Filha Recepção (backend-executors)

**Objetivo:** corrigir o desvio observado na validação ao vivo dos Cenários P1/P3 (ver
"Relatório das Fases 1-4" e checks abaixo): a Filha Recepção às vezes respondia
diretamente ao pedido comercial na 1ª bolha ("Vamos agendar seu horário...", "Nós
funcionamos de segunda a sábado...") em vez de só cumprimentar e reportar em
`pending_commercial_text`. O mecanismo de extração/reenfileiramento continuava
funcionando nesses casos, mas a instrução "apenas cumprimento" não era seguida à
risca pelo LLM.

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/decision_engine.py` (`_build_child_prompt_recepcao`) | Reestrutura o texto estático do prompt em seções explícitas: IDENTIDADE, O QUE FAZ, COMO FAZ, EXEMPLOS DO QUE FAZER (✅, 3 exemplos), O QUE NÃO FAZ, EXEMPLOS DE ERRO (❌, 3 exemplos — os 2 primeiros grounded nos desvios reais observados em P1/P3, o 3º é o anti-padrão "vou verificar" que motivou o fix original). Sem mudança de contrato JSON nem da lógica dinâmica de `greeting_instruction` (3 variantes por tipo de lead) — só reorganização e reforço com exemplos. |

### Commits Fase 5

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `acb8703` | Reforço do prompt da Filha Recepção com identidade + exemplos ✅/❌ |

---

### Fase 6 — Rótulo real da 2ª bolha no Playground + alias do enum `route_to`

**Objetivo:** testando P1/P3 pela UI do Playground (browser, via MCP), a 2ª bolha
(resultado da pendência reenfileirada) aparecia sempre rotulada genericamente
"Fluxo de Venda", mesmo quando era, na maioria dos casos, a resposta real da
Filha correspondente após a Mãe decidir a rota de verdade (confirmado nos logs
do executors: `route_to=agendamento` → `_build_child_prompt_agendamento`). O
utilizador pediu para mostrar a Filha/rota real em vez do rótulo genérico.

Investigando por que às vezes a 2ª bolha era um handoff genérico ("Vou te
conectar com alguém do time agora"), achei a causa: `MotherDecision.route_to`
(Pydantic `Literal`, obrigatório, sem tolerância de enum) às vezes vem da LLM
como `"presentation"` em vez do literal `"apresentation"`, derrubando a
validação inteira e caindo no fallback de handoff — que também era mostrado,
incorretamente, como "Fluxo de Venda". Corrigido junto, a pedido do utilizador.

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/orchestrator_models.py` | Novo `field_validator("route_to", mode="before")` em `MotherDecision`: corrige o alias pontual `"presentation"` → `"apresentation"` antes da validação do `Literal`. Valores desconhecidos continuam a levantar `ValidationError` (comportamento preservado). Log: `event=mother_decision_route_to_alias_coerced`. |
| `docs/architecture/llm-architecture.md` | Documenta o novo alias de `route_to`, distinto da tolerância genérica de enum já existente para campos opcionais. |
| `backend-crm/routes/playground.py` | Novo dict `_ROUTE_TO_LABELS`. Cada item de `auto_items` ganha `source`/`source_label`: `"sales_flow"`/"Fluxo de Venda" para blocos `send_message` genuínos; `"child_llm"`/nome da rota real (ex. "Agendamento") para a resposta da 2ª chamada ao decision engine; `"fallback"`/"Handoff (erro de decisão)" quando `_decision2.reason == "llm_failure"`. |
| `frontend-crm/src/services/api.ts` | `PlaygroundAutoItem` (variante texto) ganha `source?`/`source_label?` opcionais. |
| `frontend-crm/src/pages/Playground.tsx` | `revealAutoMessages` propaga `autoMessageSource`/`autoMessageLabel` para o `ChatMessage`. |
| `frontend-crm/src/components/playground/MessageBubble.tsx` | Rótulo passa a usar `message.autoMessageLabel` (fallback "Fluxo de Venda" para sessões antigas sem o campo). 3 cores por fonte: violeta (`sales_flow`, igual antes), teal (`child_llm`, nova), âmbar (`fallback`, nova — chama atenção para erro de decisão). |

**Validação ao vivo:** P1 (lead 393) → `auto_items[0].source_label = "Agendamento"`.
P3 (lead 394, repetido também na UI via browser) → `auto_items[0].source_label =
"Apresentação"`, confirmado visualmente com bolha teal na captura de tela. Teste
unitário direto em `MotherDecision(route_to="presentation", ...)` confirma que o
alias corrige para `"apresentation"`, e que valores realmente desconhecidos
continuam a levantar `ValidationError` (comportamento de fallback preservado
para casos genuinamente não mapeados). Não foi possível reproduzir o typo real
vindo da LLM nestes testes específicos (é um erro esporádico dela) — validação
do alias em produção fica oportunística, não bloqueante.

### Commits Fase 6

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | *(a preencher após commit)* | Alias route_to (`presentation`→`apresentation`) + rótulo real da 2ª bolha no Playground |

---

### Relatório das Fases 1-4 — o que mudou na prática

**Antes:** quando a 1ª mensagem de um lead já misturava saudação com um pedido comercial
("Olá, boa tarde, gostaria de agendar para hoje às 17:30"), o bot cumprimentava e às vezes
respondia algo como "certo, vou verificar" — e nunca mais voltava. O pedido do lead se
perdia, porque a detecção de que havia algo pendente dependia de a IA "Mãe" acertar uma
classificação no meio de várias regras concorrentes, o que falhava com frequência nos
testes reais.

**Agora:** a própria recepcionista (IA) lê a mensagem inteira, cumprimenta, e — se sobrar
algum pedido (agendamento, preço, horário de funcionamento, o que for) — extrai esse
trecho e o sistema reencaminha automaticamente para o setor certo tratar, como se fosse
uma nova mensagem do cliente chegando logo em seguida. O cliente recebe duas mensagens:
o cumprimento, e depois a resposta de verdade ao que ele pediu. Isso funciona tanto no
WhatsApp real (um novo job é processado pela fila) quanto no Playground de testes (uma
segunda chamada acontece na mesma resposta, para o operador ver as duas mensagens juntas).
Também cobre o caso de o lead mandar várias mensagens curtas seguidas ("oi", "boa tarde",
"tudo bem?", "qual o preço?") — o sistema já agrupava essas mensagens antes de chegar à IA,
então a mesma extração resolve os dois casos sem lógica extra.

**Para validar:** Cenários P1 a P4 (Playground) e C1 (WhatsApp real, se disponível), abaixo.

## Checks de Validação

### Cenário P1 — Mensagem composta com dia+hora (o bug relatado)
- [x] (2026-08-04) Playground, lead novo, 1ª mensagem: "Olá, boa tarde, gostaria de agendar horário para hoje às 17:30"
- [x] (2026-08-04) Confirmar: resposta = cumprimento + 2ª bolha tratando o agendamento de verdade (nunca "vou verificar" sem continuação)
  - Resultado real (lead_id=375): bolha 1 = "Obrigado pelo seu contato! Vamos agendar seu horário. Você gostaria de agendar para hoje às 17:30?"; `pending_commercial_text` extraído = "gostaria de agendar horario para hoje as 17:30"; bolha 2 = "Você prefere agendar para hoje às 17:30 ou um horário diferente? Vou verificar a disponibilidade assim que você me informar seu horário favorito." Categoria avançou para `agendamento`. Mecanismo de reenfileiramento funcionou; nenhuma promessa vazia sem continuação.
  - **Observação (não bloqueante):** a Filha Recepção não respeitou 100% a restrição "apenas cumprimento" — já engajou com o conteúdo do agendamento na bolha 1, em vez de só extrair e reportar. Não é falha do mecanismo (a extração/reenfileiramento ocorreu corretamente), mas sim aderência imperfeita do LLM ao prompt. Ver observação repetida no P3.

### Cenário P2 — Burst de mensagens fragmentadas (obrigatório)
- [x] (2026-08-04) Simular mensagem única `"oi\nboa tarde\ntudo bem?\nqual seria o preço da massagem e horários disponíveis?"` (replica o que o buffer de debounce concatenaria)
- [x] (2026-08-04) Confirmar: Recepção cumprimenta 1x, isola só a pergunta de preço/horário como pendência, 2ª bolha trata via rota correta
  - Resultado real (lead_id=376): bolha 1 = puro cumprimento, sem mencionar preço ("Boa tarde! Agradeço pelo contato. Me conta o que você está buscando em relação à massagem, estou aqui para ajudar."). `pending_commercial_text` extraído = "qual seria o preco da massagem e horarios disponiveis?" (limpo, sem "oi/boa tarde/tudo bem?"). Bolha 2 tratou via rota correta (redirecionou para agendar consulta antes de falar preço, coerente com `presentation_variant=scheduler`). Categoria avançou para `pre-agendamento`. **Este é o caso ideal — LLM seguiu a restrição perfeitamente.**

### Cenário P3 — Pergunta não-agendamento (generalização)
- [x] (2026-08-04) Testar "Olá, qual o horário de funcionamento de vocês?"
- [x] (2026-08-04) Confirmar: mesma dinâmica (cumprimento + 2ª bolha respondendo a pergunta), não só casos de agendamento
  - Resultado real (lead_id=377): mecanismo generalizou corretamente para pergunta fora do padrão de agendamento (horário de funcionamento). Categoria avançou para `apresentation`, bolha 2 seguiu com convite a agendar.
  - **Mesma observação do P1:** bolha 1 já respondeu ao horário de funcionamento diretamente ("Nós funcionamos de segunda a sábado, das 9h às 18h") em vez de só cumprimentar — violação da restrição "NUNCA mencione... serviços" do prompt, mas sem quebrar o mecanismo (pendência ainda foi extraída e reenfileirada, gerando a 2ª bolha).

### Cenário P4 — Saudação pura (regressão)
- [x] (2026-08-04) Testar "Oi", "Boa tarde" sem nenhum pedido embutido
- [x] (2026-08-04) Confirmar: só a saudação é enviada, sem 2ª bolha nem `pending_commercial_text`
  - Resultado real (lead_id=378 "Oi", lead_id=379 "Boa tarde"): ambos sem `auto_messages`/`auto_items`, sem reenfileiramento, categoria permaneceu `qualification`. Regressão confirmada — comportamento antigo (saudação pura, sem 2ª bolha) preservado.

### Cenário C1 — WhatsApp real (se viável no momento do teste)
- [⏭️] (2026-08-04) Não executado — requer envio de mensagem real via WhatsApp a partir de um telefone físico para a instância conectada (`whatsapp_connections.id=2`, `status=connected`), o que não é automatizável neste ambiente de agente. Cenários P1-P4 já validam a lógica ponta-a-ponta do decision engine e do reenfileiramento; C1 cobriria apenas a camada de transporte (job `whatsapp.inbound.n8n` com `source_message_id` prefixado `requeue:`, 2 mensagens outbound distintas via UazAPI). Recomenda-se ao utilizador repetir P1/P2 num número de teste real quando conveniente, usando o mesmo `ai_profile_id` de produção.

### Cenário P1-retest / P3-retest — confirmação do reforço do prompt (Fase 5)
- [x] (2026-08-04) Repetir P1 num lead novo após a reescrita do prompt
  - Resultado real (lead_id=380): bolha 1 = "Boa tarde! Agradeço por entrar em contato com a gente. Vou passar sua solicitação adiante." — agora **puro cumprimento**, sem engajar com o horário. `pending_commercial_text` extraído = "gostaria de agendar horário para hoje as 17:30". Bolha 2 = "Posso agendar para hoje às 17:30. Você prefere manter esse horário ou tem outra sugestão em mente? Vou verificar a agenda para confirmar."
- [x] (2026-08-04) Repetir P3 num lead novo após a reescrita do prompt
  - Resultado real (lead_id=381): bolha 1 = "Olá! Agradeço seu contato e fico feliz em te receber. Podemos ajudar com suas dúvidas sobre horários." — sem vazar o horário de funcionamento. Bolha 2 = "Estamos disponíveis para atender de segunda a sábado, com horários flexíveis..." tratou a pergunta de verdade.
  - **Desvio observado em P1/P3 corrigido** nos dois casos com a nova estrutura de prompt (identidade + exemplos ✅/❌).
- [x] (2026-08-04) Regressão: repetir P2 e P4 num lead novo cada
  - P2 (lead_id=382): bolha 1 continuou puro cumprimento; `pending_commercial_text` extraído limpo ("qual seria o preco da massagem e horarios disponiveis?"); bolha 2 desta vez preferiu um handoff humano ("Vou te conectar com alguém do time agora") em vez de responder o preço diretamente — variação normal da rota comercial (Mãe/guardrails), não relacionada à Recepção; mecanismo de extração/reenfileiramento continuou íntegro.
  - P4 (lead_id=383 "Oi", lead_id=384 "Boa tarde"): idêntico ao comportamento anterior — só cumprimento, sem `auto_messages`, sem reenfileiramento. Sem regressão.

---

## Ajustes Possíveis Pós-Implementação

- Corrida com o buffer de debounce (job reenfileirado pode ser concatenado por uma mensagem real subsequente do lead) — trade-off aceito, documentado na Fase 3.
- Custo de LLM duplicado quando há pendência — aceito, mesmo padrão que o mecanismo antigo já tinha.
- `check_playground_limit` conta 1x por request HTTP mesmo com 2 chamadas internas ao decision engine — não é regressão nova.
