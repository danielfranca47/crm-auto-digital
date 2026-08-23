# Guia: Como Resolver Conflitos de Merge

> Referenciado por [`CLAUDE.md`](../../CLAUDE.md), secção "Estratégia de branch por
> implementação" → "Resolução de conflitos". Ler este arquivo sempre que um
> `git merge` (passo de graduação de uma implementação, ver
> [`_processo-graduacao-implementacao.md`](_processo-graduacao-implementacao.md),
> Passo 8) reportar conflito.

---

## Por que este guia existe

O utilizador não é programador — resolver um conflito de merge tecnicamente é
sempre trabalho do Claude, nunca uma leitura de diff que se pede a ele. Este
guia existe para o Claude ter um critério consistente sobre:

1. Quando resolver sozinho (e só reportar depois)
2. Quando parar e pedir uma decisão — sempre em português simples, em termos
   de comportamento do sistema, nunca mostrando código ou marcadores de conflito

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
ou combinar de um jeito que é uma decisão de produto, não só de código.

Exemplos concretos neste sistema:
- Duas branches mudam os campos mínimos de `services/qualification_guardrails.py`
  para o mesmo `agent_mode` (ex.: uma leva `consultivo` para 5 campos, outra para 7)
- Duas branches alteram o mesmo campo em `ai_profiles` (core) com defaults ou
  validações diferentes
- Duas branches mudam o mesmo side-effect de `services/lead_category_policy.py`
  (ex.: uma desativa o bot ao entrar em `closing`, outra muda a condição)
- Qualquer conflito em **migrations/schema** — ver secção 4

**Regra:** na dúvida entre os dois casos, tratar como comportamento (mais
seguro perguntar de mais do que decidir sozinho uma regra de negócio).

---

## 3. Resolver

### Caso mecânico

1. Editar o arquivo mantendo as duas mudanças, remover os marcadores
2. `git add <arquivo>`
3. Depois de todos os arquivos resolvidos, validar (secção 5)
4. `git commit` (finaliza o merge)
5. Reportar ao utilizador em 1-2 frases, sem jargão — ex.: "o merge juntou
   as duas mudanças sem perder nada de nenhum lado"

### Caso de comportamento

1. **Não editar/resolver ainda.**
2. Preparar o resumo em português simples e concreto — o que o sistema vai
   fazer em cada opção, nunca mostrando código ou marcador de conflito. Ex.:
   "a branch A faz o desconto expirar em 7 dias; a branch B faz expirar em
   30 dias. Qual mantemos — ou você quer um valor diferente dos dois?"
3. Aguardar a decisão do utilizador
4. Aplicar a decisão no arquivo, `git add`, validar (secção 5), `git commit`
5. Reportar o resultado final

### Nunca fazer

- `git checkout --ours <arquivo>` / `--theirs <arquivo>` sem explicar antes —
  descarta um lado inteiro silenciosamente
- Commitar com marcadores de conflito ainda no arquivo
- Usar `--no-verify` para forçar o commit do merge se um hook falhar

### Se a situação não estiver clara

`git merge --abort` sempre volta ao estado de antes do merge, sem nenhum
risco. Usar sempre que não houver certeza sobre a resolução, e replanejar
antes de tentar de novo — abortar não é falha, é a opção mais segura quando
em dúvida.

---

## 4. Casos especiais deste repositório

- **Migrations / schema** (`backend-crm` sem ORM, via `ensure_column()`;
  `ai_profiles` no `backend-core` via SQLAlchemy) — tratar **sempre** como
  conflito de comportamento, nunca mecânico. Duas colunas com o mesmo nome e
  tipos diferentes, ou uma ordem de migração diferente, podem quebrar
  silenciosamente sem o git acusar conflito nenhum.
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

## 5. Depois de resolver — validar antes de finalizar

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

---

## 6. Prevenção (reduz a chance de precisar deste guia)

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
