# Canal de aquisição não é preenchido na importação por planilha

**Branch:** _(a definir no Plan Mode)_
**Status:** Aguardando Plan Mode

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`lead-origem-canal-aquisicao.md`. Aquela implementação criou o campo
`leads.acquisition_channel` (canal de marketing — Facebook Ads, Indicação,
Website...) e o expôs na criação/edição manual de lead (`NewLeadModal.tsx`,
`LeadCardDialog.tsx`) e na API (`POST`/`PATCH /api/leads`). O fluxo de
importação em massa por planilha, no entanto, não foi tocado — hoje não é
possível preencher `acquisition_channel` durante uma importação, só depois,
editando lead por lead manualmente.

---

## Problemas Identificados (estado anterior)

1. **Import por planilha não mapeia `acquisition_channel`:**
   `backend-crm/automations/assistente_ia/processor.py` (`map_row_to_lead`)
   não lê nem grava esse campo, mesmo que a planilha do utilizador tenha uma
   coluna equivalente (ex.: "Canal", "Origem do Lead", "Fonte").

---

## Diagnóstico (a fazer em Plan Mode)

- Confirmar o formato aceito hoje pela importação (colunas esperadas,
  cabeçalho fixo ou mapeável) para decidir se `acquisition_channel` vira uma
  coluna reconhecida por nome ou um mapeamento configurável.
- Decidir comportamento quando a planilha não tiver essa coluna (deixar
  `NULL`, igual aos demais pontos de criação — não inventar valor).
- Confirmar que nenhuma lógica de IA precisa ser tocada (o campo já é,
  deliberadamente, não lido pela IA — ver `docs/architecture/leads-schema.md`).

---

## Plano de Implementação

_A preencher após Plan Mode e aprovação do utilizador._

---

## Checks de Validação

_A definir em Plan Mode._
