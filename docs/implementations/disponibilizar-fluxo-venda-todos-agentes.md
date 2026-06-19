# Disponibilizar o Fluxo de Venda (Camada 7) para agentes em modo passivo

**Branch:** `main`
**Status:** Todos os cenários validados (19/06/2026)

---

## Motivação

O Fluxo de Venda (Camada 7) estava bloqueado para qualquer agente com
`response_style != "active"`, tanto no backend quanto no frontend. O utilizador
tem um agente "híbrido agendador" (`agent_mode=agenda`, `template_key=hybrid_scheduler`)
em modo passivo e queria configurar o Fluxo de Venda para personalizar o funil
— mas a aba nem aparecia na UI.

Investigação confirmou que a restrição não tem dependência estrutural com
guardrails anti-loop, `lead_category_policy` ou o auto-disable do bot em
"closing". O único risco real é de conteúdo: blocos `orientacao` podem
contradizer a regra absoluta de "zero perguntas abertas" do modo passivo — o
utilizador aceitou esse risco explicitamente e ficará responsável por configurar
blocos compatíveis com o tom do agente.

---

## Problemas Identificados (estado anterior)

1. **Backend bloqueava a engine do Fluxo de Venda em modo passivo:**
   `backend-executors/app/services/decision_engine.py` — 3 funções
   (`_evaluate_sales_flow`, `_evaluate_sales_flow_phases`,
   `_collect_intent_triggers_for_lead_phase`) retornavam vazio/None quando
   `response_style != "active"`, antes mesmo de checar se `sales_flow.enabled`.
2. **Frontend escondia a aba inteira:** `frontend-crm/src/pages/AiProfile.tsx`
   — 3 pontos (card de resumo, item de subnav, render do painel) só mostravam
   o Fluxo de Venda quando `config.response_style === 'active'`.

---

## Abordagem

Remover a condição de `response_style` nos 3 pontos do backend e nos 3 pontos
do frontend listados acima — mantendo apenas a checagem de
`sales_flow.enabled` (que já existia e continua a ser o controlo real de
on/off por agente). **Não tocar** em `qual_opener`/`_natural_reaction_block`
(decision_engine.py linhas ~2102/2109) — esses continuam restritos a modo
activo, por estarem ligados especificamente ao fluxo de perguntas de
qualificação, fora do escopo deste pedido.

---

## Plano de Implementação

### Fase 1 — Backend: remover gate em `decision_engine.py`

| Arquivo | O que mudou |
|---|---|
| `backend-executors/app/services/decision_engine.py` | `_evaluate_sales_flow()`, `_evaluate_sales_flow_phases()`, `_collect_intent_triggers_for_lead_phase()` — removida a checagem `response_style != "active"` |

### Fase 2 — Frontend: remover gate + ajustar labels em `AiProfile.tsx`

| Arquivo | O que mudou |
|---|---|
| `frontend-crm/src/pages/AiProfile.tsx` | Removida condição `response_style === 'active'` no card de resumo, na subnav e no render do painel; labels "Fluxo de Venda · Modo Ativo" / "Camada 7 · Modo Ativo" simplificados (já não é exclusivo do modo activo) |

### Fase 3 — Documentação

| Arquivo | O que mudou |
|---|---|
| `docs/architecture/sales-flow.md` | Nota confirmando disponibilidade independente de `response_style`, com aviso sobre o risco de conflito de `orientacao` em modo passivo |

### Commits

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `69f1be2` | feat: disponibilizar Fluxo de Venda para agentes em modo passivo (backend + frontend + doc) |

---

## Checks de Validação

### Cenário P1 — Fluxo de Venda visível e funcional em agente passivo
- [x] Configurar agente `hybrid_scheduler` com `response_style="passive"` e um bloco `orientacao` na fase p2
- [x] Confirmar: aba "⑦ Fluxo de Venda" aparece na UI, sem o rótulo "Modo Ativo"
- [x] Testar no Playground: confirmar que a instrução do bloco chega ao prompt da fase apresentation
- **Validado em:** 19/06/2026 — local. Chamada directa a `_evaluate_sales_flow_phases()` com o `ai_profile` real (response_style="passive") confirmou `prompt_injections` populado com o conteúdo do bloco. No Playground, o LLM nem sempre repete literalmente um texto artificial injectado (comportamento normal do modelo, não falha de injecção) — por isso a confirmação definitiva foi feita ao nível da função, não da resposta final do bot.

### Cenário C1 — Regressão em agente activo
- [x] Confirmar que um agente com `response_style="active"` continua a ver e usar o Fluxo de Venda exactamente como antes
- **Validado em:** 19/06/2026 — local. Mesmo agente, `response_style="active"`: aba "⑦ Fluxo de Venda" e o bloco da fase p2 idênticos; resumo mostra "FLUXO DE VENDA: Ativo" igual em ambos os modos (rótulo refere-se a `sales_flow.enabled`, não a `response_style` — confirma a simplificação descrita na Fase 2).

---

## Ajustes Possíveis Pós-Implementação

- Se no uso real surgirem muitos casos de blocos `orientacao` conflitando com a
  regra de "zero perguntas abertas" do modo passivo, considerar no futuro um
  aviso na UI do builder (`CamadaFluxoVenda.tsx`) quando o agente é passivo,
  sem bloquear a funcionalidade.

### Bug encontrado durante o teste (fora do escopo desta implementação)

Ao criar uma **nova** acção do tipo "Orientação ao Agente" pelo fluxo "Montar
regra → + Adicionar ação" (`CamadaFluxoVenda.tsx`, estado `pendingBlock`), o
texto digitado na "Instrução para o agente" não é persistido — o bloco salva
só com `id`/`typeId`, sem `content`. Editar um bloco **já existente** (botão
"EDITAR") funciona normalmente e persiste o `content` correctamente. Ainda não
isolada a causa exacta (suspeita: re-render do `pendingBlock` perdendo o estado
entre o `BlockForm` e `confirmPendingBlock`). Não bloqueia este check porque o
teste foi concluído editando o bloco depois de criado, mas é um bug real a
corrigir numa próxima sessão — afecta qualquer tipo de acção criada pela
primeira vez por este caminho (`orientacao`, `mensagem`, etc.), não só `p2`.
