# Labels amigáveis incompletos para valores técnicos de `origin`

**Branch:** _(a definir no Plan Mode)_
**Status:** Aguardando Plan Mode

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`lead-origem-canal-aquisicao.md`. Aquela implementação introduziu
`formatLeadOriginLabel()` (`frontend-crm/src/lib/lead-origin.ts`), que traduz
`origin` para um rótulo amigável no modo leitura do lead — mas só cobre os 2
valores canônicos do Select (`Manual` → "Inbound", `outbound` → "Outbound").
Qualquer outro valor técnico gravado pelo sistema é exibido cru na tela.

---

## Problemas Identificados (estado anterior)

1. **Valores técnicos sem rótulo amigável:** `whatsapp_inbound` (gravado pelo
   webhook inbound), `Formulário Website` (gravado pelo formulário público) e
   `Planilha` (import em massa) aparecem literalmente na UI (`LeadCardDialog.tsx`,
   `KanbanBoard.tsx`) em vez de um texto mais legível para o operador — ex.:
   "Inbound (WhatsApp)", "Inbound (Formulário do site)", "Inbound (Planilha)".

---

## Diagnóstico (a fazer em Plan Mode)

- Levantar a lista completa de valores reais de `origin` já gravados em
  produção (query direta no banco) para não deixar nenhum caso real de fora
  do mapa de labels.
- Decidir se o mapa fica hardcoded em `formatLeadOriginLabel()` ou se precisa
  de um formato mais genérico (ex.: prefixo "Inbound (…)" + o valor cru como
  sufixo, para não quebrar quando aparecer um valor novo não mapeado).
- Confirmar que a mudança é só de exibição (frontend) — não deve alterar o
  valor gravado em `leads.origin` nem a classificação usada pela IA
  (`_classify_lead_origin()` continua olhando o valor cru).

---

## Plano de Implementação

_A preencher após Plan Mode e aprovação do utilizador._

---

## Checks de Validação

_A definir em Plan Mode._
