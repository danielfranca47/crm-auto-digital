# Robustez da decisão da Mãe — enum tolerante (M4) + gate de confirmação de agendamento (M3)

**Branch:** `main`
**Status:** Em andamento

---

## Motivação

Duas falhas registadas em `docs/plans/agentes-agenda-melhorias-futuras.md` (secções M3 e M4),
identificadas em sessões de teste manual e via browser:

- **M4:** quando a LLM Mãe devolve um valor fora do enum em `next_action_hint` (ex.: `"confirmar"`
  em vez de `"reply"`), o `pydantic.ValidationError` derruba a decisão inteira do turno — o lead
  fica sem resposta, sem nenhum alerta visível.
- **M3:** a criação de um appointment depende só de `mother_decision.signals.meeting_scheduled`
  de um turno isolado, sem nenhuma verificação de que o lead já passou por uma proposta de
  horário antes. Em teste real, a Mãe marcou `meeting_scheduled=true` já na 1ª mensagem do lead
  (um pedido, não confirmação) e, noutro teste, no mesmo turno em que a filha de agendamento
  ainda negociava outro horário.

Decisão explícita do utilizador: corrigir as duas, mas com solução **estrutural** (estado de
turno/sequência), não **linguística** (listas de palavras-chave/sinónimos) — a plataforma é
multinichos, e qualquer correção baseada em texto livre exigiria manutenção infinita por
nicho/idioma. Confirmado também que o gate do M3 deve ficar **agnóstico de rota** — hoje não
existe nenhuma restrição por `route_to` sobre quem pode reivindicar `meeting_scheduled=true`
(a filha de apresentação já cria appointments reais via Fix P8 quando
`presentation_variant=scheduler`, default para `agent_mode=agenda`), e não se quer arriscar
quebrar esse caminho real.

---

## Problemas Identificados (estado anterior)

1. **Enum fechado sem tolerância (`orchestrator_models.py:16`):** `MotherDecision.next_action_hint`
   é `Literal["reply","ask_qualification","handoff","ignore","greet"]`. Qualquer valor fora disso
   levanta `ValidationError` em `MotherDecision.model_validate()`, capturado pelo `except Exception`
   genérico de `decide()` (`decision_engine.py:4776`) — a decisão inteira (não só o campo) cai no
   fallback `llm_failure_first_message_suppressed`/handoff.
2. **Sem estado de "já propusemos este horário" (`meeting_scheduler.py:399`):**
   `handle_meeting_scheduled()` cria o appointment e desativa o bot com base num único booleano
   por turno, sem considerar se este é o primeiro turno do lead nesta fase. O cálculo que já
   existe para "é a primeira vez que o lead toca esta fase" (`_is_phase_entry`,
   `decision_engine.py:4117`) nunca chega ao `decision_trace` nem ao `meeting_scheduler`.

---

## Abordagem

```
Mãe devolve JSON
  ├─ next_action_hint fora do enum → validador Pydantic (mode="before") substitui por None,
  │    loga aviso, decisão do turno segue normalmente (M4)
  └─ meeting_scheduled=true
       → compose_decision_output() expõe is_phase_entry no decision_trace (já calculado)
       → meeting_scheduler.handle_meeting_scheduled() lê is_phase_entry
            ├─ True  (lead a entrar nesta fase agora) → NÃO cria appointment, NÃO desativa bot,
            │          resposta natural da filha (proposta/negociação) segue ao lead (M3)
            └─ False (lead já estava nesta fase antes) → cria appointment normalmente
```

---

## Plano de Implementação

### Fase 1 — M4: validador tolerante para enums opcionais da Mãe

**Objetivo:** um valor fora do enum em campo opcional degrada para `None` em vez de derrubar o turno inteiro.

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/orchestrator_models.py` | Novo dict `_OPTIONAL_ENUM_FIELDS` + `field_validator(mode="before")` em `MotherDecision` para `next_action_hint`, `agent_mode`, `compound_follow_through`, `perceived_category` |

```python
# ANTES — qualquer valor fora do enum derruba a decisão inteira do turno
next_action_hint: Optional[Literal["reply", "ask_qualification", "handoff", "ignore", "greet"]] = None

# DEPOIS — valor fora do enum degrada para None (já tratado como default no resto do código)
@field_validator(*_OPTIONAL_ENUM_FIELDS.keys(), mode="before")
@classmethod
def _coerce_unknown_enum_to_none(cls, value, info):
    if value is None:
        return None
    allowed = _OPTIONAL_ENUM_FIELDS.get(info.field_name)
    if allowed is not None and value not in allowed:
        logger.warning("event=mother_decision_invalid_enum_coerced field=%s value=%r", info.field_name, value)
        return None
    return value
```

`route_to` (obrigatório, sem default seguro) fica fora — continua a falhar e a cair no
retry/fallback existente, como hoje.

### Fase 2 — M3: gate estrutural de confirmação de agendamento

**Objetivo:** só criar appointment real quando o lead já estava nesta fase antes desta mensagem.

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/decision_engine.py` | `compose_decision_output()` — expõe `decision.decision_trace["is_phase_entry"] = _is_phase_entry` junto ao cálculo já existente (~linha 4120) |
| `backend-executors/app/services/meeting_scheduler.py` | `MeetingSignal` — novo campo `is_phase_entry: bool`; `_extract_meeting_signal()` lê `decision_trace.get("is_phase_entry", False)`; `handle_meeting_scheduled()` — early-return sem side-effects quando `signal.is_phase_entry=True` |

---

## Checks de Validação

### Cenário C1 — M4: next_action_hint inválido não derruba o turno
- [x] Forçar `next_action_hint` fora do enum diretamente em `MotherDecision.model_validate(...)`
- [x] Confirmar: não levanta `ValidationError` (em vez de mockar `llm_service` e correr `decide()` completo)
- [x] Confirmar: campo resultante é `None` + log `event=mother_decision_invalid_enum_coerced`
- [x] Confirmar (regressão): `route_to` fora do enum continua a levantar `ValidationError` normalmente
- **Validado em:** 20/06/2026 — smoke test directo ao schema (`MotherDecision.model_validate`): `next_action_hint="confirmar"` → `None` + log emitido; `next_action_hint="reply"` → mantém `"reply"`; `route_to="lixo"` → `ValidationError` (comportamento inalterado, como esperado).

### Cenário C2 — M3: appointment não criado na entrada da fase
- [ ] Lead novo cuja 1ª mensagem já contém dia/hora (ex.: "quero agendar amanhã às 15h") com `meeting_scheduled=true` da Mãe
- [ ] Confirmar: appointment NÃO é criado neste turno, bot não é desativado
- [ ] Confirmar: log `event=meeting_scheduled_deferred_phase_entry`

### Cenário C3 — M3: appointment criado normalmente quando já estava na fase
- [ ] Mesmo lead, turno seguinte, já com `lead.category="agendamento"`, `meeting_scheduled=true`
- [ ] Confirmar: appointment criado, bot desativado (comportamento idêntico ao actual)

### Cenário C4 — Regressão da suite existente
- [x] `pytest tests/ scripts/test_meeting_scheduler_hook.py scripts/test_meeting_candidate_e2e.py scripts/test_structured_meeting_signal_dual_read.py scripts/test_mother_prompt_agent_mode.py -q` não introduz falhas novas
- **Validado em:** 20/06/2026 (Fase 1) — 25 falhas / 65 passes antes e depois da mudança de M4 (confirmado via `git stash`/`git stash pop`); as 25 falhas são pré-existentes e não relacionadas (ex.: `FakeCRMClient.create_lead_appointment() got an unexpected keyword argument 'source'` — fixture desatualizada de uma feature anterior, fora do escopo desta correção).

---

## Ajustes Possíveis Pós-Implementação

- Trade-off aceite: quando o lead confirma um horário na MESMA mensagem em que a Mãe move a
  categoria para a fase de agendamento (ex.: após negociar disponibilidade em pré-agendamento,
  diz "perfeito, pode confirmar às 15h" e a Mãe transiciona a categoria nesse mesmo turno), a
  criação do appointment fica diferida para mais um turno. Custa uma troca extra num caso
  legítimo, em troca de eliminar os falsos positivos relatados.
- Fora de escopo (registado em `docs/plans/agentes-agenda-melhorias-futuras.md`): a "Regra 3"
  de intenção de agendamento (`decision_engine.py:4245-4296`) usa listas de palavras-chave em
  português (`decision_engine.py:3606-3627`) — solução rígida e acoplada a nicho/idioma que não
  foi estendida nem copiada nesta correção.
