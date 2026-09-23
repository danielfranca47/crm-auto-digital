# Busca vetorial (RAG) para a base de conhecimento

**Status:** Levantado
**Origem:** `levantamentos/2026-09-23-busca-vetorial-gemini.txt` — recomendação do Gemini de trocar o "contexto estático" por busca vetorial
**Meta ligada:** M4 — Custo por cliente sustentável (secundária: M2)
**Área do sistema:** backend-crm (orchestrator, knowledge), backend-executors (decision_engine)

---

## Pergunta a responder

A partir de que tamanho de base de conhecimento vale a pena buscar só os trechos
relevantes (busca vetorial) em vez de enviar as categorias inteiras ao agente — e
estamos perto desse ponto?

## O que já se sabe

- **Não há busca vetorial** no sistema: nenhum embedding ou cálculo de semelhança em
  backend-crm/backend-executors (verificado em 23/09/2026).
- **Também não é "tudo no prompt":** o conhecimento é guardado por categoria
  (`backend-crm/services/ai_orchestrator/orchestrator.py:503`) e cada fase recebe só
  as categorias dela (`backend-executors/app/services/decision_engine.py:3144-3428`).
  A escolha da fase é feita pela Mãe (LLM), por significado e não por palavra-chave
  (`decision_engine.py:2499`).
- **Base pequena hoje (só banco local):** o maior utilizador tem ~7 mil caracteres
  ativos (~2 mil tokens); a maior categoria isolada (`objections_faq`) tem ~5 mil.
  **Produção ainda não medida.**
- Hipótese: com bases deste tamanho, RAG acrescenta custo e pontos de falha sem ganho;
  candidato natural a stand-by com gatilho de tamanho.
- Relacionado: a migração para banco vetorial dedicado foi descartada (ver radar).
