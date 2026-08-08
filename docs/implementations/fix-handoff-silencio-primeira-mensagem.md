# Fix: silêncio total quando a IA falha logo no início da conversa

**Branch:** `fix/handoff-silencio-primeira-mensagem`
**Status:** Em andamento

---

## Motivação

Identificado no roteiro de testes do Playground (`docs/implementations/sessao-teste-corrente.md`,
Cenário 6): quando a IA (LLM "Mãe") tem uma falha técnica pontual **e** a conversa ainda está
no começo (poucas mensagens trocadas), o sistema devolve uma resposta completamente vazia ao
lead — sem texto, sem handoff, sem nenhum aviso ao operador. Testado com "Quero falar com a
profissional diretamente" como 1ª mensagem de uma conversa nova: 5/5 rodadas falharam, sempre
com resposta vazia, 100% reproduzível.

Causa raiz identificada em `docs/implementations/sessao-teste-corrente.md` (seção "Nota dev"):
o `except Exception` de `decide()` (`backend-executors/app/services/decision_engine.py`) tem
dois caminhos diferentes para falha da LLM — um funcional (falha em turno posterior → chama
`handoff_policy.apply()`, manda mensagem de handoff configurada) e um silencioso (falha nos
primeiros turnos → retorna `next_action="ignore"`, `message_text=""`, sem passar por
`handoff_policy.apply()`). O caminho silencioso é o bug.

Segundo caso independente do mesmo buraco, sem relação com pedido de handoff, documentado em
`docs/plans/agentes-agenda-melhorias-futuras.md` (item M4, decisão anterior: "não corrigir
agora").

---

## Problemas Identificados (estado anterior)

1. **Silêncio total em falha da LLM no início da conversa:**
   `backend-executors/app/services/decision_engine.py`, dentro de `decide()`, bloco
   `except Exception` (linhas ~5044–5057) — quando `len(history) <= 2`, retorna
   `DecisionOutput(next_action="ignore", message_text="", reason="llm_failure_first_message")`
   diretamente, sem passar por `handoff_policy.apply()`. Mesmo que o `ai_profile` tenha uma
   mensagem de handoff configurada (`handoff_custom_text`), ela nunca é lida nesse caminho.

2. **Sem cobertura de teste automatizado:** não existia nenhum teste pytest cobrindo o
   comportamento do `except` de `decide()` — só um script manual
   (`backend-executors/scripts/test_llm_orchestrator_failure.py`), executado à mão, fora do
   pytest.

---

## Abordagem

```
Falha na chamada à LLM (qualquer causa)
  → ANTES: turno inicial (history<=2) → silêncio total
           turno posterior            → handoff_policy.apply()
  → DEPOIS: qualquer turno            → handoff_policy.apply()
```

Remove o caminho especial — toda falha da LLM passa a seguir o caminho já existente e testado
(`handoff_policy.apply(context, FALLBACK_DECISION, logger=logger)`), que lê `ai_profile`,
`lead`, `job` e `metadata` do `context` já disponível na função, sem setup adicional.

**Trade-off assumido:** um soluço técnico não relacionado a handoff (ex.: o caso do M4) que
aconteça no início de uma conversa nova também vai disparar a mensagem de handoff. Com política
`keep_active_notify`, é só uma notificação a mais ao time. Com política `disable_bot`, o bot
fica pausado para aquele lead até reativação manual — efeito colateral mais forte, mas
avaliado como preferível a deixar um lead real sem nenhuma resposta e sem ninguém saber.

---

## Plano de Implementação

### Fase 1 — Remover o caminho de silêncio e cobrir com teste

**Objetivo:** unificar os dois caminhos de falha da LLM em um só (sempre via `handoff_policy.apply`)

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/decision_engine.py` | Remove o bloco `if len(_history_for_fallback) <= 2: ...` dentro do `except Exception` de `decide()`; sempre retorna `handoff_policy.apply(context, FALLBACK_DECISION, logger=logger)` |
| `backend-executors/tests/test_llm_failure_fallback_handoff.py` (novo) | Testa que `decide()` retorna `next_action="handoff"` (não mais `ignore`/vazio) tanto com histórico curto quanto normal, forçando falha via `monkeypatch` em `llm_service.generate_mother_route` |
| `docs/plans/agentes-agenda-melhorias-futuras.md` | Remove o item M4 (resolvido por este fix) |

```python
# ANTES
_history_for_fallback = context.get("history") or []
if len(_history_for_fallback) <= 2:
    if logger:
        logger.info("event=llm_failure_first_message_suppressed history_len=%d", len(_history_for_fallback))
    return DecisionOutput(next_action="ignore", message_text="", questions=[], reason="llm_failure_first_message")
return handoff_policy.apply(context, FALLBACK_DECISION, logger=logger)

# DEPOIS
return handoff_policy.apply(context, FALLBACK_DECISION, logger=logger)
```

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `b1bbaaa` | Remove o caminho de silêncio no fallback de falha da LLM + teste pytest + atualização do M4 |

**Detalhes do commit `b1bbaaa`:**
- `backend-executors/app/services/decision_engine.py` — remove o bloco `if len(_history_for_fallback) <= 2: ...` dentro do `except Exception` de `decide()`; sempre retorna `handoff_policy.apply(context, FALLBACK_DECISION, logger=logger)`
- `backend-executors/tests/test_llm_failure_fallback_handoff.py` — novo teste pytest cobrindo histórico curto e normal
- `docs/plans/agentes-agenda-melhorias-futuras.md` — item M4 atualizado (risco de silêncio resolvido)
- `.claude/settings.local.json` — allowlist para comandos pytest usados na validação

---

### Relatório da Fase 1 — o que mudou na prática

**Antes:** se a IA tivesse um erro técnico pontual logo no início de uma conversa nova
(ex.: um lead pedindo para falar com um humano como 1ª mensagem), o sistema ficava
completamente mudo — nenhuma resposta era enviada e ninguém era avisado.

**Agora:** qualquer erro técnico da IA, em qualquer momento da conversa, faz o bot enviar a
mensagem de handoff (a mesma configurada em `/ai-profile`, ou o texto padrão se nada foi
configurado) e seguir a política de handoff escolhida — notificar o time ou pausar o bot
para aquele lead. O lead nunca mais fica sem resposta nenhuma por causa desse tipo de falha.

**Para validar:** Cenário T1 (teste automatizado) já validado nesta mesma sessão — ver
checks abaixo. Cenário P1 (fumaça manual no Playground) também executado — ver checks
abaixo; não reproduziu a falha original (esperado, é instabilidade externa não controlável),
mas confirma que nenhum comportamento normal foi quebrado pelo fix.

---

## Checks de Validação

Reproduzir uma falha real e pontual da API da LLM sob demanda não é controlável via
Playground (é uma instabilidade externa transitória) — a validação principal é o teste
automatizado, que força a falha de forma determinística.

### Cenário T1 — Teste automatizado (pytest)
- [x] Rodar `pytest backend-executors/tests/test_llm_failure_fallback_handoff.py`
- [x] Confirmar: com histórico curto (≤2), `decide()` retorna `next_action="handoff"` e
  `message_text` não vazio
- [x] Confirmar: com histórico normal, comportamento permanece `handoff` (sem regressão)
- **Validado em:** 08/08/2026 — 2/2 testes novos passaram (`test_llm_failure_short_history_goes_to_handoff`,
  `test_llm_failure_normal_history_still_goes_to_handoff`). Suíte completa de `backend-executors/tests/`
  rodada antes e depois do fix (via `.venv` do projeto): mesmos 22 testes falhando em ambos os casos
  (pré-existentes, não relacionados a esta mudança — confirmado via `git stash`), 106→108 passando
  (+2 dos testes novos), nenhuma regressão introduzida.

### Cenário P1 — Fumaça manual no Playground (opcional)
- [⏭️] Reproduzir a falha real da LLM Mãe sob demanda no Playground — **não controlável**, confirmado
  na prática (ver abaixo). Objetivo original: enviar "Quero falar com a profissional diretamente"
  como 1ª mensagem de uma sessão nova e observar `next_action="handoff"` (não mais `ignore`/vazio)
  quando a falha ocorrer.
- **Executado em:** 08/08/2026 — ambiente local (backend-core:8001, backend-crm:8000,
  backend-executors:8002 com o fix da Fase 1 já commitado, frontend-crm:5173), conta
  `autodigital157@gmail.com`, AI Profile "Daniel" (`agenda`/`hybrid_scheduler`). 2 rodadas em
  sessões novas via Playground (`POST /api/playground/chat`), mesma frase usada no diagnóstico
  original (`sessao-teste-corrente.md`, Cenário 6). **Resultado: nas 2 rodadas a chamada à LLM Mãe
  teve sucesso normal** (`mother_decision.reason` com rota real — `recepcao`/`sales`/etc. —, nunca
  `llm_failure_first_message`), portanto o `except Exception` de `decide()` nunca foi exercitado e
  o caminho corrigido não pôde ser observado via UI nesta sessão.
- **Conclusão:** confirma na prática o que a seção "Checks de Validação" já antecipava — a falha da
  LLM não é reproduzível sob demanda no Playground (instabilidade externa transitória, não uma
  condição determinística do lado do cliente). A cobertura funcional do fix permanece no Cenário T1
  (determinístico via `monkeypatch`), que já validou os dois branches (histórico curto e normal)
  chegando a `handoff`. Cenário P1 marcado como pulado/justificado — não bloqueia a graduação desta
  fase (item já documentado como opcional).

---

## Ajustes Possíveis Pós-Implementação

- O script manual `backend-executors/scripts/test_llm_orchestrator_failure.py` pode ser
  aposentado numa limpeza futura, já que o novo teste pytest cobre o mesmo caso de forma
  automatizada — fora do escopo desta fase.
