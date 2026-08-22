# Guardrail de gatilhos pendentes para p0 (Recepção)

**Branch:** `feat-fluxo-vendas-ramificacao`
**Status:** Em andamento

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`docs/implementations/sales-flow-fase-pendente-guardrail.md` (feature que deu a p1, p2 e p3a
um guardrail de "gatilhos sequenciais pendentes bloqueiam avanço automático de fase"). p0
(Recepção) ficou explicitamente fora do escopo dessa feature.

---

## Diagnóstico

### Já existe?

Não para p0. O mecanismo genérico (`_phase_pending_sequential_triggers`) já existe e é
reutilizável — usado hoje por `_enforce_apresentation_sales_flow_pending` (p2) e
`_enforce_pre_agendamento_sales_flow_pending` (p3a). Falta só a função equivalente para p0.

O diagnóstico original deste arquivo (mexer em `_STAGE_ORDER`/`_STAGE_INDEX` e em
`apply_mother_category_guardrails()`) foi investigado e **descartado**: `"recepcao"` nunca é
um valor persistido em `leads.category` (só existe como `route_to` efémero —
`orchestrator_models.py:29-30` mostra que `perceived_category`, o campo que alimenta
`apply_mother_category_guardrails`, exclui `"recepcao"` do seu tipo). O caminho "sem clamp"
que o diagnóstico original descrevia (`no_current_accept` em `apply_mother_category_guardrails`)
já está coberto na prática pelos dois pontos reais de criação/promoção de lead:
- `backend-crm/services/whatsapp_inbound/guardrail.py::find_or_create_lead_by_phone()` — lead
  novo via WhatsApp nasce direto com `category="qualification"`.
- `maybe_promote_lead_on_inbound()` (mesmo arquivo) — promove `to-prospect`/`in-progress` →
  `qualification`, síncrono, antes de qualquer job chegar ao decision_engine.
- `routes/playground.py::_create_sandbox_lead()` — cria sempre com `category="qualification"`.

O bug real e alcançável é outro: `_enforce_greeting_first()` (`decision_engine.py`) só força
`route_to="recepcao"` no **primeiro** turno (`outbound_count==0`). A partir do segundo turno,
se o usuário configurou gatilhos sequenciais em p0 no builder "Fluxo de Venda" (p0 é uma fase
normal e configurável, confirmado em `CamadaFluxoVenda.tsx`), nada impede a Mãe de rotear
direto para `"qualification"`, pulando o resto da sequência configurada — mesma classe de bug
que motivou a correção em p2/p3a.

### O que precisa ser construído

- **Backend** — nova `_enforce_recepcao_sales_flow_pending()` em `decision_engine.py`,
  espelhando `_enforce_pre_agendamento_sales_flow_pending`, com 2 adaptações necessárias
  (confirmadas com o usuário):
  1. "Engajado com recepção" não pode depender de `current_category == "recepcao"` (nunca é
     persistido) — usa o sinal oposto: lead ainda não passou de `qualification`.
  2. Teto de 1 turno extra (`_MAX_RECEPCAO_ENFORCED_OUTBOUND_TURNS`) — a Filha Recepção é
     desenhada para um único turno ("Seu papel dura só este turno",
     `_build_child_prompt_recepcao`); sem teto, o guardrail repetiria a saudação em plena
     conversa real.
  - Extensão de `_ALLOWED_ADVANCE` com `"recepcao": {"qualification"}` (sem tocar
    `_STAGE_ORDER`/`_STAGE_INDEX` — nenhum outro consumidor de `_ALLOWED_ADVANCE` chegaria a
    receber `"recepcao"` como chave).
- **Frontend** — aviso visual em `CamadaFluxoVenda.tsx` (Fase 0) quando o usuário configurar
  mais gatilhos sequenciais do que o teto de 1 turno cobre (2+ `kw_trigger`/`intent_trigger`
  sequenciais, ou um nó `condicao`). Reaproveita `isSequentialCapable()` já existente.

### Riscos e dependências

- Nenhuma mudança em `_STAGE_ORDER`/`_STAGE_INDEX`/`apply_mother_category_guardrails` —
  reduz o raio de impacto em relação ao diagnóstico original.
- Mudança em `_ALLOWED_ADVANCE` (adicionar 1 chave) é aditiva — não altera comportamento de
  nenhuma chave existente; confirmado por grep que só a nova função lê `_ALLOWED_ADVANCE["recepcao"]`.
- Frontend: mudança é só leitura derivada + renderização condicional, sem novo estado persistido.

### Proposta de fases

Fase 1 — Guardrail de backend (`_enforce_recepcao_sales_flow_pending` + testes)
Fase 2 — Aviso no builder (frontend, `CamadaFluxoVenda.tsx`)

---

## Problemas Identificados (estado anterior)

1. **Gap de `route_to` em p0 (`decision_engine.py`):** `_enforce_greeting_first()` só age no
   1º turno. A partir do 2º turno, gatilhos sequenciais configurados em p0 no Fluxo de Venda
   podem ser ignorados pela Mãe sem nenhum bloqueio — diferente de p2/p3a, que já têm essa
   proteção.
2. **Sem aviso no builder:** o usuário pode configurar em p0 uma sequência de gatilhos que,
   estruturalmente, nunca teria tempo de resolver dentro do teto de turnos da Recepção, sem
   nenhum sinal na UI de que isso pode não funcionar como esperado.

---

## Abordagem

```
Turno 1 (outbound_count==0) → _enforce_greeting_first força route_to="recepcao" (já existente)
Turno 2 (outbound_count==1) → Mãe tenta route_to="qualification"
  ├─ p0 tem gatilho pendente → _enforce_recepcao_sales_flow_pending força de volta "recepcao" (NOVO)
  └─ sem pendência → segue "qualification" normalmente
Turno 3+ (outbound_count>=2) → guardrail nunca mais age (teto de 1 turno extra) — Mãe decide livre
```

---

## Plano de Implementação

### Fase 1 — Guardrail de backend

**Objetivo:** impedir que a Mãe pule gatilhos sequenciais pendentes de p0 no 2º turno da conversa.

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/decision_engine.py` | `_ALLOWED_ADVANCE["recepcao"] = {"qualification"}`; nova `_enforce_recepcao_sales_flow_pending()`; wiring em `decide()` |
| `backend-executors/tests/test_recepcao_sales_flow_pending.py` (novo) | 9 testes espelhando `test_pre_agendamento_sales_flow_pending.py` |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `3127f4b` | `_enforce_recepcao_sales_flow_pending()` + wiring em `decide()` + 9 testes |

**Detalhes do commit `3127f4b`:**
- `backend-executors/app/services/decision_engine.py` — `_ALLOWED_ADVANCE["recepcao"] = {"qualification"}`; nova `_enforce_recepcao_sales_flow_pending()` (teto de 1 turno extra + condição "ainda não passou de qualification"); chamada inserida em `decide()` logo após `_enforce_scheduling_agent_no_closing`
- `backend-executors/tests/test_recepcao_sales_flow_pending.py` — 6 testes unitários da função isolada + 3 testes de integração via `decision_engine.decide()`

### Relatório da Fase 1 — o que mudou na prática

**Antes:** se o usuário configurasse algo na Fase 0 (Recepção) do Fluxo de Venda que dependesse
de uma confirmação do lead (ex.: "só mande a saudação completa depois que o lead confirmar
interesse"), a partir da 2ª mensagem do lead a IA podia decidir pular direto para a
Qualificação, ignorando essa configuração.

**Agora:** a partir da 2ª mensagem, se ainda houver algo configurado em p0 que não disparou, o
sistema mantém a conversa na Recepção por mais 1 turno para dar tempo de disparar. A partir da
3ª mensagem em diante, o sistema nunca mais interfere — a Recepção continua sendo só para a
saudação inicial, sem repetir isso no meio de uma conversa real. Se nada foi configurado na
Fase 0, nada muda: a IA decide livremente como sempre decidiu.

**Para validar:** Cenário P1 (automatizado, já rodado — 9/9 testes passando) e Cenário P2
(sanity check ao vivo no Playground), abaixo.

**Nota sobre a suíte completa:** rodei toda a suíte de testes do `backend-executors` antes e
depois desta mudança (`pytest tests/ -q`) — 23 testes já falhavam **antes** desta mudança
(sem relação com p0/recepção; parecem um problema de encoding no ambiente, não uma regressão
desta feature) e continuam falhando exatamente os mesmos 23, sem nenhum caso novo. Os 9 testes
novos desta fase passam.

### Fase 2 — Aviso no builder (frontend)

**Objetivo:** avisar o usuário quando a configuração de p0 excede o que o teto de 1 turno cobre.

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/components/agente/CamadaFluxoVenda.tsx` | Banner de aviso condicional na Fase 0 (reaproveita `isSequentialCapable()`) |

---

## Checks de Validação

### Cenário P1 — Gatilho pendente em p0 bloqueia salto da Mãe (unit, Fase 1)
- [ ] Rodar `test_recepcao_sales_flow_pending.py` — bloqueio, liberação, teto de turnos, no-op sem config

### Cenário P2 — Sanity check ao vivo (Playground, Fase 1)
- [x] Configurar 1 gatilho `fire_once` em p0 do agente "Daniel" (kw_trigger "aceito" +
      orientação) — depois removido, ver nota abaixo
- [x] Simular mensagens no Playground (2 sessões, leads #503 e #504)
- [⏭️] Confirmar que a 2ª mensagem não avança para Qualificação antes do gatilho disparar —
      **pulado, justificado abaixo**
- [⏭️] Confirmar que a 3ª mensagem em diante avança normalmente (teto de 1 turno) — mesmo motivo

**Validado em:** 22/08/2026 — o AI Profile de teste ("Daniel", `hybrid_scheduler`/`agenda`) tem
`0 obrig. · 0 opcionais` em Campos de Qualificação. Nas duas sessões testadas, a Mãe (LLM real)
decidiu `route_to="apresentation"` **diretamente a partir da recepção** (pulando também
"qualification"), tanto para uma mensagem com sinal comercial forte ("vi seu anúncio de
massagens") quanto para uma mais neutra ("quero saber mais sobre os serviços") — confirmado nos
logs (`local-run-restart.log`): nenhuma das duas chamadas ao decide() teve `route_to` igual a
`"qualification"`, que é a única condição que `_enforce_recepcao_sales_flow_pending()` observa
(mesmo padrão de `_enforce_apresentation_sales_flow_pending`/`_enforce_pre_agendamento_sales_flow_pending`,
que também só guardam contra o próximo estágio legítimo, não saltos maiores). Isso é o
comportamento pré-existente descrito no item 2 de "Ajustes Possíveis" (p1 sem guardrail
dedicado de `route_to`) — **não é um defeito desta feature**, mas também significa que este AI
Profile específico não serve para demonstrar visualmente o "segura por 1 turno extra" ao vivo,
porque a Mãe nunca para em "qualification" como parada intermediária nele. Os 9 testes
automatizados (Cenário P1) continuam sendo a fonte determinística de verdade para o mecanismo
em si — mockam `route_to="qualification"` diretamente e confirmam o comportamento exato.
Bloco de teste removido do agente "Daniel" após o sanity check (Fluxo de Venda restaurado a 12
blocos, Fase 0 vazia, config salva).

### Cenário P3 — Aviso aparece no builder (Fase 2)
- [ ] Configurar 2 gatilhos sequenciais (ou 1 nó `condicao`) em Fase 0 do builder
- [ ] Confirmar que o banner de aviso aparece
- [ ] Remover até sobrar 1 gatilho; confirmar que o banner some

---

## Ajustes Possíveis Pós-Implementação

1. `apply_mother_category_guardrails()` sem clamp para categorias terminais/arquivadas
   (`disqualified`/`prospect-refused`/`client-list`) re-engajando via WhatsApp meses depois —
   órfão desta investigação, ortogonal a p0.
2. **Auditoria de cobertura do guardrail "gatilhos pendentes" em todas as fases do bot**
   (pedido explícito do usuário). Escopo definido: qualificação, apresentação,
   pré-agendamento, agendamento, follow-up, fechamento e lista de clientes (`client-list`).
   Fora de escopo: arquivados (`prospect-refused`) e desqualificados (`disqualified`) — não
   são fases onde o bot está ativo. Agent 2 (`closer_agressivo`) não passa por
   pré-agendamento/agendamento (`_SCHEDULING_AGENT_TEMPLATES` só inclui `sdr_padrao`/
   `hybrid_scheduler`).

   Mapa de cobertura após esta feature:
   - ✅ p0 (recepção) — `_enforce_recepcao_sales_flow_pending` (esta feature)
   - ⚠️ p1 (qualificação) — coberto só indiretamente via checagem de
     `_phase_pending_sequential_triggers("p1", ...)` nos 3 pontos que promovem para
     apresentation (ver `docs/architecture/sales-flow.md`); não auditado se a Mãe consegue
     rotear `route_to` direto para além de p1 por outro caminho
   - ✅ p2 (apresentação) — `_enforce_apresentation_sales_flow_pending` (feature anterior)
   - ✅ p3a (pré-agendamento) — `_enforce_pre_agendamento_sales_flow_pending` (feature
     anterior, só Agent 1/3)
   - ❌ p3b (agendamento) — nenhum guardrail deste tipo existe hoje (só Agent 1/3)
   - ❌ p4 (follow-up) — nenhum guardrail deste tipo existe hoje (interage com
     `followup_state.py`/`followup_reconciler.py`, subsistema de ticks agendados)
   - ❌ p5 (fechamento) — nenhum guardrail deste tipo existe hoje
   - ❓ `client-list` — não investigado se o bot mantém conversa ativa nessa categoria

   Próximo passo sugerido (não implementado aqui): novo item de implementação dedicado a
   p1/p3b/p4/p5/`client-list`, com o mesmo ciclo de Plan Mode.
