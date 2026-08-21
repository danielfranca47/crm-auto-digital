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
| `GET /status` | — | Status normalizado + `phone_e164` |
| `POST /qr/refresh` | `{"phone"?: string}` | Gera novo QR ou código sem recriar a instância |

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

## Outros consumidores (fora deste fluxo)

- `frontend-admin/src/pages/AdminInstances.tsx` → `api.reconnectInstance()`
  usa um caminho admin-only separado (`backend-core/app/api/admin.py`, que
  também chama `uazapi_admin.connect_instance()` directamente) — não passa
  por `whatsapp_connect.py` nem suporta `phone`/código de pareamento hoje.
- `backend-crm/routes/spy_agent.py` (`/api/spy-agent/reconnect`) duplica a
  extracção de QR com helpers próprios, independentes dos desta página —
  também sem suporte a código de pareamento.
