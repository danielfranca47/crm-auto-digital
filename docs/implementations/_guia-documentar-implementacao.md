# Guia: Como Documentar uma Implementação

Este arquivo é um guia de instrução para o Claude. Leia-o antes de criar qualquer arquivo em `docs/implementations/`.

---

## Quando este guia se aplica

O utilizador pediu para melhorar algo no sistema. Pode ter dito coisas como:

- "Gostaria de melhorar X porque Y"
- "O sistema está fazendo Z, mas deveria fazer W"
- "Quero adicionar a funcionalidade X"
- "Tem um bug em X que causa Y"

Antes de escrever qualquer código, siga os passos abaixo em ordem.

---

## Passo 0 — Diagnóstico em Plan Mode (obrigatório)

> **Se o pedido vier de um plano de sprint (`plano-sprint-*.md`):** o contexto técnico
> já está pré-digerido no prompt. Usar esse contexto como ponto de partida para o Plan Mode
> — não é necessário reler o `docs/plans/*` separadamente.

**Antes de criar o arquivo ou tocar no código**, entrar em Plan Mode e responder três perguntas:

### 1. Essa funcionalidade já existe?

Ler os arquivos relevantes do sistema (rotas, serviços, frontend) e verificar se o comportamento pedido já está implementado total ou parcialmente. Citar os arquivos e linhas onde encontrou (ou não encontrou).

### 2. Se não existe, o que precisa ser construído?

Identificar os pontos de entrada e saída da mudança:
- Qual arquivo recebe a mudança primeiro?
- Quais serviços/rotas precisam ser alterados?
- Há impacto em banco de dados (nova coluna, nova tabela)?
- Há impacto no frontend?

### 3. Quais são os riscos e dependências?

- A mudança pode quebrar algo que já funciona? Onde?
- Há dependência de outra feature que ainda não existe?
- Há trade-offs relevantes que o utilizador deve conhecer antes de decidir?

**Formato do plano no Plan Mode:**

```
## Diagnóstico

### Já existe?
<Sim / Parcialmente / Não> — <explicação com arquivos e linhas>

### O que precisa ser construído
<Lista das mudanças necessárias, agrupadas por camada: backend-core / backend-crm / backend-executors / frontend>

### Riscos e dependências
<Lista de riscos. "Nenhum" é uma resposta válida se for o caso.>

### Proposta de fases
Fase 1 — <nome> — <objetivo em uma frase>
Fase 2 — <nome> — <objetivo em uma frase>
...
```

**Aguardar aprovação do utilizador antes de avançar.** O utilizador pode ajustar escopo, descartar fases ou pedir mais investigação.

---

## Passo 1 — Nomear e criar o arquivo

**Formato do nome:** `etapa-<codigo>-<slug-descritivo>.md`

Exemplos:
- `etapa-8-7-notificacoes-push.md`
- `etapa-9-1-export-leads-csv.md`
- `camada5-validacao-formulario.md`

Se não houver código de etapa claro, usar um slug descritivo direto:
- `melhoria-performance-kanban.md`
- `fix-duplicacao-follow-up.md`

---

## Passo 2 — Estrutura do arquivo a criar

> **Exemplo concreto preenchido:** [`_template-implementacao.md`](_template-implementacao.md)
> Leia-o antes de criar o seu arquivo — mostra como fica na prática cada secção descrita abaixo.

Copie e preencha o template abaixo. As seções marcadas com `(*)` são obrigatórias. As demais são opcionais conforme a complexidade da feature.

```markdown
# <Título descritivo da feature>

**Branch:** `<branch-atual>`
**Status:** Em andamento

---

## Motivação

<Por que o utilizador quer esta mudança? Qual é o comportamento atual e qual é o comportamento desejado? Se houver causa raiz conhecida, descrever aqui.>

---

## Problemas Identificados (estado anterior) (*)

<Lista numerada dos problemas concretos encontrados no código ou no comportamento. Ex:>

1. **Nome do problema:** descrição + arquivo/linha onde ocorre.
2. **Nome do problema:** descrição + arquivo/linha onde ocorre.

---

## Abordagem (*)

<Descrever em prosa ou diagrama ASCII como a solução vai funcionar. Se houver pipeline de dados, mostrar o fluxo resultante:>

```
Entrada → Passo A → Passo B → Saída
  ├─ caso X → comportamento X
  └─ caso Y → comportamento Y
```

---

## Plano de Implementação (*)

Dividir em fases quando há dependências entre partes. Cada fase deve ser implementável e testável de forma independente.

### Fase 1 — <Nome>

**Objetivo:** <uma frase>

| Arquivo | O que muda |
|---|---|
| `caminho/do/arquivo.py` | Descrição da mudança |

<Se a mudança for não-óbvia, incluir trecho antes/depois:>

```python
# ANTES
codigo_antigo()

# DEPOIS
codigo_novo()
```

### Fase 2 — <Nome> (se houver)

...

---

## Checks de Validação (*)

Cenários testáveis. Usar prefixo `P` para playground, `C` para fluxo real (WhatsApp/produção).

### Cenário P1 — <Descrição>
- [ ] Passo de setup
- [ ] Ação
- [ ] O que confirmar

### Cenário C1 — <Descrição>
- [ ] ...

---

## Ajustes Possíveis Pós-Implementação

<Limitações conhecidas, trade-offs conscientes, melhorias futuras que ficaram fora do escopo desta iteração.>
```

---

## Passo 3 — Ciclo de vida do arquivo

O arquivo **cresce** conforme a implementação avança. Nunca reescreva o que já foi documentado — acrescente.

### Quando uma fase é implementada

Adicionar à seção da fase:

```markdown
### Commits Fase N

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `<hash>` | Descrição resumida |

**Detalhes do commit `<hash>`:**
- `arquivo.py` — o que mudou especificamente
- `componente.tsx` — o que mudou especificamente
```

### Antes de pedir validação ao utilizador

Depois do commit, e **antes** de aguardar o utilizador testar, dois passos
obrigatórios:

**1. Escrever o relatório da fase em linguagem simples**, no próprio arquivo:

```markdown
### Relatório da Fase N — o que mudou na prática

**Antes:** <comportamento anterior, sem jargão de código, 1-2 frases>
**Agora:** <comportamento novo, 1-2 frases>
**Para validar:** <quais Cenários da secção "Checks de Validação" cobrem esta
fase — ex.: "Cenário P1 e C1, abaixo">
```

Obrigatório mesmo em fases pequenas — o tamanho do texto acompanha o tamanho
da mudança, mas a secção nunca fica de fora. Serve dois propósitos: (a)
comunicar o impacto real ao utilizador sem jargão, (b) permitir retomar o
trabalho numa conversa nova ("lê `<arquivo>.md`, secção Fase N, e executa os
testes do Cenário X") sem reler o histórico do chat — economiza tokens em
conversas longas ou quando uma fase adicional surge depois de um bug.

**2. Perguntar se quer o teste automatizado agora:**

> "Quer que eu rode os Cenários X agora via browser (MCP chrome-devtools),
> com você acompanhando?"

- **Se sim:** ver "Testes automatizados via browser (MCP)", abaixo.
- **Se não, ou sem ambiente local disponível:** aguardar o utilizador testar
  manualmente e reportar — possivelmente numa conversa nova, usando o
  relatório da fase (passo 1, acima) como ponto de partida.

### Quando um cenário de validação é testado

Marcar o checkbox e registrar a data:

```markdown
- [x] Confirmar: bot responde ao conteúdo transcrito
- **Validado em:** 27/05/2026 — descrição do que foi observado
```

### Quando um teste revelar um bug ou comportamento inesperado

Adicionar uma nova seção no final (não editar o que já estava escrito):

```markdown
## Fase N+1 — Diagnóstico + Correção (data)

### Problema identificado

<O que o teste revelou. Qual era a causa raiz.>

### Correção

<O que foi alterado e por quê.>

| Arquivo | Mudança |
|---|---|
| ... | ... |
```

Esta nova fase segue o mesmo ciclo da secção anterior: commit → relatório da
fase em linguagem simples → checks → oferecer teste automatizado.

### Quando a implementação estiver completa

Alterar o cabeçalho de status:

```markdown
**Status:** Todos os cenários validados (DD/MM/AAAA) — pendente: <o que ainda falta, se houver>
```

Após todos os checks obrigatórios validados, executar o processo de graduação:

> **→ Seguir [`_processo-graduacao-implementacao.md`](_processo-graduacao-implementacao.md)**
>
> Esse processo garante que o conteúdo arquitecturalmente relevante é migrado para
> `docs/architecture/` antes de o arquivo de implementação ser removido.

---

## Regras de escrita

1. **Registrar decisões, não só resultado.** Se uma abordagem foi descartada, dizer por quê em uma frase.
2. **Causa raiz explícita.** "O bug era X" é mais útil que "o sistema fazia Y errado".
3. **Antes/depois de código** apenas quando a mudança é não-óbvia. Não documentar código óbvio.
4. **Sem histórico acumulado** no texto corrido. Não escrever "antes fazia X, agora passou a fazer Y" no corpo — isso fica nos commits e na seção de diagnóstico.
5. **Tabela de arquivos sempre presente** por fase — é o mapa rápido para quem precisa revisar o código.
6. **Checks de validação realistas.** Cada cenário deve ser executável por alguém sem contexto interno. Incluir o setup necessário.
7. **Relatório em linguagem simples por fase, escrito antes de pedir validação.** Permite retomar numa conversa nova ("lê o arquivo, secção Fase N") sem reler o histórico do chat — economiza tokens em conversas longas ou quando surge uma fase adicional por bug.

---

## Testes automatizados via browser (MCP)

Quando o utilizador aceitar a oferta de teste automatizado (ver "Antes de
pedir validação ao utilizador", em Passo 3):

- **Credenciais:** vivem só em `_conta-teste-local.md` (gitignored, preenchido
  uma única vez). Nunca escrever email/senha de conta de teste no arquivo de
  implementação, no chat, ou em qualquer arquivo versionado.
- **Rascunho da sessão:** usar `_sessao-teste-corrente.md` (gitignored,
  sobrescrito a cada sessão nova) — nunca criar um arquivo
  `checklist-testes-<slug>.md` por sessão; isso acumula arquivos no disco sem
  ligação clara a qual implementação pertencem.
- **Resultado:** transcrever sempre directamente nos checks do arquivo de
  implementação (`[x]` + data). O rascunho não é fonte de verdade — pode ser
  descartado depois da transcrição.

---

## Ciclo de vida de uma fase

As fases **não são planejadas todas de uma vez**. Cada fase nasce de uma necessidade concreta: o feedback inicial do utilizador, ou o resultado dos testes da fase anterior.

```
Utilizador reporta problema/melhoria
  → Claude: Plan Mode (diagnóstico + plano da Fase 1)
  → Utilizador aprova
  → Claude: cria o arquivo .md + implementa Fase 1 + commit
  → Claude: escreve checks + "Relatório da Fase 1" (linguagem simples)
  → Claude pergunta: "Quer que eu rode os testes agora via browser (MCP)?"
      ├─ Sim → Claude testa ao vivo, regista resultados nos checks
      └─ Não → aguarda o utilizador (pode ser numa conversa nova)

Resultado dos testes (sessão ao vivo ou reportado pelo utilizador)
  → Claude: marca os checks validados no arquivo

  Caminho A — tudo ok, sem mais necessidades
    → Trabalho encerrado. Status atualizado para concluído.

  Caminho B — teste revelou problema ou nova melhoria necessária
    → Claude: Plan Mode novamente (diagnóstico da nova necessidade)
    → Utilizador aprova
    → Claude: adiciona Fase 2 ao mesmo arquivo + implementa + commit
    → Claude: escreve checks + "Relatório da Fase 2" da nova fase
    → Claude pergunta de novo sobre teste automatizado
    → Ciclo se repete
```

**Regra:** cada fase tem exatamente um commit associado. O hash do commit é registrado no arquivo assim que é criado.

---

## Exemplo de sequência de trabalho

```
Utilizador: "Gostaria de melhorar X porque Y e Z.
             Leia o guia de implementação e siga o processo."

Claude:
  1. Lê este guia (_guia-documentar-implementacao.md)
  2. Entra em Plan Mode
  3. Lê os arquivos relevantes do sistema
  4. Produz diagnóstico (já existe? / o que construir / riscos / plano da Fase 1)
  5. Aguarda aprovação ou ajustes do utilizador

Utilizador: "Ok, avança."

Claude:
  6. Sai do Plan Mode
  7. Cria docs/implementations/<nome>.md com o template preenchido (Fase 1)
  8. Implementa Fase 1
  9. Faz commit e registra o hash no arquivo
  10. Escreve os checks pendentes + "Relatório da Fase 1" (linguagem simples)
  11. Pergunta: "Quer que eu rode os testes agora via browser (MCP)?"

Utilizador: "Não, vou testar eu mesmo." (pode ser numa conversa nova depois)

[... eventualmente, na mesma conversa ou numa nova ...]
Utilizador: "Testei — P1 e P2 ok, mas P3 tem um comportamento estranho: X"

Claude:
  12. Marca [x] em P1 e P2 com a data
  13. Entra em Plan Mode novamente para diagnosticar o problema de P3
  14. Propõe Fase 2

Utilizador: "Aprovado."

Claude:
  15. Adiciona seção Fase 2 ao mesmo arquivo
  16. Implementa + commit + registra hash
  17. Escreve os checks da Fase 2 + "Relatório da Fase 2"
  18. Pergunta de novo sobre teste automatizado

... e assim por diante até o utilizador encerrar.
```

**Nota:** o arquivo `.md` só é criado após o primeiro plan ser aprovado. O Plan Mode é o rascunho; o arquivo é o contrato formal que acompanha o código.

O arquivo de implementação é o **contrato vivo** entre o utilizador e o Claude durante o desenvolvimento da feature.
