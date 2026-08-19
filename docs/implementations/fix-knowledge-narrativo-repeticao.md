# Fix: dedup de conteúdo narrativo da Base de Conhecimento (social_proof / pitch_script / product_details)

**Branch:** `fix-knowledge-narrativo-repeticao`
**Status:** Em andamento

---

## Motivação

Depois de corrigir o bug do `fire_once` do Fluxo de Venda (resolvido via configuração —
ver `docs/plans/sales-flow-fire-once-repeticao-prosa-melhorias-futuras.md`), testes reais do
utilizador (Teste 3 e Teste 4, 19/08/2026) revelaram um **segundo bug, de causa raiz
diferente**: o bloco de texto da Base de Conhecimento (Camada 4) injetado no prompt da IA
filha repete "prova social" / roteiro de pitch / detalhes do produto em **todo turno** da
fase apresentação, sem nenhum rastreamento de "já foi dito" — confirmado no Teste 3 (frase
de `social_proof` repetida em 3 turnos seguidos da mesma conversa) e agravado no Teste 4,
onde pedir "evite repetir" via `custom_instructions` não resolveu (e o modelo ainda violou a
blacklist, dizendo "estou aqui para ajudar").

A intenção da Base de Conhecimento, confirmada pelo utilizador, é ser um **recurso auxiliar
consultado quando necessário** (horários, argumentos de venda, depoimentos, bio do
profissional), não um roteiro repetido a cada rodada da fase. Algumas categorias (FAQ,
objeções, garantia, tabela de preços) já são corretamente condicionadas a "usar apenas se o
lead perguntar" — o problema está isolado a três categorias **narrativas**
(`social_proof`, `pitch_script`, `product_details`), que são informação para contar 1x, não
para responder sob demanda.

---

## Problemas Identificados (estado anterior)

1. **`_build_child_prompt_apresentation` sem dedup de knowledge narrativo**
   (`backend-executors/app/services/decision_engine.py:~2410-2994`): bloco
   `_apres_knowledge_parts`/`standard_knowledge_block` (~2663-2805) lê
   `knowledge_items.get("social_proof"|"pitch_script"|"product_details")` sem nenhum
   controle de "já mostrado" — reinjeta cru em todo turno da fase.
2. **Duplo caminho de injeção do mesmo texto**: `social_proof` é injetado tanto por
   `commercial_injection` (~2552-2578, ativo só quando `_auto_promoted_from_qual=True`)
   quanto pelo bloco on-demand (~2666-2679, ativo quando `not commercial_injection`) — os
   dois mutuamente exclusivos no mesmo turno, mas como `_auto_promoted_from_qual` pode ficar
   `True` em mais de um turno (gap já documentado em outro ponto do projeto), os dois
   caminhos precisam compartilhar o mesmo estado "já mostrado" entre turnos diferentes.
3. **Mesmo padrão em `_build_child_prompt_follow_up`** (~3178-3217), só para `social_proof`.
4. **Categorias reativas/FAQ não são o problema** — `objections_faq`, `service_faq`,
   `guarantee_policy`, `service_pricing_table`, `commercial_objections`,
   `service_differentials`, `active_promotion`, `payment_policy`, `pre_commitment_faq` já
   são corretamente condicionadas a "usar apenas se o lead perguntar X" — não devem ser
   tocadas por esta correção.

---

## Abordagem

Réplica do padrão já validado no repo para o mesmo tipo de problema
(`_evaluate_sales_flow_phases()` + `leads.triggers_fired` + `system_actions` tipo
`mark_trigger_fired`), aplicado agora a categorias de knowledge narrativas:

```
Turno N (categoria narrativa aparece pela 1ª vez)
    → conteúdo incluído no prompt normalmente
    → system_action mark_knowledge_shown[categoria] → BD atualizado (leads.knowledge_categories_shown)

Turno N+k (mesma categoria reavaliada, já em knowledge_categories_shown)
    → conteúdo OMITIDO do prompt (supressão silenciosa, sem nota — histórico da conversa +
      regra anti-repetição de _build_daughter_identity_block já cobrem o caso)

Categorias reativas/FAQ (objections_faq, service_faq, etc.)
    → nunca passam por este mecanismo, ficam disponíveis em todo turno como hoje
```

**Plumbing**: `compose_decision_output()` já rechama `_evaluate_sales_flow_phases()` de
forma independente da chamada feita dentro do prompt builder (uma vez para o texto, outra
para os `system_actions`) — replicado o mesmo padrão para a nova função de dedup.

---

## Plano de Implementação

### Fase 1 — Dedup completo (apresentation + follow_up)

**Objetivo:** suprimir repetição de conteúdo narrativo da Base de Conhecimento em turnos
subsequentes da mesma fase, sem afetar categorias reativas/FAQ.

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/decision_engine.py` | Nova função pura `_evaluate_narrative_knowledge_dedup()`; hooks em `_build_child_prompt_apresentation` (commercial_injection + knowledge_parts) e `_build_child_prompt_follow_up`; hook em `compose_decision_output` emitindo `mark_knowledge_shown` |
| `backend-crm/database.py` | `ensure_column(conn, "leads", "knowledge_categories_shown", "knowledge_categories_shown TEXT NULL")` |
| `backend-crm/routes/playground.py` | Novo helper `_mark_knowledge_shown()`; chamado nos dois loops de dispatch de `system_actions` |
| `backend-crm/routes/executor.py` | Novo bloco `elif atype == "mark_knowledge_shown":` em `_dispatch_system_actions()` |
| `backend-executors/tests/test_narrative_knowledge_dedup.py` (novo) | Testes unitários da função pura + integração com os prompt builders + `compose_decision_output` |

```python
# ANTES (decision_engine.py, dentro de _apres_knowledge_parts)
_social_proof_apres = knowledge_items.get("social_proof") or ""
_pitch_script_apres = knowledge_items.get("pitch_script") or ""
_product_details_apres = knowledge_items.get("product_details") or ""

# DEPOIS
_social_proof_apres = _narrative_dedup_apres["content"].get("social_proof") or ""
_pitch_script_apres = _narrative_dedup_apres["content"].get("pitch_script") or ""
_product_details_apres = _narrative_dedup_apres["content"].get("product_details") or ""
```

Detalhes completos (função de dedup, os 3 hooks, ensure_column, os 2 handlers de
persistência) estão no plano aprovado em `C:\Users\Daniel França\.claude\plans\ethereal-dazzling-perlis.md`.

---

## Checks de Validação

### Cenário — Unitário
- [ ] `pytest backend-executors/tests/test_narrative_knowledge_dedup.py -v` — todos os casos verdes
- [ ] `pytest backend-executors/tests -q` — suíte completa sem regressão (em especial `test_apresentation_ondemand_commercial_knowledge.py` e `test_apresentation_contextual_media.py`)

### Cenário P1 — Reprodução do Teste 3 real (Playground)
- [ ] Lead sandbox já em `category="apresentation"`, Base de Conhecimento com `social_proof` preenchido
- [ ] Turno 1: prova social aparece influenciando a resposta; `leads.knowledge_categories_shown` passa a conter `"social_proof"`
- [ ] Turnos 2 e 3 (mensagens diferentes, mesma fase): prova social não aparece mais; pergunta de FAQ/objeção explícita continua sendo respondida normalmente

### Cenário P2 — `commercial_injection`
- [ ] `_auto_promoted_from_qual=True` em 2 turnos seguidos do mesmo lead: bloco "MODO COMERCIAL" aparece nos dois, mas "PROVA SOCIAL" só no primeiro

---

## Ajustes Possíveis Pós-Implementação

- Dedup é por categoria, não por conteúdo — se o texto de `social_proof` for editado depois
  de já mostrado a um lead, esse lead nunca verá a versão nova (mesma limitação consciente
  de `triggers_fired`/`phases_triggered`, sem reset automático).
- Sem mecanismo de reset em reengajamento (lead que volta meses depois continua com a prova
  social suprimida). Fora do escopo desta correção.
