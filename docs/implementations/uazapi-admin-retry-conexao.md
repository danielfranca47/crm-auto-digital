# Retry em 429/503 nas operações de conexão de instância (uazapi_admin.py)

**Branch:** _(a definir no Plan Mode)_
**Status:** Aguardando Plan Mode

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

## Diagnóstico (a fazer em Plan Mode)

- Confirmar se faz sentido reaproveitar o helper `_request_with_retry` de
  `uazapi_client.py` (hoje específico daquele módulo) ou criar um equivalente
  síncrono/adaptado para `uazapi_admin.py::_request`.
- Definir se o retry aqui deve ser mais curto/agressivo que o de envio (UX
  interativa — usuário está com a tela de QR code aberta esperando), ou se
  deve continuar propagando rápido e deixar o frontend (`ConexaoNumero.tsx`,
  que já faz polling a cada 3s) lidar com a nova tentativa.
- Revisar se isso conflita com o comportamento documentado em
  `whatsapp-connection.md` (timeouts client-side de 90s/280s para QR/código
  de pareamento).

---

## Plano de Implementação

_A preencher após Plan Mode e aprovação do utilizador._
