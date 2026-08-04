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

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `d872e75` | fix: reconhece pedido implicito de reagendamento (so horario, sem dia) |

### Relatório da Fase 1 — o que mudou na prática

**Antes:** depois de confirmar um horário, se o lead pedisse para trocar só a hora
sem mencionar um novo dia (ex.: "pode ser às 16h em vez de 14h?"), o bot não
reconhecia isso como um pedido de reagendamento — respondia de forma neutra, como se
fosse uma pergunta qualquer, e o compromisso real não era alterado.

**Agora:** o mesmo tipo de pedido é reconhecido como reagendamento para o mesmo dia
da reunião já confirmada — o bot confirma directamente e o compromisso é actualizado
com o novo horário. Reagendamento com um novo dia explícito, cancelamento e mensagens
neutras continuam a funcionar exactamente como antes (sem regressão nos testes
automatizados).

**Para validar:** Cenário C1 (já validado acima) e Cenário P1 + Regressões P2/P3/P4,
abaixo — estes últimos só podem ser confirmados com o LLM real (Playground), já que
todos os testes automatizados mockam a resposta do LLM.

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
- [x] Confirmar uma reunião num horário (ex.: 14h) no Playground — 04/08/2026.
- [x] Enviar "pode ser às 16h em vez de 14h?" — 04/08/2026.
- [x] Confirmar: bot confirma o reagendamento diretamente (não pergunta "qual dia?"),
  trace mostra `meeting_reschedule_requested=true` e `meeting_datetime_candidate`
  válido no mesmo dia às 16h, `PUT /api/internal/appointments/{id}` disparado com o
  novo horário — 04/08/2026 (`meeting_datetime_candidate: "2026-08-05T16:00:00"`;
  confirmado end-to-end: o appointment real criado pelo Playground (`id=66`, lead
  sandbox `397`) foi lido do banco **antes** — `start_at=2026-08-05T14:00:00` — e
  **depois** do turno — `start_at=2026-08-05T16:00:00` — sem nenhuma escrita manual
  no banco. Ver nota de setup abaixo.

### Regressão — Reagendamento explícito com novo dia continua a funcionar
- [x] "pode ser domingo às 11h?" — confirma directamente, sem regressão — 04/08/2026
  (`meeting_reschedule_requested=true`, `meeting_datetime_candidate:
  "2026-08-09T11:00:00"`, próximo domingo a partir de 04/08/2026 que é terça-feira;
  appointment real actualizado no banco para o mesmo horário).

### Regressão — Cancelamento continua a funcionar
- [x] "quero cancelar" — cancela directamente, sem regressão — 04/08/2026
  (`meeting_cancel_requested=true`; appointment real marcado `status='canceled'` no
  banco e `bot_disabled` revertido a `0` automaticamente).

### Regressão — Mensagem neutra continua sem preencher sinais
- [x] "muito obrigada!" — resposta mínima, sem `meeting_reschedule_requested`/
  `meeting_cancel_requested` — 04/08/2026 (ambos os sinais `false`; testado após
  reconfirmar uma nova reunião, já que o cancelamento do passo anterior tinha
  reativado o bot).

**Nota de setup (P1/P2/P3/P4) — correcção de diagnóstico:** a primeira tentativa de
validar estes 4 cenários usou o perfil "Agente Teste Handoff" com `agent_mode=
"consultivo"`. Como `meeting_scheduler.handle_meeting_scheduled()`
(`backend-executors/app/services/meeting_scheduler.py:707`) só cria appointment real e
desliga o bot quando `agent_mode == "agenda"`, essa combinação nunca activou o
mecanismo — levando à conclusão **errada** de que "o Playground nunca chega a
`bot_disabled_reason=meeting_scheduled`". Não é uma limitação do Playground: o
mecanismo já existe e é chamado em toda requisição
(`backend-executors/app/api/playground_internal.py` → `handle_meeting_scheduled(...,
is_playground=True)` + `handle_meeting_cancel_or_reschedule(...)`), documentado em
`docs/architecture/agenda.md`, secção "Playground cria appointments reais". Bastou
trocar temporariamente o `agent_mode` do perfil de teste para `"agenda"` (via UI,
`/ai-profile` → preset "Agente 03 · Híbrido") para os 4 cenários passarem a criar
appointment real e desligar o bot sozinhos, sem qualquer escrita manual no banco —
revertido para `"consultivo"` ao final via a própria API (`PUT /ai-profiles/me`).

---

## Ajustes Possíveis Pós-Implementação

- Durante a revalidação, o Playground não exibe nenhuma indicação visual distinta
  (ex.: um "system bubble" tipo o que já existe para mudança de categoria) quando um
  appointment real é criado, reagendado ou cancelado — a confirmação aparece só como
  texto normal do bot. Melhoria futura possível, fora do escopo desta fix.
