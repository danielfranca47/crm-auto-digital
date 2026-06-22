# AI Profile como Fonte de Verdade — Campos Configuráveis

> **Status: EM ANDAMENTO**
> Etapas A, G, H concluídas e documentadas em `docs/architecture/agents.md`.
> Etapas D, E, F só concluídas do lado do backend — a UI nunca grava no lugar
> certo, ver correcção de status abaixo. D e E retomadas como M3 em
> `docs/plans/followup-proativo-e-cancelamento-agenda.md`.
> Etapa B obsoleta (supersedida por `qualification_fields`).
> **Etapa C em foco:** instruções de follow-up por agente — próxima implementação.
> Etapa I abortada por ora — sem prioridade.

---

## Princípio

O agente define a **estrutura** — fases, guardrails, fluxo de decisão, cadências. O operador define o **conteúdo** — o que é específico do seu negócio: como abordar leads, o que dizer no follow-up, quais referências usar, o tom para o seu nicho.

Um coach de vida e um gestor de imóveis podem usar o mesmo Agent 1. O fluxo é idêntico — o que muda é o que o bot diz. `custom_instructions` existe para isto, mas é global: injeta a mesma instrução em todos os prompts de todas as fases. O que está em falta são instruções **por fase**, que só chegam ao LLM quando este está naquela fase específica.

Regra para cada campo novo:
1. `String (nullable)` — texto livre, sem JSON, sem estrutura rígida
2. Opcional com fallback para o comportamento hardcoded — não quebra quem não preenche
3. Injectado depois das instruções da variante hardcoded e antes do `custom_instructions` global
4. Visível na UI do AI Profile na secção da fase correspondente

---

## Etapas concluídas

Documentadas em [`docs/architecture/agents.md`](../architecture/agents.md).

| Etapa | Campo(s) | Agentes |
|---|---|---|
| A ✅ | `origin_inbound_opener`, `origin_outbound_opener` | Todos |
| D ⚠️ | `appointment_reminder_offsets` — backend pronto, **UI nunca grava na coluna certa** (ver abaixo) | Agent 1, Agent 3 |
| E ⚠️ | `briefing_enabled`, `briefing_channel`, `briefing_lead_time`, `operator_whatsapp` — backend pronto, **UI nunca grava na coluna certa** | Agent 1, Agent 3 |
| F ⚠️ | `buying_signal_keywords` — backend pronto, **UI nunca grava na coluna certa** | Agent 1 |
| G ✅ | `offer_pack.anchor_price`, `offer_pack.guarantee_text` | Agent 2 |
| H ✅ | `payment_gateway`, `payment_webhook_secret` | Agent 2 |
| B ~~❌~~ | OBSOLETA — supersedida por `qualification_fields` já implementado | — |
| I ~~❌~~ | ABORTADA — domínio de OAuth/calendário sem prioridade actual | — |

> **Correcção de status (achado posterior):** as Etapas D, E e F foram marcadas ✅
> quando só o lado do backend (coluna no modelo, aceite pela API) estava pronto. Uma
> investigação posterior (`docs/marketing/comercial/agente-demo.md`, secção "NOTA
> TÉCNICA") confirmou em código que `frontend-crm/src/services/api.ts` e
> `src/types/agente.ts` leem/escrevem estes campos dentro de `offer_pack`, nunca nas
> colunas de topo que o motor real lê — a UI nunca foi corrigida. A correcção dos
> campos relacionados a follow-up/agenda (`appointment_reminder_offsets`, campos de
> briefing) está registada como M3 em
> `docs/plans/followup-proativo-e-cancelamento-agenda.md`. `buying_signal_keywords`
> fica fora desse escopo (não é follow-up/agenda) — sem plano próprio ainda.

---

## Etapa C — Instruções de Follow-Up por Agente

> **Estado: A IMPLEMENTAR — prioridade actual**

---

### O que é

Três campos de texto livre no AI Profile — um por tipo de agente — que o operador preenche com instruções específicas do seu negócio para a fase de follow-up. O LLM recebe essas instruções combinadas com o contexto dinâmico que já tem (outcome do lead, tentativa actual, objectivo do follow-up) e produz mensagens que soam como o assistente do operador, não como um bot genérico.

---

### Do que se trata — o problema actual

Hoje os três tipos de agente têm instruções de follow-up **hardcoded** nos playbooks. São instruções genéricas pensadas para qualquer negócio:

**Agent 1 (sdr_scheduler):**
> *"Follow-up consultivo pós-reunião; reforçar valor, síntese do contexto e próximo passo comercial."*

**Agent 2 (cart_recovery):**
> Tentativa 1: *"Lembrete neutro — o pedido está reservado."*
> Tentativa 2: *"Reforce o benefício principal e antecipe a objeção mais comum."*
> Tentativa 3: *"Urgência máxima — a oferta expira hoje."*

**Agent 3 (hybrid_scheduler, por outcome):**
> `interested_not_closed`: *"Tom de continuidade. Retome o contexto, remova a objeção e ofereça nova data."*
> `reschedule_needed`: *"Tom leve. Ofereça 2–3 horários e encerre com pergunta fechada."*
> `converted`: *"Tom de boas-vindas. Confirme o próximo passo, envie link de pagamento."*

Estas instruções funcionam como ponto de partida. O problema é que **todos os operadores recebem as mesmas mensagens de follow-up**, independentemente do seu negócio.

Um coach de desenvolvimento pessoal que faz sessões de 1h tem uma abordagem de follow-up completamente diferente de uma agência de marketing digital que fecha contratos mensais. Os leads respondem de formas diferentes. As objeções são diferentes. As referências que criam confiança são diferentes. O momento certo para criar urgência é diferente.

---

### Por que é importante

O follow-up é o momento mais crítico do funil — é onde a maioria dos negócios perde leads que já mostraram interesse. Uma mensagem genérica de follow-up tem taxa de resposta baixa porque não ressoa com o contexto específico do lead e do negócio.

Quando o bot soa como o assistente do operador — referenciando o produto real, o nicho real, as objeções reais, as referências que fazem sentido para aquele público — a probabilidade de reengajamento aumenta. A mensagem chega e parece que foi escrita por alguém que conhece o lead, não por um sistema automático.

`custom_instructions` resolve parte disto, mas como é global, o operador não consegue dizer "no follow-up faz X" sem que isso também afecte a qualificação e a apresentação.

---

### Como funciona agora

```
tick de follow-up → LLM recebe:

  [instrução hardcoded da variante]
    "Follow-up consultivo pós-reunião..."

  [contexto dinâmico do contrato]
    outcome: warm, followup_goal: advance_closing, attempts: 1...

  [custom_instructions do operador — global]
    "Tom directo mas humano. Marca XYZ..."
```

O LLM combina a instrução genérica com o contexto do lead e as instruções globais do operador. O resultado é uma mensagem que segue o fluxo correcto mas não reflecte o negócio específico.

---

### Como vai funcionar depois

```
tick de follow-up → LLM recebe:

  [instrução hardcoded da variante]
    "Follow-up consultivo pós-reunião..."

  [instrução específica do operador para este agente ← NOVO]
    "Nunca menciones preço — isso é papel do humano.
     Quando morno, referencia o caso do João que dobrou..."

  [contexto dinâmico do contrato]
    outcome: warm, followup_goal: advance_closing, attempts: 1...

  [custom_instructions do operador — global]
    "Tom directo mas humano. Marca XYZ..."
```

O LLM usa a instrução do operador como camada de personalização entre a estratégia da plataforma e o contexto dinâmico do lead. O resultado: mensagem que segue o fluxo, usa o contexto real do lead, e soa como o assistente daquele operador específico.

---

### Transformação e impacto

| | Antes | Depois |
|---|---|---|
| Quem define o conteúdo do follow-up | Plataforma (hardcoded) | Operador (texto livre) + Plataforma (estrutura) |
| Personalização por negócio | Nenhuma — todos iguais | Total — cada operador tem a sua voz |
| Curva de aprendizagem | Zero (não há nada para configurar) | Baixa — um campo de texto por agente |
| Risco de quebrar o fluxo | Zero | Zero — campo nullable, fallback para hardcoded |
| Impacto na taxa de resposta | Depende do genérico | Potencialmente significativo — mensagens mais relevantes |

---

### Os três campos

---

#### C1 — `followup_sdr_instructions` *(Agent 1 — sdr_scheduler)*

**Quando é injectado:** prompts `_build_child_followup_prompt()` quando `followup_variant = "sdr_scheduler"`.

**Contexto que o LLM já tem** (e que as instruções do operador complementam):
- `outcome` — como o lead saiu da reunião: `hot`, `warm`, `cold`, `lost`
- `followup_goal` — o que o operador escolheu no modal: `advance_closing`, `nurture`, `reschedule_conversation`
- `attempts` — em que tentativa está (1ª, 2ª ou 3ª)
- `meeting_happened` — se a reunião aconteceu
- `proposal_sent` — se enviou proposta

**Exemplo do que o operador preencheria:**
> "Nunca menciones preço no follow-up — o fechamento de valor é papel do humano. Quando o lead estiver morno, referencia o resultado do cliente João da área de tecnologia. Se frio, pergunta directamente o que está a travar — não enroles. Máx 2 frases por mensagem."

**O que muda na prática:** o bot passa de mensagens consultivas genéricas para mensagens que soam como o assistente daquele profissional específico, com as referências e limitações do seu negócio.

---

#### C2 — `followup_recovery_instructions` *(Agent 2 — cart_recovery)*

**Quando é injectado:** prompts de follow-up quando `followup_variant = "cart_recovery"`.

**Contexto que o LLM já tem:**
- `attempts` — em que tentativa está (1, 2 ou 3)
- `followup_goal` — `cart_recovery`
- `proposal_sent: true` — sabe que o link foi enviado

O operador pode usar o `attempts` como referência nas suas instruções se quiser diferenciar tentativas — o LLM sabe em qual está.

**Exemplo do que o operador preencheria:**
> "Na 1ª mensagem menciona que o link do pedido ainda está disponível e expira em 48h. Na 2ª, referencia que o curso tem garantia de 7 dias e pergunta se há alguma dúvida que esteja a travar. Na 3ª, menciona que só restam 3 vagas da turma de março — sem baixar preço."

**O que muda na prática:** em vez de um lembrete neutro genérico, o operador define exactamente o que cada tentativa de recuperação deve comunicar, usando os activos reais do seu negócio (vagas, garantia, urgência real).

---

#### C3 — `followup_postsession_instructions` *(Agent 3 — hybrid_scheduler)*

**Quando é injectado:** prompts de follow-up quando `followup_variant` é `hybrid_scheduler` ou `hybrid_scheduler_followup`.

**Contexto que o LLM já tem:**
- `outcome` — como terminou a sessão: `interested_not_closed`, `reschedule_needed`, `converted`, `lost`
- `followup_goal` — objectivo escolhido pelo operador no modal
- `meeting_happened` — se a sessão aconteceu
- `attempts` — em que tentativa está

**Exemplo do que o operador preencheria:**
> "Quando interessado mas não fechou: menciona que a próxima turma começa a 15 de Junho e que só abres 4 vagas por mês. Quando precisa remarcar: oferece apenas 3ª ou 5ª de tarde — são os meus horários disponíveis. Quando convertido: diz para verificar o email com o link de acesso e que entras em contacto pessoalmente em 24h."

**O que muda na prática:** o bot deixa de usar instruções genéricas de remarcação e continuidade para usar exactamente os horários, prazos e próximos passos reais do operador.

---

### Implementação técnica

**Padrão uniforme para os três campos:**

| Aspecto | Detalhe |
|---|---|
| Tipo no modelo | `String (nullable)` — sem JSON, sem estrutura |
| Migration | `ensure_column()` idempotente em `backend-core/app/db.py` |
| ContextBundle | Incluir via `enrich_context_bundle()` ou no builder do executor |
| Injecção no prompt | Bloco entre instrução da variante e `custom_instructions` global |
| Fallback | `None` → comportamento hardcoded inalterado |
| UI | Textarea por campo na secção Follow-Up do AI Profile, condicional ao tipo de agente |

**Arquivos afectados:**

| Arquivo | O que muda |
|---|---|
| `backend-core/app/models/ai_profile.py` | 3 novos campos nullable |
| `backend-core/app/db.py` | 3 migrations idempotentes |
| `backend-core/app/api/ai_profiles.py` | Expor em `AIProfileBase` e `AIProfileUpdate` |
| `backend-crm/services/ai_orchestrator/orchestrator.py` | Incluir campos no ContextBundle |
| `backend-executors/app/services/decision_engine.py` | Injectar em `_build_child_followup_prompt()` por variante |
| `frontend-crm/src/pages/AiProfile.tsx` | Textarea por campo, visível consoante o `template_key` |

---

## Tabela de campos

| Campo | Tipo | Status |
|---|---|---|
| `origin_inbound_opener` | String | ✅ Implementado |
| `origin_outbound_opener` | String | ✅ Implementado |
| `qualification_fields` | JSON (list[object]) | ✅ Implementado |
| `appointment_reminder_offsets` | JSON (list[int]) | ✅ Implementado |
| `briefing_enabled` / `briefing_lead_time` / `operator_whatsapp` | Boolean/Int/String | ✅ Implementado |
| `buying_signal_keywords` | JSON (list[str]) | ✅ Implementado |
| `payment_gateway` / `payment_webhook_secret` | String | ✅ Implementado |
| `followup_sdr_instructions` | String | 🔴 A implementar (Agent 1) |
| `followup_recovery_instructions` | String | 🔴 A implementar (Agent 2) |
| `followup_postsession_instructions` | String | 🔴 A implementar (Agent 3) |
| `calendar_integration` | String | ⚫ Abortado por ora |
