# Guardrail de gatilhos pendentes para p0 (Recepção)

**Branch:** `feat-fluxo-vendas-ramificacao`
**Status:** Aguardando Plan Mode

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`docs/implementations/sales-flow-fase-pendente-guardrail.md` (feature que deu a p1, p2 e p3a
um guardrail de "gatilhos sequenciais pendentes bloqueiam avanço automático de fase").

p0 (Recepção) ficou explicitamente fora do escopo dessa feature porque é estruturalmente
diferente das demais: `"recepcao"` **não existe** em `_STAGE_ORDER`/`_ALLOWED_ADVANCE`
(`backend-executors/app/services/decision_engine.py:4521-4530`) — por causa disso,
`apply_mother_category_guardrails()` aceita o `perceived_category` da Mãe **sem nenhum clamp
de salto único** quando o lead está em recepcao (path `"no_current_accept"`, ~linhas
4637-4686). Isso é mais severo do que o gap que já existia em p1/p2/p3a antes da correção: lá
o salto era de UMA fase por vez (clampado por `_ALLOWED_ADVANCE`, só sem checar gatilhos
pendentes); em p0 não há clamp nenhum — a Mãe pode, em teoria, saltar para qualquer categoria
num único turno.

Antes de replicar o guardrail de "gatilhos pendentes" (`_phase_pending_sequential_triggers`,
já existente e reutilizável) para p0, é preciso primeiro decidir como dar a `"recepcao"` uma
entrada em `_STAGE_ORDER`/`_ALLOWED_ADVANCE` sem quebrar outra lógica que já indexa por esses
dicionários — daí precisar de um diagnóstico próprio em Plan Mode, não uma repetição mecânica
do padrão das fases anteriores.

---

## Diagnóstico (a fazer em Plan Mode)

Este arquivo nasce sem plano — o Passo 0 (`_guia-documentar-implementacao.md`) ainda não foi
feito. Pontos a investigar quando essa sessão começar:

1. **Já existe?** Não — confirmado durante a investigação da feature-mãe (3 agentes Explore +
   leitura direta de `decision_engine.py`).
2. **O que precisa ser construído:**
   - Adicionar `"recepcao"` a `_STAGE_ORDER` (e decidir a posição — antes de `"qualification"`)
     e a `_ALLOWED_ADVANCE` (provavelmente `{"qualification"}`, mas confirmar se algum modo
     permite pular direto para outra fase legitimamente).
   - Levantar TODOS os outros pontos do código que leem `_STAGE_INDEX`/`_STAGE_ORDER`/
     `_ALLOWED_ADVANCE` para avaliar impacto de recepcao passar a fazer parte deles (hoje
     `_normalize_current not in _STAGE_INDEX` é o que ativa o path sem-clamp — mudar isso
     muda esse comportamento para QUALQUER lead em recepcao, não só os com Fluxo de Venda
     configurado ali).
   - Depois disso, replicar o padrão: `_enforce_recepcao_sales_flow_pending()` (mesma forma de
     `_enforce_apresentation_sales_flow_pending`/`_enforce_pre_agendamento_sales_flow_pending`).
3. **Riscos:** mudar `_STAGE_ORDER`/`_ALLOWED_ADVANCE` é uma mudança estrutural com maior raio
   de impacto que os guardrails anteriores (que só adicionaram checagens, sem tocar nessas
   constantes) — precisa de suite completa rodada e possivelmente testes adicionais para os
   caminhos que hoje dependem do comportamento "recepcao sem clamp".

---

## Arquivos prováveis

- `backend-executors/app/services/decision_engine.py` — `_STAGE_ORDER`, `_ALLOWED_ADVANCE`,
  novo `_enforce_recepcao_sales_flow_pending()`, `apply_mother_category_guardrails()`.
- Testes novos espelhando `test_pre_agendamento_sales_flow_pending.py`.

---

## Checks de Validação

_A definir após o Plan Mode._

---

## Ajustes Possíveis Pós-Implementação

_A preencher na graduação._
