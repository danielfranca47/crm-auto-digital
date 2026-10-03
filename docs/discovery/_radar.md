# Radar de Discovery

> Espelho do estado atual de `docs/discovery/` — sem histórico (está no git).
> Atualizado por todo comando `/discovery-*` que muda o estado de uma
> investigação. Processo em `_guia-discovery.md`.

---

## Prontas para decisão

| Investigação | Meta | Score RICE | Veredito proposto | Perguntas pendentes |
|---|---|---|---|---|
| [jornada-pos-agendamento](jornada-pos-agendamento.md) | M1 (M2) | 1.44 | Implementations — "Jornada do Agendamento" por momentos, começando por confirmação + lembretes com texto do utilizador (fases 1–2 de 5) | Terapeuta fixo ou variável; dúvidas pós-agendamento sempre ou só perto do horário; como o massagista avisa a chegada; pós-sessão sem marcação; regra padrão do lembrete antecipado |
| [tags-de-contato](tags-de-contato.md) | M1 (M2) | 1.07 | Implementations — tags visíveis que complementam o "disparar uma vez" (condição "tem/não tem" + ação "adicionar"); logo após as fases 1–2 da jornada | Lista livre ou fechada; a IA deve ver as tags; tag vs. coluna "Lista de Clientes" |
| [agente-ligacoes-prospeccao-voz](agente-ligacoes-prospeccao-voz.md) | M1 (M5 se virar produto) | 0.40 | Implementations — protótipo próprio (Twilio + OpenAI Realtime) + integração CRM; número celular BR em pessoa física | Modelo de comissão do representante (simulador publicado) |

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
