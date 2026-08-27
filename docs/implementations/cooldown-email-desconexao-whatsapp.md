# Cooldown/limite extra no email de desconexão do WhatsApp

**Branch:** _(a definir no Plan Mode)_
**Status:** Aguardando Plan Mode

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`docs/implementations/alerta-desconexao-whatsapp.md`. Hoje o único mecanismo
que evita reenviar o email repetidamente é a lógica de transição
(`active → inactive` dispara; eventos "disconnected" repetidos seguidos, com o
status já local `inactive`, não disparam de novo). Não existe uma protecção
adicional explícita (ex.: cooldown por tempo) para o caso de a conexão oscilar
repetidamente entre `active` e `inactive` em curto espaço de tempo (flapping),
o que geraria um email por ciclo.

---

## Problemas Identificados (estado anterior)

1. **Sem cooldown para flapping:** `connection_event()`
   (`backend-core/app/api/whatsapp_instances.py`) dispara o email sempre que
   detecta `was_active and not is_active`, sem janela mínima entre envios —
   se a sessão cair e reconectar várias vezes seguidas, cada ciclo gera um
   novo email.

---

## Diagnóstico (a fazer em Plan Mode)

- Avaliar se o flapping é um cenário real observado em produção ou só um
  risco teórico — decidir se vale a complexidade adicional agora.
- Se sim, decidir a janela de cooldown (ex.: não reenviar email para a mesma
  connection dentro de N minutos) e onde guardar o timestamp do último envio
  (novo campo em `WhatsappConnection` ou tabela separada).

---

## Plano de Implementação

_A preencher após Plan Mode e aprovação do utilizador._
