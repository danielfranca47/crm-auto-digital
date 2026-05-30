# Fluxo de Qualificação Natural — Abertura + Reação Contextual + Critérios

**Branch:** `etapa-8-7-fluxo-qualificacao-natural`
**Status:** Em andamento

---

## Motivação

Durante os testes do fluxo de venda, identificou-se que o agente:
1. Inicia perguntas de qualificação abruptamente, sem qualquer introdução — soa "frio" e mecanizado
2. Não reage à resposta anterior antes de fazer a próxima pergunta — dá sensação de questionário padronizado
3. Não há campo para o utilizador definir o critério esperado por pergunta ("qualificar se" / "não qualificar se")

O objetivo é tornar a qualificação mais natural e conversacional, mantendo o contrato LLM core intacto.

---

## Problemas Identificados (estado anterior)

1. **Ausência de abertura de qualificação (`decision_engine.py:2144`):** `_first_contact_opener_header` injeta apenas o `origin_inbound_opener` genérico. Não existe instrução para preparar o lead para uma sequência de perguntas.

2. **Transição mecânica entre perguntas (`decision_engine.py:2167`):** O prompt tem "Puxe gancho da última resposta" mas sem instrução explícita de comentário de reação antes da próxima pergunta. Resulta em sequências de perguntas sem reconhecimento do que o lead disse.

3. **Sem critérios de qualificação por campo (`agente.ts:6`):** `QualificationField` tem `question` e `passive_hint` mas não tem `qualify_if` / `disqualify_if`. O LLM não sabe o que é uma resposta "boa" vs. "fora do critério" por campo.

---

## Abordagem

```
Lead entra na qualificação
  └─ asked_questions_json vazio + qualification_fields ativo + bloco qual_opener presente
       → LLM injeta abertura amigável antes da primeira pergunta

Lead responde pergunta de qualificação
  └─ LLM lê qualify_if / disqualify_if do campo atual
       ├─ resposta dentro do critério → comentário de conexão ("Perfeito.", "Faz sentido!")
       └─ resposta fora do critério → compreensão breve ("Entendi.", "Certo.")
          → sem critério → reação natural ao contexto
  → próxima pergunta de qualificação
```

---

## Plano de Implementação

### Fase 1 — Critérios "Qualificar se" / "Não qualificar se" + Reação Natural

**Objetivo:** Adicionar campos opcionais avançados por campo e instrução de reação contextual no prompt

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/types/agente.ts` | `qualify_if?: string` e `disqualify_if?: string` em `QualificationField` |
| `frontend-crm/src/components/agente/CamadaQualificacao.tsx` | `DrawerCampo`: secção "Configurações avançadas" colapsível com 2 textareas |
| `backend-executors/app/services/decision_engine.py` | `_build_qualification_fields_block()`: incluir qualify_if/disqualify_if; `_build_child_prompt_qualification()`: instrução de reação natural |

### Fase 2 — Abertura de Qualificação no Fluxo de Venda

**Objetivo:** Bloco especial na fase p1 do Fluxo de Venda; auto-sugerido quando qualification_fields tem campos ativos

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/types/agente.ts` | `qual_opener?: boolean` em `SalesFlowBlock` |
| `frontend-crm/src/components/agente/CamadaFluxoVenda.tsx` | Fase p1: detectar bloco `qual_opener:true`; mostrar com label "Abertura de Qualificação"; banner de sugestão quando ausente e há campos ativos |
| `backend-executors/app/services/decision_engine.py` | `_build_child_prompt_qualification()`: detectar bloco `qual_opener:true` em p1; injetar apenas quando `asked_questions_json` vazio |

---

## Checks de Validação

### Cenário P1 — Critérios aparecem no editor de campo
- [ ] Abrir CamadaQualificacao → clicar num campo → abrir DrawerCampo
- [ ] Confirmar: secção "Configurações avançadas" aparece (colapsível)
- [ ] Preencher "Qualificar se" e "Não qualificar se" → Salvar
- [ ] Confirmar: campos persistem ao reabrir o drawer

### Cenário P2 — Bloco de abertura aparece e é editável no Fluxo de Venda
- [ ] Configurar pelo menos 1 campo ativo em qualification_fields
- [ ] Abrir Fluxo de Venda → fase p1
- [ ] Confirmar: banner "Adicionar instrução de abertura" aparece
- [ ] Clicar → bloco é criado com texto padrão e label "Abertura de Qualificação"
- [ ] Editar texto → Salvar → confirmar que persiste

### Cenário P3 — Playground: abertura disparada apenas na primeira mensagem
- [ ] Qualification_fields com 1+ campos ativos + bloco de abertura configurado
- [ ] Playground → enviar primeira mensagem
- [ ] Confirmar: resposta inclui abertura amigável antes da primeira pergunta
- [ ] Enviar segunda mensagem → confirmar: abertura NÃO repete

### Cenário P4 — Playground: reação contextual após cada resposta
- [ ] Qualification_fields com qualify_if/disqualify_if em pelo menos 1 campo
- [ ] Playground: responder com valor que corresponde ao qualify_if
- [ ] Confirmar: bot faz comentário de conexão antes da próxima pergunta
- [ ] Responder com valor fora do critério
- [ ] Confirmar: bot mostra compreensão breve antes de avançar

### Cenário P5 — Sem qualification_fields ativos: funcionalidades não aparecem
- [ ] Agente SEM qualification_fields (ou todos mode: 'off')
- [ ] Confirmar: Fluxo de Venda p1 não exibe banner de abertura
- [ ] Confirmar: Playground — bot não tem abertura especial nem instrução de reação

---

## Ajustes Possíveis Pós-Implementação

- `qualify_if` e `disqualify_if` são texto livre; uma versão futura poderia oferecer opções pré-definidas ou exemplos por nicho.
- A abertura de qualificação poderia ser integrada ao meta-prompter (Fase 4) para gerar um opener personalizado por nicho automaticamente.
