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
- [ ] Playground, perfil hybrid_scheduler, lead novo (reset), enviar:
      "ola gostaria de agendar uma sessao para amanha as 15 h"
- [ ] Confirmar trace: `mother_route_to=recepcao`, `effective_route_to=agendamento`
      (ou `pre-agendamento`/`qualification`, dependendo do que a Mãe percebeu)
- [ ] Confirmar: a resposta cumprimenta brevemente E trata o pedido na mesma
      mensagem (não "vou verificar, um momento")

### Cenário P2 — Saudação pura continua intacta
- [ ] Playground, lead novo, enviar apenas "ola"
- [ ] Confirmar trace: `mother_route_to=recepcao`, `effective_route_to=recepcao`
      (sem override — comportamento prévio preservado)

### Cenário C1 — Saudação composta no WhatsApp real
- [ ] Repetir o cenário P1 com um número de teste real
- [ ] Confirmar mesmo comportamento (paridade Playground/real)

---

## Ajustes Possíveis Pós-Implementação

- Quando `compound_follow_through == "qualification"`, a extração/persistência de
  campos de qualificação (`decide()`, linhas 4201-4433) não corre neste turno
  específico, porque esse bloco verifica `mother_decision.route_to == "qualification"`
  (que permanece `"recepcao"`). Sem impacto prático hoje, porque é sempre a 1ª
  mensagem do lead — mas se isso se tornar relevante, requer revisitar esses guardrails.
- Não foi adicionado teste automatizado nesta fase — avaliar conforme uso real do
  campo `compound_follow_through` em produção.
