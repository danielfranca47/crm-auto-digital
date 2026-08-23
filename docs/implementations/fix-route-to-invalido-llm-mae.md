# Fix: LLM Mãe pode retornar `route_to` fora do enum aceite

**Branch:** `fix/route-to-invalido-llm-mae`
**Status:** Todos os cenários validados (23/08/2026)

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

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `88c3101` | Novo alias `"qualificacao"` + teste standalone |

**Detalhes do commit `88c3101`:**
- `backend-executors/app/services/orchestrator_models.py` — nova entrada em `_ROUTE_TO_ALIASES`
- `backend-executors/scripts/test_route_to_alias_coercion.py` — 3 casos: alias antigo, alias novo, valor desconhecido ainda falha

### Relatório da Fase 1 — o que mudou na prática

**Antes:** se a IA responsável por decidir o próximo passo da conversa (a "Mãe") escrevesse `qualificacao` em vez de `qualification` — só uma diferença de acentuação — o sistema todo travava aquela decisão e caía num modo de emergência que desliga o bot para aquele lead, achando que a resposta era inválida.

**Agora:** essa variação específica de grafia é reconhecida e corrigida automaticamente antes de travar, do mesmo jeito que já acontecia com outra variação conhecida (`presentation` em vez de `apresentation`). Qualquer outra grafia realmente desconhecida continua a cair no modo de emergência normalmente — isso é intencional, para não mascarar erros de verdade.

**Para validar:** o teste automatizado (`scripts/test_route_to_alias_coercion.py`) já cobre os 3 casos e passou. A falha original dependia de uma resposta específica e não-determinística da IA — não é possível forçá-la de novo ao vivo com confiança, então o teste automatizado é a validação de referência aqui (não há Cenário C/P adicional a marcar).

---

## Checks de Validação

### Cenário P1 — Aliases de `route_to` normalizados, valor desconhecido ainda falha
- [x] Rodar `scripts/test_route_to_alias_coercion.py`
- [x] Confirmar: alias antigo (`presentation`) e novo (`qualificacao`) normalizam corretamente
- [x] Confirmar: valor desconhecido (`foobar`) ainda levanta `ValidationError`
- **Validado em:** 23/08/2026 — `python scripts/test_route_to_alias_coercion.py` → `OK: aliases de route_to normalizados; valor desconhecido ainda levanta ValidationError`. Confirmado também que `backend-executors` importa e sobe normalmente com a mudança.

---

## Ajustes Possíveis Pós-Implementação

Nenhum.
