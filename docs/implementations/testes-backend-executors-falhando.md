# Corrigir testes desatualizados em backend-executors/tests/

**Branch:** `fix/testes-backend-executors-desatualizados`
**Status:** Em andamento

---

## Motivação

Este item surgiu como "ajuste possível" na graduação de
`docs/implementations/sales-flow-guardrail-fases-restantes.md`. Ao rodar a suíte completa
de `backend-executors/tests/` como Cenário T3 dessa implementação, 25 dos ~285 testes
falharam. Confirmado via `git stash` que as mesmas falhas ocorrem identicamente sem nenhum
código daquela feature presente — são falhas pré-existentes, não uma regressão introduzida
ali. O utilizador validou este item como urgente na triagem pós-graduação: uma suíte com
~9% dos testes falhando é risco real para qualquer mudança futura em `decision_engine.py`
(impossibilita confiar em "suíte verde" como sinal de não-regressão).

---

## Problemas Identificados (estado anterior)

Rodei a suíte completa em 31/08/2026 (fora da lista original, numa worktree nova, com
`.env` copiado manualmente — ver `docs/implementations/worktree-copiar-env-testes-backend.md`):
**23 falhas, 265 passando** (2 a menos que os 25 originais: `test_p0_trigger_already_
fired_advances_normally` e `test_no_sequential_trigger_in_p0_behaves_like_baseline` já
passavam fora de worktree — confirmando que eram falso-positivo por `.env` ausente).

Todas as causas encontradas são **testes desatualizados refletindo comportamento antigo,
não bugs de produção**. O sistema passou por mudanças de arquitetura intencionais recentes
(motor de Fluxo de Venda, "AI Profile como única fonte de verdade" para qualificação,
guardrail de saudação) e os testes não acompanharam. Não foi encontrado nenhum caso onde o
comportamento atual do código pareça errado.

### Causa 1 — Guardrail "greeting-first" força `recepcao` no primeiro contato

Commit `7347e21` ("guardrail greeting_responded — força recepcao no primeiro contato")
introduziu `_enforce_greeting_first` (`decision_engine.py:4635`): se `history` não contém
nenhuma mensagem `outbound`, a rota é sempre forçada para `"recepcao"` antes de qualquer
outra lógica — mesmo com a Mãe (mockada no teste) decidindo `"qualification"`/`"apresentation"`.
Os testes afetados construíam `context["history"] = []` (padrão anterior a essa guardrail).

### Causa 2 — "AI Profile como única fonte de verdade" para campos obrigatórios

Commit `13b826a` ("Fase 1 — AI Profile como única fonte de verdade para qualificação")
removeu as listas hardcoded de campos obrigatórios por modo (`MIN_REQUIRED_FIELDS` em
`app/contracts/qualification_contract.py`) — hoje, sem `ai_profile.qualification_fields`
(ou `qualification_required_fields` legado) configurado, **nenhum campo é obrigatório**.
Já documentado em `docs/architecture/pipeline-phases.md`, secção "Gate de score". Testes
que dependiam dos defaults antigos (`consultivo`: service_interest/urgency/decision_role/
constraints/availability_window/budget_or_price_acceptance; `agenda`/`direto`:
service_interest/availability_window/price_acceptance) quebraram — tanto os que chamam
`compute_missing_fields()` diretamente sem override quanto os que passam por `decide()`
com `ai_profile` sem `qualification_fields`.

### Causa 3 — Assinatura nova de `generate_child_result` (kwarg `ai_profile`) e campo `system_actions`

O motor de Fluxo de Venda passou a chamar `llm_service.generate_child_result(route, prompt,
ai_profile=ai_profile)` (`decision_engine.py:5800`) e a expor `system_actions` no objeto de
decisão. Mocks/dublês escritos antes dessas mudanças, com assinatura fixa `(route, prompt)`
sem `**kwargs`, quebram com `TypeError`.

### Causa 4 — Textos de prompt reformulados

Testes fazem `assert "<string literal>" in prompt` contra texto que foi reescrito. A regra
de negócio subjacente continua presente, só a redação mudou — confirmado lendo o prompt
atual antes de mexer nos testes.

---

## Abordagem

Corrigir os testes para refletir o comportamento atual (intencional), sem alterar
`decision_engine.py`/`qualification_contract.py`. Dividido em fases por causa raiz — a
Fase 1 acabou por unir as Causas 1 e 3 porque, no arquivo mais afetado
(`test_qualification_state_loop.py`), a maioria dos testes precisava das duas correções ao
mesmo tempo (corrigir só uma delas não fazia o teste passar).

---

## Plano de Implementação

### Fase 1 — Guardrail greeting-first + assinatura de `generate_child_result`

**Objetivo:** corrigir os 14 testes afetados pelas Causas 1 e 3.

| Arquivo | O que mudou |
|---|---|
| `tests/test_qualification_state_loop.py` | 10 contextos ganharam uma entrada `{"model": "outbound", ...}` em `history` (simula "bot já cumprimentou"); 5 mocks `_child`/`_fake_child` ganharam `**_kwargs`; 7 contextos com `agent_mode: "consultivo"` ganharam `ai_profile.qualification_fields` explícito (nova constante `CONSULTIVO_REQUIRED_FIELDS` = default antigo de `MIN_REQUIRED_FIELDS["consultivo"]`) — sem isso, `required_fields` ficava `[]` (Causa 2) mesmo depois de corrigir a Causa 1, e a auto-promoção para "apresentation" disparava incorretamente |
| `tests/test_mother_qualification_route_guardrail.py` | 2 contextos ganharam `history` com outbound + `ai_profile.qualification_fields` explícito (nova constante `AGENDA_REQUIRED_FIELDS` = default antigo de `MIN_REQUIRED_FIELDS["agenda"]`) |
| `tests/test_phase2_direct_question_reply_priority.py` | `_base_context()` ganhou `history` com outbound (já usava `qualification_required_fields` legado — Causa 2 não se aplicava aqui) |

Achado durante a implementação: ao corrigir só a Causa 1 (adicionar `history` com
outbound) em `test_qualification_state_loop.py`, 7 dos 11 testes continuaram falhando —
com `effective_route_to` virando `"apresentation"` em vez do esperado, porque sem
`ai_profile.qualification_fields` explícito `required_fields` é `[]` e o motor
auto-promove o lead por não haver nada "faltando" (Causa 2, camuflada atrás da Causa 1).
Isto amplia o escopo original da Causa 2 (que eu tinha catalogado só em
`test_qualification_contract.py`/`test_guardrails_by_mode.py`) — ela também afeta este
arquivo.

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `15482e5` | Fase 1 completa — 14 testes corrigidos (Causas 1+3) |

### Relatório da Fase 1 — o que mudou na prática

**Antes:** 23 dos ~285 testes de `backend-executors` falhavam. Rodar a suíte não dava para
confiar como sinal de "nada quebrou" em mudanças futuras no motor de decisão.
**Agora:** 14 desses 23 testes foram corrigidos (ajustados para refletir 3 mudanças de
comportamento intencionais e recentes: a guardrail que sempre cumprimenta antes de
qualificar, a exigência de configurar campos obrigatórios no perfil de IA, e a nova forma
de chamar o gerador de resposta da "filha"). Nenhum bug de produto foi encontrado ou
corrigido — só os testes estavam desatualizados.
**Para validar:** não há cenário de UI/produção aqui (são testes automatizados de backend).
O check é a própria suíte: `cd backend-executors && python -m pytest tests/
test_qualification_state_loop.py tests/test_mother_qualification_route_guardrail.py tests/
test_phase2_direct_question_reply_priority.py -q` deve reportar `0 failed`.

### Fase 2 — "AI Profile como única fonte de verdade" (Causa 2 restante)

**Objetivo:** corrigir os 4 testes restantes afetados diretamente pela Causa 2.

| Arquivo | O que mudou |
|---|---|
| `tests/test_qualification_contract.py` | 3 testes passam a chamar `compute_missing_fields(modo, extracted, required_fields_override=[...])` com a lista explícita (default antigo de cada modo), em vez de depender do default removido |
| `tests/test_guardrails_by_mode.py` | `test_agenda_blocks_closing_without_booking_fields` adiciona `ai_profile.qualification_fields` explícito (service_interest/availability_window/price_acceptance) para a guardrail `guardrail_agenda_missing_booking` voltar a enxergar campos faltando |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `dd81ac7` | Fase 2 completa — 4 testes corrigidos (Causa 2) |

### Relatório da Fase 2 — o que mudou na prática

**Antes:** os testes de `compute_missing_fields` e da guardrail "agenda sem campos de
agendamento não pode fechar" dependiam de uma lista de campos obrigatórios que não existe
mais no código (foi substituída por configuração explícita no perfil de IA).
**Agora:** os testes configuram essa lista explicitamente, exercitando a mesma regra de
negócio (campos mínimos por modo) da forma como ela realmente funciona hoje.
**Para validar:** `cd backend-executors && python -m pytest tests/test_qualification_contract.py tests/test_guardrails_by_mode.py -q` → `0 failed`.

### Fase 3 — Mocks/dublês desatualizados (Causa 3 restante)

**Objetivo:** corrigir os 3 testes de follow-up com mocks sem `**kwargs` / sem `system_actions`.

- `tests/test_followup_tick_route_priority.py::test_followup_tick_forces_followup_child_route`
- `tests/test_followup_tick_runner.py` (2 testes)

_A implementar._

### Fase 4 — Textos de prompt desatualizados (Causa 4)

**Objetivo:** corrigir os 2 testes com asserts de string literal desatualizada.

- `tests/test_recepcao_pending_commercial_extraction.py`
- `tests/test_followup_prompt_contract_context.py`

_A implementar._

---

## Checks de Validação

### Cenário T1 — Suíte completa verde
- [ ] Rodar `cd backend-executors && python -m pytest tests/ -q`
- [ ] Confirmar `0 failed`

---

## Ajustes Possíveis Pós-Implementação

_A preencher na graduação._
