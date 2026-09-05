# Select de Direção sem opção para origens técnicas

**Branch:** `fix/select-direcao-sem-opcao-origem-tecnica`
**Status:** Todos os cenários validados (05/09/2026)

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

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `7916d81e1b2c6b508c67cb8f99905db82ca96b4d` | Item desabilitado com o valor técnico atual no Select de Direção |

**Detalhes do commit `7916d81`:**
- `frontend-crm/src/components/LeadCardDialog.tsx` — Select de "Direção" ganha item extra desabilitado quando `origin` não bate com Manual/outbound

### Relatório da Fase 1 — o que mudou na prática

**Antes:** ao editar um lead que chegou pelo WhatsApp, pelo formulário do
site ou por planilha, o campo "Direção" aparecia vazio no modo edição
(placeholder "Quem procurou primeiro?"), como se a origem nunca tivesse sido
registrada — mesmo o valor já estando salvo corretamente por trás.

**Agora:** o campo mostra o texto real (ex.: "Inbound (WhatsApp) — atual")
mesmo em modo edição. Esse texto não pode ser escolhido de novo no dropdown —
só serve para informar; para mudar a direção, o operador escolhe
explicitamente "Inbound" ou "Outbound".

**Para validar:** Cenários P1, P2, P3 e P4, abaixo.

---

## Checks de Validação

### Cenário P1 — Lead com origem técnica
- [x] Abrir um lead com `origin` técnico (ex.: `whatsapp_inbound`) e entrar em
      modo edição
- [x] Confirmar que o Select mostra "Inbound (WhatsApp) — atual" em vez do
      placeholder vazio
- [x] Confirmar que o item extra não é clicável no dropdown
- **Validado em:** 05/09/2026 — testado via browser (chrome-devtools MCP) no
  lead "França" (id 483, `whatsapp_inbound`) da conta de teste local. Select
  mostrou "Inbound (WhatsApp) — atual" com checkmark; o dropdown listou só as
  2 opções canônicas como selecionáveis (o item extra não aparece na lista de
  opções interativas, só como valor exibido/pré-selecionado).

### Cenário P2 — Salvar sem tocar no campo
- [x] No mesmo lead, editar outro campo (ex.: observações) sem tocar no
      Select de Direção, e salvar
- [x] Confirmar que `origin` continua com o valor técnico original
- **Validado em:** 05/09/2026 — editado o campo "Comentários/Notas" do lead
  483 sem tocar no Select; confirmado via banco (`SELECT * FROM leads WHERE
  id=483`) que `origin` continuou `whatsapp_inbound` e `observations` foi
  salvo corretamente.

### Cenário P3 — Trocar explicitamente para Manual/Outbound
- [x] No mesmo lead, escolher "Outbound — eu abordei primeiro" e salvar
- [x] Confirmar que `origin` vira `"outbound"` (sem regressão)
- **Validado em:** 05/09/2026 — trocado explicitamente para "Outbound — eu
  abordei primeiro" no lead 483 e salvo; modo leitura passou a mostrar
  "Direção: Outbound" (sem regressão no fluxo de troca explícita).

### Cenário P4 — Lead com origem já canônica (regressão)
- [x] Abrir um lead com `origin` = `Manual` ou `outbound`
- [x] Confirmar que o Select mostra a opção certa pré-selecionada, sem o item
      extra aparecer
- **Validado em:** 05/09/2026 — lead "DF FLOW BARBERSHOP" (`origin=Manual`)
  mostrou o Select já com "Inbound — o lead procurou primeiro" pré-selecionado,
  sem nenhum item extra — sem regressão para leads com origem canônica.

---

## Ajustes Possíveis Pós-Implementação

_Nenhum identificado até o momento._
