# Guia: Análise de Planos e Geração de Sprint

Este arquivo é um guia de instrução para o Claude. Leia-o quando o utilizador pedir para analisar
os planos pendentes e gerar um sprint de implementação.

---

## Quando este guia se aplica

O utilizador pediu algo como:
- "Analisa os plans e monta o sprint"
- "Faz análise de planejamento"
- "O que devemos implementar agora?"
- "Revisa os docs/plans e prioriza"

---

## Passo 1 — Inventário

Ler todos os arquivos em `docs/plans/`. Para cada arquivo, listar os itens/melhorias
identificados com:
- Nome do item (ex.: M1, seção, título)
- Prioridade declarada no arquivo (se existir)
- Arquivo de origem e seção

**Resultado esperado:** tabela consolidada com todos os itens pendentes de todos os arquivos.

---

## Passo 2 — Auditoria técnica

Para cada item inventariado, verificar o estado real no sistema:

1. Ler os docs de arquitectura relevantes (`docs/architecture/`) para entender o estado
   documentado
2. Buscar no código os arquivos e linhas citados no item — não confiar apenas na documentação
3. Classificar cada item:
   - ✅ **Já existe** — comportamento descrito já está implementado
   - 🟡 **Parcialmente existe** — estrutura existe mas incompleta
   - ❌ **Não existe** — precisa ser construído do zero

Citar arquivo e linha para cada classificação.

---

## Passo 3 — Correlação e dependências

Depois de auditar todos os itens, identificar:
- **Dependências diretas:** item B só pode ser implementado depois de item A
- **Sinergias:** itens que convém implementar juntos (tocam os mesmos arquivos)
- **Bloqueios externos:** itens que dependem de decisão do administrador (preço,
  estratégia, configuração externa que o Claude não tem acesso)

---

## Passo 4 — Diagnóstico e perguntas ao admin

Apresentar ao utilizador, **antes de gerar o sprint:**

1. **Tabela de auditoria** — todos os itens com status e observações
2. **Mapa de dependências** — o que bloqueia o quê
3. **Perguntas de negócio** — apenas as que não têm resposta no código ou nos docs.
   Exemplos do tipo de pergunta válida:
   - "O preço X está confirmado antes de criarmos o seed?"
   - "A feature Y deve estar disponível em todos os planos ou só Growth+?"
   - "Qual é a data-alvo para ter Z disponível para clientes?"

   Não fazer perguntas que podem ser respondidas lendo o código.

**Aguardar as respostas antes de avançar para a priorização.**

---

## Passo 5 — Priorização

Com o diagnóstico completo e as respostas do admin, selecionar **2–3 itens** para o
sprint seguindo estes critérios em ordem de peso:

1. **Bloqueia receita ou utilizadores actuais** → prioridade máxima
2. **Alta prioridade declarada + baixo esforço** → quick wins
3. **Dependências já resolvidas** → itens cujos pré-requisitos já existem no sistema
4. **Sinergia de arquivos** → itens que tocam os mesmos arquivos (reduz risco de conflito)

Definir: 1 item principal (P1), 1–2 secundários (P2, P3).

Justificar brevemente **por que os restantes ficaram de fora** deste sprint.

---

## Passo 6 — Proposta e geração do arquivo

Apresentar a proposta de sprint ao utilizador (itens P1/P2/P3 com justificativa de ordem).
**Aguardar aprovação ou ajuste de escopo antes de criar o arquivo.**

Após aprovação, criar `docs/implementations/plano-sprint-YYYY-MM-DD.md` seguindo o
template `_template-plano-semanal.md`.

---

## Formato do prompt pronto (por item)

Cada item do sprint inclui um prompt auto-contido para o processo de implementations.
O prompt deve ter:

1. O pedido em linguagem natural
2. A motivação em 1 frase (por que agora)
3. O contexto técnico com arquivos e linhas (não assumir que o Claude de implementations
   leu o plans/)
4. A instrução para seguir o processo

Modelo:
```
Gostaria de implementar [título].
[Motivação — por que agora, o que está em risco ou a ganhar.]

Contexto: [resumo do que existe actualmente + o que precisa mudar, com arquivos e linhas].

Leia o guia de implementação e siga o processo.
```

O prompt deve ser **auto-contido** — o Claude de implementations não precisa abrir nenhum
outro arquivo para ter o contexto necessário para o Plan Mode.

---

## Ciclo de vida dos arquivos docs/plans/*

Após cada item do sprint ser implementado (todos os checks do implementation validados e
arquivo de implementação graduado):

1. Marcar o item como implementado no arquivo `plans/*` correspondente
2. Quando **todos os itens** de um arquivo `plans/*` estiverem absorvidos → deletar:
   ```
   git rm docs/plans/<arquivo>.md
   ```
3. Incluir a remoção no commit de graduação da última implementação daquele arquivo

Um arquivo `plans/*` com todos os itens absorvidos não tem razão de existir — deletar é
o comportamento esperado.

---

## Sequência completa de trabalho

```
Utilizador: "Analisa os plans e monta o próximo sprint."

Claude:
  1. Lê este guia
  2. Lê todos os docs/plans/*.md → inventário
  3. Audita cada item no código + docs/architecture/
  4. Mapeia dependências e identifica perguntas

Claude apresenta:
  → Tabela de auditoria
  → Mapa de dependências
  → Perguntas de negócio (se houver)

Utilizador responde às perguntas

Claude:
  5. Prioriza P1/P2/P3 com justificativa
  6. Apresenta proposta de sprint e aguarda aprovação

Utilizador: "Aprovado" (ou ajusta escopo)

Claude:
  7. Cria docs/implementations/plano-sprint-YYYY-MM-DD.md

--- Ciclo de implementations ---

Utilizador copia o prompt pronto do item P1 e inicia implementação:
  → Claude de implementations lê _guia-documentar-implementacao.md
  → Segue o processo normal (Plan Mode → código → commit → validação)

Após implementations P1 concluída e graduada:
  → Marcar P1 como absorvido no plans/*
  → Se plans/* esvaziou → git rm

Repetir para P2, P3.
```

---

## Regras de escrita do arquivo de sprint

1. **Não duplicar o que está nos plans/*.** O prompt pronto já tem o contexto — a seção
   de contexto no sprint é um resumo executivo, não uma cópia.
2. **Sem histórico de deliberação.** O sprint mostra o resultado da análise, não o processo
   de como chegou lá.
3. **Perguntas respondidas ficam no arquivo.** As respostas do admin são registadas no
   sprint para referência do Claude de implementations.
4. **Itens excluídos têm justificativa em 1 frase.** Não deixar implícito o porquê de
   cada item ter ficado de fora.
