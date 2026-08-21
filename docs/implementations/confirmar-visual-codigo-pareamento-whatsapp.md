# Confirmar visual do código de pareamento na UI

**Status:** Aguardando Plan Mode

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`docs/implementations/pareamento-codigo-whatsapp-login.md` (código de
pareamento como alternativa ao QR).

A Fase 2 dessa implementação (bloco de exibição do código em
`frontend-crm/src/components/agente/ConexaoNumero.tsx`) foi validada por
type-check e por teste ao vivo da mecânica (toggle, input, geração) — mas
sempre contra uma instância já conectada, então o bloco estilizado que
renderiza `qrPayload.pair_code` como texto grande (com o CSS/layout real)
nunca chegou a ser visto na tela com um código populado de verdade.

O objetivo aqui é só a checagem visual — a lógica já está implementada e
validada; não é esperado nenhum código novo, só confirmar (e ajustar CSS se
necessário) na próxima vez que a usuária precisar reconectar o WhatsApp de
verdade.
