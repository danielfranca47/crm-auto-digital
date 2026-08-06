# Ingestão de conhecimento — extrair service_pricing_table direto em structured_v1

**Branch:** *(a definir)*
**Status:** Aguardando Plan Mode

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

## Próximos passos

Este arquivo nasce como stub — a implementação real só começa depois do diagnóstico normal
(Plan Mode) ser feito e aprovado pelo utilizador, seguindo
`docs/implementations/_guia-documentar-implementacao.md`.
