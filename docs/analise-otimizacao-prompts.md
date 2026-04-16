# Análise Técnica — Otimização dos Prompts dos Agentes de Vendas

> Gerado em: 2026-04-16  
> Base: leitura completa de `backend-executors/app/services/decision_engine.py` e `backend-crm/services/ai_orchestrator/orchestrator.py`

---

## 1. Contexto — O que o vídeo do Billy ensina (resumo objetivo)

O vídeo apresenta uma estrutura de prompt para **agente único** com 4 seções:

| Seção | Função |
|---|---|
| **ROLE** | Identidade e objetivo principal do agente |
| **TASK** | Missão operacional (tom, variação de resposta, uso do nome) |
| **SPECS** | Instruções de atendimento + ferramentas disponíveis |
| **NOTES** | Regras críticas de alta prioridade (começo/fim do prompt) |

A principal descoberta citada: **LLMs priorizam início e fim do prompt**. Regras no meio têm menor peso.

---

## 2. Análise da Arquitetura Real do Sistema

### 2.1 Sua hipótese está CORRETA — e é mais sofisticada do que o vídeo

Você imaginou:

```
LLM Mãe (roteador)
  → Filha Qualification
  → Filha Apresentação
  → Filha Follow-up
  → Filha Closing
```

A arquitetura real em `decision_engine.py` confirma exatamente isso:

| Função | Arquivo (linha) | Papel |
|---|---|---|
| `_build_mother_prompt()` | [decision_engine.py:972](../backend-executors/app/services/decision_engine.py#L972) | Roteador — retorna `route_to` + signals, NUNCA gera texto para o lead |
| `_build_child_prompt_qualification()` | [decision_engine.py:1247](../backend-executors/app/services/decision_engine.py#L1247) | Coleta campos, 1 pergunta por turno |
| `_build_child_prompt_apresentation()` | [decision_engine.py:1478](../backend-executors/app/services/decision_engine.py#L1478) | Agendamento / apresentação da oferta |
| `_build_child_prompt_follow_up()` | [decision_engine.py:1897](../backend-executors/app/services/decision_engine.py#L1897) | Reengajamento pós-apresentação |
| `_build_child_prompt_closing()` | [decision_engine.py:2140](../backend-executors/app/services/decision_engine.py#L2140) | Fechamento por modo de agente |

Existe também uma função legada `_build_prompt()` ([linha 851](../backend-executors/app/services/decision_engine.py#L851)) — prompt único sem estrutura Mãe/Filha, usado como fallback.

A analogia com o vídeo do Billy:
- **ROLE** do Billy = `PAPEL` + `ESCOPO` de cada Filha
- **TASK** do Billy = `TOM` + `FRAMEWORK` de cada Filha
- **SPECS** do Billy = bloco de proibições + `_build_qualification_fields_block()`
- **NOTES** do Billy = `_ESCAPE_HATCH_BLOCK` + `_build_validation_block()`

Seu sistema já implementa a lógica do vídeo com muito mais rigor, estrutura e separação de responsabilidade.

---

## 3. Verificação de Cada Ponto — Verdade ou Não?

### 3.1 Ponto Forte: Separação de responsabilidade — VERDADEIRO ✅

A Mãe não gera texto. As Filhas não decidem rota. O código confirma:
- Mãe: "Você NÃO gera mensagem para o lead" (linha 1013)
- Filhas: recebem `route_to` da Mãe como contexto obrigatório

Isso é superior ao sistema do Billy (LLM única) porque elimina conflito de instruções.

---

### 3.2 Ponto Forte: Few-shot por fase — PARCIALMENTE VERDADEIRO ⚠️

**O que você disse:** "Apresentação tem 2 exemplos de sales. Qualification tem training_examples."

**O que o código mostra:**

| Fase | Few-shot do Meta-prompter | Training Examples do Playground |
|---|---|---|
| Qualification | `_inject_generated_parts(..., "qualification")` linha 1476 | `_build_training_examples_block(context, "qualification")` linha 1475 |
| Apresentation | `_inject_generated_parts(..., "apresentation")` | `_build_training_examples_block(context, "apresentation")` |
| Follow-up | `_inject_generated_parts(..., "followup")` linha 2137 | `_build_training_examples_block(context, "followup")` linha 2135 |
| **Closing** | **NÃO chamado** ❌ | **NÃO chamado** ❌ (comentário linha 2233: *"Fase closing não tem few_shot_closing"*) |

**Conclusão:** Follow-up JÁ tem training examples (ao contrário do que você pensou). O gap real é apenas na Closing.

---

### 3.3 Ponto de Melhoria: System prompt das Filhas é genérico — PARCIALMENTE VERDADEIRO ⚠️

**O que você disse:** "Os system prompts são apenas 'Você é a FILHA X e deve responder SOMENTE JSON'."

**O que o código mostra:** As Filhas têm mais contexto do que você imaginou:

```python
# Qualification (linha 1411)
"Você é a FILHA QUALIFICATION de um CRM de vendas WhatsApp.\n\n"
"PAPEL: Coletar campos de qualificação do lead, um por vez..."
"TOM: {tone_of_voice} — conversacional e adaptado ao WhatsApp"
"FRAMEWORK: Modo {agent_mode_normalized}. Template {template_key}."
```

**Mas você tem razão em um aspecto crítico:** o `PAPEL` é **genérico para todos os agentes**. A Qualification diz "coletar campos" independentemente de ser um SDR de alto ticket ou um Closer de baixo ticket. Não há diferenciação de objetivo comercial por `agent_mode` no início do prompt.

**Verificado no código:**
- `agent_mode_normalized` aparece na linha `FRAMEWORK:` — mas apenas como dado, não como instrução diferenciada
- A Closing tem: `"Modo consultivo: handoff para humano. Agenda: confirmar horário+pagamento. Direto: conduzir pagamento."` — isso é bom, mas está no `ESCOPO`, não em um `PAPEL` especializado por agente

**Sua sugestão é válida e implementável.**

---

### 3.4 Ponto de Melhoria: custom_instructions sem posicionamento estratégico — VERDADEIRO ✅ (e pior do que você pensou)

**O que você disse:** "custom_instructions é injetado no meio do prompt."

**O que o código mostra:**

| Fase | custom_instructions injetado? | Posição |
|---|---|---|
| Qualification | ✅ Sim | Final — linha 1475 (correto) |
| Apresentation | Precisa verificar | — |
| Follow-up | ❌ **NÃO injetado** | — |
| Closing | ❌ **NÃO injetado** | — |

`_build_custom_instructions_block()` ([linha 225](../backend-executors/app/services/decision_engine.py#L225)) é chamada apenas na Qualification. **Follow-up e Closing ignoram completamente as `custom_instructions` do operador.** Isso é um bug de cobertura, não apenas de posicionamento.

---

### 3.5 Ponto de Melhoria: Tom de voz — ausência de variação — VERDADEIRO ✅

**O que você disse:** "Falta instrução para variar a forma de responder."

**O que o código mostra:** `_build_tone_block()` ([linha 349](../backend-executors/app/services/decision_engine.py#L349)) tem:
```
- Abertura: nunca comece com 'Olá, tudo bem?' genérico se já houve conversa anterior.
- Encerramento: sempre feche com UMA pergunta ou UM próximo passo claro.
```

Mas **não tem instrução explícita de variação de padrão de abertura**. O bloco proíbe comportamentos específicos mas não instrui o modelo a variar ativamente. Sua sugestão é cirúrgica e correta.

---

## 4. O que NÃO está documentado nas suas considerações (descobertas adicionais)

### 4.1 Closing não recebe custom_instructions nem training_examples

A fase de fechamento — a mais valiosa comercialmente — é a mais "crua" em termos de personalização. Ela recebe apenas:
- `_build_tone_block()` 
- `_ESCAPE_HATCH_BLOCK`
- `_build_validation_block()`

Nenhuma instrução do operador (`custom_instructions`) e nenhum exemplo de treino.

### 4.2 O meta-prompter (`_inject_generated_parts`) não é chamado em Closing

O meta-prompter gera few-shots por nicho, regras de tom do nicho e reformulações de objeção (formato LAER). Closing não recebe nenhum desses enriquecimentos.

### 4.3 Follow-up já tem training_examples — mas custom_instructions está ausente

Se o operador define uma instrução como "nunca mencione preço no follow-up, apenas reagende", essa instrução não chega à Filha Follow-up.

### 4.4 O _build_child_prompt() (fallback) não diferencia por agent_mode

Quando o sistema cai no fallback (sem roteamento Mãe), a `_build_prompt()` gera um prompt único genérico sem `_build_tone_block()`, sem `_build_training_examples_block()`, sem `_build_custom_instructions_block()`. É o pior caminho.

---

## 5. Viabilidade das Otimizações Sugeridas

| Sugestão | Viável? | Esforço | Impacto |
|---|---|---|---|
| Adicionar objetivo comercial por agent_mode no PAPEL das Filhas | ✅ Sim | Baixo (editar strings) | Alto |
| Mover custom_instructions para o final | ✅ Já está no final em Qualification | — | — |
| Adicionar custom_instructions em Follow-up e Closing | ✅ Sim | Baixo | Alto |
| Adicionar training_examples em Closing | ✅ Sim | Médio (criar tabela + UI) | Alto |
| Instrução de variação de abertura no tone_block | ✅ Sim | Baixo | Médio |
| Few-shot por agent_type (SDR / Closer / Híbrido) | ✅ Sim | Médio | Alto |

---

## 6. Enriquecimento das Ideias — Melhorias Adicionais

### 6.1 PAPEL diferenciado por agent_mode (ampliação da sua sugestão 1)

Em vez de apenas adicionar o objetivo comercial, criar um bloco de identidade completo por modo:

```python
def _build_agent_role_block(agent_mode: str, template_key: str, phase: str) -> str:
    roles = {
        "consultivo": {
            "qualification": "Você é um SDR consultivo de alto ticket. Seu papel é qualificar profundamente — cada pergunta deve extrair informação estratégica. Nunca force a venda.",
            "apresentation": "Você é um especialista em agendamento B2B. Seu objetivo é confirmar data e horário para uma sessão de diagnóstico. Foco em gerar confiança antes de vender.",
            "follow-up": "Você é o responsável pelo sucesso pós-reunião. Nutra o relacionamento, remova objeções com empatia e prepare o caminho para o fechamento humano.",
            "closing": "Você prepara o handoff para o especialista humano. Sinalize o interesse do lead, contextualize a conversa e sugira o próximo passo para o time de vendas.",
        },
        "agenda": {
            "qualification": "Você é um SDR focado em agendamento. Qualifique com agilidade — 3-4 campos essenciais — e avance rapidamente para propor a agenda.",
            "apresentation": "Você é um agendador de alta conversão. Confirme horário, envie link e garanta presença. Cada mensagem deve ter um próximo passo claro.",
            "follow-up": "Você reengaja leads que não compareceram ou precisam remencar. Abordagem direta, amigável. Ofereça 2-3 horários concretos.",
            "closing": "Você confirma a sessão e coleta dados operacionais. Horário confirmado, forma de pagamento, link enviado.",
        },
        "direto": {
            "qualification": "Você é um qualificador para venda direta. Valide intenção e capacidade de compra rapidamente. Se houver sinal de compra — avance.",
            "apresentation": "Você apresenta a oferta e conduz ao fechamento. Mostre valor, trate objeção, envie link de checkout. Direto ao ponto.",
            "follow-up": "Você recupera vendas não concluídas. Cart recovery — mensagem curta, benefício claro, CTA direto.",
            "closing": "Você conduz o pagamento. Confirmação, link de checkout, CTA final. Sem enrolação.",
        },
    }
    ...
```

### 6.2 Instrução de variação de abertura no tone_block (ampliação da sua sugestão 4)

Adicionar ao `_build_tone_block()`:

```python
"- Variação de abertura: NUNCA comece 2 mensagens consecutivas com a mesma palavra ou estrutura. "
"Consulte o histórico antes de formular a abertura. "
"Exemplos de padrões válidos: retomar algo que o lead disse ('Você mencionou que...'), "
"contextualizar o momento da conversa ('Como combinamos...'), "
"ou uma abertura baseada no campo recém-coletado. "
"Proibido repetir estruturas como 'Ótimo!', 'Perfeito!', 'Que bom!' em turnos consecutivos.\n"
```

### 6.3 Few-shot de Closing por agent_mode (nova sugestão)

O Closing é a fase mais crítica e a única sem exemplos. Sugestão de estrutura de dados para o playground:

```python
phases = ["qualification", "apresentation", "followup", "closing"]  # adicionar "closing"
```

E criar no UI do Playground uma aba "Closing" com exemplos de:
- Tratamento de última objeção antes do pagamento
- Envio correto do link de checkout
- Handoff para humano com contexto

### 6.4 Sinal de repetição de pergunta detectado em histórico (nova sugestão)

O sistema já tem `asked_questions_for_current_field` na Qualification. Mas nas demais fases, o modelo pode repetir perguntas inconscientemente. Adicionar ao tone_block de Follow-up e Closing:

```python
"- Anti-repetição: antes de fazer qualquer pergunta, verifique no history se a mesma pergunta já foi feita. "
"Se a resposta do lead para aquela pergunta já consta no histórico, não repita.\n"
```

### 6.5 custom_instructions como bloco "NOTES" ao final (nova sugestão)

Renomear e reposicionar o bloco para ser explicitamente o último elemento do prompt:

```python
def _build_operator_notes_block(ai_profile: Dict[str, Any]) -> str:
    """Instrução do operador — posicionada no final do prompt para máxima prioridade (princípio início/fim)."""
    ci = (ai_profile.get("custom_instructions") or "").strip()
    if not ci:
        return ""
    return (
        "\n\n---\n"
        "NOTAS DO OPERADOR (última instrução — prioridade absoluta):\n"
        f"{ci}\n"
        "---\n"
    )
```

---

## 7. Plano de Ação para Implementação

As otimizações estão ordenadas por **impacto × facilidade**. Cada tarefa é independente e pode ser feita em sprint separada.

---

### Sprint 1 — Cobertura Rápida (baixo esforço, alto impacto)

#### Tarefa 1.1 — Injetar custom_instructions em Follow-up e Closing

**Arquivo:** [decision_engine.py](../backend-executors/app/services/decision_engine.py)

- **Follow-up:** adicionar `{_build_custom_instructions_block(ai_profile)}` no final de `_followup_prompt` (linha ~2135), antes do `return`
- **Closing:** adicionar `{_build_custom_instructions_block(ai_profile)}` no final de `_closing_prompt` (linha ~2232), antes do `return`

**Impacto direto:** o operador que configurou "nunca mencione preço no follow-up" ou "sempre assine como Dr. X no closing" passa a ter essa instrução respeitada.

---

#### Tarefa 1.2 — Adicionar instrução de variação de abertura ao tone_block

**Arquivo:** [decision_engine.py:349](../backend-executors/app/services/decision_engine.py#L349) — `_build_tone_block()`

Adicionar após a linha `"- Abertura: nunca comece com..."`:

```python
"- Variação obrigatória: nunca inicie 2 mensagens consecutivas com a mesma palavra ou expressão. "
"Consulte o history para garantir variedade. Proibido repetir 'Ótimo!', 'Perfeito!', 'Claro!' consecutivamente.\n"
```

**Impacto direto:** elimina o padrão robótico mais perceptível pelos leads.

---

#### Tarefa 1.3 — Adicionar training_examples em Closing

**Arquivo:** [decision_engine.py:2232](../backend-executors/app/services/decision_engine.py#L2232)

- Adicionar `_build_training_examples_block(context, "closing")` ao final de `_closing_prompt`
- Adicionar `"closing"` à lista de fases em `_load_training_examples()` no orchestrator ([linha 403](../backend-crm/services/ai_orchestrator/orchestrator.py#L403))

**No frontend:**
- Adicionar opção `closing` no seletor de fase do Playground para que o operador possa classificar exemplos dessa fase

---

### Sprint 2 — Personalização por Agent Mode (médio esforço, alto impacto)

#### Tarefa 2.1 — Criar _build_agent_role_block() por modo e fase

**Arquivo:** [decision_engine.py](../backend-executors/app/services/decision_engine.py)

Criar nova função que retorna um parágrafo de identidade e objetivo comercial com base em `agent_mode_normalized` e `phase`. Injetar no início de cada `_build_child_prompt_*()`, logo após a primeira linha ("Você é a FILHA X...").

**Estrutura sugerida:**

```
IDENTIDADE COMERCIAL:
[texto diferenciado por modo e fase — ver seção 6.1 deste documento]
```

Prioridade de implementação:
1. `closing` — maior impacto comercial, atualmente sem diferenciação
2. `qualification` — segundo maior impacto (primeiro contato)
3. `follow-up` — importante para reengajamento
4. `apresentation` — já tem warming_injection diferenciado por template

---

#### Tarefa 2.2 — Few-shot por agent_type no playground

**Arquivo:** [orchestrator.py:403](../backend-crm/services/ai_orchestrator/orchestrator.py#L403)

A query já filtra por `agent_mode` quando disponível (linha 415-417). O gap é que o operador não consegue classificar exemplos por `agent_mode` na UI.

**No frontend do Playground:**
- Adicionar campo `agent_mode` no formulário de classificação de exemplo
- Exibir filtro por agent_mode na aba de treinamento

---

### Sprint 3 — Refinamento do tone_block por fase (baixo esforço, médio impacto)

#### Tarefa 3.1 — Diretivas de anti-repetição em Follow-up e Closing

Nas fases de reengajamento, a repetição é mais óbvia porque o lead já conhece o bot. Adicionar ao `_build_tone_block()` ou criar `_build_followup_tone_extensions()`:

```python
"- Contexto do histórico: abra fazendo referência a algo concreto da última troca "
"(ex.: 'Como conversamos na semana passada...', 'Você mencionou que...', 'Desde a nossa última conversa...').\n"
"- Nunca abra o follow-up como se fosse o primeiro contato.\n"
```

---

#### Tarefa 3.2 — Instrução de comprimento adaptativo por modo

Atualmente o `max_chars` é fixo por `agent_mode`. Mas a instrução de comprimento é a mesma para todos os contextos. Adicionar ao `_build_tone_block()`:

```python
if agent_mode == "direto":
    "- Comprimento: mensagens curtas e diretas. Se a resposta cabe em 1 frase, use 1 frase. "
    "Não expanda para preencher o limite de caracteres.\n"
elif agent_mode == "consultivo":
    "- Comprimento: pode usar até {max_chars} chars quando o lead faz uma pergunta complexa. "
    "Para perguntas simples, responda de forma objetiva mesmo abaixo do limite.\n"
```

---

### Sprint 4 — Observabilidade de Qualidade de Prompt (médio esforço, longo prazo)

#### Tarefa 4.1 — Log de qual função de prompt foi usada por decisão

**Arquivo:** [decision_engine.py](../backend-executors/app/services/decision_engine.py)

Adicionar ao log de decisão (`log_ai_decision` equivalente no executor) qual `_build_child_prompt_*()` foi chamado e qual `agent_mode` foi resolvido. Isso permite correlacionar qualidade da resposta com a versão do prompt.

---

#### Tarefa 4.2 — A/B testing de system prompt por agent_mode

Com o log da Tarefa 4.1, é possível criar uma flag feature no AI Profile (`prompt_variant: "v1" | "v2"`) e comparar KPIs (taxa de qualificação completa, taxa de agendamento, taxa de fechamento) entre variantes de prompt.

---

## 8. Resumo de Verdades e Falsos

| Afirmação | Veredito | Detalhe |
|---|---|---|
| "Fluxo é Mãe + 4 Filhas" | ✅ Verdade | Confirmado no código |
| "Mãe não gera texto" | ✅ Verdade | Linha 1013 confirma |
| "Few-shot só na Qualification e Apresentação" | ⚠️ Parcialmente verdade | Follow-up JÁ tem. Closing não tem. |
| "custom_instructions está no meio do prompt" | ⚠️ Parcialmente verdade | Está no FINAL da Qualification (correto), mas AUSENTE em Follow-up e Closing |
| "_ESCAPE_HATCH_BLOCK e _build_validation_block no final" | ✅ Verdade | Todas as Filhas têm esses blocos no final |
| "7 proibições explícitas na Qualification" | ✅ Verdade | 7 PROIBIÇÕES numeradas, linha 1446 |
| "Filhas não diferenciam por agent_type no PAPEL" | ✅ Verdade | PAPEL é genérico; diferenciação aparece apenas em ESCOPO/regras |
| "tom_block não instrui variação de abertura" | ✅ Verdade | Falta essa instrução específica |

---

## 9. Prioridade de Implementação (matriz impacto × esforço)

```
ALTO IMPACTO
    │
    │  T1.1 (custom em FU/Closing) ●────────── T2.1 (role por mode)
    │                               │
    │  T1.3 (training Closing) ●   T3.1 (anti-repetição FU)
    │                               │
    │  T1.2 (variação abertura) ●  T2.2 (few-shot por agent_type)
    │                               │
    │                              T4.1 (observabilidade)
    │
LOW ─────────────────────────────────────────────────── HIGH
 ESFORÇO                                              ESFORÇO
```

**Começar por:** T1.1 → T1.2 → T1.3 → T2.1 → T2.2

---

*Este documento deve ser revisado após cada sprint para atualizar o que foi implementado.*
