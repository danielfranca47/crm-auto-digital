# Fix: compound_follow_through nunca era lido — recepção trava em saudação composta

**Branch:** `main`
**Status:** Em andamento

---

## Motivação

Ao testar o agente demo (hybrid_scheduler "Lara", ver `docs/marketing/comercial/agente-demo.md`)
no Playground, uma mensagem composta de saudação + pedido de agendamento
("ola gostaria de agendar uma sessao para amanha as 15 h") fazia o bot prometer
"vou ajudar a agendar... um momento" e nunca devolver o horário real. A conversa
ficava travada — o lead precisava de enviar outra mensagem para o sistema avançar,
sem garantia de que avançaria para a rota certa.

Causa raiz: o campo `MotherDecision.compound_follow_through` existe desde o commit
que introduziu a filha "recepção" exatamente para este cenário (saudação + intenção
comercial na mesma mensagem) e a LLM Mãe é instruída a preenchê-lo — mas nenhum
código em `decision_engine.py` o lê. A filha recepção (proibida de falar de
agendamento/preço/catálogo, por desenho) é a única chamada nesse turno.

---

## Problemas Identificados (estado anterior)

1. **`compound_follow_through` nunca lido (`decision_engine.py:4185`):** `route_for_child = mother_decision.route_to`
   ignora por completo `mother_decision.compound_follow_through`. Confirmado por grep
   em todo o arquivo — a única outra ocorrência da string é dentro do texto do
   prompt da Mãe (`decision_engine.py:1794-1796`), como instrução, nunca como leitura
   de valor.
2. **Filha recepção não tem como agir sobre a parte comercial (`decision_engine.py:1870-1939`):**
   `_build_child_prompt_recepcao` é deliberadamente restrita ("NUNCA mencione
   preços... agendamento... Apenas cumprimento"). Quando o LLM "vaza" essa restrição
   e promete agendar, não há nenhum mecanismo no mesmo turno para cumprir a promessa.
3. **Sem trace de diagnóstico:** o trace exibido no Playground (`mother_route=recepcao,
   effective=recepcao`) não distinguia "saudação pura" de "saudação composta perdida" —
   dificultava detectar o bug a partir do transcript.

---

## Abordagem

```
Mãe decide route_to="recepcao" + compound_follow_through="agendamento"
  → decide() detecta compound_follow_through presente
      → route_for_child = compound_follow_through (pula a filha recepção)
      → context["_compound_greeting_pending"] = True
  → _build_daughter_identity_block() (chamada por todas as filhas) injeta:
      "esta é a 1ª mensagem do lead e incluía uma saudação — abra com um
       cumprimento breve antes de tratar o pedido, numa única mensagem"
  → filha comercial (agendamento/apresentation/...) responde já com o
    cumprimento + o conteúdo real (horário, preço, etc.)
  → effective_route_override=route_for_child já propaga para decision_trace
    automaticamente (compose_decision_output) — trace passa a mostrar
    mother_route_to=recepcao, effective_route_to=agendamento
```

---

## Plano de Implementação

### Fase 1 — Override de rota + instrução partilhada de abertura

**Objetivo:** quando a Mãe sinaliza saudação composta, pular a filha recepção e
chamar diretamente a filha comercial certa, com instrução para abrir com um
cumprimento breve.

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/decision_engine.py` (`decide()`, perto da linha 4185) | Após calcular `route_for_child`, se `mother_decision.route_to == "recepcao"` e `mother_decision.compound_follow_through` estiver presente (e não for tick de follow-up): `route_for_child = mother_decision.compound_follow_through`; `context["_compound_greeting_pending"] = True`; log do evento. |
| `backend-executors/app/services/decision_engine.py` (`_build_daughter_identity_block`, linha 872) | No final da função, se `context.get("_compound_greeting_pending")`, apensa um parágrafo de instrução: abrir com cumprimento breve, responder o pedido na mesma mensagem, não fragmentar. |

```python
# ANTES (decide(), ~linha 4185)
route_for_child = "follow-up" if force_followup_route else mother_decision.route_to

# DEPOIS
route_for_child = "follow-up" if force_followup_route else mother_decision.route_to
if (
    not force_followup_route
    and mother_decision.route_to == "recepcao"
    and mother_decision.compound_follow_through
):
    route_for_child = mother_decision.compound_follow_through
    context["_compound_greeting_pending"] = True
    if logger:
        logger.info(
            "event=compound_follow_through_route route_override=%s job_id=%s lead_id=%s",
            route_for_child,
            (context.get("job") or {}).get("id"),
            lead.get("id"),
        )
```

Teste automatizado novo: `backend-executors/tests/test_compound_follow_through_routing.py`
(2 cenários — saudação composta avança direto; saudação pura permanece em recepção).

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `1553aa1` | Override de `route_for_child` por `compound_follow_through` + instrução de abertura partilhada + teste |

---

### Nota — débito de testes pré-existente (não corrigido nesta fase)

Ao correr a suíte completa (`pytest tests/`) antes e depois desta mudança, confirmei que
**21 testes já falhavam antes desta alteração** (ex.: `test_mother_qualification_route_guardrail.py`,
toda a `test_qualification_state_loop.py`, `test_followup_tick_*`, `test_qualification_contract.py`).
Causa: a maioria usa `"history": []` nos contextos de teste, o que faz `_enforce_greeting_first`
forçar `route_to="recepcao"` independentemente do que a Mãe decidiu — esses testes foram escritos
antes desse guardrail existir e nunca foram atualizados. Confirmei com `git stash` que o número de
falhas (21) é idêntico antes/depois desta mudança — **nenhuma regressão introduzida**. Fora de
escopo corrigir aqui; mencionar ao utilizador.

---

## Checks de Validação

### Cenário P1 — Saudação composta com horário firme (Playground)
- [x] Playground, perfil hybrid_scheduler (ai_profile_id=5, conta de teste), lead novo,
      enviar: "oi, gostaria de agendar uma sessão para amanhã às 15h"
- [x] Confirmar trace: `mother_route_to=recepcao`, `effective_route_to=agendamento`
- [x] Confirmar: a resposta trata o pedido de fato (chegou a oferecer horário
      alternativo por conflito real de agenda — ver Fase 2), não "vou verificar, um momento"
- **Validado em:** 19/06/2026 — via chamada directa à API (`POST /api/playground/chat`),
  testes 3x. Na 1ª tentativa revelou o bug descrito na Fase 2 (route ficou em recepcao
  porque a Mãe usou `perceived_category` em vez de `compound_follow_through`); após a
  correção da Fase 2, `effective_route_to=agendamento` confirmado.
- **Revalidado em:** 20/06/2026, via UI real do Playground (browser, MCP chrome-devtools),
  com exportação do `.md` da sessão (`playground-2026-06-19_19-41-output.md`, conta de
  teste). Trace: `mother_route=recepcao, effective=agendamento, confidence=90%`. A filha de
  agendamento ainda evitou corretamente um horário já ocupado por outro teste (calendar_busy_slots).

### Cenário P2 — Saudação pura continua intacta
- [x] Playground, lead novo, enviar apenas "oi"
- [x] Confirmar trace: `mother_route_to=recepcao`, `effective_route_to=recepcao`
      (sem override — comportamento prévio preservado)
- **Validado em:** 19/06/2026 — `signals.meeting_scheduled=false`, resposta é só
  cumprimento, sem preços/agenda. Cobre também o caso de borda da Fase 2
  (`perceived_category=qualification` igual à categoria atual do lead → não dispara
  o fallback).
- **Revalidado em:** 20/06/2026, via UI real do Playground, `.md` exportado
  (`playground-2026-06-19_19-44-output.md`). Trace: `effective_route=recepcao`,
  `meeting_scheduled=false`.

### Cenário C1 — Saudação composta no WhatsApp real
- [ ] Repetir o cenário P1 com um número de teste real
- **Pendente:** não testado nesta sessão — requer instância WhatsApp de teste conectada.
  Como o caminho de código (`decision_engine.decide()`) é idêntico para Playground e
  WhatsApp real (mesmo `decide()`, mesmo `ContextBundle`), o resultado validado em P1
  tem alta probabilidade de se repetir — mas falta confirmação empírica real.

---

## Fase 2 — Diagnóstico + Correção: `perceived_category` como sinal adicional (19/06/2026)

### Problema identificado

Ao testar o Cenário P1 com uma mensagem real (LLM real, não mockado), a Mãe devolveu
`route_to="recepcao"` com `perceived_category="agendamento"` — mas **sem** preencher
`compound_follow_through`. O override da Fase 1 só lia `compound_follow_through`, então
não disparou: a filha recepção foi chamada, "vazou" a restrição e prometeu agendar sem
cumprir — exatamente o bug original, ainda reproduzível mesmo com a Fase 1 aplicada.

Causa raiz: o modelo real nem sempre usa o campo que o prompt pede explicitamente
(`compound_follow_through`) para expressar a saudação composta — por vezes usa
`perceived_category`, campo que já existe para outro propósito (indicar o estágio
percebido do lead) e que outras partes do código já líam (`apply_mother_category_guardrails`).

### Correção

Estendido o override da Fase 1: quando `compound_follow_through` está vazio, usar
`perceived_category` como sinal de fallback — **somente se diferir da categoria atual
do lead** (`lead.category`). Essa condição é necessária porque o prompt da Mãe instrui
"mantenha perceived_category = lead.category quando em dúvida" — sem essa restrição, toda
saudação pura de um lead novo (`lead.category="qualification"` por default) acionaria o
override incorretamente, porque `perceived_category` viria igual a `"qualification"`.
Confirmado empiricamente: testei "oi" puro e `perceived=qualification` (igual à categoria
atual → não dispara); testei a saudação composta e `perceived=agendamento` (diferente de
`qualification` → dispara).

| Arquivo | Mudança |
|---|---|
| `backend-executors/app/services/decision_engine.py` (`decide()`, bloco do override) | Se `compound_follow_through` ausente, calcula `_perceived = mother_decision.perceived_category`; usa como fallback apenas se não-nulo, diferente de `"recepcao"` e `_normalize_category(_perceived) != _normalize_category(lead.category)`. Log inclui `source=compound_follow_through\|perceived_category` para observabilidade. |
| `backend-executors/tests/test_compound_follow_through_routing.py` | Novo teste `test_perceived_category_fallback_routes_when_compound_follow_through_missing`, reproduzindo o cenário real observado. |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `5fa323a` | Fallback via `perceived_category` + teste de regressão |

---

## Ajustes Possíveis Pós-Implementação

- Quando `compound_follow_through == "qualification"` (via qualquer uma das duas fontes),
  a extração/persistência de campos de qualificação (`decide()`, linhas ~4201-4433) não
  corre neste turno específico, porque esse bloco verifica `mother_decision.route_to ==
  "qualification"` (que permanece `"recepcao"`). Sem impacto prático hoje, porque é sempre
  a 1ª mensagem do lead — mas se isso se tornar relevante, requer revisitar esses guardrails.
- Cenário C1 (WhatsApp real) continua pendente — repetir quando houver instância de teste
  conectada.
