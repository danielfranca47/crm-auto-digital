# Qualificação — score generalizado e presets

> Contexto: itens deixados de fora da graduação de
> `docs/implementations/qualificacao-flexivel-score-generalizado.md` (Fases 1-2
> graduadas em 13/08/2026 — captura de campos opcionais/custom + tolerância de
> extração configurável, ambas em produção). Fases 3 e 4 estavam desenhadas e
> validadas no plano, mas nunca implementadas — decisão do utilizador em
> 13/08/2026 foi adiar, porque as prioridades reais do pedido original (caso do
> cliente Gabriel Smith, ver `docs/architecture/pipeline-phases.md#qualification`)
> já estavam resolvidas nas Fases 1-2 e no fix anterior
> (`fix-qualificacao-obrigatoria-caminho-automatico.md`, também graduado).

---

## M1 — Score generalizado para campos custom (`qualifies_json`)

**Prioridade: BAIXA**

Hoje `qualification_score_threshold` só pontua 4 chaves fixas (`decision_role`,
`urgency`, `budget_or_price_acceptance`, `availability_window` —
`_4P_SCORABLE_KEYS` em `backend-crm/services/qualification_guardrails.py`).
Perfis 100% custom nunca acumulam score real, e o gate de score
(`can_advance_score_gate()`) pula a checagem inteiramente nesse caso.

**Por que é baixa prioridade:** o caminho recomendado para forçar qualificação
já funciona hoje sem esta mudança — marcar o(s) campo(s) relevante(s) como
`mode: "required"` em `qualification_fields` (isso já bloqueia `missing_fields`
e é o único sinal real que faz a LLM Mãe entrar em `qualification` — ver nota em
`pipeline-phases.md`). O score é um mecanismo secundário, só relevante para quem
quer usar *exclusivamente* score como critério sem marcar nada obrigatório.

**Desenho já validado (não implementado):**
- `field_extractor.py`: bloco de prompt adicional para campos com
  `qualify_if`/`disqualify_if` configurados; retorno ganha `"qualifies":
  {campo: yes|no|neutral}`
- `decision_engine.py`: fallbacks/patch para `crm_client` ganham `qualifies_json`
- `backend-crm/services/qualification_state.py`: novas
  `compute_custom_fields_score()`, `compute_qualification_max_score()`;
  `upsert_qualification_state()` ganha `ai_profile` opcional
- `backend-crm/database.py`: novas colunas `qualifies_json`, `custom_fields_score`
  em `lead_qualification_state`
- `qualification_guardrails.py`: `_score_below_threshold()` só pula o gate se não
  houver **nenhum** campo activo configurado (hoje pula sempre que nenhuma das 4
  chaves clássicas bate)
- `routes/leads.py`: `missing_fields_detail` passa a listar campos custom activos
  que faltam score

**Cenário de validação (não executado):** perfil 100% custom com `qualify_if`
configurado, score abaixo do threshold → `qualification_advance_blocked: true`;
após sinal positivo suficiente → avanço liberado.

---

## M2 — Presets deixam de vir `required` por padrão + banner de aviso

**Prioridade: MÉDIA (redesenhar antes de implementar — ver risco abaixo)**

Objetivo original: campos clássicos nos presets de sugestão (`SUGGESTIONS` em
`frontend-crm/src/components/agente/CamadaQualificacao.tsx`) passam de
`required` para `optional` por padrão (não retroactivo a perfis já
configurados), acompanhado de um banner de aviso quando o perfil fica com zero
campos `required`.

**Risco identificado durante o desenho original (ainda não resolvido):**
`missing_fields` (só de campos `required`) é o único sinal que faz a LLM Mãe
decidir `route_to="qualification"` (ver nota em `pipeline-phases.md`). Um perfil
com zero campos obrigatórios nunca aciona qualificação automática para uma
pergunta comercial directa — exactamente o bug que toda esta série de correcções
resolveu para o caso do Gabriel Smith. Aplicar esta fase como desenhada (presets
sem nenhum campo `required` por padrão) reproduziria esse mesmo bug para
**qualquer usuário novo que aceite o preset sem customizar**, mitigado só por um
banner de aviso passivo — não é uma prevenção real.

**Recomendação para quando isto for retomado:** não implementar como estava
desenhado sem rediscutir. Alternativas a considerar: manter ao menos 1 campo
`required` por preset (ex.: `service_interest` ou equivalente), ou exigir
confirmação explícita do utilizador em vez de um banner que pode passar
despercebido.

**Também nesta fase (independente do risco acima, pode seguir junto):**
corrigir a cópia "Cada campo qualificado vale 1 ponto" e o "/12" fixo em
`CamadaQualificacao.tsx:853,1210` — nunca foi verdade (algoritmo real é
keyword-scoring 0-3 por campo, restrito às 4 chaves fixas hoje; passaria a valor
máximo dinâmico se M1 for implementado primeiro).

---

## M3 — Didática do score na UI (exemplos concretos)

**Prioridade: BAIXA**

A correcção de copy do M2 só resolve a imprecisão factual do texto actual. Falta
uma explicação didáctica de verdade — hoje o usuário não tem como entender,
olhando só para o campo "Score mínimo", como as suas escolhas de configuração
(quantos campos marca como activos, uso de `qualify_if`/`disqualify_if`,
required vs. optional) mudam o score máximo possível e o que precisa acontecer
na conversa para bater o mínimo configurado.

**Melhoria proposta:** exemplos concretos lado a lado na UI (ex.: "Com 2 campos
custom configurados e `qualify_if` preenchido, o máximo passa a ser 18 pontos;
se o lead responder aos 2 com sinal positivo, score = 18 — se responder sem
sinal claro, score = 12"). Depende de M1 para fazer sentido em perfis custom.

---

## M4 — Badges/tooltips de transparência sobre o que cada campo "conta"

**Prioridade: BAIXA**

Hoje um campo chamado `decision_role` parece visualmente idêntico a um campo
custom qualquer na UI de Camada de Qualificação — nada indica que ele é uma das
chaves que o score automático sabe pontuar (`_4P_SCORABLE_KEYS`), nem que campos
`required` são o único sinal que faz a LLM Mãe decidir entrar em qualification
(não apenas uma trava de conclusão).

**Melhoria proposta:** badges/tooltips na lista de campos indicando (a) "conta
para o score automático" quando aplicável, (b) reforçar visualmente que
"Obrigatório" é o que aciona a qualificação automática.

---

## Nota lateral — bug relacionado, já rastreado em outro plano

`qualification_score_threshold` tem um bug de persistência conhecido e não
relacionado a este plano: `frontend-crm/src/services/api.ts` lê/escreve este
campo de dentro de `offer_pack` em vez da coluna de topo que o guardrail
(`qualification_guardrails.py`) realmente lê — o valor configurado pela UI pode
nunca chegar ao motor. Já documentado como Etapa J em
`docs/plans/pipeline-configurable-fields.md`, prioridade BAIXA lá. Vale
reconsiderar a prioridade desse item à luz de todo o trabalho desta série em
cima do mesmo campo.
