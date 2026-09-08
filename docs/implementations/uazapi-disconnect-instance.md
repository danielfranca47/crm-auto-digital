# `disconnect_instance()` — logout sem apagar a instância

**Branch:** A definir (`feat/<slug>`, decidido no Plan Mode)
**Status:** Aguardando Plan Mode

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`docs/implementations/uazapi-instancias-fantasmas.md`.

Naquela implementação adicionamos `uazapi_admin.delete_instance()` (apaga a
instância permanentemente — ver
[`whatsapp-connection.md`](../architecture/whatsapp-connection.md#apagar-instância--limpeza-de-fantasmas)),
mas não `disconnect_instance()` (logout — a UazAPI também expõe `POST
/instance/disconnect`, confirmado via código-fonte do node n8n
`n8n-nodes-uazapi` durante aquela investigação). Não implementamos por não
haver caso de uso identificado na altura.

## O que avaliar (Plan Mode)

- Levantar se existe hoje algum fluxo do produto que precise de "desconectar
  sem perder a instância/token" (ex.: um botão de "desconectar" no
  `frontend-crm` distinto de apagar/reconectar) — hoje o único controlo que
  o usuário final tem é reconectar via QR/pareamento.
- Se não houver caso de uso real, este item pode ser descartado em vez de
  implementado — confirmar com o usuário antes de prosseguir.
