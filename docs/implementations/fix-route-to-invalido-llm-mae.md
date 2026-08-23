# Fix: LLM Mãe pode retornar `route_to` fora do enum aceite

**Branch:** `feat/playground-simular-nome-whatsapp`
**Status:** Aguardando Plan Mode

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

## Diagnóstico (a fazer em Plan Mode)

Ainda não investigado a fundo. Pontos de partida sugeridos:
- `backend-executors/app/services/orchestrator_models.py` — onde `mother_decision_invalid_enum_coerced` já existe para `perceived_category`; entender por que não protege `route_to` da mesma forma.
- `backend-executors/app/api/playground_internal.py` — ponto onde a validação falha e cai no fallback de `handoff`.
- Confirmar se o mesmo pode acontecer no caminho real (`routes/executor.py`), não só no Playground.

---

## Ajustes Possíveis Pós-Implementação

<Preencher durante o diagnóstico em Plan Mode.>
