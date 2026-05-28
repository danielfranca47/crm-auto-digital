# Guia: Como Documentar uma Implementação

Este arquivo é um guia de instrução para o Claude. Leia-o antes de criar qualquer arquivo em `docs/implementations/`.

---

## Quando este guia se aplica

O utilizador pediu para melhorar algo no sistema. Pode ter dito coisas como:

- "Gostaria de melhorar X porque Y"
- "O sistema está fazendo Z, mas deveria fazer W"
- "Quero adicionar a funcionalidade X"
- "Tem um bug em X que causa Y"

Antes de escrever qualquer código, crie o arquivo de implementação conforme este guia.

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

### Quando a implementação estiver completa

Alterar o cabeçalho de status:

```markdown
**Status:** Todos os cenários validados (DD/MM/AAAA) — pendente: <o que ainda falta, se houver>
```

---

## Regras de escrita

1. **Registrar decisões, não só resultado.** Se uma abordagem foi descartada, dizer por quê em uma frase.
2. **Causa raiz explícita.** "O bug era X" é mais útil que "o sistema fazia Y errado".
3. **Antes/depois de código** apenas quando a mudança é não-óbvia. Não documentar código óbvio.
4. **Sem histórico acumulado** no texto corrido. Não escrever "antes fazia X, agora passou a fazer Y" no corpo — isso fica nos commits e na seção de diagnóstico.
5. **Tabela de arquivos sempre presente** por fase — é o mapa rápido para quem precisa revisar o código.
6. **Checks de validação realistas.** Cada cenário deve ser executável por alguém sem contexto interno. Incluir o setup necessário.

---

## Exemplo de sequência de trabalho

```
Utilizador: "Gostaria de melhorar X porque Y e Z"

Claude:
  1. Lê este guia
  2. Cria docs/implementations/<nome>.md com Motivação + Problemas + Abordagem + Plano
  3. Apresenta o plano ao utilizador antes de escrever código
  4. Aguarda confirmação (ou ajustes)
  5. Implementa Fase 1
  6. Atualiza o arquivo: adiciona commits + marca checks validados
  7. Repete para fases seguintes
```

O arquivo de implementação é o **contrato vivo** entre o utilizador e o Claude durante o desenvolvimento da feature.
