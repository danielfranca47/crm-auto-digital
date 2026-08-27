# Logs INFO invisíveis em todo o backend-crm

**Branch:** _(a definir no Plan Mode)_
**Status:** Aguardando Plan Mode

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`docs/implementations/alerta-desconexao-whatsapp.md`. Durante o teste ao vivo
dessa implementação (Cenário C3, 24/08/2026), descobriu-se que nenhum lugar do
`backend-crm` configura o nível do root logger (`logging.basicConfig` ou
equivalente) — todo `logger.info(...)` do código da aplicação (não só do
código daquela feature) fica invisível tanto em ambiente local quanto em
produção, mesmo rodando `uvicorn --log-level info` (essa flag só afeta os
loggers internos do uvicorn, não o root logger da aplicação).

Isto tem impacto directo em qualquer diagnóstico futuro: qualquer bug que
dependa de ler logs `INFO` (a maioria dos logs de negócio do sistema, ex.:
`uazapi webhook event=...`) é invisível hoje, obrigando a promover
temporariamente para `warning` sempre que se precisa de visibilidade (como foi
feito pontualmente na correção acima).

---

## Problemas Identificados (estado anterior)

1. **Root logger sem nível configurado:** `backend-crm` não tem nenhum
   `logging.basicConfig(level=...)` ou configuração equivalente no startup —
   confirmado durante o teste da implementação `alerta-desconexao-whatsapp.md`.

---

## Diagnóstico (a fazer em Plan Mode)

- Confirmar onde adicionar a configuração (ponto de entrada da app, ex.:
  `main.py`/`app.py` do `backend-crm`).
- Decidir o nível apropriado para produção (`INFO` vs. manter `WARNING` e ser
  mais seletivo sobre quais logs promover) — activar `INFO` globalmente torna
  os logs de produção mais verbosos, incluindo logs pré-existentes que hoje
  ninguém vê.
- Verificar se algum log `INFO` existente contém dados sensíveis que não
  deveriam ficar visíveis em produção antes de activar globalmente.

---

## Plano de Implementação

_A preencher após Plan Mode e aprovação do utilizador._
