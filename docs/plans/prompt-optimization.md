# Otimização de Prompts das LLMs Filhas

> **Status: MAIORIA IMPLEMENTADA**
> Itens 1, 2 e 3 concluídos. Item 4 parcialmente implementado.
> **Pendência sujeita a reavaliação** — decidir se a instrução completa de variação de abertura ainda é necessária.

## O que está bem (não mudar)

1. **Separação de responsabilidade**: Mãe decide rota; Filha gera texto. Sem conflito de instrução.
2. **Few-shot examples na Qualification**: `training_examples_block` com casos cobertos incluindo negativos.
3. **Notes no final**: `_ESCAPE_HATCH_BLOCK` e `_build_validation_block` posicionados no final (LLMs priorizam início e fim do prompt).
4. **7 proibições explícitas na Qualification**: nunca inventar, nunca urgência artificial, etc.

---

## Itens implementados

### 1. System prompt das Filhas é específico por fase ✅

`FILHA FOLLOW-UP` e `FILHA CLOSING` têm system prompts especializados com objetivo comercial da fase. A variação por tipo de agente (`agent_mode_normalized`) é injetada no contexto do prompt de cada filha.

---

### 2. custom_instructions posicionado no final ✅

`_build_custom_instructions_block` está no final de todos os prompts de fase (qualification, apresentation, follow-up, closing), garantindo que as instruções do operador sejam processadas com prioridade.

---

### 3. Follow-up e Closing com few-shot examples ✅

`_build_training_examples_block` é chamado para todas as fases: `qualification`, `apresentation`, `followup`, `closing`. Os exemplos são lidos de `context.training_examples` (populado pelo AI Profile).

---

## Item pendente (sujeito a reavaliação)

### 4. Instrução de variação de resposta ⚠️ Parcial

O `_build_tone_block()` atualmente inclui: *"não comece com 'Olá, tudo bem?' genérico se já houve conversa anterior"*.

**O que falta:** instrução explícita de variação de estrutura de abertura entre mensagens consecutivas — proposta original: *"Nunca comece duas mensagens consecutivas com a mesma palavra ou estrutura. Consulte o histórico e varie o padrão de abertura."*

**Arquivo afetado:** `backend-executors/app/services/decision_engine.py` — função `_build_tone_block()`

---

## Arquivos de referência

| Arquivo | O que contém |
|---|---|
| `backend-executors/app/services/decision_engine.py` | System prompts das Filhas, posicionamento de custom_instructions, tone_block |
| `backend-crm/services/ai_orchestrator/orchestrator.py` | Injeção de training_examples no ContextBundle |
| `frontend-crm/src/pages/AiProfile.tsx` | UI de configuração do AI Profile |
