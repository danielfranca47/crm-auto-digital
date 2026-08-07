# Ingestão de conhecimento — extrair service_pricing_table direto em structured_v1

**Branch:** `feat/ajuste-configuracao-ai-profile`
**Status:** Todos os cenários validados (07/08/2026)

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`docs/implementations/camada4-ingestao-conhecimento.md`.

A categoria `service_pricing_table` suporta dois formatos de conteúdo (ver
`docs/architecture/knowledge-base.md`): JSON estruturado `structured_v1`
(`{"format": "structured_v1", "rows": [...]}`, editável na UI como tabela) e texto livre legado
(editável só como texto). Hoje, quando a ingestão por IA classifica uma fonte como
`service_pricing_table`, o classificador (`backend-crm/services/knowledge_ingest/classifier.py`)
grava sempre texto livre — o item funciona normalmente para o agente (o orchestrator já tem
fallback para texto não-JSON), mas o utilizador não consegue editá-lo depois na UI de "Tabela
estruturada" (`ServicePricingTables.tsx`) sem primeiro convertê-lo manualmente.

A ideia é o classificador, quando a categoria for `service_pricing_table`, pedir ao LLM que
devolva já no formato `structured_v1` (linhas com nome/duração/preço/descrição), reaproveitando
`parseServicePricingContent()`/`serializeServicePricingRows()` como referência de schema.

---

## Problemas Identificados (estado anterior)

1. **Classificador não emite JSON estruturado:** `classifier.py:classify_sources()` pede um mapa
   `categoria → texto` genérico — não há tratamento especial para `service_pricing_table` gerar
   `rows` estruturadas.
2. **Item gravado como texto livre:** o item criado por `_insert_ai_item` (`ingest_worker.py`) fica
   preso ao modo "Texto livre" na UI até o utilizador editar manualmente e converter.

---

## Abordagem

```
_build_prompt(): se 'service_pricing_table' está na lista de categorias, acrescenta instrução
  pedindo, só para essa key, "rows": [{nome, duracaoMinutos, preco, descricao?}] em vez de "content"
  ↓
LLM responde {"categories": {"service_pricing_table": {"rows": [...], "source_refs": [...]}, ...}}
  ↓
classify_sources(): para a key 'service_pricing_table', serializa rows → JSON structured_v1
  (mesmas regras de ServicePricingTables.tsx:serializeServicePricingRows)
  ↓ (se rows ausente/inválido — LLM ignorou a instrução)
  fallback: usa entry.get("content") como texto livre (comportamento actual, sem regressão)
  ↓
resto do pipeline (ingest_worker.py) grava a string tal como está — sem mudança
```

Mudança isolada em `classifier.py` — o resto do pipeline trata `content` como string opaca.

---

## Plano de Implementação

### Fase 1 — classifier.py + docs

**Objetivo:** ingestão de `service_pricing_table` grava direto em `structured_v1`.

| Arquivo | O que muda |
|---|---|
| `backend-crm/services/knowledge_ingest/classifier.py` | `_build_prompt()` ganha instrução condicional para `service_pricing_table`; nova `_serialize_pricing_rows()`; `classify_sources()` usa rows quando disponível, com fallback pro texto livre |
| `docs/architecture/knowledge-base.md` | Seção "Classificação" atualizada |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `2afd04c` | classifier.py: regra especial + _serialize_pricing_rows() + fallback; docs |

### Relatório da Fase 1 — o que mudou na prática

**Antes:** quando a IA lia seus materiais e encontrava uma tabela de preços, o item criado ficava
travado no modo "Texto livre" — para editar como tabela (linhas de nome/duração/preço), era preciso
abrir o item, mudar para o modo "Tabela estruturada" e recriar as linhas manualmente.

**Agora:** quando a IA identifica uma tabela de preços nos materiais enviados, ela já organiza os
serviços em linhas (nome, duração, preço, descrição) — o item nasce direto no modo "Tabela
estruturada", pronto para editar como tabela sem esse passo extra de conversão.

**Para validar:** Cenários T1 e T2, abaixo — já executados nesta sessão via script (chamada real
ao classificador + testes determinísticos), sem necessidade de repetir manualmente.

---

## Checks de Validação

### Cenário T1 — classify_sources() emite structured_v1 (chamada real à API)
- [x] Script ad-hoc com fonte fabricada (2 serviços fictícios) + categories=[service_pricing_table]
- [x] Confirmar que o `content` retornado é JSON válido `{"format": "structured_v1", "rows": [...]}` com os 2 serviços
- **Validado em:** 07/08/2026 — chamada real a `classify_sources()` (OpenAI, `gpt-4o-mini`) com
  fonte fabricada ("Consulta Inicial: 45 min, R$120,00, Avaliação completa..." + "Sessão de
  Retorno: 30 min, R$80,00"). Retornou `content` = JSON `structured_v1` válido com as 2 linhas,
  campos corretos (`nome`, `duracaoMinutos`, `preco` exatos; `descricao` presente na 1ª linha,
  omitida na 2ª por não ter sido informada na fonte).

### Cenário T2 — _serialize_pricing_rows() isolada (determinístico, sem rede)
- [x] Lista vazia → `None`
- [x] Linha sem `nome` → filtrada
- [x] `descricao` vazia → chave omitida do dict
- [x] `duracaoMinutos` não-numérico → normalizado para `None`
- **Validado em:** 07/08/2026 — script Python com 7 asserções cobrindo os 4 casos acima + not-a-list
  + descrição presente + mistura de linha válida/inválida. Todas passaram.

---

## Ajustes Possíveis Pós-Implementação

- Com a edição inline (feature anterior), a tela de revisão mostraria o JSON bruto do
  `structured_v1` num textarea para esta categoria — funcional, mas não tão amigável quanto um
  editor de linhas. Fora do escopo desta iteração (o stub original só pedia a extração direta;
  não pedia UI de revisão dedicada).
- O preview truncado (`_PREVIEW_CHARS`) na tela "Resultado da importação" cortaria o JSON no meio
  em vez de mostrar algo como "2 serviços cadastrados". Cosmético, sem impacto funcional.
