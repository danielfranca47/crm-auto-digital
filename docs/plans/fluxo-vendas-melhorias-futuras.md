# Fluxo de Venda — melhorias futuras

> Contexto: itens deixados de fora da graduação de `fix-fluxo-vendas-sequencial.md`
> (gating sequencial de gatilhos, guardrail de transição de fase, `is_phase_entry`,
> bloco `booking_signal_opener` editável, funil visual no Kanban). Validados como
> úteis pelo utilizador na triagem pós-graduação (Passo 5b), mas marcados
> não-urgentes.

## M1 — Migrar instrução de agendamento para `consultivo` também

**Prioridade: BAIXA**

Na Fase 4 de `fix-fluxo-vendas-sequencial.md`, a instrução hardcoded "RECONHECIMENTO
DE INTERESSE DE AGENDAMENTO" (`decision_engine.py`, `_build_child_prompt_apresentation`,
variável `_booking_signal_block`) foi migrada para um bloco editável/removível
(`booking_signal_opener`) só para `agent_mode_normalized == "agenda"`.

Para `consultivo`, a instrução continua hardcoded. Diferente do caso do Closer (ver
`fix-instrucao-agendamento-closer.md`, item urgente da mesma triagem), aqui não há
contradição óbvia de propósito — `consultivo` usa `presentation_variant="scheduler"`
por padrão (mesmo formato do `agenda`), então "perguntar dia/horário" não é
tematicamente errado. O problema é mais sutil: o pipeline de `consultivo`
(`SALES_FLOW_PHASES_BY_AGENT_MODE.consultivo = ['p0','p1','p2','p4','p5']`) não tem
fase de pré-agendamento/agendamento, então `recommended_next_category='pre-agendamento'`
não corresponde a nenhum estágio real do funil dele (ainda que seja só informativo,
sem aplicação automática).

**O que fazer:** estender o mesmo padrão de `booking_signal_opener` (banner/card no
builder, leitura condicional no backend) para `agent_mode_normalized == "consultivo"`
— reaproveitando a infraestrutura já criada na Fase 4, só ampliando a condição de
`agent_mode_normalized == "agenda"` para incluir `"consultivo"`.

## M2 — Detalhar marcos do Fluxo de Venda no modal do lead

**Prioridade: BAIXA**

O funil resumido no card do Kanban (Fase 5 de `fix-fluxo-vendas-sequencial.md`,
componente `SalesFlowFunnel` em `LeadCard.tsx`) mostra só a fase atual e as fases
concluídas — não detalha *quais* gatilhos específicos dentro da fase atual já
dispararam (ex.: "já aceitou ver a tabela" vs. "ainda não escolheu o serviço").

Essa informação já existe persistida (`leads.triggers_fired`, JSON array de block
IDs) mas nunca chega à UI além do resumo por fase.

**O que fazer:** no modal completo do lead (`LeadCardDialog.tsx`), adicionar uma
secção que resolva `triggers_fired` contra os blocos `intent_trigger`/`kw_trigger`
configurados na fase atual do `sales_flow` do AI Profile, mostrando o `intent`/label
de cada gatilho já disparado (ex.: lista "✅ Cliente aceitou ver a tabela de preços").
Precisa buscar `ai_profile.sales_flow` no frontend (hoje só usado em
`CamadaFluxoVenda.tsx`) para resolver os labels a partir dos `block_id`.
