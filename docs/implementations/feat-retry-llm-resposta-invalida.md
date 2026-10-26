# Repetir a chamada à IA antes de cair no handoff

**Branch:** `worktree-feat+retry-llm-resposta-invalida`
**Status:** Em andamento
**Autonomia:** manual
**Origem:** pedido do utilizador em 26/10/2026, durante `fix-saudacao-hora-local`: a mensagem de handoff
aparece "com uma certa frequência" quando a IA falha ou não responde.

---

## Motivação

Quando a chamada à IA falha, o executor usa `FALLBACK_DECISION` (`decision_engine.py`, `next_action="handoff"`,
`reason="llm_failure"`). O cliente recebe o texto de handoff (`handoff_custom_text` do perfil ou
`HANDOFF_TEMPLATES` em `handoff_policy.py`) e, com `handoff_policy=disable_bot`, o bot fica desligado para esse
lead. Uma falha passageira acaba assim com o atendimento automático.

O utilizador pediu: em caso de falha ou sem resposta, tentar de novo pelo menos 3 vezes antes de ativar o handoff.

---

## Medição (26/10/2026, antes de propor)

| Fonte | Período | Turnos | Falhas que viraram handoff | Tipo |
|---|---|---|---|---|
| `worker backend-executors` (WhatsApp real) | 21–26/10 (retenção da Railway) | ~0 (só polls) | 0 | — |
| Base CRM de produção (`jobs`, `prospection_logs`) | desde 14/08 | 36 inbound (último em 29/09) | 1 (`llm_failure`, agosto) | — |
| `backend-executors` API (**Playground**) | 25–26/10 | 355 no dia 26 | **4** (~0,85%) | **4/4 `ValidationError`** |

- 2× Mãe `mother_validate`: `route_to="apresentacao"` (fora do enum e fora de `_ROUTE_TO_ALIASES`).
- 2× Filha `child_validate`: `confidence` em falta.
- 1 `ReadTimeout` recuperou com o retry HTTP que já existia. Nenhum 4xx/5xx.

O que domina é a resposta inválida, e ela nunca era repetida. Quase todo o tráfego atual é Playground.

---

## Problemas Identificados (estado anterior)

1. **Resposta inválida não tinha nova tentativa:** JSON mal formado ou `ValidationError` subia direto ao
   `except` de `decide()` e virava handoff (`decision_engine.py`, bloco da Mãe e laço da Filha). Só a Filha
   `qualification` tinha uma 2.ª tentativa.
2. **Retry HTTP curto e sem teto de tempo:** `_post_with_retry` (`llm_service.py`) fazia só 2 tentativas, para
   rede/429/5xx; Mãe + Filha podiam somar ~80s sem limite total, mais do que os 60s com que o Playground espera.
3. **Handoff antecipado no worker:** com `disable_bot`, `handoff_policy.apply` (dentro de `decide()`) desliga o
   bot e regista o handoff já na 1.ª falha, antes de o runner reagendar o job (`runners/whatsapp.py`,
   `llm_failure_retry`). Se a nova tentativa do job der certo, o bot fica desligado na mesma. → Fase 2.

---

## Abordagem

```
decide()  (orçamento do turno: 40s)
  Mãe:   chamar → JSON → MotherDecision
           falhou (rede/timeout/429/5xx/JSON inválido/ValidationError)?
             → nova tentativa, até 4 no total, espera 1s/2s/4s
             → timeout da chamada = min(20s, tempo restante); não começa com < 5s
           400/401/403/422 ou erro de código → não repete
  Filha: o mesmo laço, só sobre a Filha (a Mãe validada não é refeita)
  Esgotou → FALLBACK_DECISION → handoff (como antes)
```

- Um contador por etapa: Mãe/Filha chamam `_post_with_retry(max_attempts=1)`, para não multiplicar 2×4 chamadas.
- O mesmo prompt em cada tentativa. Não se mexe nas instruções da IA.
- Alias `apresentacao`/`apresentação` → `apresentation`: elimina metade das falhas medidas sem gastar tentativa.
- **Desvio do plano aprovado:** o plano dizia "não começar tentativa se o tempo restante for menor que o timeout
  de uma chamada" (20s). Isso tirava a 2.ª tentativa a um timeout logo na 1.ª chamada (o caso que recuperou nos
  logs). Em vez disso, o timeout de cada chamada passa a ser o tempo que resta, com um mínimo de 5s.

---

## Plano de Implementação

### Fase 1 — Novas tentativas por etapa (Mãe/Filha) com orçamento de tempo

**Objetivo:** até 4 tentativas por etapa, incluindo resposta inválida, sem passar 40s por turno.

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/llm_service.py` | `_post_with_retry`/`_generate_json`/`generate_mother_route`/`generate_child_result` aceitam `max_attempts` e `timeout_seconds`; `is_retryable_http_error()` |
| `backend-executors/app/services/decision_engine.py` | `_run_llm_stage()`, `_llm_stage_failure_reason()`, `_InvalidLlmJson`, `LLM_STAGE_MAX_ATTEMPTS=4`; a Mãe e cada chamada da Filha passam pelo helper |
| `backend-executors/app/core/config.py` | `llm_decision_budget_seconds = 40` |
| `backend-executors/app/services/orchestrator_models.py` | aliases `apresentacao`/`apresentação` |
| `backend-executors/tests/test_llm_stage_retry.py` | novo: 1/2/3/4 falhas na Mãe e na Filha, tipos misturados, 400, orçamento, logs, alias |
| `backend-executors/tests/test_llm_service_retry.py` | `max_attempts=1`, `timeout_seconds`, `is_retryable_http_error` |
| `backend-executors/tests/test_response_creativity_temperature.py` | o mock de `_post_with_retry` aceita os kwargs novos |
| `docs/architecture/llm-architecture.md` | secção "Falhas da IA e novas tentativas (Mãe/Filha)" |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `c376664` | Novas tentativas por etapa com orçamento de tempo, alias `apresentacao`, testes e doc |

### Relatório da Fase 1 — o que mudou na prática

**Antes:** se a IA devolvesse uma resposta mal formada (o que aconteceu em ~1 de cada 100 turnos no Playground),
o cliente recebia logo a mensagem de handoff. Só falhas de rede tinham uma 2.ª tentativa.
**Agora:** a parte que falhou (Mãe ou Filha) é repetida até 4 vezes no total, seja falha de rede ou resposta
mal formada, e só a 4.ª falha leva ao handoff. Tudo isto cabe em 40s por mensagem. A grafia "apresentacao" deixa
de ser um erro.
**Para validar:** Cenários T1 e T2 (feitos) e C1, depois do deploy.

### Fase 2 — Não desligar o bot em tentativas do job que ainda vão ser repetidas

**Objetivo:** no worker, o handoff (desligar o bot, registar o handoff) só acontece na última tentativa do job.

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/runners/whatsapp.py` | antes do `decide()`, marca no contexto `llm_failure_final = attempt >= JOB_MAX_ATTEMPTS` |
| `backend-executors/app/services/decision_engine.py` | no `except`, só chama `handoff_policy.apply` se `llm_failure_final` não for `False` |
| `backend-executors/tests/test_llm_failure_fallback_handoff.py` | tentativa não final → sem `set_lead_bot_disabled`/`log_handoff_requested`; final → igual a hoje |
| `docs/architecture/llm-architecture.md` | "Fallback final": exceção da tentativa de job não final |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `91eea4c` | Handoff por `llm_failure` só na última tentativa do job |

Detalhe: a regra "vai repetir?" passou para `_llm_failure_will_retry(attempt)` no runner, usada tanto para
marcar o contexto como para reagendar, para as duas não poderem divergir.

### Relatório da Fase 2 — o que mudou na prática

**Antes:** no WhatsApp real, com a política "desligar bot", uma falha da IA desligava o bot para esse lead logo
na 1.ª tentativa, mesmo que a nova tentativa automática do job (1 min e 3 min depois) acabasse por responder bem.
**Agora:** enquanto o job ainda vai ser repetido, não se desliga nada nem se regista handoff. Só se a última
tentativa também falhar é que o cliente recebe a mensagem de handoff e o bot é desligado. No Playground, nada muda.
**Para validar:** Cenário T3 (feito) e C1, depois do deploy.

---

## Checks de Validação

### Cenário T1 — Cliente de IA simulado a falhar 1, 2, 3 e 4 vezes (automático)
- [x] `python -m pytest tests/test_llm_stage_retry.py tests/test_llm_service_retry.py -q` em `backend-executors`
- [x] Mãe e Filha: 1, 2 e 3 falhas → resposta normal (2, 3 e 4 chamadas); 4 falhas → handoff `llm_failure` com 4 chamadas
- [x] Falha só na Filha → a Mãe é chamada uma única vez
- [x] 400 → sem nova tentativa; orçamento curto → para antes das 4
- **Validado em:** 26/10/2026 — 14 testes novos em `test_llm_stage_retry.py` e 6 em `test_llm_service_retry.py`, todos a passar

### Cenário T2 — Regressão da suíte do backend-executors
- [x] `python -m pytest tests -q` → só as 2 falhas que já existem em `main`
  (`test_recepcao_sales_flow_pending.py::test_p0_trigger_already_fired_advances_normally` e
  `::test_no_sequential_trigger_in_p0_behaves_like_baseline`, que não têm a ver com esta implementação)
- **Validado em:** 26/10/2026 — 513 passam, 2 falham (as mesmas de `main` antes da mudança: 493 passam, 2 falham)

### Cenário T3 — Fase 2: tentativa de job não final não desliga o bot (automático)
- [x] Teste do runner/decide: `llm_failure_final=False` → nenhuma chamada a `set_lead_bot_disabled`/`log_handoff_requested`
- [x] `llm_failure_final=True` (ou ausente, como no Playground) → handoff como hoje
- **Validado em:** 26/10/2026 — 4 testes novos em `test_llm_failure_fallback_handoff.py`; suíte completa com 517 a passar
  e as mesmas 2 falhas antigas de `main`

### Cenário C1 — Produção depois do deploy (observação)
- [ ] `railway logs -s backend-executors --lines 5000 --filter llm_stage_retry` (e `llm_stage_exhausted`,
  `llm_orchestrator_error`), repetido para `-s "worker backend-executors"`: recuperações > 0 e
  `llm_orchestrator_error` abaixo dos ~0,85% medidos (um termo por `--filter`; `--lines` até 5000)

---

## Ajustes Possíveis Pós-Implementação

- Na nova tentativa, juntar ao prompt o erro de validação ("faltou `confidence`"). Provavelmente aumenta a
  taxa de acerto, mas mexe nas instruções da IA (ler `prompt-engineering-principles.md` antes).
- `ChildResult.confidence` com valor por omissão: tiraria a outra metade das falhas medidas sem tentativa,
  mas muda o contrato da Filha.
- `meeting_management` (`decision_engine.py`, atalho pós-reunião) tem o seu próprio fallback e ficou de fora.
