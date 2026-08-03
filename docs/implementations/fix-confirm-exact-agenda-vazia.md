# Fix: instrução "confirm_exact" falha quando a agenda está vazia

**Branch:** `main`
**Status:** Em andamento

---

## Motivação

O usuário testou no Playground (produção) um agente com `scheduling_offer_style: "confirm_exact"`
esperando que o bot confirmasse direto horários livres (16h/17h) em vez de sempre oferecer
alternativas. O bot recusou os dois horários como "já ocupados" e ofereceu sempre as mesmas
duas alternativas (15h/18h).

Hipótese inicial (compromisso residual de teste anterior no Playground bloqueando a agenda)
foi descartada — o print da Agenda real do usuário mostra "Nenhum evento agendado" para o dia
em questão. A causa raiz está no código de montagem do prompt, não em dado sujo.

---

## Problemas Identificados (estado anterior)

1. **Bloco "HORÁRIOS JÁ OCUPADOS" desaparece quando a agenda está vazia**
   (`backend-executors/app/services/decision_engine.py:3486-3490`) — `_format_busy_slots_block()`
   retorna `""` quando `busy_slots` está vazio, e o ternário que monta `_busy_block` usa essa
   string vazia para omitir a seção inteira do prompt (cabeçalho incluído).

2. **Instrução `confirm_exact` fica sem âncora** (`decision_engine.py:3496-3512`) — a regra diz
   ao modelo para "verificar o horário pedido contra HORÁRIOS JÁ OCUPADOS **acima**", mas quando
   a agenda está livre essa seção não existe no prompt. Sem uma afirmação positiva de "está tudo
   livre", o modelo tende a recusar horários "redondos" (16h, 17h) por cautela — o oposto do que
   a regra pede.

Confirmado que não há bug em: persistência de `scheduling_offer_style` (valor `"confirm_exact"`
presente e correto no export do AI Profile), nem na query `_load_calendar_busy_slots`
(`backend-crm/services/ai_orchestrator/orchestrator.py:600-627`).

---

## Abordagem

```
Prompt de agendamento (confirm_exact) → monta _busy_block
  ├─ há compromissos → lista "HORÁRIOS JÁ OCUPADOS: ..." (comportamento já correto)
  └─ agenda vazia → ANTES: bloco some do prompt
                     DEPOIS: bloco explícito "HORÁRIOS JÁ OCUPADOS: nenhum compromisso
                     encontrado — a agenda está livre no período consultado."
```

---

## Plano de Implementação

### Fase 1 — Declarar agenda vazia explicitamente no prompt

**Objetivo:** dar ao modelo uma afirmação positiva de agenda livre, em vez de silêncio, quando
não há nenhum compromisso.

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/decision_engine.py` | `_busy_block`: fallback explícito em vez de string vazia quando `_busy_lines` está vazio |
| `backend-executors/tests/test_scheduling_offer_style.py` | Novo teste: `confirm_exact` + calendário vazio → prompt contém a frase de agenda livre |

```python
# ANTES
_busy_block = (
    f"HORÁRIOS JÁ OCUPADOS (compromissos reais já marcados — NÃO proponha nem confirme "
    f"horário que sobreponha estes intervalos):\n{_busy_lines}\n\n"
    if _busy_lines else ""
)

# DEPOIS
_busy_block = (
    f"HORÁRIOS JÁ OCUPADOS (compromissos reais já marcados — NÃO proponha nem confirme "
    f"horário que sobreponha estes intervalos):\n{_busy_lines}\n\n"
    if _busy_lines
    else "HORÁRIOS JÁ OCUPADOS: nenhum compromisso encontrado — a agenda está livre no "
    "período consultado.\n\n"
)
```

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | _(preenchido após o commit)_ | fix: declarar agenda vazia explicitamente no prompt de confirm_exact |

---

## Checks de Validação

### Cenário P1 — Playground, confirm_exact, agenda vazia
- [ ] No Playground, usar um AI Profile com `scheduling_offer_style: confirm_exact` e um lead
  sandbox sem nenhum appointment.
- [ ] Pedir um horário dentro da disponibilidade (ex.: "consigo às 15h?").
- [ ] Confirmar: o bot confirma diretamente, sem oferecer alternativas nem dizer que está ocupado.

### Cenário C1 — Teste automatizado (pytest)
- [ ] `pytest backend-executors/tests/test_scheduling_offer_style.py` passa, incluindo o novo caso.

---

## Ajustes Possíveis Pós-Implementação

- Foi observada uma anomalia no trace do teste original (`mother_route=qualification,
  effective=apresentation` para uma pergunta de agendamento no segundo turno). Não foi
  investigada nesta fase por estar fora do escopo pedido pelo usuário — candidato a
  follow-up futuro caso volte a se manifestar.
