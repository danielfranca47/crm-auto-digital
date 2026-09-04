# docs/implementations — Guia para o Developer

## O que é esta pasta

Documentos de trabalho para features e fixes em desenvolvimento. Cada arquivo
acompanha uma implementação do início ao fim — do diagnóstico inicial aos testes
validados. São documentos temporários: quando tudo estiver validado, o conteúdo
relevante é migrado para `docs/architecture/` e o arquivo é deletado.

---

## Ficheiros

### Ficheiros com `_` — guias e processos (permanentes)

| Ficheiro | Para que serve |
|---|---|
| `_guia-documentar-implementacao.md` | Processo completo: como o Claude cria e mantém um arquivo de implementação (Plan Mode, estrutura, ciclo de vida) |
| `_template-implementacao.md` | Exemplo concreto preenchido — como fica um arquivo bem estruturado na prática |
| `_processo-graduacao-implementacao.md` | O que fazer quando um arquivo está completo: migrar para architecture, deletar, sugerir próximos passos |

### Ficheiros de dados de sessão (gitignored, não são guias)

| Ficheiro | Para que serve |
|---|---|
| `_conta-teste-local.md` | Credenciais da conta de teste — preenchido uma única vez, referenciado pelas sessões de teste em vez de repetido |
| `_sessao-teste-corrente.md` | Rascunho de trabalho de uma sessão de teste automatizado via browser (MCP) — sobrescrito a cada sessão nova, nunca acumula |

### Ficheiros regulares — implementações activas

Arquivos em andamento ou recém-completados. Seguem o padrão do template.

| Ficheiro | Status |
|---|---|
| `correcao-natural-llm-e-fixes-ui-descobertos.md` | Em andamento — planeado, código ainda não iniciado |

> `agent-local-v2-app-standalone.md`, `agentlocal-assistente-ia.md`,
> `agent-local-v2-testes-manuais.md`, `agent-local-plano-execucao-testes-pendentes.md`
> e `agent-local-v2-empacotamento-exe.md` foram graduados — ver
> [`docs/architecture/agent-local-app.md`](../architecture/agent-local-app.md)
> (v2) e [`docs/plans/agent-local-melhorias-futuras-V3.md`](../plans/agent-local-melhorias-futuras-V3.md) (v3).

---

## Como funciona o ciclo de vida

```
Tu describes uma melhoria ou bug
  → Claude: Plan Mode (diagnóstico + plano)
  → Tu aprovares
  → Claude cria o arquivo + implementa + commit
  → Claude escreve checks + "Relatório da Fase N" (linguagem simples)
  → Claude pergunta: testar agora via browser (MCP)?

Testes executados (ao vivo ou reportados por ti, mesmo numa conversa nova)
  → Claude actualiza [x] neste arquivo

Arquivo com todos os checks obrigatórios [x]
  → Claude segue _processo-graduacao-implementacao.md
  → Migra para docs/architecture/
  → Triagem da secção "Ajustes Possíveis" (Passo 5b): pergunta quais são
    válidos e a prioridade; migra para implementations/ (urgente) ou plans/
    (não-urgente)
  → Deleta este arquivo
```

---

## Prompts úteis

### Quero começar uma nova feature ou fix

```
Segue o processo em docs/implementations/_guia-documentar-implementacao.md.
Quero [descrever a feature/bug].
```

### Quero continuar uma feature que estava em andamento

```
Abre docs/implementations/[nome-do-arquivo].md, lê o estado actual e
continua de onde ficou. Qual é a próxima fase?
```

### Quero saber o estado de tudo o que está em desenvolvimento

```
Lê todos os arquivos docs/implementations/ (exceto os com _) e dá-me
um resumo: o que está completo, o que está em andamento, o que falta.
```

### Quero graduar um arquivo que está completo

```
O arquivo docs/implementations/[nome].md está com todos os checks validados.
Segue docs/implementations/_processo-graduacao-implementacao.md.
```

### Quero ver o que falta para completar um arquivo específico

```
Lê docs/implementations/[nome].md e lista só os checks pendentes [ ].
O que falta para estar completo?
```

### Quero que o Claude saiba o contexto antes de trabalhar

```
Antes de começar, lê docs/implementations/[nome].md e docs/architecture/_mapa-sistema.md
para teres contexto completo.
```

---

## O que esperar do Claude

**Ao criar um arquivo:**
- Entra em Plan Mode e faz diagnóstico antes de escrever código
- Aguarda a tua aprovação antes de avançar
- Cria o arquivo com estrutura completa (motivação, problemas, abordagem, fases, checks)
- Cada fase tem um commit associado com o hash registado no arquivo

**Ao actualizar um arquivo (testes ou nova fase):**
- Marca `[x]` com data e observação após cada cenário validado
- Adiciona nova fase ao final se um bug for encontrado (não edita o que já existia)
- Actualiza o `**Status:**` quando tudo estiver validado

**Ao graduar um arquivo:**
- Lê `_processo-graduacao-implementacao.md` e segue os passos
- Antes de deletar, faz a triagem obrigatória da secção "Ajustes Possíveis" /
  "Fora do Escopo" (Passo 5b): pergunta quais itens são válidos e qual a
  prioridade, e migra os validados para `docs/implementations/` (urgente) ou
  `docs/plans/` (não-urgente) — nunca descarta esses itens em silêncio
- Só migra o que é arquitecturalmente relevante (comportamentos, schemas, fluxos)
- Deixa o histórico de fases no git log

---

## Quando um arquivo fica "completo"

Um arquivo está pronto para graduação quando:
- `**Status:**` diz `Todos os cenários validados`
- Todos os checks obrigatórios têm `[x]` (edge cases com `[⏭️]` são aceitáveis)
- Não há fases abertas sem commit associado

Se tiveres dúvida, pede:
```
O arquivo [nome].md está pronto para graduar? O que falta?
```
