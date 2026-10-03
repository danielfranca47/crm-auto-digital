# Radar de Discovery

> Espelho do estado atual de `docs/discovery/` — sem histórico (está no git).
> Atualizado por todo comando `/discovery-*` que muda o estado de uma
> investigação. Processo em `_guia-discovery.md`.

---

## Prontas para decisão

| Investigação | Meta | Score RICE | Veredito proposto | Perguntas pendentes |
|---|---|---|---|---|
| [jornada-pos-agendamento](jornada-pos-agendamento.md) | M1 (M2) | 1.20 | Implementations — workflows por gatilho (modelo ManyChat), Fluxo de Venda como workflow principal; começar pela fase 1 de 6 (motor + modelos prontos de confirmação e lembretes) | Nenhuma trava a fase 1. Para fases seguintes: cadastro simples de profissionais vs. agenda por profissional; dúvidas pós-agendamento sempre ou só perto do horário; como o profissional avisa a chegada; pós-sessão sem marcação |
| [tags-de-contato](tags-de-contato.md) | M1 (M2) | 1.07 | Implementations — tags visíveis que complementam o "disparar uma vez" (condição "tem/não tem" + ação "adicionar"); logo após a fase 1 dos workflows | Lista livre ou fechada; a IA deve ver as tags; tag vs. coluna "Lista de Clientes" |
| [workflows-canvas-de-nos](workflows-canvas-de-nos.md) | M1 (indireto) | 0.50 | Implementations em sequência — canvas (React Flow) como editor dos workflows por gatilho; Fluxo de Venda no canvas depois, sem mexer no motor; esquerda→direita, comando "Alinhar", lista como alternativa | Nenhuma |
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
