# Select de Direção sem opção para origens técnicas

**Branch:** _(a definir no Plan Mode)_
**Status:** Aguardando Plan Mode

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`lead-origin-labels-amigaveis.md`. Aquela implementação corrigiu a exibição
em modo leitura (`formatLeadOriginLabel()`), mas o Select de edição de
"Direção" (`LEAD_DIRECTION_OPTIONS`, `frontend-crm/src/lib/lead-origin.ts`)
continua oferecendo só 2 opções: `Manual` ("Inbound — o lead procurou
primeiro") e `outbound` ("Outbound — eu abordei primeiro").

---

## Problemas Identificados (estado anterior)

1. **Select em branco para origens técnicas:** um lead com `origin` gravado
   por um caminho técnico (`whatsapp_inbound`, `Formulário Website`,
   `Planilha`) não bate em nenhuma das 2 opções do Select. Em
   `LeadCardDialog.tsx`, ao entrar em modo edição, o campo aparece vazio
   (placeholder "Quem procurou primeiro?") em vez de refletir o valor real —
   ver `docs/architecture/leads-schema.md`, seção "`origin` (direção) x
   `acquisition_channel`". Isso pode levar o operador a pensar que a origem
   não foi registrada, ou a escolher uma opção manualmente e sobrescrever sem
   querer o valor técnico original (`onValueChange` só muda o estado se o
   operador efetivamente selecionar algo — mas a falta de feedback visual é o
   problema).

---

## Diagnóstico (a fazer em Plan Mode)

- Decidir se o Select ganha uma 3ª opção "somente leitura" que reflete o
  valor técnico atual (ex.: exibir o label amigável já calculado por
  `formatLeadOriginLabel()` como item desabilitado/pré-selecionado), ou se o
  campo vira somente-leitura quando `origin` já é um valor técnico (só permite
  trocar para Manual/outbound explicitamente, não permite "voltar" para o
  valor técnico depois).
- Confirmar comportamento de salvamento: hoje, salvar sem tocar no campo
  preserva o valor técnico original (via cópia do lead em `editedLead`) — essa
  garantia não pode regredir com a mudança.
- Escopo é só frontend (UI do Select) — não deve alterar `_classify_lead_origin()`
  nem os valores gravados em `leads.origin`.

---

## Plano de Implementação

_A preencher após Plan Mode e aprovação do utilizador._

---

## Checks de Validação

_A definir em Plan Mode._
