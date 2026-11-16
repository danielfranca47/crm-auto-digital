# Registar decisões

O documento mais valioso guarda o **porquê**: o contexto, as restrições e os compromissos que levaram a
uma escolha. O código mostra o quê; a documentação explica porque se fez assim e não de outra forma.
Sem isso, a mesma discussão volta meses depois, com pessoas ou agentes.

## Quando registar

- Escolher entre abordagens concorrentes.
- Algo caro de reverter: estrutura de dados, integração externa, contrato entre serviços.
- Mudar um comportamento que o utilizador ou os clientes veem.
- Ver-se a explicar a mesma coisa pela segunda vez.

O que é óbvio a ler o código não se regista.

## Onde fica: a convenção deste projeto

Este projeto **não usa uma pasta de ADRs** (`docs/decisions/`) e não se cria uma. O porquê vive no fluxo
que já existe:

| Momento da decisão | Onde se escreve |
|---|---|
| "Vale a pena fazer isto?" | `docs/discovery/<tema>.md`: opções, RICE e veredito do utilizador |
| "Como vamos fazer?" | `docs/implementations/<slug>.md`: Motivação, Abordagem, alternativas rejeitadas e "Ajustes Possíveis" |
| A implementação gradua | o porquê que **continua a explicar o código atual** migra para o doc de `docs/architecture/` dessa área, numa secção curta "Porquê está assim" |
| Fica para depois | `docs/plans/<tema>.md`, com prioridade |
| É uma preferência do utilizador sobre como trabalhar | memória do Claude, não docs |

Os docs de arquitetura são um espelho do código atual, **sem histórico** (regra do `CLAUDE.md`). Quando
uma decisão muda, reescreve-se a secção com a decisão nova e o porquê novo. O histórico fica no git, nas
mensagens de commit e nos ficheiros de implementação graduados.

## Formato do registo

Dentro do ficheiro de implementação (ou da secção "Porquê está assim" na graduação):

```markdown
### Decisão — <o que se decidiu, numa frase>

**Contexto:** <requisitos e restrições que pesaram>
**Decisão:** <o que se escolheu>
**Alternativas consideradas:**
- <opção> — <prós/contras> — rejeitada porque <motivo>
**Consequências:** <o que fica mais fácil, o que fica mais difícil, o que passa a ser preciso manter>
```

Na graduação, só migra o que ainda explica o código. Alternativas rejeitadas que já ninguém vai voltar a
propor ficam no histórico.

## Comentários no código

Comenta o **porquê**, nunca o quê: a intenção que não é óbvia, a armadilha conhecida, a razão de uma
ordem obrigatória. Código comentado e TODOs antigos apagam-se, porque o git guarda a história. Segue a
densidade de comentários que o código à volta já tem.

## Revisão do texto

Depois de acertar o conteúdo técnico, revê a escrita para quem a vai ler, sem mudar a decisão nem os
limites dela:
1. Marca o que tem de sobreviver: nomes, números e unidades, comandos, caminhos, links, condições,
   compromissos e incerteza. Confirma-os no código e assinala o que não conseguires confirmar.
2. Troca introduções genéricas, adjetivos promocionais e resumos repetidos pela informação concreta de
   que o leitor precisa. Uma afirmação sem suporte não se troca por um exemplo inventado nem por uma
   garantia mais forte.
3. Compara com o original e com as fontes. Repõe qualquer ressalva perdida e confirma que os comandos e
   exemplos continuam a funcionar.

Os textos para o utilizador vão em linguagem simples (ele não é programador). Os detalhes técnicos ficam
nos `.md` técnicos.

## Sinais de alerta

- Uma decisão de arquitetura sem porquê escrito em nenhum dos sítios da tabela.
- Uma secção de `docs/architecture/` que conta história ("agora passou a…") em vez do estado atual.
- O mesmo porquê repetido em vários docs: fica num e os outros apontam para ele.

**Concluído quando:** a decisão está no sítio certo da tabela, com contexto, alternativas e
consequências, e cada afirmação técnica foi conferida no código.
