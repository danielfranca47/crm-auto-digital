---
name: analise-fundamentada
description: Análise fundamentada antes de decidir uma solução — escolher entre abordagens para o agente de IA ou a arquitetura, responder a "qual é a melhor forma de resolver isto?", "vale a pena fazer?" ou priorizar gaps do MVP. Exige prova nossa, meta de negócio, fonte primária lida, opções e o que refutaria a escolha.
---

# Análise fundamentada

Para decisões com alternativas reais que sejam caras de reverter, mudem o que o agente diz a um cliente
ou entrem na lista do MVP. Um defeito com causa e correção evidentes segue direto para o fluxo normal.

Segue os passos por ordem. Cada afirmação leva a sua origem: **prova nossa**, **fonte externa** ou
**hipótese**.

## 1. Diagnóstico

Escreve o problema numa frase e a prova dele.
- Conversas de teste ou reais: a taxa (`falhou 3 em 3`) e a frase que falhou. Com muitas conversas por
  classificar, usa a skill `error-analysis`.
- Código: `ficheiro:linha` lido nesta sessão.

**Concluído quando:** cada afirmação tem taxa ou `ficheiro:linha`, ou está marcada como não verificada.

## 2. Meta

Liga o problema a uma meta de [`_metas-produto.md`](../../../docs/discovery/_metas-produto.md). Sem meta,
a recomendação por omissão é adiar. Para uma lista de várias iniciativas, usa
`good-strategy-bad-strategy`: um desafio principal, uma direção e o que fica por fazer.

**Concluído quando:** há uma meta nomeada e o motivo da ligação, ou a recomendação de adiar.

## 3. O que já se decidiu

Procura o tema em `docs/discovery/`, `docs/plans/`, `docs/implementations/`, `docs/architecture/` e, se
existir, `docs/speed-flow/`. Uma decisão anterior só se reabre com um dado novo, que se diz qual é.

**Concluído quando:** os documentos encontrados estão listados, ou dito que não há nenhum.

## 4. Fonte primária

Abre e lê pelo menos uma fonte do autor ou do dono da tecnologia. Começa por
[fontes.md](fontes.md); se nenhuma responder, pesquisa (a skill `research` serve para perguntas grandes e
abre um assistente à parte, com custo de utilização). As pesquisas levam só o tema, sem dados de
clientes.

Para cada fonte regista: a ligação, o que ela afirma e **o que não diz sobre o nosso caso**. Um excerto de
motor de busca ou um resumo de livro (incluindo `codebase-design` e `good-strategy-bad-strategy`) é um
guia e apresenta-se como tal.

**Concluído quando:** a passagem que sustenta a escolha veio de uma página lida, ou está escrito que a
decisão assenta só em prova nossa.

## 5. Opções

Duas ou três, sendo uma delas não fazer ou esconder. Para cada uma: o que resolve, o esforço, o risco e o
que fica de fora. Entre regra em código, instrução à IA e campo de configuração, aplica
[`prompt-engineering-principles.md`](../../../docs/architecture/prompt-engineering-principles.md).
Para o desenho de módulos, usa `codebase-design`.

**Concluído quando:** há uma só recomendação e o motivo de as outras ficarem para trás.

## 6. O que a refutaria

Antes de implementar, escreve o teste que mostraria que a escolha está errada: cenário, número de
repetições e resultado mínimo aceite, comparável com a medição de partida.

**Concluído quando:** o teste está escrito com o limiar.

## 7. Decisão do agente consultor

Quem decide é o **agente consultor**. Entrega-lhe os passos 1 a 6 e segue
[consultor.md](consultor.md): ele tenta refutar a recomendação, decide e diz o que mudaria a decisão.
Contrapõe com um facto novo quando discordares; a última posição dele é a decisão.

Mostra ao utilizador, em linguagem simples:

```markdown
**Problema:** … (prova: …)
**Serve:** M…
**Decisão do consultor:** …
**Onde discordou de mim:** …
**Porquê:** … (fonte: …; o que ela não cobre: …)
**Alternativas deixadas:** …
**Como saberemos que errámos:** …
**Por confirmar:** …
**Precisa do teu "sim":** … (ou "nada")
```

A decisão do consultor escolhe a solução. Os "sim" que o `CLAUDE.md` reserva ao utilizador (merge das
categorias que sobem, risco de perda de dados) continuam a ser dele, tal como o âmbito do produto quando o
consultor o marcar como escolha de negócio.

Regista a decisão no sítio indicado em
[registar-decisoes.md](../documentacao-projeto/references/registar-decisoes.md).

**Concluído quando:** a decisão está registada com a posição do consultor e o utilizador viu o resumo.
