# Retry com backoff para falhas de LLM no Playground

**Branch:** `main`
**Status:** Todos os cenários validados (19/06/2026)

---

## Motivação

O Playground (`backend-crm/routes/playground.py`) chama o decision engine do
`backend-executors` de forma síncrona, sem fila de jobs. Ocasionalmente o bot
respondia vazio, com `reason=llm_failure` no trace — sem qualquer nova tentativa.

Causa raiz: as 3 funções de chamada à LLM em
`backend-executors/app/services/llm_service.py` fazem uma única chamada HTTP cada,
sem retry. Já existe retry para falhas de LLM, mas só no fluxo real de WhatsApp
(commit `8802ef3`, via fila de jobs em `app/runners/whatsapp.py`, backoff 60s/180s)
— o Playground bypassa essa fila de propósito, por isso nunca foi coberto.

O guardrail `guardrail_sdr_escalate_closing` (também produz `message_text=""`, mas
é intencional — bot calado quando agente SDR/agenda chega a "closing") foi
confirmado como correto e está fora do escopo desta mudança.

---

## Problemas Identificados (estado anterior)

1. **Sem retry no Playground:** `llm_service.py` (`generate_mother_route`,
   `generate_decision_text`, `generate_child_result`) — qualquer
   `httpx.RequestError` ou status ≥400 propaga imediatamente para
   `decision_engine.py`, que cai no fallback `reason="llm_failure"` com
   `message_text=""`.
2. **Triplicação de código:** as 3 funções em `llm_service.py` são quase
   idênticas — mesma lógica de `client.post`, headers, timeout e tratamento de
   status, repetida 3x.

---

## Abordagem

```
generate_mother_route() / generate_decision_text() / generate_child_result()
  → _post_with_retry(payload)
      ├─ tentativa 1: client.post(...)
      │    ├─ sucesso (200) → devolve JSON
      │    ├─ httpx.RequestError → log + sleep(1s) → tentativa 2
      │    └─ status retryable (429/500/502/503/504) → log + sleep(1s) → tentativa 2
      └─ tentativa 2 (última): sucesso ou propaga excepção (sem mais retry)
```

`decision_engine.py` não muda — continua a capturar qualquer excepção final no seu
`except Exception` genérico, com o mesmo fallback de hoje.

---

## Plano de Implementação

### Fase 1 — `llm_service.py`: helper de retry partilhado

**Objetivo:** absorver falhas transitórias de rede/HTTP sem alterar o contrato
com `decision_engine.py`.

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/llm_service.py` | Novo helper `_post_with_retry()`; as 3 funções públicas passam a usá-lo |
| `backend-executors/tests/test_llm_service_retry.py` | Novo — cobre sucesso/retry/esgotamento/status não-retryable/modo stub |

```python
# ANTES (repetido 3x)
timeout = httpx.Timeout(settings.llm_timeout_seconds)
with httpx.Client(timeout=timeout) as client:
    response = client.post(settings.llm_api_base, headers=headers, json=payload)
if response.status_code != 200:
    logger.warning(...)
response.raise_for_status()
return _extract_output_text(response.json())

# DEPOIS (helper partilhado, até 2 tentativas, backoff 1s)
return _extract_output_text(_post_with_retry(payload))
```

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `0da5d50` | feat: retry com backoff em llm_service.py + 11 testes (zero regressão confirmada) |

---

## Checks de Validação

### Cenário P1 — Playground com LLM saudável (regressão)
- [x] Enviar mensagem normal no Playground local
- [x] Confirmar: resposta chega normalmente, sem atraso perceptível
- **Validado em:** 19/06/2026 — local, múltiplas trocas de mensagem antes e depois do teste de falha (P3), sem nenhuma regressão perceptível

### Cenário P3 — Playground com falha persistente
- [x] Confirmar nos logs do backend-executors: `event=llm_request_error attempt=1/2` seguido de `attempt=2/2` antes de `event=llm_orchestrator_error`
- **Validado em:** 19/06/2026 — local. `LLM_API_BASE` apontado para porta inexistente (`127.0.0.1:9999`) para forçar `ConnectError`; logs mostraram exactamente `event=llm_request_error attempt=1/2 exc_type=ConnectError` seguido ~3.4s depois de `attempt=2/2`, e a resposta do Playground caiu no fallback gracioso (200, `Ver trace 0%`, sem crash). Configuração restaurada e confirmado que voltou ao normal.

### Cenário C1 — WhatsApp real, mecanismo de job-retry inalterado
- [x] Confirmar que o retry de job (commit `8802ef3`) continua a reagendar normalmente quando `llm_failure` persiste após as 2 tentativas internas
- **Validado em:** 19/06/2026 — via leitura de código (não houve alteração em `app/runners/whatsapp.py` por esta implementação, que só toca `llm_service.py`) + suite `pytest backend-executors/tests` sem novas falhas

### Cenário C2 — Guardrail SDR não afetado
- [x] Confirmar que lead em agent_mode SDR/agenda chegando a "closing" continua a receber `message_text=""` com `reason` começando por `guardrail_sdr_escalate_closing`
- **Validado em:** 19/06/2026 — via suite automatizada (`test_scheduling_agent_no_closing.py` e correlatos), sem nenhuma falha nova após a mudança em `llm_service.py`; código de guardrail (`decision_engine.py`) não foi tocado por esta implementação

---

## Ajustes Possíveis Pós-Implementação

- Retry de falhas de *parsing/validação* do JSON da mother (resposta 200 mas
  conteúdo malformado) ficou fora do escopo — avaliar depois de observar logs de
  produção (`event=llm_orchestrator_error stage=mother_parse|mother_validate`).
  Se a incidência for baixa, não compensa o risco de tocar em `decision_engine.py`.
