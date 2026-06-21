# Robustez da decisão da Mãe — enum tolerante (M4) + gate de confirmação de agendamento (M3)

**Branch:** `main`
**Status:** Todos os cenários validados

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

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `b84ce18` | M4: validador tolerante de enums opcionais em `MotherDecision` |

**Detalhes do commit `b84ce18`:**
- `backend-executors/app/services/orchestrator_models.py` — `_OPTIONAL_ENUM_FIELDS` + `field_validator(mode="before")` em `MotherDecision`
- `docs/implementations/fix-robustez-decisao-mae-multinicho.md` — arquivo criado

### Fase 2 — M3: gate estrutural de confirmação de agendamento

**Objetivo:** só criar appointment real quando o lead já estava nesta fase antes desta mensagem.

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/decision_engine.py` | `compose_decision_output()` — expõe `decision.decision_trace["is_phase_entry"] = _is_phase_entry` junto ao cálculo já existente (~linha 4120) |
| `backend-executors/app/services/meeting_scheduler.py` | `MeetingSignal` — novo campo `is_phase_entry: bool`; `_extract_meeting_signal()` lê `decision_trace.get("is_phase_entry", False)`; `handle_meeting_scheduled()` — early-return sem side-effects quando `signal.is_phase_entry=True` |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `57c8ab2` | M3: gate `is_phase_entry` em `compose_decision_output()` + `handle_meeting_scheduled()` |

**Detalhes do commit `57c8ab2`:**
- `backend-executors/app/services/decision_engine.py` — `compose_decision_output()` expõe `decision.decision_trace["is_phase_entry"]`
- `backend-executors/app/services/meeting_scheduler.py` — `MeetingSignal.is_phase_entry`; early-return em `handle_meeting_scheduled()` quando `True`
- `docs/implementations/fix-robustez-decisao-mae-multinicho.md` — checks C2/C3/C4 marcados

### Relatório das Fases 1+2 — o que mudou na prática

**Antes:** se a IA "Mãe" (a camada que decide o que fazer a cada mensagem) devolvesse um valor inesperado num campo opcional, o sistema travava a decisão inteira daquele turno — o lead simplesmente não recebia resposta, sem nenhum aviso visível do motivo. Além disso, a criação de um compromisso na agenda dependia só de um sinal isolado da Mãe num único turno, sem checar se aquele lead já tinha mesmo passado por uma proposta de horário antes — em teste real, isso quase fez o sistema marcar um compromisso "confirmado" já na primeira mensagem do cliente, antes de qualquer proposta real ter sido feita.
**Agora:** um valor inesperado num campo opcional já não derruba a resposta — o sistema ignora só aquele campo e segue normalmente. E o compromisso só é criado de verdade quando o lead já estava numa conversa avançada sobre agendamento antes desta mensagem, não na primeira vez que o assunto aparece.
**Para validar:** confirmado por testes técnicos directos (sem precisar reproduzir pela tela) — Cenários C1 a C4. A confirmação visual completa pela tela real ficou coberta pelas Fases 3+4, abaixo.

---

## Checks de Validação

### Cenário C1 — M4: next_action_hint inválido não derruba o turno
- [x] Forçar `next_action_hint` fora do enum diretamente em `MotherDecision.model_validate(...)`
- [x] Confirmar: não levanta `ValidationError` (em vez de mockar `llm_service` e correr `decide()` completo)
- [x] Confirmar: campo resultante é `None` + log `event=mother_decision_invalid_enum_coerced`
- [x] Confirmar (regressão): `route_to` fora do enum continua a levantar `ValidationError` normalmente
- **Validado em:** 20/06/2026 — smoke test directo ao schema (`MotherDecision.model_validate`): `next_action_hint="confirmar"` → `None` + log emitido; `next_action_hint="reply"` → mantém `"reply"`; `route_to="lixo"` → `ValidationError` (comportamento inalterado, como esperado).

### Cenário C2 — M3: appointment não criado na entrada da fase
- [x] Simulado via `handle_meeting_scheduled()` directo: `decision_trace={"meeting_scheduled": True, "is_phase_entry": True}`, lead em `category="qualification"`
- [x] Confirmar: appointment NÃO é criado neste turno, bot não é desativado (`return None`, sem side-effects)
- [x] Log emitido: `event=meeting_scheduled_deferred_phase_entry` (confirmado por inspecção do código; não capturado no smoke test por não usar `logger=`)
- **Validado em:** 20/06/2026 — smoke test directo a `meeting_scheduler.handle_meeting_scheduled()` com `FakeClient`: `client.created == []` e `client.bot_disabled_calls == []`.
- **Pendente:** validação ponta-a-ponta real (Playground/WhatsApp) com uma 1ª mensagem de lead novo contendo dia/hora — requer o utilizador correr o cenário real.

### Cenário C3 — M3: appointment criado normalmente quando já estava na fase
- [x] Mesmo teste directo, agora com `lead.category="agendamento"` e `is_phase_entry=False`
- [x] Confirmar: appointment criado, bot desativado (comportamento idêntico ao actual)
- **Validado em:** 20/06/2026 — smoke test directo: `client.created` populado e `client.bot_disabled_calls == [(1, True, "meeting_scheduled")]`.

### Cenário C4 — Regressão da suite existente
- [x] `pytest tests/ scripts/test_meeting_scheduler_hook.py scripts/test_meeting_candidate_e2e.py scripts/test_structured_meeting_signal_dual_read.py scripts/test_mother_prompt_agent_mode.py -q` não introduz falhas novas
- **Validado em:** 20/06/2026 (Fase 1 e Fase 2) — 25 falhas / 65 passes antes e depois das duas mudanças (confirmado via `git stash`/`git stash pop` antes da Fase 1; recontagem idêntica após a Fase 2). As 25 falhas são pré-existentes e não relacionadas (ex.: `FakeCRMClient.create_lead_appointment() got an unexpected keyword argument 'source'` — fixture desatualizada de uma feature anterior, fora do escopo desta correção).

---

## Fase 3 — Diagnóstico + Correção: pré-agendamento não avança para agendamento (20/06/2026)

### Problema identificado

Ao validar o Cenário C2 via UI real (Playground, MCP chrome-devtools), um lead novo com
1ª mensagem "Oi, gostaria de agendar uma sessão para amanhã às 15h" (dia+hora específicos)
recebeu uma resposta sem sentido: "Posso te mandar uma mensagem amanhã de manhã para
confirmar a sessão?" — a filha de pré-agendamento tratou um pedido com horário já definido
como se fosse um interesse tentativo sem data.

Causa raiz dupla:
1. **Code gap:** `_build_child_prompt_pre_agendamento()` já instrui a filha — "se o lead der
   dia/hora específica, use `recommended_next_category='agendamento'`" — mas nenhum código
   lia esse campo quando `effective_route_to=="pre-agendamento"`. O mecanismo de
   "homologação" existente só cobria `qualification→apresentation` e
   `apresentation→{pre-agendamento,agendamento,follow-up}`; faltava o elo
   `pre-agendamento→agendamento`.
2. **Prompt mal-priorizado:** a secção "FLUXO DE CONVERSA" do mesmo prompt tinha 3 passos
   pensados para interesse tentativo, com frase-exemplo literal ("Posso te mandar uma
   mensagem [dia anterior] de manhã...") que dominava a resposta mesmo quando a regra
   posterior dizia para agir diferente.

### Correção

| Arquivo | Mudança |
|---|---|
| `backend-executors/app/services/decision_engine.py` (`compose_decision_output()`) | Novo bloco homologação `pre-agendamento → agendamento`, espelhando o de `apresentation`, logo depois dele |
| `backend-executors/app/services/decision_engine.py` (`_build_child_prompt_pre_agendamento()`) | Verificação "dia+hora específicos" movida para o TOPO do prompt, como exceção explícita que pula o FLUXO DE CONVERSA tentativo |
| `backend-executors/app/services/decision_engine.py` (`_build_mother_prompt()`, secção SAUDAÇÃO COMPOSTA) | 1 linha de cross-reference: ao escolher `compound_follow_through` para intenção de agendamento, aplicar a mesma distinção dia/hora da PRIORIDADE 2 (sem data → pre-agendamento; com dia/hora → agendamento direto) |
| `backend-executors/tests/test_pre_agendamento_recommended_next_category.py` | Novo arquivo, 3 cenários (avança/não avança por incompletude/não avança por categoria fora do schema) |

Nota: tentei também reforçar a instrução de saudação composta dentro deste mesmo prompt
("LEMBRETE FINAL") — revertido na Fase 4 (ver abaixo), substituído por uma chamada LLM
separada à recepção.

### Commits Fase 3

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `a07fd45` | Commitada junto com a Fase 4 — ver detalhes abaixo |

---

## Fase 4 — Diagnóstico + Correção: recepção responde primeiro em saudação composta (20/06/2026)

### Problema identificado

Revalidando o Cenário C2 após a Fase 3, a resposta melhorou substancialmente (já não dizia
"vou mandar mensagem amanhã"), mas continuava sem nenhum cumprimento — confirmado pelo
utilizador via observação directa da sessão no Playground. A instrução "ABERTURA DE
SAUDAÇÃO COMPOSTA" (injectada no prompt da filha comercial desde
`fix-compound-follow-through-recepcao.md`) chega de facto ao prompt (confirmado isolando
`_build_daughter_identity_block()`), mas a LLM não a seguia com confiança suficiente quando
o resto do prompt (fluxo + exemplo concreto) é mais longo e específico — não era um gap de
código, era a LLM a ignorar uma instrução entre várias.

Decisão do utilizador (`AskUserQuestion`, 3 opções apresentadas): em vez de reforçar ainda
mais a mesma instrução (mecanismo já comprovadamente não confiável) ou reverter para o
comportamento pré-fix (lead precisa mandar 2ª mensagem), optou por **2 chamadas LLM, 2
bolhas** — a filha recepção responde primeiro (só o cumprimento, prompt já existente e
restrito), depois a filha comercial trata o pedido.

### Correção

| Arquivo | Mudança |
|---|---|
| `backend-executors/app/services/decision_engine.py` (`decide()`, bloco `if _follow_through:`) | Chamada separada e best-effort (`try/except`) a `_build_child_prompt_recepcao()` + `llm_service.generate_child_result("recepcao", ...)`; resultado guardado em `context["_compound_greeting_text"]` |
| `backend-executors/app/services/decision_engine.py` (`decide()`, antes de `compose_decision_output(...)`) | Se `_compound_greeting_text` existir, prefixa `child_result.message_text`/`question_text` com `"{saudação}\n\n{texto comercial}"` — a divisão em bolhas distintas é feita pelo mecanismo de humanização já existente |
| `backend-executors/app/services/decision_engine.py` (`_build_daughter_identity_block()`, `_build_child_prompt_pre_agendamento()`) | Removidas as instruções "ABERTURA DE SAUDAÇÃO COMPOSTA" / "LEMBRETE FINAL" — ficaram redundantes e causariam saudação duplicada |
| `backend-executors/tests/test_compound_follow_through_routing.py` | Mock de `generate_child_result` passa a diferenciar por `route` (1º arg); asserções actualizadas para o texto prefixado |

```python
# decide() — dentro de `if _follow_through:`, depois de route_for_child = _follow_through
try:
    _greeting_prompt = _build_child_prompt_recepcao(context, message_text, mother_decision)
    _greeting_text_raw = llm_service.generate_child_result("recepcao", _greeting_prompt)
    _greeting_payload = _extract_json_payload(_greeting_text_raw)
    _greeting_text = str((_greeting_payload or {}).get("message_text") or "").strip()
    if _greeting_text:
        context["_compound_greeting_text"] = _greeting_text
except Exception:
    pass

# decide() — antes de compose_decision_output(...)
_greeting_prefix = context.get("_compound_greeting_text")
if _greeting_prefix:
    if child_result.message_text:
        child_result.message_text = f"{_greeting_prefix}\n\n{child_result.message_text}"
    if child_result.question_text:
        child_result.question_text = f"{_greeting_prefix}\n\n{child_result.question_text}"
```

### Commits Fase 4

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `a07fd45` | Fase 3 (homologação + prompt) e Fase 4 (recepção em 2 chamadas) — 1 único commit |

**Detalhes do commit `a07fd45`:**
- `backend-executors/app/services/decision_engine.py` — homologação `pre-agendamento→agendamento`; prompt de pré-agendamento reestruturado; reforço na SAUDAÇÃO COMPOSTA da Mãe; chamada separada à recepção + prefixo de saudação; remoção das instruções de abertura embutida
- `backend-executors/tests/test_pre_agendamento_recommended_next_category.py` — criado
- `backend-executors/tests/test_compound_follow_through_routing.py` — mock por rota + asserções actualizadas
- `docs/implementations/fix-compound-follow-through-recepcao.md` — nota de evolução do mecanismo

### Relatório das Fases 3+4 — o que mudou na prática

**Antes:** quando um cliente novo já dizia dia e hora exactos na primeira mensagem (ex.: "quero amanhã às 15h"), a IA respondia de forma sem sentido — perguntando se podia "mandar uma mensagem no dia seguinte para confirmar", em vez de tratar o pedido a sério. E quando a mensagem combinava uma saudação com esse pedido, a IA várias vezes ia direto ao assunto sem cumprimentar o cliente, ficando seca.
**Agora:** quando o cliente já dá dia e hora certos, a IA trata o pedido de imediato, oferecendo horários reais da agenda. E volta a cumprimentar sempre primeiro — com uma resposta dedicada só para o cumprimento, gerada à parte, antes de tratar o pedido em si, sem duplicar a saudação.
**Para validar:** Cenário P1 (saudação + pedido com hora certa) e P2 (saudação pura, sem regressão) — confirmado também que isto não criou nenhuma chamada extra à IA fora do caso de saudação composta.

---

## Checks de Validação — Fase 3 + Fase 4

### Cenário P1 — Saudação composta com dia/hora específicos (Playground, revalidação completa)
- [x] Lead novo, Playground, perfil `hybrid_scheduler`/`agenda` (ai_profile_id=5): "Oi,
      gostaria de agendar uma sessão para amanhã às 15h"
- [x] Confirmar: resposta abre com cumprimento real (ex.: "Oi, Empresa Teste! Que bom que
      você entrou em contato.")
- [x] Confirmar: NÃO pergunta permissão de check-in nem diz "vou mandar mensagem amanhã" —
      trata o pedido directamente com horários reais (ex.: "Para amanhã, posso te agendar
      às 14:00 ou às 17:00")
- [x] Confirmar via log: apenas 1 `decide()` por mensagem (não 2 turnos)
- [x] Confirmar via API (`GET /api/leads/{id}/appointments`): nenhum appointment criado
      neste turno (gate do M3, `is_phase_entry=True`, continua a funcionar)
- **Validado em:** 20/06/2026 — via UI real (browser, MCP chrome-devtools), lead #271. Log:
  `compound_follow_through_route route_override=agendamento source=perceived_category`,
  `prompt_function=_build_child_prompt_agendamento` (Fix D funcionou nesta execução — Mãe
  escolheu "agendamento" directamente, sem precisar do turno extra de pré-agendamento).
  `GET /api/leads/271/appointments` → `[]`.

### Cenário P2 — Saudação pura continua sem chamada extra (regressão)
- [x] Lead novo, Playground, enviar só "oi"
- [x] Confirmar: cumprimento normal ("Oi, Empresa Teste!"), sem nenhuma chamada extra à
      recepção (o bloco novo só corre dentro de `if _follow_through:`, que não dispara em
      saudação pura)
- **Validado em:** 20/06/2026 — via UI real, lead #272. Trace `recepcao 90% 1 guardrail`.

### Cenário C1 — Regressão da suite existente
- [x] `pytest tests/ scripts/test_meeting_scheduler_hook.py scripts/test_meeting_candidate_e2e.py scripts/test_structured_meeting_signal_dual_read.py scripts/test_mother_prompt_agent_mode.py -q`
- **Validado em:** 20/06/2026 — 25 falhas pré-existentes (mesmas da Fase 1/2, não
  relacionadas) / 68 passes (65 + 3 novos cenários de `test_pre_agendamento_recommended_next_category.py`).

---

## Fase 5 — Diagnóstico + Correção: categoria presa em "apresentation" bloqueava o appointment para sempre (20/06/2026)

### Problema identificado

Ao validar ao vivo o Cenário C3 do M3 (appointment deve ser criado quando o lead já estava
na fase de agendamento antes da confirmação), descobri que isso **nunca** acontecia no
caminho onde `effective_route_to` vai direto para `"agendamento"` sem o `lead.category`
ter passado por `"pre-agendamento"` antes (cenário que a Fase 3D tornou mais comum).
Reproduzido ao vivo: lead #273, 2 turnos, `meeting_scheduled=true` nos dois,
`GET /api/leads/273/appointments` → `[]` nos dois. Categoria real no SQLite
(`backend-crm/database/crm.db`): presa em `"apresentation"`.

Causa raiz: `_ALLOWED_ADVANCE["apresentation"]` (`decision_engine.py:3593-3599`) não inclui
`"agendamento"` — só `{"closing","follow-up","pre-agendamento"}`. O clamp de salto único de
`apply_mother_category_guardrails()` bloqueia o salto (`"jump_blocked"`, pois
`len(allowed_next)=3 != 1`), e nenhum dos 3 elos de homologação existentes cobre
genericamente "estou efectivamente em agendamento agora, seja qual for a categoria
anterior". `lead.category` fica preso em `"apresentation"` para sempre — e o gate
`is_phase_entry` do M3 nunca vê `lead.category` alcançar `"agendamento"`, bloqueando a
criação real do appointment indefinidamente (não só no turno de entrada, que era o
trade-off já aceite na Fase 2).

### Correção

| Arquivo | Mudança |
|---|---|
| `backend-executors/app/services/decision_engine.py` (`compose_decision_output()`, depois do bloco `pre_agendamento_complete_auto_advance`) | Novo bloco: quando `effective_route_to=="agendamento"` (para `_SCHEDULING_AGENT_TEMPLATES`), `suggested_category="agendamento"` directamente, ignorando o que o clamp de salto único decidiu |
| `backend-executors/tests/test_pre_agendamento_recommended_next_category.py` | Novo cenário `test_direct_jump_to_agendamento_advances_category_despite_stage_clamp` |

```python
if (
    effective_route_to == "agendamento"
    and template_key in _SCHEDULING_AGENT_TEMPLATES
):
    suggested_category = "agendamento"
    category_reason = (
        f"{category_reason}|effective_route_agendamento_auto_advance"
        if category_reason else "effective_route_agendamento_auto_advance"
    )
```

O gate `is_phase_entry` do M3 (Fase 2) não foi alterado — continua a bloquear a criação
real no turno de entrada; esta correcção só desbloqueia a persistência da categoria para
os turnos seguintes.

### Commits Fase 5

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `8c39555` | Novo bloco de homologação `effective_route_to=="agendamento"` + teste + documentação |

### Relatório da Fase 5 — o que mudou na prática

**Antes:** em certos casos, mesmo depois do cliente confirmar claramente um horário ("sim, pode ser às 9h"), o compromisso nunca era de facto criado na agenda — o sistema respondia como se tivesse marcado, mas por uma falha interna no acompanhamento da fase da conversa, o registo do lead nunca avançava para a etapa de agendamento, e por isso o sistema continuava a bloquear a criação real do compromisso para sempre.
**Agora:** essa falha foi corrigida — uma confirmação real do cliente já resulta sempre num compromisso criado de facto na agenda e no bot a desligar-se correctamente para aquele lead.
**Para validar:** confirmado pela tela real, ponta-a-ponta (desde a primeira mensagem até o compromisso aparecer na agenda). Achado separado e ainda não corrigido: em certos casos a hora exacta gravada internamente no compromisso não corresponde exactamente à hora que o cliente confirmou (a mensagem ao cliente continua certa — é só um detalhe interno de registo); fica para investigação futura.

### Cenário C3 — revalidação completa (categoria + appointment)
- [x] Lead novo, Playground: "Oi, gostaria de agendar uma sessão para amanhã às 11h"
      (conflito real de calendário) → IA oferece 09:00/10:00
- [x] Confirmar via SQLite: `lead.category` já é `"agendamento"` depois do 1º turno (antes
      da Fase 5 ficava em `"apresentation"`)
- [x] Responder "pode ser às 9h então, perfeito"
- [x] Confirmar via log: `lead_current=agendamento`, `guardrail=same_stage`,
      `POST /api/appointments "201 Created"`, `POST .../bot-disabled "200 OK"`
- [x] Confirmar via API (`GET /api/leads/{id}/appointments`): appointment criado
- **Validado em:** 20/06/2026 — via UI real, lead #274, appointment `id=28`
  (`source="playground"`). `pytest` sem regressões novas (25 pré-existentes / 69 passes).

**Achado separado, fora de escopo (não corrigido):** o `start_at` gravado no appointment
(`2026-06-21T13:25:53Z`) não corresponde a "9h" pedido — corresponde ao instante em que o
`decide()` correu. `meeting_scheduler.py` logou `event=meeting_datetime_source
source=fallback_extract_start_at`, indicando que a extracção heurística de data/hora não
conseguiu juntar "amanhã" (mencionado num turno anterior) com "9h" (mencionado só na
mensagem de confirmação) e caiu num fallback impreciso. Pré-existente, não introduzido por
esta sessão de fixes original (Fases 1-5) — corrigido na Fase 6 abaixo.

---

## Fase 6 — Correção: start_at impreciso por falta de candidato estruturado na filha de agendamento (21/06/2026)

### Problema identificado

Reavaliado o achado da Fase 5 a pedido do utilizador: embora a mensagem enviada ao lead
estivesse correta, o `start_at` gravado internamente no appointment não corresponder à hora
combinada tem impacto real na gestão da agenda — afeta a verificação de conflito de horário
(`calendar_busy_slots`) e a visão real da agenda do profissional, não é só um detalhe
cosmético interno.

Causa raiz confirmada no código actual: o mecanismo que captura a hora exacta combinada de
forma estruturada (`signals_structured.meeting_datetime_candidate`, lido por
`meeting_scheduler.py:83-97` antes de cair no fallback heurístico `extract_start_at`) só
estava implementado na filha de **apresentação** (`_build_child_prompt_apresentation`,
quando `presentation_variant=scheduler`). A filha de **agendamento**
(`_build_child_prompt_agendamento`) — usada por `sdr_padrao`/`hybrid_scheduler` no caminho
`pre-agendamento → agendamento`, exactamente o caminho do lead #274 da Fase 5 — nunca recebeu
essa instrução; o schema JSON que ela devolve nem incluía `signals_structured`. Já estava
identificado no item **M3** de `docs/plans/agentes-agenda-melhorias-futuras.md`. O lado
consumidor (`meeting_scheduler._extract_meeting_signal`) já é agnóstico de rota — não
precisou de nenhuma mudança.

### Correção

| Arquivo | Mudança |
|---|---|
| `backend-executors/app/services/decision_engine.py` (`_build_child_prompt_agendamento`) | Schema JSON de saída passa a incluir `signals_structured` (`meeting_proposed`, `meeting_datetime_candidate`); novo bloco de regras instruindo a filha a combinar informação de turnos anteriores do `history` e respeitar `ai_profile.timezone`; `ai_summary` passa a incluir `timezone` (antes só usado internamente no cálculo de `calendar_busy_slots`, nunca exposto ao prompt) |
| `backend-executors/app/services/decision_engine.py` (`_normalize_scheduler_child_signals`) | `is_scheduler_context` estendido para também normalizar quando `effective_route_to=="agendamento"` e o perfil for de um template de agendamento (`_SCHEDULING_AGENT_TEMPLATES`) — mesma lógica de default/limpeza já aplicada à apresentação |
| `backend-executors/tests/test_agendamento_scheduler_structured_signals.py` | Novo arquivo, 4 cenários (espelho de `test_presentation_scheduler_structured_signals.py`): candidato presente, candidato ausente (defaults), template fora de `_SCHEDULING_AGENT_TEMPLATES` (não forçado), prompt contém as novas instruções |

`_build_child_prompt_pre_agendamento` não foi alterado — nesta fase o lead ainda não
confirmou nada, só decide se avança para `agendamento` (mecanismo da Fase 3). A confirmação
real acontece sempre em `agendamento` ou `apresentation`, ambas já cobertas.

### Commits Fase 6

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `b1e9954` | Candidato estruturado de horário na filha de agendamento + normalização + testes |
| 2 | `fe77413` | Achado da validação ao vivo: `today_date` no contexto das filhas de agendamento e apresentação |

### Achado adicional durante a validação ao vivo: data alucinada sem `today_date`

Ao repetir o cenário do lead #274 no Playground (lead #275), a filha de agendamento devolveu
`meeting_datetime_candidate="2023-10-11T09:00:00"` — uma data fixa sem relação com "amanhã".
`meeting_scheduler.py` rejeitou o candidato (`event=meeting_datetime_candidate_invalid
reason=parse_or_past`) e caiu de volta no fallback heurístico, mascarando a correcção da Fase
6. Causa: nenhuma das duas filhas (`_build_child_prompt_agendamento`,
`_build_child_prompt_apresentation`) expunha a data actual no prompt — sem isso, a LLM não
tem como resolver "amanhã"/"depois de amanhã" para uma data absoluta. `_build_child_prompt_pre_agendamento`
já fazia isto (`today_date`) para outro campo (`checkin_at_iso`); estendi o mesmo padrão às
outras duas filhas.

### Relatório da Fase 6 — o que mudou na prática

**Antes:** quando a confirmação de horário acontecia pelo caminho de agendamento puro (sem passar pela apresentação comercial), a hora gravada internamente no compromisso não correspondia à hora que o cliente realmente combinou — o sistema gravava o instante em que processou a mensagem, não o horário pedido. Isso podia bagunçar a verificação de conflito de horários e a visão real da agenda do profissional.
**Agora:** essa mesma IA de agendamento passou a anotar a data e hora combinada de forma exacta e estruturada — igual ao que já era feito na IA de apresentação — em vez de depender só do sistema "adivinhar" lendo o texto da conversa. Na validação ao vivo, a primeira tentativa revelou que a IA não sabia "que dia é hoje" e por isso calculava "amanhã" errado — corrigido dando-lhe essa informação explicitamente, no mesmo turno de testes.
**Para validar:** confirmado por testes técnicos directos (Cenário C5) e por validação ao vivo completa no Playground (lead #276, ver checklist abaixo).

---

## Checks de Validação — Fase 6

### Cenário C5 — Candidato estruturado de horário na filha de agendamento
- [x] Testes unitários directos (`test_agendamento_scheduler_structured_signals.py`, 4 cenários): candidato presente → normalizado (`meeting_proposed=true`); ausente → defaults (`false`/`null`); template fora de `_SCHEDULING_AGENT_TEMPLATES` → não forçado; prompt contém `meeting_proposed`, `meeting_datetime_candidate` e `ai_profile.timezone`
- [x] Regressão: `pytest tests/ scripts/test_meeting_scheduler_hook.py scripts/test_meeting_candidate_e2e.py scripts/test_structured_meeting_signal_dual_read.py scripts/test_mother_prompt_agent_mode.py -q` — 25 falhas pré-existentes idênticas (confirmado via `git stash`/`git stash pop` antes/depois da mudança) / 75 passes (71 + 4 novos), mantido após o commit `fe77413`
- [x] Validação ponta-a-ponta real (Playground): repetido o cenário do lead #274 — "Oi, gostaria de agendar uma sessão para amanhã às 11h" (conflito real, IA ofereceu 09:00/14:00) + confirmação "pode ser às 9h então, perfeito"
- **Validado em:** 21/06/2026 — via UI real (Playground, MCP chrome-devtools), lead #276. 1ª tentativa (lead #275, antes do commit `fe77413`) expôs o achado do `today_date` acima. Após a correcção: log `event=meeting_datetime_source source=structured_candidate tz_used=UTC`; resposta da filha `signals_structured={"meeting_proposed":true,"meeting_datetime_candidate":"2026-06-22T09:00:00"}`; `GET /api/leads/276/appointments` → `start_at="2026-06-22T09:00:00+00:00"` (criado em `2026-06-21T14:12:50Z`) — corresponde exactamente a "amanhã às 9h", não ao instante de execução.

---

## Fase 7 — Diagnóstico + Correção: nomes de dia da semana (sábado, quinta-feira...) resolvidos para a data errada (21/06/2026)

### Problema identificado

O utilizador perguntou se o sistema também agenda corretamente quando o lead diz um **nome
de dia da semana** (ex.: "sábado", "quinta-feira") em vez de "amanhã"/"depois de amanhã".
Validado ao vivo no Playground (lead #277, perfil id=5, hoje=domingo 21/06):

1. Lead pediu "sábado" → perfil não atende sábado (`availability_schedule` real,
   seg-sex 09:00-18:00) → IA redirecionou corretamente para segunda-feira. Comportamento
   correto, mas não testa o cálculo de dia da semana (segunda = "amanhã", caso trivial já
   coberto pela Fase 6).
2. Lead pediu para trocar para "quinta-feira" → IA confirmou "quinta-feira, 22 de junho" —
   **22/06/2026 é segunda-feira, não quinta**. `meeting_datetime_candidate` confirmado via
   rede: `"2026-06-22T09:00:00"`.

Causa raiz: dar à LLM só a data de hoje (`today_date`, da Fase 6) resolve "amanhã" (soma
trivial de 1 dia), mas não é suficiente para "quinta-feira" — isso exige primeiro descobrir
em que dia da semana cai hoje e depois contar quantos dias faltam até o dia pedido, uma
conta que a LLM não faz de forma confiável.

**Primeira tentativa (insuficiente, revertida antes do commit):** adicionar o nome do dia da
semana junto à data (`"2026-06-21 (domingo)"`). Revalidado ao vivo (lead #278): a IA ainda
errou — confirmou "quinta-feira" como `2026-06-23T09:30:00` (terça-feira de verdade), não
`2026-06-25` (quinta real). Saber que hoje é domingo não bastou; ela continuou a errar a
contagem de dias.

### Correção (definitiva, validada)

| Arquivo | Mudança |
|---|---|
| `backend-executors/app/services/decision_engine.py` | Nova função `_calendar_lookup_table_pt(days_ahead=14)`: gera uma tabela com hoje + 14 dias seguintes, cada linha já com a data E o nome do dia da semana calculados (`2026-06-25 (quinta-feira)`). Substitui o helper anterior (`_today_date_with_weekday`) |
| `backend-executors/app/services/decision_engine.py` (`_build_child_prompt_agendamento`, `_build_child_prompt_apresentation`, `_build_child_prompt_pre_agendamento`) | Passam a injetar a tabela completa (`tabela_de_dias`) em vez de uma única data; instrução reescrita para "procure a linha correspondente na tabela — NUNCA calcule a data ou o dia da semana por conta própria" |
| `backend-executors/tests/test_today_date_with_weekday.py` | Novo arquivo, 5 cenários: tabela de nomes de dia da semana bate com datas conhecidas; sequência da tabela de 15 dias está correta; os 3 prompts contêm `tabela_de_dias` e a instrução anti-cálculo |

Ideia central: eliminar qualquer aritmética de calendário do lado da LLM. Em vez de pedir
para ela "calcular" uma data, a tabela já entrega a resposta pronta — ela só precisa
**localizar a linha** cujo dia da semana bate com o que o lead disse. É uma tarefa de busca,
não de cálculo, e LLMs são muito mais confiáveis em busca/correspondência do que em
aritmética de datas.

### Commits Fase 7

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `4b8e1f4` | Tabela de dias (`_calendar_lookup_table_pt`) substituindo o cálculo de data único; testes; validado ao vivo (quinta-feira → 25/06 correto) |

### Relatório da Fase 7 — o que mudou na prática

**Antes:** quando o cliente dizia um nome de dia da semana (ex.: "quinta-feira", "sábado") em vez de "amanhã", a IA podia confirmar a data errada — disse "quinta-feira" mas marcou numa segunda ou terça-feira de verdade, sem o cliente perceber pelo texto da mensagem (que parecia certo).
**Agora:** a IA recebe uma lista pronta com os próximos 14 dias e o nome de cada um já calculado — ela só precisa achar a linha certa, não fazer conta de calendário sozinha. Testado de novo ao vivo: pedindo "quinta-feira", a sessão foi marcada para 25/06, que é de fato a próxima quinta-feira a partir de hoje (domingo 21/06).
**Para validar:** confirmado por testes técnicos diretos e por validação ao vivo completa no Playground (Cenário C6, abaixo).

---

## Checks de Validação — Fase 7

### Cenário C6 — Nomes de dia da semana resolvidos corretamente
- [x] Testes unitários diretos (`test_today_date_with_weekday.py`, 5 cenários): tabela de nomes de dia da semana bate com datas de referência conhecidas; sequência de 15 dias da tabela está correta (data + dia da semana incrementam juntos); os 3 prompts (`agendamento`, `apresentation`, `pre-agendamento`) contêm `tabela_de_dias` e a instrução "NUNCA calcule a data ou o dia da semana por conta própria"
- [x] Regressão: `pytest tests/ scripts/test_meeting_scheduler_hook.py scripts/test_meeting_candidate_e2e.py scripts/test_structured_meeting_signal_dual_read.py scripts/test_mother_prompt_agent_mode.py -q` — 25 falhas pré-existentes idênticas / 80 passes (75 + 5 novos)
- [x] Validação ponta-a-ponta real (Playground): lead novo, "Oi, gostaria de agendar uma sessão para quinta-feira às 9h" → 1ª oferta (9h) marcada como ocupada pela IA, ofereceu 10h/11h → confirmado "pode ser 10h então, perfeito"
- **Validado em:** 21/06/2026 — via UI real (Playground, MCP chrome-devtools), lead #279. Log: `event=meeting_datetime_source source=structured_candidate tz_used=UTC`. Resposta da filha: `signals_structured={"meeting_proposed":true,"meeting_datetime_candidate":"2026-06-25T10:00:00"}`. `GET /api/leads/279/appointments` → `start_at="2026-06-25T10:00:00+00:00"` — 25/06/2026 confirmado como quinta-feira real (hoje, 21/06, é domingo).

---

## Fase 8 — Reforço: saudação composta com dia+hora específicos ainda ia para "pre-agendamento" às vezes (21/06/2026)

### Problema identificado

O utilizador exportou e revisou uma sessão do Playground (lead #281, mensagem "Oi,
gostaria de agendar uma sessão para amanhã às 16h") onde a 1ª resposta do bot não trouxe
nenhuma verificação de disponibilidade — só um genérico "vou verificar e te confirmo". O
trace mostrava `mother_route=recepcao, effective_route=pre-agendamento`, apesar da
mensagem ter dia ("amanhã") E hora ("16h") específicos.

Causa raiz: a regra já existente em `_build_mother_prompt()` (secção SAUDAÇÃO COMPOSTA,
introduzida na Fase 3D) já dizia explicitamente "COM dia/hora específicos → agendamento
diretamente, nunca pre-agendamento" — mas é uma regra abstrata, sem checklist nem exemplo
do erro a evitar. A Mãe nem sempre a seguiu (mesma classe de não-determinismo já aceite na
Fase 3D). Reproduzido nos meus próprios testes da Fase 7 (mesma sessão): leads #276, #279,
#280 (mesmo tipo de mensagem, dia+hora específicos) foram directo para "agendamento"; o
lead #281 do utilizador foi o único que não foi — 3 de 4 directo (75%) na amostra
disponível antes desta fase.

### Correção

| Arquivo | Mudança |
|---|---|
| `backend-executors/app/services/decision_engine.py` (`_build_mother_prompt()`, secção SAUDAÇÃO COMPOSTA) | Regra reescrita com checklist explícito de 2 perguntas (tem dia? tem hora?) + exemplo CORRETO usando a frase exacta do lead #281 + exemplo ERRADO explicando a consequência (lead precisa confirmar de novo antes do agente checar disponibilidade) |
| `backend-executors/tests/test_mother_compound_greeting_day_hour_checklist.py` | Novo arquivo, confirma que o checklist e os exemplos estão no prompt da Mãe |

Mesmo padrão de reforço que funcionou na Fase 7 para `scheduling_offer_style`: regra
abstracta → checklist + exemplo concreto contrastando certo vs. errado.

### Commits Fase 8

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `87d4dbc` | Checklist dia+hora no prompt da Mãe + teste |

### Relatório da Fase 8 — o que mudou na prática

**Antes:** quando o cliente já dizia dia e hora certos na primeira mensagem (ex.: "amanhã às 16h"), o sistema às vezes pulava a etapa de checar disponibilidade de verdade — respondia só "vou verificar e te confirmo", obrigando o cliente a perguntar de novo antes de receber uma resposta real.
**Agora:** a IA que decide o caminho recebeu uma lista de verificação mais clara e um exemplo prático do que fazer (e do que não fazer) nesse caso específico — reduzindo bastante a frequência desse passo extra desnecessário.
**Para validar:** Cenário C7, abaixo. Como o comportamento depende de uma IA tomar a mesma decisão de forma consistente, a melhoria é estatística (testada em várias tentativas), não uma garantia de 100% — continua a ser a mesma natureza de risco residual já aceite na Fase 3D.

---

## Checks de Validação — Fase 8

### Cenário C7 — Taxa de acerto da saudação composta com dia+hora específicos
- [x] Teste unitário directo (`test_mother_compound_greeting_day_hour_checklist.py`): prompt da Mãe contém o checklist e os exemplos
- [x] Regressão: `pytest tests/ scripts/test_meeting_scheduler_hook.py scripts/test_meeting_candidate_e2e.py scripts/test_structured_meeting_signal_dual_read.py scripts/test_mother_prompt_agent_mode.py scripts/test_mother_prompt_rules.py -q` — 25 falhas pré-existentes idênticas / 84 passes (83 + 1 novo)
- [x] Validação ao vivo (Playground, 10 leads novos, frases variadas todas com dia+hora específicos): 9 de 10 foram directo para `effective_route=agendamento`; 1 de 10 foi para `pre-agendamento` (mesmo padrão residual, frequência reduzida)
- **Validado em:** 21/06/2026 — via API do Playground (chamadas directas autenticadas, mesma sessão de browser), leads #282–291. Antes do reforço (amostra da Fase 7, leads #276/#279/#280/#281): 3/4 directo (75%). Depois do reforço: 9/10 directo (90%). Amostra pequena nos dois casos — não é uma medição estatisticamente robusta, mas a direcção é claramente positiva.

---

## Fase 9 — Remoção do override por palavras-chave da "Regra 3" (legado, defasado) (21/06/2026)

### Problema identificado

Revisando a secção "Ajustes Possíveis Pós-Implementação" deste documento, o utilizador
perguntou se havia ali algo "antigo e sensível" já defasado que pudesse ser removido.
Confirmado por leitura directa do código: a "Regra 3" de intenção de agendamento
(`decision_engine.py`) era exactamente o tipo de solução que a Motivação deste documento já
tinha rejeitado — "corrigir... com solução **estrutural**, não **linguística**... qualquer
correção baseada em texto livre exigiria manutenção infinita por nicho/idioma".

A área (dentro de `decide()`, bloco `if mother_decision.route_to == "qualification" and not
force_followup_route:`) misturava dois mecanismos distintos:
- **Override por palavras-chave** (3 listas + 3 funções de detecção): sobrescrevia a rota da
  Mãe para `pre-agendamento`/`agendamento` quando o texto do lead batia com keywords em
  português e o lead já estava em `apresentation`/`pre-agendamento`.
- **Anti-loop estrutural** (sem keywords): evita o bot voltar para `qualification` quando o
  lead já avançou de fase — mecanismo diferente, continua válido e necessário.

Confirmado (grep nos testes) que nenhum teste exercitava directamente o ramo de
palavras-chave. Confirmado também por que ficou redundante: as Fases 3, 5, 7 e 8 deste mesmo
documento já substituíram a função que esse override cumpria por mecanismos estruturais
(homologação de categoria, tabela de datas, checklist dia+hora no prompt da Mãe) — quando a
Mãe ainda erra e cai no anti-loop, o lead recebe `route_for_child="apresentation"`, o mesmo
destino que o anti-loop já dá a qualquer outro caso, e a filha de apresentação avança o lead
pela sua própria homologação (não baseada em keyword) no mesmo turno ou no seguinte.

### Correção

| Arquivo | Mudança |
|---|---|
| `backend-executors/app/services/decision_engine.py` | Removidas as 3 listas de palavras-chave (`_SCHEDULING_TEMPORAL_SIGNALS`, `_SCHEDULING_ACTION_SIGNALS`, `_SOFT_SCHEDULING_SIGNALS`) e as 3 funções de detecção (`_has_scheduling_intent`, `_has_soft_scheduling_intent`, `_has_hard_scheduling_intent`); o bloco `if mother_decision.route_to == "qualification"...` ficou só com o anti-loop estrutural, agora incondicional (deixou de estar dentro de um `if/else` com o ramo de keywords) |
| `backend-executors/tests/test_qualification_state_loop.py` | Novo cenário `test_rule3_keyword_override_removed_falls_back_to_anti_loop`: confirma que, mesmo com mensagem de keyword forte de agendamento e template de agendamento, o lead em `apresentation` cai no anti-loop estrutural — já não é desviado por pattern matching de texto |

`_SCHEDULING_AGENT_TEMPLATES` foi mantido — é infra partilhada com outros mecanismos (Fases
5-7), sem relação com as keywords removidas.

**Achado durante a validação:** o teste irmão já existente
(`test_t3_rule3_blocks_return_to_qualification_when_already_apresentation`) já estava entre as
falhas pré-existentes desta suite, por motivo não relacionado a esta remoção — usa um fixture
com `history=[]`, que activa o gate `_enforce_greeting_first` (força `route_to="recepcao"`
quando `outbound_count==0`), nunca chegando a avaliar o bloco de anti-loop. Confirmado via
`git stash`/`git stash pop` que esta falha já existia antes da Fase 9. O novo teste desta fase
usa um fixture com histórico (`outbound`+`inbound`) para evitar esse gate não relacionado e
exercitar de facto o mecanismo correcto.

### Commits Fase 9

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `_(pendente)_` | Remoção do override por palavras-chave da Regra 3 + teste + documentação |

### Relatório da Fase 9 — o que mudou na prática

**Antes:** existia uma regra antiga que tentava adivinhar se o cliente queria agendar procurando por palavras específicas em português (tipo "marcar", "agendar", nomes de dias) — uma solução frágil, porque só funciona num idioma e quebra fácil com frases diferentes do esperado. Essa regra só entrava em acção como um "plano B" para quando a IA principal (a "Mãe") errava e voltava para a etapa de qualificação mesmo o cliente já estando mais adiante na conversa.
**Agora:** essa regra antiga foi removida. As correcções já feitas nas fases anteriores deste mesmo documento (a lista de dias, o checklist de dia+hora, as transições automáticas de etapa) já resolvem o mesmo problema de forma mais confiável, sem depender de palavras exactas. A rede de segurança que evita o bot voltar para qualificação continua intacta — só a parte baseada em palavras-chave foi removida.
**Para validar:** Cenário C8, abaixo.

---

## Checks de Validação — Fase 9

### Cenário C8 — Remoção do override por palavras-chave sem regressão
- [x] Teste unitário novo (`test_rule3_keyword_override_removed_falls_back_to_anti_loop`): mensagem com keyword forte de agendamento + template de agendamento + lead em `apresentation` → cai no anti-loop estrutural (`route_for_child="apresentation"`, não mais desviado por keyword)
- [x] Confirmado por leitura directa: nenhum outro ponto do código referenciava as listas/funções removidas; `_SCHEDULING_AGENT_TEMPLATES` permanece intacto (usado por outros mecanismos)
- [x] Regressão: `pytest tests/ scripts/test_meeting_scheduler_hook.py scripts/test_meeting_candidate_e2e.py scripts/test_structured_meeting_signal_dual_read.py scripts/test_mother_prompt_agent_mode.py scripts/test_mother_prompt_rules.py -q` — 25 falhas pré-existentes idênticas (confirmado via `git stash`/`git stash pop` antes/depois) / 85 passes (84 + 1 novo)
- **Validado em:** 21/06/2026 — smoke test directo a `decision_engine.decide()` confirmando o comportamento esperado, e suite de regressão completa sem novas falhas.

---

## Ajustes Possíveis Pós-Implementação

- Trade-off aceite: quando o lead confirma um horário na MESMA mensagem em que a Mãe move a
  categoria para a fase de agendamento (ex.: após negociar disponibilidade em pré-agendamento,
  diz "perfeito, pode confirmar às 15h" e a Mãe transiciona a categoria nesse mesmo turno), a
  criação do appointment fica diferida para mais um turno. Custa uma troca extra num caso
  legítimo, em troca de eliminar os falsos positivos relatados.
- **Custo de 1 chamada LLM extra (Fase 4):** só no turno em que `compound_follow_through`
  dispara (1ª mensagem composta de um lead) — aceite explicitamente pelo utilizador. Não
  afecta turnos normais.
- **Não-determinismo da Mãe na escolha pre-agendamento vs. agendamento (Fase 3D, reforçado na Fase 8):** o
  reforço no prompt da Mãe melhora (75%→90% directo na amostra testada) mas não garante 100% das vezes que
  `compound_follow_through` seja directamente "agendamento" quando dia+hora são específicos — quando a Mãe ainda
  escolhe "pre-agendamento", a Fase 3A+3B absorvem o caso (a filha de pré-agendamento
  corrige no mesmo turno e a categoria avança para o turno seguinte), só custando 1 turno
  extra em vez de resposta incorrecta.
- **Resolução de datas (Fase 7) é busca em tabela, não garantia matemática:** a tabela
  `tabela_de_dias` elimina a aritmética de calendário do lado da LLM, mas a LLM ainda
  precisa ler a linha certa — mesma classe de risco residual já documentada para a Mãe
  acima. `days_ahead=14` cobre referências de até 2 semanas (ex.: "semana que vem"); uma
  referência mais distante ("mês que vem") ficaria fora da tabela e cairia de volta no
  fallback heurístico impreciso.
- **Padrão "primeira oferta sempre recusada" observado mas não investigado:** durante a
  validação da Fase 7, todas as ofertas de horário testadas (leads #276, #278, #279)
  vieram com a IA recusando o primeiro horário pedido por "conflito" antes de confirmar um
  segundo — inclusive quando a tabela de `calendar_busy_slots` não mostrava nenhum conflito
  real para a data correta. Pode ser táctica deliberada de jogo de cintura comercial, ou um
  efeito colateral de outro mecanismo (não investigado nesta sessão — fora do escopo da
  resolução de datas).
