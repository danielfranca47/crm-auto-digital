# Guia: Como Resolver Conflitos de Merge

> Referenciado por [`CLAUDE.md`](../../CLAUDE.md), secção "Estratégia de branch por
> implementação" → "Resolução de conflitos". Ler este arquivo sempre que um
> `git merge` (passo de graduação de uma implementação, ver
> [`_processo-graduacao-implementacao.md`](_processo-graduacao-implementacao.md),
> Passo 8) reportar conflito.

---

## Por que este guia existe

O utilizador não é programador e não vai saber decidir qual lado de um
conflito manter — nem é essa a expectativa. **Claude resolve todo conflito
sozinho, sempre**, usando os critérios abaixo, e só depois explica em
português simples o que aconteceu, o que foi decidido e como reverter caso a
decisão não seja a desejada. Não há passo de "aguardar decisão do
utilizador" no meio do processo — a única exceção é risco real e
irreversível de perda de dados (secção 5).

---

## 0. Configuração que ajuda antes de qualquer conflito acontecer

Rodar uma vez neste repositório (já feito nesta máquina — ver nota no fim
desta secção):

```bash
git config merge.conflictStyle zdiff3
```

Isto muda os marcadores de conflito para incluir o **ancestral comum** — a
versão do trecho antes de qualquer uma das duas branches mexer nele:

```
<<<<<<< HEAD (branch atual)
...conteúdo da branch atual...
||||||| (ancestral comum — como era antes de qualquer lado mudar)
...conteúdo original...
=======
...conteúdo da branch que está sendo mergeada...
>>>>>>> feat/nome-da-branch
```

Sem isso, o Claude só vê "lado A" e "lado B", sem saber qual era a intenção
original de cada mudança — com o ancestral visível, dá pra perceber se as
duas mudanças são complementares (mecânico) ou realmente contraditórias
(comportamento). `zdiff3` (mais recente que `diff3`) também resolve
automaticamente mais casos triviais, deixando só os conflitos reais para
análise.

*(Configuração local via `git config`, não versionada — cada clone deste
repositório precisa rodar o comando uma vez.)*

---

## 1. Ao detectar o conflito

- `git status` — lista os arquivos em conflito (`both modified`)
- `git diff --name-only --diff-filter=U` — lista só os arquivos conflitantes
- Para isolar o que cada lado mudou em relação ao ancestral comum:
  `git diff --ours -- <arquivo>` e `git diff --theirs -- <arquivo>`

---

## 2. Classificar o conflito

### Mecânico

O git não conseguiu juntar automaticamente duas mudanças só por estarem
próximas no arquivo, mas elas **não se contradizem** — ex.: duas funções
novas adicionadas na mesma área, dois imports adicionados perto um do outro,
duas linhas de uma tabela markdown inseridas no mesmo ponto.

**Resolução:** manter as duas mudanças, remover os marcadores.

### Comportamento / regra de negócio

As duas branches mudaram a **mesma regra, valor, config, schema ou lógica**
de forma incompatível — manter as duas não faz sentido, é preciso escolher
ou combinar de um jeito que normalmente seria uma decisão de produto.

Exemplos concretos neste sistema:
- Duas branches mudam os campos mínimos de `services/qualification_guardrails.py`
  para o mesmo `agent_mode` (ex.: uma leva `consultivo` para 5 campos, outra para 7)
- Duas branches alteram o mesmo campo em `ai_profiles` (core) com defaults ou
  validações diferentes
- Duas branches mudam o mesmo side-effect de `services/lead_category_policy.py`
  (ex.: uma desativa o bot ao entrar em `closing`, outra muda a condição)
- Qualquer conflito em **migrations/schema** — ver secção 6

**Regra:** a classificação decide qual critério da secção 3 usar para
escolher — não decide mais se o Claude pausa ou não. Os dois casos são
resolvidos sozinho, sem exceção fora da secção 5.

---

## 3. Heurística de decisão (conflitos de comportamento)

Quando as duas branches mudaram a mesma coisa de forma incompatível e não dá
para manter as duas, aplicar esta ordem de critérios até um deles decidir:

1. **Segurança/conservadorismo primeiro.** Entre duas opções, preferir a que
   falha de forma mais segura: a validação mais estrita (guardrail que
   bloqueia mais casos em vez de menos), a permissão mais restritiva, o
   valor que evita perda de dados. Ex.: se uma branch exige 6 campos mínimos
   de qualificação e a outra exige 4, manter os 6 — é mais fácil relaxar uma
   regra estrita depois do que descobrir que dados incompletos passaram.
2. **Intenção mais recente vence.** Se nenhum lado é claramente "mais
   seguro", usar o commit mais recente (`git log -1 --format=%cI <hash>` de
   cada lado) como critério de desempate — representa a decisão mais atual
   sobre aquele comportamento.
3. **Se a mudança tem impacto financeiro, de compliance ou de dados do
   cliente** (preço, desconto, prazo de cobrança, retenção de dados, acesso)
   e os critérios 1–2 não resolvem com confiança — **ainda assim resolver**,
   aplicando o critério 2 como default, mas marcar isso com destaque no
   relatório pós-merge (secção 7.2) para o utilizador poder corrigir com uma
   frase, sem precisar reabrir o merge manualmente.

Este critério é sempre aplicado sozinho — a resolução não espera confirmação
antes de prosseguir. A única exceção genuína está na secção 5.

---

## 4. Resolver

1. Editar o(s) arquivo(s) aplicando a escolha (mecânico: manter as duas
   mudanças; comportamento: aplicar o resultado da heurística da secção 3)
2. `git add <arquivo>`
3. Validar (secção 7.1) antes de finalizar
4. `git commit` (finaliza o merge)
5. Escrever o relatório pós-merge (secção 7.2) — obrigatório, mesmo em
   conflitos triviais

### Nunca fazer

- `git checkout --ours <arquivo>` / `--theirs <arquivo>` sem entender o que
  está sendo descartado — descarta um lado inteiro; usar só quando já se
  decidiu (pela heurística) que um lado inteiro perde mesmo
- Commitar com marcadores de conflito ainda no arquivo
- Usar `--no-verify` para forçar o commit do merge se um hook falhar

### Se a resolução ficar confusa tecnicamente

`git merge --abort` sempre volta ao estado de antes do merge, sem nenhum
risco. Usar sempre que a resolução técnica não estiver clara (ex.: o
conflito é grande demais pra entender com confiança o que cada lado faz), e
replanejar antes de tentar de novo — abortar e reavaliar não é falha, é a
opção mais segura quando em dúvida técnica genuína.

---

## 5. Quando ainda assim pausar (exceção)

A única situação em que Claude pausa e pergunta antes de finalizar o merge:
**risco real e irreversível de perda ou corrupção de dados**, onde nenhuma
das duas opções da heurística (secção 3) é claramente segura — ex.: duas
migrations renomeiam/removem a mesma coluna de formas diferentes, ou duas
branches mudam a mesma lógica de exclusão de dados de cliente.

Mesmo aí, a pergunta é sempre concreta, não-técnica, e já vem com uma opção
padrão pronta — nunca um pedido pra "decidir entre estes dois trechos de
código":

> "Encontrei um conflito envolvendo [o quê, em termos simples]. Não dá pra
> saber com segurança qual versão está certa sem reverter dados possíveis.
> Vou seguir com [opção X] a menos que você prefira [opção Y] — pode
> confirmar ou pedir a outra?"

Fora deste caso específico (dados irreversíveis), **não pausar** — resolver,
validar e reportar depois, mesmo em conflitos de comportamento com impacto
de negócio (ver secção 3, critério 3).

---

## 6. Casos especiais deste repositório

- **Migrations / schema** (`backend-crm` sem ORM, via `ensure_column()`;
  `ai_profiles` no `backend-core` via SQLAlchemy) — tratar como conflito de
  comportamento (secção 2) e prestar atenção redobrada: se envolver
  remoção/renomeação de coluna com dados existentes, cai na exceção da
  secção 5. Se for só duas chamadas `ensure_column()` idempotentes
  adicionando colunas diferentes, é mecânico — manter as duas.
- **`docs/architecture/*.md`** — não tentar "juntar" os dois textos linha a
  linha. Reescrever a seção afetada como espelho do estado atual do código
  pós-merge — mesma regra já usada no processo de graduação ("sem histórico
  acumulado, reescrever a secção").
- **`docs/implementations/<arquivo>.md`** — cada implementação tem a própria
  branch (ver `CLAUDE.md`), então normalmente não há conflito aqui. Se
  acontecer (duas implementações relacionadas tocando o mesmo arquivo),
  tende a ser mecânico: o padrão do guia já é sempre *acrescentar* seções de
  fase, nunca reescrever o que já existe (ver
  [`_guia-documentar-implementacao.md`](_guia-documentar-implementacao.md),
  regra de escrita 4).

---

## 7. Validar e relatar

### 7.1 Validar antes de finalizar

- Se o merge tocou código (não só docs): rodar o que for rápido e já existir
  no projeto (testes, typecheck, lint) antes do commit final do merge.
  Conflitos textuais resolvidos sem erro do git ainda podem quebrar
  comportamento — chamado de **conflito semântico**: o merge "compila" mas o
  resultado não faz o que nenhuma das duas branches pretendia (ex.: uma
  branch muda a assinatura de uma função, a outra branch adiciona uma
  chamada a essa função longe o suficiente pra não gerar conflito textual,
  mas o código final quebra).
- Buscar marcadores esquecidos antes do `git add` final:
  `grep -rn "<<<<<<<\|=======\|>>>>>>>" <arquivos-resolvidos>`

### 7.2 Relatório obrigatório pós-merge

Depois de qualquer merge que teve conflito (mecânico ou de comportamento),
escrever sempre um resumo em português simples, sem jargão de código, com:

1. **O que conflitou** — em que arquivo/área, em uma frase (ex.: "as regras
   de quantos campos são obrigatórios antes de fechar venda")
2. **O que cada lado tentava fazer** — sem mostrar código
3. **O que foi decidido e por quê** — qual critério da secção 3 foi usado
4. **Como reverter, se não for o que o utilizador queria** — normalmente
   basta pedir para ajustar; Claude cuida da mecânica do git

Este relatório substitui a pergunta prévia — é a forma de o utilizador
manter controlo sobre o resultado sem precisar entender o processo técnico.

---

## 8. Prevenção (reduz a chance de precisar deste guia)

- Branches curtas — já é regra do processo (graduação assim que os checks passam)
- Merges sempre sequenciais, nunca simultâneos — já é regra do `CLAUDE.md`
- Se uma branch ficar aberta por muito tempo, sincronizar com a branch
  original periodicamente (merge da original nela) — conflitos pequenos e
  frequentes são mais fáceis de resolver do que um grande no final

---

## Fontes

- [Git - git-merge Documentation](https://git-scm.com/docs/git-merge/2.38.0)
- [Git's Diff3 Conflict Style And How To Use It](https://medium.com/codex/gits-diff3-conflict-style-and-how-to-use-it-91132a040837)
- [Git: Improve conflict display with the zdiff3 style — Adam Johnson](https://adamj.eu/tech/2023/12/29/git-conflict-display-zdiff3/)
- [Understanding zealous diff3 style in Git conflicts](https://neg4n.dev/blog/understanding-zealous-diff3-style-git-conflict-markers)
- [Popular git config options — Julia Evans](https://jvns.ca/blog/2024/02/16/popular-git-config-options/)
- [Detecting Semantic Conflicts using Static Analysis (arXiv)](https://arxiv.org/html/2310.04269)
- [Detecting Semantic Conflicts with Unit Tests (arXiv)](https://arxiv.org/html/2310.02395)
- [5 Steps for Resolving Merge Conflicts in Git — OneNine](https://onenine.com/5-steps-for-resolving-merge-conflicts-in-git/)
