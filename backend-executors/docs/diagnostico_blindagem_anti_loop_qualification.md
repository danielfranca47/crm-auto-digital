# Diagnóstico — Blindagem Anti-loop da Qualification (sem implementação)

## Escopo analisado
- Runtime principal: `app/services/decision_engine.py`.
- Políticas pós-decisão: `app/services/handoff_policy.py` e `_sanitize_category_decision` no próprio decision engine.
- Contrato/estado: `app/schemas/decision.py` e `qualification_state` já persistido via `crm_client`.
- Evidência de comportamento atual: `tests/test_qualification_state_loop.py`.

---

## Checklist por regra

### Regra 1
**Regra:** se `missing_fields == []`, então `next_action` nunca pode ser `ask_qualification`.

- **Status atual:** **cobre parcialmente**.
- **O que já cobre hoje:**
  - Em `compose_decision_output`, quando `mother_route_to == "qualification"`, `missing_fields` vazio e `lead_current_category == "qualification"`, há auto-promotion para `effective_route_to = "apresentation"`, e isso muda `next_action` para `reply` (não `ask_qualification`).
- **Gap:**
  - A trava depende de `lead_current_category == "qualification"`.
  - Se a mãe continuar retornando `route_to="qualification"` com `missing_fields=[]` e categoria atual já estiver fora de qualification, ainda pode sair `ask_qualification`.

### Regra 2
**Regra:** se um campo já está em `qualification_state.data_json`, esse campo não pode ser o próximo perguntado.

- **Status atual:** **cobre parcialmente (com boa base)**.
- **O que já cobre hoje:**
  - `missing_fields` é calculado a partir de `required_fields - filled_fields` quando existe `qualification_state` com `data_json`; então um campo preenchido sai da lista de faltantes.
  - Fluxo de controle do anti-loop usa `current_field = missing[0]`, logo o "próximo campo" técnico já evita campos preenchidos **se** `missing_fields` estiver correto.
- **Gap:**
  - A filha qualification decide o texto livremente; ela é instruída a priorizar `missing_fields`, mas não existe sanitizer rígido para bloquear pergunta de campo já preenchido caso LLM "desobedeça".
  - Não há validação semântica do `message_text` contra `current_field` (intencionalmente, sem dedupe semântico).

### Regra 3
**Regra:** após promoção já ocorrida na conversa, não reavaliar qualification na mesma conversa (não voltar para `route_to=qualification`).

- **Status atual:** **não cobre**.
- **O que existe hoje e pode ser reutilizado:**
  - `decision_trace.qualification_auto_promoted` (observabilidade por execução).
  - `lead_current_category` no contexto e guardrails de avanço de categoria.
- **Gap principal:**
  - Não há "latch"/trava no início do `decide()` para impedir nova passagem em qualification após promoção.
  - `decision_trace` não é persistência confiável entre jobs; por si só não garante bloqueio em mensagens futuras.

---

## Onde aplicar cada blindagem

## Regra 1 — `missing_fields == [] => never ask_qualification`

### Local mais barato (menor patch)
- **`compose_decision_output(...)`**:
  - após calcular `missing_fields`, remover dependência de `lead_current_category == "qualification"` para auto-promotion.
  - condição-alvo mínima: `mother_decision.route_to == "qualification" and not missing_fields`.

### Local arquiteturalmente mais correto
- **Pré-roteamento em `decide(...)`**, antes de chamar filha qualification:
  - se rota mãe vier qualification e `missing_fields` vazio, trocar rota efetiva para apresentation já no runtime (ou pular child qualification).
  - evita custo/chance de gerar prompt da filha errada.

### Trade-off
- **Mais barato:** 1 patch pequeno, baixo risco de regressão estrutural, mantém fluxo atual de prompts.
- **Mais correto:** reduz custo de LLM e incoerência de rota, mas mexe no fluxo de orquestração (maior superfície de teste).

---

## Regra 2 — não perguntar campo já preenchido

### Local mais barato (menor patch)
- **`_build_mode_contract_context(...)`** já é a fonte correta: garantir que `filled_fields` considere apenas valores válidos (já considera via `_is_filled_value`).
- **`decide(...)` no bloco qualification**:
  - manter `current_field = missing[0]` como fonte única de `last_questioned_field`.
  - opcional mínimo: registrar log explícito com `current_field` e `filled_fields` para auditoria.

### Local arquiteturalmente mais correto
- **Sanitizer de saída de qualification (pós-child)**:
  - checar se resposta indica pergunta fora do `current_field` esperado e forçar rephrase/bloqueio.
  - porém isso exigiria heurística semântica de texto, que o escopo pediu evitar.

### Trade-off
- **Mais barato:** aproveita estrutura já existente de missing_fields (determinística), sem NLP extra.
- **Mais correto:** exigiria interpretação textual, aumenta complexidade e risco de falso positivo.

---

## Regra 3 — não voltar a qualification após promoção na mesma conversa

### Local mais barato (menor patch)
- **`decide(...)` após `mother_decision` validada e antes do bloco qualification/child prompt**:
  - se `mother_decision.route_to == "qualification"` e houver marcador de promoção prévia no contexto atual, sobrescrever rota efetiva para `apresentation`.

### Local arquiteturalmente mais correto
- **Guardrail de categoria/roteamento centralizado** (função dedicada):
  - aplicar "anti-regressão pós-promoção" no mesmo ponto que outros guardrails de stage.

### Trade-off
- **Mais barato:** if único no fluxo principal.
- **Mais correto:** mais limpo para manutenção, porém cria novo ponto de política e requer cobertura adicional.

---

## Marcador pragmático para Regra 3 (sem migrations)

Como não há `conversation_id` explícito garantido no runtime analisado, alternativa pragmática:

1. **Primário:** `lead_current_category` já em `apresentation` (ou acima) => bloquear retorno para qualification.
2. **Complementar de execução atual:** `decision_trace.qualification_auto_promoted` disponível apenas no resultado corrente (útil para logs/auditoria, não como única fonte).
3. **Opcional já existente no estado:** se `qualification_state.data_json` completo (`missing_fields=[]`), tratar qualification como concluída e bloquear nova rota qualification mesmo sem category atualizada ainda.

> Estratégia recomendada sem persistência nova: combinar `(mother route=qualification) AND (missing_fields vazio OR lead_current_category != qualification e já >= apresentation)` para forçar rota efetiva não-qualification.

---

## Riscos/regressões possíveis

- **handoff_policy.apply:** impacto **baixo**; só atua quando `next_action == handoff`. Blindagem proposta mexe principalmente em `ask_qualification` vs `reply`.
- **_sanitize_category_decision:** impacto **médio-baixo**; essa função zera categoria quando `ask_qualification`. Se reduzirmos `ask_qualification`, pode aumentar sugestão de categoria em cenários ambíguos (observar logs `suggested_category_final`).
- **Guardrails de categoria (`apply_mother_category_guardrails`)**: impacto **médio** se a rota efetiva for reescrita; garantir coerência entre `effective_route_to`, `suggested_category` e `category_reason`.
- **agent_mode (consultivo/agenda/direto):** impacto **médio**; em agenda/direto pode acelerar ida para apresentation sem perguntar algo que playbook esperava. Mitigar com condição estrita baseada em `missing_fields` vazio.
- **Risco de "silenciar" resposta:** baixo se mantermos fallback `next_action=reply` com `message_text` da filha correta. Risco sobe se bloquear qualification sem trocar prompt da filha (por isso ponto arquitetural de rotear antes do child é mais robusto).

---

## Plano mínimo de patch (1–3 alterações pequenas, sem refactor)

1. **Alteração 1 (obrigatória):**
   - Arquivo: `app/services/decision_engine.py`
   - Função: `compose_decision_output(...)`
   - Check: `if mother_decision.route_to == "qualification" and not missing_fields:`
   - Efeito: forçar `effective_route_to="apresentation"`, `next_action != ask_qualification`, setar `qualification_auto_promoted=True`.

2. **Alteração 2 (obrigatória para Regra 3):**
   - Arquivo: `app/services/decision_engine.py`
   - Função: `decide(...)`
   - Check logo após mother parse/validate:
     - `if mother_decision.route_to == "qualification" and anti_loop_promoted_latch:`
   - `anti_loop_promoted_latch` derivado sem migração de:
     - `lead.category` já em `apresentation|follow-up|closing`, **ou**
     - `missing_fields == []` no `mode_ctx` atual.
   - Efeito: usar rota efetiva `apresentation` para escolha de prompt child.

3. **Alteração 3 (observabilidade, recomendada):**
   - Arquivo: `app/services/decision_engine.py`
   - Funções: `decide(...)` e/ou `compose_decision_output(...)`
   - Add trace/log:
     - `anti_loop_rule1_applied`, `anti_loop_rule3_applied`, `current_field`, `missing_fields`, `effective_route_to`, `qualification_auto_promoted`.

Compatibilidade:
- Sem migration.
- Sem mudar contrato do webhook (`DecisionOutput` inalterado).
- Reuso de campos já existentes em `decision_trace`.

---

## Evidência objetiva para validação

## Logs esperados (por job)
Registrar/confirmar presença de:
- `job_id`, `lead_id`
- `missing_fields`
- `next_action`
- `effective_route_to`
- `qualification_auto_promoted`
- (novo) `anti_loop_rule1_applied`, `anti_loop_rule3_applied`

Formato pode aproveitar logs atuais de `decision_mother_category` + `decision llm` e enriquecer com os campos acima.

## Testes de evidência (manual/script)

- **T1 — missing_fields vazio**
  - Setup: qualification_state completo para required_fields do modo.
  - Esperado: `next_action != ask_qualification`; `effective_route_to=apresentation`; `qualification_auto_promoted=true`.

- **T2 — campo já preenchido não repete**
  - Setup: `qualification_state.data_json` com `decision_role` preenchido.
  - Esperado: `missing_fields` não contém `decision_role`; `current_field` aponta outro campo.

- **T3 — pós-auto-promotion não volta para qualification**
  - Setup: lead já em `apresentation` (ou missing_fields vazio) e mother retorna qualification em mensagem seguinte.
  - Esperado: guardrail anti-loop força rota efetiva não-qualification e não pergunta campo de qualification novamente.

---

## Conclusão executiva
- A base atual já resolve parte importante das regras 1 e 2 via `missing_fields` e auto-promotion.
- O principal buraco é a ausência de trava explícita para regra 3 entre mensagens/jobs.
- O menor patch seguro é concentrar checagens em `decision_engine.py` (compose + decide), sem refatoração, sem migration e sem alteração de contrato público.
