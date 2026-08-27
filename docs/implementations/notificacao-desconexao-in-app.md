# Notificação in-app (sino) de desconexão do WhatsApp

**Branch:** _(a definir no Plan Mode)_
**Status:** Aguardando Plan Mode

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`docs/implementations/alerta-desconexao-whatsapp.md`. Hoje o único aviso de
queda de conexão é por email. Uma notificação dentro do próprio CRM (ex.: um
sino no topo da interface) tornaria o aviso mais visível para quem usa o
sistema durante o dia e não checa email com frequência.

---

## Problemas Identificados (estado anterior)

1. **Sem superfície de notificação de conta:** o sistema de notificações do
   `frontend-crm` hoje é 100% lead-cêntrico (ex.: alertas dentro do card do
   lead) — não existe um mecanismo de notificação a nível de conta/utilizador
   para eventos como "WhatsApp desconectado".

---

## Diagnóstico (a fazer em Plan Mode)

- Definir onde a notificação in-app deve viver (sino global? banner
  persistente na página de Conexão?).
- Definir a fonte de dados: reaproveitar o `WhatsappConnection.status`
  já existente (backend-core) ou criar uma tabela de notificações de conta.
- Escopo maior que os outros itens desta lista — considerar tratar como
  feature própria, não como extensão pontual do alerta por email.

---

## Plano de Implementação

_A preencher após Plan Mode e aprovação do utilizador._
