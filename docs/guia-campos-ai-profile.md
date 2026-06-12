# Guia de Campos — Página AI Profile

> Documento de referência leiga para configuração do perfil de IA.
> Organizado por camada, igual ao layout da tela.
> Colunas: **campo na tela → variável no backend → o que faz na prática**.
>
> Foco: **Agente 3 Híbrido Agendador Passivo** (`hybrid_scheduler`, `agent_mode=agenda`, `response_style=passive`)

---

## Como ler este guia

- **Campo na tela** — nome exibido no formulário
- **Variável** — nome técnico que o backend lê
- **Impacto** — o que acontece se você preencher errado ou deixar em branco
- **Recomendado para Agente 3** — valor sugerido quando há uma escolha clara

---

## Camada 1 — Identidade e Estratégia

> "Quem é o agente, como ele fala e como ele vende."

---

### Nome do agente
| | |
|---|---|
| **Variável** | `name` |
| **O que é** | O nome com que o bot se apresenta ao lead nas mensagens. |
| **Onde é usado** | Injetado no início de toda conversa. Aparece nas variáveis `{nome}` e `{agente}` das mensagens de abertura. |
| **Impacto** | Se vazio, o agente pode se apresentar de forma genérica ou inconsistente. |
| **Recomendado** | Um nome pessoal (ex: "Sofia", "Lucas") reforça o modo `human_agent` e aumenta taxa de resposta. |

---

### Nome da empresa
| | |
|---|---|
| **Variável** | `brand_name` |
| **O que é** | Nome da marca ou do profissional (ex: "Clínica Renovar", "Dr. João Faria"). |
| **Onde é usado** | Injetado no contexto do prompt em toda conversa. Disponível como variável `{empresa}` nos openers. |
| **Impacto** | Deixar vazio faz o agente não saber "a quem representa". Reduz coerência nas respostas. |

---

### Nicho de mercado
| | |
|---|---|
| **Variável** | `niche` |
| **O que é** | Segmento em que o profissional atua (ex: "coaching executivo", "terapia cognitivo-comportamental"). |
| **Onde é usado** | Injetado no prompt mãe e no prompt filho. Guia o tom das perguntas de qualificação. |
| **Impacto** | Sem nicho, o agente fala de forma genérica — perde a linguagem específica do segmento. |

---

### Tipo de agente (template)
| | |
|---|---|
| **Variável** | `template_key` |
| **O que é** | O "modelo base" do agente. Define qual playbook de fluxo será usado. |
| **Valores possíveis** | `sdr_padrao` · `hybrid_scheduler` · `closer_agressivo` |
| **Onde é usado** | Seleciona qual bloco de lógica é ativado no `decision_engine.py`. Para o Agente 3, **deve ser `hybrid_scheduler`**. |
| **Impacto crítico** | Se for `sdr_padrao` com `agent_mode=agenda`, o **estágio de aquecimento (warming stage) não será ativado** — perde a prova social + prévia da sessão. |
| **Recomendado** | `hybrid_scheduler` |

---

### Forma de vender (modo do agente)
| | |
|---|---|
| **Variável** | `agent_mode` |
| **O que é** | Define a estratégia de vendas: o que o agente tenta conquistar e como conduz o lead. |
| **Valores possíveis** | `sdr_scheduler` · `agenda` · `closer` · `direto` · `consultivo` |
| **Onde é usado** | Determina os campos obrigatórios de qualificação, os guardrails de avanço e o tom do prompt filho. |
| **Para o Agente 3** | Deve ser **`agenda`** — foco em qualificar para agendar uma sessão/consulta, não em fechar venda diretamente. |
| **Impacto** | Se for `consultivo`, o agente exige 6 campos de qualificação (mais lento). Se for `closer`, pula a fase de aquecimento. |

---

### Modo de identidade
| | |
|---|---|
| **Variável** | `identity_mode` |
| **O que é** | Como o bot se apresenta ao lead. |
| **Valores** | `human_agent` (se passa por humano) · `virtual_assistant` (assume ser IA) · `user_clone` (imita o próprio profissional) |
| **Onde é usado** | Injetado no prompt como instrução de persona. |
| **Para o Agente 3** | `human_agent` é o mais recomendado — cria proximidade. Se o profissional preferir transparência, use `virtual_assistant`. |

---

### Tom de voz
| | |
|---|---|
| **Variável** | `tone_of_voice` |
| **O que é** | Descrição livre do estilo de comunicação (ex: "pessoal e próximo", "formal e direto"). |
| **Onde é usado** | Injetado diretamente no prompt filho como instrução de tom. |
| **Para o Agente 3** | O tom padrão do hybrid_scheduler já é *"pessoal e próximo, como assistente do próprio profissional — nunca SDR agressivo"*. Reforce isso aqui. |
| **Exemplo** | `"Caloroso, próximo, como uma recepcionista de confiança do Dr. João"` |

---

### Fuso horário
| | |
|---|---|
| **Variável** | `timezone` |
| **O que é** | Fuso horário do profissional/empresa. |
| **Onde é usado** | Usado para interpretar horários de agendamento (ex: "quinta às 14h") e convertê-los para ISO datetime. Também controla o horário permitido de envio de follow-ups. |
| **Impacto** | Errado = agendamentos salvos com hora incorreta + follow-ups enviados fora do horário comercial. |
| **Recomendado** | `America/Sao_Paulo` para Brasil. `Europe/Lisbon` para Portugal. |

---

### Prioridades do atendimento (goals)
| | |
|---|---|
| **Variável** | `goals` |
| **O que é** | Lista de objetivos que o agente deve ter em mente em toda conversa (um por linha). |
| **Onde é usado** | Injetado no prompt mãe como instrução de comportamento geral. |
| **Para o Agente 3** | Ex: `"1. Qualificar disponibilidade em até 3 mensagens" / "2. Gerar confiança antes de propor agendamento" / "3. Nunca mencionar preço antes da sessão"` |

---

### Política de handoff
| | |
|---|---|
| **Variável** | `handoff_policy` |
| **O que é** | O que o sistema faz quando o agente entende que um humano deve assumir. |
| **Valores** | `keep_active_notify` (mantém bot + avisa operador) · `disable_bot` (desliga imediatamente) · `ignore` (sem ação) |
| **Onde é usado** | `lead_category_policy.py` — executado quando o agente emite sinal de handoff. |
| **Para o Agente 3** | `keep_active_notify` é mais seguro — o agente continua respondendo enquanto o operador não assume. |

---

### Mensagem de abertura — Inbound
| | |
|---|---|
| **Variável** | `origin_inbound_opener` |
| **O que é** | Primeira mensagem enviada quando o **lead entra em contato** (ele fala primeiro). |
| **Variáveis disponíveis** | `{nome}` (nome do agente) · `{empresa}` (nome da empresa) |
| **Onde é usado** | `inbound_handler.py` — disparado na primeira interação de um lead novo. |
| **Impacto** | Deixar vazio = o agente usa uma saudação genérica do sistema. |

---

### Mensagem de abertura — Outbound
| | |
|---|---|
| **Variável** | `origin_outbound_opener` |
| **O que é** | Primeira mensagem quando o **bot inicia o contato** (prospecção ativa). |
| **Variáveis disponíveis** | `{nome}` (nome do lead) · `{agente}` (nome do bot) · `{empresa}` |
| **Onde é usado** | Disparado em jobs de outbound (prospecção). |

---

### Social proof para aquecimento
| | |
|---|---|
| **Variável** | `warming_social_proof` |
| **O que é** | Texto de prova social usado na **fase de aquecimento** (exclusiva do Agente 3), logo após a qualificação ser aprovada. |
| **Onde é usado** | `_build_child_prompt_apresentation()` — injetado como `warming_injection` quando `template_key=hybrid_scheduler` e a qualificação acabou de ser completada. |
| **Impacto** | Se vazio, o sistema usa o texto padrão: *"Um profissional com o seu perfil já utilizou essa abordagem e conseguiu resultados expressivos. Posso te contar mais detalhes na nossa conversa."* |
| **Recomendado** | Personalize com dados reais: número de clientes, resultados específicos, depoimentos resumidos. |
| **Exemplo** | `"Mais de 200 executivos já passaram por essa metodologia e reduziram o estresse no trabalho em menos de 60 dias."` |

---

### Preview da sessão/serviço
| | |
|---|---|
| **Variável** | `warming_session_preview` |
| **O que é** | Descrição do que acontece durante a sessão — usada junto com a prova social no aquecimento. |
| **Onde é usado** | Mesmo bloco que `warming_social_proof`. Os dois são combinados em **uma única mensagem fluida** antes da proposta de agendamento. |
| **Impacto** | Se vazio, usa o padrão: *"Na sessão de aproximadamente 1h, vamos mapear sua situação atual, identificar os principais pontos de melhoria e sair com um plano de ação claro para você."* |
| **Recomendado** | Seja específico sobre o formato e o resultado tangível da sessão. |
| **Exemplo** | `"Na nossa sessão de diagnóstico de 45 minutos, vamos mapear seus bloqueios atuais e você sai com um plano prático de 3 ações para a próxima semana."` |

---

### Perfil / Instruções personalizadas
| | |
|---|---|
| **Variável** | `custom_instructions` |
| **O que é** | Texto livre injetado diretamente no prompt — qualquer regra extra que não se encaixa nos outros campos. |
| **Onde é usado** | Adicionado ao final do prompt filho como instrução de override. |
| **Exemplos de uso** | "Nunca mencionar concorrentes" · "Sempre chamar o lead pelo primeiro nome" · "Se o lead mencionar X, direcionar para Y" |
| **Cuidado** | Instruções contraditórias com os guardrails do sistema podem causar comportamento imprevisível. |

---

### Modo de coleta (response_style)
| | |
|---|---|
| **Variável** | `response_style` |
| **O que é** | Como o agente coleta as informações de qualificação. |
| **Valores** | `active` (conduz a conversa — faz perguntas diretas) · `passive` (responde primeiro, coleta no fluxo natural) |
| **Para o Agente 3 Passivo** | **`passive`** — o agente responde as dúvidas do lead e captura os dados de qualificação de forma natural, sem interrogatório. |
| **Impacto** | No modo `passive`, o agente nunca faz perguntas de qualificação proativamente (exceto a pergunta de fechamento de agendamento). Ideal para coaches e terapeutas onde pressionar o lead é contraproducente. |

---

## Camada 2 — Qualificação

> "O que o agente precisa saber antes de propor o agendamento."

---

### Produto / Serviço (offer_description)
| | |
|---|---|
| **Variável** | `offer_description` |
| **O que é** | Descrição do que é oferecido. Pode ser simples: "Sessão de coaching executivo de 1h". |
| **Onde é usado** | Injetado no contexto do prompt filho de qualificação e apresentação. O agente usa isso para responder perguntas do lead sobre "o que é isso". |
| **Impacto** | Sem isso, o agente não sabe descrever o serviço quando o lead perguntar. |

---

### Público-alvo
| | |
|---|---|
| **Variável** | `target_audience` |
| **O que é** | Descrição do cliente ideal. Ex: "Executivos C-level com mais de 5 anos de experiência". |
| **Onde é usado** | Injetado no prompt. Ajuda o agente a avaliar se o lead se encaixa no perfil e a direcionar a linguagem. |

---

### Principal dor
| | |
|---|---|
| **Variável** | `main_pain` |
| **O que é** | O maior problema que o serviço resolve. |
| **Onde é usado** | Injetado no prompt filho de qualificação. O agente usa para criar empatia e conectar a oferta ao problema do lead. |
| **Exemplo** | `"Estresse crônico e dificuldade de delegar que impedem a liderança eficaz"` |

---

### Campos de qualificação
| | |
|---|---|
| **Variável** | `qualification_fields` (array de objetos) |
| **O que é** | Lista dos campos que o agente precisa coletar antes de propor o agendamento. Cada campo tem: chave, label, pergunta ativa, dica passiva e obrigatoriedade. |
| **Para o Agente 3** | Os 4 campos padrão do modo `agenda` são: `availability_window` (disponibilidade), `service_interest` (interesse no serviço), `location_preference` (presencial/online), `decision_role` (decisor). |
| **Obrigatório vs Opcional** | Campos `required` bloqueiam o avanço para a apresentação enquanto não forem coletados. Campos `optional` o agente coleta se aparecer naturalmente. |
| **Modo passivo** | No modo `passive`, o agente **não pergunta proativamente** — apenas captura quando o lead menciona. A exceção é a "pergunta de fechamento" (`closing_question`) do campo `availability_window`. |

---

### Score mínimo de qualificação
| | |
|---|---|
| **Variável** | `qualification_score_threshold` |
| **O que é** | Pontuação mínima no score 4P (Power, Priority, Price, Timing) para o agente avançar para a apresentação. |
| **Padrão** | `6` de `12` pontos possíveis. |
| **Onde é usado** | `qualification_guardrails.py` — bloqueia o avanço se a pontuação for menor que o threshold. |
| **Para o Agente 3** | O score 4P no modo `agenda` avalia principalmente `price_acceptance` (3 pts) e `availability_window` (3 pts). |
| **Impacto** | Score muito alto = agente nunca avança (leads escapam). Score muito baixo = agente avança com leads desqualificados. |

---

### O que fazer com leads de baixo score
| | |
|---|---|
| **Variável** | `nurture_vs_discard_rule` |
| **O que é** | Decisão sobre leads que não atingem o score mínimo. |
| **Valores** | `false` = descartar (mover para arquivado) · `true` = nutrir (manter no funil com follow-up mais suave) |
| **Para o Agente 3** | `true` (nutrir) — coaches e terapeutas muitas vezes têm leads que precisam de mais tempo para se decidir. |

---

### Faixa de investimento (ticket_range)
| | |
|---|---|
| **Variável** | `ticket_range` |
| **O que é** | Faixa de valor do serviço (ex: "R$ 500 a R$ 1.500 por sessão"). |
| **Onde é usado** | Armazenado no `offer_pack`. Usado como contexto quando o agente precisa responder sobre preço. |
| **Para o Agente 3** | No modo `schedule_then_offer`, o preço só é mencionado após a sessão — este campo fica como referência interna. |

---

### Objeção mais comum (main_objection)
| | |
|---|---|
| **Variável** | `main_objection` |
| **O que é** | A objeção que o lead mais levanta (ex: "Não tenho tempo", "Está caro demais"). |
| **Onde é usado** | Injetado no prompt filho de qualificação e follow-up. O agente usa para antecipar e tratar a objeção de forma natural. |

---

## Camada 3 — Pipeline e Comportamento

> "Como o agente reage a situações específicas e como se comporta no tempo."

---

### Cadência de follow-up (thresholds)
| | |
|---|---|
| **Variáveis** | `followup_h1` · `followup_h2` · `followup_h3` |
| **O que é** | Intervalos de tempo (em horas) entre as tentativas de follow-up quando o lead para de responder. |
| **Onde é usado** | `followup_state.py` — agenda os jobs `whatsapp.followup.tick`. |
| **Para o Agente 3** | O Agente 3 tem cadência padrão de 24h + 48h (2 tentativas). Configure `followup_h1=24`, `followup_h2=48`. A 3ª tentativa (`followup_h3`) pode ser usada para reativação mais tardia (ex: 7 dias). |
| **Impacto** | Intervalos muito curtos = risco de ban do número. Muito longos = lead esfria. |

---

### Follow-up avançado
| | |
|---|---|
| **Variáveis** | `followup_max_attempts` · `followup_cadence` · `followup_allowed_hours` · `followup_first_offset` |

| Campo | O que faz |
|---|---|
| **Máx. tentativas** (`followup_max_attempts`) | Quantas vezes o agente tenta o follow-up antes de arquivar o lead. Para o Agente 3: `2`. |
| **Cadência completa** (`followup_cadence`) | Lista de offsets em minutos (ex: `1440,2880` = 24h, 48h). **Override** dos thresholds acima — se preenchido, tem prioridade. |
| **Horário permitido** (`followup_allowed_hours`) | Janela horária para envio (ex: `08:00-20:00`). Protege de enviar mensagem às 2h da manhã. |
| **Primeiro offset** (`followup_first_offset`) | Minutos de silêncio do lead antes da 1ª tentativa ser agendada. |

---

### Limite diário de disparos
| | |
|---|---|
| **Variável** | `daily_limit` |
| **O que é** | Máximo de mensagens enviadas pelo agente por dia. |
| **Onde é usado** | `backend-executors` — worker verifica antes de cada envio. |
| **Recomendado** | 150–300 para uso regular. Não é o limite da Meta/WhatsApp — é uma proteção comportamental adicional. |

---

### Intervalo entre mensagens
| | |
|---|---|
| **Variáveis** | `interval_min` · `interval_max` |
| **O que é** | Delay aleatório (em segundos) entre o processamento e o envio de cada mensagem, simulando digitação humana. |
| **Recomendado** | Min: 3s · Max: 8s. Muito rápido = parece robô. Muito lento = lead perde o interesse. |

---

### Mídia inválida
| | |
|---|---|
| **Variáveis** | `media_fallback` · `media_fallback_msg` |
| **O que é** | O que fazer quando o lead envia áudio, vídeo, figurinha ou reação (o agente não consegue processar). |
| **Valores** | `continuar` (responde e segue o fluxo) · `pausar` (responde e para o bot até operador retomar) · `ignorar` (silêncio) |
| **Para o Agente 3** | `continuar` com mensagem amigável — coaches recebem muito áudio de leads. Não pausar automaticamente. |

---

### Opt-out por palavra-chave
| | |
|---|---|
| **Variáveis** | `opt_out_keywords` · `opt_out_disable` · `opt_out_notify` · `opt_out_confirm` · `opt_out_confirm_msg` |
| **O que é** | Palavras que, quando enviadas pelo lead, fazem o bot parar imediatamente. |
| **Crítico** | **Obrigatório** — sem isso, leads que pedem para parar continuam sendo contactados, risco de ban e multa LGPD. |
| **Padrão sugerido** | `PARAR, STOP, SAIR, CANCELAR, NÃO QUERO` |
| **Ações recomendadas** | Ativar: desabilitar bot, registrar com timestamp, enviar confirmação ao lead. |

---

### Consentimento LGPD
| | |
|---|---|
| **Variáveis** | `lgpd_mode` · `lgpd_msg` |
| **O que é** | Como o sistema registra o consentimento do lead para receber mensagens. |
| **Crítico** | **Obrigatório por lei** no Brasil. |
| **Valores** | `inbound` (consentimento implícito — lead entrou em contato) · `explicit` (envia mensagem pedindo confirmação) · `outbound` (só coleta no outbound) |
| **Para o Agente 3** | `inbound` para leads que entram em contato. `explicit` para leads prospectados. |

---

### Reativação de arquivados
| | |
|---|---|
| **Variáveis** | `reactivation_mode` · `reactivation_msg` |
| **O que é** | O que acontece quando um lead arquivado envia uma mensagem espontaneamente. |
| **Valores** | `reativar-notificar` · `reiniciar` · `retomar` · `notificar-somente` |
| **Para o Agente 3** | `retomar` — retoma do último estágio da qualificação. Coaches frequentemente têm leads que somem e voltam meses depois. |

---

## Camada 5 — Apresentação e Agendamento

> "Como o agente gerencia a sessão depois de qualificar o lead."

---

### Objetivo do agendamento (appointment_mode)
| | |
|---|---|
| **Variável** | `appointment_mode` |
| **O que é** | Define o que acontece na fase de apresentação (após o aquecimento). |
| **Valores** | `exploratory` (sessão de diagnóstico sem compromisso de compra) · `commercial` (fecha pacote antes de agendar) |
| **Para o Agente 3 Passivo** | **`exploratory`** — o objetivo é agendar uma sessão gratuita ou de diagnóstico. A venda acontece dentro da sessão, conduzida pelo profissional. |
| **Impacto** | `commercial` faz o agente falar sobre preços e pacotes antes do agendamento — contraproducente para coaches e terapeutas. |

---

### Lembretes automáticos
| | |
|---|---|
| **Variáveis** | `appointment_reminder_h1` · `appointment_reminder_h2` |
| **O que é** | Mensagens automáticas enviadas ao lead antes da sessão agendada. |
| **Para o Agente 3** | `appointment_reminder_h1=24` (1 dia antes) · `appointment_reminder_h2=2` (2 horas antes). |
| **Impacto** | Reduz no-shows. Enviados pelo WhatsApp conectado ao agente, no fuso da Camada 1. |

---

### Dossiê pré-reunião (briefing)
| | |
|---|---|
| **Variáveis** | `briefing_enabled` · `briefing_channel` · `briefing_lead_time` · `operator_whatsapp` |
| **O que é** | Resumo automático do lead (qualificação, histórico, sinais) enviado ao profissional antes da sessão. |
| **Para o Agente 3** | **Altamente recomendado** para coaches e terapeutas — chegar na sessão sabendo o contexto do lead. |
| **Configuração** | `briefing_enabled=true` · `briefing_channel=whatsapp` · `briefing_lead_time=2` (horas antes) · `operator_whatsapp=+5511...` |

---

### Integração de calendário
| | |
|---|---|
| **Variável** | `calendar_integration` |
| **O que é** | Como o agente verifica disponibilidade e cria eventos. |
| **Valores** | `none` · `google_calendar` · `calendly` |
| **Situação atual** | Integração detalhada em desenvolvimento. Selecionar reserva a configuração para quando estiver disponível. |
| **Para o Agente 3 agora** | `none` — o agente propõe horários em texto e o profissional confirma manualmente. |

---

## Camada 6 — Oferta e Pagamento

> "Materiais de venda enviados na fase de apresentação (menos relevante para Agente 3 passivo)."

> **Nota para o Agente 3:** Com `appointment_mode=exploratory`, a maior parte desta camada não é ativada — o fecho acontece na sessão, não pelo bot. Preencha apenas o que for usar como referência interna.

---

### Preço âncora
| | |
|---|---|
| **Variável** | `offer_anchor_price` |
| **O que é** | Texto do preço exibido na apresentação da oferta (ex: "de R$1.500 por R$997"). |
| **Para o Agente 3** | Deixar vazio se o preço só é discutido na sessão. |

---

### Texto da garantia
| | |
|---|---|
| **Variável** | `offer_guarantee_text` |
| **O que é** | Texto da garantia do serviço, enviado junto com a oferta. |

---

### Mensagem de upsell
| | |
|---|---|
| **Variável** | `offer_upsell_message` |
| **O que é** | Mensagem enviada após o cliente confirmar a compra, oferecendo algo complementar. |

---

### Gateway de pagamento
| | |
|---|---|
| **Variável** | `payment_gateway` |
| **O que é** | Plataforma onde o link de pagamento será gerado (Hotmart, Kiwify, Stripe, link genérico). |
| **Para o Agente 3** | Preencher apenas se usar checkout online. Muitos coaches recebem presencialmente. |

---

## Camada 4 — Base de Conhecimento

> Seção separada — não é um formulário de campos, mas um editor de documentos.

---

### Categorias de conhecimento
| | |
|---|---|
| **O que é** | Documentos que o agente consulta para responder perguntas específicas do lead. |
| **Onde é usado** | `backend-crm/routes/knowledge.py` — base de conhecimento recuperada pelo agente quando a pergunta do lead corresponde a uma categoria. |
| **Para o Agente 3** | Preencha no mínimo: **Sobre o profissional/empresa**, **Como funciona a sessão**, **Perguntas frequentes**, **Política de cancelamento**. |
| **Impacto** | Seções críticas vazias = o agente inventa respostas ou desvia o lead para o operador desnecessariamente. |

---

## Resumo para o Agente 3 Híbrido Agendador Passivo

Configuração mínima para funcionar corretamente:

| Campo | Valor obrigatório |
|---|---|
| `template_key` | `hybrid_scheduler` |
| `agent_mode` | `agenda` |
| `response_style` | `passive` |
| `appointment_mode` | `exploratory` |
| `identity_mode` | `human_agent` (recomendado) |
| `timezone` | fuso correto do profissional |
| `opt_out_keywords` | configurado (PARAR, STOP, etc.) |
| `lgpd_mode` | configurado |
| `reactivation_mode` | configurado |
| `qualification_fields` | mínimo: `availability_window` obrigatório |
| `warming_social_proof` | personalizado (ou aceitar o padrão) |
| `warming_session_preview` | personalizado (ou aceitar o padrão) |
| `briefing_enabled` | `true` + `operator_whatsapp` preenchido |

