# Fix: LLM Mãe pode retornar `route_to` fora do enum aceite

**Branch:** `fix/route-to-invalido-llm-mae`
**Status:** Em andamento

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`docs/implementations/playground-simular-nome-whatsapp.md`.

Durante um teste ao vivo no Playground (23/08/2026), a LLM Mãe respondeu
`"route_to": "qualificacao"` (grafia com "ç", aparente alucinação de idioma)
em vez do único valor aceite pelo enum, `"qualification"`. O Pydantic
rejeitou a resposta (`ValidationError: literal_error`), e o pipeline caiu no
fallback de `handoff` (`next_action=handoff, reason=llm_failure`),
desabilitando o bot para o lead afetado — mesmo a intenção da Mãe sendo
clara e correta, só a grafia do enum estava errada.

Log observado (`backend-executors`):
```
WARNING app.services.orchestrator_models event=mother_decision_invalid_enum_coerced field=perceived_category value='qualificacao'
WARNING app.api.playground_internal event=llm_orchestrator_error stage=mother_validate exc_type=ValidationError ...
  route_to: Input should be 'qualification', 'apresentation', 'pre-agendamento', 'agendamento', 'follow-up', 'closing' or 'recepcao' [type=literal_error, input_value='qualificacao', input_type=str]
decision fallback next_action=handoff reason=llm_failure
```

Interessante notar que `perceived_category` já tem um mecanismo de coerção
(`mother_decision_invalid_enum_coerced`) que aparentemente não cobre (ou não
cobriu neste caso) o campo `route_to`.

Reproduzido uma vez em várias tentativas no mesmo teste — parece raro/esporádico, não veio a acontecer de novo em tentativas subsequentes.

---

## Diagnóstico

**Causa raiz confirmada** em `backend-executors/app/services/orchestrator_models.py`:

- `perceived_category` já tolera exatamente esse tipo de erro: `_OPTIONAL_ENUM_FIELDS` degrada qualquer valor fora do enum para `None` via `_coerce_unknown_enum_to_none()` — foi isso que aconteceu no log (`event=mother_decision_invalid_enum_coerced field=perceived_category value='qualificacao'`, sem erro).
- `route_to`, por ser **obrigatório e sem default seguro**, foi deliberadamente deixado fora desse mecanismo genérico (comentário no código, linhas 19-22): usa uma lista fechada de aliases conhecidos (`_ROUTE_TO_ALIASES`, hoje só `"presentation" → "apresentation"`), normalizada por `_normalize_route_to_alias()` antes da validação do `Literal`. Qualquer valor fora dessa lista continua a levantar `ValidationError` de propósito.
- `"qualificacao"` nunca tinha sido adicionado a essa lista — só isso causou a falha. `perceived_category` e `route_to` são validados pelo mesmo `MotherDecision.model_validate()` em `decision_engine.py:5284`, único ponto usado tanto pelo Playground quanto pelo executor real (`routes/executor.py`) — corrigir aqui cobre os dois caminhos automaticamente, sem duplicação.

**Decisão de abordagem:** manter o padrão existente (lista fechada de aliases conhecidos) em vez de generalizar para uma normalização de acentos/hífens. O comentário do código já documenta essa escolha como deliberada — valores realmente desconhecidos devem continuar a falhar alto (fail loud) em vez de serem silenciosamente coeridos, para não mascarar bugs futuros.

---

## Abordagem

```
Mãe responde route_to="qualificacao"
  → _normalize_route_to_alias() consulta _ROUTE_TO_ALIASES
      ├─ encontrado ("qualificacao" → "qualification")  → normaliza, valida OK
      └─ não encontrado (ex.: "foobar")                  → ValidationError, fallback handoff (comportamento preservado)
```

---

## Plano de Implementação

### Fase 1 — Adicionar alias conhecido

**Objetivo:** parar de derrubar a decisão da Mãe quando ela responde `"qualificacao"` em vez de `"qualification"`.

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/orchestrator_models.py` | Adicionar `"qualificacao": "qualification"` a `_ROUTE_TO_ALIASES`, mesmo padrão do alias `"presentation"` já existente |
| `backend-executors/scripts/test_route_to_alias_coercion.py` (novo) | Teste standalone (mesmo padrão de `scripts/test_category_validation.py`): confirma os aliases `"qualificacao"` e `"presentation"`, e que um valor desconhecido (`"foobar"`) ainda levanta `ValidationError` |

---

## Ajustes Possíveis Pós-Implementação

<A preencher se surgir algo durante a implementação/validação.>
