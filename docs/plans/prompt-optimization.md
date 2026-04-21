# Otimização de Prompts das LLMs Filhas

## Contexto

Análise baseada em boas práticas de engenharia de prompt (estrutura ROLE → TASK → SPECS → NOTES). O sistema já usa uma arquitetura Mãe+Filha sólida, mas os prompts das Filhas têm oportunidades de melhoria.

---

## O que está bem (não mudar)

1. **Separação de responsabilidade**: Mãe decide rota; Filha gera texto. Sem conflito de instrução.
2. **Few-shot examples na Qualification**: `training_examples_block` com 11 casos cobertos incluindo negativos.
3. **Notes no final**: `_ESCAPE_HATCH_BLOCK` e `_build_validation_block` posicionados no final (LLMs priorizam início e fim do prompt).
4. **7 proibições explícitas na Qualification**: nunca inventar, nunca urgência artificial, etc.

---

## Oportunidades de melhoria

### 1. System prompt das Filhas é genérico

Atualmente: "Você é a FILHA X e deve responder SOMENTE JSON".

**Proposta:** adicionar ao system prompt de cada Filha:
- Objetivo comercial da fase
- Tom de voz esperado
- Regra mais crítica dessa fase

Exemplo para Closing: *"Você é uma especialista em fechamento de vendas para WhatsApp. Seu único objetivo é confirmar a decisão de compra dos leads. Nunca envie links antes de confirmar interesse. Retorne SOMENTE JSON."*

**Atenção:** o system prompt pode precisar variar por tipo de agente (Agent 1, 2, 3), já que cada um tem objetivos diferentes.

---

### 2. custom_instructions injetado no meio do prompt

O bloco `custom_instructions` tem "prioridade máxima" mas é inserido no meio do prompt. LLMs priorizam início e fim.

**Proposta:** mover `custom_instructions_block` para o **final** de cada prompt Filha — junto com `_build_validation_block`. Isso garante que as instruções do operador sejam as últimas que o modelo vê.

---

### 3. Follow-up e Closing sem few-shot examples

Qualification tem `training_examples`. Apresentação tem 2 exemplos de sales. Follow-up e Closing não têm exemplos próprios — apenas regras descritivas.

**Proposta:**
- Criar estrutura de exemplos por fase e por tipo de agente
- Expor na UI de treinamento do AI Profile para que usuários possam customizar
- Garantir que exemplos de todas as fases apareçam nos prompts das Filhas correspondentes

---

### 4. Falta instrução de variação de resposta

O `_build_tone_block()` já proíbe bullet points, markdown e CAPS. Mas não instrui variação de abertura.

**Proposta:** adicionar ao tone_block: *"Nunca comece duas mensagens consecutivas com a mesma palavra ou estrutura. Consulte o histórico e varie o padrão de abertura."*

---

## Arquivos afetados

| Arquivo | O que mudar |
|---|---|
| `backend-executors/app/services/decision_engine.py` | System prompts das Filhas, posicionamento de custom_instructions, instrução de variação |
| `backend-crm/services/ai_orchestrator/orchestrator.py` | Injeção de examples por fase no ContextBundle |
| `frontend-crm/src/pages/AiProfile.tsx` | UI para treinamento de exemplos por fase |
