# Fluxo de Qualificação Natural — Abertura + Reação Contextual + Critérios

**Branch:** `etapa-8-7-fluxo-qualificacao-natural`
**Status:** P1, P2 e P3 validados (31/05/2026); P4 validado parcialmente (transições naturais observadas, reação explícita a qualify_if com compliance parcial do LLM)

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
| `frontend-crm/src/components/agente/CamadaQualificacao.tsx` | `DrawerCampo`: componente `AdvancedCriteria` colapsível com 2 textareas para os critérios |
| `backend-executors/app/services/decision_engine.py` | `_build_qualification_fields_block()`: inclui qualify_if/disqualify_if no bloco; `_build_child_prompt_qualification()`: instrução `_natural_reaction_block` |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `ff32a7b` | Fases 1 e 2 em conjunto (critérios + reação natural + abertura de qualificação) |

**Detalhes do commit `ff32a7b`:**
- `frontend-crm/src/types/agente.ts` — qualify_if/disqualify_if em QualificationField; qual_opener em SalesFlowBlock
- `frontend-crm/src/components/agente/CamadaQualificacao.tsx` — componente AdvancedCriteria no DrawerCampo
- `frontend-crm/src/components/agente/CamadaFluxoVenda.tsx` — QualOpenerBanner, QualOpenerCard, extraHeader em PhaseSection, lógica no loop p1
- `backend-executors/app/services/decision_engine.py` — qualify_if/disqualify_if em _build_qualification_fields_block; _natural_reaction_block e _qual_opener_injection em _build_child_prompt_qualification

---

### Fase 2 — Abertura de Qualificação no Fluxo de Venda

**Objetivo:** Bloco especial na fase p1 do Fluxo de Venda; auto-sugerido quando qualification_fields tem campos ativos

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/types/agente.ts` | `qual_opener?: boolean` em `SalesFlowBlock` |
| `frontend-crm/src/components/agente/CamadaFluxoVenda.tsx` | Fase p1: `QualOpenerBanner` quando ausente; `QualOpenerCard` quando presente (editável/removível) |
| `backend-executors/app/services/decision_engine.py` | `_build_child_prompt_qualification()`: detecta `qual_opener:true` em p1 + injeta apenas quando `asked_questions_json` vazio |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `ff32a7b` | Ver Fase 1 — mesmo commit |

---

## Checks de Validação

### Cenário P1 — Critérios aparecem no editor de campo
- [x] Abrir CamadaQualificacao → clicar num campo → abrir DrawerCampo
- [x] Confirmar: secção "Configurações avançadas" aparece (colapsível)
- [x] Preencher "Qualificar se" e "Não qualificar se" → Salvar
- [x] Confirmar: campos persistem ao reabrir o drawer
- **Validado em:** 31/05/2026 — DrawerCampo do campo "Decisor" (Filtro 1 SDR) mostrou secção "CONFIGURAÇÕES AVANÇADAS" colapsível. Badge "configurado" aparece ao preencher os campos. Após SALVAR CAMADA 2, reabrir o drawer confirma badge "configurado" persistido no servidor.

### Cenário P2 — Bloco de abertura aparece e é editável no Fluxo de Venda
- [x] Configurar pelo menos 1 campo ativo em qualification_fields
- [x] Abrir Fluxo de Venda → fase p1
- [x] Confirmar: banner "Adicionar instrução de abertura" aparece
- [x] Clicar → bloco é criado com texto padrão e label "Abertura de Qualificação"
- [x] Editar texto → Salvar → confirmar que persiste
- **Validado em:** 31/05/2026 — Agente Sofia (8 campos ativos). Fase 1 mostrou banner "Sem instrução de abertura configurada". "+ ADICIONAR ABERTURA" criou QualOpenerCard com label "ABERTURA DE QUALIFICAÇÃO", badges "automática · 1ª mensagem" e texto padrão. EDITAR abriu textarea inline. Após salvar, bloco persiste (total: 13 blocos configurados).

### Cenário P3 — Playground: abertura disparada apenas na primeira mensagem
- [x] Qualification_fields com 1+ campos ativos + bloco de abertura configurado
- [x] Playground → enviar primeira mensagem (recepcao) → segunda mensagem (qualification)
- [x] Confirmar: resposta inclui abertura amigável antes da primeira pergunta
- [x] Enviar segunda mensagem de qualificação → confirmar: abertura NÃO repete
- **Validado em:** 31/05/2026 — Lead #164 (Sofia). Turno de qualificação (4 bolhas): "Oi! Sou Sofia da AutoSell." + "Posso te fazer algumas perguntas rápidas antes de avançar?" + "Primeiro, quero entender melhor." + "Você é o sócio, CEO, CFO ou diretor da empresa?". Turno seguinte: 1 bolha apenas com a próxima pergunta — opener não repetiu.
- **Fix aplicado (commit `5311744`):** `_qual_opener_injection` foi movido do início do prompt para imediatamente antes do CONTEXTO (maior saliência para o LLM). A phrasing foi também melhorada para deixar explícito que abertura e pergunta ficam juntas em `message_text`.

### Cenário P4 — Playground: reação contextual após cada resposta
- [x] Qualification_fields com qualify_if/disqualify_if em pelo menos 1 campo
- [x] Playground: responder com valor que corresponde ao qualify_if (CEO)
- [⚠️] Confirmar: bot faz comentário de conexão antes da próxima pergunta
- [⏭️] Responder com valor fora do critério — não testado separadamente
- [⏭️] Confirmar: bot mostra compreensão breve antes de avançar — não testado separadamente
- **Validado parcialmente em:** 31/05/2026 — O LLM usa frases de transição naturais ("Para entender como podemos ajudar melhor, qual é o orçamento mensal...") ao invés de sair direto de pergunta para pergunta. No entanto, o comentário de conexão explícito baseado em qualify_if ("Perfeito!", "Faz sentido!") não foi observado de forma consistente — o LLM prioriza a transição fluida sobre a reação explícita ao critério. A instrução `_natural_reaction_block` está a funcionar mas com compliance parcial do LLM.

### Cenário P5 — Sem qualification_fields ativos: funcionalidades não aparecem
- [⏭️] Agente SEM qualification_fields (ou todos mode: 'off')
- [⏭️] Confirmar: Fluxo de Venda p1 não exibe banner de abertura
- [⏭️] Confirmar: Playground — bot não tem abertura especial nem instrução de reação
- **Pulado:** verificado por leitura de código — condição `hasActiveQualFields` (frontend) e `_has_active_qual_fields` (backend) são `false` quando não há campos ativos; ambos os blocos UI e prompt ficam inativos.

---

## Fase 3 — Fix: reposicionamento do qual_opener_injection (31/05/2026)

### Problema identificado

O `_qual_opener_injection` estava a ser injectado no INÍCIO do prompt de qualificação (antes do bloco de identidade e regras). O LLM tendia a "esquecer" a instrução ao gerar a resposta — o resultado era apenas a pergunta de qualificação sem a abertura.

### Correção

Movido para imediatamente antes do CONTEXTO (ao lado da ROTA MÃE), que é a posição de maior saliência. A phrasing foi melhorada para explicitar que abertura + pergunta ficam juntas em `message_text`.

| Arquivo | Mudança |
|---|---|
| `backend-executors/app/services/decision_engine.py` | `_qual_opener_injection` movido do topo do f-string para antes do CONTEXTO; phrasing melhorada |

### Commits Fix

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `5311744` | fix: reposicionar qual_opener_injection para antes do CONTEXTO no prompt de qualificação |

---

## Ajustes Possíveis Pós-Implementação

- `qualify_if` e `disqualify_if` são texto livre; uma versão futura poderia oferecer opções pré-definidas ou exemplos por nicho.
- A abertura de qualificação poderia ser integrada ao meta-prompter (Fase 4) para gerar um opener personalizado por nicho automaticamente.
- A reação explícita a qualify_if/disqualify_if (P4) tem compliance parcial do LLM — considerar adicionar exemplos few-shot de reações (via meta-prompter `qualification_phrasing`) para reforçar o comportamento.
