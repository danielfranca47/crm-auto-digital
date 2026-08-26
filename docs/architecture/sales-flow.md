# Camada 7 — Fluxo de Venda

## Visão geral

O Fluxo de Venda (Camada 7) é um builder visual que permite configurar **blocos tipados por fase** do pipeline de vendas. Em vez de depender exclusivamente do LLM para decidir como agir em cada etapa, o usuário pode pré-programar comportamentos determinísticos: injectar orientações no prompt, enviar mídias automáticas, avançar fases, disparar webhooks ou configurar espera.

O Fluxo de Venda opera **como uma camada que corre antes do prompt filho** no `decision_engine.py`. Seus resultados (orientações injectadas, mídias, system_actions) são compostos no `DecisionOutput` juntamente com o resultado do LLM.

**Onde é configurado:** tela do Agente → aba "Fluxo de Venda" (componente `CamadaFluxoVenda.tsx`).

**Onde é armazenado:** campo `sales_flow` em `ai_profiles` — JSON com estrutura `{phases: [{id, blocks[]}]}`.

**Onde é executado:** `backend-executors/app/services/decision_engine.py` → `_evaluate_sales_flow_phases()`.

**Disponibilidade:** o Fluxo de Venda está disponível para qualquer agente, independente de `response_style` (`active` ou `passive`) — o único controlo de on/off é `sales_flow.enabled`. Em modo passivo, o prompt de qualificação tem uma regra absoluta de "zero perguntas abertas" (inferência silenciosa); blocos `orientacao` configurados com instruções que façam perguntas directas podem contradizer essa regra, já que são injectados com prioridade alta. É responsabilidade de quem configura o Fluxo de Venda manter os blocos coerentes com o `response_style` do agente — não há validação automática disso.

---

## Fases (p0–p5)

| Phase ID | Nome | `effective_route_to` | Sempre ativo? |
|---|---|---|---|
| `p0` | Recepção | `recepcao` | Sim |
| `p1` | Qualificação | `qualification` | Sim |
| `p2` | Apresentação | `apresentation` | Sim |
| `p3a` | Pré-Agendamento | `pre_agendamento` | Só `agenda` |
| `p3b` | Agendamento | `agendamento` | Só `agenda` |
| `p4` | Follow Up | `followup` / `follow-up` | Não para `direto` |
| `p5` | Fechamento | `closing` | Sim |

O mapeamento `effective_route_to → phase_id` está em `_ROUTE_TO_PHASE_ID` dentro de `_evaluate_sales_flow_phases()`.

Todas as fases — incluindo `p5` (Fechamento) — injectam blocos `orientacao` configurados no prompt da respectiva LLM filha via `_build_sales_flow_phases_block(_evaluate_sales_flow_phases(...))`, chamado no fim de cada `_build_child_prompt_<fase>()`. É assim que, para o Closer (`direto`), instruções de fechamento (ex.: quando enviar o link de pagamento) podem ser configuradas em `p5` pelo builder — sem precisar de nenhum flag especial de bloco, ao contrário de `qual_opener`/`booking_signal_opener` (ver abaixo).

---

## Pipeline por tipo de agente

O builder adapta a UI e o executor filtra os blocos com base no `agent_mode` do AI Profile.

| Grupo (normalizado) | `agent_mode` equivalente | Fases ativas |
|---|---|---|
| `consultivo` | `consultivo` | p0 → p1 → p2 → p4 → p5 |
| `direto` | `direto`, `closer` | p0 → p1 → p2 → p5 |
| `agenda` | `agenda`, `sdr_scheduler` | p0 → p1 → p2 → p3a → p3b → p4 → p5 |

**No builder (frontend):**
- Fases p3a/p3b são renderizadas apenas para agentes do grupo `agenda`
- Fases inativas para o agent_mode atual ficam com opacidade reduzida e badge "Não ativo neste agente"

**No executor (backend):**
- `_evaluate_sales_flow_phases()` recebe `effective_route_to` da decisão da LLM Mãe e processa apenas os blocos da fase correspondente — não há filtragem explícita por agent_mode no backend, pois rotas inativas simplesmente nunca chegam ao engine

---

## Tipos de bloco

### Triggers (activam a avaliação de blocos de ação)

| `typeId` | Nome | Comportamento em runtime |
|---|---|---|
| `kw_trigger` | Palavra-chave | Activa se a mensagem do lead contém a(s) keyword(s) definidas. Suporta `sequential` e `fire_once` (ver abaixo). |
| `phase_trigger` | Entrada na fase | Activa **uma única vez por lead** — na primeira mensagem que chega à fase. Rastreado por `leads.phases_triggered` (JSON array de phase IDs disparados). Quando dispara, injeta contexto no `prompt_injections` e emite `mark_phase_triggered`. |
| `no_reply_trigger` | Sem resposta | Placeholder de UI. Não avaliado em runtime. |
| `intent_trigger` | Intenção detectada | A LLM Mãe recebe secção `[DETECÇÃO DE INTENÇÃO]` condicional se a fase **atual** do lead ou a **fase seguinte** (dado o pipeline do `agent_mode`, ver tabela acima) tiver blocos deste tipo. Retorna `detected_intents: list[str]`. O bloco dispara se `intent_label in detected_intents`. Suporta `sequential` e `fire_once` (ver abaixo). |
| `block_trigger` | Depende de outro bloco | Gatilho leve sem condição de conteúdo — dispara **uma única vez por lead**, assim que o bloco referenciado em `requires_block_id` já tiver disparado num turno anterior. Sempre sequencial (equivalente a `phase_trigger`, não depende de `fire_once`). Nunca aparece como card no seletor "Escolher gatilho" do builder — é criado implicitamente quando o utilizador escolhe "Sem gatilho" e opcionalmente define uma dependência (ver "No frontend" em 2b, abaixo). Sem `requires_block_id` definido, o builder colapsa para o comportamento legado (nenhum bloco de gatilho é persistido) — não existe `block_trigger` sem dependência. |

> **Janela de detecção de 1 fase à frente:** `_collect_intent_triggers_for_lead_phase()` mostra à mãe os `intent_trigger` da fase salva em `lead.category` **e** da fase seguinte na sequência de `_SALES_FLOW_PHASE_SEQUENCE_BY_AGENT_MODE` (`decision_engine.py`, espelha a tabela de pipeline acima). Isso é necessário porque a transição de fase só é decidida pela própria mãe nesse turno — sem essa antecipação, um `intent_trigger` configurado como o sinal de entrada numa fase (ex.: "cliente aceitou a oferta") nunca teria como disparar na mensagem que efetivamente o causa. A avaliação de disparo em si (`_evaluate_sales_flow_phases`) continua olhando só a fase escolhida pelo `effective_route_to` da mãe nesse turno — a antecipação afeta apenas o que é mostrado à mãe, não quais blocos podem executar.
>
> **Consistência `reason` ↔ `detected_intents`:** `generate_mother_route()` usa JSON solto (`text.format.type="json_object"`), sem schema reforçado pela API — a mãe pode reconhecer a intenção em prosa livre no campo `reason` sem replicá-la em `detected_intents`. O bloco `[DETECÇÃO DE INTENÇÃO]` (fim do prompt, mais perto da geração) inclui uma instrução explícita exigindo essa consistência. Se `detected_intents` continuar inconsistente com `reason` em produção, revisar esse reforço antes de mexer no motor de avaliação — o bug historicamente esteve na confiabilidade do prompt, não em `_evaluate_sales_flow_phases`.

### Flag especial de bloco: `qual_opener`

Blocos do tipo `orientacao` na fase p1 podem ter o flag `qual_opener: true`. Identifica o bloco como **abertura de qualificação** — uma instrução que pede permissão ao lead antes das perguntas de qualificação.

**Comportamento em runtime:** detectado em `_build_child_prompt_qualification()` e injectado no prompt apenas quando `asked_questions_json` está vazio (primeira mensagem da fase de qualificação) e `qualification_fields` tem pelo menos 1 campo ativo. Não repete em turnos seguintes.

**No frontend:** na fase p1 do builder (`CamadaFluxoVenda.tsx`), quando `qualification_fields` tem campos ativos:
- Se não existe bloco `qual_opener` → banner "Sem instrução de abertura configurada" com botão "+ Adicionar abertura"
- Se existe → `QualOpenerCard` com label "Abertura de Qualificação", badge "automática · 1ª mensagem", botões "Editar" e "Remover"

**Texto padrão gerado:** "Antes de fazer as primeiras perguntas de qualificação, pede permissão ao lead de forma natural, sem repetir saudações já feitas: algo como 'Posso te fazer algumas perguntas rápidas para perceber como podemos ajudar melhor?' — adapta ao tom de voz e ao contexto da conversa."

### Flag especial de bloco: `booking_signal_opener`

Blocos do tipo `orientacao` na fase p2 podem ter o flag `booking_signal_opener: true`. Identifica o bloco como **reconhecimento de interesse de agendamento** — a instrução que reconhece quando o lead já escolheu um serviço ou perguntou sobre horários, e pede para avançar diretamente para o agendamento.

**Escopo:** só relevante para agentes com recursos de agendamento — `agent_1` (`template_key` "sdr_padrao") e `agent_3` (`template_key` "hybrid_scheduler"), ambos no grupo normalizado `agenda` (ver `map_template_key_to_agent_type()` em `backend-crm/services/agent_type.py`). Para `direto`/`consultivo`, este mecanismo não se aplica.

**Comportamento em runtime:** detectado em `_build_child_prompt_apresentation()`. Quando `agent_mode_normalized == "agenda"`:
- `sales_flow` desabilitado OU fase p2 nunca configurada (`blocks` vazio) → mantém o texto **hardcoded** original (compatibilidade com perfis legados que nunca tocaram no Fluxo de Venda)
- Fase p2 configurada (qualquer bloco presente) → usa **apenas** o que o utilizador definiu: o bloco `booking_signal_opener` se presente, ou nada se ausente (remoção deliberada — sem fallback)

Para `direto` (Closer), a instrução **nunca** é injectada — nem o texto hardcoded, nem um bloco editável equivalente em p2: "perguntar disponibilidade" contradiz o objectivo do variant `sales` (CONFIRMAR/ENVIAR LINK). Instruções de fechamento específicas do Closer (ex.: quando enviar o link de pagamento) vivem em p5, através de blocos `orientacao` comuns (ver "Fases (p0–p5)", acima). `consultivo` permanece fora de escopo desta migração (mantém o texto hardcoded — ver `docs/plans/fluxo-vendas-melhorias-futuras.md`, item M1).

**No frontend:** na fase p2 do builder (`CamadaFluxoVenda.tsx`), só quando `agentGroup === 'agenda'`:
- Sem bloco `booking_signal_opener` e p2 sem outros blocos → banner "Sem reconhecimento de interesse de agendamento configurado" (ainda usando o padrão do sistema)
- Sem bloco `booking_signal_opener` mas p2 já tem outros blocos → banner "Reconhecimento de interesse de agendamento desativado" (nada ativo — reflete o comportamento real do backend)
- Com bloco → `OpenerCard` com label "Reconhecimento de Interesse de Agendamento", badge "automática · qualquer turno", botões "Editar" e "Remover"

`OpenerBanner`/`OpenerCard` são componentes genéricos (parametrizados por título/descrição/label/badge/cor) reutilizados tanto por `qual_opener` (p1) quanto por `booking_signal_opener` (p2).

### Ações (executadas quando o trigger bate)

| `typeId` | Nome | Comportamento em runtime |
|---|---|---|
| `orientacao` | Orientação ao LLM | Texto injectado como instrução adicional no prompt filho da fase |
| `mensagem` | Mensagem fixa | Texto enviado como `system_actions[{type: "send_message", content}]` |

> O campo `content` de blocos `orientacao`/`mensagem` suporta variáveis dinâmicas `{{chave}}` (ex.: `{{lead.nome_whatsapp}}`), com atalho `/` no builder. Resolvidas por `_resolve_sales_flow_variables()` dentro de `enrich_context_bundle()` — nunca chegam literais ao prompt ou ao lead. Ver [`dynamic-variables.md`](dynamic-variables.md).
| `midia` | Mídia | Enviado como `system_actions[{type: "send_media", media_url, media_type}]`, na sequência configurada entre outros blocos. |
| `avancar_fase` | Avançar fase | Dispara `system_actions[{type: "advance_phase", target_phase}]` → move lead no Kanban |
| `webhook` | Webhook | Dispara `system_actions[{type: "webhook", url, method, note, block_id, phase_id}]` → job assíncrono dedicado (ver "Execução do bloco `webhook`" abaixo) |

> Quando `phase_trigger` dispara, blocos `mensagem` e `midia` subsequentes também adicionam o conteúdo enviado a `prompt_injections`, para que o LLM filho saiba o que foi enviado automaticamente e possa complementar sem repetir.

### Lógica

| `typeId` | Nome | Comportamento em runtime |
|---|---|---|
| `condicao` | Lógica de Ramificação (bifurcação em N caminhos, avaliados pela Mãe) | Ver secção "Lógica de Ramificação" abaixo |
| `espera` | Espera inteligente (Smart Delay) | Pausa o restante da fase por um tempo definido (`wait_value` + `wait_unit`) — ver secção "Pausa do Fluxo" abaixo |

> **Nota:** `webhook`, `espera` e `condicao` (Lógica de Ramificação) estão todos
> implementados — ver "Execução do bloco `webhook`", "Pausa do Fluxo" e "Lógica de
> Ramificação" abaixo.

---

## Flags opcionais em blocos de trigger

### `sequential` (`kw_trigger`, `intent_trigger`)

Campo independente de `fire_once` — decide só se o gatilho participa do **encadeamento
sequencial** da fase (espera os gatilhos sequenciais anteriores, trava os seguintes, conta
como pendência no guardrail de troca de fase — ver "Modelo sequencial de trigger" abaixo).
Duas opções no builder: **"Respeitar ordem cronológica"** (`sequential: true`) ou **"Pode
ser acionado a qualquer momento"** (`sequential: false`).

**Fallback de compatibilidade:** blocos sem o campo `sequential` (salvos antes desta
feature) usam o valor de `fire_once` como padrão — `_is_sequential_trigger_block()`
(`decision_engine.py`) e `isSequentialCapable()` (`CamadaFluxoVenda.tsx`) leem
`"sequential" in block ? block.sequential : block.fire_once`. Isto preserva exatamente o
comportamento anterior (quando os dois conceitos eram o mesmo campo) para todo bloco já
configurado; só blocos novos ou reeditados no builder passam a ter os dois campos de facto
independentes. Blocos novos criados no builder já nascem com `sequential: true`.

`phase_trigger` e `block_trigger` são sempre sequenciais estruturalmente (não têm este
campo — nenhum conteúdo/keyword/intenção a avaliar que justifique torná-los esporádicos).

### `fire_once` (`kw_trigger`, `intent_trigger`)

Quando `fire_once: true`, o bloco dispara apenas **uma vez por lead** — independente do
valor de `sequential` acima:
- Ao disparar, emite `{type: "mark_trigger_fired", block_id}` nos `system_actions`
- CRM (playground e executor) faz append do `block_id` em `leads.triggers_fired` (JSON array)
- Em disparos seguintes: `already_fired = block_id ∈ triggers_fired` → `fired = False`

Quando `sequential: true` e `fire_once: false` (repetível mas respeitando a fila), o motor
ainda emite `mark_trigger_fired` na **1ª vez** que o bloco dispara — não para suprimir
disparos seguintes (que continuam normalmente), mas para servir de registo de "já passou
por aqui" ao gating sequencial (`_trigger_persisted_satisfied()`). A checagem
`_block_id not in _triggers_fired` evita reemitir a acção em cada disparo repetido.

**DB:** coluna `leads.triggers_fired TEXT NULL` (adicionada em `backend-crm/database.py` via `ensure_column`).

### `suppress_llm_response` (`kw_trigger`, `intent_trigger`, `phase_trigger`)

Quando `suppress_llm_response: true` e o trigger dispara:
- As ações automáticas (`mensagem`, `midia`) são executadas normalmente
- O `decision_engine` força `next_action = "ignore"` e `message_text = ""`
- **Playground:** frontend omite o turno da LLM; exibe apenas os `auto_items`
- **WhatsApp real:** runner despacha `_send_actions` sincronamente, completa job com `skipped_suppress_llm` (sem enviar mensagem LLM)

---

## Fluxo de execução (backend)

### Modelo sequencial de trigger (`_evaluate_sales_flow_phases`)

Os blocos de uma fase são avaliados em sequência, com dois mecanismos combinados:

**1) Disparo por turno (`last_trigger_active`)** — como antes, propaga a decisão do último trigger visto para os blocos de ação imediatamente seguintes:

```
last_trigger_active = True   # default: ações sem trigger explícito sempre disparam

para cada block em fase.blocks:
    se block é trigger (kw/phase/intent/no_reply):
        fired = avaliar_trigger(block, context)
        last_trigger_active = fired
        se fired e block.suppress_llm_response:
            result["suppress_llm_response"] = True
    se block é ação (orientacao/mensagem/midia/avancar_fase):
        se last_trigger_active:
            executar_ação(block, result)
```

**2) Gating sequencial entre gatilhos (`_prereqs_satisfied`)** — só gatilhos **sequenciais** (`phase_trigger`, `block_trigger`, ou `kw_trigger`/`intent_trigger` com o campo `sequential: true` — fallback para `fire_once: true` em blocos sem o campo novo, ver "Flags opcionais em blocos de trigger" acima) participam: um gatilho sequencial só pode ser avaliado (`fired` possivelmente `True`) se **todos os gatilhos sequenciais anteriores da mesma fase** já estiverem satisfeitos — persistidos em `leads.phases_triggered`/`leads.triggers_fired` **antes** deste turno, ou disparando neste mesmo turno. Se um gatilho anterior ainda não foi satisfeito, os gatilhos sequenciais seguintes ficam **bloqueados** (`fired = False`), independentemente de keyword match ou de `detected_intents` da LLM Mãe. Isso impede que uma etapa mais à frente na sequência (ex.: "cliente indicou o serviço") dispare antes de uma etapa anterior configurada pelo utilizador (ex.: "cliente aceitou ver a tabela"). Gatilhos não-sequenciais (`kw_trigger`/`intent_trigger` com `sequential: false`, `no_reply_trigger`) não participam — nem bloqueiam, nem são bloqueados; `sequential` é ortogonal a `fire_once`, que continua a controlar só se o gatilho pode disparar mais de uma vez.

**2b) Dependência explícita (`requires_block_id`)** — trava **aditiva** à gating posicional acima, opcional, em `kw_trigger`/`intent_trigger`, e **obrigatória** (para ter qualquer efeito) em `block_trigger`: o campo `requires_block_id` referencia o `id` (imutável) de outro gatilho sequencial da mesma fase — nunca o `label` (editável a qualquer momento). Diferença central face ao gating posicional: **nunca aceita satisfação no mesmo turno** — só considera o bloco referenciado satisfeito se já estiver persistido (`leads.triggers_fired`/`leads.phases_triggered`) de um turno **estritamente anterior**. Resolvido por `_requires_block_satisfied()` contra um mapa `block_id → (block, phase_id)` de todas as fases do profile (`_build_block_lookup()`), usando o `phase_id` do **bloco referenciado** (não da fase sendo avaliada agora — necessário para uma referência a um `phase_trigger` de outra fase resolver corretamente).

Referência **falha aberto** (sem efeito, nunca bloqueia para sempre) em dois casos: bloco referenciado apagado, ou bloco ainda existe mas deixou de ser `_is_sequential_trigger_block()` (ex.: "Ordem" mudada para "Pode ser acionado a qualquer momento" depois de outro bloco já ter passado a depender dele). O builder (`CamadaFluxoVenda.tsx`) sinaliza visualmente ambos os casos como "dependência quebrada", mas o backend nunca deixa um gatilho permanentemente travado por uma referência inválida — sem cascade-delete automático quando o bloco-alvo é removido.

**No frontend** (`CamadaFluxoVenda.tsx`): `SalesFlowBlock.requires_block_id?: string` e `label?: string` (este último já existia para `condicao`, estendido para `kw_trigger`/`intent_trigger` como "Nome do gatilho" — `blockSummary()` prefere o `label` quando presente). O formulário de `kw_trigger`/`intent_trigger` ganha um campo "Depende de" (`<select>`), populado por `dependencyOptions(block, phaseBlocks)` — filtra para blocos da mesma fase que sejam `isSequentialCapable()` (espelha `_is_sequential_trigger_block()` do backend), excluindo o próprio bloco e qualquer opção cuja cadeia de `requires_block_id` já leve de volta a ele (`requiresChainIncludes()`) — previne ciclos diretamente no seletor, sem depender de validação no backend. `BlockRow` calcula `hasBrokenDependency` (alvo ausente ou não mais `isSequentialCapable`) e mostra "⚠ dependência quebrada — bloco removido".

**`block_trigger` — mesma trava, sem formulário de gatilho:** o card tracejado "Sem gatilho" do seletor de gatilhos abre o mesmo campo "Depende de" usado por `kw_trigger`/`intent_trigger`. Se o utilizador não escolher dependência nenhuma, o builder colapsa para o comportamento legado (`triggerBlock = null`, nenhum bloco de gatilho persistido — idêntico ao "Sem gatilho" de antes desta feature). Só quando uma dependência é escolhida um bloco real `{typeId:"block_trigger", requires_block_id}` é criado. Existe justamente para os casos em que o utilizador só quer sequenciamento puro ("dispare depois que o bloco anterior já disparou"), sem precisar configurar um `intent_trigger`/`kw_trigger` completo só para ter acesso ao campo de dependência.

Independente do gating posicional: não participa de `_prereqs_satisfied_by_scope` (que é uma chave de *escopo*, não de *bloco*) — a trava chega às regras de escopo indiretamente, via `fired=False` do bloco travado.

**3) Orientações críticas como guarda permanente** — depois da passagem principal, uma segunda passagem percorre a fase novamente: toda `orientacao` com `priority: "critical"` que não foi injectada neste turno (porque o `last_trigger_active` da sua posição estava `False`) é reinjectada mesmo assim, **desde que o próximo gatilho sequencial da fase (o primeiro depois dela na lista de blocos) ainda não esteja satisfeito** (persistido). Isto faz uma instrução como "não pergunte disponibilidade ainda" continuar presente em todo turno da fase — não só no turno em que foi originalmente disparada — até a condição que ela guarda ser efetivamente cumprida. Orientações com `priority` diferente de `critical` continuam com o comportamento antigo: só aparecem no turno em que o `last_trigger_active` da sua posição é `True`.

**Avaliação por tipo de trigger:**

| Trigger | Condição de `fired = True` |
|---|---|
| `phase_trigger` | `is_phase_entry = True` — derivado de `lead.category != effective_route_to` **E** `phase_id ∉ leads.phases_triggered` — **e** nenhum gatilho sequencial anterior bloqueado (não se aplica ao `phase_trigger`, que é sempre o primeiro da fase) |
| `kw_trigger` | Keyword match na mensagem + `fire_once` check (`block_id ∉ leads.triggers_fired` se `fire_once=True`) + gating sequencial se `sequential=True` (fallback `fire_once=True` sem o campo novo) |
| `intent_trigger` | `intent_label in detected_intents` (da LLM Mãe) + `fire_once` check + gating sequencial se `sequential=True` (fallback `fire_once=True` sem o campo novo) |
| `block_trigger` | Sem condição de conteúdo — dispara sempre que não `_locked` (ou seja, assim que `requires_block_id` estiver satisfeito) **e** `block_id ∉ leads.triggers_fired` (checagem obrigatória — este tipo não tem nenhum outro mecanismo de "uma vez só") |
| `no_reply_trigger` | Nunca (placeholder) |

**Destino das ações:**

| Ação | Destino |
|---|---|
| `orientacao` | `result["prompt_injections"]` → injectado no prompt filho |
| `mensagem` | `result["system_actions"][{type:"send_message", content}]` |
| `midia` | `result["system_actions"][{type:"send_media", media_url, media_type}]` |
| `avancar_fase` | `result["system_actions"][{type:"advance_phase", target_phase}]` |

**Contexto para o LLM filho (quando `phase_trigger` dispara):**

O engine adiciona um preamble a `prompt_injections` seguido das mensagens/mídias automáticas enviadas. O LLM filho recebe o contexto do que foi enviado e deve complementar — não repetir.

**Contexto para o LLM filho (quando `midia`/`mensagem` dispara SEM `phase_trigger`):**

Como a ordem de despacho manda essas mensagens/mídias **depois** da resposta da LLM (ver tabela abaixo), o engine injeta uma nota combinada em `prompt_injections` — `"[FLUXO DE VENDA — envio automático pendente: ...]"` — avisando que o conteúdo ainda não foi enviado, para a LLM frasear no futuro (ex.: "vou te mandar já") em vez de tratar como já entregue (ex.: "aqui está"). Uma nota só por resposta, mesmo com múltiplos blocos `midia`/`mensagem` pendentes.

**Supressão da LLM (`suppress_llm_response`):**

Se `result["suppress_llm_response"] = True`, `compose_decision_output()` força `next_action = "ignore"` e `message_text = ""`. As `system_actions` são preservadas e despachadas normalmente.

### Guardrail de gatilhos pendentes bloqueia avanço automático de fase

O gating sequencial descrito acima só se aplica **dentro** da fase para onde `effective_route_to` aponta neste turno — não impede, por si só, que a **Mãe** (via `route_to`) ou a **Filha** (via o sinal `did_complete_phase`) decidam avançar para uma fase **seguinte**, pulando a fase inteira (e todo o seu Fluxo de Venda) num único turno. Isso acontece na prática quando o lead responde de forma ambígua (ex.: "ok") e a Mãe interpreta como sinal suficiente para avançar, ou quando a Filha sinaliza conclusão da fase antes de o gatilho configurado ter tido chance de disparar.

`_phase_pending_sequential_triggers(phase_id, ai_profile, triggers_fired)` (`decision_engine.py`) resolve os `block_id`s de `kw_trigger`/`intent_trigger` sequenciais (`sequential: true`, fallback `fire_once: true` sem o campo novo) ou `block_trigger` (sempre sequencial) configurados numa fase que ainda não dispararam. Lista vazia = sem gate — `sales_flow` desligado, fase inexistente no profile, ou nenhum gatilho sequencial configurado nela (ou todos já dispararam). Opt-in: só há pendência quando o utilizador configurou explicitamente pelo menos um gatilho sequencial nessa fase.

Este helper é consultado em dois tipos de ponto, por fase:

**Ao nível da Mãe** (bloqueia `route_to` saltando a fase inteira num turno) — guardrails dedicados, chamados em sequência em `decide()` logo após `_enforce_qualification_route_when_missing`/`_enforce_greeting_first`/`_enforce_scheduling_agent_no_closing`:

```
se lead "engajado" com <fase> (phases_triggered contém "<id>" OU lead.category == "<fase>")
   e mother_decision.route_to ∈ _ALLOWED_ADVANCE["<fase>"] (tentando sair dela):
       pendentes = _phase_pending_sequential_triggers("<id>", ai_profile, triggers_fired)
       se houver pendentes:
           força mother_decision.route_to = "<fase>"
```

- `_enforce_apresentation_sales_flow_pending` — p2 (apresentação)
- `_enforce_pre_agendamento_sales_flow_pending` — p3a (pré-agendamento), só relevante para o modo `agenda` (único que visita esta fase)
- `_enforce_agendamento_sales_flow_pending` — p3b (agendamento), mesmo template do bloco acima, sem diferenças estruturais; só relevante para templates com fase de agendamento (`_SCHEDULING_AGENT_TEMPLATES`)
- `_enforce_followup_sales_flow_pending` — p4 (follow-up), com 1 diferença estrutural: "engajado" usa **só** `lead.category == "follow-up"` — nunca `"p4" in phases_triggered` (diferente de todas as outras funções deste grupo). `phases_triggered` é cumulativo e o check-in automático de relacionamento pós-venda (`start_client_checkin_followup`, `followup_state.py`, `followup_variant="client_checkin"`) reusa a fase p4 sem mover `lead.category` para `"follow-up"` (o lead permanece em `"client-list"`) — usar o sinal de `phases_triggered` faria o guardrail intervir também nesse check-in, onde a semântica de "gatilhos pendentes de venda" não se aplica. Não interage com o subsistema de ticks agendados (`whatsapp.followup.tick`): o resultado de `decide()` durante um tick é descartado por `complete_job_internal` (`backend-crm/routes/executor.py`) — só `job_type == "whatsapp.inbound.n8n"` persiste `suggested_category`/`system_actions`; o guardrail roda no tick mas não tem efeito nele.
- `_enforce_recepcao_sales_flow_pending` — p0 (recepção), com 2 diferenças estruturais face ao template acima:
  1. **Condição de "engajado" invertida** — `current_category == "recepcao"` nunca é persistido em `leads.category` (só existe como `route_to` efémero; ver `orchestrator_models.py`). O guardrail usa o sinal oposto: o lead ainda não passou de `"qualification"` no pipeline (`to-prospect`/`in-progress`/ausente/já `"qualification"`).
  2. **Teto de 1 turno extra** (`_MAX_RECEPCAO_ENFORCED_OUTBOUND_TURNS`) — a Filha Recepção é desenhada para um único turno ("Seu papel dura só este turno", `_build_child_prompt_recepcao`). Sem teto, o guardrail forçaria `route_to="recepcao"` indefinidamente enquanto o gatilho de p0 não disparasse, repetindo a saudação em plena conversa real. A partir do 2º turno após `_enforce_greeting_first` (que já cobre o 1º turno incondicionalmente), o guardrail falha aberto — nunca mais intervém.

  `_ALLOWED_ADVANCE["recepcao"] = {"qualification"}` (único destino legítimo a partir da recepção) foi adicionado só para este guardrail — `_STAGE_ORDER`/`_STAGE_INDEX` (usados por `apply_mother_category_guardrails`) não foram tocados, pois `"recepcao"` nunca aparece como valor de `lead.category`.

  **Aviso no builder:** `CamadaFluxoVenda.tsx` mostra um banner somente-leitura na Fase 0 quando a configuração excede o que o teto de 1 turno cobre — mais de 1 bloco `kw_trigger`/`intent_trigger` sequencial (`isSequentialCapable()`, escopo raiz, exclui `phase_trigger`) ou qualquer nó `condicao` presente.

**Qualificação (p1) não tem um guardrail dedicado ao nível da Mãe (auditado, cobertura indireta considerada suficiente)** — a saída de p1 é decidida por "missing_fields vazio", não por `route_to` direto, em 3 pontos independentes que promovem `route_to`/`effective_route_to` para `"apresentation"`: Regra 3 e o auto-promote de runtime (`decide()`), e a Regra 1 + fallback `ask_qualification` (`compose_decision_output()`). Os 3 são gateados por `not _phase_pending_sequential_triggers("p1", ...)`, exceto o escape valve `is_upper_stage` da Regra 3 (lead já numa fase posterior cuja Mãe tentou rotear de volta para qualificação por engano — não é "saindo de p1 agora", não deve ser bloqueado por pendência de p1).

**Ao nível da Filha** (bloqueia `suggested_category` avançando via `did_complete_phase` — sinal não-determinístico da própria Filha, que pode contornar o guardrail da Mãe acima): gate `and not _phase_pending_sequential_triggers(...)` adicionado às condições já existentes em `compose_decision_output()`:
- `apresentation_complete_auto_advance` — fase `"p2"`
- `pre_agendamento_complete_auto_advance` — fase `"p3a"`

**Por que `phases_triggered` e não só `lead.category`** (nos guardrails de Mãe): testes ao vivo mostraram `leads.category` podendo ficar defasado — a Mãe gera conteúdo da fase via `route_to` num turno sem que a categoria persistida do lead necessariamente seja atualizada para o mesmo valor (esse campo depende de `perceived_category` + `apply_mother_category_guardrails`, um mecanismo separado de `route_to`). `leads.phases_triggered` conter o id da fase é o sinal mais confiável de que o `phase_trigger` dela já disparou para aquele lead.

**Escopo, o mesmo em toda fase:** só gatilhos "sequenciais" (`kw_trigger`/`intent_trigger` com `sequential: true` — fallback `fire_once: true` sem o campo novo —, ou `block_trigger`, sempre sequencial — mesmo critério de `_is_sequential_trigger_block()`) contam como pendência. `no_reply_trigger` e gatilhos com `sequential: false` nunca participam — são reavaliados a cada turno, sem estado persistido de satisfação para efeitos de fila (mesmo que `fire_once` esteja marcado — nesse caso o registo existe só para suprimir re-disparo, não para o gating).

**Cobertura completa (auditada):** p0, p2, p3a, p3b e p4 têm guardrail dedicado ao nível da Mãe
(lista acima). p1 tem cobertura indireta considerada suficiente (ver acima) — o único bypass
(`is_upper_stage`) é intencional, não uma lacuna. **p5 (fechamento) e `client-list` não
aplicam**, por razões estruturais diferentes:

- **p5 é terminal** — `_STAGE_ORDER`/`_ALLOWED_ADVANCE` não têm entrada de saída a partir de
  `"closing"`, e `MotherDecision.route_to`/`perceived_category` (Literal, `orchestrator_models.py`)
  não aceitam nenhum valor além de `"closing"`. Não há "próximo destino" a proteger — o guardrail
  equivalente (proteger a *entrada* prematura em closing) é `_enforce_followup_sales_flow_pending`
  (p4 → closing), já listado acima.
- **`client-list` não é uma fase do Fluxo de Venda** — não tem `phase_id` em
  `_ROUTE_TO_PHASE_ID`/`_CATEGORY_TO_PHASE_ID`; a transição para lá acontece via webhook de
  pagamento (`backend-crm/routes/webhooks.py`), fora de `decide()`; e o check-in de
  relacionamento pós-venda que roda com o lead nessa categoria reusa a fase p4 (ver acima), sem
  fase própria a consultar.

### Lógica de Ramificação (`condicao`)

Nó de bifurcação real, estilo ManyChat/n8n: N caminhos nomeados, cada um com o seu critério de avaliação pela LLM Mãe, cada um contendo os seus próprios blocos filhos. Depois de um lead seguir por um caminho, os blocos dos caminhos irmãos ficam fora do prompt enviado à IA (redução de poluição de tokens).

**Modelo de dados** (`SalesFlowBlock`, `frontend-crm/src/types/agente.ts`):

```ts
interface SalesFlowBranch { id: string; label: string; criteria: string }

// no nó condicao (typeId === 'condicao'):
branches?: SalesFlowBranch[]   // caminhos nomeados, mínimo 2
sticky?: boolean               // default true — fixa o caminho escolhido após a 1ª vez

// em qualquer bloco filho pertencente a um caminho:
branch_group_id?: string       // id do bloco condicao pai
branch_id?: string             // id do caminho (SalesFlowBranch.id) dentro desse nó
```

Blocos filhos vivem na mesma lista plana `phase.blocks[]` — não há árvore aninhada no JSON; o agrupamento visual (`CamadaFluxoVenda.tsx::PhaseSection` → `BranchGroupRow`) é reconstruído a partir de `branch_group_id`/`branch_id`. Sem ramificação de segundo nível nesta versão (um caminho não pode conter outro nó `condicao`) — o modelo de dados já suporta via `branch_group_id` genérico, mas o editor visual não expõe.

**Papel da Mãe — bloco `[LÓGICA DE RAMIFICAÇÃO]` + `branch_selections`:** mesma mecânica do `[DETECÇÃO DE INTENÇÃO]`, sem chamada extra de LLM. `_collect_branch_nodes_for_lead_phase(context, agent_mode_normalized)` coleta os nós `condicao` com `branches` configurados da fase **atual** do lead e da fase **seguinte** (lookahead de 1 fase via `_SALES_FLOW_PHASE_SEQUENCE_BY_AGENT_MODE` — mesmo motivo do lookahead de `intent_trigger`: uma transição de fase decidida neste turno não pode ficar cega ao nó da fase de destino). Nós `sticky` já resolvidos (`leads.branches_selected`) não são listados de novo — a mãe não reavalia o que já foi decidido.

`_build_mother_prompt()` lista, por nó, os caminhos com `id`/`label`/`criteria`, e pede à Mãe para preencher `branch_selections: {node_id: branch_id}` — se nenhum caminho tiver evidência clara na conversa, a lógica é **omitida** do objeto (não força escolha sem sinal). O campo está listado tanto no schema JSON explícito (bloco "Retorne SOMENTE JSON válido no schema MotherDecision") quanto no texto descritivo do bloco `[LÓGICA DE RAMIFICAÇÃO]` — os dois precisam estar sincronizados, já que a LLM segue o schema explícito com mais fidelidade do que instruções soltas mais acima no prompt. `MotherDecision.branch_selections: Dict[str, str]` (`orchestrator_models.py`) chega no mesmo JSON de `route_to`/`detected_intents`.

**Resolução do ramo activo** — dentro de `_evaluate_sales_flow_phases()`, ao encontrar um bloco `typeId == "condicao"`:
1. Se `sticky=True` e já persistido em `leads.branches_selected` → usa a escolha persistida.
2. Senão, usa `branch_selections[node_id]` vindo da Mãe neste turno.
3. Se resolvido, regista em `_active_branches[node_id] = branch_id` para o resto da passagem; se `sticky` e ainda não persistido, emite `system_actions: [{type: "mark_branch_selected", block_id, branch_id}]`.
4. Se não resolvido (Mãe sem sinal suficiente ainda), nenhum caminho fica activo neste turno — todos os blocos filhos desse nó são ignorados por completo (nem `prompt_injections`, nem `system_actions`).

Cada bloco seguinte com `branch_group_id` só é avaliado se `branch_id` bate com `_active_branches[branch_group_id]` — senão é ignorado por completo. É aqui que a redução de poluição de tokens dos caminhos irmãos acontece de facto.

**Escopo do gating sequencial:** o mecanismo de `_prereqs_satisfied` (ver "Modelo sequencial de trigger" acima) passa a ser **por escopo** — `"root"` para blocos fora de qualquer caminho, `"{branch_group_id}:{branch_id}"` dentro de um. Cada escopo começa desbloqueado de forma independente: um `kw_trigger`/`intent_trigger` sequencial dentro do Caminho A nunca bloqueia nem é bloqueado por nada do Caminho B — são mutuamente exclusivos do mesmo nó.

**Persistência sticky:** coluna `leads.branches_selected TEXT NULL` (JSON `{block_id: branch_id}`, `ensure_column()` em `backend-crm/database.py`) — mesmo padrão de `triggers_fired`. `mark_branch_selected` é despachado por `executor.py`/`playground.py` (mesmo padrão de `mark_trigger_fired`). Default do checkbox "fixar caminho" no builder é `true`.

**No frontend:** `emptyBlock('condicao')` semeia 2 caminhos + `sticky=true`. No loop de agrupamento de `PhaseSection`, o próprio nó `condicao` é um item comum de `group.actions` — como `orientacao`/`mensagem`/`midia` — herdando visualmente (recuo, linha conectora) o grupo do gatilho que o precede no array; só a renderização do item individual muda (`<BranchGroupRow>` em vez de `<BlockRow>`). Isto espelha o `last_trigger_active` do backend (ver "Modelo sequencial de trigger" acima): o `condicao` nunca é um boundary de grupo de nível raiz por si só. Separadamente, `PhaseSection` também reconhece blocos com `branch_group_id` e sub-agrupa por `branch_id` num `BranchGroupRow` próprio, dentro do card do `condicao`; `saveBranchBlock()` insere um bloco novo no fim do caminho selecionado. Remover o nó `condicao` faz cascade-delete de todos os blocos filhos (mesmo `branch_group_id`). `BlockModal`, ao adicionar bloco a um caminho, recebe `excludeTypes=['condicao']` — sem ramificação de segundo nível, mas o caminho pode ter o seu próprio `kw_trigger`/`intent_trigger`.

### Pausa do Fluxo (`espera` / Smart Delay)

Bloco de ação (typeId `espera`): quando dispara (mesma regra `last_trigger_active` de qualquer outra ação), pausa o restante da fase por um tempo definido (`wait_value` + `wait_unit`, minutos/horas/dias) — os gatilhos e ações que vêm **depois** dele na mesma fase (mesmo escopo — raiz ou o mesmo caminho de um `condicao`) não são avaliados enquanto a pausa está ativa, nem no turno em que disparou nem nos turnos seguintes.

**Checkbox `allow_llm_during_wait`** (default `true`, "Responder dúvidas durante a espera" no builder):
- `true` — a LLM filha continua respondendo normalmente a qualquer mensagem do lead durante a pausa; só as ações automáticas do Fluxo de Venda abaixo do `espera` ficam paradas.
- `false` — pausa total: `result["suppress_llm_response"] = True` é forçado em todo turno dentro da janela (reaproveita o mecanismo já existente de `suppress_llm_response`, ver "Flags opcionais em blocos de trigger" acima) — o bot não responde nada enquanto o tempo está correndo.

**Persistência:** coluna `leads.sales_flow_wait TEXT NULL` (JSON `{until, block_id, phase_id, suppress_llm}`, `ensure_column()` em `backend-crm/database.py`) — mesmo padrão de `branches_selected`. Ações despachadas por `executor.py`/`playground.py`: `sales_flow_pause_set` (grava o JSON ao disparar) e `sales_flow_pause_clear` (limpa quando `decision_engine` detecta que `until` já passou). Mutação de estado pura, sem side-effect externo — roda de verdade também no Playground.

**Gate em runtime (`_evaluate_sales_flow_phases`):** no início da avaliação, `_load_sales_flow_wait()` lê o estado persistido; se `phase_id` bate com a fase sendo avaliada e `until` ainda está no futuro, o gatilho de origem (`block_id`) é usado como marco: ao alcançá-lo durante a passagem pelos blocos da fase, o escopo (`_scope_key`, mesmo conceito usado pelo gating sequencial de `condicao`) é marcado como pausado — todo bloco seguinte do mesmo escopo é ignorado por completo (nem gatilho é avaliado, nem ação executa), incluindo na segunda passagem de orientações críticas (guarda permanente). Se `until` já expirou, o gate não se aplica (fica no-op) e a fase é reavaliada normalmente — incluindo o próprio bloco `espera`, que pode disparar de novo se o gatilho que o precede voltar a bater.

### Ordem de exibição / envio

| Cenário | Ordem |
|---|---|
| `phase_trigger` disparou | Auto-mensagens → LLM |
| `kw_trigger` ou `intent_trigger` disparou (sem `suppress_llm_response`) | LLM → Auto-mensagens |
| `suppress_llm_response = True` | Apenas auto-mensagens (LLM omitido) |
| Nenhum trigger activo | Apenas LLM |

---

## Dispatch de system_actions (executor CRM)

Após receber o `DecisionOutput`, o `backend-crm/routes/executor.py` chama `_dispatch_system_actions()`:

```python
_PHASE_ID_TO_CATEGORY = {
    "p1":  "qualification",
    "p2":  "apresentation",
    "p3a": "apresentation",
    "p3b": "apresentation",
    "p4":  "followup",
    "p5":  "closing",
}
```

| `action.type` | O que faz |
|---|---|
| `send_message` | Cria job `whatsapp.send.local` com o texto do campo `content` |
| `send_media` | Cria job `whatsapp.send.local` com `media_url` e `media_type` |
| `advance_phase` | Resolve `target_phase` via `_PHASE_ID_TO_CATEGORY` → chama `apply_suggested_category()` |
| `mark_phase_triggered` | Append do `phase_id` em `leads.phases_triggered` |
| `mark_trigger_fired` | Append do `block_id` em `leads.triggers_fired` |
| `webhook` | Monta payload (lead + `note`/`url`/`method`/`block_id`/`phase_id`) e cria job `sales_flow.webhook.dispatch` — ver secção dedicada abaixo |
| `sales_flow_pause_set` | Grava `{until, block_id, phase_id, suppress_llm}` em `leads.sales_flow_wait` |
| `sales_flow_pause_clear` | Limpa `leads.sales_flow_wait` (`NULL`) — emitido quando `decision_engine` detecta que a pausa já expirou |

---

## Execução do bloco `webhook`

Chamada HTTP externa despachada de forma **assíncrona**, via job dedicado —
mesmo padrão estrutural do worker de email (`email.send.cold`), não o do
worker pesado de WhatsApp (que está acoplado ao pipeline de geração de
resposta via LLM). O `webhook` é uma chamada de I/O independente do LLM, que
não deve bloquear a conclusão do job de inbound nem a resposta ao lead.

```
decision_engine.py → system_action {type: "webhook", url, method, note, block_id, phase_id}
  ↓
executor.py::_dispatch_system_actions() → create_job("sales_flow.webhook.dispatch",
  {lead_id, phone, name, email, url, method, note, block_id, phase_id, triggered_at})
  ↓
backend-executors/app/workers/sales_flow_webhook_worker.py (polling dedicado)
  ↓
backend-executors/app/runners/sales_flow_webhook.py::execute_job()
  → GET: query params simples | POST/PUT: corpo JSON com o payload completo
  → 2xx → complete_job | timeout/erro de rede/5xx/429 → fail_job(retryable=True)
  → 4xx específico → fail_job(retryable=False)
```

- **Retry:** usa os defaults genéricos de `jobs_service.py` (`JOB_MAX_ATTEMPTS=3`,
  backoff `{1: 60s, 2: 180s}`) — sem override por tipo.
- **Timeout:** 10s por chamada (`REQUEST_TIMEOUT_SECONDS` em `runners/sales_flow_webhook.py`).
- **Playground:** nunca dispara a chamada HTTP real (mesmo princípio de
  `send_message`, que no sandbox só aparece no chat simulado). `playground.py`
  adiciona um `auto_item` de texto ("🌐 Webhook (simulado): MÉTODO url — nota"),
  sem criar job nem tocar rede.
- **Sem suporte a headers customizados/autenticação** — a UI do builder
  (`CamadaFluxoVenda.tsx`) não tem esses campos; limitação conhecida.
- **Sem allowlist de domínio/SSRF guard** — a URL é configurada pelo próprio
  dono da conta, mesmo nível de confiança já usado para outras integrações
  configuradas pelo usuário no sistema.

---

## WhatsApp real — runner (`whatsapp.py`)

Após `decision_engine.decide()`, o runner classifica as `system_actions` em dois grupos:

```python
_send_actions  = [a for a in system_actions if a["type"] in ("send_message", "send_media")]
_state_actions = [a for a in system_actions if a["type"] not in ("send_message", "send_media")]
```

- **`_send_actions`** são despachados sincronamente via `_send_sales_flow_action()` (chamada directa à API do WhatsApp), antes ou depois da mensagem LLM consoante `phase_trigger_fired`.
- **`_state_actions`** são passados ao CRM no `result_payload["system_actions"]` para persistência (executor.py os processa via `_dispatch_system_actions()`).

Comportamento especial quando `suppress_llm_response=True`:
- `_send_actions` são despachados normalmente (sem mensagem LLM)
- Job completa com `outbound_status = "skipped_suppress_llm"`

---

## Armazenamento

O Fluxo de Venda é salvo no campo `sales_flow` da tabela `ai_profiles` (backend-core), como JSON:

```json
{
  "phases": [
    {
      "id": "p0",
      "blocks": []
    },
    {
      "id": "p2",
      "blocks": [
        {
          "id": "uuid",
          "typeId": "orientacao",
          "content": "Apresente a oferta principal no início da conversa.",
          "priority": "high"
        }
      ]
    }
  ]
}
```

O campo é lido pelo orchestrator do CRM e inserido no `ContextBundle` via `enrich_context_bundle()`, chegando ao executor no `context.ai_profile.sales_flow`.

**Colunas adicionais em `leads` (backend-crm):**

| Coluna | Tipo | Descrição |
|---|---|---|
| `phases_triggered` | `TEXT NULL` | JSON array de phase IDs disparados por este lead (ex: `["p2", "p3a"]`) |
| `triggers_fired` | `TEXT NULL` | JSON array de block IDs já disparados pelo menos uma vez — `fire_once: true` (suprime re-disparo) e/ou `sequential: true` (registo de "já passou por aqui" para o gating, mesmo repetível) (ex: `["uuid1", "uuid2"]`) |
| `branches_selected` | `TEXT NULL` | JSON `{block_id: branch_id}` — ramos escolhidos por nós `condicao` com `sticky=true` |
| `sales_flow_wait` | `TEXT NULL` | JSON `{until, block_id, phase_id, suppress_llm}` — pausa ativa de um bloco `espera`, ver "Pausa do Fluxo" acima |

Todas adicionadas via `ensure_column()` em `backend-crm/database.py`.

---

## Visualização no Kanban (funil resumido)

O card do lead no Kanban (`frontend-crm/src/components/LeadCard.tsx`) mostra um breadcrumb compacto — uma bolinha por fase do pipeline do `agent_mode` da conta — resumindo o progresso do lead no Fluxo de Venda, sem detalhar os gatilhos individuais.

**Dados usados** (já expostos pela API de leads via `dict(row)`, sem endpoint novo):
- `lead.category` → fase atual, mapeada para `phase_id` por uma tabela local em `LeadCard.tsx` (`CATEGORY_TO_PHASE_ID`, espelha `_ROUTE_TO_PHASE_ID` do backend)
- `lead.phasesTriggered` (`leads.phases_triggered` parseado em `LeadsContext.tsx::mapRawLead()`) → fases já disparadas (concluídas)

**Sequência de fases:** `KanbanBoard.tsx` busca `ai_profile.agent_mode` **uma única vez** por sessão (não por card — uma conta tem um único AI Profile) no mesmo `useEffect` que já resolvia `profileAgentType`, deriva a sequência via `SALES_FLOW_PHASES_BY_AGENT_MODE` (mesma normalização do builder: `sdr_scheduler`→`agenda`, `closer`→`direto`) e passa como prop (`phaseSequence`) através de `KanbanColumn` até `LeadCard`.

**Estado de cada bolinha** (componente `SalesFlowFunnel` em `LeadCard.tsx`):
- **Concluída:** `phase_id ∈ lead.phasesTriggered`, ou fase anterior à atual na sequência (fallback para leads sem `phases_triggered` populado)
- **Atual:** `phase_id === CATEGORY_TO_PHASE_ID[lead.category]` — bolinha maior, com contorno
- **Futura:** as demais — cor apagada (baixa opacidade)

Cor de cada fase vem de `SALES_FLOW_PHASE_COLORS` (`frontend-crm/src/types/agente.ts`), partilhada com o builder (`CamadaFluxoVenda.tsx`) para a mesma fase ter sempre a mesma cor nos dois lugares.

---

## Arquivos críticos

| Arquivo | Responsabilidade |
|---|---|
| `frontend-crm/src/types/agente.ts` | Tipos TypeScript: `SalesFlowPhaseId`, `SalesFlowBlock`, `SalesFlowPhaseData`, `SALES_FLOW_PHASES_BY_AGENT_MODE`, `SALES_FLOW_PHASE_COLORS` |
| `frontend-crm/src/components/agente/CamadaFluxoVenda.tsx` | Builder visual: renderização de fases, blocos, formulários de configuração |
| `backend-executors/app/services/decision_engine.py` | `_evaluate_sales_flow_phases()` — avaliação de triggers, resolução de ramos (`condicao`), gate de pausa (`espera`), coleta de orientações/mídia/system_actions; `_collect_intent_triggers_for_lead_phase()` — seleciona quais `intent_trigger` mostrar à mãe (fase atual + seguinte); `_collect_branch_nodes_for_lead_phase()` — idem para nós `condicao` (fase atual + seguinte); `_load_branches_selected_map()` — lê `leads.branches_selected`; `_load_sales_flow_wait()`/`_sales_flow_wait_timedelta()` — lê `leads.sales_flow_wait` e converte `wait_value`/`wait_unit` num timedelta; `_build_block_lookup()`/`_requires_block_satisfied()` — resolução da dependência explícita `requires_block_id`; `_enforce_apresentation_sales_flow_pending()`/`_enforce_pre_agendamento_sales_flow_pending()`/`_enforce_recepcao_sales_flow_pending()` — guardrails que impedem a Mãe de pular p2/p3a/p0 com gatilhos sequenciais pendentes (p0 com teto de 1 turno extra); `_compute_is_phase_entry()` — cálculo único de `is_phase_entry`, reutilizado tanto na construção do prompt filho (`_build_child_prompt_recepcao/qualification/apresentation/follow_up`) quanto no despacho real de `system_actions` em `compose_decision_output()` |
| `backend-executors/app/services/orchestrator_models.py` | `MotherDecision.branch_selections: Dict[str, str]` |
| `backend-crm/routes/executor.py` | `_dispatch_system_actions()`, `_dispatch_sales_flow_media()`, `_PHASE_ID_TO_CATEGORY` |
| `backend-crm/services/jobs_service.py` | `TYPE_SALES_FLOW_WEBHOOK` |
| `backend-executors/app/runners/sales_flow_webhook.py` / `app/workers/sales_flow_webhook_worker.py` | Execução assíncrona do bloco `webhook` — ver "Execução do bloco `webhook`" acima |
| `backend-core/app/models/ai_profile.py` | Campo `sales_flow` na tabela `ai_profiles` |
| `backend-crm/services/ai_orchestrator/orchestrator.py` | `enrich_context_bundle()` — inclui `sales_flow` no ContextBundle; `_resolve_sales_flow_variables()` — resolve `{{}}` no `content` de blocos `orientacao`/`mensagem` (ver [`dynamic-variables.md`](dynamic-variables.md)) |
| `frontend-crm/src/components/KanbanBoard.tsx` / `KanbanColumn.tsx` / `LeadCard.tsx` | Funil visual resumido no card — ver "Visualização no Kanban" acima |
