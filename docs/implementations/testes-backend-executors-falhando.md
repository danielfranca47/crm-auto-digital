# Investigar 25 testes falhando em backend-executors/tests/

**Branch:** `feat-fluxo-vendas-ramificacao` (a definir na criação da worktree)
**Status:** Aguardando Plan Mode

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`docs/implementations/sales-flow-guardrail-fases-restantes.md`. Ao rodar a suíte completa
de `backend-executors/tests/` como Cenário T3 dessa implementação, 25 dos ~285 testes
falharam. Confirmado via `git stash` (isolando as mudanças da implementação e rodando a
suíte de novo) que as mesmas 25 falhas ocorrem **identicamente sem nenhum código daquela
feature presente** — são falhas pré-existentes, não uma regressão introduzida ali.

O usuário validou este item como urgente na triagem pós-graduação (Passo 5b) — uma suíte
com ~9% dos testes falhando é risco real para qualquer mudança futura em
`decision_engine.py` (impossibilita confiar em "suíte verde" como sinal de não-regressão).

---

## Diagnóstico (a fazer em Plan Mode)

Lista dos 25 testes falhando (capturada em 26/08/2026, antes de qualquer correção):

```
tests/test_followup_prompt_contract_context.py::test_followup_prompt_includes_contract_signals_and_variant_rule
tests/test_followup_tick_route_priority.py::test_followup_tick_forces_followup_child_route
tests/test_followup_tick_runner.py::test_followup_tick_job_uses_synthetic_in_reply_and_completes
tests/test_followup_tick_runner.py::test_followup_tick_job_fail_reports_retryable
tests/test_guardrails_by_mode.py::test_agenda_blocks_closing_without_booking_fields
tests/test_mother_qualification_route_guardrail.py::test_mother_route_forced_to_qualification_when_missing_fields
tests/test_mother_qualification_route_guardrail.py::test_mother_route_kept_when_qualification_is_complete
tests/test_phase2_direct_question_reply_priority.py::test_no_direct_question_qualifies_naturally
tests/test_qualification_contract.py::test_compute_missing_fields_consultivo_next_step_without_time_still_requires_availability
tests/test_qualification_contract.py::test_compute_missing_fields_agenda_requires_booking_fields
tests/test_qualification_contract.py::test_compute_missing_fields_direto_minimal
tests/test_qualification_state_loop.py::test_state_absent_extractor_upsert_then_final_source_is_state
tests/test_qualification_state_loop.py::test_anti_loop_triggers_handoff_after_two_attempts
tests/test_qualification_state_loop.py::test_t1_missing_fields_empty_never_ask_qualification
tests/test_qualification_state_loop.py::test_t3_rule3_blocks_return_to_qualification_when_already_apresentation
tests/test_qualification_state_loop.py::test_rule3_keyword_override_removed_falls_back_to_anti_loop
tests/test_qualification_state_loop.py::test_ask_qualification_message_is_deterministic_for_current_field
tests/test_qualification_state_loop.py::test_field_mismatch_repair_uses_second_attempt
tests/test_qualification_state_loop.py::test_anti_repetition_triggers_retry
tests/test_qualification_state_loop.py::test_current_field_recalculated_when_extractor_fills_previous_field
tests/test_qualification_state_loop.py::test_fallback_safe_when_repair_fails_twice
tests/test_qualification_state_loop.py::test_auto_promote_never_uses_qualification_fallback_message
tests/test_recepcao_pending_commercial_extraction.py::test_recepcao_prompt_instructs_pending_commercial_extraction
tests/test_recepcao_sales_flow_pending.py::test_p0_trigger_already_fired_advances_normally
tests/test_recepcao_sales_flow_pending.py::test_no_sequential_trigger_in_p0_behaves_like_baseline
```

Pontos a investigar quando o Plan Mode desta sessão começar:

1. **Padrão comum?** As falhas se concentram fortemente em qualificação
   (`test_qualification_*`), follow-up e p0/recepção — verificar se compartilham uma causa
   raiz única (ex.: uma assinatura de função mudou, um fixture/mock ficou desatualizado, um
   comportamento de `decide()` mudou numa implementação recente sem os testes serem
   atualizados junto) ou se são causas distintas por área.
2. **Desde quando falham?** Rodar a suíte em commits anteriores (`git log` +
   `git checkout <hash> -- backend-executors` ou `git stash`/`git bisect`) para identificar
   o commit que introduziu cada grupo de falhas — provavelmente não foi um único commit.
3. **É um bug de produção ou só de teste desatualizado?** Para cada falha, determinar se o
   comportamento atual do código está errado (bug real, o teste está certo) ou se o teste
   ficou defasado em relação a uma mudança de comportamento intencional (o teste está
   errado, precisa ser atualizado).
4. Dado o volume (25 testes, várias áreas), considerar dividir esta implementação em fases
   por área (ex.: Fase 1 — qualificação, Fase 2 — follow-up/recepção, Fase 3 — guardrails
   por modo) em vez de uma fase única.

---

## Arquivos prováveis

- `backend-executors/app/services/decision_engine.py` — provável causa raiz de várias
  falhas (motor de decisão central).
- `backend-executors/tests/test_qualification_*.py`, `test_followup_*.py`,
  `test_recepcao_*.py`, `test_guardrails_by_mode.py`,
  `test_mother_qualification_route_guardrail.py`,
  `test_phase2_direct_question_reply_priority.py` — os 25 testes falhando.

---

## Checks de Validação

_A definir após o Plan Mode._

---

## Ajustes Possíveis Pós-Implementação

_A preencher na graduação._
