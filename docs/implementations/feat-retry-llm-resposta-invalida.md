# Repetir a chamada à IA antes de cair no handoff

**Branch:** (a criar)
**Status:** Aguardando Plan Mode
**Origem:** pedido do utilizador em 26/10/2026, durante `fix-saudacao-hora-local`: a mensagem de handoff
aparece "com uma certa frequência" quando a IA falha ou não responde.

---

## Motivação

Quando a chamada à IA falha, o executor usa `FALLBACK_DECISION` (`decision_engine.py`, `next_action="handoff"`,
`reason="llm_failure"`). O cliente recebe o texto de handoff (`handoff_custom_text` do perfil ou
`HANDOFF_TEMPLATES` em `handoff_policy.py`) e, com `handoff_policy=disable_bot`, o bot fica desligado para esse
lead. Uma falha passageira acaba assim com o atendimento automático.

O utilizador pediu: em caso de falha ou sem resposta, tentar de novo pelo menos 3 vezes antes de ativar o handoff.

## O que já existe

- `backend-executors/app/services/llm_service.py` `_post_with_retry`: `_MAX_ATTEMPTS = 2`, só em erro de rede/
  timeout e status 429/500/502/503/504, com 1 s de espera.
- **Não** há nova tentativa quando a IA responde mas o conteúdo é inválido (JSON mal formado, campos em falta,
  `ValidationError` do `MotherDecision`/`ChildResult`). Essas exceções sobem até ao `except` de
  `decision_engine.py` (evento `llm_orchestrator_error`) e caem direto no handoff.

## A decidir no Plan Mode

- Número de tentativas (pedido: 3 além da primeira) e espera entre elas (exponencial?), sem passar o tempo
  máximo de resposta do WhatsApp/worker.
- Repetir só a etapa que falhou (Mãe ou Filha), não o turno todo.
- Medir antes: nos logs do `worker backend-executors` (Railway), contar `event=llm_orchestrator_error` e
  `llm_response_error` por motivo nos últimos dias, para saber que tipo de falha domina.

## Área do sistema

- `backend-executors/app/services/llm_service.py`, `backend-executors/app/services/decision_engine.py`
- Docs: `docs/architecture/llm-architecture.md`
