# Fix: blocos da fase Recepção (p0) do Fluxo de Venda nunca disparam

**Branch:** (ainda não criada — nasce após Plan Mode aprovado)
**Status:** Aguardando Plan Mode

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`nome-whatsapp-lead-variaveis-fluxo-venda.md` (achado lateral, confirmado ao
vivo durante o teste da Fase 3 dessa implementação, 20/08/2026).

`docs/architecture/sales-flow.md` documenta a fase `p0` (Recepção) como
"Sempre ativo? Sim", mas um bloco `mensagem`/`orientacao` configurado em p0
nunca dispara na prática: `_evaluate_sales_flow_phases()`
(`backend-executors/app/services/decision_engine.py`) só avalia blocos das
fases `p1`–`p5` — `p0` está fora do mapa `_ROUTE_TO_PHASE_ID` usado por essa
função.

Confirmado via chamada real ao Playground durante o teste da feature acima:
um bloco `mensagem` configurado em Recepção resultou em
`phase_trigger_fired=false` e `auto_items=[]`. Não é causado por nenhuma
mudança daquela feature — a resolução de variáveis `{{}}` funciona
corretamente onde os blocos SÃO avaliados (confirmado em p2/Apresentação);
o problema é anterior e independente.

---

## Problemas Identificados (estado anterior)

1. **`_evaluate_sales_flow_phases()` não avalia p0:** `_ROUTE_TO_PHASE_ID`
   (`backend-executors/app/services/decision_engine.py`) mapeia
   `effective_route_to → phase_id` apenas para `p1`–`p5`. Blocos de ação
   (`mensagem`, `midia`, `orientacao`, `avancar_fase`) configurados na fase
   `p0` no builder (`CamadaFluxoVenda.tsx`) são salvos normalmente em
   `ai_profile.sales_flow.phases[].blocks[]`, mas nunca chegam a ser
   avaliados em runtime.

2. **Guardrail de p0 já existe e assume que blocos disparam:**
   `_enforce_recepcao_sales_flow_pending` (mesmo arquivo) já trata `p0` como
   fase com gatilhos sequenciais pendentes (bloqueia a Mãe de sair da
   recepção antes de um `kw_trigger`/`intent_trigger` `fire_once` disparar)
   — mas se os blocos de p0 nunca são avaliados por
   `_evaluate_sales_flow_phases()`, o próprio gatilho sequencial de p0 nunca
   dispara (nunca é persistido em `leads.triggers_fired`), potencialmente
   deixando o guardrail sempre bloqueado a partir do teto de 1 turno extra
   (`_MAX_RECEPCAO_ENFORCED_OUTBOUND_TURNS`) — **precisa confirmação em Plan
   Mode**: verificar se isso já é coberto/mitigado por esse teto ou se é um
   segundo bug decorrente do primeiro.

3. **Documentação desalinhada:** `docs/architecture/sales-flow.md`, tabela de
   fases, diz `p0` "Sempre ativo? Sim" — não reflete o comportamento real
   hoje. Corrigir junto com o fix (não fazer parte do Plan Mode, é
   consequência direta da correção).

---

## Abordagem

<A definir em Plan Mode — diagnóstico ainda não fez leitura completa de
`_evaluate_sales_flow_phases()` para propor a correção (ex.: incluir `p0` no
`_ROUTE_TO_PHASE_ID`, ou criar tratamento dedicado, dado que `"recepcao"`
nunca é persistido em `leads.category` — ver nota em `sales-flow.md` sobre
`_enforce_recepcao_sales_flow_pending`, "Condição de 'engajado' invertida").>

---

## Plano de Implementação

<A definir em Plan Mode.>

---

## Checks de Validação

<A definir em Plan Mode.>

---

## Ajustes Possíveis Pós-Implementação

<A definir após implementação.>
