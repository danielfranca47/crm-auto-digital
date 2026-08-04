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

---

## Checks de Validação

### Cenário P1 — Mensagem composta com dia+hora (o bug relatado)
- [ ] Playground, lead novo, 1ª mensagem: "Olá, boa tarde, gostaria de agendar horário para hoje às 17:30"
- [ ] Confirmar: resposta = cumprimento + 2ª bolha tratando o agendamento de verdade (nunca "vou verificar" sem continuação)

### Cenário P2 — Burst de mensagens fragmentadas (obrigatório)
- [ ] Simular mensagem única `"oi\nboa tarde\ntudo bem?\nqual seria o preço da massagem e horários disponíveis?"` (replica o que o buffer de debounce concatenaria)
- [ ] Confirmar: Recepção cumprimenta 1x, isola só a pergunta de preço/horário como pendência, 2ª bolha trata via rota correta

### Cenário P3 — Pergunta não-agendamento (generalização)
- [ ] Testar "Olá, qual o horário de funcionamento de vocês?"
- [ ] Confirmar: mesma dinâmica (cumprimento + 2ª bolha respondendo a pergunta), não só casos de agendamento

### Cenário P4 — Saudação pura (regressão)
- [ ] Testar "Oi", "Boa tarde" sem nenhum pedido embutido
- [ ] Confirmar: só a saudação é enviada, sem 2ª bolha nem `pending_commercial_text`

### Cenário C1 — WhatsApp real (se viável no momento do teste)
- [ ] Repetir cenário P1/P2 num número de teste real
- [ ] Confirmar: 2 mensagens outbound distintas chegam ao lead; 2º job (`whatsapp.inbound.n8n`, `source_message_id` prefixado `requeue:`) aparece na fila

---

## Ajustes Possíveis Pós-Implementação

- Corrida com o buffer de debounce (job reenfileirado pode ser concatenado por uma mensagem real subsequente do lead) — trade-off aceito, documentado na Fase 3.
- Custo de LLM duplicado quando há pendência — aceito, mesmo padrão que o mecanismo antigo já tinha.
- `check_playground_limit` conta 1x por request HTTP mesmo com 2 chamadas internas ao decision engine — não é regressão nova.
