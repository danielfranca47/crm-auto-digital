# Escrever para agentes

Vale para qualquer documento que um agente lê: uma skill, um comando slash, o `CLAUDE.md` ou um doc a que
eles apontam. A embalagem muda, a escrita não. O objetivo é o agente seguir o mesmo **processo** em todas
as execuções; não é produzir sempre o mesmo resultado.

## Apontadores

Um **apontador** é uma referência que está no contexto do agente e nomeia material que está fora dele,
dizendo quando ir buscá-lo. A `description` de uma skill é um apontador; uma linha do `CLAUDE.md` que
nomeia um doc também. É a **redação** do apontador, e não o destino, que decide quando o agente lá chega e
com que fiabilidade. Se um material essencial está atrás de um apontador mal escrito, primeiro afia-se a
redação; só se isso falhar se traz o material para dentro.

Um apontador faz duas coisas: diz o que é o material e lista os **ramos** que devem levar a ele (um ramo
é um caso distinto que o documento trata). Cada palavra de um apontador sempre carregado custa em todos os
turnos, por isso corta-se ainda mais do que o corpo:
- a palavra-chave vai à frente;
- um gatilho por ramo: sinónimos do mesmo ramo contam como um só;
- corta-se a identidade que o corpo já diz.

## As duas cargas

- **Carga de contexto:** o custo do que está sempre carregado (uma linha do `CLAUDE.md`, a descrição de
  uma skill). Gasta tokens e atenção em todos os turnos, quer dispare quer não.
- **Carga cognitiva:** o custo para o humano de saber que documentos existem e quando usar cada um. Não
  é para minimizar: é o preço de o humano decidir. Gasta-se onde o julgamento humano importa.

O que só se alcança por um apontador escapa à carga de contexto, ao preço da linha do apontador.

## Hierarquia da informação

Um documento tem **passos** (o que o agente faz, por ordem) e **referência** (definições, regras, factos
consultados quando preciso). Cada peça fica num destes níveis, conforme a urgência com que o agente
precisa dela:

1. **Passo no ficheiro:** o nível principal.
2. **Referência no ficheiro:** consultada quando preciso. Uma lista plana de regras é legítima.
3. **Referência à parte:** num ficheiro separado, alcançado por um apontador e carregado só quando ele
   dispara. Pode ser um ficheiro irmão ou um doc em qualquer sítio, como `docs/architecture/`.

A **divulgação progressiva** desce material na escada para o topo ficar legível. O teste mais limpo é o
dos ramos: fica no ficheiro o que todos os ramos usam e vai para trás de um apontador o que só alguns
usam. **Co-localização:** definição, regras e ressalvas de um conceito ficam juntas sob um título.
**Expansão excessiva** é a falha: um documento longo demais, mesmo que todas as linhas sejam válidas. A
cura é a escada.

## Passos e critério de conclusão

Cada passo acaba num **critério de conclusão**:
- **Clareza:** o agente distingue feito de não feito? Um limite vago ("perceber o problema") convida a
  acabar cedo, porque os passos seguintes à vista puxam por isso. Primeiro afia-se o critério; só se
  continuar vago e se se vir a pressa, separa-se a sequência noutro contexto (subagente ou passagem de
  testemunho).
- **Exigência:** "todos os modelos alterados contabilizados" obriga a mais trabalho do que "produz uma
  lista de alterações". Os critérios mais fortes são verificáveis e exaustivos.

## Quando dividir

Dividir gasta uma das cargas, por isso só se divide quando compensa:
- **Por sequência:** quando os passos seguintes tentam o agente a apressar o atual.
- **Por invocação** (skills): ver abaixo.

## Palavras-guia

Uma **palavra-guia** é um conceito compacto que o modelo já conhece (_lição_, _bala traçadora_,
_estreito_) e que ancora um comportamento com poucos tokens. Repete-se a palavra, nunca a frase. Prefere
palavras existentes a inventadas. Quando a mesma palavra vive nos teus prompts, docs e código, o agente
liga-os com mais fiabilidade. Procura frases repetidas que uma palavra substitua.

**Pedir pelo positivo:** proibir traz o comportamento proibido para o contexto. Diz o comportamento
pretendido ("escreve comentários de uma linha"). Uma proibição só vale como barreira que não se consegue
dizer pela positiva, e mesmo então junta-lhe o alvo positivo.

## Podar

- **Fonte única de verdade:** cada significado num só sítio. Duplicar custa manutenção e tokens.
- **O ambiente também é fonte de verdade** (configuração, estrutura de pastas, `--help`, o próprio
  código). Um doc que o repete é uma **cache** e só se justifica quando procurar é caro. Guarda em doc o
  que não se encontra a procurar: a convenção não escrita, o porquê, a armadilha.
- **Relevância:** cada linha ainda serve o que o documento faz? Sem poda, acumulam-se **sedimentos**:
  camadas desatualizadas que ficam porque acrescentar parece seguro e tirar parece arriscado.
- **Não-ops:** uma instrução que o modelo já cumpre por omissão não muda nada. Apaga a frase inteira. Uma
  palavra-guia fraca demais para vencer o comportamento por omissão também é um não-op; troca-a por uma
  mais forte.

## Skills: invocação e routers

- **Invocada pelo modelo** (com `description`): o agente dispara-a sozinho e outras skills alcançam-na.
  A descrição fica sempre carregada. Usa-a só quando o agente, ou outra skill, tem de a alcançar.
- **Invocada pelo utilizador** (`disable-model-invocation: true`): zero carga de contexto, mas é o humano
  que tem de se lembrar dela; a descrição passa a ser um resumo de uma linha para humanos.
- Uma skill nova à parte só compensa quando tem uma palavra de gatilho própria ou quando outra skill a
  tem de chamar. Material de vários casos do **mesmo** assunto fica numa skill com referências à parte
  (como esta).
- **Router:** uma skill que nomeia outras e diz quando usar cada uma. Neste projeto, a
  `diagnosticar-agente` encaminha para `agente-01/02/03`; as especialistas mantêm a descrição porque a
  router tem de as chamar.

## Neste projeto

- As skills e os comandos vivem em `.claude/skills/` e `.claude/commands/` e são versionados. Os factos
  do sistema vivem em `docs/architecture/` e as skills apontam para lá em vez de os copiar.
- Escreve em português de Portugal, com o vocabulário do produto (ex.: os nomes da página Tipos de
  Agentes para os agentes).
- Alterar `.claude/` ou `CLAUDE.md` é uma categoria que sobe: o merge precisa do "sim" do utilizador.

**Concluído quando:** cada apontador novo tem um gatilho por ramo, nenhum significado está duplicado
noutro documento, e cada frase passou o teste do não-op.
