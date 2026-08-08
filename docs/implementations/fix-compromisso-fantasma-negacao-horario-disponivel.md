# Compromisso fantasma + negação incorreta de horário disponível (Agendamento)

**Status:** Aguardando Plan Mode
**Origem:** achado durante reteste do Cenário 1 de `docs/implementations/sessao-teste-corrente.md`

---

## Motivação

Ao retestar o Cenário 1 (contradição entre bolhas ao perguntar horário) com
`scheduling_offer_style=offer_alternatives` — a pedido do utilizador, para verificar se o bot
nega incorretamente um segundo horário diferente do que ele mesmo ofereceu, mesmo quando esse
horário está genuinamente disponível — o comportamento temido foi reproduzido, e revelou um
segundo problema mais grave na mesma rodada: um compromisso real é criado na agenda com uma
data/hora que não tem relação nenhuma com o que foi conversado, mesmo quando a resposta enviada
ao lead foi uma **negação** (não uma confirmação).

**Decisão do utilizador:** registrar o achado e não investigar/corrigir agora — este arquivo é
o ponto de partida para quando o assunto for retomado.

---

## Problemas Identificados

### Achado A — Negação de horário genuinamente disponível numa negociação de 2 turnos

Depois de o bot já ter oferecido alternativas num turno anterior, ao lead propor um terceiro
horário diferente (não pedido originalmente, não um dos ofertados), o bot pode negá-lo mesmo
sem nenhum conflito real na agenda.

### Achado B — Compromisso fantasma: `appointment_event` criado com data/hora sem relação com a conversa

Na mesma rodada que reproduziu o Achado A, o sistema criou um evento de agendamento
(`appointment_event.action="created"`) com `start_at` correspondente a **outro dia** (9 de
agosto, quando a conversa toda era sobre dia 13) e um horário com precisão de segundos batendo
com o instante real da chamada — sinal de um fallback tipo "agora", não uma data extraída da
conversa. Isso aconteceu **apesar de a mensagem enviada ao lead ter sido uma negação** ("o
horário das 13h está ocupado, posso oferecer 15h ou 16h?") — ou seja, o paciente recebe um
"não", mas o sistema registra um compromisso mesmo assim, na data errada.

---

## Evidência (reproduzida ao vivo, ambiente local, 08/08/2026)

**Setup:** `ai_profile.id=5` (conta `autodigital157@gmail.com`, ver
`docs/implementations/_conta-teste-local.md`), `scheduling_offer_style` alterado manualmente
para `offer_alternatives` para este teste (era `confirm_exact`) — **a conta continua nessa
configuração, não foi revertida.** Agenda real da conta: vazia (confirmado via
`POST /api/playground/chat`, bloco `HORÁRIOS JÁ OCUPADOS: nenhum compromisso encontrado`).

**Turno 1** (5 sessões novas, `lead_id=null` cada): *"Oi, queria saber se tem horário quinta às
15h"*
**Turno 2** (mesmo `lead_id` do turno 1): *"Prefiro às 13h então, pode ser?"*

| # | lead_id | Turno 2 — resposta ao lead | `appointment_event` criado |
|---|---|---|---|
| 1 | 415 | ✅ "A quinta-feira às 13h está confirmada!" | `start_at=2026-08-13T16:00:00Z` (13h local, correto) |
| 2 | 416 | ❌ "No dia 13/08, o horário das 13h está ocupado. Posso te oferecer opções às 15h ou às 16h." | ⚠️ `start_at=2026-08-09T03:50:29Z` — **dia errado, hora batendo com "agora"** |
| 3 | 417 | ✅ "Temos a disponibilidade às 13h. Podemos confirmar?" | Nenhum (`null`) |
| 4 | 418 | ✅ "Às 13h, o Digital Pro tem disponibilidade." | Nenhum (`null`) |
| 5 | 419 | ✅ "Está disponível! Posso agendar esse horário." | Nenhum (`null`) |

**Trecho relevante da rodada 2 (lead 416), turno 2 — JSON bruto:**
```json
{
  "message_to_send": "No dia 13/08, o horário das 13h está ocupado. Posso te oferecer opções às 15h ou às 16h. Algum desses funciona para você?",
  "mother_decision": { "signals": { "meeting_scheduled": true, ... } },
  "child_result": { "signals_structured": { "meeting_datetime_candidate": null, ... } },
  "appointment_event": { "action": "created", "start_at": "2026-08-09T03:50:29Z", "end_at": "2026-08-09T04:50:29Z" }
}
```

Comparar com a rodada 1 (confirmação correta), mesmo turno: `meeting_datetime_candidate:
"2026-08-13T13:00:00"` → `appointment_event.start_at: "2026-08-13T16:00:00Z"` (13h local convertido
para UTC corretamente).

---

## Hipótese de causa raiz (preliminar — não aprofundada, ponto de partida para o Plan Mode)

`backend-executors/app/services/meeting_scheduler.py`, função `_extract_meeting_signal()`:

1. **Linhas 73-78:** `meeting_scheduled` é lido do sinal da **Mãe**
   (`decision_trace["meeting_scheduled"]`, dual-read documentado em
   `docs/architecture/llm-architecture.md`) — decidido a partir da leitura que a Mãe faz da
   mensagem do lead, **antes** de a Filha de agendamento checar a agenda real e gerar a
   resposta final. Na rodada 2, a Mãe interpretou "Prefiro às 13h então, pode ser?" como sinal
   de confirmação (`meeting_scheduled=true`) — mas a Filha, com acesso à agenda real, acabou
   negando o horário. O sinal da Mãe não é corrigido/descartado quando a Filha diverge.
2. **Linhas 83-103:** quando `meeting_scheduled=true`, o código tenta obter a data/hora do
   `meeting_datetime_candidate` estruturado da **Filha**. Na rodada 2 esse campo veio `null`
   (esperado — a Filha negou o horário, não tinha motivo para extrair uma data confirmada).
   Como fallback, chama `extract_start_at(metadata, history, ...)` (heurística de extração por
   texto sobre o histórico da conversa) — que, neste caso, parece ter retornado algo próximo de
   "agora" em vez de nenhuma data válida ou de recusar o fallback.

**Não investigado ainda:** o comportamento interno de `extract_start_at()` (linha 354 do mesmo
arquivo) — por que produziu especificamente `2026-08-09` (dia errado) com precisão de segundos
batendo com o instante da chamada, em vez de retornar `None`/falhar de forma segura.

**Achado A (negação incorreta) provavelmente compartilha causa com o mesmo fenômeno** — a
Filha de agendamento, ao gerar a resposta de texto, tem uma taxa de erro não-determinística ao
verificar um horário contra uma agenda vazia (mesma classe de variância estocástica já discutida
para o Cenário 1 original) — mas isso não foi confirmado em código, só observado no comportamento.

---

## Estado deixado para trás (importante para retomar)

- `ai_profile.id=5` (conta de teste) está com `scheduling_offer_style=offer_alternatives`.
  Era `confirm_exact` antes deste teste. **Não foi revertido.**
- Nenhuma alteração de código foi feita — só investigação/leitura.
- 1 compromisso fantasma (`lead_id=416`, sandbox) pode ter sido gravado na tabela `appointments`
  do ambiente local, com data 2026-08-09 — irrelevante em produção (é dado de teste local), mas
  vale limpar se for mexer nessa área depois.

---

## Ajustes Possíveis Pós-Implementação

- Considerar não confiar cegamente no sinal `meeting_scheduled` da Mãe para criar o
  `appointment_event` — cruzar com o resultado real da Filha (ex.: só criar se o
  `meeting_datetime_candidate` estruturado da Filha for válido; se vier `null`, não cair no
  fallback heurístico de texto, ou pelo menos não aceitar um resultado tão próximo de "agora"
  sem confiança razoável).
- Investigar `extract_start_at()` isoladamente com o histórico exato desta rodada para entender
  a causa do "quase agora".
- Reavaliar Achado A (negação incorreta) junto — pode precisar de mais rodadas de teste para
  confirmar taxa de reincidência antes de decidir se vale ajuste de prompt.
