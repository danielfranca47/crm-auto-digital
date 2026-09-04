# Labels amigáveis incompletos para valores técnicos de `origin`

**Branch:** `fix/lead-origin-labels-amigaveis`
**Status:** Em andamento

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

2. **`formatLeadOriginLabel()` não é chamada em 3 pontos que exibem `origin`
   cru** — gap encontrado durante o diagnóstico, não estava no problema
   original:
   - `frontend-crm/src/components/LeadCard.tsx:224` — card do Kanban (visão
     principal do pipeline)
   - `frontend-crm/src/components/prospection/ProspectionCard.tsx:109` — card
     do board de prospecção
   - `frontend-crm/src/components/SearchAutocomplete.tsx:144` — resultado da
     busca

---

## Diagnóstico

### Levantamento dos valores reais de `origin`

Tentativa de consultar o SQLite de produção via `railway ssh` para confirmar
que não há valor técnico fora dos já conhecidos foi bloqueada pelo
classificador do Auto Mode (sem exec arbitrário liberado — mesma política já
registrada em memória). Na ausência disso, o levantamento foi feito por grep
exaustivo de todo `INSERT`/`UPDATE` em `leads.origin` no backend. É uma lista
fechada: a única forma de gravar `origin` é código — o Select de edição do
frontend só oferece "Manual"/"outbound", não há campo livre.

| Valor técnico | Onde é gravado |
|---|---|
| `Manual` (default) | `backend-crm/models.py:20` |
| `outbound` | `services/jobs_service.py:1168`, `routes/leads.py` (PATCH manual) |
| `whatsapp_inbound` | `services/whatsapp_inbound/guardrail.py:47,56` |
| `Formulário Website` | `routes/public.py:202` |
| `Planilha` | `automations/assistente_ia/processor.py:129` |

`_classify_lead_origin()` (`services/ai_orchestrator/orchestrator.py:247`) já
trata isso como conjunto fechado: só `outbound` é outbound, qualquer outro
valor é inbound por default seguro. O mapa de labels segue a mesma semântica.

### Formato do mapa

Genérico, não só hardcoded 1:1: qualquer valor desconhecido no futuro cai num
fallback `"Inbound (<valor cru>)"` em vez de aparecer cru — coerente com o
default-safe do `_classify_lead_origin()`. Evita repetir o problema se
aparecer um valor novo amanhã.

### Escopo confirmado

- Só exibição (frontend) — não altera `leads.origin` gravado nem
  `_classify_lead_origin()`.
- Não mexe no Select de edição (`LEAD_DIRECTION_OPTIONS` continua só
  Manual/outbound — assunto separado, fora do escopo).

---

## Abordagem

```
lead.origin (valor cru gravado)
  → formatLeadOriginLabel(origin)
      ├─ "manual"              → "Inbound"
      ├─ "outbound"            → "Outbound"
      ├─ "whatsapp_inbound"    → "Inbound (WhatsApp)"
      ├─ "formulário website"  → "Inbound (Formulário do site)"
      ├─ "planilha"            → "Inbound (Planilha)"
      ├─ "" / null             → "—"
      └─ qualquer outro valor  → "Inbound (<valor original>)"
  → usado em todo ponto de exibição (LeadCardDialog, KanbanBoard, LeadCard,
    ProspectionCard, SearchAutocomplete)
```

---

## Plano de Implementação

### Fase 1 — Cobertura completa do mapa + uso em todos os pontos de exibição

**Objetivo:** cobrir os 5 valores técnicos conhecidos com fallback genérico, e
usar `formatLeadOriginLabel()` nos 3 pontos que hoje mostram `lead.origin` cru.

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/lib/lead-origin.ts` | `formatLeadOriginLabel()`: adicionar `whatsapp_inbound`, `formulário website`, `planilha`; fallback genérico `Inbound (<valor original>)` para qualquer outro valor não vazio |
| `frontend-crm/src/components/LeadCard.tsx` | linha 224: `{lead.origin}` → `{formatLeadOriginLabel(lead.origin)}` + import |
| `frontend-crm/src/components/prospection/ProspectionCard.tsx` | linha 109: `{lead.origin}` → `{formatLeadOriginLabel(lead.origin)}` + import |
| `frontend-crm/src/components/SearchAutocomplete.tsx` | linha 144: `highlightMatch(lead.origin, searchTerm)` → `highlightMatch(formatLeadOriginLabel(lead.origin), searchTerm)` + import |

Os usos em `ProspectionBoard.tsx:50` e `SearchAutocomplete.tsx:42` são só
filtro de busca por texto (comparam contra o valor cru) — ficam como estão,
não são exibição.

```typescript
// ANTES
export function formatLeadOriginLabel(origin: string | null | undefined): string {
  const normalized = (origin || "").trim().toLowerCase();
  if (normalized === "manual") return "Inbound";
  if (normalized === "outbound") return "Outbound";
  return origin || "—";
}

// DEPOIS
export function formatLeadOriginLabel(origin: string | null | undefined): string {
  const raw = (origin || "").trim();
  const normalized = raw.toLowerCase();
  if (!raw) return "—";
  if (normalized === "manual") return "Inbound";
  if (normalized === "outbound") return "Outbound";
  if (normalized === "whatsapp_inbound") return "Inbound (WhatsApp)";
  if (normalized === "formulário website") return "Inbound (Formulário do site)";
  if (normalized === "planilha") return "Inbound (Planilha)";
  return `Inbound (${raw})`;
}
```

---

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `42c6335b9c8003ce26fff0be40b560bec0f5741e` | Labels amigáveis para os 5 valores técnicos de `origin` + uso em todos os pontos de exibição |

**Detalhes do commit `42c6335`:**
- `frontend-crm/src/lib/lead-origin.ts` — `formatLeadOriginLabel()` ganha `whatsapp_inbound`, `formulário website`, `planilha` e fallback genérico `Inbound (<valor>)`
- `frontend-crm/src/components/LeadCard.tsx` — card do Kanban passa a usar `formatLeadOriginLabel()`
- `frontend-crm/src/components/prospection/ProspectionCard.tsx` — card do board de prospecção, idem
- `frontend-crm/src/components/SearchAutocomplete.tsx` — resultado da busca, idem (mantém o destaque do termo buscado)

### Relatório da Fase 1 — o que mudou na prática

**Antes:** quando um lead chegava pelo WhatsApp, pelo formulário do site ou por
uma planilha importada, o campo "Origem" mostrava o valor técnico cru
(`whatsapp_inbound`, `Formulário Website`, `Planilha`) em 5 lugares diferentes
da tela — card do Kanban, modal do lead, card de prospecção e resultado da
busca. Três desses 5 lugares nem convertiam "Manual"/"outbound" para
"Inbound"/"Outbound" — mostravam tudo cru.

**Agora:** todo lugar que mostra a origem do lead usa o mesmo texto amigável:
"Inbound", "Outbound", "Inbound (WhatsApp)", "Inbound (Formulário do site)" ou
"Inbound (Planilha)". Se amanhã o sistema gravar um valor técnico novo que
ainda não foi mapeado, ele aparece como "Inbound (<valor>)" em vez de cru —
não fica mais sujeito a esse mesmo problema se surgir um valor novo.

**Para validar:** Cenários P1, P2, P3 e P4, abaixo.

---

## Checks de Validação

### Cenário P1 — Kanban board (visão principal)
- [ ] Abrir o Kanban com leads de origens variadas (`whatsapp_inbound`,
      `Formulário Website`, `Planilha`, `Manual`, `outbound`)
- [ ] Confirmar que cada card mostra o label amigável (não o valor cru) no
      campo "Origem"

### Cenário P2 — Modal do lead (LeadCardDialog)
- [ ] Abrir um lead com origem `whatsapp_inbound` (ou outro valor técnico)
- [ ] Confirmar que o modo leitura mostra "Inbound (WhatsApp)" etc.

### Cenário P3 — Board de prospecção
- [ ] Abrir a página de Prospecção com leads outbound
- [ ] Confirmar que o card mostra o label amigável

### Cenário P4 — Busca (SearchAutocomplete)
- [ ] Buscar um lead e conferir que o resultado mostra o label amigável (com
      destaque do termo buscado ainda funcionando)

---

## Ajustes Possíveis Pós-Implementação

- O Select de edição (`LEAD_DIRECTION_OPTIONS`) continua só com
  Manual/outbound — se um lead tiver `whatsapp_inbound` e o operador entrar em
  modo edição, o Select fica sem seleção correspondente (comportamento
  pré-existente, fora do escopo desta implementação).
