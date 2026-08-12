# Backoff exponencial em 429/503 + validação E.164 do número de destino

**Branch:** _(a definir no Plan Mode)_
**Status:** Aguardando Plan Mode

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`etapa-uazapi-migracao-plano-pago.md`. Com a migração para o servidor pago da
UazAPI concluída e 2 clientes reais prestes a conectar, reduzir o risco de
mensagens perdidas por rate-limit ou número mal formatado passa a ter
prioridade — no plano free isso era tolerável, com clientes pagantes não é.

Dois problemas distintos, ambos em `backend-core`:

1. **Sem retry em rate-limit:** `backend-core/app/services/uazapi_admin.py`
   (`_request`, linha ~168) propaga erros 429/503 da UazAPI diretamente para o
   chamador, sem nenhuma tentativa automática de repetir a chamada. Um pico de
   tráfego (múltiplos leads sendo atendidos ao mesmo tempo) pode gerar falha
   silenciosa de envio.

2. **Sem validação de formato do número:** `backend-core/app/api/whatsapp_send.py`
   (linha ~123) só remove caracteres de formatação (espaços, traços,
   parênteses) do número de destino, sem validar se o resultado é um número
   E.164 válido. Números malformados geram chamadas pagas à UazAPI que falham
   de qualquer forma.

---

## Diagnóstico (a fazer em Plan Mode)

- Confirmar o formato exato dos erros 429/503 retornados pela UazAPI paga
  (`digitalpro.uazapi.com`) — pode diferir do free.
- Definir a política de backoff (nº de tentativas, delays) e se deve ser
  configurável por env var.
- Definir regex/validação E.164 e onde ela deve recusar (antes ou depois de
  outras validações existentes em `whatsapp_send.py`).

---

## Plano de Implementação

_A preencher após Plan Mode e aprovação do utilizador._
