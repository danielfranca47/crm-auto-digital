# Qualificação flexível + score generalizado

**Branch:** `fix/qualificacao-nao-obrigatoria-antes-apresentacao`
**Status:** Em andamento

---

## Motivação

Item deixado em aberto na graduação de
`docs/implementations/fix-qualificacao-obrigatoria-caminho-automatico.md`
(removido nessa graduação): o score de qualificação
(`qualification_score_threshold`) só pontua 4 chaves fixas (`decision_role`,
`urgency`, `budget_or_price_acceptance`, `availability_window`) via
keyword-matching hardcoded — campos custom (como os do cliente Gabriel Smith)
nunca contribuem para o score, e o gate de score é pulado inteiramente
quando o perfil só usa campos custom.

Investigando o código para desenhar essa correção, dois problemas
adicionais e relacionados na raiz foram levantados pelo utilizador:

1. **Captura incompleta**: a extração automática de respostas de
   qualificação (`field_extractor.py::extract_fields_llm()`, uma chamada LLM
   dedicada e já separada da Mãe/Filha) só considera campos marcados
   `required` — respostas a campos `optional`/custom nunca são persistidas
   em `lead_qualification_state`, mesmo quando a LLM as interpreta
   corretamente. Isso é a causa raiz de o bot "ignorar" respostas do lead a
   perguntas de qualificação não-obrigatórias.
2. **Rigidez de interpretação**: os limiares de confiança do extractor
   (0.4/0.6) e os enums fechados do schema (`decision_role:
   "owner|partner|employee|other|null"`) são hardcoded, sem espaço para o
   utilizador calibrar o quão literal a extração deve ser.

Escopo confirmado com o utilizador:
- "Itens padrão obrigatórios" que devem virar sugeridos = só os filtros
  clássicos (tomador de decisão, disponibilidade, urgência, etc.) —
  mudança nos **presets sugeridos no frontend**, não retroativa para
  perfis já configurados em produção.
- Tolerância de interpretação: configurável, **default no máximo de
  flexibilidade** (não tratar respostas apenas no literal), ajustável pelo
  utilizador na Camada de Qualificação se quiser mais rigor.

Não existe "segunda LLM" a ser criada do zero — `field_extractor.py`
já cumpre esse papel (chamada isolada, prompt próprio, não é a Mãe nem a
Filha). O trabalho é fechar os gaps concretos nela, generalizar o score, e
ajustar os presets do frontend.

---

## Problemas Identificados (estado anterior)

1. **Score só pontua 4 chaves fixas:** `backend-crm/services/qualification_state.py:81-120`
   (`compute_4p_scores`) — keyword-matching PT hardcoded só para
   `decision_role`/`urgency`/`budget_or_price_acceptance`/`availability_window`.
   Qualquer outra chave nunca entra no cálculo.

2. **Gate de score pulado para perfis 100% custom:** `backend-crm/services/qualification_guardrails.py:111-123`
   (`_score_below_threshold`) — se nenhuma chave configurada bate com as 4
   fixas, retorna `(True, [])` sem checar nada.

3. **Extractor só captura campos `required`:** `backend-executors/app/services/decision_engine.py:4606-4637`
   — `fields_schema` (o que é pedido ao extractor) e o filtro `new_extracted`
   (o que é persistido) usam só `required_fields`. Respostas a campos
   `optional`/custom são extraídas com sucesso pela LLM mas descartadas
   antes de chegar em `lead_qualification_state.data_json`.

4. **Limiares de confiança e enums rígidos hardcoded:** `backend-executors/app/services/field_extractor.py:86-87`
   (thresholds 0.4/0.6 no texto do prompt) e linha 9-16 (`DEFAULT_FIELD_SCHEMA`
   com enums fechados tipo `owner|partner|employee|other|null`) — sem
   nenhuma forma de o utilizador calibrar o quão literal a interpretação
   deve ser.

5. **`qualify_if`/`disqualify_if` nunca viram sinal estruturado:**
   `backend-executors/app/services/decision_engine.py:683-711` — só
   injetados como texto livre no prompt da Filha de Qualification, nunca
   convertidos em pontuação.

6. **Cópia da UI incorreta:** `frontend-crm/src/components/agente/CamadaQualificacao.tsx:853,1210`
   — afirma "Cada campo qualificado vale 1 ponto", o que nunca foi verdade
   (o algoritmo real é keyword-scoring 0-3 por campo, restrito às 4 chaves
   fixas).

7. **Presets do frontend marcam campos clássicos como obrigatórios por
   padrão:** `frontend-crm/src/components/agente/CamadaQualificacao.tsx:14-47`
   (`SUGGESTIONS`) — `decision_role`, `availability_window`, `urgency`
   vêm `mode: 'required'` em vários presets, tornando o guardrail de
   `missing_fields` mais rígido do que o necessário quando combinado com o
   gap #3 acima (resposta dada mas não capturada = trava percebida como bug).

---

## Abordagem

```
Lead responde pergunta de qualificação (Playground ou WhatsApp real)
  → decision_engine.py: route_to == "qualification"
      → field_extractor.extract_fields_llm(context, fields_schema)
          [Fase 1] fields_schema agora inclui TODOS os campos ativos
                    (required + optional), não só required
          [Fase 2] prompt usa threshold/instrução de qualification_extraction_tolerance
                    (default "flexivel") em vez de 0.4/0.6 fixos
          [Fase 3] retorno ganha "qualifies": {campo: yes|no|neutral}
                    para campos com qualify_if/disqualify_if configurados
      → persistido em lead_qualification_state (backend-crm)
          [Fase 1] campos opcionais/custom agora chegam em data_json
          [Fase 3] qualifies_json + custom_fields_score somam ao score total
      → missing_fields/anti-loop/HTTP 409 continuam baseados só em required_fields
        (inalterado em todas as fases — só o que é CAPTURADO muda, não o que BLOQUEIA)
      → can_advance_score_gate() (qualification_guardrails.py)
          [Fase 3] deixa de pular o gate quando o perfil só tem campos custom

Configuração (frontend, Camada de Qualificação)
  [Fase 4] presets sugeridos (decisor/disponibilidade/urgência) passam a
           default "optional" em vez de "required" — usuário ainda pode
           marcar manualmente como obrigatório se quiser
```

---

## Plano de Implementação

### Fase 1 — Captura de campos ativos (não só `required`)

**Objetivo:** `extract_fields_llm()` passa a poder capturar qualquer campo
`mode in ("required", "optional")` de `qualification_fields`, não só os
`required`. Não muda `missing_fields`/bloqueio HTTP 409/anti-loop.

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/decision_engine.py` | Nova função `_get_active_fields_for_extraction(context)`; `fields_schema`/`new_extracted` usam a união de `required_fields` + campos ativos; `has_progress` corrigido para continuar restrito a `required_fields` |

```python
# ANTES
fields_schema = {field: "string|number|object|null" for field in required_fields}
...
new_extracted = {k: v for k, v in extracted.items() if k in required_fields and _is_filled_value(v)}
...
has_progress = bool(new_extracted)

# DEPOIS
active_fields = list(required_fields)
for key in _get_active_fields_for_extraction(context):
    if key not in active_fields:
        active_fields.append(key)
fields_schema = {field: "string|number|object|null" for field in active_fields}
...
new_extracted = {k: v for k, v in extracted.items() if k in active_fields and _is_filled_value(v)}
...
has_progress = any(field in new_extracted for field in required_fields)
```

### Fase 2 — Tolerância de extração configurável

**Objetivo:** novo campo `qualification_extraction_tolerance` no AI Profile
(`"flexivel" | "equilibrado" | "rigoroso"`, default `"flexivel"`).

| Arquivo | O que muda |
|---|---|
| `backend-core/app/models/ai_profile.py` | Nova coluna `qualification_extraction_tolerance` |
| `backend-core/app/db.py` | Entrada em `ensure_ai_profile_columns()` |
| `backend-core/app/api/ai_profiles.py` | Enum `QualificationExtractionTolerance`; campo em `AIProfileBase`/`AIProfileUpdate` |
| `backend-executors/app/services/field_extractor.py` | `_TOLERANCE_THRESHOLDS`, `_TOLERANCE_INSTRUCTIONS`, `_resolve_tolerance()`, `_loosen_enum_schema()` |
| `frontend-crm/src/components/agente/CamadaQualificacao.tsx` | Novo controle para o utilizador escolher o nível |
| `docs/architecture/admin-agents-contract.md` | Documentar novo campo (regra do CLAUDE.md) |
| `backend-crm/routes/admin_agents.py` | Verificar se a whitelist de campos exibidos ao admin precisa incluir o novo campo |

### Fase 3 — Score generalizado para qualquer campo configurado

**Objetivo:** campos custom ativos passam a pontuar via sinal `qualifies`
(derivado de `qualify_if`/`disqualify_if`), sem alterar o algoritmo das 4
chaves clássicas.

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/field_extractor.py` | Bloco de prompt adicional para campos com `qualify_if`/`disqualify_if`; retorno ganha `"qualifies"` |
| `backend-executors/app/services/decision_engine.py` | Fallbacks e patch para `crm_client` ganham `qualifies_json` |
| `backend-crm/services/qualification_state.py` | `compute_custom_fields_score()`, `compute_qualification_max_score()`; `upsert_qualification_state()` ganha `ai_profile` opcional |
| `backend-crm/database.py` | Novas colunas `qualifies_json`, `custom_fields_score` em `lead_qualification_state` |
| `backend-crm/services/qualification_guardrails.py` | `_score_below_threshold()` só pula o gate se não houver nenhum campo ativo configurado; `_4P_SCORABLE_KEYS` importado de `qualification_state.py` |
| `backend-crm/routes/leads.py:565-578` | `missing_fields_detail` passa a listar também campos custom ativos que faltam score |
| `backend-crm/tests/test_qualification_integrity_guardrails.py` | Reescrever `test_apply_suggested_category_allows_advance_with_custom_fields_only` |

### Fase 4 — Presets padrão do frontend deixam de ser `required`

**Objetivo:** campos clássicos nos presets de sugestão (`SUGGESTIONS` em
`CamadaQualificacao.tsx`) passam de `required` para `optional`. Não afeta
perfis já configurados.

| Preset | Campo | Antes | Depois |
|---|---|---|---|
| `sdr_scheduler` | `decision_role` | required | optional |
| `sdr_scheduler` | `availability_window` | required | optional |
| `agenda` | `decision_role` | required | optional |
| `agenda` | `availability_window` | required | optional |
| `closer` | `decision_role` | required | optional |
| `direto` | `decision_role` | required | optional |
| `consultivo` | `urgency` | required | optional |

Também nesta fase: corrigir a cópia "Cada campo qualificado vale 1 ponto" e
o "/12" fixo (`CamadaQualificacao.tsx:853,1210`) para refletir o mecanismo
pós-Fase 3, com valor máximo dinâmico.

---

## Checks de Validação

### Cenário P1 — Campo opcional é capturado e persistido
- [ ] Perfil com um campo `mode="optional"` custom configurado
- [ ] Playground: responder à pergunta desse campo
- [ ] Confirmar via `GET /api/leads/{id}/qualification-fields` que o valor foi persistido
- [ ] Confirmar que a categoria não é bloqueada por causa dele (continua fora de `missing_fields`)

### Cenário P2 — Tolerância flexível captura resposta não-literal
- [ ] Perfil com `qualification_extraction_tolerance` no default (`flexivel`)
- [ ] Playground: responder a `decision_role` com frase que não usa os termos do enum (ex.: "sou eu mesmo que decido")
- [ ] Confirmar que o campo é capturado mesmo sem correspondência literal

### Cenário P3 — Score generalizado bloqueia e libera perfil 100% custom
- [ ] Perfil 100% custom com `qualify_if` configurado, score abaixo do threshold
- [ ] Confirmar: `qualification_advance_blocked: true`
- [ ] Após sinal positivo suficiente: confirmar avanço

### Cenário P4 — Presets sugeridos não vêm mais como obrigatórios
- [ ] Abrir Camada de Qualificação, aplicar sugestão para cada `agent_mode`
- [ ] Confirmar que os campos da tabela da Fase 4 aparecem como "Opcional"/"Desejável"

---

## Ajustes Possíveis Pós-Implementação

- **Didática do score na UI:** a correção de copy da Fase 4 só resolve a
  imprecisão factual do texto atual ("Cada campo qualificado vale 1
  ponto" → texto correto). Falta uma explicação didática de verdade — o
  usuário não tem hoje como entender, olhando só para o campo "Score
  mínimo", como suas escolhas de configuração (quantos campos marca como
  ativos, quais usa `qualify_if`/`disqualify_if`, required vs. optional)
  mudam o score máximo possível e o que precisa acontecer na conversa para
  bater o mínimo configurado. Melhoria proposta: adicionar exemplos
  concretos lado a lado na UI (ex.: "Com 2 campos custom configurados e
  `qualify_if` preenchido, o máximo passa a ser 18 pontos; se o lead
  responder aos 2 com sinal positivo, score = 18 — se responder sem sinal
  claro, score = 12"). Não bloqueante para as Fases 1-4.
