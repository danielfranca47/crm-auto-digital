# Busca vetorial (RAG) para a base de conhecimento

**Status:** Pronta para decisão
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
- Relacionado: a migração para banco vetorial dedicado foi descartada (ver radar).

---

## Evidência no código

- **Como o conhecimento chega ao agente hoje** — um "roteamento por categoria":
  1. `_load_knowledge_items` (`backend-crm/services/ai_orchestrator/orchestrator.py:503-528`)
     carrega todas as categorias ativas do cliente (1 item por categoria, exceto a
     tabela de preços — problema já tratado em
     `docs/implementations/fix-categorias-conhecimento-orfas.md`).
  2. A Mãe decide a fase pelo significado da mensagem (`decision_engine.py:2419-2501`).
  3. Cada filha recebe só as categorias da sua fase (apresentação:
     `decision_engine.py:3288-3428`; follow-up: `3843-3881`), e as categorias
     "narrativas" (prova social, pitch) são enviadas no máximo 1 vez por lead
     (`_evaluate_narrative_knowledge_dedup`, `decision_engine.py:1020`).
- **Isto já faz parte do que o RAG promete** (enviar só o relevante), só que com um
  critério mais grosseiro: a categoria inteira em vez do trecho exato.
- **Tamanho (banco local, 23/09/2026):** 3 utilizadores com conhecimento ativo; o
  maior tem 8 itens / ~7 mil caracteres (~2 mil tokens); a maior categoria isolada
  tem ~5 mil caracteres. **Produção não medida** (ver "Em aberto").
- **Modelo:** `gpt-4o-mini` por padrão (`backend-executors/app/core/config.py:17`),
  janela de ~128 mil tokens; OpenRouter opcional por perfil
  (`app/services/llm_service.py:57`). A maior base local ocupa ~1,5% da janela.

## Como o mercado faz

| Referência | Como resolve | Aplica-se a nós? |
|---|---|---|
| Anthropic — *Contextual Retrieval* | Para bases com menos de ~200 mil tokens (~500 páginas), recomenda **pôr a base inteira no prompt** e usar cache de prompt, sem RAG. Para bases maiores, RAG com embeddings + BM25 + reranking (menos 49–67% de falhas de busca) | **Sim.** Estamos ~100× abaixo desse limite. O próximo passo natural é o cache de prompt (investigação `prompt-caching-custo-tokens`), não o RAG |
| Intercom Fin (agente de suporte de referência) | RAG completo: modelo de busca próprio, reranker e resumo, sobre centros de ajuda com centenas de artigos, PDFs e conversas antigas | **Não, por agora.** O contexto deles são bases enormes e genéricas; as nossas são pequenas e curadas por categoria. Mostra o destino se um dia importarmos sites ou PDFs grandes |
| Estudos "lost in the middle" / long context vs RAG | Com contextos longos o modelo perde informação que fica no meio do prompt (queda >30%); o RAG funciona como "compressor" de contexto | **Parcialmente.** Isto dói com dezenas de milhares de tokens; com 2 mil, não. Serve para definir o gatilho |
| `sqlite-vec` (extensão de SQLite) | Busca vetorial dentro do próprio arquivo `.db`, em SQL, sem servidor à parte | **Sim, se o gatilho disparar:** evita migrar para Pinecone/Qdrant/pgvector |

## Opções de solução

### Opção A — Não fazer nada agora; stand-by com gatilho de tamanho
- **Prós:** custo zero; o roteamento por categoria já filtra o que cada fase recebe;
  alinhado com a recomendação da Anthropic para bases pequenas.
- **Contras:** se um cliente cadastrar uma base grande (catálogo com centenas de
  itens, PDF longo), só vamos perceber quando as respostas piorarem, a menos que o
  gatilho seja verificado.
- **Esforço:** 0 (o gatilho é verificado pelo `/discovery-status`).

### Opção B — RAG por trechos dentro das categorias grandes, com `sqlite-vec`
- **O que é:** partir as categorias grandes (FAQ, catálogo) em trechos, gerar
  embeddings ao gravar, e na hora da resposta enviar só os 3–5 trechos mais próximos
  da pergunta do lead.
- **Prós:** preparado para bases grandes; menos tokens por mensagem nesses clientes.
- **Contras:** nova dependência (modelo de embeddings + extensão SQLite nos 2
  backends); nova forma de falha (a busca não encontrar o trecho certo = o agente
  "não sabe" algo que está cadastrado); precisa manter a paridade playground ↔
  WhatsApp; ganho nulo para as bases atuais.
- **Esforço:** ~3 fases (ingestão + embeddings, busca na montagem do prompt, testes
  de qualidade/paridade).

## Recomendação

**Opção A.** Hoje as bases são ~100 vezes menores que o ponto a partir do qual até
a Anthropic recomenda RAG, e o sistema já envia a cada fase só as categorias dela.
Construir RAG agora gastaria 3 fases para resolver um problema que ainda não temos e
criaria um novo risco de o agente não encontrar informação que foi cadastrada. Para
poupar tokens, o caminho mais barato é o cache de prompt (outra investigação).

## Pontuação RICE

| R | I | C | E | Score |
|---|---|---|---|---|
| 1 | 1 | 0.8 | 3 | **0.27** |

- **R = 1:** nenhum cliente conhecido tem base grande (banco local).
- **I = 1:** a poupança de tokens com bases de ~2 mil tokens é mínima para M4, e o
  ganho de qualidade (M2) só aparece com bases grandes.
- **C = 0.8:** medido no banco local e confirmado no código; produção não medida.
- **E = 3:** ingestão + embeddings, busca na montagem do prompt, testes.

## Veredito proposto

**Stand-by** — não compensa com o tamanho atual das bases; volta à mesa se alguma base crescer.
**Gatilho de revisão:** algum cliente com mais de **40 mil caracteres (~10 mil
tokens) de conhecimento ativo**, OU relatos de respostas erradas em que a informação
certa estava cadastrada e foi enviada ao agente (sinal de "lost in the middle").

## Perguntas ao utilizador

1. Algum cliente atual ou em negociação tem um **catálogo grande** (centenas de
   produtos ou serviços) ou quer carregar documentos longos (PDFs, site inteiro)?
   Se sim, o gatilho pode já estar perto.
2. Autorizas uma **consulta só de leitura** ao banco de produção, com números
   agregados (tamanho da base por cliente, sem ler conteúdo)? O modo automático
   bloqueou-a, corretamente, por ser acesso a produção.

## Em aberto

- Tamanho real das bases em **produção** (depende da pergunta 2). Se algum cliente
  já passar do gatilho, o veredito muda.

## Fontes

- [Contextual Retrieval in AI Systems — Anthropic](https://www.anthropic.com/engineering/contextual-retrieval)
- [The Fin AI Engine — Intercom Help](https://www.intercom.com/help/en/articles/9929230-the-fin-ai-engine)
- [Fin AI Agent explained — Intercom Help](https://www.intercom.com/help/en/articles/7120684-fin-ai-agent-explained)
- [Solving the "Lost in the Middle" problem — Maxim](https://www.getmaxim.ai/articles/solving-the-lost-in-the-middle-problem-advanced-rag-techniques-for-long-context-llms/)
- [RAG vs long context: what the 2026 data shows — Wire](https://usewire.io/blog/long-context-vs-rag-what-the-data-shows/)
- [sqlite-vec — Alex Garcia](https://alexgarcia.xyz/sqlite-vec/)
