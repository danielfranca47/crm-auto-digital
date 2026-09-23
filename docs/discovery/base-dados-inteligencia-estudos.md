# Base de dados de inteligência para os estudos da discovery

**Status:** Levantado
**Origem:** sugestão do utilizador na graduação de `feat-discovery-centro-inteligencia.md` (23/09/2026)
**Meta ligada:** nenhuma meta de produto direta — melhoria do processo interno (Impact máximo 1 no RICE, ver `_guia-discovery.md`)
**Área do sistema:** `docs/discovery/` (processo); possivelmente um armazenamento novo

---

## Pergunta a responder

Vale a pena guardar os estudos da discovery (medições, scores, vereditos) num banco
de dados para recapitular e acompanhar a evolução — ou chega melhorar o que os
arquivos + git já guardam?

## O que já se sabe

- Hoje cada investigação é um arquivo `.md`, o `_radar.md` mostra o estado atual e
  o **histórico fica no git** (cada comando = 1 commit). Consultar a evolução (ex.:
  "como mudou o tamanho das bases ao longo dos meses?") exige ler o git log.
- A primeira medição com valor histórico já existe: o gatilho da investigação
  `rag-busca-vetorial-conhecimento` (tamanho das bases em produção, 23/09/2026).
- Opções a comparar no aprofundamento: (a) não fazer nada; (b) uma secção
  "Histórico de medições" no radar ou nas investigações em stand-by; (c) um
  arquivo estruturado (CSV/JSON) versionado; (d) um banco de verdade.
- Relacionado: `docs/plans/discovery-melhorias-futuras.md` (M1, rotina semanal),
  que seria o principal produtor de medições periódicas.
