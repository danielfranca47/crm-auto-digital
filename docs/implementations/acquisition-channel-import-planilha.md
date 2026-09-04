# Canal de aquisição não é preenchido na importação por planilha

**Branch:** `worktree-feat+acquisition-channel-import-planilha`
**Status:** Em andamento

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

## Diagnóstico

- **Já existe?** Não. `map_row_to_lead()` em
  `backend-crm/automations/assistente_ia/processor.py:107-145` não lê nem
  grava `acquisition_channel` — o dict retornado não tem essa chave, então
  `create_lead()` nunca a insere e `update_lead_light()` nunca a preserva.
- **Mecanismo de mapeamento já existente a reutilizar:** o import já suporta
  mapeamento de colunas configurável pelo utilizador via `column_map` (dict
  campo-lógico → nome-da-coluna-na-planilha), passado do frontend
  (`AssistenteIA.tsx`) → `POST /api/assistente-ia/processar`
  (`routes/assistente_ia.py:103`) → `AssistIAProcessor.process()` →
  `map_row_to_lead(row, column_map=column_map)`. O padrão a seguir é
  idêntico ao já usado para `empresa`, `contato`, `telefone`, `notas`: helper
  `_pick(campo_logico, *fallbacks_de_nome_de_coluna)`.
- **Risco de colisão de nome:** a planilha pode ter uma coluna chamada
  "origem", mas essa palavra já é usada como fallback bruto (`d.get("origem")`,
  linha 129) para o campo **`origin`** (direção da conversa — inbound/outbound),
  que é semanticamente diferente e É lido pela IA. Não reaproveitei "origem"
  como alias de `acquisition_channel` para não quebrar esse comportamento
  existente — os aliases automáticos ficam em "canal", "canal_aquisicao" e
  "fonte" (nomes que não colidem com nada hoje). O mapeamento explícito via
  `column_map` (UI) continua sendo o caminho robusto para qualquer nome de
  coluna, incluindo variações de "Origem do Lead".
- **Sem impacto em banco de dados** — a coluna `acquisition_channel` já existe
  na tabela `leads` desde a implementação anterior.
- **Sem impacto em IA/orquestração** — confirmado por
  `docs/architecture/leads-schema.md:75-78`.

---

## Plano de Implementação

### Fase 1 — Backend: mapear e persistir `acquisition_channel` na importação

| Arquivo | O que muda |
|---|---|
| `backend-crm/automations/assistente_ia/processor.py` | `map_row_to_lead()`: adicionar `acquisition_channel = _pick("acquisition_channel", "canal", "canal_aquisicao", "fonte")` e incluir `"acquisition_channel": acquisition_channel` no dict retornado. `update_lead_light()`: adicionar `"acquisition_channel"` à lista `columns` para que o merge (`overwrite="update"`) preserve/preencha o campo do mesmo jeito que os demais — só sobrescreve se o lead existente estiver vazio nesse campo. |
| `backend-crm/tests/test_processor_lead_mapping.py` | Novo teste cobrindo: (a) `column_map` explícito mapeando uma coluna arbitrária para `acquisition_channel`; (b) fallback automático via coluna chamada `canal`; (c) ausência da coluna → `None` (sem inventar valor). |

Nenhuma mudança em `create_lead()` — o INSERT é dinâmico a partir das chaves
do dict, então a nova chave é persistida automaticamente.

### Fase 2 — Frontend: expor o campo no mapeamento de colunas do Assistente IA

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/pages/AssistenteIA.tsx` | `COLUMN_ALIASES`: adicionar `acquisition_channel: ['canal', 'canal_aquisicao', 'fonte', 'canal de aquisição']` para auto-detecção. Lista de campos da UI de mapeamento (hoje `['empresa', 'contato', 'telefone', 'notas']`): adicionar `'acquisition_channel'`. Como a label usa `className="capitalize"` sobre o nome cru do campo (ficaria "Acquisition_channel"), introduzir um pequeno mapa `FIELD_LABELS` (`{ empresa: 'Empresa', contato: 'Contato', telefone: 'Telefone', notas: 'Notas', acquisition_channel: 'Canal de aquisição' }`) e usar `FIELD_LABELS[field]` no lugar do texto cru + `capitalize`. |

Fora de escopo, deliberadamente: não adicionar `acquisition_channel` à grid de
prévia (a prévia hoje já omite `notas` e serve só para conferência rápida de
empresa/contato/dedup — manter simetria com o que já existe).

---

## Checks de Validação

### Cenário P1 — Mapeamento explícito via UI
- [ ] Planilha CSV com colunas `Empresa`, `Telefone`, `Origem Marketing`
- [ ] No "1.5 Mapeamento de Colunas", mapear `Canal de aquisição` → `Origem Marketing`
- [ ] Confirmar mapeamento, processar, abrir o lead criado no Kanban → campo
      "Canal de aquisição" preenchido com o valor da planilha

### Cenário P2 — Auto-detecção por nome de coluna
- [ ] Planilha CSV com uma coluna literalmente chamada `canal`
- [ ] Upload → mapeamento já vem pré-preenchido automaticamente para `Canal de aquisição`
- [ ] Processar → lead criado com `acquisition_channel` correto

### Cenário P3 — Planilha sem essa coluna
- [ ] Planilha sem nenhuma coluna relacionada a canal
- [ ] Processar normalmente → lead criado com `acquisition_channel = NULL` (campo em branco no card, sem erro)

### Cenário P4 — Overwrite "update" preserva/preenche sem sobrescrever
- [ ] Lead já existente sem `acquisition_channel`, reimportar planilha com essa coluna preenchida e `overwrite=update` → campo passa a ser preenchido
- [ ] Lead já existente **com** `acquisition_channel` já preenchido manualmente, reimportar com valor diferente na planilha e `overwrite=update` → valor manual é preservado (mesmo comportamento hoje aplicado a `companyName`/`contactName`/etc.)

---

## Ajustes Possíveis Pós-Implementação

- A grid de prévia do Assistente IA não mostra `acquisition_channel` (nem
  mostra `notas` hoje) — se um utilizador pedir para conferir o canal antes de
  processar, adicionar essa linha à prévia é uma extensão pequena e isolada.
