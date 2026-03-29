# Otimização de Prompts — Especificação de Implementação

> **Data:** 29 de março de 2026  
> **Destinatário:** Claude Code / Equipe de desenvolvimento  
> **Arquivos afetados:** `backend-executors/app/services/decision_engine.py`, `backend-executors/app/services/field_extractor.py`, `backend-crm/automations/assistente_ia/llm.py`, `backend-core/app/db.py`, `backend-core/app/api/ai_profiles.py`, `backend-crm/routes/executor.py`  
> **Contexto:** O sistema serve multi-nichos (fisioterapia, coaching, SaaS B2B, e-commerce, etc.). Nenhum exemplo ou cenário deve ser fixo para um nicho específico. As partes personalizáveis dos prompts devem ser geradas dinamicamente por uma LLM meta-prompter com base nos dados do `ai_profile`.

---

## Índice de Tarefas

| Fase | Tarefa | Prioridade | Esforço |
|---|---|---|---|
| 1 | Reestruturar system prompts com 5 camadas | Alta | Baixo |
| 1 | Adicionar regras de recusa a todas as filhas | Alta | Baixo |
| 1 | Adicionar directivas de uso ao knowledge injetado | Alta | Baixo |
| 2 | Bloco de tom WhatsApp operacional | Média | Baixo |
| 2 | Enriquecer contexto do field extractor | Média | Baixo |
| 2 | Escape hatch para alucinações | Média | Baixo |
| 3 | Tabela de prioridade de sinais na Mãe | Média | Médio |
| 3 | Chain-of-thought implícito na Mãe | Baixa | Baixo |
| 3 | Validação semântica de output no prompt | Baixa | Baixo |
| 4 | Meta-prompter — backend (LLM + armazenamento) | Alta | Médio |
| 4 | Meta-prompter — injeção no decision_engine | Alta | Médio |
| 4 | Meta-prompter — cenários dinâmicos de outreach | Baixa | Médio |

---

## FASE 1 — Quick Wins (prompts estáticos)

Estas tarefas alteram apenas o texto dos prompts em `decision_engine.py`. Não requerem mudanças de schema, banco de dados ou frontend.

---

### Tarefa 1.1 — Reestruturar System Prompts com 5 Camadas

**Arquivo:** `decision_engine.py` — todas as funções `_build_*`

**Estado atual:** Os system prompts são frases de uma linha:
```
"Você é um roteador MÃE de um CRM (WhatsApp). Retorne SOMENTE JSON válido."
"Você é a FILHA QUALIFICATION e deve responder SOMENTE JSON válido."
```

**O que fazer:** Expandir cada system prompt para incluir 5 camadas: Persona, Escopo, Tom, Framework, Recusas. O conteúdo de cada camada é injetado com variáveis dinâmicas que já existem no contexto.

**Template de system prompt para CADA Filha:**

```
Você é a FILHA {NOME_DA_FASE} de um CRM de vendas WhatsApp.

PAPEL: {descrição do papel específico desta filha}
ESCOPO: {o que esta filha pode fazer — e o que NÃO pode}
TOM: {tone_of_voice} — conversacional, adaptado ao WhatsApp. Máx {max_chars} caracteres.
FRAMEWORK: Modo {agent_mode}. Template {template_key}.
RECUSAS: Nunca invente informação. Nunca cite preços fora de offer_pack. Nunca prometa condições inexistentes.

Retorne SOMENTE JSON válido no schema ChildResult.
```

**Exemplo concreto — Filha Qualification:**
```
Você é a FILHA QUALIFICATION de um CRM de vendas WhatsApp.

PAPEL: Coletar campos de qualificação do lead, um por vez, através de perguntas naturais e contextuais.
ESCOPO: Você APENAS faz perguntas de qualificação. Não agenda reuniões. Não faz pitch. Não apresenta ofertas.
TOM: {tone_of_voice} — conversacional e adaptado ao WhatsApp (mensagens curtas, sem formatação).
FRAMEWORK: Modo {agent_mode}. Campos obrigatórios: {required_fields}. Campo atual: {current_field}.
RECUSAS: Nunca invente informação. Nunca cite preços. Nunca agende reunião nesta fase. Se não souber responder, redirecione ao tema da qualificação.

Retorne SOMENTE JSON válido no schema ChildResult.
```

**Exemplo concreto — Filha Apresentação:**
```
Você é a FILHA APRESENTATION de um CRM de vendas WhatsApp.

PAPEL: Conduzir a fase de apresentação — agendamento (scheduler) ou oferta+fechamento (sales).
ESCOPO: Variant {presentation_variant}. Gera a mensagem de apresentação e preenche signals_structured.
TOM: {tone_of_voice} — direto e focado na ação. Máx {max_chars} caracteres.
FRAMEWORK: Modo {agent_mode}. Template {template_key}. Appointment mode: {appointment_mode}.
RECUSAS: Nunca invente features ou benefícios fora de knowledge_items. Nunca cite preço diferente de offer_pack. Nunca mencione "veja a imagem/vídeo" (mídia enviada automaticamente). Nunca envie link E peça permissão no mesmo turno.

Retorne SOMENTE JSON válido no schema ChildResult.
```

**Exemplo concreto — Filha Follow-up:**
```
Você é a FILHA FOLLOW-UP de um CRM de vendas WhatsApp.

PAPEL: Re-engajar o lead pós-apresentação. Variante: {followup_variant}.
ESCOPO: Nutrir, tratar objeções, reagendar. Nunca reabrir campos de qualificação antigos em ticks automáticos.
TOM: {tone_of_voice} — empático e orientado a ação. Máx {max_chars} caracteres.
FRAMEWORK: Tentativa {next_attempt}/{max_attempts}. Outcome: {outcome}. Tick automático: {is_followup_tick}.
RECUSAS: Nunca invente informação. Nunca use urgência artificial sem urgency_offer. Nunca reabra qualificação em follow-up tick.

Retorne SOMENTE JSON válido no schema ChildResult.
```

**Exemplo concreto — Filha Closing:**
```
Você é a FILHA CLOSING de um CRM de vendas WhatsApp.

PAPEL: Finalizar o fechamento conforme o modo do agente.
ESCOPO: Modo {agent_mode}. Consultivo: handoff para humano. Agenda: confirmar horário+pagamento. Direto: conduzir pagamento.
TOM: {tone_of_voice} — confiante e claro. Máx {max_chars} caracteres.
FRAMEWORK: Campos verificados: {required_fields}. Missing: {missing_fields}.
RECUSAS: Nunca feche sozinho em modo consultivo (handoff obrigatório). Nunca emita outcome/kanban_highlight fora da categoria closing.

Retorne SOMENTE JSON válido no schema ChildResult.
```

**Exemplo concreto — LLM Mãe:**
```
Você é o ROTEADOR MÃE de um CRM de vendas WhatsApp.

PAPEL: Decidir para qual fase do funil rotear o lead. Você NÃO gera mensagem para o lead.
ESCOPO: Retornar route_to + sinais + confidence. Nunca gerar message_text.
FRAMEWORK: Modo {agent_mode}. Template {template_key}. Missing fields: {missing_fields}.
RECUSAS: Nunca retorne route_to="follow-up" sem evidência textual de apresentação realizada. agent_mode DEVE ser null (vem do sistema).

Retorne SOMENTE JSON válido no schema MotherDecision.
```

---

### Tarefa 1.2 — Adicionar Regras de Recusa a Todas as Filhas

**Arquivo:** `decision_engine.py` — todas as funções `_build_child_prompt_*`

**O que fazer:** Adicionar o seguinte bloco no corpo (user prompt) de TODAS as filhas, logo após as regras de comportamento existentes:

```
PROIBIÇÕES (violar qualquer uma é crítico):
1. NUNCA invente informações que não estejam no contexto fornecido.
2. NUNCA prometa descontos, prazos ou condições não presentes em offer_pack ou knowledge_items.
3. NUNCA dê conselhos médicos, jurídicos ou financeiros.
4. NUNCA mencione concorrentes pelo nome, a menos que estejam em knowledge_items.
5. NUNCA use urgência artificial — só mencione urgência se urgency_offer estiver preenchido.
6. NUNCA responda sobre assuntos fora do nicho do negócio — redirecione para o tema.
7. Se não souber a resposta, diga que vai verificar com a equipa (→ handoff), não improvise.
```

**Adicionais por filha:**

Para `_build_child_prompt_apresentation` (modo `sales`):
```
8. NUNCA mencione "veja a imagem" ou "veja o vídeo" — a mídia é enviada automaticamente pelo sistema.
9. NUNCA envie link de checkout E peça permissão no mesmo turno.
10. NUNCA cite preço diferente do que está em offer_pack.
```

Para `_build_child_prompt_follow_up` (modo `cart_recovery`):
```
8. NUNCA reabra campos de qualificação em ticks automáticos.
9. NUNCA exceda {max_chars} caracteres nas mensagens de recovery.
```

---

### Tarefa 1.3 — Adicionar Directivas de Uso ao Knowledge Injetado

**Arquivo:** `decision_engine.py` — funções que injetam `knowledge_items` no prompt (principalmente `_build_child_prompt_apresentation` e `_build_child_prompt_follow_up`)

**Estado atual:** Os knowledge_items são injetados como blocos de texto crus sem instrução de uso.

**O que fazer:** Envolver cada bloco de knowledge com uma directiva de contexto. Alterar a forma como os knowledge_items são formatados no prompt:

```python
# ANTES (atual):
prompt += f"PROVA SOCIAL: {social_proof}\n"
prompt += f"OBJEÇÕES: {objections_faq}\n"
prompt += f"FAQ: {service_faq}\n"

# DEPOIS (com directivas):
if social_proof:
    prompt += (
        f"PROVA SOCIAL (usar na fase de warming ou quando o lead demonstrar hesitação):\n"
        f"{social_proof}\n"
        f"INSTRUÇÃO: Integre naturalmente na conversa. Nunca diga 'temos uma prova social'. "
        f"Adapte ao perfil do lead se possível.\n\n"
    )

if objections_faq:
    prompt += (
        f"OBJEÇÕES E RESPOSTAS (usar APENAS quando o lead levantar uma objeção):\n"
        f"{objections_faq}\n"
        f"INSTRUÇÃO: Se o lead levantar uma objeção listada, use a resposta configurada como base. "
        f"Adapte ao tom de voz e ao contexto. Nunca copie literalmente. "
        f"Se o lead levantar uma objeção NÃO listada, use empatia + reformulação de valor.\n\n"
    )

if service_faq:
    prompt += (
        f"FAQ DO SERVIÇO (usar APENAS quando o lead fizer uma pergunta diretamente coberta):\n"
        f"{service_faq}\n"
        f"INSTRUÇÃO: Responda com base no FAQ. Se a pergunta não estiver coberta, "
        f"diga que vai confirmar com a equipa.\n\n"
    )
```

Aplicar o mesmo padrão a todos os knowledge_items injetados: `company_profile`, `pitch_script`, `product_details`, `guarantee_policy`, `urgency_offer`, `service_pricing_table`, `commercial_objections`, `service_differentials`, `active_promotion`, `payment_policy`, `pre_commitment_faq`, etc.

**Regra geral:** Cada bloco de knowledge deve ter (1) o nome do bloco, (2) a condição de quando usar, (3) o conteúdo, (4) a instrução de como usar.

---

## FASE 2 — Melhorias de Qualidade (prompts estáticos)

---

### Tarefa 2.1 — Bloco de Tom WhatsApp Operacional

**Arquivo:** `decision_engine.py` — todas as funções `_build_child_prompt_*`

**O que fazer:** Adicionar o seguinte bloco no corpo de todas as filhas, logo após as regras de tom existentes. Substituir a injeção genérica de `tone_of_voice`:

```python
tone_block = (
    f"TOM DE VOZ — REGRAS WHATSAPP:\n"
    f"- Tom configurado: {tone_of_voice}\n"
    f"- Comprimento máximo: {max_chars} caracteres\n"
    f"- Formato: 1 parágrafo curto ou 2–3 linhas. Sem bullet points. Sem formatação markdown.\n"
    f"- Linguagem: conversacional, como se escrevesse a um colega. Sem jargão corporativo.\n"
    f"- Abertura: nunca comece com 'Olá, tudo bem?' genérico se já houve conversa anterior. "
    f"Use o contexto: referir algo que o lead disse antes, ou o campo recém-coletado.\n"
    f"- Encerramento: sempre feche com UMA pergunta ou UM próximo passo claro. Nunca dois.\n"
    f"- PROIBIDO: emojis excessivos (máx 1 por mensagem), CAPS LOCK, exclamações consecutivas (!!), "
    f"linguagem de vendas agressiva ('IMPERDÍVEL', 'CORRA', 'NÃO PERCA').\n"
)
```

Para o template `hybrid_scheduler`, acrescentar:
```python
if template_key == "hybrid_scheduler":
    tone_block += (
        f"- Persona: fale como se fosse o assistente pessoal do {brand_name}, não como vendedor.\n"
        f"- Referência ao profissional: use 'o/a {brand_name}' na terceira pessoa. "
        f"Ex: 'A Dra. Maria tem horário disponível terça e quinta.'\n"
    )
```

---

### Tarefa 2.2 — Enriquecer Contexto do Field Extractor

**Arquivo:** `field_extractor.py` — função `extract_fields_llm`

**Estado atual:** O extractor recebe schema, mensagem e últimas 6 mensagens. Não recebe `current_field`, `filled_fields` nem contexto de nicho.

**O que fazer:** Alterar o prompt do extractor para:

```python
prompt = (
    f"Você é um extractor de campos de qualificação para um CRM de vendas.\n\n"
    f"CAMPO PRIORITÁRIO A EXTRAIR: {current_field}\n"
    f"CAMPOS JÁ PREENCHIDOS (não sobrescrever a menos que haja evidência forte de correção):\n"
    f"{json.dumps(filled_fields, ensure_ascii=False)}\n\n"
    f"NICHO DO NEGÓCIO: {niche}\n"
    f"PÚBLICO-ALVO: {target_audience}\n\n"
    f"Regras:\n"
    f"- Priorize a extração de {current_field}\n"
    f"- Para os demais campos, extraia APENAS se houver evidência CLARA e DIRETA\n"
    f"- confidence < 0.6 = não extrair (retornar null para o campo)\n"
    f"- Nunca infira valores — extraia apenas do texto\n"
    f"- Se o lead disse algo ambíguo, retorne confidence baixa, não invente interpretação\n\n"
    f"Schema: {fields_schema}\n"
    f"Inbound: {inbound_message}\n"
    f"Histórico: {history_text}\n\n"
    f"Retorne SOMENTE JSON válido: "
    f'{{"extracted": {{}}, "confidence": {{}}, "evidence": {{}}}}'
)
```

**Requer:** Passar `current_field`, `filled_fields`, `niche` e `target_audience` para a função. Estes valores já existem no `ContextBundle` — verificar se são passados ao `field_extractor`.

---

### Tarefa 2.3 — Escape Hatch para Alucinações

**Arquivo:** `decision_engine.py` — todas as funções `_build_child_prompt_*`

**O que fazer:** Adicionar o seguinte bloco a todas as filhas, no final das regras:

```
QUANDO NÃO SOUBER RESPONDER:
- Se não tem informação suficiente para responder com confiança → retorne confidence < 0.5
- Em message_text, faça uma pergunta de esclarecimento em vez de inventar
- Se o lead fez uma pergunta técnica fora do knowledge fornecido, use:
  "Vou confirmar essa informação com a equipa e já te respondo."
  E retorne signals_structured.handoff_requested = true
```

---

## FASE 3 — Otimização da LLM Mãe

---

### Tarefa 3.1 — Tabela de Prioridade de Sinais na Mãe

**Arquivo:** `decision_engine.py` — função `_build_mother_prompt`

**O que fazer:** Adicionar o seguinte bloco no prompt da Mãe, ANTES dos exemplos few-shot existentes:

```
REGRAS DE ROUTING — AVALIAR NESTA ORDEM (a primeira que coincidir vence):

PRIORIDADE 1 (obrigatória — sistema sobrescreve mesmo se você retornar outra):
- missing_fields NÃO vazio → route_to = "qualification"

PRIORIDADE 2 (sinais fortes):
- Lead confirmou horário/data específica → route_to = "apresentation"
- Lead disse "quero comprar/assinar/fechar" com intent_level=high → route_to = "closing"
- Lead mencionou reunião/sessão passada + dúvida/objeção/feedback → route_to = "follow-up"

PRIORIDADE 3 (sinais médios — usar confidence para desambiguar):
- Lead mostrou interesse mas sem confirmação → route_to = "apresentation", confidence < 0.7
- Lead pediu "para pensar" sem evidência de apresentação prévia → MANTER rota atual, não avançar

PRIORIDADE 4 (sinais fracos — contexto decide):
- Mensagem genérica ("oi", "tudo bem") → manter rota anterior, confidence baixa
- Mensagem fora de contexto → route_to = rota atual, next_action_hint = "reply"

SE EM DÚVIDA: mantenha a rota atual com confidence < 0.6.
NUNCA retorne route_to="follow-up" se não houver evidência textual de apresentação/sessão realizada.
```

---

### Tarefa 3.2 — Chain-of-Thought Implícito na Mãe

**Arquivo:** `decision_engine.py` — função `_build_mother_prompt`

**O que fazer:** Adicionar logo antes do schema de output:

```
Antes de decidir o route_to, raciocine internamente:
1. O lead tem missing_fields? Se sim → qualification (obrigatório)
2. Há evidência de apresentação/sessão já realizada? Se sim, qual foi o resultado?
3. O lead demonstrou intenção de compra/agendamento? Qual o nível?
4. A mensagem é uma resposta a algo que o bot perguntou, ou é espontânea?

Use o campo "reason" para documentar o raciocínio em 1-2 frases curtas.
```

---

### Tarefa 3.3 — Validação Semântica de Output no Prompt

**Arquivo:** `decision_engine.py` — todas as funções `_build_child_prompt_*`

**O que fazer:** Adicionar no final de cada prompt de filha, antes do fechamento:

```
VALIDAÇÃO — VERIFICAR ANTES DE RETORNAR:
- Se should_ask=true → field DEVE estar preenchido com o current_field
- Se checkout_sent=true → message_text DEVE conter uma URL real (não placeholder)
- Se did_complete_phase=true → recommended_next_category DEVE estar preenchido
- confidence DEVE refletir a certeza real (não usar 0.85 como padrão)
- message_text NÃO deve exceder {max_chars} caracteres
```

---

## FASE 4 — Meta-Prompter (geração dinâmica de blocos de prompt por nicho)

**Contexto importante:** O sistema é multi-nicho. Exemplos few-shot fixos de um nicho (ex: marketing digital) prejudicam a performance quando o agente atende outro nicho (ex: fisioterapia, coaching, SaaS B2B). A solução é uma LLM meta-prompter que gera blocos personalizáveis dos prompts com base nos dados do `ai_profile`.

---

### Tarefa 4.1 — Backend: Serviço Meta-Prompter

**Novo arquivo sugerido:** `backend-executors/app/services/meta_prompter.py` (ou integrar em serviço existente)

**Schema de armazenamento — alterar `AIProfile`:**

```python
# backend-core — modelo AIProfile (adicionar campos)
generated_prompt_parts: Optional[dict] = None     # JSON com blocos gerados
prompt_parts_generated_at: Optional[datetime] = None
prompt_parts_version: int = 0
```

**Migração de banco:** Adicionar coluna `generated_prompt_parts` (JSONB nullable), `prompt_parts_generated_at` (timestamp nullable), `prompt_parts_version` (integer default 0) à tabela `ai_profiles`.

**Função principal:**

```python
async def generate_prompt_parts(ai_profile: dict) -> dict:
    """
    Chama a LLM meta-prompter para gerar blocos personalizáveis do prompt
    com base nos dados do ai_profile.
    
    Retorna dict com chaves:
    - few_shot_qualification: list[dict]
    - few_shot_apresentation: list[dict]
    - few_shot_followup: list[dict]
    - tone_rules: list[str]
    - objection_rewrites: list[dict]  (formato LAER)
    - qualification_phrasing: dict[str, list[str]]
    """
```

**Prompt do meta-prompter:**

```
Você é um META-PROMPTER especializado em criar blocos de prompt para agentes de vendas WhatsApp.

CONTEXTO DO AGENTE:
- Nicho: {niche}
- Público-alvo: {target_audience}
- Tom de voz: {tone_of_voice}
- Oferta: {offer_description}
- Template: {template_key} (define o fluxo: sdr_padrao→qualificar+agendar, closer_agressivo→qualificar+vender, hybrid_scheduler→aquecer+agendar)
- Modo: {agent_mode}
- Objeções configuradas pelo usuário: {objections_faq} (pode estar vazio)
- Campos de qualificação obrigatórios: {required_fields}

SUA TAREFA:
Gerar os seguintes blocos em JSON, personalizados para este nicho específico:

1. "few_shot_qualification": Array de 2-3 exemplos de interação na fase de qualificação.
   Cada exemplo: {scenario: "descrição curta", inbound: "mensagem do lead", expected_output: {question_text: "...", field: "campo", should_ask: true, confidence: 0.xx}}
   REGRAS: As perguntas devem soar naturais para ESTE nicho. Usar o tom configurado.
   Cobrir: 1 lead cooperativo, 1 lead hesitante, 1 lead com resposta ambígua.

2. "few_shot_apresentation": Array de 2 exemplos de interação na fase de apresentação.
   Para template scheduler: exemplos de proposta de agendamento natural.
   Para template sales: exemplos de pitch curto com oferta.
   Para hybrid_scheduler: exemplo com aquecimento + proposta de agendamento.

3. "few_shot_followup": Array de 2 exemplos de reengagement pós-apresentação.
   Para sdr_padrao: follow-up consultivo pós-reunião.
   Para closer_agressivo: cart recovery (mensagem curta, máx 280 chars).
   Para hybrid_scheduler: follow-up pós-sessão com tom pessoal.

4. "tone_rules": Array de 3-5 regras concretas de comunicação para este nicho.
   NÃO use adjetivos vagos. Use instruções operacionais diretas.
   Exemplos bons: "tratar por tu", "evitar jargão X", "referir contexto Y do lead".
   Exemplos ruins: "ser simpático", "tom profissional".

5. "objection_rewrites": Array com as objeções reformuladas no formato LAER.
   Cada item: {objection: "...", real_concern: "o que o lead realmente quer dizer", acknowledge: "validar", explore: "pergunta exploratória", respond: "argumento de valor", next_step: "CTA concreto"}
   Se objections_faq do usuário estiver vazio, gere as 3 objeções mais comuns DESTE nicho.

6. "qualification_phrasing": Objeto com chave = campo de qualificação, valor = array de 2 formas naturais de perguntar este campo NESTE nicho.
   Campos: {required_fields}
   Ex para fisioterapia: {"service_interest": ["O que te traz aqui hoje?", "É uma situação de recuperação ou prevenção?"]}

REGRAS GERAIS:
- Idioma: {language}
- Tom SEMPRE consistente com tone_of_voice configurado
- Mensagens de exemplo com máximo de {max_chars} caracteres
- NUNCA use placeholders genéricos ([nome], [serviço]) — use linguagem natural contextual
- Os exemplos devem parecer conversas WhatsApp reais, não templates de CRM
- Retorne SOMENTE JSON válido, sem texto adicional
```

**Triggers de execução:**

| Momento | Ação |
|---|---|
| Onboarding finalizado (wizard completo) | Gerar todos os blocos |
| Edição de `niche`, `target_audience`, `tone_of_voice` ou `offer_description` | Regenerar todos os blocos |
| Edição de `objections_faq` no knowledge base | Regenerar apenas `objection_rewrites` |
| Botão manual no frontend | Regenerar todos os blocos |

**Fallback:** Se `generated_prompt_parts` for `null` ou vazio, os prompts funcionam normalmente sem blocos dinâmicos (comportamento atual).

**Modelo:** Usar o mesmo modelo configurado em `settings.llm_model` (ou um modelo mais leve se disponível). Não precisa ser o modelo mais potente — gera texto estruturado, não raciocina em tempo real.

---

### Tarefa 4.2 — Injeção dos Blocos Gerados no Decision Engine

**Arquivo:** `decision_engine.py` — todas as funções `_build_child_prompt_*`

**Pré-requisito:** O `ContextBundle` montado em `executor.py` já inclui dados do `ai_profile`. Garantir que `generated_prompt_parts` seja incluído no bundle passado ao `decision_engine`.

**Arquivo:** `backend-crm/routes/executor.py` — onde monta o `ContextBundle`:
```python
# Adicionar ao contexto enviado ao decision_engine:
context["generated_prompt_parts"] = ai_profile.get("generated_prompt_parts", {})
```

**Padrão de injeção (aplicar a cada `_build_child_prompt_*`):**

```python
def _inject_generated_parts(prompt: str, context: dict, phase: str) -> str:
    """Injeta blocos gerados pelo meta-prompter no prompt da filha."""
    parts = context.get("generated_prompt_parts") or {}
    
    # Few-shot examples
    few_shot_key = f"few_shot_{phase}"  # qualification, apresentation, followup
    examples = parts.get(few_shot_key)
    if examples:
        prompt += "\n\nEXEMPLOS DE REFERÊNCIA PARA ESTE NICHO (adapte ao contexto atual, não copie):\n"
        for ex in examples:
            prompt += f"\nCenário: {ex.get('scenario', '')}\n"
            prompt += f"Lead: \"{ex.get('inbound', '')}\"\n"
            prompt += f"Resposta esperada: {json.dumps(ex.get('expected_output', {}), ensure_ascii=False)}\n"
    
    # Tone rules
    tone_rules = parts.get("tone_rules")
    if tone_rules:
        prompt += "\n\nREGRAS DE TOM PARA ESTE NICHO:\n"
        for rule in tone_rules:
            prompt += f"- {rule}\n"
    
    # Qualification phrasing (apenas para filha qualification)
    if phase == "qualification":
        phrasing = parts.get("qualification_phrasing", {})
        current_field = context.get("current_field")
        if current_field and current_field in phrasing:
            prompt += f"\n\nFORMAS NATURAIS DE PERGUNTAR '{current_field}' NESTE NICHO:\n"
            for p in phrasing[current_field]:
                prompt += f"- {p}\n"
    
    # Objection rewrites (para apresentation e follow-up)
    if phase in ("apresentation", "followup"):
        rewrites = parts.get("objection_rewrites")
        if rewrites:
            prompt += "\n\nOBJEÇÕES REFORMULADAS (formato LAER — usar quando o lead levantar objeção):\n"
            for obj in rewrites:
                prompt += (
                    f"\nObjeção: \"{obj.get('objection', '')}\"\n"
                    f"  Causa real: {obj.get('real_concern', '')}\n"
                    f"  Reconhecer: {obj.get('acknowledge', '')}\n"
                    f"  Explorar: {obj.get('explore', '')}\n"
                    f"  Responder: {obj.get('respond', '')}\n"
                    f"  Próximo passo: {obj.get('next_step', '')}\n"
                )
    
    return prompt
```

**Usar em cada filha:**
```python
def _build_child_prompt_qualification(context, message_text, mother_decision):
    prompt = "..."  # prompt base existente com melhorias das fases 1-3
    prompt = _inject_generated_parts(prompt, context, "qualification")
    return prompt

def _build_child_prompt_apresentation(context, message_text, mother_decision):
    prompt = "..."  # prompt base existente
    prompt = _inject_generated_parts(prompt, context, "apresentation")
    return prompt

def _build_child_prompt_follow_up(context, message_text, mother_decision):
    prompt = "..."  # prompt base existente
    prompt = _inject_generated_parts(prompt, context, "followup")
    return prompt
```

---

### Tarefa 4.3 — Cenários Dinâmicos de Outreach (llm.py)

**Arquivo:** `backend-crm/automations/assistente_ia/llm.py`

**Estado atual:** O outreach usa 3 cenários fixos baseados em análise de website (`no_site`, `weak_site`, `decent_site`), desenhados para agências de marketing.

**O que fazer:** Adicionar ao meta-prompter a geração de `outreach_scenarios` e usá-los no `llm.py` em vez dos cenários fixos:

Adicionar ao prompt do meta-prompter (tarefa 4.1):
```
7. "outreach_scenarios": Array de 2-3 cenários de prospecção específicos para este nicho.
   Cada cenário: {scenario_key: "identificador", description: "quando usar", email_angle: "ângulo do e-mail", whatsapp_angle: "ângulo do WhatsApp", cta: "call-to-action sugerido"}
   Os cenários devem refletir situações reais de prospecção NESTE nicho, não cenários genéricos de website.
```

No `llm.py`, alterar a lógica de seleção de cenário:
```python
# ANTES:
scenario = compute_scenario(lead)  # no_site, weak_site, decent_site

# DEPOIS:
prompt_parts = ai_profile.get("generated_prompt_parts", {})
outreach_scenarios = prompt_parts.get("outreach_scenarios")
if outreach_scenarios:
    # Usar cenários dinâmicos do nicho
    scenario_context = format_outreach_scenarios(outreach_scenarios)
else:
    # Fallback para cenários fixos existentes
    scenario = compute_scenario(lead)
    scenario_context = format_legacy_scenario(scenario)
```

**Nota:** Os cenários fixos existentes permanecem como fallback. Não remover — apenas adicionar a nova lógica por cima.

---

## Notas Finais para Implementação

1. **Ordem de execução:** Fases 1→2→3 podem ser implementadas sequencialmente sem dependências. Fase 4 depende de migração de banco (novo campo em ai_profiles) mas não depende das fases anteriores.

2. **Retrocompatibilidade:** Todas as mudanças são aditivas. Se `generated_prompt_parts` for null, o sistema funciona como antes. Se os novos blocos de prompt forem adicionados mas sem meta-prompter, o sistema continua a funcionar — apenas sem os blocos dinâmicos.

3. **Teste:** Para cada fase, testar com pelo menos 2 nichos diferentes (ex: "fisioterapia desportiva" e "consultoria SaaS B2B") para validar que o mesmo prompt base funciona bem em ambos os contextos.

4. **Observabilidade:** O `decision_trace` já existente deve registar `prompt_parts_version` quando os blocos dinâmicos estiverem ativos. Isto permite correlacionar versões do prompt com métricas de performance.
