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

**Estado atual:**
A UazAPI suporta envio de áudio via `POST /send/audio` com parâmetro `url`. O cliente `uazapi_client.py` já implementa `send_media()` com suporte ao tipo `"audio"`. A rota `POST /whatsapp/send-media` no backend-core também já suporta `media_type="audio"`. Portanto, **a infraestrutura de envio já existe**.

O que não existe:
- Campo específico para áudio na base de conhecimento
- Lógica no orchestrator ou playbook para decidir **quando** enviar áudio
- Tipo de job dedicado para envio de áudio
- Endpoint de upload de arquivo de áudio pelo usuário
- O type `myaudio` mencionado na nota (alternativa ao PTT) — isso seria `"audio"` no nosso mapeamento interno, mas precisa ser verificado se a UazAPI requer parâmetros diferentes para voz vs. arquivo de áudio comum

**O que falta:**
1. Um campo na base de conhecimento (tabela `knowledge_items`) para armazenar URLs de áudio com uma categoria/tag (ex: `"audio_introduction"`, `"audio_offer"`)
2. Lógica no orchestrator para incluir esses áudios no `knowledge_media` do ContextBundle
3. Decisão no executor: se o playbook ou AI Profile indicar `send_audio_on_opening: true`, enviar o áudio correspondente logo após (ou antes de) a mensagem de texto
4. UI no frontend-crm para o usuário fazer upload e vincular o áudio a uma categoria

**Recomendação:** Começar pela infraestrutura de dados (campo na tabela de knowledge e lógica no orchestrator). O envio em si já funciona — só precisa de contexto para saber quando usar.

---

### 3. API de "digitando" e "gravando áudio"

**Estado atual:**
**Nenhuma implementação existe.** O `uazapi_client.py` só tem `send_text()` e `send_media()`. Não há método para enviar typing indicator ou recording indicator. A UazAPI provavelmente disponibiliza esses endpoints (ex: `POST /presence/typing` ou similar — verificar documentação).

**O que falta:**
1. Verificar na documentação UazAPI o endpoint exato e parâmetros para typing/recording indicator
2. Implementar `send_typing_indicator(instance_id, number, duration_ms)` em `uazapi_client.py`
3. Implementar `send_recording_indicator(instance_id, number, duration_ms)` em `uazapi_client.py`
4. Adicionar chamada no `backend-core/app/api/whatsapp_send.py`, antes de chamar `send_text()` ou `send_media()`, para:
   - Enviar typing por N segundos (proporcional ao tamanho do texto)
   - Enviar recording quando for enviar áudio

**Paridade com playground:**
No playground não faz sentido chamar a UazAPI. A resposta do playground (`PlaygroundChatResponse`) pode incluir um campo `humanization_preview: { typing_seconds: float, recording_seconds: float }` para o frontend exibir visualmente o comportamento simulado.

**Onde implementar:**
- `backend-core/app/providers/uazapi_client.py` — novos métodos
- `backend-core/app/api/whatsapp_send.py` — chamada antes do envio
- `backend-crm/routes/playground.py` — campo adicional na resposta para simulação visual

**Recomendação:** O typing indicator deve ser proporcional ao comprimento da mensagem (ex: `len(text) * 40ms`, com mínimo 1s e máximo 8s). Para áudio, simular "gravando" por 2–5s antes de enviar.

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
