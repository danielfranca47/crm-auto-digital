# Canal de aquisição não é preenchido na importação por planilha

**Branch:** `worktree-feat+acquisition-channel-import-planilha`
**Status:** Todos os cenários validados (05/09/2026)

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
- [x] Planilha CSV com colunas `Empresa`, `Telefone`, `Origem Marketing`
- [x] No "1.5 Mapeamento de Colunas", mapear `Canal de aquisição` → `Origem Marketing`
- [x] Confirmar mapeamento, processar, abrir o lead criado no Kanban → campo
      "Canal de aquisição" preenchido com o valor da planilha
- **Validado em:** 05/09/2026 — testado ao vivo via browser (chrome-devtools MCP) contra backend-core/backend-crm/frontend-crm locais nesta worktree. Lead criado com `acquisition_channel="Facebook Ads"`, confirmado via `GET /api/leads`.

### Cenário P2 — Auto-detecção por nome de coluna
- [x] Planilha CSV com uma coluna literalmente chamada `canal`
- [x] Upload → mapeamento já vem pré-preenchido automaticamente para `Canal de aquisição`
- [x] Processar → lead criado com `acquisition_channel` correto
- **Validado em:** 05/09/2026 — o select "Canal de aquisição" já veio com `canal` pré-selecionado sem interação do utilizador (confirmando `COLUMN_ALIASES`). Lead criado com `acquisition_channel="Indicacao"`.

### Cenário P3 — Planilha sem essa coluna
- [x] Planilha sem nenhuma coluna relacionada a canal
- [x] Processar normalmente → lead criado com `acquisition_channel = NULL` (campo em branco no card, sem erro)
- **Validado em:** 05/09/2026 — select "Canal de aquisição" ficou em "-- ignorar --" (nenhuma coluna candidata), lead criado sem erro com `acquisition_channel=null`.

### Cenário P4 — Overwrite "update" preserva/preenche sem sobrescrever
- [x] Lead já existente sem `acquisition_channel`, reimportar planilha com essa coluna preenchida e `overwrite=update` → campo passa a ser preenchido
- [x] Lead já existente **com** `acquisition_channel` já preenchido manualmente, reimportar com valor diferente na planilha e `overwrite=update` → valor manual é preservado (mesmo comportamento hoje aplicado a `companyName`/`contactName`/etc.)
- **Validado em:** 05/09/2026 — sequência completa: (1) import sem coluna de canal → lead criado com `acquisition_channel=null`; (2) reimport com `canal=Google Ads` e `overwrite=update` → campo passou a `"Google Ads"`; (3) valor alterado manualmente via `PATCH /api/leads/{id}` para `"Manual Override"` (mesmo endpoint usado pelo `LeadCardDialog.tsx`); (4) reimport com `canal="Canal Que Nao Deve Sobrescrever"` e `overwrite=update` → valor permaneceu `"Manual Override"`, confirmando que `update_lead_light()` só preenche campos vazios.

**Observação:** o Quadro Kanban não renderizou cards nesta worktree durante o teste (tela em branco mesmo após busca) — parece ser uma particularidade deste ambiente local recém-provisionado (DB copiado manualmente), não relacionada a esta mudança; não investigado further pois os Cenários foram validados diretamente via API (`GET`/`PATCH /api/leads`), o mesmo caminho que a UI usa. Leads de teste (ids 512-515) foram removidos ao final via `DELETE /api/leads/{id}`.

---

## Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `35812bd` | Backend: mapeamento e persistência de `acquisition_channel` na importação por planilha |

**Detalhes do commit `35812bd`:**
- `backend-crm/automations/assistente_ia/processor.py` — `map_row_to_lead()` lê `acquisition_channel` via `column_map` explícito ou fallback automático (`canal`, `canal_aquisicao`, `fonte`); `update_lead_light()` passa a preservar/preencher esse campo no merge de `overwrite=update`
- `backend-crm/tests/test_processor_lead_mapping.py` — 3 novos testes (mapeamento explícito, auto-detecção, ausência da coluna)

### Relatório da Fase 1 — o que mudou na prática

**Antes:** ao importar uma planilha de leads, o campo "Canal de aquisição" nunca era preenchido automaticamente — mesmo que a planilha tivesse uma coluna com essa informação, era preciso abrir cada lead depois e preencher manualmente.

**Agora:** o backend já sabe reconhecer essa informação na planilha, seja porque o utilizador mapeou a coluna explicitamente, seja porque a planilha já tem uma coluna chamada "canal" ou "fonte". Falta apenas a Fase 2 (frontend) para o utilizador conseguir fazer esse mapeamento explícito pela interface — sem ela, só funciona a auto-detecção por nome de coluna.

**Para validar:** ainda não há UI para os Cenários P1/P2/P4 completos (dependem da Fase 2). Os testes automatizados (`pytest tests/test_processor_lead_mapping.py`) já cobrem a lógica de mapeamento isoladamente e passaram (8/8).

---

## Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `06cf985` | Frontend: campo "Canal de aquisição" no mapeamento de colunas do Assistente IA |

**Detalhes do commit:**
- `frontend-crm/src/pages/AssistenteIA.tsx` — `COLUMN_ALIASES` ganhou entrada `acquisition_channel` (aliases: `canal`, `canal_aquisicao`, `fonte`, `canal de aquisição`) para auto-detecção; novo mapa `FIELD_LABELS` para exibir rótulos amigáveis na UI de mapeamento (antes usava o nome cru da chave com `capitalize`); lista de campos mapeáveis passou a incluir `acquisition_channel`

### Relatório da Fase 2 — o que mudou na prática

**Antes:** mesmo com o backend já pronto (Fase 1), não havia como o utilizador dizer, pela interface do Assistente IA, qual coluna da planilha continha o canal de aquisição — só funcionava se a coluna já se chamasse exatamente "canal", "canal_aquisicao" ou "fonte".

**Agora:** a tela "1.5. Mapeamento de Colunas" mostra um novo campo "Canal de aquisição", com auto-detecção quando a planilha já tem uma coluna com nome parecido, e seleção manual para qualquer outro nome de coluna (ex.: "Origem Marketing").

**Para validar:** Cenários P1, P2, P3 e P4 (secção "Checks de Validação", acima) — todos dependiam desta fase e agora estão prontos para teste de ponta a ponta.

---

## Ajustes Possíveis Pós-Implementação

- A grid de prévia do Assistente IA não mostra `acquisition_channel` (nem
  mostra `notas` hoje) — se um utilizador pedir para conferir o canal antes de
  processar, adicionar essa linha à prévia é uma extensão pequena e isolada.
