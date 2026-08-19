# Fix: `fire_once` não avisa a LLM que a ação já foi cumprida (repetição em prosa)

**Branch:** `fix-fire-once-repeticao-prosa`
**Status:** Proposta — aguardando avaliação/decisão do utilizador (não implementado)

---

## Motivação

Utilizador reportou (conta de teste `aydebarbaraqod@gmail.com`, AI Profile "Daniel", 19/08/2026):
configurou um bloco `intent_trigger` na fase p2 (Apresentação) do Fluxo de Venda, com
`fire_once=true`, intent `"Quando o cliente aceita ou diz sim para a tabela de preços"`,
seguido de 3 blocos `midia` (tabela de preços em imagens).

**Teste real (transcript do Playground, 19/08/2026 00:30):**
1. Lead pergunta sobre massagens → bot apresenta-se e pergunta "Posso enviar a tabela de
   preços com detalhes sobre cada serviço?"
2. Lead diz "sim" → `intent_trigger` dispara corretamente, as 3 imagens são enviadas.
3. Lead pergunta algo não relacionado ("onde fica o espaço?"), 2 turnos depois, ainda na
   fase p2 → o bot responde à pergunta de localização **mas volta a perguntar** "Posso
   enviar a tabela de preços para você conhecer melhor os serviços que oferecemos?" — como
   se a permissão nunca tivesse sido dada nem a tabela enviada.

**Confirmado por inspeção do transcript:** na 2ª ocorrência **nenhuma imagem foi reenviada**
— só a IA repetiu o pedido em texto. O mecanismo de deduplicação real (banco de dados)
funcionou; o problema é que a LLM não tem nenhum sinal, no seu próprio prompt, de que aquele
pedido já foi atendido antes nesta conversa.

**Pergunta original do utilizador:** *"Esse check é lido pela LLM ou existe um registro no
banco de dados quando ele é acionado uma vez para garantir que não seja enviado de novo?"*
— resposta confirmada abaixo, na secção de diagnóstico.

---

## Diagnóstico

### Já existe deduplicação real (banco de dados)?

**Sim.** Coluna `leads.triggers_fired` (`TEXT NULL`, JSON array de `block_id`s, adicionada
via `ensure_column` em `backend-crm/database.py`) é a fonte de verdade. Quando um bloco
`fire_once=true` dispara, o `decision_engine` emite
`system_actions[{type: "mark_trigger_fired", block_id}]`; o CRM
(`backend-crm/routes/executor.py` e `backend-crm/routes/playground.py`) faz o append do
`block_id` nessa coluna. Em turnos seguintes, a checagem é **determinística em código**, não
delegada à LLM:

`backend-executors/app/services/decision_engine.py`, função `_evaluate_sales_flow_phases`:
```python
# kw_trigger — linha ~401-403
if _fire_once and _block_id and _block_id in _triggers_fired:
    fired = False

# intent_trigger — linha ~422-425
if _fire_once and _block_id and _block_id in _triggers_fired:
    fired = False
```

Isso está correto e é o que impediu o reenvio das imagens no teste do utilizador.

### Então por que a pergunta se repetiu?

**Gap real, confirmado por leitura de código.** O dedup acima só decide se o **bloco de
ação** (`midia`/`mensagem`) volta a disparar — ele não deixa nenhum rastro no **prompt da
LLM**. Duas lacunas, ambas na mesma função/arquivo:

1. **`_evaluate_sales_flow_phases`** (`decision_engine.py:322-540`): quando `fired=False`
   por já estar em `_triggers_fired`, o código simplesmente segue sem adicionar nada a
   `result["prompt_injections"]`. O resultado dessa função (incluindo `prompt_injections`)
   é injetado diretamente no prompt do LLM filho via `_build_sales_flow_phases_block()`
   (`decision_engine.py:550-555`), chamado em `_qual_prompt` (~2407), `_apres_prompt`
   (~2993 — a fase do bug relatado) e `_followup_prompt` (~3325). Sem nota, a LLM filha
   fica sem qualquer sinal estrutural de "isso já foi cumprido" — depende inteiramente de
   inferir isso sozinha a partir do histórico de mensagens, e (neste teste) falhou, porque
   o `custom_instructions` do utilizador tem um roteiro fixo numerado ("2- Pergunte se pode
   enviar a tabela... 4- Envie a tabela...") injetado com prioridade máxima todo turno.

2. **`_collect_intent_triggers_for_lead_phase`** (`decision_engine.py:569-615`): monta a
   lista de `intent_trigger` da fase atual+seguinte para a secção `[DETECÇÃO DE INTENÇÃO]`
   do prompt da IA Mãe (`_build_mother_prompt`, ~1787-1792) — **sem checar `fire_once`/
   `triggers_fired`**. A Mãe continua a ver o mesmo `intent_trigger` (com o seu `note`
   completo) todo turno enquanto o lead estiver na fase p2, mesmo depois de já ter disparado
   uma vez. Isto não causa reenvio (o dedup na hora de executar continua a proteger isso),
   mas mantém o tópico "aceitar a tabela" artificialmente vivo no contexto da Mãe.

### Paridade Playground ↔ WhatsApp real

Confirmado: os dois convergem na mesma função `decision_engine.decide()` —
Playground via HTTP para `backend-executors/app/api/playground_internal.py:68`, WhatsApp
real via import direto em `backend-executors/app/runners/whatsapp.py`. Uma correção dentro
de `_evaluate_sales_flow_phases`/`_collect_intent_triggers_for_lead_phase` (reaproveitando
dados já presentes em `context["lead"]["triggers_fired"]`) vale automaticamente para os dois
caminhos — não precisa de alteração em `enrich_context_bundle()` nem duplicação de lógica.

### Padrão semelhante já existente no código?

O flag `qual_opener` (fase p1) tem lógica de "não repetir depois da 1ª vez", mas por
**omissão condicional** (só injeta quando `asked_questions_json` está vazio —
`decision_engine.py:2241-2265`), não por uma nota explícita de "já feito". Não há hoje um
precedente idêntico de "avisar a LLM que uma ação já foi cumprida" — mas o padrão de nota
informativa em `prompt_injections` já existe para outro caso (nota de "envio automático
pendente", mesma função, ~linha 484-502), o que dá o precedente de formatação/tom a seguir.

### Testes existentes

`backend-executors/tests/test_sales_flow_intent_trigger_phase_entry.py` — importa
`_evaluate_sales_flow_phases` e `_collect_intent_triggers_for_lead_phase` diretamente,
testa com `context` mockado em dict puro (sem DB/HTTP). Tem helpers reutilizáveis
(`_context()`, `_sales_flow_with_intent_trigger_and_media()`, constante `INTENT_LABEL`).
Nenhum teste cobre hoje o caso "`fire_once` + já em `triggers_fired`" — gap de cobertura
real, não só de comportamento.

---

## Abordagem proposta

Adicionar, dentro de `_evaluate_sales_flow_phases`, uma nota em `result["prompt_injections"]`
quando um bloco `fire_once` já disparado é reavaliado (branch que hoje só marca
`fired=False`), avisando a LLM filha que aquele pedido/ação já foi cumprido antes nesta
conversa — mas deixando explícito que isso não a impede de voltar a falar do assunto se o
lead tocar nele por conta própria (só não deve repetir o pedido/oferta automática, como se
fosse a primeira vez).

```
Turno N (trigger dispara)        → ação executada + mark_trigger_fired → BD atualizado
Turno N+k (mesmo trigger reavaliado, já em triggers_fired)
    → fired = False (como hoje)
    → NOVO: prompt_injections recebe nota "[FLUXO DE VENDA — ação já cumprida: ...]"
    → LLM filha lê a nota no mesmo prompt onde receberia o roteiro/custom_instructions
    → LLM evita repetir o pedido de permissão em prosa
```

### Fase única proposta (implementação + testes num só commit)

**1. Novo helper `_read_triggers_fired_set(context)`** — extrai a leitura/parse de
`leads.triggers_fired` que hoje está inline em `_evaluate_sales_flow_phases`
(`decision_engine.py:368-378`), para reaproveitar também na Opção B (abaixo) sem duplicar
o parsing.

**2. Novo helper `_build_already_fired_trigger_note(type_id, block)`** — gera o texto da
nota, no mesmo padrão das notas existentes (prefixo `[FLUXO DE VENDA — ...]`), citando o
`intent`/`keywords` do bloco e (se preenchida) a `note` original como referência.

**3. Hook nos branches `fired=False` por já disparado** — adiciona a chamada ao helper
acima logo depois de `fired = False`, tanto em `kw_trigger` (~linha 401-403) quanto em
`intent_trigger` (~linha 422-425) — ver "Opção A" abaixo sobre incluir ou não `kw_trigger`.

**4. Testes novos** em `test_sales_flow_intent_trigger_phase_entry.py`, seguindo o padrão
já usado no arquivo:
- Nota aparece quando `intent_trigger` com `fire_once` já disparado é reavaliado (reproduz
  o bug relatado) — e a mídia continua sem ser reenviada.
- Nota NÃO aparece quando o trigger nunca disparou (regressão do comportamento atual).
- (Se Opção A incluir `kw_trigger`) mesmo teste para `kw_trigger`.
- (Se Opção B for incluída) `_collect_intent_triggers_for_lead_phase` deixa de retornar um
  bloco já disparado.

---

## Opções em aberto (a decidir antes de implementar)

### Opção A — Escopo: só `intent_trigger`, ou também `kw_trigger`?

| | Descrição | Trade-off |
|---|---|---|
| **A1 — Só `intent_trigger`** | Corrige exatamente o caso relatado. | `kw_trigger` fica com o mesmo gap não corrigido — se acontecer na prática (mesmo mecanismo, mesmo risco), precisa de um novo ciclo de diagnóstico/fix. |
| **A2 — `intent_trigger` + `kw_trigger` (recomendado pelo diagnóstico)** | Mesmo helper cobre os dois — custo extra é pequeno (poucas linhas + 1 teste), fecha o mesmo bug potencial em `kw_trigger`. | Escopo da mudança um pouco maior; nenhum caso real de `kw_trigger` foi reportado ainda (é preventivo, não reativo). |

### Opção B — Incluir também o filtro na IA Mãe?

| | Descrição | Trade-off |
|---|---|---|
| **B1 — Não incluir agora** | Foca só na causa direta do bug relatado (nota na LLM filha). | A Mãe continua a ver o `intent_trigger` já disparado na secção `[DETECÇÃO DE INTENÇÃO]` todo turno — ruído de prompt que não causa reenvio, mas mantém o tópico "vivo" sem necessidade. |
| **B2 — Incluir (`_collect_intent_triggers_for_lead_phase` passa a filtrar blocos já disparados)** | Filtro aditivo de baixo risco, reaproveita o mesmo helper de leitura. Reduz ruído no prompt da Mãe sobre um tópico já resolvido. | Mudança adicional num segundo ponto do código — mais uma função a testar/revisar, embora de risco baixo (não afeta o dedup real de ação). |

**Nenhuma decisão foi tomada ainda.** Este arquivo existe para o utilizador avaliar as
opções acima (e o diagnóstico) antes de aprovar a implementação — nesse momento, entra-se
em Plan Mode novamente para confirmar o plano final com o escopo escolhido, e o `Status`
deste arquivo passa a `Em andamento`.

---

## Checks de Validação propostos (a confirmar quando a implementação for aprovada)

### Cenário — Unitário
- [ ] `pytest backend-executors/tests/test_sales_flow_intent_trigger_phase_entry.py -v` —
  suite completa (existente + novos testes) verde.

### Cenário P1 — Reprodução do bug relatado no Playground
- [ ] Configurar `intent_trigger` (`fire_once=true`) + 3 blocos `midia` na fase p2.
- [ ] Turno 1: lead diz "sim" → confirmar as 3 mídias disparam e `triggers_fired` é
  atualizado no lead sandbox.
- [ ] Turno 2/3 (mensagens neutras, ex. pergunta de localização): confirmar que nenhuma
  mídia é reenviada **e** que a resposta da IA não volta a pedir permissão para enviar a
  tabela.

---

## Ajustes possíveis pós-implementação

- Nenhum identificado ainda — este arquivo é uma proposta pré-implementação.
