# Resiliência do Envio WhatsApp (retry + validação de número)

Cobre o caminho de envio de mensagens via UazAPI em `backend-core`: retry
automático em rate-limit e validação de formato do número de destino antes da
chamada paga à UazAPI. As operações de conexão/QR code de instância têm o
mesmo padrão de retry, documentado separadamente em
[`whatsapp-connection.md`](whatsapp-connection.md#retry-em-429503-uazapi_adminpy)
(implementação própria, não compartilha código com este módulo). Não cobre
timing de humanização (ver [`humanization.md`](humanization.md)).

---

## Fluxo

```
whatsapp_send.py (POST /whatsapp/send | /whatsapp/send-media)
  → _sanitize_number()                — remove espaço/traço/parênteses/'+'
  → _is_valid_e164_digits()           — inválido → 400 invalid_number_format (sem chamar UazAPI)
  → uazapi_client.send_text() / send_media()
       → _request_with_retry()
            ├─ 2xx → retorna
            ├─ 429/503 e tentativas restantes → aguarda → repete
            ├─ 429/503 sem mais tentativas → UazapiClientError (status_code preservado)
            └─ timeout/erro de rede/outro status → propaga imediatamente, sem retry
```

---

## Retry em 429/503 (`backend-core/app/providers/uazapi_client.py`)

`_request_with_retry()` é o helper assíncrono usado por `send_text` e
`send_media`. Constantes:

| Constante | Valor | Descrição |
|---|---|---|
| `_RETRYABLE_STATUS_CODES` | `{429, 503}` | Únicos status que disparam retry |
| `_MAX_ATTEMPTS` | `3` | Total de tentativas (1 inicial + 2 retries) |
| `_RETRY_BASE_BACKOFF_SECONDS` | `0.5` | Base do backoff exponencial (`0.5s`, depois `1s`) |
| `_RETRY_AFTER_CAP_SECONDS` | `3.0` | Teto para o header `Retry-After` da UazAPI |

Regras:
- Se a resposta trouxer `Retry-After`, esse valor é usado (capado em 3s);
  senão, backoff exponencial `0.5 * 2^(tentativa-1)`.
- **Erros de rede/timeout (`httpx.RequestError`/`TimeoutException`) não são
  re-tentados** — propagam imediatamente como `UazapiTimeoutError`/
  `UazapiClientError`, igual ao comportamento antes deste retry existir.
  Motivo: um timeout já é lento por natureza — re-tentar só composeria mais
  atraso sem ganho (ver "Orçamento de timeout" abaixo).
- Qualquer outro status code (4xx exceto os listados, 500/502/504) também não
  re-tenta — comportamento inalterado.
- O escopo deste retry é só `uazapi_client.py` (envio de mensagens). As
  operações de conexão de instância em `uazapi_admin.py` (init/connect/
  status/webhook) têm sua própria implementação de retry, com as mesmas
  constantes — ver [`whatsapp-connection.md`](whatsapp-connection.md#retry-em-429503-uazapi_adminpy).

### Orçamento de timeout (executor → core → UazAPI)

O timeout do chamador nunca é menor que o pior caso realista da chamada que
ele aguarda, para evitar que o executor desista antes do core terminar um
envio que, na prática, é concluído com sucesso na UazAPI (o que causaria
reenvio duplicado da mesma mensagem ao lead num retry de job):

| Chamada | Timeout | Pior caso da chamada seguinte |
|---|---|---|
| `core_client.py::send_whatsapp_message` (executor → core) | 25.0s | `send_text` no core: até 20s (última tentativa) + até ~1.5s de backoff ≈ 21.5s |
| `core_client.py::send_whatsapp_media` (executor → core) | 35.0s | `send_media` no core: até 30s (última tentativa) + até ~1.5s de backoff ≈ 31.5s |

`send_whatsapp_message`/`send_whatsapp_media` são chamados de dentro do loop
síncrono de polling do worker (`backend-executors/app/workers/whatsapp_worker.py`)
— não há usuário esperando a resposta em tempo real, então a margem extra
não tem custo de UX perceptível.

---

## Validação E.164 (`backend-core/app/api/whatsapp_send.py`)

`_is_valid_e164_digits(sanitized: str) -> bool` valida o número já
sanitizado (sem `+`, só dígitos) contra `^[1-9]\d{7,14}$` — 8 a 15 dígitos,
sem zero à esquerda. Chamada em `send_whatsapp` e `send_whatsapp_media`,
logo após `_sanitize_number()` e **depois** do bypass de stub
(`settings.core_whatsapp_stub`) — números fake em modo stub continuam
funcionando. Número inválido → `400 invalid_number_format`, sem chegar a
chamar a UazAPI.

Não reimplementa normalização completa (country code, regra do 9º dígito
BR) — isso é responsabilidade de
`backend-crm/services/phone_normalizer.py::normalize_to_e164`, aplicada no
momento de entrada do lead/mensagem (`routes/leads.py`, `routes/webhooks.py`).
A validação aqui é só uma checagem de guarda antes da chamada paga, já que
`backend-core` é outro serviço/banco e não há garantia de que todo número que
chega já passou pela normalização do CRM.

---

## Arquivos Críticos

| Arquivo | Responsabilidade |
|---|---|
| `backend-core/app/providers/uazapi_client.py` | `_request_with_retry`, `send_text`, `send_media` |
| `backend-core/app/api/whatsapp_send.py` | `_sanitize_number`, `_is_valid_e164_digits`, rotas `/whatsapp/send` e `/whatsapp/send-media` |
| `backend-executors/app/clients/core_client.py` | `send_whatsapp_message`, `send_whatsapp_media` — timeouts alinhados ao pior caso do core |
