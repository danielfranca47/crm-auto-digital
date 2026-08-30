# Fix: gate de score de qualificação ignora campos desativados (`mode: "off"`)

**Branch:** `fix/qualification-score-gate-mode-off`
**Status:** Em andamento

---

## Motivação

Cliente reportou (conta `autodigital157@gmail.com`, testada em produção): um
lead avança de verdade na conversa real do WhatsApp — chega a receber link
de checkout, com sinais de intenção alta e aceitação de preço — mas o
Kanban continua a mostrar a categoria "Qualificação", nunca avançando.

Reproduzido ao vivo no Playground de produção com o AI Profile real da
conta (agente "Ana", `closer_agressivo`, `agent_mode=direto`). O
`decision_trace` da resposta mostrou:

```json
"qualification_advance_blocked": true,
"qualification_advance_blocked_reason": ["score_0_of_12_below_threshold_6"]
```

mesmo com a Mãe já tendo decidido `route_to="closing"` com
`price_acceptance="yes"` e `intent_level="high"`.

Causa raiz identificada: o AI Profile desta conta tem dois
`qualification_fields` configurados, **ambos com `"mode":"off"`**
(desativados na UI):

```json
{"key": "service_interest", "mode": "off", ...}
{"key": "availability_window", "mode": "off", ...}
```

`availability_window` é uma das 4 chaves clássicas que o gate de score
("4Ps") sabe pontuar (`_4P_SCORABLE_KEYS` em
`backend-crm/services/qualification_guardrails.py`).

---

## Problemas Identificados (estado anterior)

1. **Gate de score ignora `mode == "off"` (`qualification_guardrails.py:111-123`):**
   `_score_below_threshold()` decide se o gate de score 4P deve ser aplicado
   verificando se alguma das 4 chaves clássicas está "configurada" em
   `ai_profile.qualification_fields` — mas monta `_configured_keys` sem
   filtrar `f.get("mode") == "off"`:

   ```python
   _qfields = ai_profile.get("qualification_fields") or []
   _configured_keys = {f["key"] for f in _qfields if isinstance(f, dict) and "key" in f}
   if not _configured_keys or not (_configured_keys & _4P_SCORABLE_KEYS):
       return True, []  # bypass — perfil sem score real configurado
   ```

   Como `availability_window` ainda aparece no array (só desligada), o
   bypass pensado para perfis "100% custom" não dispara — o gate fica
   ativo. Como o campo está `off`, o bot nunca pergunta isso, o score nunca
   sai de 0, e o gate fica impossível de satisfazer para sempre: o lead
   nunca mais sai de `"qualification"` no Kanban.

   Confirmado (via exploração do código) que o bug está isolado nesta
   função — `can_advance_from_qualification()` e `can_advance_score_gate()`
   só herdam o problema por delegarem a ela. `compute_4p_scores()`
   (`qualification_state.py`) não tem o bug (não itera `qualification_fields`).
   Já existe a convenção correta em outro lugar do código
   (`backend-executors/app/services/decision_engine.py:1272`:
   `f.get("mode") != "off"`) — só não foi replicada aqui.

---

## Abordagem

Filtrar `mode == "off"` ao montar `_configured_keys` em
`_score_below_threshold()`, mirrorando a convenção já usada em
`decision_engine.py:1272`:

```python
_configured_keys = {
    f["key"] for f in _qfields
    if isinstance(f, dict) and "key" in f and f.get("mode") != "off"
}
```

Com isso, um perfil onde a única chave 4P configurada está `off` volta a
cair no bypass correto — igual a um perfil "100% custom" sem nenhuma chave
4P configurada. Se houver outra chave 4P ativa (`required`/`optional`), o
gate continua a funcionar normalmente.

---

## Plano de Implementação

### Fase 1 — Fix + teste de regressão

**Objetivo:** corrigir `_score_below_threshold()` e cobrir o cenário com teste

| Arquivo | O que muda |
|---|---|
| `backend-crm/services/qualification_guardrails.py` | `_score_below_threshold()` passa a excluir campos `mode == "off"` de `_configured_keys` |
| `backend-crm/tests/test_qualification_integrity_guardrails.py` | Novo teste: perfil com única chave 4P (`availability_window`) em `mode: "off"` → `can_advance_score_gate()` deve retornar `(True, [])` (bypass), não bloquear |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | _(a preencher)_ | fix: gate de score ignora campos qualification_fields desativados |

---

## Checks de Validação

### Cenário T1 — Teste automatizado de regressão
- [x] Rodar `backend-crm/tests/test_qualification_integrity_guardrails.py` — novo caso passa
- [x] Rodar suíte completa de `backend-crm/tests/` — 18 falhas pré-existentes, todas em
  arquivos não relacionados (meeting_management_gate, whatsapp_group_ignore,
  start_followup_transition, etc.) e causadas por problemas de ambiente (ex.:
  `ImportError: cannot import name 'APIRouter' from 'fastapi'`, `PermissionError`
  de arquivo temporário no Windows) — confirmado que já falhavam sem o fix (`git
  stash` + rerun). Nenhuma falha nos arquivos tocados por esta mudança.
- **Validado em:** 30/08/2026

### Cenário P1 — Reprodução no Playground (opcional, se o utilizador quiser confirmar ao vivo)
- [ ] Repetir a reprodução feita no diagnóstico (perfil `autodigital157@gmail.com`,
  mensagem de fechamento claro tipo "Perfeito, gostei. Como faço para começar?")
- [ ] Confirmar: `decision_trace.qualification_advance_blocked` passa a `false`
- [ ] Confirmar: categoria do lead sandbox avança para `closing`

---

## Fora do escopo

- Gate de campos obrigatórios (`can_advance_from_qualification`, verificação 1)
  não muda — já filtra corretamente por `required_fields`, que já exclui
  `mode == "off"` na origem.
- UI de qualificação (`AiProfile.tsx`) não muda — só o cálculo de "quais
  chaves contam como configuradas" para decidir se o gate de score 4P se
  aplica.
