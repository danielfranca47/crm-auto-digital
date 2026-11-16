# Auditar o CLAUDE.md

**Mostra sempre o relatório antes de alterar qualquer coisa** e só altera com a aprovação do utilizador.
Mudar o `CLAUDE.md` é uma categoria que sobe na fila automática.

## 1. Encontrar os ficheiros

```bash
git ls-files | grep -iE '(^|/)(CLAUDE|AGENTS)\.md$|\.claude\.local\.md$'
```

Inclui os `CLAUDE.md` de subpastas, que o Claude carrega quando trabalha nessas pastas. O
`~/.claude/CLAUDE.md` (global do utilizador) e o `.claude.local.md` (pessoal, fora do git) só se avaliam
se o utilizador pedir.

## 2. Avaliar (100 pontos)

Lê cada ficheiro inteiro e confronta-o com o repositório: os caminhos existem? Os comandos funcionam? As
descrições batem com o código?

| Critério | Pontos | O que se avalia |
|---|---|---|
| Comandos e fluxos | 20 | arrancar, testar e fazer deploy de cada serviço; fluxo de trabalho claro |
| Clareza da arquitetura | 20 | mapa dos serviços e pastas, relações, pontos de entrada |
| Padrões não óbvios | 15 | armadilhas, contornos, "porquê fazemos assim" |
| Concisão | 15 | cada linha acrescenta; nada repetido de outros docs ou do código |
| Atualidade | 15 | caminhos, comandos e stack correspondem ao estado atual |
| Acionabilidade | 15 | instruções executáveis: comandos copiáveis, caminhos reais |

Nota: A 90–100 · B 70–89 · C 50–69 · D 30–49 · F 0–29.

**Sinais de alerta:** comandos que falhariam; referências a ficheiros ou pastas apagados; versões
desatualizadas; texto de modelo sem adaptação; conselhos genéricos; TODOs nunca feitos; a mesma
informação em vários `CLAUDE.md` ou em `docs/`.

### Regras próprias deste projeto

- O `CLAUDE.md` é **índice e regras**. O detalhe vive em `docs/` e o `CLAUDE.md` aponta para lá
  ("Processo completo: ver …"). Propor mover detalhe para `docs/` e deixar o apontador é a forma
  preferida de encurtar.
- As secções de regras obrigatórias ("Git workflow", "Workflow de Implementação", "Fila automática",
  "Painel Admin — regra obrigatória", "Paridade Playground ↔ WhatsApp") pesam no comportamento. Nunca
  se cortam nem se suavizam sem o utilizador decidir explicitamente; encurtar só movendo o detalhe para
  o doc que já existe.
- Cada apontador do `CLAUDE.md` tem de levar a um ficheiro existente: verifica todos os links e
  caminhos citados.
- A tabela "Documentação de Arquitetura" tem de listar todos os docs de `docs/architecture/` que um
  agente precisa de conhecer.

## 3. Relatório (antes de qualquer alteração)

```
## Relatório do CLAUDE.md

### Resumo
- Ficheiros: X · Nota média: X/100 · A precisar de alteração: X

### ./CLAUDE.md — XX/100 (X)
| Critério | Nota | Notas |
|---|---|---|
| Comandos e fluxos | X/20 | … |
| … | | |

**Problemas:** <lista concreta, com linha>
**Propostas:** <lista>
```

Para o utilizador, acrescenta um parágrafo em linguagem simples: o que está bem, o que mais pesa e o
que propões.

## 4. Propor alterações

Só entra o que ajuda sessões futuras: comandos descobertos, armadilhas, relações entre serviços que o
código não mostra, abordagens de teste que funcionaram, particularidades de configuração.

Não entra: o que o nome do código já diz, boas práticas genéricas, correções pontuais que não se repetem
e explicações longas onde chega uma linha.

Para cada alteração:
1. **Ficheiro e secção** onde entra.
2. **A alteração** em formato diff.
3. **Porque ajuda**, numa frase.

Escreve as alterações com as regras de [escrever-para-agentes.md](escrever-para-agentes.md).

## 5. Aplicar

Depois do "sim", aplica com Edit, mantendo a estrutura. Antes de dar por concluído, confirma:
- [ ] cada acrescento é específico do projeto;
- [ ] os comandos foram testados e os caminhos existem;
- [ ] é a forma mais curta de dizer aquilo;
- [ ] nada ficou duplicado com `docs/`.

**Concluído quando:** o relatório foi mostrado, as alterações aprovadas foram aplicadas, os links foram
verificados e a nota foi recalculada.
