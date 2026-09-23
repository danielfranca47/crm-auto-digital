# Centro de Discovery (`docs/discovery/`)

**Branch:** `feat/discovery-centro-inteligencia` (na sessão: `worktree-feat+discovery-centro-inteligencia`)
**Status:** Todos os cenários validados (23/09/2026) — pendente: graduação (inclui instalar os comandos na pasta principal e apagar o `.txt` original da raiz de `docs/`)

---

## Motivação

Uma análise de uma conversa com o Gemini sobre busca vetorial levantou vários
gaps possíveis no sistema, com graus de certeza muito diferentes: um bug
confirmado, várias hipóteses e uma ideia de longo prazo. O repositório só tinha
a frente de **entrega** (`docs/plans/` → `docs/implementations/`); faltava uma
frente de **descoberta**, onde um levantamento é dividido em gaps e cada gap é
investigado a fundo (código + mercado + soluções + ligação às metas do produto)
antes de decidir se vai para `implementations/`, `plans/`, stand-by ou se é
descartado.

No mercado isto chama-se **Product Discovery / Dual-Track Agile**. Cada
investigação é um **spike** (tempo limitado, termina num documento com
recomendação), a ligação às metas segue o **Opportunity Solution Tree** e o
veredito é inspirado no **Technology Radar** da Thoughtworks.

Decisões do utilizador: pasta `docs/discovery/`; as categorias de conhecimento
que a IA nunca lê vão direto para `implementations/` (bug confirmado, não precisa
de discovery).

---

## Problemas Identificados (estado anterior)

1. **Sem lugar para incerteza:** `docs/plans/` guarda ideias já formuladas e
   `docs/implementations/` exige Plan Mode com escopo claro. Um levantamento com
   vários gaps de certeza diferente não tinha onde ser triado.
2. **Prioridade sem âncora:** não havia metas do produto escritas, então
   "prioridade alta" nos plans era opinião, não correspondência a uma meta.
3. **Sem pesquisa de mercado no processo:** nenhum guia pede comparar com
   plataformas de referência antes de escolher a solução.
4. **Levantamento solto na raiz de `docs/`:** a conversa com o Gemini ficou como
   arquivo não rastreado, "analisar depois".

---

## Abordagem

```
Levantamento (conversa, relatório, feedback de cliente…)
  → /discovery-levantar — triagem de cada gap
      ├─ bug confirmado + solução clara → implementations/ (Aguardando Plan Mode)
      └─ incerteza → docs/discovery/<slug>.md (Levantado)
  → /discovery-aprofundar <slug> — código + mercado + soluções + RICE + meta
      → Pronta para decisão
  → /discovery-status — painel para o utilizador decidir em lote
  → /discovery-decidir — implementations | plans | stand-by (com gatilho) | descartar
```

O utilizador só intervém em dois momentos: validar as metas (raramente) e dar
vereditos em lote.

Fora do escopo: agente periódico automático (ver "Ajustes Possíveis").

---

## Plano de Implementação

### Fase 1 — Estrutura e processo

**Objetivo:** criar a pasta, o processo, os comandos e ligá-los ao resto do repo.

| Arquivo | O que muda |
|---|---|
| `docs/discovery/README.md` | Visão geral da pasta, diferença entre discovery, plans e implementations, prompts úteis |
| `docs/discovery/_guia-discovery.md` | Processo completo para o Claude (triagem, aprofundar, RICE, veredito, regras) |
| `docs/discovery/_template-investigacao.md` | Template de cada investigação |
| `docs/discovery/_metas-produto.md` | Rascunho das metas do produto (a validar pelo utilizador) |
| `docs/discovery/_radar.md` | Painel vazio |
| `docs/discovery/levantamentos/README.md` | O que guardar em `levantamentos/` |
| `docs/ops/local-dev.md` | 4 comandos novos na secção "Comandos slash locais" |
| `CLAUDE.md` | Subsecção "Discovery" + linha na tabela de documentação |
| `docs/plans/_guia-analise-planos.md` | Indicação de que itens podem vir da discovery |
| `docs/implementations/README.md` | Idem |
| `.claude/commands/discovery-*.md` (gitignored) | 4 comandos — ver nota abaixo |

**Nota — onde estão os comandos agora:** a sessão está isolada na worktree e não
pode escrever na pasta principal, por isso os 4 comandos foram criados em
`.claude/commands/` **da worktree**. Na graduação, depois do `ExitWorktree`,
instalá-los na pasta principal recriando-os a partir dos blocos de
`docs/ops/local-dev.md` (o mesmo prompt de recuperação que a secção descreve).
Até lá, só funcionam numa sessão aberta dentro da worktree.

#### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `205594c` | Pasta `docs/discovery/` (README, guia, template, metas em rascunho, radar, levantamentos) + comandos em `local-dev.md` + CLAUDE.md e guias de plans/implementations |

### Fase 2 — Primeiro levantamento (ensaio real)

**Objetivo:** processar a conversa com o Gemini com o fluxo novo.

| Arquivo | O que muda |
|---|---|
| `docs/discovery/levantamentos/2026-09-23-busca-vetorial-gemini.txt` | Conversa com o Gemini, copiada sem alterações da raiz de `docs/` (o original, não rastreado, é apagado da pasta principal na graduação) |
| `docs/discovery/rag-busca-vetorial-conhecimento.md` | Investigação `Levantado` (M4) |
| `docs/discovery/conhecimento-fora-fase-apresentacao.md` | Investigação `Levantado` (M2) |
| `docs/discovery/prompt-caching-custo-tokens.md` | Investigação `Levantado` (M4) |
| `docs/discovery/alucinacao-escape-hatch-cobertura.md` | Investigação `Levantado` (M2) |
| `docs/discovery/_radar.md` | 4 investigações + "banco vetorial dedicado" em Descartados |
| `docs/implementations/fix-categorias-conhecimento-orfas.md` | Bug confirmado → `Aguardando Plan Mode` (decisão do utilizador) |

#### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `a3be117` | Levantamento guardado, 4 investigações, radar preenchido, stub do fix de categorias órfãs |

### Relatório das Fases 1 e 2 — o que mudou na prática

**Antes:** uma análise como a da conversa com o Gemini ficava solta em `docs/`
("analisar depois"), sem forma de separar o que é bug, o que é dúvida e o que
não se aplica, e sem metas escritas para dizer o que é prioritário.
**Agora:** existe `docs/discovery/` com processo, metas do produto (em rascunho)
e um painel. A conversa com o Gemini já foi processada: 1 bug foi para
implementations, 4 dúvidas viraram investigações e 1 sugestão (banco vetorial
dedicado) foi descartada com o motivo registado.
**Para validar:** Cenários P1–P4, abaixo. P1–P3 precisam de uma sessão aberta
dentro da worktree (ou dos comandos já instalados na pasta principal).

---

## Checks de Validação

### Cenário P1 — Painel numa conversa nova
- [x] Numa conversa nova, rodar `/discovery-status`
- [x] Confirmar: lista as investigações da Fase 2 com meta, estado e o que falta decidir
- **Validado em:** 23/09/2026 — executado nesta conversa, seguindo o texto do comando (não numa conversa nova). Encontrou as 4 investigações, as metas em RASCUNHO (pede validação) e nenhuma inconsistência entre o radar e os arquivos; recomendou aprofundar primeiro uma investigação M2.

### Cenário P2 — Aprofundar uma investigação
- [x] Rodar `/discovery-aprofundar rag-busca-vetorial-conhecimento`
- [x] Confirmar: documento preenchido com evidência no código (arquivo:linha), mercado com fontes, 2–3 opções, RICE e veredito proposto
- **Validado em:** 23/09/2026 — commit `c2c6234`. 4 pesquisas (limite 6), 6 fontes, RICE 0.27, veredito proposto stand-by com gatilho. A medição em produção foi bloqueada pelo modo automático (acesso a produção) e ficou em "Em aberto" + pergunta ao utilizador — comportamento correto do processo.

### Cenário P3 — Decidir
- [x] Rodar `/discovery-decidir` com um veredito "stand-by" e outro "implementations"
- [x] Confirmar: stand-by fica no radar com gatilho; implementations gera o stub `Aguardando Plan Mode`
- **Validado em:** 23/09/2026 — veredito "stand-by" do utilizador aplicado à investigação RAG (commit `5a778dd`): arquivo mantido com status Stand-by e linha no radar com gatilho e última verificação. O caminho "implementations" não teve investigação pronta para testar pelo `/discovery-decidir`; o mesmo formato de stub foi exercitado pela triagem do `/discovery-levantar` (`fix-categorias-conhecimento-orfas.md`, commit `a3be117`) — aceite como cobertura suficiente.

### Cenário P4 — Recuperação dos comandos
- [x] Comparar `.claude/commands/discovery-*.md` com os blocos em `docs/ops/local-dev.md`
- [x] Confirmar: conteúdo idêntico
- **Validado em:** 23/09/2026 — comparação por script: os 4 comandos IDENTICO.

---

## Ajustes Possíveis Pós-Implementação

- **Rotina semanal automática** (`/schedule`): aprofundar 1–2 investigações
  pendentes e verificar gatilhos de stand-by sem intervenção. Só depois de
  validar a qualidade das investigações feitas à mão; exige adaptar a regra de
  git (sem push automático) para um agente que corre sozinho.
- **Base de dados de inteligência** (ideia do utilizador, 23/09/2026): guardar
  os estudos feitos num banco para recapitular e acompanhar a evolução
  (ex.: histórico de medições dos gatilhos, scores ao longo do tempo, vereditos
  tomados). Hoje os arquivos + o git já guardam isto, mas sem consulta fácil.
  Candidato a primeira investigação "de processo" da própria discovery.
- **Análise de conversas reais** (autorizada pelo utilizador): usar o conteúdo
  de produção (conversas e conhecimento) nas investigações para medir a
  efetividade do agente com casos reais — ex.: na investigação
  `conhecimento-fora-fase-apresentacao`, contar quantas vezes o agente disse
  "vou confirmar com a equipa".
