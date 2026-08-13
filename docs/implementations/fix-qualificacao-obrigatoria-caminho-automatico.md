# Fix: qualificação obrigatória sendo ignorada no caminho automático do bot

**Branch:** `fix/qualificacao-nao-obrigatoria-antes-apresentacao`
**Status:** Em andamento

---

## Motivação

Gabriel Smith (`gabrielsmith.original@gmail.com`, `user_id=3`, ai_profile `id=2`, cliente real em produção) configurou campos de qualificação e um "score" na Camada de Qualificação do AI Profile, esperando que o bot fosse obrigado a qualificar o lead antes de apresentar a oferta. Nos testes dele no Playground (transcrições anexadas pelo utilizador em 12/08/2026), depois da saudação (recepção) o bot pulou direto para apresentação — sem passar por qualificação — mesmo com o score configurado.

Comportamento esperado: se há campos obrigatórios ou um score mínimo configurado e ainda não atingido, o bot deveria permanecer em qualificação até completar o critério.

---

## Problemas Identificados (estado anterior)

Investigação de código (`decision_engine.py`, `qualification_guardrails.py`, `routes/leads.py`, `routes/playground.py`, `routes/executor.py`, `jobs_service.py`) combinada com leitura direta da produção (`railway ssh -s backend-core`, `/data/core.db`, autorizado pelo utilizador) para confirmar a config real do ai_profile do Gabriel.

**Config real confirmada (produção):**
- `qualification_fields`: 2 campos custom (`custom_uso_do_produto`, `custom_pergunta_de_endereco`), **ambos `"mode": "optional"`** — nenhum marcado `"required"`.
- `qualification_score_threshold`: 6 (coluna) / 2 (dentro de `offer_pack`, valor legado duplicado).

1. **Nenhum campo marcado `required`, então `missing_fields` nunca bloqueia (comportamento correto, não é bug):** `backend-executors/app/services/decision_engine.py:1310-1323` (`_get_required_fields_override`) só inclui campos com `mode=="required"`. Sem isso, `missing_fields` é sempre `[]` e `_enforce_qualification_route_when_missing()` (`decision_engine.py:3879-3892`) nunca força `route_to="qualification"`. O sistema está a respeitar exatamente o que foi configurado.

2. **Gap real — o guardrail de score só existe no caminho manual (bug):** `can_advance_from_qualification()` (`backend-crm/services/qualification_guardrails.py:69-140`) é a função que compara `qualification_score_threshold` com `qualification_total_score` do lead. Ela só é chamada em dois lugares, **ambos manuais/HTTP**:
   - `backend-crm/routes/leads.py:543` (transição assistida apresentation→follow-up)
   - `backend-crm/routes/leads.py:941` (`PATCH /api/leads/{id}`, usado quando um operador arrasta o card no Kanban)

   **Nunca é chamada no caminho automático do bot:**
   - Playground: `backend-crm/routes/playground.py:652-654` chama `_update_lead_category()` — um `UPDATE` direto na tabela `leads`, sem nenhum guardrail.
   - WhatsApp real: `backend-crm/routes/executor.py:857-866` chama `apply_suggested_category()` (`backend-crm/services/jobs_service.py:953`), que só verifica `_check_inbound_signal` (keywords fortes no texto inbound) — nunca o score nem campos obrigatórios.

   Ou seja: o score configurado pelo Gabriel só protegia o operador arrastando o card manualmente. Quando é o próprio bot que decide avançar durante a conversa automática — exatamente o cenário testado — nada verificava score nem completude.

3. **Limitação arquitetural relacionada, fora do escopo desta fase:** mesmo com o gap acima corrigido, o score configurado pelo Gabriel **ainda não seria aplicado ao caso dele**, porque `can_advance_from_qualification()` só calcula score a partir de 4 chaves hardcoded (`decision_role`, `urgency`, `budget_or_price_acceptance`, `availability_window` — `qualification_guardrails.py:131`). Como os campos dele são 100% custom, a função detecta que nenhuma chave configurada bate com as 4P e pula o check de score de propósito (`qualification_guardrails.py:134-135`, para não travar permanentemente perfis 100% custom). Registrado em "Ajustes Possíveis" abaixo.

4. **Bug de crash independente, encontrado durante a investigação:** `backend-crm/routes/executor.py:329-335`, o branch `advance_phase` do Fluxo de Venda (Camada 7) chama `apply_suggested_category(...)` sem passar `inbound_message_text`, que é kwarg obrigatório sem default em `jobs_service.py:953-964`. Isso lança `TypeError` sempre que um bloco `avancar_fase` dispara de verdade no WhatsApp real. Gabriel não usa Fluxo de Venda com `avancar_fase` (confirmado por ele), então não é a causa do caso dele, mas é um crash real para quem usa.

---

## Abordagem

**Achado a meio da implementação que mudou o escopo:** o teste `test_apply_suggested_category_allows_advance_without_pipeline_guardrail` documentava uma decisão deliberada de 05/04/2026 (commit `511d9c9`, "audit: Fase 5 — isolar guardrail de qualificação"): `can_advance_from_qualification()` foi removida de propósito de `apply_suggested_category` (pipeline da IA) porque campos obrigatórios já são verificados em `decision_engine.py` antes de a IA decidir avançar — checar de novo em `apply_suggested_category` seria redundante, e o objetivo maior documentado era ter `qualification_fields` como única fonte de verdade, sem lógica "hardcoded" duplicada fora desse contrato. Reintroduzir a função inteira reverteria essa decisão. Como o **score de 4Ps é um mecanismo separado** (não tem equivalente em `decision_engine.py`), a correção ficou restrita a **só o score**, preservando o isolamento de campos obrigatórios que a Fase 5 quis.

Fechar o gap de paridade apenas para o score: fazer `qualification_score_threshold` valer também no caminho automático do bot — não só no drag manual do Kanban.

```
Bot decide avançar categoria (qualification → apresentation/follow-up/closing)
  ├─ Playground:      playground.py, antes de _update_lead_category(...)
  └─ WhatsApp real:   jobs_service.py, dentro de apply_suggested_category(...)
       ├─ campos obrigatórios pendentes? → decision_engine.py já cuida disso antes (inalterado)
       ├─ score abaixo do threshold (quando há chave 4P compatível configurada)? → bloqueia, mantém em qualification, loga o motivo
       └─ tudo completo → aplica a transição normalmente
```

`backend-crm/services/qualification_guardrails.py` foi refatorado (sem mudar o comportamento de `can_advance_from_qualification`, usada só pelo `PATCH` manual) para extrair a checagem de score isolada:
- `_score_below_threshold(ai_profile, total_score)` — lógica de score pura (chave 4P compatível configurada? score >= threshold?), compartilhada pelos dois caminhos.
- `can_advance_score_gate(conn, lead_id, user_id)` — nova função pública, só score, sem verificar campos obrigatórios nem herdar o atalho "`qualification_required_fields=[]` → pula score também" (esse atalho permanece só em `can_advance_from_qualification`, para o `PATCH` manual). `qualification_score_threshold` é uma configuração independente de campos obrigatórios — o usuário pode querer o score como único critério.

Não mexe em `decision_engine.py` (backend-executors) — esse serviço não tem acesso direto ao SQLite do backend-crm nem ao `core_client` completo da forma que `qualification_guardrails.py` usa. Gating na camada de persistência (backend-crm, onde a categoria realmente é gravada) é o ponto único e correto; os dois call sites (Playground + executor real) convergem para lá.

**Trade-off aceito conscientemente:** se o bot já gerou uma resposta no estilo "apresentação" no mesmo turno em que a promoção foi barrada, a mensagem já foi enviada — bloquear a categoria não desfaz isso retroativamente. Mesma limitação que o `PATCH` manual já tem hoje. Cobre o efeito prático mais importante: o lead não fica preso em "apresentação" pulando qualificação nos turnos seguintes.

**Limitação que permanece, mesmo após esta fase (confirmado por teste):** o score continua não fazendo nada para perfis 100% custom, como o do Gabriel — `_score_below_threshold` só ativa quando pelo menos 1 campo configurado bate com as 4 chaves hardcoded (`decision_role`, `urgency`, `budget_or_price_acceptance`, `availability_window`). Ver "Fora do escopo" abaixo.

---

## Plano de Implementação

### Fase 1 — Gate de score no caminho automático + visibilidade no trace

**Objetivo:** o bot (Playground e WhatsApp real) passa a respeitar `qualification_score_threshold` antes de mover um lead de `qualification` para `apresentation`/`follow-up`/`closing` (quando há chave 4P compatível configurada), igual ao que já acontece no `PATCH` manual. Campos obrigatórios continuam fora do escopo do pipeline automático — decision_engine.py já cuida disso, e re-checar aqui reverteria a decisão da Fase 5 histórica (ver "Abordagem").

| Arquivo | O que muda |
|---|---|
| `backend-crm/services/qualification_guardrails.py` | Refatorado: extrai `_score_below_threshold()` e `_load_lead_mode_and_score()` como helpers compartilhados; adiciona `can_advance_score_gate()` (só score, sem campos obrigatórios); `can_advance_from_qualification()` mantém o comportamento original (usa os mesmos helpers por baixo). Nova constante pública `QUALIFICATION_GATED_CATEGORIES`. |
| `backend-crm/services/jobs_service.py` | `apply_suggested_category()`: antes do `UPDATE`, se categoria atual é `qualification` e a nova é `apresentation`/`follow-up`/`closing`, chama `can_advance_score_gate()`. Se bloqueado, loga e retorna sem aplicar. |
| `backend-crm/routes/playground.py` | Antes de `_update_lead_category(...)` para a categoria sugerida pela decisão: mesma checagem via `can_advance_score_gate()`. Se bloqueado, não move a categoria e expõe o motivo no payload de trace devolvido ao frontend. |
| `backend-crm/routes/executor.py` | `advance_phase` (linha ~329): corrige o crash, passando `inbound_message_text=` (thread through em `_dispatch_system_actions`). |
| `backend-crm/tests/test_qualification_integrity_guardrails.py` | Atualiza o comentário do teste que documentava o isolamento da Fase 5 (esclarece que continua valendo só para campos obrigatórios); adiciona 2 testes novos: score bloqueia quando há chave 4P compatível; score não bloqueia com campos 100% custom (documenta a limitação conhecida). |
| Trace do Playground (`DecisionTrace`/`_build_decision_trace` em `playground.py`) | Passa a expor `required_fields`/`missing_fields`/`qualification_total_score`/`qualification_score_threshold`/`qualification_advance_blocked`/`qualification_advance_blocked_reason`. |

---

## Checks de Validação

### Cenário P1 — Campo obrigatório configurado, bot não pula qualificação
- [ ] AI Profile de teste local com config equivalente à do Gabriel (`sdr_padrao`, `agent_mode=sdr_scheduler`, `response_style=passive`, mesmos 2 `qualification_fields` custom), mas com 1 campo marcado `required`
- [ ] Playground: mensagem inicial pedindo orçamento de um produto específico
- [ ] Confirmar: bot vai para qualificação, não pula pra apresentação

### Cenário P2 — Config idêntica à do Gabriel (0 campos required, score configurado, chaves não-4P)
- [ ] Mesmo AI Profile, replicando a config real dele (2 campos `optional`, `qualification_score_threshold=6`)
- [ ] Confirmar: comportamento documentado — sem campo required e sem chave 4P, o score continua sendo pulado (não corrigido nesta fase); serve para confirmar que não há regressão de comportamento não intencional

### Cenário P3 — Score com chaves 4P compatíveis, abaixo do threshold
- [ ] AI Profile de teste com `qualification_required_fields=[]`, `qualification_fields` usando pelo menos 1 chave 4P (ex.: `availability_window`), `qualification_score_threshold` alto
- [ ] Simular conversa que não atinge o score
- [ ] Confirmar: bot fica bloqueado em qualification (antes do fix, isso pulava — é o caso que a Fase 1 corrige de fato)

### Cenário C1 — Fluxo de Venda `avancar_fase` não crasha mais
- [ ] AI Profile com bloco `avancar_fase` na Camada 7 configurado para disparar
- [ ] Confirmar via logs do executor que não há mais `TypeError` por falta de `inbound_message_text`

---

## Ajustes Possíveis Pós-Implementação

- **Score não funciona para `qualification_fields` 100% custom** — causa mais provável de o Gabriel achar que tinha um score válido configurado. Corrigir exigiria generalizar `compute_4p_scores()` para pontuar campos custom (possivelmente usando `qualify_if`/`disqualify_if`, já existentes no schema de `qualification_fields`, hoje só injetados como texto no prompt, nunca convertidos em pontuação estruturada). Escopo maior — decisão de priorização pendente do utilizador.
- **Ação imediata recomendada para o Gabriel, sem esperar deploy:** marcar pelo menos 1 dos 2 campos dele como "Obrigatório" em vez de "Desejável" na Camada de Qualificação — já funciona hoje, independente desta fase.
