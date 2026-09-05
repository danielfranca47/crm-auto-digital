# Select de Direção sem opção para origens técnicas

**Branch:** `fix/select-direcao-sem-opcao-origem-tecnica`
**Status:** Em andamento

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

## Diagnóstico

- `LeadCardDialog.tsx:394-396` — `editedLead` nasce sempre como cópia exata
  do `lead` (`setEditedLead({ ...lead })`), ou seja, `editedLead.origin` já
  contém o valor técnico correto desde o início. O bug é **puramente
  visual**: o Radix `<Select value={...}>` (linhas 826-843) só sabe renderizar
  o texto de um valor que bate com um `<SelectItem>` existente — como só há 2
  itens (`LEAD_DIRECTION_OPTIONS`), qualquer outro valor cai no placeholder.
- Salvar sem tocar no campo já preserva o valor técnico original hoje
  (`onValueChange` só dispara com interação explícita) — essa garantia não
  pode regredir.
- `NewLeadModal.tsx` (criação) não tem esse problema: `origin` nasce sempre
  `"Manual"` ou vazio, nunca um valor técnico pré-existente — fora do escopo.
- Escopo é só frontend/exibição — não toca `_classify_lead_origin()` nem
  altera valores gravados em `leads.origin`.

### Abordagem escolhida

Injetar dinamicamente um 3º `<SelectItem>` **desabilitado** no topo da lista,
só quando `editedLead.origin` não bate com nenhum dos 2 valores canônicos:
value = o próprio valor técnico cru, label = `formatLeadOriginLabel(origin)`
(reaproveita a função já existente) + sufixo indicando que é somente leitura.
Radix Select localiza o item pelo `value` para renderizar o texto selecionado
mesmo quando o item está `disabled` — então o Select passa a mostrar
"Inbound (WhatsApp) — atual" em vez do placeholder, mas o item não é
clicável: o operador só consegue *mudar* a direção escolhendo Manual ou
Outbound explicitamente.

---

## Plano de Implementação

### Fase 1 — Item desabilitado com o valor técnico atual

**Objetivo:** Select mostra o label amigável do valor técnico atual em vez de
placeholder vazio, sem permitir "reselecioná-lo".

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/components/LeadCardDialog.tsx` | No bloco do Select de "Direção" (~linha 826-843): antes de mapear `LEAD_DIRECTION_OPTIONS`, renderizar condicionalmente um `<SelectItem>` extra desabilitado quando `editedLead.origin` não bate com nenhum valor canônico |

```tsx
// DEPOIS (dentro do <SelectContent>)
{editedLead?.origin && !LEAD_DIRECTION_OPTIONS.some((o) => o.value === editedLead.origin) && (
  <SelectItem value={editedLead.origin} disabled>
    {formatLeadOriginLabel(editedLead.origin)} — atual
  </SelectItem>
)}
{LEAD_DIRECTION_OPTIONS.map((option) => (
  <SelectItem key={option.value} value={option.value}>
    {option.label}
  </SelectItem>
))}
```

---

## Checks de Validação

### Cenário P1 — Lead com origem técnica
- [ ] Abrir um lead com `origin` técnico (ex.: `whatsapp_inbound`) e entrar em
      modo edição
- [ ] Confirmar que o Select mostra "Inbound (WhatsApp) — atual" em vez do
      placeholder vazio
- [ ] Confirmar que o item extra não é clicável no dropdown

### Cenário P2 — Salvar sem tocar no campo
- [ ] No mesmo lead, editar outro campo (ex.: observações) sem tocar no
      Select de Direção, e salvar
- [ ] Confirmar que `origin` continua com o valor técnico original

### Cenário P3 — Trocar explicitamente para Manual/Outbound
- [ ] No mesmo lead, escolher "Outbound — eu abordei primeiro" e salvar
- [ ] Confirmar que `origin` vira `"outbound"` (sem regressão)

### Cenário P4 — Lead com origem já canônica (regressão)
- [ ] Abrir um lead com `origin` = `Manual` ou `outbound`
- [ ] Confirmar que o Select mostra a opção certa pré-selecionada, sem o item
      extra aparecer

---

## Ajustes Possíveis Pós-Implementação

_Nenhum identificado até o momento._
