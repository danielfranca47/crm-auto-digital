# Fix: instrução de agendamento vazando para o agente "Fechamento Direto" (Closer)

**Branch:** `fix/instrucao-agendamento-closer`
**Status:** Em andamento

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de `fix-fluxo-vendas-sequencial.md`.

Na Fase 4 desse trabalho, a instrução hardcoded "RECONHECIMENTO DE INTERESSE DE
AGENDAMENTO" (`backend-executors/app/services/decision_engine.py`,
`_build_child_prompt_apresentation`, variável `_booking_signal_block`) foi migrada
para um bloco editável/removível do Fluxo de Venda (`booking_signal_opener`) — mas
só para `agent_mode_normalized == "agenda"` (agentes "Foco em Agenda": SDR e
Híbrido). Para `direto`/`consultivo`, o texto hardcoded original continua a ser
injectado sempre, sem controlo do utilizador.

Investigação feita durante a triagem de graduação confirmou que, para o Closer
(`agent_mode: "direto"`, `agent_type: "agent_2"`), isso é um problema real, não só
uma limitação de escopo: `_resolve_presentation_variant()` (mesmo arquivo,
linha ~1396) resolve `presentation_variant="sales"` por padrão para `direto` —
o formato "Confirmar / Enviar Link" cujo objectivo é fechar a venda directamente.
A instrução hardcoded, porém, manda o agente "reconhecer o interesse e perguntar
sobre dia/horário preferencial" quando o lead já escolheu um serviço ou pergunta
sobre horários — ou seja, empurra o Closer para pedir agendamento em vez de seguir
o fluxo de fechamento (Confirmar/Enviar Link) que é o propósito real desse tipo de
agente. `recommended_next_category='pre-agendamento'` também não corresponde a
nenhum estágio real do pipeline de `direto`
(`SALES_FLOW_PHASES_BY_AGENT_MODE.direto = ['p0','p1','p2','p5']` — sem p3a/p3b),
ainda que esse campo seja só informativo nesta rota (não aplicado automaticamente).

**Decisão de escopo tomada na triagem:** só o Closer entra nesta correcção agora.
O caso de `consultivo` (mais cinzento — ver diagnóstico em
`docs/implementations/fix-fluxo-vendas-sequencial.md`, secção "Fase 4") ficou
registado como item não-urgente em
[`docs/plans/fluxo-vendas-melhorias-futuras.md`](../plans/fluxo-vendas-melhorias-futuras.md) (M1).

---

## Problemas Identificados (estado anterior)

1. **Instrução de agendamento aplicada ao Closer sem filtro:** `decision_engine.py`,
   `_build_child_prompt_apresentation` — o texto hardcoded de reconhecimento de
   agendamento é injectado para qualquer `agent_mode`, incluindo `direto`, mesmo
   sem nenhum bloco `booking_signal_opener` configurado pelo utilizador (o
   mecanismo dessa Fase 4 só existe para `agent_mode_normalized == "agenda"`).
2. **Contradição com o propósito do variant `sales`:** a instrução pede para
   "perguntar dia/horário" no mesmo turno em que as regras do variant `sales`
   (mesma função, mais acima no prompt) esperam CONFIRMAR ou ENVIAR LINK — dois
   comportamentos concorrentes no mesmo prompt.

---

## Abordagem

**Decisão do utilizador (Plan Mode):** remover a instrução de agendamento por
completo do Closer — sem oferecer um bloco equivalente ("horário") na fase de
apresentação (p2), já que "perguntar disponibilidade" nunca é o comportamento
correto para um Closer. Em vez disso, o utilizador quer poder configurar, para o
Closer, instruções sobre **quando enviar o link de pagamento / configuração de
pagamento** — e essa configuração deve viver no **fim do fechamento da venda**
(fase p5 "Fechamento" / rota `closing`), não em p2.

Achado extra durante a investigação: a fase p5 já existe, já está sempre ativa
(inclusive para `direto`: `p0→p1→p2→p5`), e o builder do frontend
(`CamadaFluxoVenda.tsx`, linha ~1798) já renderiza p5 com a UI genérica de blocos
(`orientacao`, `mensagem`, `mídia`, `avançar_fase`) para **qualquer** agent_mode,
sem nenhum gate especial — ou seja, o utilizador já consegue hoje adicionar um
bloco `orientacao` em p5 pelo builder. O problema é que
`_build_child_prompt_closing()` (linha 3863) nunca chama
`_build_sales_flow_phases_block(_evaluate_sales_flow_phases(...))` como todos os
outros builders de fase fazem (`recepcao`, `qualification`, `apresentation`,
`follow_up`) — então qualquer bloco `orientacao` configurado em p5 é
**silenciosamente ignorado** no prompt, para todos os agent_modes. Ligar essa
fiação entrega o pedido do utilizador sem precisar de nenhum componente novo no
frontend: o Closer passa a poder escrever, no builder já existente (fase
"Fechamento"), instruções livres sobre o momento de enviar o link / configuração
de pagamento — e essas instruções finalmente chegam à LLM.

```
p2 (apresentação, direto)          p5 (fechamento, direto)
  └─ _booking_signal_block=""        └─ orientacao configurada pelo utilizador
     (nunca mais injectado)             → agora chega ao prompt (antes: descartada)
```

---

## Plano de Implementação

Duas fases independentes, cada uma com 1 commit.

### Fase 1 — Remover a instrução de agendamento do Closer (p2)

**Objetivo:** o Closer (`direto`) para de receber a instrução hardcoded de
"perguntar dia/horário" na apresentação.

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `372446c` | Remove `_booking_signal_block` hardcoded para `direto`; testes atualizados; doc atualizada |

**Detalhes do commit `372446c`:**
- `backend-executors/app/services/decision_engine.py` — `_build_child_prompt_apresentation`: novo `elif agent_mode_normalized == "direto":` força `_booking_signal_block = ""` sempre; comentário acima atualizado.
- `backend-executors/tests/test_sales_flow_intent_trigger_phase_entry.py` — `test_booking_signal_not_migrated_for_direto_mode` (que documentava o bug) substituído por `test_booking_signal_never_injected_for_direto_mode_with_sales_flow` e `test_booking_signal_never_injected_for_direto_mode_without_sales_flow`.
- `docs/architecture/sales-flow.md` — seção "Flag especial de bloco: `booking_signal_opener`" atualizada.

### Relatório da Fase 1 — o que mudou na prática

**Antes:** o agente Closer (fechamento direto) recebia sempre uma instrução interna dizendo para "perguntar o dia e horário preferencial" sempre que o lead escolhia um serviço ou perguntava sobre horários — mesmo esse agente sendo configurado para fechar a venda diretamente (confirmar ou enviar link de pagamento), nunca para agendar.

**Agora:** essa instrução deixou de ser enviada para o Closer em qualquer situação. O Closer segue apenas as regras de fechamento (confirmar/enviar link), sem a contradição interna.

**Para validar:** Cenários P1 e P2, na seção "Checks de Validação" abaixo (testes automatizados já rodados e passando — ver commit `372446c`).

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/decision_engine.py` | Em `_build_child_prompt_apresentation` (~linha 3391), estender o `if agent_mode_normalized == "agenda":` para também tratar `"direto"`: quando `agent_mode_normalized == "direto"`, `_booking_signal_block = ""` sempre (sem bloco editável equivalente). |
| `backend-executors/app/services/decision_engine.py` | Atualizar o comentário acima de `_booking_signal_block` (linhas 3379-3383) — já não é "fora de escopo para direto". |
| `backend-executors/tests/test_sales_flow_intent_trigger_phase_entry.py` | Reescrever `test_booking_signal_not_migrated_for_direto_mode` — hoje afirma (bug) que o marker permanece para `direto`; passa a afirmar que o marker está ausente, independente de `sales_flow` configurado ou não. |
| `docs/architecture/sales-flow.md` | Seção "Flag especial de bloco: `booking_signal_opener`": para `direto` o texto nunca é injectado (nem hardcoded, nem editável); `consultivo` continua fora de escopo (ver `docs/plans/fluxo-vendas-melhorias-futuras.md`, item M1). |

### Fase 2 — Ligar blocos de `orientacao` da fase p5 (Fechamento) ao prompt de closing

**Objetivo:** instruções configuradas na fase "Fechamento" do builder (ex.:
"envie o link de pagamento só depois de confirmar o serviço") passam a chegar de
facto à LLM filha de closing — hoje são aceitas na UI mas descartadas no
backend, para todos os agent_modes.

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/decision_engine.py` | `_build_child_prompt_closing()` ganha parâmetro `is_phase_entry: bool = True` (mesmo padrão de `_build_child_prompt_apresentation`/`_build_child_prompt_recepcao`). Antes do `return`, adiciona `_closing_prompt += _build_sales_flow_phases_block(_evaluate_sales_flow_phases(context, "closing", message_text, detected_intents=mother_decision.detected_intents, is_phase_entry=is_phase_entry, branch_selections=mother_decision.branch_selections))`. |
| `backend-executors/app/services/decision_engine.py` | No call site (`route_for_child == "closing"`), passar `is_phase_entry=_is_phase_entry_for_prompt` (variável já calculada, reaproveitada pelos outros builders). |
| `backend-executors/tests/test_sales_flow_intent_trigger_phase_entry.py` | Novo teste: contexto com bloco `orientacao` em `p5` com `content` customizado → `_build_child_prompt_closing(...)` deve incluir esse texto no prompt. |
| `docs/architecture/sales-flow.md` | Deixar explícito que `p5` também injecta `orientacao` como `prompt_injections` no prompt de closing (mesmo mecanismo das outras fases). |

---

## Checks de Validação

### Cenário P1 — Closer sem Fluxo de Venda configurado
- [x] Gerar prompt de apresentação para `agent_mode="direto"`, sem `sales_flow`
- [x] Confirmar: `"RECONHECIMENTO DE INTERESSE DE AGENDAMENTO"` NÃO aparece no prompt
- **Validado em:** 24/08/2026 — via teste automatizado `test_booking_signal_never_injected_for_direto_mode_without_sales_flow` (commit `372446c`)

### Cenário P2 — Closer com Fluxo de Venda configurado (p2 com blocos)
- [x] Gerar prompt de apresentação para `agent_mode="direto"`, com `sales_flow` configurado em p2
- [x] Confirmar: mesmo resultado — marker ausente
- **Validado em:** 24/08/2026 — via teste automatizado `test_booking_signal_never_injected_for_direto_mode_with_sales_flow` (commit `372446c`)

### Cenário P3 — Bloco de orientação em p5 chega ao prompt de closing
- [ ] Configurar bloco `orientacao` em p5 com conteúdo customizado (ex.: sobre envio de link de pagamento)
- [ ] Gerar prompt de closing
- [ ] Confirmar: o conteúdo do bloco aparece no prompt

### Cenário P4 — p5 sem blocos configurados (regressão zero)
- [ ] Gerar prompt de closing sem nenhum bloco em p5
- [ ] Confirmar: prompt idêntico ao comportamento anterior (sem alterações)

### Cenário — Suíte completa
- [ ] Rodar `pytest` em `backend-executors/tests/` — suíte completa passa, incluindo os testes de `agenda`/`consultivo` já existentes (garantir zero regressão)
