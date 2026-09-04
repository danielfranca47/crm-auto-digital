# Conexão WhatsApp (QR e Código de Pareamento)

Fluxo de vínculo da instância WhatsApp (UazAPI) usado pelo utilizador final na
página **AiProfile → Conexão**. Cobre os dois métodos de vínculo suportados —
QR code e código de pareamento — e como o estado é normalizado entre a UazAPI
e o frontend.

---

## Visão geral do fluxo

```
frontend-crm (ConexaoNumero.tsx)
  → POST /api/whatsapp/connect (backend-crm, routes/whatsapp_connect.py)
      → connect_core_whatsapp_instance() (core_client.py)
          → POST /whatsapp-instances/connect (backend-core, app/api/whatsapp_instances.py)
              → uazapi_admin.connect_instance() → POST {UAZAPI_BASE_URL}/instance/connect
                  ← resposta crua da UazAPI (qrcode / paircode / status)
      ← raw devolvido sem filtragem (uazapi_admin.redact_instance_token(), só mascara o token)
  → backend-crm extrai qr/pair_code do raw e normaliza o status
  ← ConnectResponse { instance_id, status, qr, pair_code, raw }
```

`GET /api/whatsapp/status` segue o mesmo padrão (proxy para
`/whatsapp-instances/status` no backend-core), sem QR/pair_code — só status e
`phone_e164`.

---

## QR code vs. código de pareamento

A UazAPI (`/instance/connect`) decide qual método usar com base num único
campo do corpo da requisição:

| Campo enviado | Resultado | Expira em |
|---|---|---|
| (nenhum, ou `phone` omitido) | Gera QR code | 2 minutos |
| `phone` (formato internacional, ex.: `5511999999999`, **sem `+`**) | Gera código de pareamento | 5 minutos |

Isso permite conectar usando um único aparelho: o telefone lê o código no
próprio navegador (aba Conexão) e digita-o em **WhatsApp → Aparelhos
conectados → Conectar um aparelho → Conectar com número de telefone**, sem
precisar de uma segunda tela para escanear QR.

Se a instância já estiver conectada com o mesmo número, `/instance/connect`
não gera novo QR nem código — a UazAPI responde `"response": "Already
connected"` e a sessão activa não é afectada.

---

## backend-core — repasse transparente

`app/api/whatsapp_instances.py`:
- `InstanceConnectPayload` tem `class Config: extra = "allow"` — qualquer
  campo extra enviado pelo backend-crm (ex.: `phone`) passa automaticamente
  para a UazAPI via `_format_admin_payload()`, sem necessidade de declarar o
  campo explicitamente no schema.
- A rota `POST /whatsapp-instances/connect` devolve
  `uazapi_admin.redact_instance_token(raw)` — o dict **completo** da resposta
  da UazAPI, só com o token mascarado. Nenhum campo é filtrado aqui; é o
  backend-crm que decide o que expor ao frontend.

`app/services/uazapi_admin.py`:
- `connect_instance()` — POST a `{UAZAPI_BASE_URL}/instance/connect`, body
  `{"name": instance_id, "instanceId": instance_id, **payload}`.
- `extract_connection_meta(raw)` — normaliza `status`, e extrai `qr_code`
  (`qrcode`/`qrCode`/`qr_code`) e `pair_code` (`paircode`/`pairCode`/
  `pair_code`) do payload cru, buscando recursivamente em dicts/listas
  aninhados.

---

## backend-crm — sanitização, extração e webhook

`routes/whatsapp_connect.py` (prefixo `/api/whatsapp`):

| Rota | Corpo aceito | Descrição |
|---|---|---|
| `POST /connect` | `{"phone"?: string}` | Cria/reusa instância, chama connect, registra webhook |
| `GET /status` | — | Status normalizado + `phone_e164` (chama a UazAPI ao vivo) |
| `POST /qr/refresh` | `{"phone"?: string}` | Gera novo QR ou código sem recriar a instância |
| `GET /connection-alert` | — | `{ disconnected, since }` — leitura barata (sem UazAPI), ver "Deteção de queda de sessão" |

- `ConnectRequest.phone` é sanitizado por `_sanitize_phone()` (remove
  espaço/`-`/`+`/parênteses) antes de seguir para `core_client.py` — a
  UazAPI espera dígitos com DDI, sem `+`.
- `_extract_qr(raw)` / `_extract_pair_code(raw)` usam `_find_in_payload()`
  para localizar `qrcode`/`paircode` em qualquer nível do JSON cru, igual ao
  padrão usado por `_extract_phone()`/`_normalize_status()`.
- `ConnectResponse.pair_code` é `None` quando a UazAPI não gerou código (ex.:
  já conectado, ou modo QR).
- Toda chamada a `/connect` ou `/qr/refresh` dispara `_set_whatsapp_webhook()`
  (não-bloqueante) — ver [`webhooks.md`](webhooks.md#registo-do-webhook-na-uazapi)
  para o registo do webhook em si.

`core_client.py`:
- `connect_core_whatsapp_instance(user_id, instance_id, phone=None)` — só
  inclui `"phone"` no payload POST para o backend-core quando informado;
  omitir o campo preserva o comportamento QR-only original.

---

## frontend-crm — `ConexaoNumero.tsx`

Componente usado em `AiProfile.tsx` (aba "Conexão"). Estado local relevante:

- `modo: 'qr' | 'pareamento'` — alterna entre os dois fluxos; `toggleModo()`
  limpa o payload pendente ao trocar.
- `qrPayload: WhatsappConnectResponse | null` — resposta de `/connect` ou
  `/qr/refresh`; o bloco de exibição decide QR vs. texto do código conforme
  `qrPayload.pair_code` estar preenchido.
- Timeout de expiração cliente-side: 90s para QR, 280s para código de
  pareamento (`startPolling(timeoutMs)`) — alinhado (com margem) aos limites
  reais da UazAPI (2min / 5min).
- Polling de status a cada 3s enquanto um QR/código está pendente; para
  automaticamente ao detectar `status === 'connected' | 'open'`.

`src/services/api.ts` — `whatsappConnect(phone?)` e `whatsappRefreshQr(phone?)`
só enviam corpo quando `phone` é informado; `WhatsappConnectResponse.pair_code`
é opcional.

---

## Retry em 429/503 (`uazapi_admin.py`)

`app/services/uazapi_admin.py::_request()` — helper único usado por
`init_instance`, `connect_instance`, `get_status` e `configure_webhook` —
retenta automaticamente em 429/503 antes de propagar erro, com o mesmo
padrão (e mesmas constantes) do retry de envio de mensagens
(`uazapi_client.py`, ver [`whatsapp-send-resiliencia.md`](whatsapp-send-resiliencia.md)):

| Constante | Valor | Descrição |
|---|---|---|
| `_RETRYABLE_STATUS_CODES` | `{429, 503}` | Únicos status que disparam retry |
| `_MAX_ATTEMPTS` | `3` | Total de tentativas (1 inicial + 2 retries) |
| `_RETRY_BASE_BACKOFF_SECONDS` | `0.5` | Base do backoff exponencial (`0.5s`, depois `1s`) |
| `_RETRY_AFTER_CAP_SECONDS` | `3.0` | Teto para o header `Retry-After` da UazAPI |

Regras:
- Se a resposta trouxer `Retry-After`, esse valor é usado (capado em 3s);
  senão, backoff exponencial `0.5 * 2^(tentativa-1)`.
- Timeout/erro de rede (`httpx.TimeoutException`/`RequestError`) **não são
  re-tentados** — propagam imediatamente, mesmo motivo do retry de envio: o
  timeout (20s por tentativa) já é lento por natureza, e os timeouts
  client-side de 90s/280s (QR/pareamento, acima) já absorvem a latência
  normal sem precisar de retry em cima de timeout.
- Qualquer outro status (401, 400, 500/502/504 etc.) propaga imediatamente —
  ex.: um `instance_token` expirado/inválido (401) não é re-tentado; o
  chamador (`whatsapp_instances.py`) trata a recuperação via re-`init` do
  fluxo normal, sem relação com este retry.
- Implementação própria (não reaproveita `_request_with_retry` de
  `uazapi_client.py`) porque `_request()` suporta método HTTP variável (GET
  em `get_status`, POST nos demais) e nome de header variável (`admintoken`
  vs. `token`).
- Como `_request()` é compartilhado, o retry cobre automaticamente todos os
  consumidores de `uazapi_admin.py` — incluindo a reconexão via painel admin
  (`backend-core/app/api/admin.py`) e `configure_webhook`, além do fluxo
  normal de conexão descrito acima.

---

## Credenciais UazAPI: admin_token vs. instance_token

Dois segredos distintos, com blast radius diferente:

- **`UAZAPI_ADMIN_TOKEN`** (`backend-core/.env`, header `admintoken`) — só
  usado em `init_instance()` (`POST /instance/init`, criação de instância) e
  em `configure_webhook(global_webhook=True)` (`POST /globalWebhook`).
  Ambos chamados só a partir de rotas administrativas de
  `whatsapp_instances.py` — fora do fluxo normal de conexão descrito acima.
- **`instance_token`** (por instância, persistido no banco, header `token`)
  — usado em tudo o resto: `connect_instance()`, `get_status()`, o webhook
  por instância (`_set_whatsapp_webhook`, ver [`webhooks.md`](webhooks.md#registo-do-webhook-na-uazapi))
  e o envio de mensagens (`uazapi_client.py`, `backend-executors`).

Consequência prática: rotacionar o `UAZAPI_ADMIN_TOKEN` **não afeta**
instâncias já conectadas nem o envio/recebimento de mensagens — só
operações administrativas (criar instância nova, reconfigurar webhook
global) até o token novo ser propagado. Runbook de rotação:
[`docs/ops/rotacao-uazapi-admin-token.md`](../ops/rotacao-uazapi-admin-token.md).

---

## Deteção de queda de sessão

`WhatsappConnection.status` não é só escrito pelos endpoints acima — a UazAPI
também envia um evento `connection` ao webhook quando a sessão cai de verdade
(ex.: logout forçado pelo WhatsApp). Esse evento atualiza o status em segundo
plano e dispara um email ao dono da conta pedindo para reconectar; quando a
conta reconecta depois dessa queda, um segundo email confirma que a Lara
voltou a funcionar (coluna `WhatsappConnection.disconnect_alert_sent_at`
controla esse segundo envio — só dispara se o primeiro alerta de queda
realmente foi enviado, evitando um falso "reconectou" na primeira conexão de
uma instância nova). Ver
[`webhooks.md`](webhooks.md#evento-de-conexão-eventconnection--status-real--alerta-de-desconexão)
para o fluxo completo — inclui a limitação conhecida de depender da entrega
do webhook, sem verificação periódica independente ainda.

Além do email, o `frontend-crm` mostra um banner in-app persistente em
qualquer página autenticada enquanto a desconexão não for resolvida:

- `GET /api/whatsapp/connection-alert` (`backend-crm/routes/whatsapp_connect.py`)
  retorna `{ disconnected: bool, since: str | null }`, lido via
  `_resolve_instance_id()` → `GET /whatsapp-connections/me` no backend-core
  (leitura de banco, sem chamar a UazAPI) — barato o suficiente para polling
  global. `disconnected` é `true` apenas quando o `status` normalizado não é
  activo **e** `WhatsappConnection.disconnect_alert_sent_at` está preenchido
  — a mesma condição usada para o email de reconexão, o que evita mostrar o
  banner para quem nunca conectou o WhatsApp.
- `frontend-crm/src/hooks/useWhatsappConnectionAlert.ts` — React Query,
  `refetchInterval: 60_000`.
- `frontend-crm/src/components/WhatsappDisconnectBanner.tsx` — banner
  vermelho fixo, montado em `App.tsx` (`AppShell`) ao lado do
  `UsageAlertBanner`; link para `/ai-profile`. Some sozinho assim que
  `disconnect_alert_sent_at` é limpo na reconexão — reflete o estado ao vivo,
  sem "marcar como lido".

**Hipótese principal (a confirmar):** conflito de sessão — o mesmo número
com o WhatsApp Web/Desktop aberto em paralelo à ligação da API. Motivo real
capturado num teste ao vivo: `"401: logged out from another device"`, padrão
documentado como causa comum de queda em APIs Baileys/UazAPI. Por isso
`ConexaoNumero.tsx` (frontend-crm) mostra, na página de Conexão, um alerta
avisando para não usar WhatsApp Web/Desktop no número ligado ao CRM.

---

## Outros consumidores (fora deste fluxo)

- `frontend-admin/src/pages/AdminInstances.tsx` → `api.reconnectInstance()`
  usa um caminho admin-only separado (`backend-core/app/api/admin.py`, que
  também chama `uazapi_admin.connect_instance()` directamente) — não passa
  por `whatsapp_connect.py` nem suporta `phone`/código de pareamento hoje.
- `backend-crm/routes/spy_agent.py` (`/api/spy-agent/reconnect`) duplica a
  extracção de QR com helpers próprios, independentes dos desta página —
  também sem suporte a código de pareamento.
