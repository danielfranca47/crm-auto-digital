# Fix: Conexão WhatsApp QR Code na página AI Profile

**Branch:** `etapa-8-6-desabilitar-bot-lead`
**Status:** Em andamento

---

## Motivação

Usuários não conseguiam conectar o número WhatsApp na aba "Conexão do número" da página AI Profile. O botão "Reconectar QR" existia mas não exibia o QR code — o componente `ConexaoNumero.tsx` descartava silenciosamente a resposta da API que continha o QR.

---

## Problemas Identificados

1. **QR code descartado no frontend:** `ConexaoNumero.tsx` chamava `api.crm.whatsappConnect()` mas ignorava o retorno `{ qr: { kind, value } }`. Nenhum QR era exibido ao usuário.

2. **Sem polling de status:** Após clicar "Reconectar QR", não havia verificação periódica para detectar quando o usuário escaneava o QR. O componente fazia apenas uma checagem de status imediata após o connect.

3. **Webhook bloqueava o QR:** Em `backend-crm/routes/whatsapp_connect.py`, a chamada `_set_whatsapp_webhook()` ocorria antes do `return ConnectResponse(...)`. Se `CRM_PUBLIC_BASE_URL` ou `CRM_WEBHOOK_SECRET` não estivessem configurados, o endpoint retornava HTTP 500 sem nunca entregar o QR ao frontend.

---

## Abordagem

```
Usuário clica "Reconectar QR"
  → POST /api/whatsapp/connect
    ├─ UazAPI retorna QR code
    ├─ Webhook configurado (falha não-bloqueante)
    └─ ConnectResponse { instance_id, status, qr } retornado

Frontend recebe resposta
  ├─ qr.value presente → exibe imagem do QR
  │   ├─ Inicia polling 3s → detecta scan → limpa QR, atualiza status
  │   └─ Timeout 90s → exibe botão "Novo QR code"
  └─ qr.value ausente → já conectado, atualiza status
```

Lógica de exibição do QR (`getQrSrc`) reusada de `SpyAgentSetup.tsx` — já suporta `base64`, `url`, e `data:image` URI.

---

## Plano de Implementação

### Fase 1 — Frontend: display QR + polling

**Objetivo:** exibir o QR code retornado pela API e detectar automaticamente o scan

| Arquivo | O que mudou |
|---|---|
| `frontend-crm/src/components/agente/ConexaoNumero.tsx` | Adicionado: estado `qrPayload`, `qrExpired`; refs `pollRef`, `qrTimeoutRef`; funções `startPolling`, `stopPolling`, `handleRefreshQr`, `handleCancelQr`, `getQrSrc`; bloco JSX do QR com imagem, instruções, expiração e botão "Novo QR" |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | *(pendente)* | Frontend QR display + polling + Fase 2 webhook resilience |

---

### Fase 2 — Backend: webhook não-bloqueante

**Objetivo:** garantir que falha no setup do webhook não impeça o QR de chegar ao frontend

| Arquivo | O que mudou |
|---|---|
| `backend-crm/routes/whatsapp_connect.py` | `_set_whatsapp_webhook()` em `connect_whatsapp` e `refresh_qr` agora capturado em `try/except` — falha loga warning mas não aborta o retorno do QR |

---

## Checks de Validação

### Cenário P1 — QR code exibido ao clicar "Reconectar QR"
- [ ] Abrir AI Profile → aba "Conexão do número"
- [ ] Clicar "Reconectar QR"
- [ ] Confirmar: bloco de QR aparece com imagem escaneável

### Cenário P2 — Conexão detectada automaticamente
- [ ] QR exibido (P1 ok)
- [ ] Escanear com o celular
- [ ] Confirmar: status muda para "Conectado" sem refresh manual (polling 3s)

### Cenário P3 — QR expira após 90s
- [ ] QR exibido (P1 ok)
- [ ] Aguardar 90 segundos sem escanear
- [ ] Confirmar: QR é substituído por mensagem "QR code expirado" e botão "Novo QR code"
- [ ] Clicar "Novo QR code" → confirmar: novo QR aparece

### Cenário P4 — Webhook não configurado não bloqueia QR
- [ ] Remover `CRM_PUBLIC_BASE_URL` do `.env` do backend-crm
- [ ] Clicar "Reconectar QR"
- [ ] Confirmar: QR code aparece mesmo assim (webhook falha com warning no log)
