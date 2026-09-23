# Cache de prompt do provedor para reduzir custo de tokens

**Status:** Levantado
**Origem:** `levantamentos/2026-09-23-busca-vetorial-gemini.txt` — preocupação do utilizador em "economizar token"
**Meta ligada:** M4 — Custo por cliente sustentável
**Área do sistema:** backend-executors (decision_engine — ordem de montagem dos prompts, chamada ao LLM)

---

## Pergunta a responder

Os prompts do agente estão montados de forma a aproveitar o desconto de cache do
provedor de LLM (a parte fixa primeiro, a parte que muda no fim)? Quanto isso pouparia
por conversa?

## O que já se sabe

- O Gemini sugeriu busca vetorial para poupar tokens; com bases de ~2 mil tokens
  (ver `rag-busca-vetorial-conhecimento.md`), o ganho maior tende a estar no **cache
  de prompt**, que os provedores oferecem para prefixos repetidos.
- O sistema usa OpenAI (ex.: `backend-crm/routes/qualification.py`, `_call_openai`);
  o provedor e o modelo usados pela Mãe/Filhas não foram verificados na triagem.
- Não verificado: a ordem dos blocos nos prompts (fixos vs. variáveis por turno), a
  existência de métricas de tokens em cache, e o custo atual por conversa. Há
  trabalho relacionado em `docs/plans/motor-llm-otimizacoes.md` — ler antes de
  aprofundar para não duplicar.
