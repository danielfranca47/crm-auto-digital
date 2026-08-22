# Guardrail de gatilhos pendentes para p3b (Agendamento) e p4 (Follow-up)

**Branch:** `feat-fluxo-vendas-ramificacao`
**Status:** Aguardando Plan Mode

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`docs/implementations/sales-flow-fase-pendente-guardrail.md` (feature que deu a p1, p2 e p3a
um guardrail de "gatilhos sequenciais pendentes bloqueiam avanço automático de fase").

p3b (Agendamento → follow-up/client-list) e p4 (Follow-up → closing) ficaram fora do escopo
porque, ao contrário de p2/p3a, **não têm nenhum atalho `*_complete_auto_advance`** hoje —
só o `route_to` bruto da Mãe, clampado por `_ALLOWED_ADVANCE`. Isso reduz a superfície (só
precisaria de um novo `_enforce_*_sales_flow_pending` ao nível da Mãe, sem o segundo gate que
p2/p3a precisaram), mas p4/Follow-up tem uma complicação própria: interage com o subsistema
separado `services/followup_state.py`/`services/followup_reconciler.py` (ticks agendados via
job `whatsapp.followup.tick`, não só turnos ao vivo de conversa) — precisa de investigação
dedicada para confirmar que um guardrail de "gatilhos pendentes" não conflita com esse
mecanismo antes de aplicar a mesma receita usada em p1/p2/p3a.

---

## Diagnóstico (a fazer em Plan Mode)

Este arquivo nasce sem plano — o Passo 0 (`_guia-documentar-implementacao.md`) ainda não foi
feito. Pontos a investigar quando essa sessão começar:

1. **Já existe?** Não para p3b/p4 — confirmado durante a investigação da feature-mãe.
2. **O que precisa ser construído:**
   - `_enforce_agendamento_sales_flow_pending()` (mesmo padrão de
     `_enforce_pre_agendamento_sales_flow_pending`, trocando p3a→p3b e
     `_ALLOWED_ADVANCE["agendamento"]`), adicionado à cadeia de `decide()`.
   - `_enforce_followup_sales_flow_pending()` para p4 — mas primeiro ler
     `services/followup_state.py`/`services/followup_reconciler.py` e `docs/architecture/followup.md`
     para entender como o job `whatsapp.followup.tick` decide sair de follow-up hoje, e se esse
     caminho passa por `decide()`/`_ALLOWED_ADVANCE` da mesma forma que turnos ao vivo.
3. **Riscos:** confirmar que nenhum dos dois novos guardrails interfere com
   `_is_followup_tick_context()`/`force_followup_route` (que já força `route_for_child =
   "follow-up"` incondicionalmente em `decide()`, ANTES dos guardrails de gatilhos pendentes
   rodarem) — pode ser preciso decidir explicitamente se o guardrail de p4 deve ou não se
   aplicar durante um tick agendado.

---

## Arquivos prováveis

- `backend-executors/app/services/decision_engine.py` — dois novos `_enforce_*_sales_flow_pending`.
- `backend-executors/app/services/followup_state.py` / `followup_reconciler.py` — só leitura,
  para entender a interação antes de decidir se precisam de mudança.
- Testes novos espelhando `test_pre_agendamento_sales_flow_pending.py`.

---

## Checks de Validação

_A definir após o Plan Mode._

---

## Ajustes Possíveis Pós-Implementação

_A preencher na graduação._
