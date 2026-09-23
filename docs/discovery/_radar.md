# Radar de Discovery

> Espelho do estado atual de `docs/discovery/` — sem histórico (está no git).
> Atualizado por todo comando `/discovery-*` que muda o estado de uma
> investigação. Processo em `_guia-discovery.md`.

---

## Prontas para decisão

| Investigação | Meta | Score RICE | Veredito proposto | Perguntas pendentes |
|---|---|---|---|---|
| — | | | | |

## Em investigação / Levantadas

| Investigação | Meta | Status | Origem |
|---|---|---|---|
| [conhecimento-fora-fase-apresentacao](conhecimento-fora-fase-apresentacao.md) | M2 | Levantado | levantamentos/2026-09-23-busca-vetorial-gemini.txt |
| [alucinacao-escape-hatch-cobertura](alucinacao-escape-hatch-cobertura.md) | M2 | Levantado | levantamentos/2026-09-23-busca-vetorial-gemini.txt |
| [prompt-caching-custo-tokens](prompt-caching-custo-tokens.md) | M4 | Levantado | levantamentos/2026-09-23-busca-vetorial-gemini.txt |
| [base-dados-inteligencia-estudos](base-dados-inteligencia-estudos.md) | — (processo) | Levantado | Sugestão do utilizador na graduação da discovery |

## Stand-by (gatilhos)

| Investigação | Gatilho de revisão | Última verificação |
|---|---|---|
| [rag-busca-vetorial-conhecimento](rag-busca-vetorial-conhecimento.md) | Cliente com >40 mil caracteres de conhecimento ativo, OU respostas erradas com a informação certa cadastrada e enviada. Verificar ao ativar o cliente com catálogo grande (em negociação) | 2026-09-23 — produção: máx. 2.580 caracteres (não disparou) |

## Descartados (não reabrir sem facto novo)

| Tema | Motivo | Data |
|---|---|---|
| Migrar para banco vetorial dedicado (Pinecone, Qdrant, pgvector) | Base de conhecimento pequena (~2 mil tokens por cliente); se um dia houver RAG, o SQLite tem extensão própria (`sqlite-vec`) sem trocar de banco. Reabrir só via `rag-busca-vetorial-conhecimento` | 2026-09-23 |
