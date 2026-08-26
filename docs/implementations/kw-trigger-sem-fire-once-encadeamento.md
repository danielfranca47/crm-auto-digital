# Campo independente "ordem da fila" para kw_trigger e intent_trigger

**Branch:** `feat/kw-trigger-sem-fire-once-encadeamento`
**Status:** Em andamento

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de `fix-fluxo-vendas-sequencial.md`.

As Fases 1 e 2 desse trabalho introduziram o conceito de gatilho "sequencial" —
`phase_trigger` ou `kw_trigger`/`intent_trigger` com `fire_once: true` — usado tanto
para o gating dentro da fase (`_evaluate_sales_flow_phases`, `_is_sequential_trigger_block`)
quanto para o guardrail que impede a Mãe de saltar a fase de apresentation inteira
(`_enforce_apresentation_sales_flow_pending`). Um `kw_trigger` **sem** `fire_once`
(pensado para disparar toda vez que o lead repetir uma palavra-chave, não só na
primeira) foi deliberadamente deixado de fora desse encadeamento.

**Diagnóstico feito em Plan Mode com o utilizador** (várias rodadas de perguntas):
a causa raiz é que o checkbox **"Disparar apenas uma vez por lead"** (`fire_once`)
faz duas coisas ao mesmo tempo, sem isso estar declarado em lugar nenhum da tela:

1. O que o texto promete — controla se o gatilho pode disparar mais de uma vez.
2. O que ele controla nos bastidores, sem aviso — se o gatilho participa do
   encadeamento sequencial (`_is_sequential_trigger_block`): espera os gatilhos
   anteriores da fase, trava os seguintes, conta como "pendência" no guardrail
   que impede a IA Mãe de pular a fase inteira.

Duas propostas intermediárias (regra fixa por tipo de gatilho: kw_trigger sempre
sequencial / intent_trigger nunca sequencial) foram descartadas por trocar um
acoplamento invisível por outro, sem o usuário poder escolher, e por mudar o
comportamento de fluxos já configurados com `intent_trigger` + `fire_once=True`.

**Decisão final:** separar os dois conceitos em dois campos independentes no
builder, ambos disponíveis em `kw_trigger` e `intent_trigger`:

| Campo | Opções | Controla |
|---|---|---|
| **Ordem** (`sequential`, novo) | "Respeitar ordem cronológica" / "Pode ser acionado a qualquer momento" | Se o gatilho espera a vez dele na fila, trava os seguintes e conta como pendência de fase |
| **Disparar apenas uma vez por lead** (`fire_once`, já existe) | ligado/desligado | Se o gatilho para de disparar depois da 1ª vez — disponível nas duas opções de Ordem acima, sem relação com a fila |

As 4 combinações passam a ser válidas e distintas:
- Respeita ordem + só uma vez → comportamento sequencial de hoje (`fire_once=True`).
- Respeita ordem + repetível → **o caso que este arquivo perguntava originalmente**:
  vira um marco de fila, mas continua disparando toda vez que a palavra-chave/
  intenção aparecer depois de "liberado".
- Qualquer momento + só uma vez → fura a fila, mas só conta uma vez por lead.
- Qualquer momento + repetível → comportamento de hoje para `fire_once=False`
  (transparente, fora da fila).

**Compatibilidade:** blocos já salvos não têm o campo `sequential`. Quando
ausente, `sequential` é tratado como igual ao valor atual de `fire_once` desse
bloco — ou seja, exatamente o comportamento de produção hoje, para `kw_trigger`
e `intent_trigger`. Zero regressão em fluxos já configurados; só blocos novos ou
reeditados no builder passam a ter os dois campos de fato independentes.

---

## Problemas Identificados (estado anterior)

1. **Acoplamento invisível:** o checkbox "Disparar apenas uma vez por lead"
   controlava, sem nenhuma indicação na UI, tanto a supressão de re-disparo
   quanto a participação no encadeamento sequencial — dois conceitos distintos
   fundidos num único campo.
2. **`intent_trigger` sem alternativa de "furar a fila":** hoje, um
   `intent_trigger` com `fire_once=True` é sempre sequencial — não há como o
   usuário configurar uma detecção de intenção esporádica (que pode acontecer
   a qualquer momento da fase) que ainda assim só dispare uma vez por lead.

---

## Abordagem

`_is_sequential_trigger_block()` (`backend-executors/app/services/decision_engine.py`)
passa a ler o novo campo com fallback para `fire_once`:

```python
# ANTES
if type_id in ("kw_trigger", "intent_trigger"):
    return bool(block.get("fire_once"))

# DEPOIS
if type_id in ("kw_trigger", "intent_trigger"):
    if "sequential" in block:
        return bool(block.get("sequential"))
    return bool(block.get("fire_once"))  # legado: sem o campo novo, comportamento atual
```

`_trigger_persisted_satisfied()` deixa de exigir `fire_once` para
`kw_trigger`/`intent_trigger` — passa a olhar só se já disparou alguma vez
(`block_id in triggers_fired`), já que "é sequencial ou não" já foi decidido
por `_is_sequential_trigger_block()` antes desta função ser chamada.

Os blocos de avaliação de `kw_trigger` e `intent_trigger` marcam
`mark_trigger_fired` na 1ª vez que disparam, independente de `fire_once` —
reaproveitando `leads.triggers_fired`, sem nova coluna/migração:

```python
# ANTES
if fired and _fire_once and _block_id:
    result["system_actions"].append({"type": "mark_trigger_fired", "block_id": _block_id})

# DEPOIS
if fired and _block_id and _block_id not in _triggers_fired:
    result["system_actions"].append({"type": "mark_trigger_fired", "block_id": _block_id})
```

A supressão de re-disparo não muda — continua só suprimindo quando
`fire_once=True`. Toda a maquinaria de gating restante (`_locked`,
`_prereqs_satisfied_by_scope`, `_requires_block_satisfied`,
`_phase_pending_sequential_triggers`) já delega para
`_is_sequential_trigger_block()` — herda o comportamento novo sem alteração
própria.

---

## Plano de Implementação

### Fase 1 — Motor de decisão (backend-executors)

**Objetivo:** o campo `sequential` (com fallback para `fire_once`) governa a
participação no encadeamento; `fire_once` passa a controlar só re-disparo.

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/decision_engine.py` | `_is_sequential_trigger_block()`, `_trigger_persisted_satisfied()`, blocos de avaliação `kw_trigger`/`intent_trigger` (marcação `mark_trigger_fired` na 1ª vez) |
| `backend-executors/tests/test_sales_flow_intent_trigger_phase_entry.py`, `test_sales_flow_requires_block_id.py`, `test_sales_flow_branching.py` | Cobertura nova para as combinações `sequential`×`fire_once` que não existiam antes |

#### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `6bb8092` | Campo `sequential` com fallback para `fire_once` em `_is_sequential_trigger_block()`; marcação de 1ª ocorrência independente de `fire_once`; 6 testes novos cobrindo as combinações |

**Detalhes do commit `6bb8092`:**
- `decision_engine.py` — `_is_sequential_trigger_block()` lê `sequential` com fallback
  para `fire_once`; `_trigger_persisted_satisfied()` simplificado; blocos de avaliação de
  `kw_trigger`/`intent_trigger` marcam `mark_trigger_fired` na 1ª vez que disparam
  (antes só marcavam quando `fire_once=True`).
- `test_sales_flow_intent_trigger_phase_entry.py` — testes novos: fallback do campo
  `_is_sequential_trigger_block`, `sequential=True`+repetível trava até a 1ª ocorrência e
  continua repetindo depois, `sequential=False`+`fire_once=True` fura a fila mas só
  dispara uma vez.

#### Relatório da Fase 1 — o que mudou na prática

**Antes:** o checkbox "Disparar apenas uma vez por lead" decidia, sem avisar em lugar
nenhum da tela, se o gatilho também esperava a vez dele numa fila — palavra-chave e
Intenção de IA só respeitavam a ordem quando essa caixa estava marcada.

**Agora:** o motor de decisão já entende um campo novo e independente (`sequential`) que
separa "espera a vez na fila" de "só dispara uma vez". Enquanto o builder (Fase 2) ainda
não expõe esse campo na tela, todo bloco já configurado continua se comportando
exatamente como antes (o motor usa o valor atual de "Disparar apenas uma vez" como
padrão quando o campo novo não existe) — nada muda na prática até a Fase 2 entrar.

**Para validar:** esta fase é só o motor por trás da tela — ainda não dá para testar via
Playground porque o builder não tem o controle novo ainda (isso é a Fase 2). A suíte
automatizada de testes (`pytest`) já cobre as 4 combinações e passou sem nenhuma
regressão nos testes existentes (247 passando, mesmas 25 falhas pré-existentes e não
relacionadas, confirmadas rodando a suíte na baseline antes da mudança).

**Prompt de retomada**, se quiser continuar depois:
> Lê `docs/implementations/kw-trigger-sem-fire-once-encadeamento.md`, secção "Fase 2 —
> Builder (frontend-crm)", e implementa.

### Fase 2 — Builder (frontend-crm)

**Objetivo:** expor os dois campos como controles independentes no formulário
de `kw_trigger`/`intent_trigger`.

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/components/agente/CamadaFluxoVenda.tsx` | `isSequentialCapable()` com o mesmo fallback; novo controle "Ordem" (2 opções) nos formulários de `kw_trigger`/`intent_trigger`; `sequentialCount` do banner de p0/Recepção usando `isSequentialCapable()` |

#### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `ee19698` | Campo `sequential` no tipo `SalesFlowBlock`; controle "Ordem" (2 opções, radio) no formulário; `isSequentialCapable()`/`sequentialCount` usando o novo fallback |

**Detalhes do commit `ee19698`:**
- `types/agente.ts` — novo campo `SalesFlowBlock.sequential?: boolean`.
- `CamadaFluxoVenda.tsx` — `isSequentialCapable()` lê `sequential` com fallback para
  `fire_once`; `renderSequentialOrderControl()` (novo helper) desenha os 2 radios "Ordem"
  acima do checkbox "Disparar apenas uma vez por lead" nos formulários de `kw_trigger` e
  `intent_trigger`; `emptyBlock()` já cria blocos novos desses dois tipos com
  `sequential: true`; `sequentialCount` do banner de aviso da fase p0/Recepção passou a
  usar `isSequentialCapable()` em vez da condição manual antiga.

#### Relatório da Fase 2 — o que mudou na prática

**Antes:** o único jeito de um gatilho de palavra-chave ou Intenção de IA "esperar a vez"
numa sequência era marcar "Disparar apenas uma vez por lead" — não havia como escolher as
duas coisas de forma independente, e a tela não avisava que o checkbox fazia isso.

**Agora:** o formulário de gatilho de palavra-chave e de Intenção de IA ganhou um campo
novo, "Ordem", com duas opções — "Respeitar ordem cronológica" ou "Pode ser acionado a
qualquer momento" — separado do checkbox "Disparar apenas uma vez por lead", que continua
existindo do lado, com o mesmo significado de sempre. Um gatilho já configurado antes
desta mudança abre com a opção pré-selecionada de acordo com o que ele já fazia (sem
precisar o usuário reconfigurar nada); um gatilho novo já nasce com "Respeitar ordem
cronológica" marcado.

**Para validar:** Cenários P1, P2 e P3 da secção "Checks de Validação", abaixo — via
Playground.

**Verificação técnica feita nesta fase:** `npx tsc --noEmit` sem erros e `npm run build`
concluído com sucesso (únicos avisos são pré-existentes, não relacionados a esta mudança).

**Prompt de retomada**, se quiser continuar depois:
> Lê `docs/implementations/kw-trigger-sem-fire-once-encadeamento.md`, secção "Checks de
> Validação", e executa os Cenários P1, P2 e P3 via Playground.

---

## Checks de Validação

### Cenário P1 — kw_trigger "respeita ordem + repetível"
- [ ] Configurar p2: `kw_trigger` A (fire_once, "aceito") → `kw_trigger` B ("obrigado", Ordem="Respeitar ordem cronológica", "Disparar apenas uma vez"=desligado) → orientação "SÓ APÓS B"
- [ ] Mandar "obrigado" antes de "aceito": orientação NÃO aparece
- [ ] Mandar "aceito", depois "obrigado": orientação aparece
- [ ] Mandar "obrigado" de novo: dispara de novo (continua repetível)

### Cenário P2 — intent_trigger "fura a fila + só uma vez"
- [ ] Configurar `intent_trigger` com Ordem="Pode ser acionado a qualquer momento" e "Disparar apenas uma vez"=ligado, posicionado depois de um gatilho sequencial ainda não satisfeito
- [ ] Confirmar que dispara mesmo assim (fura a fila)
- [ ] Confirmar que uma 2ª ocorrência da mesma intenção não dispara de novo

### Cenário P3 — compatibilidade de blocos existentes
- [ ] Reabrir no builder um `intent_trigger` já existente com `fire_once=True` e sem o campo novo
- [ ] Confirmar que a opção pré-selecionada é "Respeitar ordem cronológica" (reflete o fallback)

### Automatizado — suíte backend
- [ ] `cd backend-executors && python -m pytest tests/ -q` sem falhas

---

## Ajustes Possíveis Pós-Implementação

<A preencher se surgir algo durante a implementação ou os testes.>
