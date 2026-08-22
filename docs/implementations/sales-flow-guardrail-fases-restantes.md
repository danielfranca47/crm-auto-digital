# Guardrail de gatilhos pendentes — fases restantes (p1, p3b, p4, p5, client-list)

**Branch:** `feat-fluxo-vendas-ramificacao`
**Status:** Aguardando Plan Mode

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`docs/implementations/sales-flow-guardrail-p0-recepcao.md` (feature que deu a p0 o mesmo
guardrail de "gatilhos sequenciais pendentes bloqueiam avanço automático de fase" já existente
para p2/p3a). O usuário pediu explicitamente uma auditoria de cobertura completa — todas as
fases em que o bot é responsável, não só as já corrigidas.

Escopo definido pelo usuário na sessão anterior: qualificação (p1), agendamento (p3b),
follow-up (p4), fechamento (p5) e lista de clientes (`client-list`). Fora de escopo, por
decisão do usuário: arquivados (`prospect-refused`) e desqualificados (`disqualified`) — não
são fases onde o bot está ativo. Observação dada pelo usuário: Agent 2 (`closer_agressivo`) não
passa por pré-agendamento nem agendamento (`_SCHEDULING_AGENT_TEMPLATES` só inclui
`sdr_padrao`/`hybrid_scheduler`), então p3b só se aplica a Agent 1/3.

---

## Diagnóstico (a fazer em Plan Mode)

Mapa de cobertura conhecido no momento em que este item foi aberto (ver
`docs/architecture/sales-flow.md`, secção "Guardrail de gatilhos pendentes bloqueia avanço
automático de fase" para o estado sempre atualizado):

- ✅ p0 (recepção) — `_enforce_recepcao_sales_flow_pending`
- ✅ p2 (apresentação) — `_enforce_apresentation_sales_flow_pending`
- ✅ p3a (pré-agendamento) — `_enforce_pre_agendamento_sales_flow_pending`, só Agent 1/3
- ⚠️ p1 (qualificação) — coberto só indiretamente: a saída de p1 é decidida por
  "missing_fields vazio" (não por `route_to` direto), em 3 pontos que já checam
  `_phase_pending_sequential_triggers("p1", ...)` — mas não foi auditado se a Mãe consegue
  rotear `route_to` direto para além de p1 por um caminho que não passe por esses 3 pontos
  (ex.: perfil sem nenhum campo de qualificação obrigatório configurado — ver achado ao vivo em
  `sales-flow-guardrail-p0-recepcao.md`, Cenário P2, onde a Mãe pulou de recepção direto para
  apresentação nessa condição).
- ❌ p3b (agendamento) — nenhum guardrail deste tipo existe hoje
- ❌ p4 (follow-up) — nenhum guardrail deste tipo existe hoje; interage com o subsistema
  separado de ticks agendados (`followup_state.py`/`followup_reconciler.py`) — investigar se o
  mesmo padrão de `_enforce_<fase>_sales_flow_pending` faz sentido aqui ou se precisa de
  desenho próprio
- ❌ p5 (fechamento) — nenhum guardrail deste tipo existe hoje; é a última fase do pipeline —
  avaliar se "pular p5" tem o mesmo sentido de risco que as demais (não há "fase seguinte" a
  proteger, mas pode haver risco de pular *para* p5 prematuramente sem os gatilhos de p5 terem
  disparado)
- ❓ `client-list` — não investigado se o bot mantém alguma conversa ativa/responsiva nessa
  categoria; se não, este item não se aplica a ela

Pontos a investigar quando o Plan Mode desta sessão começar:
1. Confirmar quais dessas fases têm de facto o bot respondendo ativamente (pré-requisito para o
   guardrail fazer sentido).
2. Para p1: decidir se um guardrail dedicado ao nível da Mãe é necessário, ou se reforçar os 3
   pontos existentes (Regra 1/3 anti-loop + fallback `ask_qualification`) resolve o gap sem
   nova função.
3. Para p4: como este guardrail (turno-a-turno) interage com o subsistema de ticks agendados —
   pode não fazer sentido da mesma forma.
4. Para p5: definir se existe um "próximo destino legítimo" a proteger, ou se o risco é
   diferente o suficiente para não precisar do mesmo padrão.
5. Padrão de implementação a reaproveitar: `_phase_pending_sequential_triggers()` (já genérico,
   reutilizável sem mudanças) + uma função `_enforce_<fase>_sales_flow_pending()` por fase que
   precisar, seguindo o mesmo molde de `_enforce_apresentation_sales_flow_pending`/
   `_enforce_pre_agendamento_sales_flow_pending`/`_enforce_recepcao_sales_flow_pending`.

---

## Arquivos prováveis

- `backend-executors/app/services/decision_engine.py` — novas funções `_enforce_<fase>_sales_flow_pending()` conforme decidido no Plan Mode.
- Testes novos espelhando `test_recepcao_sales_flow_pending.py`/`test_pre_agendamento_sales_flow_pending.py`.
- `docs/architecture/sales-flow.md` — atualizar mapa de cobertura ao graduar.

---

## Checks de Validação

_A definir após o Plan Mode._

---

## Ajustes Possíveis Pós-Implementação

_A preencher na graduação._
