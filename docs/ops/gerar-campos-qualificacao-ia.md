# Análise: Qualificação no Playground e Feature "Gerar com IA"

> Contexto: teste realizado em 08/05/2026 com o perfil Sofia (sdr_scheduler / AutoSell).  
> Complementa `analise-qualificacao-ai-profile.md` — foca nos achados do teste e nas melhorias implementadas.

---

## Ponto Zero — "Quantas pessoas compõem sua equipe de vendas?"

### O que aconteceu

O agente perguntou "Quantas pessoas compõem sua equipe de vendas?" sem que o campo `company_size` tivesse sido configurado nos filtros F1/F2/F3.

### Causa raiz (bug corrigido)

O campo apareceu porque `qualification_required_fields` (lista legada, derivada automaticamente pelo backend quando o perfil foi salvo) continha:

```json
["service_interest", "company_size", "availability_window", "custom_decisor"]
```

Na função `_get_required_fields_override()` em `backend-executors/app/services/decision_engine.py`, a lógica **verificava a lista legada primeiro**. Como ela existia e era uma lista, retornava imediatamente — ignorando o `qualification_fields` rico que o usuário configurou (que continha apenas "Decisor").

Resultado: `company_size` entrou em `required_fields`, foi marcado como `missing_field`, virou `current_field`, e o LLM foi instruído a perguntar sobre ele. Sem `question` configurada, o agente improvisou usando o `QUALIFICATION_FIELD_FALLBACK_LABELS` interno.

### Correção aplicada

A função agora **verifica `qualification_fields` primeiro**. Se existir (mesmo resultando em lista vazia de obrigatórios), usa e descarta a lista legada.

```
Antes: qualification_required_fields → qualification_fields (fallback)
Depois: qualification_fields → qualification_required_fields (backward compat somente se qualification_fields ausente)
```

**Efeito:** o agente pergunta **somente** os campos que o usuário configurou explicitamente nos filtros F1/F2/F3.

---

## Por que "Critérios de Qualificação" (base de conhecimento) não dispara perguntas

### O que é o campo "Critérios de Qualificação"

É um `knowledge_item` com `category = 'qualification_criteria'` — texto livre descritivo, como:

```
Aprovado se:
- Faturamento acima de R$ 500k/ano
- Decisor: sócio, CEO, CFO ou diretor
...
```

### Por que não gera perguntas automaticamente

A base de conhecimento é injetada no prompt do LLM como **contexto informativo** — o agente sabe o que qualifica ou desqualifica um lead, mas não sabe *o que* perguntar para descobrir se o lead se enquadra.

A lógica de perguntas usa exclusivamente:
1. `qualification_fields[].question` — a pergunta configurada para cada campo
2. `missing_fields` / `current_field` — qual campo ainda falta coletar

**Não é um bug.** São dois sistemas com responsabilidades distintas:

| Sistema | Propósito | Quem usa |
|---|---|---|
| `qualification_fields` | Estrutura operacional — o agente *sabe o que perguntar* | Orquestrador (controle de fluxo) |
| Critérios de Qualificação (knowledge) | Contexto semântico — o agente *sabe o que aprovaria/reprovaria* | LLM (interpretação de respostas) |

### O gap identificado

O usuário define critérios em linguagem natural na knowledge base, mas precisa manualmente criar campos estruturados equivalentes nos filtros F1/F2/F3. Esse trabalho de tradução é repetitivo e propenso a omissões — daí a feature "Gerar com IA".

---

## Por que o campo "Decisor" funcionou corretamente

O usuário configurou explicitamente em F1:
- **Nome:** Decisor
- **Pergunta:** "Qual seu cargo na empresa?"
- **Capturar passivamente:** Lead mencionar o cargo

Esse campo entrou em `qualification_fields` com `mode: "required"` e `question` preenchida. O agente encontrou a pergunta configurada e a usou — exatamente o comportamento esperado.

---

## Feature: Botão "Gerar com IA"

### Problema resolvido

Eliminar o trabalho manual de traduzir os "Critérios de Qualificação" (texto livre na knowledge base) em campos estruturados dos filtros F1/F2/F3.

### Como funciona

```
Usuário clica "Gerar com IA" em Camada 2 - Qualificação
  → POST /api/qualification/generate-fields
  → Backend lê knowledge_items WHERE category='qualification_criteria'
  → Backend lê AI profile (niche, target_audience, agent_mode)
  → Chama GPT-4o-mini com prompt estruturado
  → Retorna array de QualificationField[]
  → Frontend exibe preview para confirmação
  → Usuário aceita → campos são aplicados aos filtros
```

### Contexto do LLM (system prompt)

O LLM recebe instruções completas sobre:
- O que é cada tipo de agente (SDR, closer, consultivo)
- O que pertenece a F1, F2 e F3 no caso SDR
- Como formular perguntas naturais para WhatsApp
- Formato JSON esperado

### Restrições da geração

- Máximo 8 campos no total (SDR: máximo 3 por filtro)
- Apenas campos decisivos para qualificação/desqualificação marcados como `required`
- Perguntas naturais para WhatsApp (não estilo formulário)
- Para SDR: campos classificados em `group: f1 | f2 | f3`
- Para outros agentes: lista plana sem grupos

### Onde está implementado

| Componente | Arquivo |
|---|---|
| Endpoint backend | `backend-crm/routes/qualification.py` |
| Registro do router | `backend-crm/app.py` |
| Método no cliente HTTP | `frontend-crm/src/services/api.ts` |
| Botão + preview UI | `frontend-crm/src/components/agente/CamadaQualificacao.tsx` |

---

## Avaliação de necessidades futuras

### 4.1 — Rotas de perguntas condicionais

**Descrição:** fluxo hierárquico onde a próxima pergunta depende da resposta anterior.

**Avaliação:**
- Valor: alto — conversa muito mais natural
- Complexidade: alta — requer novo schema de campo com `branches[]`, impacto em orchestrator e decision_engine
- Risco: alto para a fase atual

**Recomendação:** adiar. O botão "Gerar com IA" resolve o problema de configuração; `custom_instructions` pode ser usado para instruir o LLM a adaptar a ordem das perguntas contextualmente. Um fluxo condicional determinístico exige mudança de arquitetura.

### 4.3 — Usar respostas anteriores como gancho

**Descrição:** se o lead já mencionou X, usar isso como contexto natural para a próxima pergunta em vez de repetir ou ignorar.

**Avaliação:**
- Valor: médio — comportamento mais humanizado
- Complexidade: baixa para versão básica

**Recomendação:** implementar via `custom_instructions` no AI Profile. Exemplo de instrução a orientar o usuário a adicionar:

```
Se o lead já mencionou o cargo ou empresa, não repita a pergunta.
Use o que já foi dito como gancho natural para a próxima qualificação
("Você mencionou que é diretor — e quanto ao timing para implementar...").
```

Uma versão mais robusta (injetar o histórico de campos já coletados no prompt de forma explícita) pode ser feita no `decision_engine.py` como melhoria incremental futura.
