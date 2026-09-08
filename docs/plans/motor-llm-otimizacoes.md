# Otimizações do motor de LLM (temperature, structured outputs, prompt injection, cache)

> Contexto: 4 achados levantados durante a implementação
> `prompt-engineering-principles` (Fase 3), ao ler o cliente de LLM real
> (`backend-executors/app/services/llm_service.py`) e cruzar com pesquisa de
> mercado. Chegaram a entrar como seção 9 em
> [`docs/architecture/prompt-engineering-principles.md`](../architecture/prompt-engineering-principles.md),
> mas foram removidos de lá (Fase 4) a pedido do usuário: aquele documento é
> conhecimento para escrever prompt **com o que já existe hoje**, não um
> lugar para otimizações futuras ainda não implementadas — esse é o papel
> deste arquivo. Quando um item aqui for implementado e mudar como um prompt
> deve ser escrito na prática (ver nota em M3 e M4), a instrução resultante
> volta para `prompt-engineering-principles.md` como parte da própria
> implementação.

## M1 — Definir `temperature` baixa nas chamadas estruturadas

**Prioridade: MÉDIA**

`_build_payload()` (`backend-executors/app/services/llm_service.py:154`)
nunca envia `temperature` — fica no default do provider (tipicamente alto).
Para as chamadas que geram JSON estruturado e precisam de consistência —
`generate_mother_route()` (rota da IA Mãe) e `generate_child_result()`
(resposta da Filha, incluindo extração de campo/sinais) — isso é fonte de
variância desnecessária: mesma situação, respostas de rota/campo
inconsistentes entre turnos.

**O que muda:** adicionar `temperature` baixa (ex.: 0.2) ao payload dessas
duas chamadas. `generate_conflict_message()` e os geradores de texto livre
(lembrete de agendamento/título) não entram — texto solto continua se
beneficiando de uma temperature moderada.

**Risco de fazer:** baixo — é 1 parâmetro por chamada, sem mudança de
prompt. Precisa de teste A/B ou monitorização pós-deploy para confirmar que
a taxa de erro de JSON/rota realmente cai (não é óbvio o quanto, sem medir).

## M2 — Structured Outputs (`json_schema` + `strict`) no caminho OpenAI

**Prioridade: ALTA**

`_build_payload()` (`llm_service.py:166-168`) usa `text.format.type=
"json_object"` — garante só sintaxe JSON válida, não que os campos/enums
batem com o schema esperado (`ChildResult`, `MotherDecision`). A Responses
API da OpenAI já suporta `type="json_schema"` + `schema` + `strict=true`,
que impede por decodificação qualquer token fora do schema (~100% de
aderência vs. ~80% do `json_object`).

Isso ataca na raiz um problema **já confirmado em produção** (ver
[`sales-flow.md`](../architecture/sales-flow.md#-consistência-reason--detected_intents)):
o campo `reason` da Mãe pode divergir de `detected_intents` sem violar
nenhuma validação hoje.

**O que muda:** definir os JSON Schemas de `MotherDecision` e `ChildResult`
(hoje só existem como contrato implícito no texto do prompt) e passá-los via
`text.format` quando `cfg.name == PROVIDER_OPENAI`. **Não se aplica** ao
caminho OpenRouter (Llama 3.3 / Hermes 3, via Chat Completions) — sem
suporte nativo equivalente confirmado; manter `json_object` nesse caminho.

**Risco de fazer:** médio — schema mal definido pode rejeitar respostas
válidas (ex.: campo opcional definido errado). Precisa de teste no
Playground contra os casos reais de `training_examples` antes de ir a
produção, e checar comportamento do fallback quando a API rejeita o schema.

## M3 — Isolar a mensagem do lead do texto de instrução (defesa contra prompt injection)

**Prioridade: MÉDIA**

Em todos os builders de `decision_engine.py`, a mensagem do lead entra
direto no prompt como texto solto (ex.: `f"Mensagem recebida:
{message_text}"`), sem delimitador nem aviso de que aquele conteúdo é dado
do usuário, não instrução. Como qualquer lead do WhatsApp pode mandar texto
arbitrário — incluindo tentativas de prompt injection ("ignore as regras
anteriores e...") — esta é uma superfície ainda sem tratamento específico
(ver OWASP GenAI LLM01:2025 — [genai.owasp.org/llmrisk/llm01-prompt-injection](https://genai.owasp.org/llmrisk/llm01-prompt-injection/)).

**O que muda:** envolver a mensagem do lead num delimitador claro (ex.:
`<mensagem_do_lead>...</mensagem_do_lead>`) em todos os builders de prompt,
com uma frase fixa avisando que o conteúdo dentro do delimitador é dado do
usuário e nunca deve ser seguido como instrução — reforçada perto do fim do
prompt (onde o modelo dá mais peso).

**Risco de fazer:** baixo — mudança aditiva no texto do prompt, não muda
schema de saída nem lógica de negócio. Vale testar no Playground que o
comportamento normal (sem tentativa de injection) não muda.

**Ao implementar:** este item muda como um prompt deve ser escrito de
verdade (todo prompt novo passa a precisar desse delimitador) — a
implementação deve incluir, como parte do próprio plano/fases, voltar a
`docs/architecture/prompt-engineering-principles.md` e adicionar essa regra
como princípio/checklist novo, com o formato exato já em uso no código.

## M4 — Reordenar o prompt da Filha para aproveitar prompt caching automático da OpenAI

**Prioridade: BAIXA**

A OpenAI cacheia automaticamente (sem mudança de código) o maior prefixo
comum entre chamadas consecutivas que comece igual, acima de ~1024 tokens —
até 90% de desconto nos tokens cacheados e 80% menos latência. Hoje, em
`_build_child_prompt_closing()` (mesmo padrão nas outras Filhas), o bloco
`FRAMEWORK: ... Missing: {missing_fields}` — que muda a cada turno — aparece
logo no início do prompt, antes de todo o conteúdo 100% estático (JSON
schema, PROIBIÇÕES, escape hatch, bloco de validação). Isso invalida o
prefixo cacheável mais cedo do que precisaria, num sistema que chama a LLM a
cada mensagem de WhatsApp (alto volume).

**O que muda:** reorganizar os builders de prompt de Filha para que tudo que
só depende de `ai_profile`/`playbook` (estável entre todos os leads do mesmo
negócio) fique agrupado no início, e tudo que muda a cada turno
(`missing_fields`, `history`, `inbound_message_text`, fases do sales_flow
avaliadas) fique no final.

**Risco de fazer:** baixo-médio — é reordenação de string, não muda o
conteúdo de nenhum bloco, mas toca em todos os builders de Filha (Recepção,
Qualification, Apresentation, Follow-up, Closing, Pré-agendamento,
Agendamento) — mudança de superfície ampla, ainda que mecânica. Vale medir
custo/latência real antes/depois via logs, já que o ganho depende do volume
de mensagens por conversa.

**Ao implementar:** este item redefine a ordem do esqueleto documentado no
princípio 8 de `prompt-engineering-principles.md` (hoje: identidade → faz →
não faz → exemplos → formato de saída). A implementação deve incluir voltar
lá e atualizar esse princípio para refletir a nova ordem real (bloco
estável-por-perfil primeiro, bloco dinâmico-por-turno por último) — sem
deixar o documento desalinhado do código.
