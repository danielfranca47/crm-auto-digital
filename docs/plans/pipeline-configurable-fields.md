# AI Profile como Fonte de Verdade — Campos Configuráveis

> **Status: SUBSTANCIALMENTE IMPLEMENTADO**
> Etapa B obsoleta (supersedida por `qualification_fields`). Etapa C parcialmente coberta por mecanismos existentes. Etapa I é um novo domínio de integração.
> **Pendências sujeitas a reavaliação** antes de qualquer implementação.

## Princípio geral

O objetivo é migrar hardcodes de comportamento do bot para campos configuráveis no AI Profile. Cada novo campo deve:
1. Ser opcional com fallback sensato (não quebrar quem não preencher)
2. Ser visível na UI do AI Profile de forma contextual ao tipo de agente
3. Ser injetado no prompt do LLM de forma clara
4. Ter default derivado do `template_key` selecionado

---

## Etapas concluídas

### Etapa A — Contexto inbound/outbound no LLM ✅ *(todos os agentes)*

`lead_origin` no `ContextBundle`. Campos `origin_inbound_opener` e `origin_outbound_opener` no AI Profile.
Leads de Prospecção recebem `origin = "outbound"` forçado.

---

### Etapa D — Lembretes de appointment ✅ *(Agent 1, Agent 3)*

Campo `appointment_reminder_offsets: JSON` no AI Profile (lista de inteiros negativos em minutos).
Ao criar appointment, jobs de lembrete são agendados em `appointments.py` para cada offset.

---

### Etapa E — Dossiê/briefing pré-reunião ✅ *(Agent 1, Agent 3)*

Implementado como: `briefing_enabled`, `briefing_channel`, `briefing_lead_time`, `operator_whatsapp` no AI Profile.
Serviço de briefing disponível. Jobs enfileirados via appointments.

---

### Etapa F — Sinais de compra e alerta ao vendedor ✅ *(Agent 1)*

Campo `buying_signal_keywords: JSON` no AI Profile.
Detecção via `_detect_buying_signals()` em `decision_engine.py`.
Alerta enviado para `operator_whatsapp`.

---

### Etapa G — Campos de mídia no offer_pack ✅ *(Agent 2)*

`anchor_price` e `guarantee_text` consumidos pelo `decision_engine.py`.
Quando presentes, o prompt da Filha inclui preço âncora e garantia na mensagem de apresentação.

---

### Etapa H — Integração de pagamento ✅ *(Agent 2)*

Campos `payment_gateway` e `payment_webhook_secret` no AI Profile.
Rota `POST /webhooks/payment/{gateway}` em `backend-crm/routes/webhooks.py`.
Ao confirmar pagamento: lead movido para `"client-list"`, cart recovery interrompido, boas-vindas enfileiradas.

---

## Avaliação das etapas restantes

---

### Etapa B — Perguntas de qualificação configuráveis ~~❌~~ → OBSOLETA

**O que foi proposto:** campo `qualification_questions: JSON` como lista simples de strings para substituir as perguntas hardcoded nos playbooks.

**Por que está obsoleta:** o sistema já implementou `qualification_fields` — uma estrutura mais poderosa que cobre e excede o que esta etapa propunha.

#### O que existe hoje (`qualification_fields`)

Cada campo tem: `key`, `label`, `question` (pergunta direta), `passive_hint` (captura silenciosa sem perguntar), `qualify_if`, `disqualify_if` (critérios opcionais), `mode`, `group`.

Quando `qualification_fields` está configurado no AI Profile:
- Substitui inteiramente as perguntas hardcoded dos playbooks
- A Filha de Qualification usa a lista de campos pendentes para guiar as perguntas
- `qual_opener` pode ser configurado na fase p1 do Fluxo de Venda para controlar a abertura da qualificação
- `_natural_reaction_block` orienta a LLM a reagir à resposta do lead antes de avançar para a próxima pergunta

O `LeadCardDialog` exibe a secção "Critérios de Qualificação" com os campos capturados, badge de pendentes/completo e edição inline — tudo baseado em `qualification_fields`.

**Conclusão:** não há nada a implementar. Quem quiser perguntas customizadas configura `qualification_fields`.

---

### Etapa C — Estratégia de follow-up configurável ❌ *(Agent 2, Agent 3)*

#### O que mudaria na prática para o utilizador

**Agent 2 — `cart_recovery_strategy`:**
Hoje o bot tem uma estratégia fixa de 3 tentativas: 1ª lembrete neutro → 2ª benefício + objeção → 3ª urgência máxima. Este comportamento está hardcoded em `ai_playbooks/__init__.py` no playbook `closer_agressivo_cart_recovery`.

Com o campo configurável, o operador poderia personalizar a instrução de cada tentativa para o seu negócio:
> "Na 2ª tentativa, menciona que temos 20% de desconto até amanhã. Na 3ª, referencia que o cliente X também hesitou e hoje está satisfeito."

Quem vende produto físico tem uma abordagem de recuperação diferente de quem vende curso online — hoje todos recebem a mesma instrução genérica.

**Agent 3 — `followup_strategy`:**
Hoje quando o operador regista no modal de transição "a sessão aconteceu mas o lead não fechou" (`interested_not_closed`), o bot usa uma instrução fixa: "retome o contexto, remova a objeção e ofereça nova data". Esta instrução está hardcoded em `hybrid_scheduler_followup`.

Com o campo configurável, o operador poderia personalizar por outcome:
> "Quando interested_not_closed: menciona que a próxima turma começa dia 15 e as vagas são limitadas."
> "Quando reschedule_needed: oferece apenas 2ª ou 4ª de tarde, que é quando tenho disponibilidade real."

#### O que já existe e cobre parcialmente esta necessidade

Antes de decidir implementar, vale notar que o sistema já oferece dois mecanismos que fornecem controlo similar:

1. **`custom_instructions`** — campo de texto livre no AI Profile injectado no final de todos os prompts. O operador pode escrever: "Nas mensagens de recuperação de carrinho, menciona sempre a garantia de 7 dias." A limitação é que é global — a mesma instrução chega a todos os prompts, não só ao follow-up.

2. **`training_examples` por fase** — o operador pode carregar exemplos de mensagens de follow-up no AI Profile. A LLM usa esses exemplos como few-shot para calibrar o tom e estilo. Menos específico por tentativa, mas cobre a personalização de voz e abordagem geral.

#### O que a Etapa C ainda acrescentaria que não existe

A especificidade **por tentativa numerada** para cart recovery, e **por outcome específico** para Agent 3. Os mecanismos actuais permitem personalizar o estilo geral — não permitem dizer "na 3ª tentativa do carrinho, seja urgente; nas anteriores, não".

#### Recomendação

Baixa prioridade. Os defaults hardcoded nos playbooks são razoáveis para a maioria dos casos. Implementar quando o feedback de utilizadores indicar que as mensagens de recovery não se adaptam bem ao negócio deles, ou quando existirem múltiplos utilizadores com estratégias de follow-up muito diferentes entre si.

---

### Etapa I — Integração de calendário ⚠️ *(Agent 1, Agent 3)*

**Estado atual:** campo `calendar_integration` existe no AI Profile com valor `"none"`. Nenhuma lógica lê este campo. Appointments locais funcionam como fallback e são o sistema operacional.

#### O que mudaria na prática para o utilizador

Hoje quando o bot agenda uma reunião, cria um `appointment` na base de dados local. O operador vê no CRM, mas **não aparece na agenda do Google Calendar nem no Calendly** do profissional. O operador tem de replicar manualmente.

Com a integração real, ao criar um appointment no CRM, o sistema sincronizaria automaticamente com o calendário do profissional — criando o evento, enviando convite ao lead e mantendo as duas agendas em sincronia.

#### Por que está como stub e não foi implementada

Esta etapa é um domínio novo, não uma extensão do sistema actual. Requer:
- OAuth com Google Calendar ou Calendly (fluxo de autorização, armazenamento de tokens, refresh)
- Tratamento de conflitos de agenda
- Sincronização bidirecional (se o profissional cancela no Google, o CRM deve reflectir)
- UI de configuração da integração no frontend

É mais próxima de um novo produto do que de uma feature incremental. A complexidade é significativamente maior do que as outras etapas deste plano.

#### Recomendação

Implementar como fase independente quando existir procura clara de utilizadores. Não bloqueia nenhuma funcionalidade actual — os appointments locais funcionam de forma autónoma.

---

## Tabela de campos no AI Profile

| Campo | Tipo | Status |
|---|---|---|
| `origin_inbound_opener` | String | ✅ Implementado |
| `origin_outbound_opener` | String | ✅ Implementado |
| `qualification_fields` | JSON (list[object]) | ✅ Implementado — supersede `qualification_questions` proposto |
| `appointment_reminder_offsets` | JSON (list[int]) | ✅ Implementado |
| `briefing_enabled` / `briefing_lead_time` / `operator_whatsapp` | Boolean/Int/String | ✅ Implementado |
| `buying_signal_keywords` | JSON (list[str]) | ✅ Implementado |
| `payment_gateway` / `payment_webhook_secret` | String | ✅ Implementado |
| `cart_recovery_strategy` | JSON | ❌ Baixa prioridade — coberto parcialmente por `custom_instructions` + `training_examples` |
| `followup_strategy` | JSON | ❌ Baixa prioridade — coberto parcialmente por `custom_instructions` + `training_examples` |
| `calendar_integration` | String | ⚠️ Stub — domínio novo, implementação independente |
