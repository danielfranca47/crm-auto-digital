# Fix: intent_trigger nunca dispara na mensagem que causa entrada na fase

**Branch:** `fix-intent-trigger-fase-entrada`
**Status:** Em andamento

---

## Motivação

A usuária Daniel (perfil "Sensi Vitae", `agent_mode=agenda`) configurou na fase `p2`
(Apresentação) um bloco `intent_trigger` — "Quando o cliente aceita ou diz sim para a
tabela de preços" — seguido de 3 blocos `midia` que deveriam enviar a tabela de preços
em imagem. No teste via Playground, quando o lead responde "sim, pode enviar", o
`mother_route` muda corretamente para `apresentation`, mas as 3 mídias nunca são
enviadas.

Causa raiz identificada em `_collect_intent_triggers_for_lead_phase()`
(`backend-executors/app/services/decision_engine.py:540-569`, antes do fix): essa
função decide quais blocos `intent_trigger` mostrar à LLM Mãe na secção
`[DETECÇÃO DE INTENÇÃO]` do prompt dela, e fazia isso olhando `lead.category` — o
estágio **salvo no banco antes desta mensagem chegar**. No turno em que o lead diz
"sim", `lead.category` ainda reflete a fase anterior (a transição para `apresentation`
só é decidida *nesse mesmo turno*, pela própria mãe). Como a fase `p2` ainda não
"existia" do ponto de vista da categoria salva, a mãe nunca via o trigger listado no
prompt dela → `detected_intents` voltava sem o rótulo → o `intent_trigger` avaliava
`fired=False` → os blocos `midia` seguintes (que dependem do trigger anterior no
modelo sequencial) nunca disparavam.

Não era um bug isolado da fase `p2`: qualquer `intent_trigger` configurado para
detectar "o lead fez/disse X" como o próprio sinal de entrada numa fase sofria o mesmo
problema, em qualquer fase (p1 a p5) — o que bate com o relato da usuária de que
"todas as etapas e gatilhos configurados no fluxo de venda não estão disparando" em
outros testes. `kw_trigger` e `phase_trigger` não têm esse problema, porque são
avaliados diretamente contra o `effective_route_to` já decidido nesse turno (fresco),
sem depender de uma previsão feita antes da decisão da mãe.

---

## Problemas Identificados (estado anterior)

1. **Coleta de intent triggers usava categoria desatualizada
   (`decision_engine.py:540-569`):** `_collect_intent_triggers_for_lead_phase()` só
   incluía os blocos `intent_trigger` da fase que já batia com `lead.category` — nunca
   incluía os da fase para a qual o lead estava prestes a transicionar naquele turno.
2. **Sem representação em Python da sequência de fases por `agent_mode`:** a tabela
   `consultivo` (p0→p1→p2→p4→p5), `direto` (p0→p1→p2→p5), `agenda`
   (p0→p1→p2→p3a→p3b→p4→p5) só existia em `frontend-crm/src/types/agente.ts:111-115`
   e documentada em `docs/architecture/sales-flow.md` — não havia equivalente no
   backend.
3. **Sem cobertura de teste:** nenhum teste em `backend-executors/tests/` cobria
   `_collect_intent_triggers_for_lead_phase`, `_evaluate_sales_flow_phases` ou o fluxo
   `intent_trigger` → `detected_intents` → `system_actions`.

---

## Abordagem

```
Mensagem do lead chega → decision_engine monta prompt da LLM Mãe
  → _collect_intent_triggers_for_lead_phase(context, agent_mode_normalized)
       fase_atual   = mapear lead.category → phase_id (default "p0" se vazio/recepção)
       fase_seguinte = próxima fase na sequência de agent_mode_normalized
                       (nova constante _SALES_FLOW_PHASE_SEQUENCE_BY_AGENT_MODE)
       retorna blocos intent_trigger de {fase_atual, fase_seguinte}
  → mãe vê AMBAS as fases no [DETECÇÃO DE INTENÇÃO] e classifica detected_intents
  → mãe decide route_to (pode já ser a fase seguinte, no mesmo turno)
  → _evaluate_sales_flow_phases(context, effective_route_to=route_to escolhido, detected_intents)
       avalia SÓ os blocos da fase escolhida (sem mudança aqui — já correto antes)
       intent_trigger.fired = intent_label in detected_intents  → agora pode ser True
       → midia/mensagem seguintes disparam normalmente
```

A avaliação final (`_evaluate_sales_flow_phases`) já era correta — usa o
`effective_route_to` fresco da decisão da mãe. O gap estava só na etapa anterior, de
"o que mostrar à mãe antes dela decidir". Olhar 1 fase à frente (não mais que isso)
mantém o prompt da mãe focado e é consistente com o resto do sistema, que já impede
saltar mais de um estágio por turno (`_ALLOWED_ADVANCE`, `decision_engine.py:~3969`).

---

## Plano de Implementação

### Fase 1 — Backend: olhar 1 fase à frente na detecção de intenção + testes + doc

**Objetivo:** permitir que `intent_trigger` dispare na própria mensagem que causa a
transição de fase, para qualquer fase e qualquer `agent_mode`.

| Arquivo | O que mudou |
|---|---|
| `backend-executors/app/services/decision_engine.py` | Nova constante `_SALES_FLOW_PHASE_SEQUENCE_BY_AGENT_MODE`; `_collect_intent_triggers_for_lead_phase()` passou a receber `agent_mode_normalized` e a incluir a fase seguinte além da atual; call site em `_build_mother_prompt()` (linha ~1766) passa o `agent_mode_normalized` já calculado (linha ~1754) |
| `backend-executors/tests/test_sales_flow_intent_trigger_phase_entry.py` (novo) | 7 testes: coleta com fase seguinte, modo `direto` (pula p3a/p3b/p4), limite de 1 fase à frente, compatibilidade com comportamento antigo, e 2 testes ponta-a-ponta reproduzindo o cenário relatado (mídia dispara com detecção; não dispara sem detecção) |
| `docs/architecture/sales-flow.md` | Linha do `intent_trigger` na tabela de triggers + nota sobre a janela de detecção de 1 fase à frente |

```python
# ANTES (decision_engine.py:540-569)
def _collect_intent_triggers_for_lead_phase(context: Dict[str, Any]) -> List[dict]:
    ...
    phase_id = _CATEGORY_TO_PHASE_ID.get(raw_category)  # None se lead ainda não está na fase
    if not phase_id:
        return []
    ...

# DEPOIS
_SALES_FLOW_PHASE_SEQUENCE_BY_AGENT_MODE: Dict[str, List[str]] = {
    "consultivo": ["p0", "p1", "p2", "p4", "p5"],
    "direto": ["p0", "p1", "p2", "p5"],
    "agenda": ["p0", "p1", "p2", "p3a", "p3b", "p4", "p5"],
}

def _collect_intent_triggers_for_lead_phase(context, agent_mode_normalized: str) -> List[dict]:
    ...
    current_phase_id = _CATEGORY_TO_PHASE_ID.get(raw_category, "p0")
    candidate_phase_ids = {current_phase_id}
    sequence = _SALES_FLOW_PHASE_SEQUENCE_BY_AGENT_MODE.get(agent_mode_normalized)
    if sequence and current_phase_id in sequence:
        idx = sequence.index(current_phase_id)
        if idx + 1 < len(sequence):
            candidate_phase_ids.add(sequence[idx + 1])
    # coleta blocos de todas as fases em candidate_phase_ids
```

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `b05a82f` | fix: intent_trigger passa a olhar a fase seguinte na detecção de intenção |

**Detalhes do commit:**
- `backend-executors/app/services/decision_engine.py` — nova constante `_SALES_FLOW_PHASE_SEQUENCE_BY_AGENT_MODE`; `_collect_intent_triggers_for_lead_phase()` agora recebe `agent_mode_normalized` e inclui a fase seguinte na coleta de intent triggers; call site atualizado
- `backend-executors/tests/test_sales_flow_intent_trigger_phase_entry.py` — novo arquivo de testes (7 casos)
- `docs/architecture/sales-flow.md` — documentação da janela de detecção de 1 fase à frente

---

### Relatório da Fase 1 — o que mudou na prática

**Antes:** quando um agente configurava um gatilho de "intenção detectada" (ex.:
"cliente aceitou a tabela de preços") numa fase do Fluxo de Venda para servir como o
próprio sinal de entrada nessa fase, o gatilho nunca disparava — as mídias/mensagens
automáticas associadas simplesmente não eram enviadas, silenciosamente, tanto no
Playground quanto no WhatsApp real.

**Agora:** o gatilho dispara corretamente na própria mensagem que causa a entrada na
fase, para qualquer fase (p1 a p5) e qualquer tipo de agente (`consultivo`, `direto`,
`agenda`).

**Para validar:** Cenário P1, abaixo.

---

## Checks de Validação

### Cenário P1 — Reprodução exata do bug relatado (Playground)
- [ ] Abrir Playground com o agente "Daniel" (ID 3, perfil Sensi Vitae, `agent_mode=agenda`)
- [ ] Cenário Inbound: lead diz "olá boa tarde, gostaria de saber sobre as massagens"
- [ ] Lead diz "sim, pode enviar" quando o bot oferecer a tabela de preços
- [ ] Confirmar: as 3 mídias da tabela de preços chegam no mesmo turno em que
      `mother_route` muda para `apresentation`
- **Testado em:** 18/08/2026, ao vivo via Playground local (perfil importado do export
  da usuária, conta de teste `autodigital157@gmail.com`) — o gatilho passou a ser
  mostrado corretamente à LLM Mãe (confirmado via log de depuração temporário), mas a
  mídia **ainda não chegou**: a mãe não preencheu `detected_intents` mesmo vendo a
  opção listada. Ver Fase 2 abaixo — bug diferente do corrigido na Fase 1, checkbox
  fica em aberto até a Fase 2 ser validada.

### Verificação automatizada (pytest — já executada nesta sessão, sem browser)
- [x] `pytest backend-executors/tests/test_sales_flow_intent_trigger_phase_entry.py -v`
      — 7/7 passaram
- **Validado em:** 18/08/2026 — também confirmado, via `git stash`, que as mesmas 7
  falhas ocorrem no código anterior ao fix (prova de que o teste captura o bug real) e
  que a suíte completa de `backend-executors/tests/` não teve nenhuma regressão nova
  (22 falhas pré-existentes, não relacionadas a este fix, idênticas antes/depois)

---

## Fase 2 — Diagnóstico: mãe não preenche `detected_intents` mesmo vendo a opção (18/08/2026)

### Problema identificado

Testando o Cenário P1 ao vivo (Playground, perfil real da usuária importado), confirmei
via log de depuração temporário que a Fase 1 funciona exatamente como projetado: mesmo
com o lead ainda em `qualification` (p1), o `intent_trigger` de `p2` já aparece na
lista `active_triggers` mostrada à LLM Mãe — a barreira de timing foi removida.

Porém, em **3 de 3 tentativas** (frases diferentes: "sim, pode enviar", "quero sim,
manda a tabela"), a mãe devolveu `detected_intents: []` mesmo com o trigger listado na
secção `[DETECÇÃO DE INTENÇÃO]` do prompt — apesar de, no mesmo turno, o campo `reason`
da própria mãe dizer explicitamente "Cliente aceitou o envio da tabela de preços". Ou
seja, a mãe *reconhece* a intenção em prosa livre mas não a replica no campo
estruturado `detected_intents`.

Causa provável: `generate_mother_route()` (`llm_service.py:132`) usa
`text.format.type="json_object"` — modo solto, sem schema JSON reforçado pela API, só
com instrução em texto. O bloco `[DETECÇÃO DE INTENÇÃO]` (`_intent_detection_block`) é
concatenado no **fim** do prompt (`decision_engine.py:1946`), mas a descrição do campo
`detected_intents` no schema JSON esperado aparece ~130 linhas **antes**, seguida de um
bloco extenso de "REGRAS DE ROTEAMENTO". É plausível que o modelo perca a ligação entre
a lista de intenções (vista por último) e o campo do schema (descrito bem antes),
priorizando o raciocínio de `route_to`/`reason` — que domina o prompt — sobre o
preenchimento de `detected_intents`, campo secundário.

Isto é um problema separado do corrigido na Fase 1 — a Fase 1 resolveu corretamente
"a mãe não via a opção"; este é "a mãe vê a opção mas não a reporta no campo certo".
Sem corrigir isto também, o sintoma relatado pela usuária (mídia não chega) continua a
acontecer na prática, mesmo com a Fase 1 aplicada.

### Correção

Reforçado o próprio `_intent_detection_block` (a última coisa que a mãe lê antes de
gerar o JSON) com um parágrafo final que: (1) reafirma que preencher
`detected_intents` é obrigatório quando a intenção for detectada, e (2) nomeia
explicitamente a inconsistência observada nos testes ao vivo — reconhecer a intenção
em `reason` mas devolver `detected_intents` vazio — como uma resposta inválida.

Não foi feita nenhuma reordenação do prompt nem duplicação do schema completo — a
posição atual do bloco (no fim, mais perto da geração) já é estruturalmente boa; o
problema era a força da instrução, não a posição.

| Arquivo | Mudança |
|---|---|
| `backend-executors/app/services/decision_engine.py` | `_intent_detection_block` (`_build_mother_prompt()`) ganhou 5 linhas de reforço final |
| `backend-executors/tests/test_sales_flow_intent_trigger_phase_entry.py` | Novo teste `test_mother_prompt_reinforces_detected_intents_consistency_with_reason` — confirma que o texto de reforço está presente no prompt (guarda de regressão; não substitui o teste ao vivo, já que valida conteúdo do prompt, não comportamento da LLM real) |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `490ce9b` | fix: reforçar instrução de detected_intents no prompt da mãe |

**Detalhes do commit:**
- `backend-executors/app/services/decision_engine.py` — `_intent_detection_block` ganha parágrafo "OBRIGATÓRIO" nomeando a inconsistência reason/detected_intents
- `backend-executors/tests/test_sales_flow_intent_trigger_phase_entry.py` — novo teste de conteúdo do prompt

### Relatório da Fase 2 — o que mudou na prática

**Antes:** mesmo depois da Fase 1 (que já fazia a mãe ver o gatilho a tempo), ela
reconhecia a intenção do cliente em texto livre (no campo interno "motivo" da decisão)
mas não marcava isso no campo estruturado que o sistema realmente usa — resultado:
mídia continuava sem ser enviada, mesmo após a Fase 1.

**Agora:** o prompt da mãe inclui um aviso final explícito dizendo que essa
inconsistência específica (reconhecer mas não marcar) é uma resposta inválida.

**Para validar:** Cenário P1, abaixo (repetição do mesmo teste da Fase 1, agora
verificando se a mídia realmente chega).

---

## Ajustes Possíveis Pós-Implementação

- `_ALLOWED_ADVANCE`/`_STAGE_ORDER` (`decision_engine.py:~3969`) é uma lógica paralela
  de "transições permitidas" usada nos guardrails de categoria — não foi unificada com
  a nova constante nesta fase por serem vocabulários diferentes (`route_to` vs
  `phase_id`) e por já cobrirem necessidades distintas; se divergirem no futuro vale
  revisar juntas.
- Blocos `webhook`, `condicao` e `espera` continuam sem execução em runtime (fora do
  escopo deste fix, já documentado como reservado para o futuro).
- A suíte `backend-executors/tests/` tem 22 testes falhando que já estavam quebrados
  antes deste fix (não relacionados ao Fluxo de Venda — parecem ligados a mojibake de
  encoding em prompts e a guardrails de qualificação). Fora do escopo deste fix, mas
  vale abrir um item separado para investigar.
