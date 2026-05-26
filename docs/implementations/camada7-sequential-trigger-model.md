# Implementação: Modelo Sequencial de Gatilho — Camada 7 (Sales Flow)

## Porquê

O utilizador queria configurar, na fase de Apresentação da Camada 7, que ao entrar na fase o sistema enviasse automaticamente uma **mensagem fixa + áudio** antes da resposta da filha LLM. Para isso configurou blocos na seguinte ordem:

```
[phase_trigger] → [mensagem] → [midia]
```

Nada acontecia. A investigação revelou que o sistema de blocos tipados (`_evaluate_sales_flow_phases`) tinha um bug estrutural: blocos de ação (`mensagem`, `midia`, `avancar_fase`, `webhook`, `espera`) **nunca eram executados**, porque o loop de avaliação só marcava como `triggered = True` os blocos de gatilho (`phase_trigger`, `kw_trigger`, `intent_trigger`) — todos os outros caíam no `if not triggered: continue`.

---

## O Que Estávamos Tentando

Implementar um **modelo de execução sequencial/herdado** (Sequential Inherited Trigger) onde:

- A sequência de blocos dentro de uma fase é processada em ordem
- Quando um bloco de gatilho é encontrado, ele é avaliado e o resultado atualiza um flag `last_trigger_active`
- Os blocos de ação subsequentes executam **se e somente se** `last_trigger_active == True`
- Por defeito (no início da lista, sem nenhum gatilho antes), `last_trigger_active = True` — ações puras de fase disparam automaticamente

**Regras práticas do novo modelo:**

| Configuração | Comportamento |
|---|---|
| Ação sozinha (sem gatilho antes) | Sempre dispara ao entrar na fase |
| `phase_trigger` → Ação | Sempre dispara (phase_trigger é sempre True) |
| `kw_trigger` que não fez match → Ação | **Não** dispara |
| `kw_trigger` que fez match → Ação | Dispara |
| Múltiplos gatilhos em sequência | Cada um governa as ações que vêm depois dele |

**Deficiências identificadas além do bug principal:**

1. **Bug crítico (Fase 1):** Blocos de ação nunca executam — `_evaluate_sales_flow_phases`, `decision_engine.py:325–466` ✅ **Corrigido**
2. **Deficiência (Fase 2):** Frontend sem agrupamento visual — `CamadaFluxoVenda.tsx` ✅ **Corrigido**
3. **Deficiência (Fase 3):** Bloco `midia` ignora `media_item_id` — **Não é problema real**: o frontend já persiste `media_url` ao selecionar da knowledge base (linha 258 do `CamadaFluxoVenda.tsx`)
4. **Futuro (Fase 4):** Bloco `condicao` armazenado mas não avaliado — branching Sim/Não inoperante — iteração futura

---

## Plano de Implementação

### Fase 1 — Backend: modelo sequencial (bug crítico)
**Ficheiro:** `backend-executors/app/services/decision_engine.py`
**Função:** `_evaluate_sales_flow_phases` (linhas 325–466)

Substituir o modelo de trigger independente:
```python
# ANTES — blocos de ação nunca executam
triggered = False
if type_id == "phase_trigger":
    triggered = True
if not triggered:
    continue
```

Por modelo sequencial:
```python
# DEPOIS — ações herdam o trigger anterior
last_trigger_active = True  # default: fase entrou

if type_id in ("phase_trigger", "kw_trigger", "intent_trigger", "no_reply_trigger"):
    fired = evaluate_trigger(block, ...)
    last_trigger_active = fired
    if fired:
        dispatch_prompt_injection(block, result)
else:
    if last_trigger_active:
        dispatch_action(block, result)
```

### Fase 2 — Frontend: agrupamento visual
**Ficheiro:** `frontend-crm/src/components/agente/CamadaFluxoVenda.tsx`

Renderizar blocos agrupados visualmente por gatilho (indentação/borda). Nenhuma mudança no modelo de dados.

### Fase 3 — Backend: resolução de `media_item_id` — Não necessária
O frontend já persiste `media_url` junto com `media_item_id` ao salvar um bloco `midia`. O backend usa `media_url` diretamente. Nenhuma alteração necessária.

### Fase 4 — Backend + Frontend: avaliação real de `condicao`
Requer mudança no modelo de dados (`branch_yes`/`branch_no` passam a ser listas de blocos). Iteração futura separada.

---

## Commits Realizados

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `50f38f9` | Fase 1 + 2 — modelo sequencial no backend + agrupamento visual no frontend |

**Detalhes do commit `50f38f9`:**
- `backend-executors/app/services/decision_engine.py` — `_evaluate_sales_flow_phases` refatorado: substituído modelo de trigger independente pelo modelo sequencial com `last_trigger_active`. Blocos `mensagem`, `midia`, `avancar_fase`, `webhook`, `espera`, `orientacao` agora executam corretamente.
- `frontend-crm/src/components/agente/CamadaFluxoVenda.tsx` — lista de blocos agora renderiza grupos visuais: ações indentadas sob o gatilho que as governa, com linha vertical colorida; label "⚡ Sempre ao entrar na fase" para ações sem gatilho explícito.
- `docs/implementations/camada7-sequential-trigger-model.md` — este ficheiro criado.

---

## Resultado / Notas de Acompanhamento

> _Preencher após testar no playground ou com lead real._

**Fase 1 + 2 (backend sequencial + frontend visual) — commit `50f38f9`:**
- [ ] Testado
- Resultado: _(preencher)_

**Comportamento esperado ao testar:**
1. Configurar fase Apresentação com: `[phase_trigger com orientação]` → `[mensagem fixa]` → `[midia áudio]`
2. Simular lead a entrar na fase no playground
3. Esperado: mensagem fixa enviada + áudio enviado antes da resposta da filha LLM
4. Verificar agrupamento visual no editor da Camada 7

**Notas gerais / comportamentos inesperados observados:**
_(preencher)_

---

## Observações Após Teste do Agrupamento Visual (commit `50f38f9`)

Após testar o agrupamento visual implementado na Fase 2, o utilizador identificou dois problemas de UX e uma questão de comportamento prático:

### Problema A — Modal não é composicional (UX bloqueante)
O fluxo atual obriga a clicar "Adicionar bloco" N vezes para montar uma regra completa. Cada clique abre o modal, salva **um** bloco e fecha. Para configurar `phase_trigger → mensagem → mídia`, o utilizador precisa de 3 sessões separadas no modal. Isso é contra-intuitivo porque:
- O utilizador não sabe antecipadamente quantos blocos precisará criar
- Não há feedback visual de qual gatilho está "atualmente activo" durante a criação
- A relação de hierarquia (gatilho governa as ações seguintes) não é comunicada no momento da adição

### Problema B — `intent_trigger` sempre dispara (comportamento inesperado)
Na implementação atual (`decision_engine.py`), `intent_trigger` tem `fired = True` incondicional — funciona como `phase_trigger` (sempre ativa). Isso significa que **qualquer bloco de ação após um `intent_trigger` dispara em cada mensagem**, independente de haver intenção detectada ou não. O utilizador configurou `intent_trigger "demonstrar hesitação" → midia "myaudio"` esperando que o áudio só fosse enviado quando hesitação fosse detectada — mas o áudio seria enviado em toda mensagem.

### Interpretação visual do agrupamento atual
- **Linha vertical colorida (seta amarela)** abaixo de `intent_trigger`: indica que `MIDIA myaudio` pertence a esse gatilho. A cor vem do `BLOCK_META` do tipo `intent_trigger`. Correto visualmente, mas o comportamento backend não corresponde à intenção.
- **Grupo "⚡ Sempre ao entrar na fase" (seta cinza)**: agrupa blocos de ação sem gatilho explícito anterior. Não está conectado visualmente ao `kw_trigger` — são grupos independentes. O utilizador inicialmente interpretou como conexão entre os dois.

---

## Fase 5 — Modal Composicional de Regras

### Motivação
Resolver o Problema A (UX bloqueante) e tornar a configuração de regras intuitiva, incluindo suporte a lógica opcional (ex: `espera`) na mesma sessão.

### Abordagem: Rule Builder Modal
Substituir o modal de adição único por um modal multi-passo que produz N blocos de uma vez.

**Fluxo do novo modal (modo ADD):**

```
Step 1: Pick Trigger
  ┌─────────────────────────────────────────────┐
  │ Escolhe: [Fase iniciada] [Palavra-chave]    │
  │          [Sem resposta]  [Intenção IA]      │
  │          [⚡ Sem gatilho (sempre ao entrar)] │
  └─────────────────────────────────────────────┘
           ↓ (se gatilho selecionado)
Step 2: Configure Trigger
  ┌─────────────────────────────────────────────┐
  │ [BlockForm do tipo de gatilho]              │
  │                          [Próximo →]        │
  └─────────────────────────────────────────────┘
           ↓
Step 3: Rule Builder
  ┌─────────────────────────────────────────────┐
  │ GATILHO                                     │
  │  🚀 FASE INICIADA                           │
  │                                             │
  │ AÇÕES / LÓGICA                              │
  │  📩 MENSAGEM  "bom dia..."           [✕]   │
  │  🎵 MIDIA     "audio.mp3"            [✕]   │
  │                                             │
  │  [+ Adicionar ação]  [+ Adicionar lógica]   │
  │  [← Voltar]                [SALVAR REGRA]   │
  └─────────────────────────────────────────────┘
```

**Sub-step "adding-block"** (aberto pelos botões `+`):
- Grid de tipos filtrado por categoria (ação ou lógica)
- Form de configuração do bloco
- "Confirmar" → bloco adicionado à lista, volta ao Step 3

**Modo EDIT** (botão "EDITAR" num bloco existente): inalterado — abre `BlockModal` existente para editar 1 bloco.

### Ficheiro a alterar
`frontend-crm/src/components/agente/CamadaFluxoVenda.tsx` — único ficheiro. Sem alterações a tipos, backend ou modelo de dados.

**Reutilizações:**
- `BlockForm` (linhas 116–378) — inalterado, reutilizado nos sub-steps
- `BLOCK_META` / `SALES_FLOW_BLOCK_CATEGORIES` — labels, cores, ícones
- `emptyBlock()` — criar blocos vazios por typeId
- `updateFlow()` — persistir alterações
- `BlockModal` — continua para edit mode

**Nova função `saveBlocks`:**
```typescript
function saveBlocks(phaseId: SalesFlowPhaseId, newBlocks: SalesFlowBlock[]) {
  updateFlow(phases.map(p => {
    if (p.id !== phaseId) return p;
    return { ...p, blocks: [...p.blocks, ...newBlocks] };
  }));
}
```

### Resolução esperada
1. Utilizador clica "+ Adicionar bloco nesta fase"
2. Seleciona "Fase iniciada" → configura (sem campos extras) → "Próximo"
3. Clica "+ Adicionar ação" → escolhe Mensagem → escreve texto → "Confirmar"
4. Clica "+ Adicionar ação" → escolhe Mídia → seleciona áudio → "Confirmar"
5. Clica "+ Adicionar lógica" → escolhe Espera → configura tempo → "Confirmar" (opcional)
6. Clica "Salvar regra" → todos os blocos inseridos em sequência na fase
7. Agrupamento visual mostra a regra completa com indentação correta

### Commits Fase 5

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `64304b6` | RuleBuilderModal + BLOCK_TYPE_LABELS + saveBlocks |

**Detalhes do commit `64304b6`:**
- `frontend-crm/src/components/agente/CamadaFluxoVenda.tsx`:
  - Adicionado `BLOCK_TYPE_LABELS` — centraliza labels de tipo (elimina ternário longo no `BlockModal`)
  - Adicionado `RuleBuilderModal` — modal multi-passo com 4 steps: `pick-trigger` → `config-trigger` → `rule-builder` → `adding-block`
  - `openAdd` agora abre `RuleBuilderModal` em vez do `BlockModal`
  - `saveBlocks()` — persiste array de blocos em sequência na fase
  - `BlockModal` (EDITAR) inalterado — continua para edição de bloco único

### Verificação
- [x] Add com gatilho + 2 ações → salva 3 blocos em sequência ✅
- [x] Add com "sem gatilho" → salva só ações no grupo "Sempre ao entrar" ✅
- [x] Editar bloco existente (EDITAR) → abre BlockModal individual inalterado ✅
- [x] Cancelar no Step 3 → nenhum bloco é salvo ✅

---

## Próximas Iterações

- **Fase 4 — `condicao` com branching real:** requer mudança no modelo de dados e UI para editar blocos aninhados dentro de cada branch (Sim/Não). Não bloqueante para o caso de uso atual.
- **`intent_trigger` real:** ver Fase 6 abaixo — plano detalhado.

---

## Fase 6 — `intent_trigger` Real via LLM Mãe

### Motivação

Hoje `intent_trigger` tem `fired = True` incondicional no backend — funciona como `phase_trigger` (sempre ativa). O utilizador configura `intent_trigger "demonstrar hesitação" → midia "audio-objeção"` esperando que o áudio só seja enviado quando hesitação for detectada, mas o áudio é enviado em toda mensagem.

### Abordagem: detecção integrada na LLM Mãe

A avaliação de intenção será feita **na mesma chamada** da LLM Mãe, sem custo extra de LLM. A mãe já recebe histórico completo e contexto do lead — é o lugar natural para interpretar nuance emocional.

**Por que a LLM Mãe e não uma chamada separada:**
- Já possui histórico completo da conversa
- Sem custo adicional de chamada LLM
- Raciocínio contextual mais rico (sabe fase, qualificação, mensagens anteriores)
- Prompt condicional: só aparece se a fase ativa tiver `intent_trigger` blocos configurados

### Fluxo de implementação

```
Orchestrator
  → coleta intent_triggers da fase ativa
  → se existirem: injeta secção [DETECÇÃO DE INTENÇÃO] no prompt da mãe
  → LLM Mãe retorna detected_intents: ["demonstrar hesitação"]
  → decision_engine recebe detected_intents
  → intent_trigger bloco: fired = intent_label in detected_intents
```

### Prompt condicional (secção injetada na LLM Mãe)

Só adicionada ao prompt quando `len(active_intent_triggers) > 0`:

```
[DETECÇÃO DE INTENÇÃO]
A mensagem do lead pode conter intenções específicas que ativam ações automáticas.
Avalie a última mensagem do lead e indique quais das intenções abaixo foram detectadas:

{lista dinâmica de intent_triggers da fase ativa}
Ex:
- "demonstrar hesitação": lead expressa dúvida, receio, resistência ou hesitação
- "demonstrar interesse forte": lead pede mais detalhes, demonstra entusiasmo explícito

Retorne no campo `detected_intents` uma lista dos labels detectados (pode ser lista vazia []).
Seja conservador: só marque se houver sinal claro na mensagem. Dúvida = não marcar.
```

### Output estruturado da LLM Mãe (campo novo)

```json
{
  "should_respond": true,
  "routing_decision": "...",
  "detected_intents": ["demonstrar hesitação"]
}
```

Campo `detected_intents` é `list[str]`, padrão `[]` quando não há `intent_trigger` na fase.

### Ficheiros a alterar

| Ficheiro | Mudança |
|---|---|
| `backend-crm/services/ai_orchestrator/orchestrator.py` | Coletar `intent_triggers` da fase ativa; injetar secção no prompt da mãe se existirem |
| `backend-crm/services/ai_orchestrator/orchestrator.py` | Parsear `detected_intents` do output da mãe e incluir no `ContextBundle` ou passar para o decision engine |
| `backend-executors/app/services/decision_engine.py` | `intent_trigger`: substituir `fired = True` por `fired = intent_label in detected_intents` |

**Sem alterações em:** modelo de dados, tipos frontend, `CamadaFluxoVenda.tsx`.

### Comportamento esperado após implementação

| Configuração | Comportamento atual | Comportamento após |
|---|---|---|
| `intent_trigger "hesitação" → midia` | áudio enviado em **toda** mensagem | áudio só quando hesitação detectada |
| `intent_trigger "interesse" → mensagem` | mensagem enviada em **toda** mensagem | mensagem só quando interesse detectado |
| Fase sem `intent_trigger` | sem impacto | sem impacto (campo omitido do prompt) |

### Commits Fase 6

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `8947eb6` | `detected_intents` no MotherDecision + helper + `_evaluate_sales_flow_phases` + 4 call sites |

**Detalhes do commit `8947eb6`:**
- `backend-executors/app/services/orchestrator_models.py` — `detected_intents: list[str] = Field(default_factory=list)` adicionado ao `MotherDecision`
- `backend-executors/app/services/decision_engine.py`:
  - `_collect_intent_triggers_for_lead_phase()` — coleta `intent_trigger` blocks da fase atual do lead
  - `_build_mother_prompt()` — injeta `[DETECÇÃO DE INTENÇÃO]` condicional + campo `detected_intents` no schema JSON
  - `_evaluate_sales_flow_phases()` — parâmetro `detected_intents`; `intent_trigger`: `fired = intent_label in detected_intents` (fallback `True` se `detected_intents is None`)
  - 4 call sites atualizados para passar `mother_decision.detected_intents`

### Verificação
- [ ] Configurar `intent_trigger "demonstrar hesitação" → midia` numa fase
- [ ] Enviar mensagem neutra no playground → mídia **não** deve ser enviada
- [ ] Enviar mensagem com hesitação ("não sei se vale...") → mídia **deve** ser enviada
- [ ] Fase sem `intent_trigger` → prompt da mãe não inclui secção de detecção

---

## Fase 7 — `phase_trigger` com deteção de entrada + guardrail "disparar apenas uma vez"

### Problema identificado

O `phase_trigger` avaliava `fired = True` **incondicionalmente** a cada mensagem enquanto o lead estivesse na fase. Consequência: se configurado `PHASE TRIGGER → MENSAGEM "Bem-vindo!" → MIDIA`, o bot enviaria essas ações em **toda mensagem** do lead naquela fase (loop).

Bugs adicionais corrigidos nesta fase:
1. **`_apres_route` errado** — `_build_child_prompt_apresentation()` usava `mother_decision.route_to` para selecionar a fase do Fluxo de Venda no child prompt. Quando a mãe dizia "qualification" e o sistema auto-promovia para "apresentation", os blocos de orientação da Fase 2 não chegavam ao LLM filho.
2. **Mapeamento `_ROUTE_TO_PHASE_ID` incompleto** — `"pre-agendamento"` (hífen) não estava mapeado, apenas `"pre_agendamento"` (underscore). Blocos da Fase p3a nunca eram avaliados.

### Arquitetura da solução

**Parâmetro `is_phase_entry: bool = True`** adicionado a `_evaluate_sales_flow_phases()`.

- Quando `True`: `phase_trigger` dispara → ações downstream executam
- Quando `False`: `phase_trigger` não dispara → ações downstream ignoradas

**Cálculo de `is_phase_entry`** em `compose_decision_output()` antes da chamada principal:

```python
_lead_current_route = _LEAD_CAT_TO_ROUTE.get(lead.category)
_is_phase_entry = (_lead_current_route != effective_route_to)
```

Se `lead.category` (categoria antes desta mensagem) é diferente do `effective_route_to` (fase que vai executar agora) → é uma transição → dispara uma vez.

**Chamadas dos child prompt builders** (qualification, apresentation, followup) mantêm `is_phase_entry=True` implícito (default) — as `prompt_injections` de orientação chegam sempre ao LLM.

### Comportamento resultante

| Cenário | `lead.category` | `effective_route_to` | `is_phase_entry` | `phase_trigger` dispara? |
|---|---|---|---|---|
| Qualificação completa → entra em Apresentação | `qualification` | `apresentation` | `True` | ✅ Uma vez |
| 2ª mensagem já em Apresentação | `apresentation` | `apresentation` | `False` | ❌ Não repete |
| Transição apresentação → pré-agendamento | `apresentation` | `pre-agendamento` | `True` | ✅ Uma vez |
| Já em pré-agendamento, nova mensagem | `pre-agendamento` | `pre-agendamento` | `False` | ❌ Não repete |

### Ficheiros alterados

| Ficheiro | Mudança |
|---|---|
| `backend-executors/app/services/decision_engine.py` | Único ficheiro alterado |

### Commits Fase 7

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | eb9b7675576547f16cf6ded978415bee5b05ad8d | `is_phase_entry` + `_ROUTE_TO_PHASE_ID` fix + `_apres_route` fix |

**Detalhes:**
- `_evaluate_sales_flow_phases()` — novo parâmetro `is_phase_entry: bool = True`; `phase_trigger`: `fired = is_phase_entry`
- `_ROUTE_TO_PHASE_ID` — adicionado `"pre-agendamento": "p3a"` (hífen) ao lado de `"pre_agendamento"`
- `compose_decision_output()` — computa `_is_phase_entry` a partir de `lead.category` vs `effective_route_to`; passa para chamada principal de `_evaluate_sales_flow_phases()`
- `_build_child_prompt_apresentation()` — removida linha `_apres_route = mother_decision.route_to or "apresentation"`; chamada hardcoded com `"apresentation"`

### Verificação Fase 7
- [x] Phase trigger disparou na transição qualification → apresentation (confirmado no teste 26/05/2026)
- [x] `auto_messages` com "Olá, aqui estão os detalhes" e "Gostou?" apareceram correctamente
- [x] LLM filho recebeu orientações via `prompt_injections`
- [ ] ~~2ª mensagem já em Apresentação sem repetição~~ → substituído por Fase 8 (flag `phases_triggered`)

---

## Fase 8 — Diagnóstico da Verificação + Duas Correcções (26/05/2026)

### Teste realizado

Sessão de playground com agente `sdr_scheduler` (Sofia / AutoSell), lead ID 144, fase 2 configurada com `PHASE TRIGGER → MENSAGEM "Olá, aqui estão os detalhes" → MIDIA myaudio → MENSAGEM "Gostou?"`.

### Problema 1 — Ordem dos blocos (media no sítio errado)

**Observado:** media `myaudio` aparece inline com a mensagem LLM (antes das mensagens de texto configuradas).
**Esperado:** sequência `LLM → "Olá..." → 🎵 áudio → "Gostou?"`.

**Causa raiz:** blocos `midia` iam para `pre_send_media` (enviados *antes* da resposta LLM), enquanto blocos `mensagem` iam para `system_actions` → `auto_messages` (enviados *depois*). As duas pipelines quebravam a ordem sequencial configurada.

### Problema 2 — Phase trigger re-disparava após lead avançar para outra fase

**Observado:** no teste, à 20:38 o lead expressou dúvida e a LLM Mãe encaminhou de volta para `apresentation`. O phase trigger disparou de novo (media + "Olá..." + "Gostou?" repetiram).

**Causa raiz:** o agente `sdr_scheduler` faz auto-advance imediato — na mesma mensagem que entra em apresentação, o LLM filho marca `did_complete_phase=True` e `suggested_category` avança para `agendamento`. Na mensagem seguinte, `lead.category = "agendamento"` ≠ `"apresentation"` → `is_phase_entry = True` → trigger re-dispara. O check de `lead.category != effective_route_to` capturava re-entradas de fases mais avançadas como "nova entrada".

---

### Arquitectura das Correcções

#### Fix 1 — `midia` → `system_actions` (ordenação correcta)

**`backend-executors/app/services/decision_engine.py`** — `_evaluate_sales_flow_phases()`:

```python
# ANTES: midia ia para pre_send_media (antes do LLM)
result["pre_send_media"].append({...})

# DEPOIS: midia vai para system_actions (sequência com mensagens)
result["system_actions"].append({
    "type": "send_media",
    "media_url": media_url,
    "media_type": ...,
    "caption": ...,
})
```

**`backend-crm/routes/playground.py`** — loop `raw_system_actions`:
- `send_media` → adiciona a `auto_items` como `{type: "media", media_url, media_type}`
- `auto_items` é o novo campo retornado com a sequência completa ordenada

**`backend-crm/routes/executor.py`** — `_dispatch_system_actions()`:
- `send_media` → cria job `whatsapp.send.local` com `media_url`

**Frontend** — `Playground.tsx` + `api.ts`:
- `PlaygroundAutoItem = {type:"text", content} | {type:"media", media_url, media_type}`
- `revealAutoMessages` renomeado/actualizado: itera `auto_items`, cria mensagem de texto ou mensagem com `preMediaItems` para media
- `resolveAutoItems()` — fallback: se não há `auto_items`, converte `auto_messages` em `[{type:"text"}]`

#### Fix 2 — Flag `phases_triggered` por lead (disparo verdadeiramente único)

**`backend-crm/database.py`** — `init_db()`:
```python
ensure_column(conn, "leads", "phases_triggered", "phases_triggered TEXT NULL")
```
JSON array de phase IDs já disparados por lead: `["p2", "p3a"]`.

**`backend-executors/app/services/decision_engine.py`** — `compose_decision_output()`:
```python
# Carrega fases já disparadas do contexto do lead
_triggered_phases = set(json.loads(lead["phases_triggered"] or "[]"))
# Entrada na fase: categoria diferente E fase nunca disparada antes
_is_phase_entry = (
    _lead_current_route != effective_route_to
    and _effective_phase_id not in _triggered_phases
)
```
Quando `phase_trigger` dispara → adiciona `{type: "mark_phase_triggered", phase_id: "p2"}` aos `system_actions`.

**`backend-crm/routes/playground.py`** — `_mark_phase_triggered()` + loop:
- Quando recebe `mark_phase_triggered`: carrega JSON, adiciona `phase_id`, grava no DB.

**`backend-crm/routes/executor.py`** — `_dispatch_system_actions()`:
- Mesmo tratamento para WhatsApp real.

### Comportamento resultante

| Cenário | `lead.category` | `phases_triggered` | `effective_route_to` | `is_phase_entry` | Dispara? |
|---|---|---|---|---|---|
| 1ª entrada em apresentação | `qualification` | `[]` | `apresentation` | `True` | ✅ Uma vez |
| 2ª mensagem em apresentação | `apresentation` | `["p2"]` | `apresentation` | `False` | ❌ Não |
| Lead avança para agendamento, volta para apresentação | `agendamento` | `["p2"]` | `apresentation` | `False` | ❌ Não (já disparou) |
| 1ª entrada em pré-agendamento | `apresentation` | `["p2"]` | `pre-agendamento` | `True` | ✅ Uma vez |

### Ficheiros alterados

| Ficheiro | Mudança |
|---|---|
| `backend-executors/app/services/decision_engine.py` | `midia`→`system_actions`; `phase_trigger_fired`; `_is_phase_entry` com `phases_triggered`; `mark_phase_triggered` action |
| `backend-crm/database.py` | `ensure_column leads.phases_triggered TEXT NULL` |
| `backend-crm/routes/playground.py` | `_mark_phase_triggered()`; `auto_items`; handlers `send_media` e `mark_phase_triggered` |
| `backend-crm/routes/executor.py` | handlers `send_media` e `mark_phase_triggered` em `_dispatch_system_actions` |
| `frontend-crm/src/services/api.ts` | tipo `PlaygroundAutoItem`; campo `auto_items` em `PlaygroundChatResponse` |
| `frontend-crm/src/pages/Playground.tsx` | `revealAutoMessages` com suporte a media; `resolveAutoItems()`; call sites actualizadas |

### Verificação Fase 8
- [ ] Playground: transition qual → apres → confirmar ordem correcta: LLM → "Olá..." → 🎵 áudio → "Gostou?"
- [ ] Enviar 2ª mensagem em apresentação → `auto_items` vazio (flag `["p2"]` impede re-disparo)
- [ ] Lead avança para agendamento e volta para apresentação → trigger NÃO re-dispara
- [ ] WhatsApp real: media e mensagens enviados em jobs separados na ordem correcta
- [ ] Verificar coluna `phases_triggered` populada no DB após primeira execução
