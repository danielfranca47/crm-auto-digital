# DIAGNÓSTICO DO SISTEMA — Agentes IA WhatsApp CRM

> Auditoria técnica realizada em 2026-03-21 com base na análise direta do código-fonte em `backend-crm/`.

---

## Resumo Executivo

| Métrica | Valor |
|---|---|
| Total de itens auditados | 23 |
| ✅ Implementados | 7 |
| ⚠️ Parciais | 5 |
| ❌ Não implementados | 11 |
| **Percentual de cobertura** | **41,3%** *(7 completos + 2,5 de 5 parciais × 50%) / 23* |

O sistema tem uma base funcional sólida para o fluxo principal de inbound (receber mensagem → identificar lead → responder via IA → atualizar CRM). O pipeline de follow-up automático também está operacional. No entanto, há lacunas críticas em segurança/conformidade, qualidade de conversa avançada e gestão de reativação de leads.

---

## Resultado por Categoria

---

### Categoria 1 — Gestão de Sessão e Contexto

**1.1 — Detecção automática de lead existente e carregamento de histórico**
✅ IMPLEMENTADO

O sistema normaliza o número para E.164 e consulta a tabela `leads` em `guardrail.py:20-25`. Se encontrado, retorna o `lead_id` existente sem criar duplicata. O histórico das últimas 20 mensagens é carregado automaticamente em `history.py:9-27` e injetado no contexto do LLM antes de qualquer resposta.

---

**1.2 — Retomada do ponto exato em qualificação interrompida**
⚠️ PARCIAL

> **O que falta:** O estado de qualificação (campos coletados, perguntas já feitas, `last_questioned_field`) é persistido na tabela `lead_qualification_state` e recuperado via `qualification_state.py:61-69`. Porém, o motor de decisão em `orchestrator.py` reavalia quais campos estão faltando a partir dos campos mínimos definidos em `qualification_guardrails.py:100`, não necessariamente continuando do último campo perguntado na sequência. Leads que retornam após longo silêncio são tratados sem verificação de janela de tempo — o sistema sempre retoma, sem opção de reiniciar o fluxo.

---

**1.3 — Cálculo de silêncio e disparo automático de follow-up**
✅ IMPLEMENTADO

`followup_state.py:14-52` calcula o próximo `next_followup_at` a cada envio com base no número de tentativas e na variante do agente. `followup_reconciler.py:25-60` detecta leads elegíveis por SQL (`next_followup_at <= CURRENT_TIMESTAMP`) e enfileira jobs automaticamente. Os thresholds são hardcoded: `sdr_scheduler` → 24h, 3d, 7d; `hybrid_scheduler` → 24h, 48h.

---

**1.4 — Detecção de mudança de idioma e adaptação em tempo real**
❌ NÃO IMPLEMENTADO

> **O que falta:** O idioma é resolvido uma única vez a partir do `ai_profile` do usuário em `orchestrator.py:209-210` e nunca reavaliado por mensagem. Não há nenhuma lógica de detecção de idioma inbound. Seria necessário adicionar um passo de detecção no pipeline de inbound (ex.: via LLM ou biblioteca `langdetect`) e sobrescrever o idioma do contexto dinamicamente.

---

**1.5 — Detecção de sinais de alto interesse e elevação de prioridade**
⚠️ PARCIAL

> **O que falta:** As palavras-chave de alto sinal estão definidas em `jobs_service.py:67-75` (`_STRONG_SIGNAL_KEYWORDS`: "quero", "comprar", "agendar", "preço", "contratar", "fechar"), mas **nunca são comparadas contra o texto inbound**. Não há campo de prioridade dinâmica na tabela `leads` nem lógica que eleve a prioridade do lead no CRM ao detectar esses termos.

---

### Categoria 2 — Qualidade da Conversa

**2.1 — Detecção de loop e interrupção de perguntas repetidas**
⚠️ PARCIAL

> **O que falta:** `qualification_state.py:101-124` rastreia tentativas por campo (máximo 3 por campo, 20 no total) via `increment_attempt()` e `merge_asked_questions()`. Porém, não há lógica explícita no orquestrador que, ao verificar que um campo atingiu 3 tentativas, **bloqueie novas perguntas para aquele campo** e mova o fluxo adiante. O limite existe na estrutura de dados mas não é enforced na decisão.

---

**2.2 — Identificação de sinais de frustração e pause automático do bot**
✅ IMPLEMENTADO

Qualquer resposta inbound de um lead em follow-up para o bot automaticamente via `inbound_handler.py:272-278` → `followup_state.py:135-150` (`stop_followup_on_inbound_reply()`). Transições de categoria para `prospect-refused` ou `disqualified` disparam disable do bot via `lead_category_policy.py:165-187`. A detecção é baseada em interação/categoria, não em palavras-chave explícitas de frustração.

---

**2.3 — Limite automático de tamanho de mensagem para o padrão WhatsApp**
✅ IMPLEMENTADO

`orchestrator.py:91-107` (`apply_mode_overrides()`) define `max_chars` por modo: 700 (consultivo), 350 (agenda), 300 (direto). `text_renderer.py:63-75` quebra parágrafos longos em blocos de 2–4 linhas nos limites de pontuação.

---

**2.4 — Quebra automática de resposta longa em múltiplas mensagens com delay**
❌ NÃO IMPLEMENTADO

> **O que falta:** `runners/whatsapp.py:156-161` envia sempre um único corpo de mensagem. Não há lógica de splitting em múltiplas mensagens nem delay simulado de digitação entre elas. Seria necessário implementar um pipeline de multi-send no executor com intervalos proporcionais ao tamanho de cada parte.

---

**2.5 — Tratamento configurável para mensagens inválidas (áudio, vídeo, figurinha)**
❌ NÃO IMPLEMENTADO

> **O que falta:** `webhooks.py:129-136` verifica `message_type != "text"` e retorna `{"status": "ignored"}` silenciosamente. O lead não recebe nenhuma resposta. Não há comportamento configurável (ex.: "Por favor, envie apenas texto."). Seria necessário adicionar lógica de fallback por tipo de mídia, configurável no `ai_profile`.

---

### Categoria 3 — Segurança e Conformidade

**3.1 — Opt-out imediato por palavras-chave com registro no CRM**
⚠️ PARCIAL

> **O que falta:** Não há matching de palavras-chave explícitas ("PARAR", "SAIR", "STOP", "CANCELAR") no pipeline inbound do CRM. O opt-out acontece via transição de categoria (ex.: mover para `prospect-refused`) que desabilita o bot, mas isso exige ação do operador ou que o LLM decida por conta própria. Seria necessário um filtro pré-LLM que detecte essas palavras e acione `bot_disabled=1` + registro de log com timestamp automaticamente.

---

**3.2 — Proteção contra solicitação ou armazenamento de dados sensíveis**
❌ NÃO IMPLEMENTADO

> **O que falta:** Não existe nenhuma camada de sanitização ou validação que impeça o agente de coletar CPF, dados bancários ou senhas. `qualification_state.py` armazena o conteúdo bruto extraído pelo LLM em `data_json` sem nenhum filtro. Seria necessária uma lista de campos proibidos validada antes da persistência e instruções explícitas no system prompt do LLM.

---

**3.3 — Detecção de prompt injection e manutenção do comportamento configurado**
❌ NÃO IMPLEMENTADO

> **O que falta:** O texto do lead é passado diretamente para o contexto do LLM em `orchestrator.py:231` sem nenhum pré-processamento ou sanitização. Não há detecção de padrões como "ignore suas instruções anteriores" ou "você agora é". Seria necessário um filtro de regex/pattern matching pré-LLM que detecte tentativas de injection e responda com fallback seguro sem processar o conteúdo.

---

**3.4 — Registro automático de consentimento com timestamp (LGPD)**
❌ NÃO IMPLEMENTADO

> **O que falta:** Não existe tabela de consentimentos no schema do banco (`database.py`). A criação do lead em `guardrail.py:37-52` registra `origin` mas não registra consentimento explícito com timestamp. Para conformidade com a LGPD, seria necessária uma tabela `lead_consents` com `lead_id`, `user_id`, `consent_type`, `timestamp`, `channel` populada automaticamente no momento da primeira interação inbound.

---

### Categoria 4 — Gestão de Pipeline

**4.1 — Movimentação automática de estágio conforme qualificação avança**
✅ IMPLEMENTADO

`guardrail.py:63-136` (`maybe_promote_lead_on_inbound()`) promove leads de `to-prospect` e `in-progress` para `qualification` automaticamente a cada inbound. `lead_category_policy.py` aplica side-effects (disable bot, pausa follow-up) nas transições de categoria. Transições explícitas (ex.: para `closing`) continuam sendo via PATCH manual.

---

**4.2 — Score de temperatura atualizado a cada resposta recebida**
❌ NÃO IMPLEMENTADO

> **O que falta:** Não existe campo `temperature_score` ou `lead_score` na tabela `leads` (verificado em `database.py`). `qualification_state.py` mantém `confidence_json` por campo individual, mas não existe uma função que aggregate esses valores em um score composto e atualizado a cada mensagem recebida. Seria necessário definir o modelo de scoring e expô-lo como coluna indexável no CRM.

---

**4.3 — Arquivamento automático após limite máximo de tentativas**
✅ IMPLEMENTADO

`followup_state.py:190-244` (`progress_followup_after_auto_send()`) verifica `attempts >= max_attempts` e marca o contrato de follow-up com `status="closed"` e `stop_reason="MAX_ATTEMPTS_REACHED"`. **Observação:** o fechamento do follow-up não altera automaticamente a `category` do lead para `archived` — esta transição fica pendente.

---

**4.4 — Deduplicação de leads do mesmo número por canais diferentes**
⚠️ PARCIAL

> **O que falta:** A deduplicação funciona para inbound WhatsApp: `guardrail.py:20-25` consulta `WHERE user_id = ? AND phone = ?` antes de criar. Porém, leads criados manualmente, via importação de planilha ou via outros canais (email, formulário web) com o mesmo número não passam por essa verificação. Não há dedup cross-canal no momento de criação por outras vias.

---

**4.5 — Reativação automática de lead arquivado que reabre conversa**
❌ NÃO IMPLEMENTADO

> **O que falta:** `guardrail.py:88-99` bloqueia explicitamente a promoção de leads cujo `category` não seja `to-prospect` ou `in-progress`. Leads em `archived`, `disqualified`, `closed` ou `prospect-refused` que enviem uma mensagem têm o inbound ignorado sem qualquer reativação. Seria necessário um fluxo de reativação que, ao detectar inbound de lead arquivado, mova para uma categoria de reengajamento e reinicie um playbook de nutrição adequado.

---

### Categoria 5 — Integrações Técnicas

**5.1 — Sincronização em tempo real entre WhatsApp e CRM**
✅ IMPLEMENTADO

`webhooks.py:64-75` recebe eventos da UazAPI validando `X-Webhook-Secret`. `inbound_handler.py:224-279` processa o evento em transação única: atualiza lead, loga em `prospection_logs`, atualiza `orion_conversations`, para follow-up ativo — tudo em `conn.commit()` atômico. Não requer configuração manual de webhook por parte do usuário.

---

**5.2 — Validação de número WhatsApp ativo antes de campanha outbound**
❌ NÃO IMPLEMENTADO

> **O que falta:** O envio em `runners/whatsapp.py` despacha para qualquer número sem pré-validação. A UazAPI provavelmente oferece um endpoint de checagem de número ativo, mas ele não é utilizado. Seria necessário adicionar uma etapa de validação no job de envio outbound ou no momento de importação de lista de contatos.

---

**5.3 — Rotação de números de envio e proteção contra limites diários**
❌ NÃO IMPLEMENTADO

> **O que falta:** `rate_limit_service.py` controla apenas cotas mensais de plano SaaS (unidades de mensagem), não limites diários por número de WhatsApp. Não existe pool de números remetentes nem lógica de rotação. Se um número for banido ou atingir limite da Meta, todas as mensagens param. Seria necessário um modelo de pool de instâncias UazAPI com balanceamento de carga por número.

---

**5.4 — Geração automática de dossiê do lead antes do handoff para humano**
❌ NÃO IMPLEMENTADO

> **O que falta:** `lead_category_policy.py` desabilita o bot quando o lead entra em `closing`, mas não gera nenhum resumo consolidado. O operador humano recebe a conversa sem contexto estruturado. Seria necessário um serviço que, ao detectar a transição para handoff, consolide: histórico recente, campos de qualificação coletados, score, tentativas de contato e notas em um documento ou mensagem interna enviada ao operador.

---

## Itens Críticos

> Itens ❌ que, se ausentes, comprometem o funcionamento básico em produção:

| Item | Risco imediato |
|---|---|
| **3.1** Opt-out por palavras-chave | Leads enviando "STOP" continuam sendo contatados — risco regulatório e de ban do número |
| **3.3** Prompt injection | Lead pode subverter o comportamento do agente em produção a qualquer momento |
| **3.4** LGPD consent logging | Risco de notificação pela ANPD em caso de auditoria |
| **4.5** Reativação de leads arquivados | Leads que retornam espontaneamente são ignorados — perda direta de oportunidade de venda |
| **2.5** Fallback para mídia inválida | Lead envia áudio, não recebe resposta, experiência quebrada sem diagnóstico |

---

## Próximos Passos Sugeridos

Ordenados por impacto imediato no produto e na conformidade:

**1. Opt-out por palavras-chave (3.1) + LGPD (3.4)**
Filtro pré-LLM detectando "PARAR/STOP/SAIR/CANCELAR" → `bot_disabled=1` + insert em tabela `lead_consents`. Uma sprint curta resolve os dois riscos regulatórios simultaneamente.

**2. Reativação de leads arquivados (4.5)**
Remover o bloqueio em `guardrail.py:92` para categorias específicas e adicionar playbook de reengajamento. Alto impacto de receita — leads que retornam são os mais quentes do pipeline.

**3. Detecção e ação em sinais de alto interesse (1.5)**
Conectar `_STRONG_SIGNAL_KEYWORDS` ao pipeline inbound: ao detectar, elevar `priority` do lead, notificar operador e opcionalmente acelerar o fluxo de qualificação.

**4. Dossiê automático no handoff (5.4)**
Ao mover lead para `closing`, gerar e enviar para o operador um resumo estruturado com qualificação, histórico e score. Reduz tempo de onboarding do vendedor humano e aumenta taxa de fechamento.

**5. Proteção contra prompt injection (3.3)**
Adicionar filtro de regex pré-LLM detectando padrões de injection. Baixo custo de implementação, alto risco se ausente em ambiente de produção com volume de leads.

---

*Gerado automaticamente por auditoria de código — backend-crm @ branch `feature/etapa-8-n8n-orion`*
