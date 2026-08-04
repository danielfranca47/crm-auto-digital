# Fix: IA não reconhece pedido natural de reagendamento como reagendamento

**Branch:** *(a definir ao iniciar)*
**Status:** Aguardando Plan Mode

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

1. **Sinal de reagendamento não detectado em frase implícita:** observado em teste manual
   real no Playground — não há ainda diagnóstico de qual prompt/filha decide esse sinal
   (`_decide_post_meeting_management()` em `decision_engine.py`, a confirmar em Plan Mode).

---

## Abordagem (rascunho — a confirmar em Plan Mode)

A confirmar: provavelmente ajustar a instrução do prompt de `_decide_post_meeting_management()`
para reconhecer padrões implícitos de reagendamento (proposta de horário alternativo dentro da
janela pós-confirmação, sem palavra-chave), talvez com exemplos few-shot adicionais.

---

## Plano de Implementação

*(a preencher em Plan Mode)*

---

## Checks de Validação

*(a preencher em Plan Mode)*
