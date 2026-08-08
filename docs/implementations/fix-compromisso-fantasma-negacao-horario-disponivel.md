# Compromisso fantasma + negação incorreta de horário disponível (Agendamento)

**Branch:** `fix/handoff-silencio-primeira-mensagem`
**Status:** Em andamento
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

## Causa raiz (confirmada com reprodução directa)

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
   (esperado — a Filha negou o horário). O bug: `candidate_str=None` cai no **mesmo** `else` que
   trata candidato inválido/passado — ambos disparam o fallback heurístico `extract_start_at()`,
   que tenta adivinhar uma data varrendo o texto cru da conversa com a biblioteca `dateparser`.
3. **Confirmado por reprodução directa:** chamando `dateparser.search_dates("Prefiro às 13h
   então, pode ser?", ...)` com as mesmas configurações do código (sem nenhuma âncora de dia na
   frase — sem "hoje"/"amanhã"/dia da semana/data explícita), o `dateparser` interpreta "13h"
   como um **deslocamento de 13 horas a partir de agora** (duração), não como "13:00" (hora do
   relógio). Resultado: `now + 13h`, cruzando a meia-noite UTC — batendo quase ao segundo com a
   data/hora bugada observada (`2026-08-09T03:50:xxZ`).
4. Como `signal.start_at` acaba preenchido (embora errado), o guard existente em
   `handle_meeting_scheduled()` (linha 732, `if not signal.start_at: ... return None`) não
   protege este caso — só existe hoje para quando **nenhum** valor é encontrado, não para um
   valor implausível. O gate M3 (`is_phase_entry`, linha 717) também não cobre — só protege a
   *primeira* mensagem do lead numa fase; aqui o lead já estava em "agendamento" desde o turno
   anterior.

**Achado A (negação incorreta) permanece fora de escopo** — é variância do texto gerado pela
Filha ao verificar disponibilidade, sem causa determinística de código identificada (mesma
classe dos achados de qualidade já discutidos para os Cenários 1 e 3 do roteiro de testes).

---

## Abordagem

Distinguir os dois motivos de `candidate_str` estar vazio, tratando-os de forma diferente —
mudança cirúrgica, sem tocar em `extract_start_at()`/`dateparser` nem no gate M3:

- **Candidato inválido ou no passado** (Filha tentou confirmar algo, mas o valor não presta) →
  comportamento actual mantido: cai no fallback heurístico. Já coberto por
  `test_extract_meeting_signal_invalid_candidate_falls_back` e
  `test_extract_meeting_signal_past_candidate_falls_back`.
- **Candidato ausente/`null`** (Filha não confirmou nada) → **não** cai mais no fallback
  heurístico. `start_at` fica `None`, e o guard já existente em `handle_meeting_scheduled()`
  (`reason="missing_start_at"`) cuida de não criar nada — código já existe, só passa a ser
  alcançado neste caso.

```
meeting_scheduled=true (sinal da Mãe)
  candidato da Filha:
    ├─ válido e futuro               → usa direto (inalterado)
    ├─ presente mas inválido/passado → fallback extract_start_at() (inalterado)
    └─ ausente (null)                → ANTES: também caía no fallback (raiz do bug)
                                        DEPOIS: start_at=None → handle_meeting_scheduled() já
                                        recusa criar (reason=missing_start_at)
```

---

## Plano de Implementação

### Fase 1 — Não usar fallback heurístico quando a Filha não fornece candidato nenhum

**Objetivo:** parar de criar compromissos fantasma quando a Filha nega/não confirma um horário

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/meeting_scheduler.py` | `_extract_meeting_signal()`, troca o `else` genérico por `elif candidate_str:` — só cai no fallback quando há valor não-vazio |
| `backend-executors/tests/test_meeting_scheduler_structured_candidate.py` | Novo teste: candidato `None`, confirma que `extract_start_at` não é chamado e `signal.start_at is None` |
| `backend-executors/tests/test_meeting_scheduled_events.py` | Novo teste: `handle_meeting_scheduled()` com candidato `None` não cria nenhum compromisso |
| `docs/architecture/llm-architecture.md` | Esclarece que o fallback heurístico só roda para candidato inválido/passado, nunca para candidato ausente |

```python
# ANTES
if start_at is not None:
    ...
else:
    if candidate_str:
        ...warning candidate_invalid...
    ...fallback_extract_start_at...
    start_at = extract_start_at(...)

# DEPOIS
if start_at is not None:
    ...
elif candidate_str:
    ...warning candidate_invalid...
    ...fallback_extract_start_at...
    start_at = extract_start_at(...)
else:
    ...log source=none_child_no_candidate...
    # start_at permanece None
```

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `49a23e3` | Distingue candidato ausente de inválido/passado; não cria compromisso quando ausente + 2 testes + doc |

**Detalhes do commit `49a23e3`:**
- `backend-executors/app/services/meeting_scheduler.py` — `_extract_meeting_signal()`: `else` genérico vira `elif candidate_str:`; novo `else` final loga e deixa `start_at=None`
- `backend-executors/tests/test_meeting_scheduler_structured_candidate.py` — `test_extract_meeting_signal_missing_candidate_does_not_fallback`
- `backend-executors/tests/test_meeting_scheduled_events.py` — `test_handle_meeting_scheduled_no_candidate_creates_nothing`
- `docs/architecture/llm-architecture.md` — secção "Filha Agendamento" esclarecida

### Relatório da Fase 1 — o que mudou na prática

**Antes:** quando a IA negava um horário ao lead (não confirmava nada), o sistema podia mesmo
assim criar um compromisso real na agenda, com uma data/hora inventada sem relação com a
conversa — um "compromisso fantasma".

**Agora:** quando a IA nega/não confirma um horário, nenhum compromisso é criado. O sistema só
tenta recuperar uma data por conta própria (heurística de texto) quando a IA *tentou* confirmar
algo mas o valor veio malformado ou já expirado — nunca quando ela simplesmente não confirmou
nada.

**Para validar:** Cenário T1 (testes automatizados) — ver checks abaixo, já rodados e
validados nesta sessão. Cenário P1 (fumaça manual no Playground) é opcional — a causa raiz foi
reproduzida de forma 100% determinística (diferente de achados de variância de LLM), então os
testes automatizados já dão confiança alta sem precisar do teste ao vivo.

---

## Checks de Validação

### Cenário T1 — Testes automatizados (pytest)
- [x] `pytest backend-executors/tests/test_meeting_scheduler_structured_candidate.py` — 7/7 passou
- [x] `pytest backend-executors/tests/test_meeting_scheduled_events.py` — 3/3 passou
- [x] Suíte completa `pytest backend-executors/tests/` — mesmos 22 testes pré-existentes
  falhando (não relacionados, confirmados antes desta sessão via `git stash`), 110 passando
  (108 + 2 novos), zero regressão
- **Validado em:** 08/08/2026

### Cenário P1 — Fumaça manual no Playground (opcional)
- [ ] Repetir a sequência exata do Achado B (turno 1: horário quinta 15h; turno 2: "Prefiro às
  13h então, pode ser?", mesmo `lead_id`) e confirmar que nenhum `appointment_event` é criado
  mesmo que a Filha negue de novo (Achado A é variância aceita, fora de escopo)

---

## Estado da conta de teste

- `ai_profile.id=5` (conta de teste) está com `scheduling_offer_style=offer_alternatives`.
  Era `confirm_exact` antes do reteste do Cenário 1. **Não foi revertido.**
- 1 compromisso fantasma (`lead_id=416`, sandbox) foi gravado na tabela `appointments` do
  ambiente local, com data 2026-08-09 — irrelevante em produção (é dado de teste local).

---

## Ajustes Possíveis Pós-Implementação

- Achado A (negação incorreta de horário genuinamente disponível) permanece sem causa
  determinística de código — pode precisar de mais rodadas de teste para confirmar taxa de
  reincidência antes de decidir se vale ajuste de prompt.
