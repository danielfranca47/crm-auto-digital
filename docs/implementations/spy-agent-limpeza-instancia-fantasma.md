# Investigar/corrigir acúmulo de instância fantasma no Agente Espião

**Branch:** A definir (`fix/<slug>`, decidido no Plan Mode)
**Status:** Aguardando Plan Mode

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`docs/implementations/uazapi-instancias-fantasmas.md`.

Naquela implementação, corrigimos duas causas confirmadas de instância
fantasma na UazAPI (reinit de `whatsapp_connect.py` abandonando a instância
antiga; remoção de colaborador monitorado nunca desconectando na UazAPI) —
ver [`docs/architecture/whatsapp-connection.md`](../architecture/whatsapp-connection.md#apagar-instância--limpeza-de-fantasmas).

O Agente Espião (`backend-crm/routes/spy_agent.py`) tem um padrão de conexão
temporária parecido (janela de observação de 14 dias, 1 instância por
conta) e já está documentado como duplicando lógica própria de
extração de QR, independente do fluxo normal — mas **não foi confirmado**
se ele também abandona instâncias na UazAPI quando a janela expira ou é
encerrada manualmente.

## O que investigar (Plan Mode)

- Ler `backend-crm/routes/spy_agent.py` e `services/spy_agent/*` para
  mapear todo ponto que cria (`init`) ou encerra uma instância de agente
  espião.
- Confirmar se existe (ou não) alguma chamada de limpeza quando a janela de
  14 dias expira ou o usuário encerra manualmente.
- Se confirmado o mesmo problema: reaproveitar
  `delete_core_whatsapp_instance()` (já existe em `backend-crm/core_client.py`,
  criado na implementação graduada acima) no ponto de encerramento — mesmo
  padrão não-bloqueante usado em `whatsapp_connect.py` e `collab_monitor.py`.
