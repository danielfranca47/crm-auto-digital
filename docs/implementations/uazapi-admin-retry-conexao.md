# Retry em 429/503 nas operações de conexão de instância (uazapi_admin.py)

**Branch:** `fix/uazapi-admin-retry-conexao`
**Status:** Em andamento

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`docs/implementations/uazapi-backoff-e164.md` (23/08/2026). Aquela
implementação adicionou retry com backoff exponencial só no caminho de
**envio de mensagens** (`backend-core/app/providers/uazapi_client.py`) —
decisão explícita para não atrasar a UX interativa de conectar o WhatsApp via
QR code/código de pareamento (`backend-core/app/services/uazapi_admin.py`,
usado por `whatsapp_instances.py` e documentado em
`docs/architecture/whatsapp-connection.md`).

Se rate-limit (429/503) nessas operações de conexão também virar problema
recorrente (não só no envio), vale estender o mesmo padrão de retry para lá.

---

## Problemas Identificados (estado anterior)

1. **Sem retry em `uazapi_admin.py::_request`:** usado por `init_instance`,
   `connect_instance`, `get_status`, `configure_webhook` — propaga 429/503
   direto ao chamador (que hoje já trata 429 especificamente em
   `whatsapp_instances.py::_raise_uazapi_http_error`, repassando
   `Retry-After` ao frontend, mas sem nenhuma tentativa automática antes
   disso).

---

## Diagnóstico

### Já existe?

Não. `uazapi_admin.py::_request` (linha 143) é o único ponto de chamada HTTP
para `init_instance`, `connect_instance`, `get_status` e `configure_webhook`
— hoje sem nenhum retry: qualquer status de erro (incluindo 429/503)
propaga imediatamente como `UazapiAdminError`, com `status_code` e
`retry_after` (extraído do header `Retry-After`) preservados no objeto de
exceção.

O chamador HTTP, `whatsapp_instances.py::_raise_uazapi_http_error` (linha
122), já trata 429 especificamente: repassa `Retry-After` como header HTTP
429 ao frontend. Qualquer outro erro vira 502. Ou seja, hoje o "retry" é
100% manual — o usuário precisa clicar em conectar/atualizar de novo.

O frontend (`ConexaoNumero.tsx`) não retenta automaticamente em erro de
`/connect` ou `/qr/refresh` — o catch é silencioso e delega a um toast
genérico (linhas 83-100). O polling de status a cada 3s só existe **depois**
que um QR/pair code já foi obtido com sucesso — não ajuda no caso de a
própria chamada de connect/init falhar com 429/503.

### O que precisa ser construído

Estender o padrão de retry já existente em `uazapi_client.py` para
`uazapi_admin.py::_request`:

- Mesmas constantes de `uazapi_client.py` para consistência entre os dois
  módulos: `_RETRYABLE_STATUS_CODES = {429, 503}`, `_MAX_ATTEMPTS = 3`,
  `_RETRY_BASE_BACKOFF_SECONDS = 0.5`, `_RETRY_AFTER_CAP_SECONDS = 3.0`.
- Mesma lógica de backoff: respeita `Retry-After` do response (capado em
  3s), senão exponencial `0.5 * 2^(tentativa-1)`.
- **Sem retry em timeout/erro de rede** — mesma decisão já tomada no path de
  envio, pelo mesmo motivo: timeout já é lento por natureza (aqui, 20s por
  tentativa) e re-tentar só comporia mais espera.
- Implementação própria dentro de `uazapi_admin.py` (não reaproveita
  `_request_with_retry` de `uazapi_client.py` diretamente) porque `_request`
  aqui suporta método HTTP variável (GET para `get_status`, POST para os
  demais) e nome de header variável (`admintoken` vs `token`) — o helper de
  `uazapi_client.py` é POST-only e não parametrizado para isso.
- Log de retry análogo ao existente (`event=uazapi_admin_retry`), para
  distinguir do log de retry do path de envio nas mesmas ferramentas de
  observação.

Como `_request` é o helper único e compartilhado, o retry passa a valer
automaticamente para todos os consumidores: fluxo normal de conexão
(`whatsapp_instances.py`), reconexão via painel admin
(`backend-core/app/api/admin.py`) e configuração de webhook global — sem
precisar tocar em nenhum desses chamadores.

### Riscos e dependências

- Nenhum risco de comportamento no caminho de sucesso (2xx) — mudança é
  aditiva, só afeta o que acontece antes de levantar `UazapiAdminError` em
  429/503.
- Latência adicional no pior caso: até ~1.5s (0.5s + 1s) antes de
  finalmente propagar erro após esgotar tentativas — desprezível frente aos
  timeouts client-side existentes (90s QR / 280s pareamento,
  `whatsapp-connection.md`).
- `get_status` também passa a ter retry (é chamado pelo polling do
  frontend a cada 3s) — aceitável: o pior caso é uma resposta de poll
  ocasionalmente ~1.5s mais lenta, sem quebrar o intervalo de 3s entre
  polls.
- Sem dependência de outros itens pendentes (diferente de
  `uazapi-retry-status-adicionais.md`, que depende de M3/orçamento de
  timeout) — este item é autocontido.

---

## Abordagem

```
uazapi_admin._request(method, path, ...)
  → tentativa 1 → 2xx → retorna
              → 429/503 e tentativas restantes → aguarda backoff → repete
              → 429/503 sem mais tentativas → UazapiAdminError (status/retry_after preservados)
              → timeout/erro de rede/outro status → propaga imediatamente, sem retry
```

Aplica-se igualmente a `init_instance`, `connect_instance`, `get_status` e
`configure_webhook`, pois todas passam por `_request`.

---

## Plano de Implementação

### Fase 1 — Retry 429/503 em `uazapi_admin.py::_request`

**Objetivo:** `_request()` retenta 429/503 com backoff antes de propagar
erro, sem afetar timeout/rede nem outros status codes.

| Arquivo | O que muda |
|---|---|
| `backend-core/app/services/uazapi_admin.py` | Constantes de retry + `_resolve_retry_delay` + loop de retry dentro de `_request()` |
| `backend-core/tests/test_uazapi_admin.py` | Testes de retry (429→sucesso, 503→sucesso, esgota tentativas, 400 não retenta, timeout não retenta, Retry-After respeitado/capado) |

```python
# ANTES — uazapi_admin.py::_request, sem retry
try:
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.request(method, url, headers=headers, json=json, params=params)
except httpx.TimeoutException as exc:
    raise UazapiAdminTimeoutError("Uazapi admin request timed out") from exc
except httpx.RequestError as exc:
    raise UazapiAdminError("Uazapi admin request failed") from exc

if response.is_error:
    ...  # levanta UazapiAdminError direto

# DEPOIS — retry 429/503 antes de levantar erro
for attempt in range(1, _MAX_ATTEMPTS + 1):
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.request(method, url, headers=headers, json=json, params=params)
    except httpx.TimeoutException as exc:
        raise UazapiAdminTimeoutError("Uazapi admin request timed out") from exc
    except httpx.RequestError as exc:
        raise UazapiAdminError("Uazapi admin request failed") from exc

    if response.status_code in _RETRYABLE_STATUS_CODES and attempt < _MAX_ATTEMPTS:
        delay = _resolve_retry_delay(response, attempt)
        logger.warning("event=uazapi_admin_retry attempt=%s/%s status=%s delay=%.2f", ...)
        await asyncio.sleep(delay)
        continue
    break

if response.is_error:
    ...  # mesmo tratamento de erro de hoje
```

---

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `0d0ccad` | retry 429/503 com backoff em `uazapi_admin.py::_request` + testes |

**Detalhes do commit `0d0ccad`:**
- `backend-core/app/services/uazapi_admin.py` — constantes de retry
  (`_RETRYABLE_STATUS_CODES`, `_MAX_ATTEMPTS`, `_RETRY_BASE_BACKOFF_SECONDS`,
  `_RETRY_AFTER_CAP_SECONDS`), `_resolve_retry_delay()` e loop de retry
  dentro de `_request()`
- `backend-core/tests/test_uazapi_admin.py` — 7 novos testes cobrindo
  429/503 com sucesso na retentativa, esgotamento de tentativas,
  `Retry-After` respeitado/capado, 400 e timeout sem retry

### Relatório da Fase 1 — o que mudou na prática

**Antes:** se a UazAPI respondesse 429 (rate-limit) ou 503 (indisponível)
durante uma tentativa de conectar o WhatsApp (QR code ou código de
pareamento), o erro ia direto para o usuário — que precisava clicar em
"Conectar" ou "Atualizar" de novo manualmente.

**Agora:** o backend tenta automaticamente até 2 vezes a mais (com pequena
espera entre tentativas) antes de mostrar erro ao usuário. Na prática, um
rate-limit passageiro da UazAPI tende a se resolver sozinho, sem o usuário
perceber. Não há mudança visível quando tudo funciona normalmente.

**Para validar:** Cenário P1 (testes automatizados, já rodados — 9/9
passaram) e Cenário C1 (fluxo real de conexão), abaixo.

---

## Checks de Validação

### Cenário P1 — Suíte de testes unitários (retry mockado)
- [x] Rodar `cd backend-core && python -m pytest tests/test_uazapi_admin.py -v`
- [x] Confirmar: casos de 429→sucesso, 503→sucesso, esgotamento de
      tentativas, 400 sem retry, timeout sem retry e `Retry-After`
      respeitado/capado passam
- **Validado em:** 26/08/2026 — 9/9 testes passaram. Suíte completa do
  backend-core rodada também (`SECRET_KEY=test-secret python -m pytest`):
  8 falhas pré-existentes em `test_ai_profile_agent_mode.py` /
  `test_ai_profile_timezone_persistence.py`, confirmadas idênticas na pasta
  principal (`main`) antes desta mudança — sem relação com este item.

### Cenário C1 — Fluxo real de conexão sem regressão
- [ ] Abrir a página AiProfile → Conexão
- [ ] Gerar QR code e confirmar que continua funcionando normalmente
- [ ] Gerar código de pareamento e confirmar que continua funcionando
      normalmente
- **Nota:** não é possível forçar um 429/503 real da UazAPI em ambiente de
  teste — este cenário valida apenas ausência de regressão no caminho
  feliz; a cobertura do retry em si fica no Cenário P1 (testes unitários).

---

## Ajustes Possíveis Pós-Implementação

- Se 429/503 nas operações de conexão se mostrarem raros na prática, este
  retry pode não ter efeito observável — está aqui por consistência e
  robustez, não por um problema já observado em produção.
- `docs/architecture/whatsapp-send-resiliencia.md` cobre hoje só o retry do
  caminho de envio; na graduação, avaliar se o escopo do doc deve crescer
  para cobrir também conexão, ou se um doc próprio faz mais sentido.
