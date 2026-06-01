# AI Profile — Instruções por Fase (Personalização de Negócio)

> **Status: PLANEADO — não iniciado**
> Separado de `pipeline-configurable-fields.md` por ser um domínio próprio.
> Foco: campos de texto livre que permitem ao operador injectar o contexto do seu negócio em fases específicas do agente, sem afectar as outras.

---

## Princípio

O agente define a **estrutura** (fases, guardrails, fluxo de decisão). O operador define o **conteúdo** (o que é específico do seu negócio). Um coach de vida e um gestor de imóveis podem usar o mesmo Agent 1 — o fluxo é idêntico, mas o que dizem, como abordam objeções, e como conduzem reuniões é completamente diferente.

`custom_instructions` existe para cobrir isto, mas é global — injectado em TODOS os prompts de TODAS as fases. O que está em falta são instruções por fase, que só chegam ao LLM quando este está naquela fase específica.

**Padrão de implementação:** todos os campos abaixo são `String (nullable)` no AI Profile. Quando preenchidos, são injectados no prompt da Filha correspondente, depois das instruções da variante hardcoded e antes do `custom_instructions` global. Sem JSON, sem estrutura — texto livre.

---

## Prioridade Alta

> Resolve gaps onde `custom_instructions` global é claramente insuficiente por precisar de ser fase-específico. Impacto directo na qualidade das mensagens dos agentes.

---

### 1. `followup_sdr_instructions` *(Agent 1 — sdr_scheduler)*

**O problema:** a instrução hardcoded do follow-up do Agent 1 é genérica para qualquer negócio:
> *"Follow-up consultivo pós-reunião; reforçar valor, síntese do contexto e próximo passo comercial."*

O LLM já recebe `outcome` (hot/warm/cold), `followup_goal` (advance_closing/nurture/reschedule) e `attempts` como contexto dinâmico. O que falta é a instrução de negócio específica do operador para complementar esse contexto.

**O que o operador pode precisar expressar:**
> "Nunca menciones preço no follow-up — o fechamento de valor é papel do humano. Quando o lead estiver morno, referencia sempre o caso de sucesso do cliente X. Se for lead frio, pergunta directamente o que está a travar, sem enrolar."

**Onde injectar:** prompt `_build_child_followup_prompt()` em `decision_engine.py`, na variante `sdr_scheduler`.

**Arquivos afectados:**
- `backend-core/app/models/ai_profile.py` — novo campo
- `backend-core/app/db.py` — migration idempotente
- `backend-crm/services/ai_orchestrator/orchestrator.py` — incluir no ContextBundle
- `backend-executors/app/services/decision_engine.py` — injectar no prompt de follow-up
- `frontend-crm/src/pages/AiProfile.tsx` — textarea na secção de Follow-Up do Agent 1

---

### 2. `followup_recovery_instructions` *(Agent 2 — cart_recovery)*

**O problema:** a estratégia de cart recovery tem 3 tentativas com instruções fixas (lembrete neutro → benefício + objeção → urgência). O operador não consegue personalizar o conteúdo para o seu nicho.

O LLM já recebe `attempts` (1, 2 ou 3) como contexto — o operador pode escrever instruções condicionais por tentativa em texto livre se quiser, ou instruções gerais que se aplicam a todas.

**O que o operador pode precisar expressar:**
> "Na 1ª mensagem menciona sempre que o link expira em 48h. Na 2ª, inclui o depoimento do cliente Y. Na 3ª, oferece o bónus extra X como incentivo final — nunca baixa o preço."

**Onde injectar:** prompt de follow-up quando `followup_variant = "cart_recovery"` em `decision_engine.py`.

**Arquivos afectados:** mesmos que `followup_sdr_instructions`.

---

### 3. `followup_postsession_instructions` *(Agent 3 — hybrid_scheduler)*

**O problema:** o follow-up pós-sessão do Agent 3 tem instruções fixas por outcome (`interested_not_closed`, `reschedule_needed`, `converted`). O LLM já recebe o `outcome` capturado no modal — o que falta é contexto de negócio específico do operador.

**O que o operador pode precisar expressar:**
> "Quando o lead está interessado mas não fechou, menciona sempre que a próxima turma começa no dia 15 e que as vagas são limitadas. Quando precisa remarcar, oferece apenas 2ª ou 4ª de tarde — esses são os meus horários disponíveis."

**Onde injectar:** prompt quando `followup_variant = "hybrid_scheduler"` ou `"hybrid_scheduler_followup"`.

**Arquivos afectados:** mesmos que `followup_sdr_instructions`.

---

### 4. `presentation_instructions` *(Agent 1 e Agent 3)*

**O problema:** o prompt da Filha de apresentação instrui o bot a propor e confirmar horários, mas não sabe nada sobre como o operador quer que as reuniões sejam propostas.

**O que o operador pode precisar expressar:**
> "Oferece sempre duas opções de horário, nunca uma só. Usa a palavra 'conversa' em vez de 'reunião'. A call é via Google Meet — envia o link só após confirmação. Menciona que dura 30 minutos."

**Onde injectar:** prompt `_build_child_prompt_apresentation()` em `decision_engine.py`, para agentes com `presentation_variant = "scheduler"`.

**Arquivos afectados:**
- `backend-core/app/models/ai_profile.py` — novo campo
- `backend-crm/services/ai_orchestrator/orchestrator.py` — incluir no ContextBundle
- `backend-executors/app/services/decision_engine.py` — injectar no prompt de apresentação
- `frontend-crm/src/pages/AiProfile.tsx` — textarea na secção de Apresentação

---

### 5. `objection_handling_instructions` *(todos os agentes)*

**O problema:** o campo `objection_common` existe no AI Profile mas **não está a ser injectado nos prompts**. Além disso, só lista a objeção — não instrui como responder.

**O que o operador pode precisar expressar:**
> "Quando mencionarem o preço cedo demais, redireciona para o valor e pede para continuar. Nunca ofereças desconto automaticamente — isso é papel do humano. A objeção mais comum é 'preciso pensar' — responde com urgência leve e um próximo passo concreto."

**Onde injectar:** todos os prompts das Filhas (qualificação, apresentação, follow-up, closing). Pode aproveitar e activar o `objection_common` existente como parte do contexto.

**Arquivos afectados:**
- `backend-executors/app/services/decision_engine.py` — injectar em todos os `_build_child_prompt_*`
- `frontend-crm/src/pages/AiProfile.tsx` — textarea (o campo `objection_common` já existe na UI?)

---

## Prioridade Média

> Melhoram a experiência mas `custom_instructions` cobre parcialmente. Implementar após os campos de alta prioridade.

---

### 6. `disqualification_response` *(todos os agentes)*

**O problema:** quando o lead não atinge o `qualification_score_threshold`, o bot tecnicamente para de avançar — mas não tem instrução sobre o que dizer. O campo `nurture_vs_discard_rule` decide o destino mas não configura a mensagem.

**O que o operador pode precisar expressar:**
> "Quando o lead não se qualifica, agradece o tempo, oferece o e-book gratuito X e encerra com leveza. Nunca deixes a conversa morrer sem uma saída digna."

**Onde injectar:** prompt de qualificação quando `missing_fields` foi esgotado mas o score é insuficiente.

---

### 7. `closing_transition_instructions` *(Agent 1, Agent 2, Agent 3)*

**O problema:** há uma janela onde o bot ainda está activo ao entrar em closing (antes de se desligar para Agent 1 e Agent 3). Não existe instrução configurável para o que dizer nesse momento.

**O que o operador pode precisar expressar:**
> "Quando confirmares o agendamento, diz sempre para verificar o email com o convite do calendário e para trazer o documento X para a sessão. Para Agent 2: ao fechar a venda, diz que o acesso chega em até 24h no email."

**Onde injectar:** prompt `_build_child_prompt_closing()`.

---

## Prioridade Baixa

> Mais niche. `custom_instructions` cobre razoavelmente. Avaliar com base em feedback de utilizadores.

---

### 8. `qualification_opening_instructions` *(todos os agentes)*

**O problema:** além do `qual_opener` do Fluxo de Venda (bloco específico para a primeira mensagem), não existe campo para instruir como conduzir o processo de qualificação.

**O que o operador pode precisar expressar:**
> "Antes de qualquer pergunta, cria rapport mencionando o problema comum do nicho. Nunca perguntes orçamento na primeira mensagem — cria confiança primeiro."

**Nota:** coberto parcialmente pelo `qual_opener` do `sales_flow` e pelo `custom_instructions`. Avaliar impacto real antes de implementar.

---

### 9. `pitch_instructions` *(Agent 2)*

**O problema:** o Agent 2 apresenta a oferta directamente mas não tem instrução específica de abordagem de pitch. O `offer_pack` já cobre `anchor_price` e `guarantee_text` como elementos de conteúdo, mas não a estratégia de apresentação.

**O que o operador pode precisar expressar:**
> "Lidera sempre com a transformação, não com as funcionalidades. Menciona a garantia apenas se o lead mostrar resistência — não logo de entrada. Nunca compara com concorrentes."

**Nota:** coberto parcialmente pelo `custom_instructions` global e pelos elementos do `offer_pack`. Avaliar se a separação por fase acrescenta valor suficiente.

---

## Tabela resumo

| Campo | Fase | Agentes | Prioridade |
|---|---|---|---|
| `followup_sdr_instructions` | Follow-up | Agent 1 | 🔴 Alta |
| `followup_recovery_instructions` | Follow-up | Agent 2 | 🔴 Alta |
| `followup_postsession_instructions` | Follow-up | Agent 3 | 🔴 Alta |
| `presentation_instructions` | Apresentação | Agent 1, Agent 3 | 🔴 Alta |
| `objection_handling_instructions` | Todas | Todos | 🔴 Alta |
| `disqualification_response` | Qualificação | Todos | 🟡 Média |
| `closing_transition_instructions` | Closing | Todos | 🟡 Média |
| `qualification_opening_instructions` | Qualificação | Todos | 🟢 Baixa |
| `pitch_instructions` | Apresentação | Agent 2 | 🟢 Baixa |
