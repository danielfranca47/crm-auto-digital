# Fix: IA não reconhece pedido natural de reagendamento como reagendamento

**Branch:** `fix/deteccao-intencao-reagendamento-ia`
**Status:** Em andamento

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de `fix-confirm-exact-agenda-vazia.md`
(Cenário P2, Fase 2) e foi reforçado por um achado equivalente registado em
`docs/plans/cancelamento-reagendamento-melhorias-futuras.md` (M1–M5, área correlata).

Durante a validação manual (Playground), depois de confirmar um horário, um pedido de
reagendamento em linguagem natural — "pode ser às 16h em vez de 14h?" — não disparou
`PUT /api/internal/appointments/{id}` (rota interna já implementada e testada, ver
`docs/architecture/agenda.md`, secção "Rotas internas para o backend-executors"). O trace
mostrou confiança 0% para o sinal de reagendamento; a IA respondeu como se fosse uma nova
confirmação de horário, em vez de reconhecer o compromisso já existente e reagendá-lo.

**Comportamento actual:** `meeting_reschedule_requested` + `meeting_datetime_candidate`
válido é o par de sinais que `handle_meeting_cancel_or_reschedule()`
(`backend-executors/app/services/meeting_scheduler.py`) espera para agir — ver
`docs/architecture/agenda.md`, secção "Cancelamento e reagendamento via IA". O gap está em
quando/como a Mãe ou a filha de agendamento decide emitir `meeting_reschedule_requested`
diante de uma frase que não usa palavras explícitas de reagendar ("remarcar", "mudar o
horário"), mas ainda assim implica isso pelo contexto (já existe reunião confirmada, o lead
propõe outro horário).

**Comportamento desejado:** frases que impliquem reagendamento dentro da janela pós-
confirmação (`bot_disabled_reason="meeting_scheduled"`) devem ser reconhecidas mesmo sem
palavra-chave explícita.

---

## Problemas Identificados (estado anterior)

1. **Prompt sem regra para reagendamento implícito (só horário, sem dia):**
   `_build_child_prompt_meeting_management()`
   (`backend-executors/app/services/decision_engine.py:3628-3699`) — não passa por
   nenhum pré-filtro de palavra-chave; toda a detecção é feita pelo LLM a partir das
   regras do prompt. Hoje o prompt só ensina **um** padrão de reagendamento (linha
   3666-3672): "dia E horário juntos" (ex.: *"pode ser domingo às 11h?"*). Não existe
   nenhuma regra para o caso de o lead só corrigir o horário sem repetir o dia — esse
   tipo de frase cai no bucket genérico "qualquer outra mensagem" (linha 3676-3678),
   que exige explicitamente que nenhum sinal seja preenchido. Confirmado com o pedido
   real que motivou este arquivo: "pode ser às 16h em vez de 14h?" (sem dia, sem
   palavra "remarcar") — o LLM não preencheu `meeting_reschedule_requested`.

2. **Dado necessário já disponível, só falta a instrução:** o bloco "REUNIÃO/SESSÃO JÁ
   CONFIRMADA" (`_meeting_block`, construído a partir de `_format_busy_slots_block`,
   linha 3646-3654) já inclui a data e hora exactas do compromisso confirmado — não é
   um problema de dado ausente.

---

## Abordagem

Adicionar uma nova regra + exemplo ao prompt de
`_build_child_prompt_meeting_management()`, entre a regra de "dia E horário" e a de
"sem horário novo": quando a mensagem propuser só um horário diferente do já
confirmado, sem mencionar um novo dia, tratar como reagendamento para o **mesmo dia**
da reunião já confirmada — preencher `meeting_reschedule_requested=true` e
`meeting_datetime_candidate` combinando a data já conhecida (bloco acima) com o novo
horário mencionado.

`handle_meeting_cancel_or_reschedule()` e `_extract_cancel_reschedule_signal()`
(`backend-executors/app/services/meeting_scheduler.py`) já fazem o que deveriam com
esses sinais — sem mudança necessária aí, nem em `orchestrator_models.py`/rotas. Fix
cirúrgico, só no prompt.

---

## Plano de Implementação

### Fase 1 — Nova regra de reagendamento implícito no prompt

**Objetivo:** o LLM passa a reconhecer um pedido de troca de horário sem dia
explícito como reagendamento do compromisso já confirmado, no mesmo dia.

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/decision_engine.py` | `_build_child_prompt_meeting_management()` (~linha 3662-3678): nova regra + exemplo para reagendamento implícito (só horário, mesmo dia); reforça a regra existente deixando explícito que ela cobre o caso de um **novo dia** ser mencionado |
| `backend-executors/tests/test_meeting_management.py` | Estende `test_prompt_includes_meeting_management_instructions` (ou nova asserção) verificando a nova regra no prompt; novo teste `test_decide_post_meeting_management_detects_implicit_same_day_reschedule` (LLM mockado, mesmo padrão dos testes existentes) |

---

## Checks de Validação

### Cenário C1 — Testes automatizados (pytest)
- [x] `pytest backend-executors/tests/test_meeting_management.py` passa, incluindo os
  novos/estendidos — 04/08/2026 (9 testes, incluindo o novo
  `test_decide_post_meeting_management_detects_implicit_same_day_reschedule` e a
  asserção estendida de `test_prompt_includes_meeting_management_instructions`).
  `test_meeting_cancel_reschedule_action.py` também roda junto sem regressão (15
  testes no total).

### Cenário P1 — Playground, reagendamento implícito (só horário, mesmo dia)
- [ ] Confirmar uma reunião num horário (ex.: 14h) no Playground.
- [ ] Enviar "pode ser às 16h em vez de 14h?".
- [ ] Confirmar: bot confirma o reagendamento diretamente (não pergunta "qual dia?"),
  trace mostra `meeting_reschedule_requested=true` e `meeting_datetime_candidate`
  válido no mesmo dia às 16h, `PUT /api/internal/appointments/{id}` disparado com o
  novo horário.

### Regressão — Reagendamento explícito com novo dia continua a funcionar
- [ ] "pode ser domingo às 11h?" — confirma directamente, sem regressão.

### Regressão — Cancelamento continua a funcionar
- [ ] "quero cancelar" — cancela directamente, sem regressão.

### Regressão — Mensagem neutra continua sem preencher sinais
- [ ] "muito obrigada!" — resposta mínima, sem `meeting_reschedule_requested`/
  `meeting_cancel_requested`.
