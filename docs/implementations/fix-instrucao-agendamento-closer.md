# Fix: instrução de agendamento vazando para o agente "Fechamento Direto" (Closer)

**Branch:** `<a definir no Plan Mode>`
**Status:** Aguardando Plan Mode

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

A definir em Plan Mode. Hipótese inicial (não validada): aplicar o mesmo padrão já
construído na Fase 4 (bloco `booking_signal_opener`, banner/card no builder) também
para `agent_mode_normalized == "direto"` — permitindo ao utilizador editar/remover
essa instrução como já pode fazer para `agenda`. Alternativa a considerar no
diagnóstico: para `direto`, pode fazer mais sentido **remover** a instrução por
completo (sem oferecer um bloco equivalente), já que "perguntar disponibilidade"
nunca é o comportamento correcto para um Closer — precisa de decisão do utilizador
sobre qual das duas abordagens prefere.

---

## Plano de Implementação

A preencher após o diagnóstico em Plan Mode (Passo 0 de
`_guia-documentar-implementacao.md`) ser aprovado pelo utilizador.

**Arquivos prováveis:**
- `backend-executors/app/services/decision_engine.py` — `_build_child_prompt_apresentation`
- `frontend-crm/src/components/agente/CamadaFluxoVenda.tsx` — se optar por reaproveitar `OpenerBanner`/`OpenerCard` também para `direto`
- `backend-executors/tests/test_sales_flow_intent_trigger_phase_entry.py`
- `docs/architecture/sales-flow.md` — secção "Flag especial de bloco: `booking_signal_opener`"

---

## Checks de Validação

A preencher após o Plano de Implementação ser definido.
