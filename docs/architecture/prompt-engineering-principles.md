# Princípios de Engenharia de Prompt

## Quando ler este documento

Antes de criar ou editar qualquer prompt de LLM Mãe/Filha em
`backend-executors/app/services/decision_engine.py`, o extrator de campos em
`field_extractor.py`, a geração de outreach em
`backend-crm/automations/assistente_ia/llm.py`, ou configurar blocos da
Camada 7 (`sales_flow`, ver [`sales-flow.md`](sales-flow.md)) que injetam
texto em algum desses prompts.

Este documento é **prescritivo** — não é um mapa do estado atual do sistema
(esse é o papel de [`docs/prompts_llms.md`](../prompts_llms.md), que lista
variável por variável de cada prompt real). Aqui o objetivo é: qual critério
usar para decidir *como* escrever ou revisar uma instrução de prompt, e onde
no nosso próprio código já existe um exemplo do padrão recomendado.

Cada princípio segue o mesmo formato: a regra, o motivo (com fonte), onde já
aplicamos no sistema (referência real de arquivo/função), e o gap conhecido
quando a regra não está 100% seguida hoje.

---

## 1. Guardrail de código > instrução em prompt para regras que não podem falhar

**Regra:** uma regra de negócio que não pode falhar (ex.: nunca avançar de
fase sem qualificação completa, nunca enviar link de checkout sem URL real)
deve ser aplicada em código — não só pedida ao LLM em texto.

**Por quê:** um prompt é uma sugestão que o LLM pode interpretar e "alucinar
cumprimento" — ele lê a instrução como contexto, não como limite rígido. Um
guardrail em código, ao contrário, intercepta a decisão antes de ela virar
efeito no sistema; o LLM não tem como contorná-lo. (Ver "AI Agent Guardrails:
Rules That LLMs Cannot Bypass", dev.to/aws.)

**Onde já aplicamos (bem):**
- Camada 7 — `_evaluate_sales_flow_phases()` e os guardrails
  `_enforce_apresentation_sales_flow_pending()` /
  `_enforce_pre_agendamento_sales_flow_pending()` /
  `_enforce_agendamento_sales_flow_pending()` /
  `_enforce_followup_sales_flow_pending()` /
  `_enforce_recepcao_sales_flow_pending()`
  (`backend-executors/app/services/decision_engine.py`) — sobrescrevem em
  código o `route_to` que o LLM Mãe decidiu, se houver gatilho sequencial
  pendente. Ver [`sales-flow.md`](sales-flow.md#guardrail-de-gatilhos-pendentes-bloqueia-avanço-automático-de-fase).
- `backend-crm/services/qualification_guardrails.py` — `can_advance_score_gate()` /
  `can_advance_from_qualification()`: bloqueiam avanço de categoria por
  código, independente do que o LLM sinalizou.
- `field_extractor.py` — filtro de confiança fail-closed: um campo extraído
  só é aceito se `confidence[key] >= threshold`; sem essa checagem em código,
  qualquer menção tangencial vira campo preenchido.

**Gap conhecido:** os blocos "PROIBIÇÕES" e "VALIDAÇÃO — VERIFICAR ANTES DE
RETORNAR" nos prompts de Filha (ex.: "se `checkout_sent=true` →
`message_text` DEVE conter uma URL real") pedem que a própria LLM se
autoverifique antes de responder — não há checagem em código depois.
`_sanitize_signals_structured()` (`decision_engine.py:1837`) só faz whitelist
de chaves contra `SIGNALS_SCHEMA`, não valida semântica nenhuma (não checa
URL quando `checkout_sent=true`, não checa preço contra `offer_pack`, não
verifica se um nome de concorrente vazou pra `message_text`). Ainda não
corrigido — candidato a uma implementação própria (`docs/plans/*-melhorias-futuras.md`)
com seus próprios testes, não faz parte deste documento.

---

## 2. Instrução positiva > instrução negativa

**Regra:** dizer o que o LLM deve fazer é mais confiável do que listar o que
ele não deve fazer. Se for necessário proibir algo, reformule também o
comportamento alternativo esperado.

**Por quê:** modelos seguem melhor uma ação afirmativa do que a negação de
uma ação — uma lista longa de "NUNCA X" tende a ser seguida com menos
consistência do que a mesma regra reescrita como instrução positiva.

**Gap conhecido:** os blocos "PROIBIÇÕES" replicados em `qualification`,
`apresentation` e outras Filhas (`decision_engine.py`, linhas ~2984, ~3608,
~3959, ~4082) têm 7-10 regras no formato "NUNCA X" cada. É o padrão oposto ao
recomendado. Não reescrever agora — próxima vez que uma dessas Filhas for
revisada por outro motivo, vale reformular a proibição tocada em positivo
("se não tiver certeza, diga que vai verificar" em vez de só "nunca invente
informação").

---

## 3. Few-shot com exemplos positivos e negativos

**Regra:** 3-5 exemplos relevantes e diversos (cobrindo casos-limite)
ensinam melhor um padrão de resposta do que uma descrição longa da regra.
Combinar exemplo do que fazer (✅) com exemplo do que não fazer (❌) reforça
o contraste.

**Onde já aplicamos (bem):**
- `_build_mother_prompt()` — 11 casos few-shot cobrindo os 3 `agent_mode`
  em variações de saudação, fechamento e roteamento negativo (ver
  [`prompts_llms.md`](../prompts_llms.md#12-_build_mother_prompt--roteador-mãe)).
- `_build_child_prompt_recepcao()` — 3 exemplos ✅ e 3 exemplos ❌ hardcoded,
  iguais para qualquer usuário.
- `_build_child_prompt_apresentation()` — exemplos CONFIRMAR/ENVIAR LINK no
  modo `sales`.
- Meta-prompter (`generated_prompt_parts.few_shot_qualification` /
  `few_shot_apresentation` / `few_shot_followup`) — few-shot dinâmico por
  nicho, gerado por perfil.

Nenhum gap relevante identificado aqui — é a prática mais bem coberta do
sistema hoje.

---

## 4. Contexto/motivo por trás da regra

**Regra:** explicar o porquê de uma instrução ajuda o modelo a generalizar
melhor para casos não previstos do que só listar a regra seca.

**Onde já aplicamos (parcialmente):** o bloco "PRIORIDADE 0 — PRIMEIRO
CONTATO" da Mãe (`_build_mother_prompt()`) é o melhor exemplo no sistema —
explica *por que* a regra vence sobre qualificação ("é como um vendedor em
loja que ignora o 'bom dia' do cliente"), não só o quê fazer. A "REGRA
ANTI-REPETIÇÃO" também justifica o motivo.

**Gap conhecido:** a maioria das PROIBIÇÕES (ver princípio 2) são regras
secas sem motivo — "NUNCA dê conselhos médicos, jurídicos ou financeiros"
não explica por quê. Baixo risco de ambiguidade nesses casos específicos
(a regra é auto-explicativa), mas vale ter em mente ao escrever uma regra
nova menos óbvia.

---

## 5. JSON estruturado com schema reforçado, e validação de código depois

**Regra:** ao pedir JSON, use o mecanismo de schema reforçado da API quando
disponível (não só instrução textual "retorne JSON válido") e valide o
resultado em código antes de usar — nunca assuma que o parse bem-sucedido
significa que os valores estão corretos.

**Gap conhecido (já documentado no próprio sistema):** `generate_mother_route()`
usa `text.format.type="json_object"` solto, sem schema reforçado pela API —
por isso o campo `reason` (prosa livre) pode divergir de `detected_intents`
(lista estruturada) sem violar nenhuma validação. Ver
[`sales-flow.md`](sales-flow.md#-consistência-reason--detected_intents) para
o detalhamento e o motivo de isso não ter sido corrigido ainda (o bug
historicamente esteve na confiabilidade do prompt, não no motor de
avaliação). Não duplicar a investigação aqui — só linkar.

---

## 6. Permissão explícita para incerteza

**Regra:** dar autorização explícita para o modelo dizer "não sei" em vez de
arriscar uma resposta — reduz alucinação por adivinhação forçada.

**Onde já aplicamos (bem):** bloco "QUANDO NÃO SOUBER RESPONDER" presente em
`_build_child_prompt_qualification()` e `_build_child_prompt_apresentation()` —
instrui a retornar `confidence < 0.5`, fazer uma pergunta de esclarecimento
em vez de inventar, e sinalizar `signals_structured.handoff_requested = true`
quando a pergunta do lead está fora do knowledge fornecido.

Nenhum gap relevante identificado.

---

## 7. Minimalismo — auditar o prompt final, não só cada bloco isoladamente

**Regra:** "o melhor prompt não é o mais longo — é o que atinge o objetivo
com o mínimo de estrutura necessária." Cada bloco novo pode fazer sentido
isoladamente e ainda assim o prompt final ficar inchado ou redundante depois
de somado a todos os outros.

**Gap conhecido:** os prompts de Filha (especialmente
`_build_child_prompt_apresentation()`) empilham múltiplos blocos condicionais
— tom de voz, identidade comercial, warming/commercial injection, knowledge
base, meta-prompter (`generated_prompt_parts`), Camada 7 (`sales_flow`),
training examples do Playground — sem nenhum mecanismo que audite o
tamanho ou redundância do prompt final montado para um perfil real. Ao
adicionar um bloco condicional novo, vale perguntar: esse bloco pode
coexistir com os outros já injetados nessa fase sem se repetir ou
contradizer? (Ver também a nota já existente em
[`sales-flow.md`](sales-flow.md) sobre blocos `orientacao` em modo passivo
poderem contradizer a regra de "zero perguntas abertas".)

---

## 8. Esqueleto de um prompt de Filha

**Regra:** um prompt de Filha bem estruturado segue sempre a mesma sequência
de blocos: **IDENTIDADE** (o que ela é) → **O QUE FAZ** → **COMO FAZ** →
**O QUE NÃO FAZ** → **EXEMPLOS (✅/❌)** → **FORMATO DE SAÍDA**. Identidade e
escopo vêm primeiro porque ancoram a interpretação de tudo que vem depois;
exemplos ficam perto do fim, mais perto de onde a IA gera a resposta — é a
parte do prompt com mais peso sobre o resultado final.

**Por quê:** é a estrutura recomendada pelo guia oficial de boas práticas de
prompt engineering da Anthropic (2026): papel/identidade → função principal
(verbos diretos) → restrições (de preferência em positivo) → contexto/motivo
→ formato de saída → exemplos (fixos quando o padrão é sempre igual;
dinâmicos quando a tarefa varia caso a caso). Está alinhada aos princípios 2
e 6 deste documento.

**Onde já aplicamos (bem):**
- `_build_child_prompt_recepcao()` (`decision_engine.py:2569`) segue o
  esqueleto inteiro, 100% fixo: `IDENTIDADE` → `O QUE VOCÊ FAZ` →
  `COMO VOCÊ FAZ` → `O QUE VOCÊ NÃO FAZ` → `EXEMPLOS DO QUE FAZER (✅)` →
  `EXEMPLOS DE ERRO (❌)` → JSON de saída. Faz sentido ser 100% fixo porque
  os exemplos descrevem um **comportamento** (extrair pedido comercial
  embutido na saudação), não um fato de negócio — vale igual para qualquer
  nicho de cliente.
- `_build_child_prompt_closing()` (`decision_engine.py:3993`) segue o mesmo
  esqueleto com nomes de seção próprios — `PAPEL` / `ESCOPO` / `TOM` /
  `FRAMEWORK` / `RECUSAS` (= identidade + faz + não faz), `PROIBIÇÕES` (o que
  não faz, em lista), `_ESCAPE_HATCH_BLOCK` (permissão para dizer "não
  sei"), `_build_validation_block()` (checklist antes de retornar) — mas os
  **exemplos vêm de `_build_training_examples_block()`
  (`decision_engine.py:1211`)**, não hardcoded: são classificações reais de
  "bom"/"ruim" feitas pelo próprio operador no Playground
  (`context["training_examples"]`), few-shot dinâmico por negócio.

**Regra para multi-tenant (importante):** a **estrutura** do esqueleto
(quais blocos existem e em que ordem) é decidida por nós, no código — igual
para todo usuário. O **conteúdo** de cada bloco só pode ser hardcoded quando
descreve um padrão de comportamento universal do agente (ex.: "a Recepção
nunca responde ao pedido comercial, só o registra"). Qualquer exemplo que
cite preço, nome de serviço, oferta ou particularidade de nicho **tem que
vir de uma variável dinâmica por negócio** — meta-prompter
(`generated_prompt_parts`), `training_examples` do Playground, ou
`qualification_fields` configurados pelo usuário — nunca hardcoded num
prompt compartilhado por todos os usuários da plataforma.

**Gap conhecido:** nem toda Filha usa os mesmos *nomes* de seção — Recepção
usa "O QUE VOCÊ FAZ", Closing usa "PAPEL/ESCOPO". Não é uma contradição (é o
mesmo esqueleto com vocabulário diferente), mas padronizar os nomes de seção
entre Filhas é uma melhoria de baixo risco para uma implementação futura —
não corrigida aqui.

Fonte: [Prompt engineering best practices for 2026 — Claude by Anthropic](https://claude.com/blog/best-practices-for-prompt-engineering).

---

## 9. Achados de pesquisa aplicados ao nosso motor de LLM

Esta seção não documenta prática já aplicada — documenta 4 gaps encontrados
ao ler o cliente de LLM real (`backend-executors/app/services/llm_service.py`)
e cruzar com pesquisa de mercado. Nenhum é corrigido aqui: são candidatos a
implementação futura própria (mudança de código, com plano e testes
dedicados), igual ao padrão já usado para os gaps dos princípios 1 e 5.

### 9.1 — Nenhuma chamada define `temperature`

`_build_payload()` (`llm_service.py:154`) nunca envia `temperature` — fica
no default do provider (tipicamente 1.0, alto). Pesquisa de mercado:
tarefas de classificação/extração estruturada devem usar `temperature`
baixa (0.0–0.3) — criatividade nesse tipo de tarefa só aumenta o risco de
JSON malformado ou de inconsistência de rota. Isso vale para as chamadas
estruturadas do sistema (`generate_mother_route`, `generate_child_result`,
extração de campos) — não necessariamente para texto livre voltado ao lead
(`generate_conflict_message`, lembretes de agendamento), onde uma
temperature moderada continua fazendo sentido.

### 9.2 — `json_object` solto vs. Structured Outputs com schema reforçado

Concretiza o gap já citado no princípio 5 (que só dizia "não há schema
reforçado", sem apontar o mecanismo disponível). `_build_payload()`
(`llm_service.py:166-168`) usa `text.format.type="json_object"` — garante
sintaxe JSON válida, não que os campos/enums batem com o schema real
(`ChildResult`, `MotherDecision`). A Responses API da OpenAI já suporta
`text.format` com `type="json_schema"` + `schema` + `strict=true`: o modelo
literalmente não consegue emitir um token que quebre o schema (~100% de
aderência, contra ~80% do `json_object`). Isso ataca na raiz o exemplo já
citado no princípio 5 (`reason` divergir de `detected_intents`,
`checkout_sent=true` sem URL) — sem substituir a validação em código que o
princípio 5 já lista como pendente, e sim complementando-a (schema reforçado
reduz a chance do erro; validação em código continua como rede de segurança
final). **Ressalva:** só se aplica ao caminho OpenAI — o caminho OpenRouter
(Llama 3.3 / Hermes 3) usa Chat Completions com `response_format:
json_object` simples, sem suporte nativo equivalente confirmado.

### 9.3 — Nenhum isolamento entre a mensagem do lead e o texto de instrução

Em todos os builders de `decision_engine.py`, a mensagem do lead entra
direto no meio do prompt como texto solto (ex.: `f"Mensagem recebida:
{message_text}"`) — sem delimitador, sem instrução explícita de "isto é
dado do usuário, não comando". Como o sistema é multi-tenant e qualquer lead
do WhatsApp pode mandar texto arbitrário — inclusive tentando instruir a IA
a ignorar regras anteriores ou revelar o prompt do sistema — isso é uma
superfície de prompt injection ainda não tratada. Boas práticas de mercado
(OWASP GenAI LLM01:2025) recomendam: (1) delimitar claramente o conteúdo não
confiável (tags ou marcador textual), (2) instruir explicitamente que texto
dentro desse delimitador é dado, nunca instrução, (3) repetir a regra
crítica perto do fim do prompt, onde o modelo dá mais peso. Recomendação
concreta de formato: envolver a mensagem do lead em
`<mensagem_do_lead>...</mensagem_do_lead>` com uma frase fixa avisando que
esse conteúdo nunca deve ser tratado como instrução.

### 9.4 — Ordem do prompt não está otimizada para prompt caching automático

A OpenAI cacheia automaticamente (zero mudança de código) o maior prefixo
comum entre chamadas consecutivas que comece igual, acima de ~1024 tokens —
até 90% de desconto nos tokens cacheados e até 80% de redução de latência.
Isso é especialmente valioso aqui: o sistema chama a LLM a cada mensagem de
WhatsApp (alto volume). Hoje, em `_build_child_prompt_closing()` (mesmo
padrão nas outras Filhas), o bloco `FRAMEWORK: ... Missing:
{missing_fields}` — que muda a cada turno conforme o lead responde
perguntas de qualificação — aparece logo no início do prompt, antes de todo
o conteúdo 100% estático (JSON schema, PROIBIÇÕES, escape hatch, bloco de
validação). Isso invalida o prefixo cacheável muito mais cedo do que
precisaria. Recomendação: agrupar no início tudo que só depende do
`ai_profile`/`playbook` (estável entre TODOS os leads do mesmo negócio, não
só entre turnos do mesmo lead), e deixar para o final tudo que muda a cada
turno (missing_fields, history, inbound_message_text, fases do sales_flow
avaliadas). Isso maximiza cache hit não só entre turnos da mesma conversa,
mas potencialmente entre leads diferentes do mesmo negócio.

Fontes: [Introducing Structured Outputs in the API — OpenAI](https://openai.com/index/introducing-structured-outputs-in-the-api/), [LLM01:2025 Prompt Injection — OWASP GenAI](https://genai.owasp.org/llmrisk/llm01-prompt-injection/), [Prompt caching — OpenAI API docs](https://developers.openai.com/api/docs/guides/prompt-caching).

---

## Checklist rápida antes de shippar um prompt novo/editado

- [ ] Essa regra é crítica o suficiente para não poder falhar? Se sim, ela
      tem (ou devia ter) um guardrail de código equivalente — não só texto
      no prompt.
- [ ] A instrução está escrita como proibição ("nunca X")? Dá para
      reformular como ação positiva?
- [ ] Tem pelo menos 1 exemplo (✅ e, se for regra de exclusão, também ❌)
      em vez de só descrição da regra?
- [ ] A regra explica o motivo, ou só a instrução seca? Motivo ajuda o LLM a
      generalizar para casos não previstos.
- [ ] Se o output é JSON, o schema está reforçado pela API ou é só pedido em
      texto? Existe validação de código depois de receber a resposta?
- [ ] O LLM tem permissão explícita para dizer "não sei"/pedir handoff em
      vez de inventar?
- [ ] Esse bloco novo foi conferido junto dos outros blocos já injetados na
      mesma fase — sem repetição, sem contradição?
- [ ] O prompt segue o esqueleto do princípio 8 (identidade → faz → não faz
      → exemplos → formato de saída)? Os exemplos citados são só de
      comportamento (podem ser fixos) ou envolvem fato de negócio (têm que
      vir de variável dinâmica por usuário)?
- [ ] A mensagem do lead está delimitada e marcada como dado, não instrução
      (ver princípio 9.3)?
