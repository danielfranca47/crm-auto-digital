---
description: Aplica as confirmações de /statusplans-verificar — limpa itens já feitos/obsoletos de docs/plans/, gera o sprint plan, e já cria os arquivos docs/implementations/<slug>.md correspondentes com status "Aguardando Plan Mode" (sem gastar tokens rodando o diagnóstico agora). Passo 3 do fluxo
---

**Pré-requisito:** uma classificação já confirmada pelo usuário nesta conversa (via
`/statusplans-verificar`). Se não houver confirmação explícita, **não prossiga** — peça
para rodar `/statusplans-verificar` primeiro.

Este comando cobre a transição entre o Passo 5/6 de
[`_guia-analise-planos.md`](../../docs/plans/_guia-analise-planos.md) ("Priorização" +
"Proposta e geração do arquivo") e o **início do Passo 1** de
[`_guia-documentar-implementacao.md`](../../docs/implementations/_guia-documentar-implementacao.md)
("Criar a branch e nomear o arquivo") — mas **sem** executar o Passo 0 (Diagnóstico em
Plan Mode) ainda. Plan Mode é uma investigação de código que custa tokens; fazer isso
automaticamente para até 6 itens de uma vez é caro e desnecessário se o usuário só quer
priorizar agora e decidir depois por qual começar. Em vez disso, este comando **cria os
arquivos de implementação já com o contexto conhecido, marcados como pendentes** — o
Plan Mode roda depois, só para o item que o usuário escolher, quando escolher.

Separe os itens confirmados em dois grupos:

## Grupo A — ✅ já implementado / 🗑️ obsoleto (confirmados)

Para cada arquivo de `docs/plans/` afetado:
- Remova apenas a seção/item confirmado. **Sem histórico** — o objetivo é o arquivo
  refletir só o que ainda falta, não um changelog (não escrever "item removido por
  estar obsoleto"; simplesmente remover)
- Se o arquivo ficar sem nenhum item pendente, apague o arquivo inteiro (`git rm`)
- **Nunca** apague arquivos prefixados com `_` em `docs/plans/`
- **Nunca** apague `plano-sprint-*.md` aqui — isso só acontece no Passo 6b da graduação
  de implementations (ver
  [`_processo-graduacao-implementacao.md`](../../docs/implementations/_processo-graduacao-implementacao.md)),
  quando todos os itens daquele sprint já estiverem `✅` no tracking

## Grupo B — 🟡/❌ confirmados para avançar

**Máximo 6 itens.** Se houver mais confirmados que isso, avance só os 6 de maior
prioridade recomendada (da resposta de `/statusplans`) e avise quais ficaram de fora
para uma próxima rodada.

### 1. Gerar o sprint plan

Gere `docs/plans/plano-sprint-YYYY-MM-DD.md` (data de hoje), no formato de
[`_template-plano-semanal.md`](../../docs/plans/_template-plano-semanal.md): diagnóstico,
mapa de dependências/sinergias, e tabela de "Tracking de absorção" — já preenchendo a
coluna "Arquivo de implementação" (ver passo 2 abaixo, os nomes já são conhecidos neste
momento) com status inicial `⏳ Aguardando Plan Mode`.

Se algum item tiver uma pergunta de produto/negócio/experiência sem resposta óbvia no
código ou nos plans, **pare e pergunte ao usuário** antes de seguir com aquele item —
não adivinhe decisão de negócio (ver critérios de "Perguntas ao admin" no Passo 4 do
guia de análise).

### 2. Criar o arquivo de implementação pendente, por item

Para cada item do Grupo B, **direto na pasta principal** (sem criar branch/worktree
ainda — isso só acontece depois do Passo 0 ser aprovado, ver abaixo), criar
`docs/implementations/<slug>.md` com esta estrutura reduzida:

```markdown
# <Título do item>

**Status:** Aguardando Plan Mode
**Autonomia:** noturna
**Sprint:** `docs/plans/plano-sprint-YYYY-MM-DD.md` (item P<N>)
**Origem:** `docs/plans/<arquivo-original>.md` — <seção/item de origem>

---

## Motivação

<Mesmo conteúdo que iria num prompt: comportamento actual, comportamento desejado,
por que agora / o que está em risco ou a ganhar.>

---

## Área do sistema

<Serviço(s) envolvidos (backend-core / backend-crm / frontend-crm / etc.) — sem
prescrever arquivo, linha ou abordagem técnica, isso é trabalho do Plan Mode.>

---

## Próximo passo

Este arquivo ainda não passou pelo **Passo 0 (Diagnóstico em Plan Mode)** de
`_guia-documentar-implementacao.md`. Para iniciar: entrar em Plan Mode usando o
contexto acima como ponto de partida, responder as 3 perguntas do Passo 0, e só depois
de aprovado seguir para a criação de branch + worktree (Passo 1).
```

**Nome do arquivo:** seguir o Passo 1 de `_guia-documentar-implementacao.md` — slug
descritivo direto (sem código de etapa, já que ainda não houve Plan Mode para confirmar
o escopo exato).

**Linha `Autonomia`:** `noturna` deixa a fila automática pegar no item sozinha; trocar
para `manual` se o usuário disser que quer acompanhar esse item de perto (ver
`docs/ops/fila-automatica.md`).

Isso não conta como "avançar para código sem plano aprovado" — nenhuma branch, worktree
ou linha de código é criada aqui, só um documento de fila com o contexto já levantado.

## Fechamento

1. Faça um **commit único** cobrindo tudo (limpeza de plans + sprint plan + os novos
   arquivos `docs/implementations/*.md` pendentes), seguindo a convenção de commit do
   `CLAUDE.md` (`git add` nos arquivos específicos, mensagem Conventional Commits,
   corpo listando o que mudou em cada arquivo e a motivação). Tudo isso é documentação —
   não abre worktree/branch própria, é feito direto na branch atual.
2. Mostre ao usuário um resumo curto: quais arquivos de plans foram limpos/removidos, e
   a lista dos itens criados em `docs/implementations/` (P1..P6, cada um com o nome do
   arquivo e uma linha de título).
3. Feche perguntando por qual item ele quer começar agora (ou se prefere só deixar
   todos na fila). Deixe claro que escolher um item é o que dispara o Plan Mode
   (Passo 0) — só nesse momento o código é investigado, e só para o item escolhido.

**Nota técnica para quando um item for escolhido depois:** `EnterWorktree` cria a
branch a partir de `origin/<branch base>`. Se o commit deste comando ainda não foi
enviado ao remoto (`git push`), a worktree nova não terá o arquivo pendente
automaticamente — nesse caso, ao entrar na worktree, recrie o arquivo lá com o mesmo
conteúdo (já está disponível no contexto ou pode ser lido da pasta principal antes de
trocar) antes de completá-lo com o diagnóstico do Plan Mode.

Não entre em Plan Mode nesta resposta para nenhum item — isso só acontece quando o
usuário escolher explicitamente por qual começar.
