O objetivo é ter novas funcionalidades que agreguem na humanização de comportamento do agente.

Fase 1 - Melhorias básicas

**Melhorias de humanização**

- Quebra de mensagens longas em múltiplas mensagens curtas (2–3 linhas cada)
- Possível criação de um agente, ia ou função específica para dividir mensagens antes do envio , qual couber melhor.
- Nota de ideia: No comportamento humano nós enviamos a mensagem geralmente separadas por pontuação. A cada pontuação ". , … , ! , ? " é enviada uma mensagem.

**Funcionalidades pendentes**

- Envio de áudio:
    - Implementar envio de áudio (inicialmente áudio estático)
    - Nota: A ideia do "áudio estático" é o usuário fazer um upload em base de conhecimento e o sistema conseguir enviar como se fosse áudio gravado na hora. type= 
    • **`myaudio`**: Mensagem de voz (alternativa ao PTT) , para mais detalhes consultar: https://docs.uazapi.com/endpoint/post/send~media
- Comportamento:
    - API de "digitando"
    - API de "gravando áudio"
    - Quando aplicar: Toda vez que for antes de enviar a resposta de uma mensagem de mensagem ou áudio.

**Tempo de resposta**

O objetivo do tempo de resposta seria personalizar o período que o agente ficaria disponível para enviar as respostas. São boas práticas de uso e também evita respostas em horários indesejados pelos usuários.

- Configuração de tempo disponibilidade do agente para receber mensagens:
    - Online para receber mensagens - Horário comercial, 24h ou horário personalizado.
    - Respostas da primeira mensagem: Tempo variável (ex: 1–60 min, 1–3h)
    - Dentro da conversa: Tempo variável  (1 segundo - 5 minutos)
- Aplicação:
    - Horários de trabalho - período de envio das respostas.
    - Primeira mensagem (entrada do lead) - tempo mínimo para responder a primeira mensagem.
    - Respostas dentro da conversa - tempo mínimo para responder uma mensagem na conversa.
- Nota: Antes de aplicar, verificar se no ai-profile já tem essa funcionalidade, se sim, verificar se está implementada e detectar pendencias.

**Observação geral**

- Foco atual em ajustes, humanização e expansão de funcionalidades
- O plano deve garantir que este comportamento exista tanto no whats app nas conversas reais com os leads quanto no playground. Garantir que não tenham diferenças de resultados finais , para que o usuário consiga ter a segurança que seus testes serão aplicados na prática.

---

## Análise do sistema atual

*Escrita pelo Claude após leitura completa do código — abril 2026.*

### Visão geral

O sistema possui uma arquitetura sofisticada com playbooks, ContextBundle, AI Profiles e fila de jobs. Porém, **nenhum mecanismo de humanização está implementado hoje**: não há delays de resposta, nenhuma chamada a API de "digitando"/"gravando", e nenhuma quebra de mensagem por pontuação antes do envio. O comportamento atual é determinístico e instantâneo — a mensagem gerada pela LLM vai direto para a UazAPI sem nenhuma simulação de comportamento humano.

---

### 1. Quebra de mensagens por pontuação

**Estado atual:**
Existe uma função `format_whatsapp_or_dm()` em `backend-crm/automations/assistente_ia/text_renderer.py` que quebra o texto em blocos curtos de 2–4 linhas. Porém ela apenas formata o texto para exibição — o conteúdo ainda é enviado como **uma única mensagem** para a UazAPI.

O `backend-executors/app/runners/whatsapp.py` tem lógica para "mensagens extras" (split de texto longo), mas elas são enviadas em fire-and-forget sem nenhum delay entre si — chegam todas ao mesmo tempo no WhatsApp do lead.

**O que falta:**
Um splitter que divida o texto gerado pela LLM por marcadores de pontuação (`. ! ? …`) e envie cada fragmento como um job separado com `scheduled_at` escalonado (ex: +2s, +5s, +9s). O campo `scheduled_at` na tabela `jobs` já existe e já é respeitado pelo worker — só precisa ser preenchido com os offsets corretos.

**Onde implementar:**
- `backend-executors/app/runners/whatsapp.py` — após a geração do texto, antes do envio, quebrar em partes e criar múltiplos jobs com delays crescentes.
- Ou: criar uma função `split_by_punctuation(text) -> List[str]` no `backend-crm` e usar `create_job()` com `scheduled_at` para cada fragmento.

**Recomendação:** Implementar no executor, pois é onde o texto final já está disponível e onde o controle de envio acontece. Criar os sub-jobs diretamente com `scheduled_at = now + offset_acumulado`.

---

### 2. Envio de áudio estático

**Verificação da documentação UazAPI (`POST /send/media`) — confirmado via browser:**

A UazAPI V2 unifica todos os tipos de mídia em um único endpoint `POST /send/media` com campo `type`. Os tipos de áudio disponíveis são:

| type | Comportamento no WhatsApp |
|---|---|
| `audio` | Arquivo de áudio comum — aparece como player de MP3/OGG |
| `myaudio` | **Mensagem de voz** (alternativa ao PTT) — aparece como bolha de voz |
| `ptt` | Mensagem de voz Push-to-Talk — aparece como bolha de voz |

**Para "áudio estático que parece gravado na hora"** o tipo correto é `myaudio` ou `ptt` — ambos aparecem como mensagem de voz no WhatsApp. O `myaudio` é a alternativa preferida ao `ptt` segundo a documentação.

**Estado atual do código:**
O cliente `uazapi_client.py` usa endpoints separados (`send/image`, `send/audio`, etc.) que são o padrão da V1. A V2 usa `POST /send/media` com campo `type`. O tipo `"myaudio"` não existe no mapeamento atual — apenas `"audio"` (que envia como arquivo, não como voz). Isso significa que **o envio de áudio como mensagem de voz ainda não está implementado**.

O que não existe:
- Suporte ao tipo `myaudio` no `uazapi_client.py` (necessário migrar para o endpoint `/send/media` da V2 ou adicionar `myaudio` como endpoint separado se a V1 também suportar)
- Campo específico para áudio na base de conhecimento
- Lógica no orchestrator ou playbook para decidir **quando** enviar áudio
- Endpoint de upload de arquivo de áudio pelo usuário

**O que falta:**
1. Atualizar `_MEDIA_TYPE_TO_ENDPOINT` em `uazapi_client.py` para incluir `myaudio` e verificar se aponta para `send/media?type=myaudio` ou `send/myaudio` (depende da versão da API em uso)
2. Um campo na base de conhecimento (tabela `knowledge_items`) para armazenar URLs de áudio com uma categoria/tag (ex: `"audio_introduction"`, `"audio_offer"`)
3. Lógica no orchestrator para incluir esses áudios no `knowledge_media` do ContextBundle
4. Decisão no executor: se o playbook ou AI Profile indicar `send_audio_on_opening: true`, enviar o áudio `myaudio` correspondente antes da mensagem de texto
5. UI no frontend-crm para o usuário fazer upload e vincular o áudio a uma categoria

**Recomendação:** Confirmar versão da UazAPI em uso no projeto antes de implementar (V1 com endpoints separados vs. V2 com `/send/media` unificado). Depois, mapear `myaudio` corretamente e construir a infraestrutura de base de conhecimento para áudio.

---

### 3. API de "digitando" e "gravando áudio"

**Verificação da documentação UazAPI — confirmado via browser:**

**A UazAPI já resolve isso nativamente com o campo `delay`.** Não é necessário implementar endpoints separados de typing/recording indicator.

Da documentação oficial do campo `delay`:
> *"Atraso em milissegundos antes do envio, durante o atraso aparecerá 'Digitando...' ou 'Gravando áudio...'"*

O comportamento é automático:
- Para mensagens de texto: mostra **"Digitando..."** durante o delay
- Para áudio (`audio`, `myaudio`, `ptt`): mostra **"Gravando áudio..."** durante o delay

**Estado atual:**
O campo `delay` não está sendo passado em nenhum envio. Tanto `send_text()` quanto `send_media()` em `uazapi_client.py` não aceitam esse parâmetro. A rota `POST /whatsapp/send` no backend-core também não expõe esse campo.

**O que falta:**
1. Adicionar parâmetro `delay_ms: int = 0` em `send_text()` e `send_media()` em `uazapi_client.py`, incluindo no payload quando maior que zero
2. Expor `delay_ms` na rota `POST /whatsapp/send` e `POST /whatsapp/send-media` no backend-core
3. No executor (`backend-executors/app/runners/whatsapp.py`), calcular o delay antes de enviar:
   - Texto: `delay_ms = min(max(len(text) * 40, 1000), 8000)` (40ms/char, entre 1s e 8s)
   - Áudio (`myaudio`/`ptt`): `delay_ms` fixo entre 2000–5000ms (simula gravação)
4. Passar o `delay_ms` calculado na chamada ao core, que repassa à UazAPI

**Paridade com playground:**
No playground a UazAPI não é chamada. A resposta `PlaygroundChatResponse` pode incluir `humanization_preview: { typing_seconds: float, recording_seconds: float }` para o frontend exibir visualmente a simulação do que aconteceria no WhatsApp real.

**Onde implementar:**
- `backend-core/app/providers/uazapi_client.py` — adicionar `delay_ms` nos métodos existentes
- `backend-core/app/api/whatsapp_send.py` — expor `delay_ms` nos request bodies
- `backend-executors/app/runners/whatsapp.py` — calcular e passar o delay
- `backend-crm/routes/playground.py` — campo adicional na resposta para simulação visual

---

### 4. Tempo de resposta e disponibilidade do agente

**Estado atual:**
Este é o ponto mais importante e há uma **boa notícia**: vários campos já existem no schema do AI Profile em `backend-core/app/models/ai_profile.py`:

| Campo | Descrição | Status |
|---|---|---|
| `timezone` | Timezone do agente | Campo existe, não usado no executor |
| `followup_allowed_hours` | Janela horária para follow-ups (ex: "09:00-18:00") | Campo existe, não validado |
| `availability_schedule` | Agenda de disponibilidade (JSON) | Campo existe, não validado |
| `followup_cadence` | Cadência entre follow-ups (lista de minutos) | **Implementado e funcionando** |

**O que existe e funciona:**
- A tabela `jobs` tem coluna `scheduled_at` que o worker já respeita: jobs só são executados quando `scheduled_at <= CURRENT_TIMESTAMP`. Isso significa que é tecnicamente possível agendar uma resposta para daqui a 15 minutos apenas setando o `scheduled_at` ao criar o job.

**O que falta:**

**4a. Delay de primeira resposta (novo lead):**
Não existe campo no AI Profile para isso. Precisaria adicionar:
- `first_reply_delay_min_seconds: int` (delay mínimo antes de responder o primeiro contato)
- `first_reply_delay_max_seconds: int` (delay máximo — o sistema sortearia entre min e max)

Na criação do job inbound em `inbound_handler.py`, verificar se é a primeira mensagem do lead e aplicar o delay calculado no `scheduled_at` do job.

**4b. Delay dentro da conversa:**
Similar, mas para mensagens subsequentes:
- `reply_delay_min_seconds: int`
- `reply_delay_max_seconds: int`

Aplicado em toda criação de job de resposta, independente de ser primeiro contato.

**4c. Janela de horário (não responder fora do horário):**
Os campos `followup_allowed_hours` e `availability_schedule` já existem mas não são validados. A lógica seria: ao criar o job, se o horário atual estiver fora da janela, calcular o próximo horário dentro da janela e usar como `scheduled_at`.

**4d. Horário comercial vs. 24h vs. personalizado:**
Uma opção mais simples e clara seria substituir `availability_schedule` (string JSON sem parsing) por:
- `availability_mode: "24h" | "business_hours" | "custom"`
- `custom_hours: JSON` (apenas se mode = "custom") — ex: `{"mon": "09:00-18:00", "tue": "09:00-18:00", ...}`

**Onde implementar:**
- `backend-core/app/models/ai_profile.py` — adicionar os novos campos
- `backend-crm/services/whatsapp_inbound/inbound_handler.py` — calcular e aplicar o delay ao criar o job
- `backend-crm/services/jobs_service.py` — função auxiliar `compute_scheduled_at(ai_profile, is_first_message)` que encapsula toda a lógica de timing
- `backend-executors/app/runners/whatsapp.py` — verificar disponibilidade também no momento da execução do job (fallback de segurança)

**Recomendação:** Priorizar 4a e 4b (delay de resposta) pois são o maior impacto na humanização e mais simples de implementar. Os campos novos não quebram o schema atual. A janela de horário (4c/4d) pode vir em seguida.

---

### 5. Paridade playground ↔ WhatsApp real

**Estado atual:**
O playground (`routes/playground.py`) já segue o princípio de paridade para conteúdo (usa o mesmo `enrich_context_bundle()` e o mesmo ContextBundle). Porém, **não simula nenhum comportamento temporal**: não há delays, não há typing, não há quebra de mensagem em partes.

**O que falta:**
A resposta `PlaygroundChatResponse` deve incluir os campos de humanização simulados para que o usuário veja no playground exatamente o que acontecerá no WhatsApp real:
- `simulated_delay_seconds: float` — quanto tempo o agente "esperaria" antes de responder
- `message_parts: List[str]` — como a mensagem seria dividida em partes
- `humanization_preview: { typing_seconds: float, recording_seconds: float }` — tempo de "digitando"/"gravando" que seria exibido

Esses campos não chamam nenhuma API real — apenas expõem a lógica de cálculo para o frontend renderizar visualmente.

**Onde implementar:**
- `backend-crm/routes/playground.py` — adicionar campos na resposta
- `backend-crm/services/humanization.py` (novo arquivo) — funções `compute_reply_delay()`, `split_message_by_punctuation()`, `compute_typing_duration()` que são usadas tanto pelo playground quanto pelo executor real

---

### Resumo das lacunas e ordem de implementação sugerida

| # | Funcionalidade | Complexidade | Impacto | Pré-requisito |
|---|---|---|---|---|
| 1 | Delay de resposta (primeira msg e conversa) | Baixa | Alto | Adicionar campos no AI Profile |
| 2 | Typing indicator antes de enviar | Média | Alto | Verificar endpoint UazAPI |
| 3 | Quebra de mensagem por pontuação | Média | Médio | — |
| 4 | Janela de horário / disponibilidade | Média | Alto | Refatorar `availability_schedule` |
| 5 | Áudio estático com recording indicator | Alta | Médio | Infraestrutura de upload |
| 6 | Paridade playground (preview de humanização) | Baixa | Médio | Depende de 1, 2 e 3 |

A ordem recomendada para a Fase 1: **1 → 2 → 3 → 6**, deixando áudio e janela de horário para uma Fase 2.


----

## Implementações:

Implementação concluída. Aqui está o resumo do que foi feito:

5 arquivos alterados / criados:

Commit hash: 5853a0af90e65f82f3861d4d48295654874ee084

backend-core/app/models/ai_profile.py — 4 novos campos: first_reply_delay_min/max_seconds e reply_delay_min/max_seconds (default 0 = sem delay)
backend-core/app/db.py — migrations idempotentes para os 4 campos via ensure_ai_profile_columns
backend-crm/services/humanization.py — novo módulo com compute_reply_delay() (sorteia entre min/max) e scheduled_at_from_delay() (retorna None se delay = 0)
backend-crm/services/whatsapp_inbound/inbound_handler.py — captura bundle.ai_profile, conta mensagens do lead para detectar primeira mensagem, passa scheduled_at ao create_job() com fallback seguro
backend-crm/routes/playground.py — campo simulated_delay_seconds: int na resposta do playground para paridade visual com o WhatsApp real
O worker já respeitava scheduled_at automaticamente — nenhuma alteração necessária no executor.


## Commit hash : 1fb7fe57f94ef9c3cc6f80baac2a9af230714976
Implementação concluída. Resumo do que foi feito:

5 arquivos de código + 1 doc alterados:

humanization.py — nova função compute_typing_ms(): 40ms/char, mínimo 1s, máximo 8s
uazapi_client.py — delay_ms em send_text() e send_media(); injeta campo "delay" no payload quando > 0
whatsapp_send.py — campo delay_ms: int = 0 nos dois request bodies; repassado ao client
whatsapp.py (executor) — calcula _delay_ms = min(max(len(text) * 40, 1000), 8000) e inclui no payload ao core
playground.py — campo typing_seconds: float na resposta, calculado com compute_typing_ms()
playground-parity.md — documenta a paridade de humanização comportamental
Efeito: a partir de agora, toda mensagem enviada pelo agente real exibirá "Digitando..." no WhatsApp do lead proporcional ao tamanho da mensagem antes de ela chegar.


## Item 3 — Quebra de mensagem por pontuação
commit hash: 97497f4ec367ac4c6859377ba1507ac52d0ff023


Implementação concluída. 3 arquivos alterados:

backend-crm/services/humanization.py — nova função split_by_punctuation(): divide texto em partes por marcadores de sentença (. ! ? …); parágrafos duplos sempre criam quebra; frases curtas (< 15 chars) fundidas com a próxima para evitar bolhas triviais.
backend-executors/app/runners/whatsapp.py — _split_message_body() substituída por _split_message_by_punctuation() (pontuação-first, sem limite de chars); partes extras agora enviadas com time.sleep proporcional ao tamanho + delay_ms na chamada ao core (typing indicator para cada bolha).
backend-crm/routes/playground.py — campo message_parts: List[str] adicionado à PlaygroundChatResponse, populado com split_by_punctuation() para paridade visual.

Efeito: a partir de agora, toda resposta da IA com múltiplas frases chega ao WhatsApp do lead como bolhas separadas, cada uma precedida de "Digitando...", com gap proporcional ao tamanho da frase anterior.

