# Expandir retry da UazAPI para 500/502/504 (sem retry em timeout)

**Branch:** `fix/uazapi-retry-status-adicionais`
**Status:** Todos os cenários validados (26/08/2026)

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

Se no uso real (com clientes pagantes) 500/502/504 da UazAPI também se
mostrarem transitórios (resolvidos por uma segunda tentativa), vale expandir
a cobertura do retry.

**Escopo decidido no Plan Mode (via `AskUserQuestion`):** só ampliar
`_RETRYABLE_STATUS_CODES` para 500/502/504. Retry em timeout/erro de rede
**não** entra neste item — ver "Diagnóstico" abaixo para o motivo.

---

## Problemas Identificados (estado anterior)

1. **Retry não cobre 500/502/504:** `_RETRYABLE_STATUS_CODES = {429, 503}` em
   `uazapi_client.py` — qualquer outro erro 5xx propaga direto, sem
   tentativa.

---

## Diagnóstico

### Já existe?

Não. `backend-core/app/providers/uazapi_client.py:23` —
`_RETRYABLE_STATUS_CODES = {429, 503}` — 500/502/504 propagam direto, sem
tentativa.

### O que precisa ser construído

- Adicionar `500`, `502`, `504` a `_RETRYABLE_STATUS_CODES` — mesmo padrão
  de backoff já existente (`_MAX_ATTEMPTS=3`,
  `_RETRY_BASE_BACKOFF_SECONDS=0.5`, `_RETRY_AFTER_CAP_SECONDS=3.0`,
  `_resolve_retry_delay`). Nenhuma mudança de lógica, só a constante.

**Por que é seguro sem dado de produção observado:** retry em status code é
uma resposta **rápida** do servidor (não consome o timeout completo) — o
custo adicional no pior caso é o mesmo de hoje para 429/503 (~1.5s de
backoff entre tentativas), que cabe com folga nos 25s/35s do orçamento do
executor (ajustado em `uazapi-alinhar-orcamento-timeout.md`, M3). 502/504
são classicamente sintomas de instabilidade transitória de gateway/proxy (a
UazAPI é ela mesma um proxy para uma sessão WhatsApp Web); mesmo que não
ajude num 500 persistente, o overhead extra é desprezível.

### Por que retry em timeout/erro de rede fica fora deste item

Retentar em timeout tem um conflito real com o orçamento de timeout
recém-ajustado no M3 (`uazapi-alinhar-orcamento-timeout.md`): cada tentativa
de timeout já consome o timeout inteiro (20s texto / 30s mídia no core), então
até 1 retry em timeout já estouraria os 25s/35s do executor — a menos que se
reduza bastante o timeout por tentativa, o que reintroduziria exatamente o
problema que o M3 acabou de resolver (chamadas lentas-porém-válidas viram
falsas falhas). Decidido com o usuário adiar essa parte para um item futuro,
desenhado desde já para um modelo de "orçamento total de tempo" (deadline
global entre tentativas) em vez de "timeout fixo por tentativa × N
tentativas" — ver "Ajustes Possíveis" no final.

### Riscos e dependências

- Nenhum risco de comportamento no caminho de sucesso (2xx) ou em status
  não listados (4xx, exceto 429).
- Nenhuma mudança de timeout ou de orçamento — só a lista de status
  retentáveis.
- Sem dependência de outros itens pendentes.

---

## Abordagem

```
uazapi_client._request_with_retry(url, ...)
  → tentativa → 2xx → retorna
             → 429/500/502/503/504 e tentativas restantes → aguarda backoff → repete
             → esses status sem mais tentativas → UazapiClientError (status_code preservado)
             → timeout/erro de rede/outro status → propaga imediatamente, sem retry (inalterado)
```

---

## Plano de Implementação

### Fase 1 — Ampliar `_RETRYABLE_STATUS_CODES`

**Objetivo:** `_request_with_retry()` também retenta em 500/502/504, com o
mesmo backoff já existente; timeout/rede continuam propagando na hora.

| Arquivo | O que muda |
|---|---|
| `backend-core/app/providers/uazapi_client.py` | `_RETRYABLE_STATUS_CODES = {429, 503}` → `{429, 500, 502, 503, 504}` |
| `backend-core/tests/test_uazapi_client_retry.py` | Novos testes: 500/502/504 → sucesso na retentativa; 400/401 continuam sem retry (regressão) |

```python
# ANTES
_RETRYABLE_STATUS_CODES = {429, 503}

# DEPOIS
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
```

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `f3e8094` | `_RETRYABLE_STATUS_CODES` ampliado + testes |

**Detalhes do commit `f3e8094`:**
- `backend-core/app/providers/uazapi_client.py` — `_RETRYABLE_STATUS_CODES`
  `{429, 503}` → `{429, 500, 502, 503, 504}`; docstring atualizada
- `backend-core/tests/test_uazapi_client_retry.py` — 4 novos testes
  (500/502/504 com retry, 401 sem retry)

### Relatório da Fase 1 — o que mudou na prática

**Antes:** se a UazAPI respondesse 500, 502 ou 504 ao tentar enviar uma
mensagem, o erro ia direto para o job, sem nenhuma tentativa automática de
novo — mesmo esses códigos sendo, tipicamente, sinais de instabilidade
passageira do servidor/proxy.

**Agora:** o backend tenta automaticamente até 2 vezes a mais (mesmo padrão
já usado para 429/503) antes de desistir. Timeout e erro de rede continuam
sem retry — decisão deliberada, documentada, para não estourar o orçamento
de tempo do executor.

**Para validar:** Cenário P1 e P2, abaixo (já rodados nesta sessão).

---

## Checks de Validação

### Cenário P1 — Suíte de testes unitários (retry mockado)
- [x] Rodar `cd backend-core && python -m pytest tests/test_uazapi_client_retry.py -v`
- [x] Confirmar: 500/502/504 → sucesso na retentativa; 400/401 continuam
      sem retry (regressão)
- **Validado em:** 26/08/2026 — 12/12 testes passaram.

### Cenário P2 — Suíte completa do backend-core sem regressão
- [x] Rodar `SECRET_KEY=test-secret python -m pytest` na raiz de
      `backend-core`
- [x] Confirmar: nenhuma falha nova além das já pré-existentes e
      documentadas (`test_ai_profile_*`)
- **Validado em:** 26/08/2026 — 8 falhas / 43 passaram, mesmas 8 falhas
  pré-existentes já documentadas nos itens anteriores (`test_ai_profile_*`),
  sem relação com este módulo.

**Nota:** validação real de "os 500/502/504 realmente eram transitórios" só
será observável em produção (logs `event=uazapi_send_retry`) ao longo do
tempo — não bloqueante para esta implementação, já que o custo do retry é
baixo mesmo se não ajudar.

---

## Ajustes Possíveis Pós-Implementação

- **Retry em timeout/erro de rede** — decisão explícita de não fazer agora
  (conflito de orçamento com M3, ver "Diagnóstico" acima). Se o padrão de
  timeouts reais da UazAPI mudar no futuro (dados de produção mostrando
  timeouts frequentes e transitórios), revisitar como item novo, desenhado
  desde já para um modelo de "orçamento total de tempo" (deadline global
  entre tentativas) em vez de "timeout fixo por tentativa × N tentativas" —
  isso evitaria o conflito com o orçamento do executor.
