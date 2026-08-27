# Notificação de reconexão bem-sucedida do WhatsApp

**Branch:** _(a definir no Plan Mode)_
**Status:** Aguardando Plan Mode

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`docs/implementations/alerta-desconexao-whatsapp.md`. Aquela implementação
envia um email ao utilizador quando a conexão WhatsApp cai
(`active → inactive`), mas fica silenciosa na transição inversa
(`inactive → active`) — o utilizador reconecta e não recebe nenhuma
confirmação de que voltou a funcionar.

---

## Problemas Identificados (estado anterior)

1. **Sem confirmação de reconexão:**
   `backend-core/app/api/whatsapp_instances.py::connection_event()` só dispara
   email quando `was_active and not is_active`; a transição
   `not was_active and is_active` não tem nenhuma acção associada.

---

## Diagnóstico (a fazer em Plan Mode)

- Reaproveitar o mesmo mecanismo de email (`render_*_email` +
  `connection_event()`), criando `render_whatsapp_reconnected_email()`.
- Decidir se deve disparar sempre que `inactive → active`, ou só quando a
  desconexão anterior tinha gerado um email de aviso (evitar notificar
  reconexões "normais" do fluxo inicial de conexão, que não são uma
  recuperação de queda).

---

## Plano de Implementação

_A preencher após Plan Mode e aprovação do utilizador._
