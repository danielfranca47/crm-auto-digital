# Backoff exponencial em 429/503 + validação E.164 do número de destino

**Branch:** `worktree-fix+uazapi-backoff-e164`
**Status:** Em andamento

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`etapa-uazapi-migracao-plano-pago.md`. Com a migração para o servidor pago da
UazAPI concluída e 2 clientes reais prestes a conectar, reduzir o risco de
mensagens perdidas por rate-limit ou número mal formatado passa a ter
prioridade — no plano free isso era tolerável, com clientes pagantes não é.

---

## Problemas Identificados (estado anterior)

1. **Sem retry em rate-limit no envio de mensagens:** `backend-core/app/providers/uazapi_client.py`
   (`send_text`, `send_media`) — chamado por `backend-core/app/api/whatsapp_send.py`, o caminho real
   de envio usado pelo executor — propaga qualquer erro HTTP (incluindo 429/503) direto ao chamador,
   sem nenhuma tentativa automática de repetir. Um pico de tráfego (vários leads atendidos ao mesmo
   tempo) pode gerar falha silenciosa de envio.

2. **Sem validação de formato do número:** `whatsapp_send.py::_sanitize_number` (linha 56-57) só
   remove espaços/traços/parênteses/`+` do número — não valida se o resultado é um número válido.
   Números malformados geram chamadas pagas à UazAPI que falham de qualquer forma.

---

## Diagnóstico (Plan Mode)

- Escopo do retry decidido com o utilizador: **só o caminho de envio de mensagens**
  (`uazapi_client.py`), não as operações de conexão de instância (`uazapi_admin.py` —
  init/connect/status/webhook, usadas para conectar o WhatsApp via QR code). Essas são
  interativas — retry ali atrasaria a UX sem resolver o problema descrito.
- Já existe um padrão de retry equivalente em `backend-executors/app/services/llm_service.py::_post_with_retry`
  (2 tentativas, delay fixo de 1s, não exponencial) — usado como referência de estilo (helper local
  dentro do próprio módulo), mas não reaproveitável diretamente: é síncrono (`httpx.Client`) e
  `uazapi_client.py` é assíncrono (`httpx.AsyncClient`).
- Já existe validação completa de E.164 em `backend-crm/services/phone_normalizer.py::normalize_to_e164`
  (normalização com country code, regra do 9º dígito BR etc.), aplicada em `routes/leads.py` e
  `routes/webhooks.py`. Isso não cobre `backend-core` (outro serviço, outro banco, sem garantia de
  que todo número que chega já passou por essa normalização). A validação aqui é só uma checagem de
  guarda (regex), não uma reimplementação da normalização completa.
- **Risco de orçamento de tempo identificado:** `backend-executors/app/clients/core_client.py::send_whatsapp_message`
  tem timeout total de 15s (executor → core). Dentro disso, `uazapi_client.send_text` já usa timeout
  de 20s por tentativa (`send_media` usa 30s) — uma única tentativa lenta já pode estourar o
  orçamento do executor hoje, antes mesmo desta mudança. Para não piorar isso, o retry novo:
  - **não** re-tenta em timeout/erro de rede (só em respostas HTTP 429/503);
  - usa poucas tentativas (3 no total) com backoff curto e exponencial (0.5s, 1s);
  - respeita `Retry-After` da UazAPI quando presente, com teto de 3s.
  - A inconsistência de timeouts (15s executor vs 20-30s core→uazapi) é pré-existente e fica fora
    do escopo — ver "Ajustes Possíveis Pós-Implementação".

---

## Abordagem

```
whatsapp_send.py (rota /whatsapp/send | /whatsapp/send-media)
  → _sanitize_number()
  → _is_valid_e164_digits() ─ inválido → 400 (sem chamar UazAPI)
  → uazapi_client.send_text() / send_media()
       → _request_with_retry()
            ├─ 2xx → retorna
            ├─ 429/503 e tentativas restantes → aguarda (Retry-After capado ou backoff exponencial) → repete
            ├─ 429/503 sem mais tentativas → UazapiClientError (como hoje)
            └─ outro erro / timeout / rede → propaga imediatamente (como hoje)
```

---

## Plano de Implementação

### Fase 1 — Backoff exponencial no envio de mensagens (429/503)

**Objetivo:** repetir automaticamente o envio quando a UazAPI responder 429/503, sem comprometer o orçamento de tempo do chamador.

| Arquivo | O que muda |
|---|---|
| `backend-core/app/providers/uazapi_client.py` | Novo helper `_request_with_retry`; `send_text`/`send_media` passam a usá-lo |

```python
# ANTES (send_text, resumido)
async with httpx.AsyncClient(timeout=20.0) as client:
    response = await client.post(url, headers=headers, json=payload)
if response.is_error:
    raise UazapiClientError(...)

# DEPOIS
response = await _request_with_retry(url=url, headers=headers, json=payload, timeout=20.0)
if response.is_error:
    raise UazapiClientError(...)
```

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `8bc71c3` | Backoff exponencial em 429/503 no envio de mensagens (`uazapi_client.py`) + testes |

**Detalhes do commit `8bc71c3`:**
- `backend-core/app/providers/uazapi_client.py` — novo helper assíncrono `_request_with_retry`
  usado por `send_text` e `send_media`; re-tenta até 3 vezes em 429/503 com backoff exponencial
  (0.5s, 1s), respeitando `Retry-After` da UazAPI com teto de 3s; erros de rede/timeout continuam
  propagando imediatamente (sem retry).
- `backend-core/tests/test_uazapi_client_retry.py` — 8 testes cobrindo sucesso sem retry, retry em
  429, retry em 503, esgotamento de tentativas, `Retry-After` respeitado/capado, timeout não
  re-tenta, 400 não re-tenta, `send_media` também usa o helper.

### Relatório da Fase 1 — o que mudou na prática

**Antes:** se a UazAPI respondesse "muitas requisições" (429) ou "indisponível" (503) — o que pode
acontecer quando vários leads são atendidos ao mesmo tempo — o CRM desistia na hora e a mensagem
não era enviada, sem nenhuma nova tentativa.

**Agora:** nesses dois casos específicos, o sistema tenta de novo automaticamente até 3 vezes, com
uma pequena espera entre tentativas (meio segundo, depois um segundo) antes de desistir de verdade.
Erros de rede/timeout continuam se comportando exatamente como antes (sem retry) para não atrasar
ainda mais um pedido que já está lento.

**Para validar:** Cenário P1 (abaixo) — já validado via testes automatizados nesta sessão
(`test_uazapi_client_retry.py`, 8/8 passando). Não há UI envolvida (é lógica interna de backend),
então não há cenário de browser para este item.

### Fase 2 — Validação E.164 antes do envio

**Objetivo:** recusar números malformados antes de pagar pela chamada à UazAPI.

| Arquivo | O que muda |
|---|---|
| `backend-core/app/api/whatsapp_send.py` | Nova função `_is_valid_e164_digits`; chamada em `send_whatsapp` e `send_whatsapp_media` logo após `_sanitize_number` |

---

## Checks de Validação

### Cenário P1 — Retry em 429/503
- [x] Rodar `backend-core/tests/test_uazapi_client_retry.py`
- [x] Confirmar: 429 seguido de sucesso não propaga erro (retry funcionou)
- [x] Confirmar: esgotadas as tentativas, erro é propagado como antes
- **Validado em:** 23/08/2026 — 8/8 testes passando (`python -m pytest tests/test_uazapi_client_retry.py -v`)

### Cenário P2 — Validação E.164
- [ ] Rodar `backend-core/tests/test_whatsapp_send_e164.py`
- [ ] Confirmar: número inválido retorna 400 sem chamar a UazAPI
- [ ] Confirmar: número válido segue o fluxo normal

### Cenário C1 — Suíte completa do backend-core
- [ ] Rodar `cd backend-core && python -m pytest` — nada quebrou

---

## Ajustes Possíveis Pós-Implementação

- **Inconsistência de timeouts:** `core_client.send_whatsapp_message` (executor→core) usa 15s de
  timeout total, enquanto `uazapi_client.send_text`/`send_media` (core→UazAPI) usam 20s/30s por
  tentativa — já hoje, antes deste item, uma única tentativa lenta pode estourar o orçamento do
  executor. Não foi tratado aqui (fora do escopo: este item trata especificamente de 429/503, não
  de lentidão). Vale um item futuro para alinhar esses timeouts.
- Retry limitado a 429/503 — não cobre 500/502/504 nem timeout/erro de rede. Se no uso real esses
  também se mostrarem transitórios e valer a pena re-tentar, pode ser revisitado.
- Retry não aplicado a `uazapi_admin.py` (operações de conexão) — decisão consciente para não
  atrasar a UX interativa de conectar o WhatsApp; pode ser revisitado se rate-limit nessas rotas
  também virar problema recorrente.
