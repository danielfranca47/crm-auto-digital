# Fix: qualificação obrigatória sendo ignorada no caminho automático do bot

**Branch:** `fix/qualificacao-nao-obrigatoria-antes-apresentacao`
**Status:** Todos os cenários validados, incluindo Fase 2 (13/08/2026) — pendente: decisão do utilizador sobre o item em "Ajustes Possíveis" (score para campos 100% custom) antes da graduação

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

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `f872662` | Gate de score no caminho automático (Playground + WhatsApp real) + fix de crash em `advance_phase` + visibilidade no trace |
| 2 | `4b2ac22` | Fix encontrado ao validar ao vivo: gate também na 2ª chamada do Playground (saudação composta) + `QUALIFICATION_GATED_CATEGORIES` passa a incluir pré-agendamento/agendamento |

**Detalhes do commit `f872662`:**
- `backend-crm/services/qualification_guardrails.py` — extrai `_score_below_threshold()`/`_load_lead_mode_and_score()`; adiciona `can_advance_score_gate()` e `QUALIFICATION_GATED_CATEGORIES`; `can_advance_from_qualification()` inalterada em comportamento
- `backend-crm/services/jobs_service.py` — `apply_suggested_category()` chama `can_advance_score_gate()` antes de mover para fora de `qualification`
- `backend-crm/routes/playground.py` — mesma checagem antes de `_update_lead_category()`; `DecisionTrace` expõe campos novos de qualificação
- `backend-crm/routes/executor.py` — `advance_phase` passa `inbound_message_text` (crash corrigido)
- `backend-crm/tests/test_qualification_integrity_guardrails.py` — 2 testes novos + comentário do teste antigo atualizado

**Detalhes do commit `4b2ac22`** (achado durante validação ao vivo — ver "Relatório da validação" abaixo):
- `backend-crm/routes/playground.py` — a 2ª chamada síncrona do Playground (quando a 1ª mensagem tem saudação + pedido comercial embutido, "saudação composta") não passava pelo gate; corrigido
- `backend-crm/services/qualification_guardrails.py` — `QUALIFICATION_GATED_CATEGORIES` ampliada para incluir `pre-agendamento`/`agendamento` (decision_engine.py pode saltar direto pra essas fases num único turno)

### Relatório da validação ao vivo (13/08/2026)

Subi os 3 backends localmente (`backend-core`, `backend-crm`, `backend-executors` — a venv do `backend-executors` teve que ser isolada do Python global durante o processo, ver nota abaixo) e testei via chamadas diretas ao `POST /api/playground/chat`, usando a conta de teste (`_conta-teste-local.md`, `ai_profile_id=5`), reconfigurando `qualification_fields`/`qualification_required_fields`/`qualification_score_threshold` por SQL direto no `core.db` local entre cada cenário.

**Bug pego durante a validação, corrigido no commit `4b2ac22`:** o primeiro teste do Cenário P3 (mensagem com saudação + pergunta comercial na mesma frase) revelou que o gate só tinha sido aplicado na 1ª chamada de decisão do Playground — a "saudação composta" reenfileira a parte comercial como uma 2ª chamada síncrona, e essa 2ª chamada (onde a categoria de fato avança na prática) não tinha o gate. O lead pulou direto de `qualification` para `pre-agendamento` nesse teste. Corrigido e reconfirmado.

**Nota de ambiente (não relacionada ao fix):** `backend-executors` não tem venv própria e usa o Python global — esse Python global estava com `fastapi==0.116.2` incompatível com `starlette==1.3.1` já instalado (pré-existente, não causado por esta mudança). Criei uma venv isolada para `backend-executors` (mesmo padrão que `backend-crm`/`backend-core` já têm) para não depender mais do Python global. O Python global ficou com `starlette` numa versão diferente da original (`0.48.0` em vez de `1.3.1`) — vale o utilizador conferir se isso afeta outras ferramentas dele (gradio, sse-starlette/MCP apareceram como conflito nos avisos do pip).

### Relatório da Fase 1 — o que mudou na prática

**Antes:** o "score" configurado na Camada de Qualificação (`qualification_score_threshold`) só era respeitado quando um operador arrastava o card manualmente no Kanban. Quando era o próprio bot que decidia avançar a conversa — no Playground ou no WhatsApp real — nada verificava o score, então o lead podia pular de qualificação direto para apresentação mesmo com o score configurado e não atingido.

**Agora:** o bot (Playground e WhatsApp real) verifica o score antes de avançar, do mesmo jeito que o drag manual do Kanban já fazia. Se o score estiver configurado com pelo menos um campo compatível (as 4 chaves clássicas: papel de decisão, urgência, orçamento/aceite de preço, disponibilidade) e o lead ainda não atingiu o mínimo, o bot fica em qualificação em vez de avançar.

**Limitação que continua existindo (não é bug novo, é o mesmo score legado):** para perfis que usam só campos 100% personalizados — como o do Gabriel — o score continua não fazendo nada, porque o cálculo de pontuação só sabe reconhecer aquelas 4 chaves clássicas, não campos customizados. Para o caso específico do Gabriel, a solução imediata (sem precisar de deploy) é marcar pelo menos 1 dos 2 campos dele como "Obrigatório" em vez de "Desejável" — isso já funciona hoje e não depende desta correção.

**Para validar:** Cenários P1, P2, P3 e C1, abaixo.

---

## Checks de Validação

### Cenário P1 — Campo obrigatório configurado, bot não pula qualificação
- [x] AI Profile de teste local (`ai_profile_id=5`, `template_key=hybrid_scheduler`, `agent_mode=agenda`) com 1 campo `qualification_fields` marcado `required` (`service_interest`)
- [x] Playground: mensagem vaga sem mencionar serviço ("Oi, me passaram esse contato, será que vocês conseguem me ajudar?")
- [x] Confirmar: bot fica em `qualification` (`missing_fields: ["service_interest"]`, `category: "qualification"`)
- **Validado em:** 13/08/2026 — lead 450. (1ª tentativa com uma mensagem que mencionava "preço e como funciona" acabou preenchendo `service_interest` via extração automática do próprio texto — não é bug, é o extractor funcionando; refeito com mensagem vaga para isolar o cenário certo.)

### Cenário P2 — Config idêntica à do Gabriel (0 campos required, score configurado, chaves não-4P)
- [x] Mesmo AI Profile, replicando a config real dele (`custom_uso_do_produto`/`custom_pergunta_de_endereco`, ambos `optional`, `qualification_score_threshold=6`)
- [x] Confirmar: comportamento documentado — sem campo required e sem chave 4P, o score continua sendo pulado (não corrigido nesta fase)
- **Validado em:** 13/08/2026 — lead 447, `category: "apresentation"`, `qualification_advance_blocked: false`. Confirma a limitação documentada, sem regressão.

### Cenário P3 — Score com chaves 4P compatíveis, abaixo do threshold
- [x] AI Profile de teste com `qualification_required_fields=[]`, `qualification_fields=[{"key":"availability_window","mode":"optional"}]`, `qualification_score_threshold=6`
- [x] Mensagem com pedido comercial direto (lead novo, score parte de 0)
- [x] Confirmar: bot fica bloqueado em `qualification` (antes do fix, isso pulava — é o caso que a Fase 1 corrige de fato)
- **Validado em:** 13/08/2026 — lead 445, `category: "qualification"`, `qualification_advance_blocked: true`, `qualification_advance_blocked_reason: ["score_0_of_12_below_threshold_6"]`. 1ª tentativa (lead 444) revelou o bug da 2ª chamada (ver commit `4b2ac22`); reconfirmado depois da correção.

### Cenário C1 — Fluxo de Venda `avancar_fase` não crasha mais
- [x] Chamada direta a `_dispatch_system_actions()` (função real, não mock) com uma ação `advance_phase`
- [x] Confirmar: executa sem `TypeError` e move a categoria corretamente
- **Validado em:** 13/08/2026 — lead 450, categoria movida para `apresentation` sem exceção. Não testei via webhook WhatsApp real completo (exigiria simular todo o ciclo de job) — a chamada direta já exercita o código corrigido (`executor.py:329`) e a assinatura de `apply_suggested_category`.

---

## Ajustes Possíveis Pós-Implementação

- **Score não funciona para `qualification_fields` 100% custom** — causa mais provável de o Gabriel achar que tinha um score válido configurado. Corrigir exigiria generalizar `compute_4p_scores()` para pontuar campos custom (possivelmente usando `qualify_if`/`disqualify_if`, já existentes no schema de `qualification_fields`, hoje só injetados como texto no prompt, nunca convertidos em pontuação estruturada). Escopo maior — decisão de priorização pendente do utilizador.
- **Ação imediata recomendada para o Gabriel, sem esperar deploy:** marcar pelo menos 1 dos 2 campos dele como "Obrigatório" em vez de "Desejável" na Camada de Qualificação — já funciona hoje, independente desta fase.

---

## Fase 2 — Diagnóstico + Correção: extractor ignora o próprio limiar de confiança (13/08/2026)

### Problema identificado

Testando se a "ação imediata recomendada" acima (marcar campo como
`required`) realmente resolve o caso do Gabriel, reproduzi localmente um
AI Profile espelhando a config dele (`agent_mode=sdr_scheduler`,
`template=sdr_padrao`, 2 campos custom — desta vez `required`) e mandei a
mensagem real dele pelo Playground:

> "Vi 'Kit de Casa Pré-Fabricada em Madeira...' e quero um orçamento
> detalhado."

Resultado: o bot pulou qualificação de novo, mesmo com os campos
obrigatórios. Trace mostrou `filled_fields=['custom_uso_do_produto',
'custom_pergunta_de_endereco']` — o extractor (`field_extractor.py`)
**alucinou** as respostas: preencheu "endereço de entrega" com o texto
"orçamento detalhado" e "uso do produto" com o nome do produto. Isso
esvaziou `missing_fields`, e o código de auto-promoção
(`decision_engine.py:4696`) empurrou a resposta pra `apresentation` —
mesmo sintoma do bug original, causa diferente.

Causa raiz, confirmada lendo o código e testando ao vivo contra a LLM
real:

1. **Confiança nunca é verificada em código.** O prompt de
   `extract_fields_llm` (`field_extractor.py`) pede um score de confiança
   por campo ("confidence >= 0.4 é suficiente"), mas o valor nunca é
   comparado a esse limiar em lugar nenhum — busca no repo inteiro
   confirmou que `confidence_json` é só escrito e repassado
   (`qualification_state.py`), e explicitamente descartado pela rota do
   playground (`routes/playground.py`, `extra="ignore"`). Nada decide com
   base nele.
2. **A LLM extractora nunca via a pergunta configurada do campo** — só o
   nome da chave (`custom_pergunta_de_endereco`). Sem saber o que a chave
   significa, associava qualquer texto tematicamente próximo à pergunta.
3. **A instrução do prompt pressionava a LLM a "achar" algo:** "extraia
   TODOS que aparecerem no texto, mesmo sendo campos secundários" —
   incentivava match forçado em vez de permitir `null` quando a mensagem
   não respondia à pergunta.

### Correção

| Arquivo | Mudança |
|---|---|
| `backend-executors/app/services/field_extractor.py` | Nova `_field_questions()` lê `question`/`label` de `ai_profile.qualification_fields`; prompt passa a incluir a pergunta real de cada campo e exige resposta direta (menção genérica ao produto não conta); `extract_fields_llm()` filtra `extracted` por `confidence[key] >= threshold` antes de devolver (0.4 campos do perfil / 0.6 contexto padrão, fail-closed se não houver confidence) |
| `backend-executors/tests/test_field_extractor.py` | Novo arquivo — não existia cobertura direta deste módulo. 5 testes: confiança abaixo do limiar filtrada, acima mantida, ausente tratada como reprovada, threshold maior para campo de contexto padrão, pergunta configurada chega no prompt |
| `backend-executors/tests/test_qualification_state_loop.py` | Mock de `extract_fields_llm` no teste da Fase 1 de `qualificacao-flexivel-score-generalizado.md` passa a incluir `confidence` realista (antes tinha `{}`) |

Validei o wording do prompt ao vivo contra a LLM real antes de aplicar —
uma primeira versão mais rígida ("só extraia se responder literalmente")
rejeitou até respostas genuínas (falso negativo); a versão final aceita
respostas informais/breves desde que respondam de fato à pergunta.

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `c320e0e` | fix: extractor de qualificação passa a respeitar o próprio limiar de confiança |

### Relatório da Fase 2 — o que mudou na prática

**Antes:** quando um campo de qualificação (obrigatório ou não) era
customizado — não um dos 4 clássicos — a IA que tenta interpretar a
resposta do lead podia "inventar" uma resposta a partir de uma menção
apenas tangencial ao assunto (ex.: o lead citar o nome do produto contava
como resposta a "pra que você vai usar o produto"). Isso fazia o campo
parecer preenchido sem realmente ter sido, e o bot avançava para a
apresentação pulando a pergunta de verdade.

**Agora:** a IA só considera um campo respondido se o lead realmente deu
uma informação que responde à pergunta configurada — mesmo que de forma
breve ou informal. Uma menção só ao produto/assunto, sem responder de
fato, não conta mais, e o bot continua perguntando até ter uma resposta
real.

**Para validar:** Cenário P4, abaixo.

### Nota de ambiente

Backends locais já estavam de pé nesta sessão (Fase 1 anterior desta
mesma implementação). `backend-executors` precisou reiniciar (não usa
`--reload`) para carregar o fix.

---

## Checks de Validação (continuação — Fase 2)

### Cenário P4 — Extractor não alucina resposta a partir de menção tangencial
- [x] AI Profile espelhando o caso do Gabriel: `agent_mode=sdr_scheduler`, `template=sdr_padrao`, 2 campos custom `required` com perguntas configuradas ("Para que você vai usar o produto?" / "Qual o endereço de entrega?")
- [x] Playground: mensagem que só menciona o produto e pede orçamento, sem responder nenhuma das duas perguntas
- [x] Confirmar: `missing_fields` continua com os 2 campos, bot pergunta "Para que você vai usar o produto?" (não pula pra apresentation)
- [x] Enviar resposta genuína respondendo às duas perguntas → confirmar que os 2 campos são capturados com os valores corretos (não regrediu para falso negativo)
- **Validado em:** 13/08/2026 — lead 456. 1ª mensagem: `filled_fields=[]`, bot perguntou "Para que você vai usar o produto?". 2ª mensagem (resposta genuína): `GET /api/leads/456/qualification-fields` retornou `{"custom_uso_do_produto": "hospedagem de temporada", "custom_pergunta_de_endereco": "Rua das Flores 123 no Rio"}` — valores corretos, categoria avançou para apresentation normalmente.
