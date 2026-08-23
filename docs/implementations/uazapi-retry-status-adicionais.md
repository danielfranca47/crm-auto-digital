# Expandir retry da UazAPI para 500/502/504 e timeout/erro de rede

**Branch:** _(a definir no Plan Mode)_
**Status:** Aguardando Plan Mode

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`docs/implementations/uazapi-backoff-e164.md` (23/08/2026). Aquela
implementação adicionou retry com backoff exponencial em
`backend-core/app/providers/uazapi_client.py` (`_request_with_retry`), mas
**limitado a 429/503** e **sem retry em timeout/erro de rede** — decisão
consciente na época para não estourar o orçamento de tempo apertado do
chamador (executor → core → UazAPI, ver
`docs/architecture/whatsapp-send-resiliencia.md`).

Se no uso real (com clientes pagantes) 500/502/504 ou timeouts pontuais da
UazAPI também se mostrarem transitórios (resolvidos por uma segunda
tentativa), vale expandir a cobertura do retry.

---

## Problemas Identificados (estado anterior)

1. **Retry não cobre 500/502/504:** `_RETRYABLE_STATUS_CODES = {429, 503}` em
   `uazapi_client.py` — qualquer outro erro 5xx propaga direto, sem
   tentativa.
2. **Retry não cobre timeout/erro de rede:** `httpx.TimeoutException`/
   `httpx.RequestError` propagam imediatamente, mesmo sendo potencialmente
   transitórios.

---

## Diagnóstico (a fazer em Plan Mode)

- Confirmar (por observação real de logs/produção, se possível) se 500/502/504
  ou timeouts da UazAPI paga são de fato transitórios ou indicam problema
  persistente (nesse caso retry não ajudaria).
- Se decidido re-tentar timeout, é necessário revisitar o orçamento de tempo
  documentado em `whatsapp-send-resiliencia.md` — ver também o item
  relacionado "M3 — Alinhar orçamento de timeout executor → core → UazAPI" em
  `docs/plans/confiabilidade-integracoes-externas-melhorias-futuras.md`
  (idealmente resolvido antes ou junto deste item, para não re-tentar sobre
  um orçamento já insuficiente).

---

## Plano de Implementação

_A preencher após Plan Mode e aprovação do utilizador._
