# Implementar execução em runtime dos blocos `webhook`, `condicao` e `espera`

**Branch:** (a definir)
**Status:** Aguardando Plan Mode

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`fix-intent-trigger-fase-entrada.md`.

O builder visual do Fluxo de Venda (Camada 7, `CamadaFluxoVenda.tsx`) já permite
configurar três tipos de bloco de lógica — `webhook` (disparar chamada HTTP externa),
`condicao` (bifurcação com ramos `branch_yes`/`branch_no`) e `espera` (agendar
próxima avaliação após um delay) — com a infraestrutura de dados completa (schema,
UI de configuração, persistência em `sales_flow.phases[].blocks[]`). Nenhum dos três
tem execução em runtime no `decision_engine.py` (`_evaluate_sales_flow_phases()`) —
são blocos que o usuário pode configurar na UI mas que não têm nenhum efeito real na
conversa.

Isso já estava documentado como limitação conhecida em
`docs/architecture/sales-flow.md` ("blocos reservados para implementação futura")
antes do fix `fix-intent-trigger-fase-entrada` — não é uma regressão introduzida por
ele, mas foi validado como item ainda relevante durante a graduação dessa
implementação.

---

## Problemas Identificados (estado anterior)

1. **`webhook` sem execução:** bloco de ação para chamar uma URL externa quando um
   trigger dispara — configurável na UI, sem nenhum código correspondente em
   `_evaluate_sales_flow_phases()` (`decision_engine.py`).
2. **`condicao` sem execução:** bifurcação `branch_yes`/`branch_no` — schema de dados
   existe, mas o motor de decisão não avalia a condição nem segue nenhum ramo.
3. **`espera` sem execução:** agendamento de reavaliação após `wait_value`/`wait_unit`
   — sem integração com a fila de jobs (`services/jobs_service.py`) ou com o
   `followup_reconciler.py`, que já resolve um problema parecido (agendar próxima
   ação) para follow-up.

---

## Abordagem

(A definir em Plan Mode — três sub-features distintas, provavelmente merecem
diagnóstico e fases separadas. Pontos a considerar:)
- `espera` provavelmente reaproveita padrões já existentes em
  `services/followup_reconciler.py`/`services/jobs_service.py` para agendar
  reavaliação futura — evitar reinventar uma fila paralela.
- `webhook` precisa de decisão sobre retry/timeout/tratamento de falha de rede, e se
  a chamada é síncrona (bloqueia a resposta ao lead) ou assíncrona (job).
- `condicao` precisa de uma linguagem de avaliação de condição (comparar campo de
  qualificação, resultado de outro bloco, etc.) — o schema atual do bloco deve ser
  revisado para confirmar que já suporta o que for decidido.

---

## Plano de Implementação

(A preencher após diagnóstico em Plan Mode — ver
`docs/implementations/_guia-documentar-implementacao.md`, Passo 0. Considerar dividir
em três implementações separadas, uma por tipo de bloco, dado que não têm
dependências fortes entre si.)

---

## Checks de Validação

(A definir junto com o plano de implementação.)
