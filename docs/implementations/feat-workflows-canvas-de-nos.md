# Canvas de nós para os workflows

**Branch:** (a criar)
**Status:** Aguardando Plan Mode
**Origem:** docs/discovery (investigação `workflows-canvas-de-nos`, graduada em 2026-10-03) — pedido do utilizador registado em `docs/discovery/levantamentos/2026-10-03-acompanhamento-pos-agendamento.md`, "Complemento do utilizador"
**Meta ligada:** M1 — Conquistar os primeiros clientes pagantes (clareza da configuração e impacto em demonstração); ligação indireta

---

## Motivação

O utilizador quer que os workflows (o Fluxo de Venda e os novos workflows por
gatilho) sejam editados numa tela ao estilo ManyChat — blocos soltos que se
arrastam, ligam com linhas e organizam na horizontal ou na vertical — em vez da
lista vertical fixa de hoje.

**Solução aprovada (ver "Opção B" abaixo):** um único canvas (React Flow) para
os dois tipos de workflow. Nos workflows por gatilho é canvas de verdade; no
Fluxo de Venda é uma nova vista do desenho atual, com as fases como molduras e
sem mexer no motor. Abre da esquerda para a direita, tem comando "Alinhar" e
mantém a lista como vista alternativa (telemóvel).

## Área do sistema

frontend-crm (Configurar Agente → Fluxo de Venda e novos workflows) /
backend-core (onde o desenho é guardado)

## Estado atual

- A tela atual é uma **lista vertical fixa**: uma secção por fase, blocos
  empilhados, edição em janelas (`CamadaFluxoVenda.tsx`, 1.922 linhas —
  `PhaseSection`, `BlockModal`, `RuleBuilderModal`, `BlockForm`).
- **Não existe nenhuma biblioteca de canvas/nós no projeto** — só `@dnd-kit`
  (arrastar em listas), em `frontend-crm/package.json`.
- O desenho guardado **não tem posições nem linhas**: é uma lista ordenada de
  blocos por fase, e é essa ordem que o motor executa
  (`docs/architecture/sales-flow.md`, "Armazenamento" e "Modelo sequencial de trigger").

---

## Evidência no código

**Como as "ligações" existem hoje, sem serem linhas.** No Fluxo de Venda atual, o
que liga um bloco a outro é implícito:

| Ligação | Como é guardada | Onde |
|---|---|---|
| Gatilho → ações que ele dispara | Posição: as ações vêm logo a seguir ao gatilho na lista | `sales-flow.md`, `last_trigger_active` |
| "Só depois de outro gatilho" | Campo `requires_block_id` | `types/agente.ts:90` |
| Ramificação → blocos de cada caminho | Campos `branch_group_id` / `branch_id` | `types/agente.ts:102-105` |
| Fase → fase seguinte | **Não é ligação do utilizador** — quem decide a fase é a IA Mãe a cada mensagem | `sales-flow.md`, "Pipeline por tipo de agente" |

O motor (`_evaluate_sales_flow_phases`, dentro de um arquivo de 6.078 linhas com
9 suítes de teste dedicadas ao Fluxo de Venda) percorre a lista por ordem e
depende dela para os bloqueios de avanço de fase. Fazê-lo "seguir linhas" em vez
de "seguir a ordem" seria reescrever a peça mais sensível do agente.

**Consequência para o desenho.** Há duas coisas diferentes a que se pode chamar
"canvas":

1. **Canvas como nova vista** — os blocos passam a ser nós que se arrastam
   livremente, com zoom, minimapa e escolha horizontal/vertical; as linhas são
   desenhadas a partir das ligações que já existem (tabela acima); ligar dois nós
   com o rato altera, por baixo, a ordem ou a dependência. O motor não muda.
2. **Canvas como modelo** — as linhas passam a ser a verdade, e o motor executa
   seguindo-as. Natural para os **novos** workflows por gatilho (que ainda não
   têm motor — ver [`feat-workflows-por-gatilho.md`](feat-workflows-por-gatilho.md),
   "Evidência", ponto 6); arriscado para o Fluxo de Venda.

**Telemóvel.** A tela atual do Fluxo de Venda não tem nenhuma adaptação a ecrã
pequeno. Um canvas livre é ainda mais difícil de usar num telemóvel do que uma lista.

## Como o mercado faz

| Referência | Como resolve | Aplica-se a nós? |
|---|---|---|
| **ManyChat — Flow Builder** | Canvas livre: duplo clique cria um passo, arrasta-se do ponto de ligação de um passo até outro para os ligar; "passo inicial" concentra os gatilhos; passos: enviar mensagem, ações, espera inteligente, condição, iniciar outra automação | **Sim** — é a referência pedida. Funciona bem lá porque cada automação é um fluxograma verdadeiro (um passo leva ao seguinte), como serão os nossos workflows por gatilho |
| **ManyChat — telemóvel e vista simples** | Mantém dois editores para a mesma automação, com botão para alternar: **Flow Builder** (canvas, com botão "Auto-Arrange" que arruma tudo) e **Basic Builder** (linear, mensagem a mensagem, indicado para automações simples). A app de telemóvel é pensada para conversas e acompanhamento: fluxos feitos na web podem ser abertos e editados, mas não criados do zero (exceto Instagram); a própria documentação recomenda computador para montar fluxos | **Sim** — confirma as duas decisões: manter uma vista em lista ao lado do canvas, e no telemóvel privilegiar ver/ajustar em vez de construir |
| **React Flow** (`@xyflow/react`) | Biblioteca aberta (licença MIT) para editores de nós em React: nós personalizados, ligações, zoom, minimapa; organização automática com `dagre`/`elkjs`, com direção configurável (de cima para baixo ou da esquerda para a direita); encaixe em grelha (`snapToGrid`); arrastar e ligar nós também em ecrã tátil. As "linhas-guia de alinhamento ao arrastar" só existem como exemplo pago — teríamos de as fazer nós | **Sim** — encaixa na nossa stack (React 18); orientação, arrumação automática e encaixe em grelha vêm praticamente prontos |
| **GoHighLevel** | Construtor de fluxos em árvore vertical: gatilhos no topo, passos e ramos Se/Senão para baixo — menos livre, mais guiado | **Parcial** — mostra a alternativa "guiada": menos liberdade, menos formas de o utilizador se perder |

## Opções avaliadas — aprovada a Opção B

### Opção A — Não fazer nada / manter a lista
- **Prós:** zero esforço; a lista é fácil num telemóvel.
- **Contras:** os novos workflows por gatilho têm esperas e condições com vários
  caminhos — numa lista ficam difíceis de ler; o utilizador pediu explicitamente
  o formato de nós.

### Opção B — Canvas para tudo, sem mexer no motor do Fluxo de Venda
- **O que é:** uma única tela de canvas (React Flow) usada pelos dois tipos de
  workflow:
  - **Workflows por gatilho (novos):** canvas de verdade — o utilizador cria nós,
    liga-os livremente, e o motor novo segue as linhas.
  - **Fluxo de Venda:** os mesmos nós e o mesmo visual, mas como nova vista do
    desenho atual. Cada fase aparece como uma **moldura** (a IA decide a passagem
    de fase, não uma linha); dentro da moldura o utilizador arrasta, liga e
    reorganiza, e isso traduz-se em ordem/dependência por baixo.
  - Em ambos: abre **da esquerda para a direita** (como o ManyChat), com
    liberdade total para o utilizador pousar os nós onde quiser; zoom, minimapa,
    botão **horizontal / vertical**, posições guardadas.
  - Comando **"Alinhar"**: sem desfazer a arrumação do utilizador, encaixa os nós
    na grelha do sistema — margens iguais, linhas e colunas direitas, espaçamento
    padrão. (Diferente do "Auto-Arrange" do ManyChat, que reposiciona tudo; a
    arrumação automática completa fica só para o primeiro desenho de um workflow
    que ainda não tem posições, como o Fluxo de Venda atual e os modelos prontos.)
  - A lista continua disponível como vista alternativa ("Lista | Canvas"). No
    telemóvel abre em lista por omissão — ver, ligar/desligar e editar textos; o
    canvas fica disponível para consulta com zoom. Montar um workflow do zero é
    tarefa de computador, como no ManyChat.
- **Prós:** entrega o visual pedido nos dois sítios; risco baixo (o motor do
  Fluxo de Venda e os seus testes ficam intactos); a vista em lista serve de rede
  de segurança durante a transição.
- **Contras:** no Fluxo de Venda a liberdade de **ligar** é limitada pelas fases
  (não dá para puxar uma linha de um bloco da Qualificação para um do
  Fechamento) — é preciso deixar isso claro na tela para não frustrar; duas
  vistas do mesmo desenho para manter.
- **Esforço:** ~3 fases
  1. Canvas dos workflows por gatilho (criar/ligar nós, horizontal/vertical,
     "Alinhar", guardar posições, lista no telemóvel) — é o editor da fase 2 de
     `feat-workflows-por-gatilho.md`, feito já neste formato em vez de em lista.
  2. Fluxo de Venda visto no canvas (molduras por fase, nós, linhas derivadas;
     clicar num nó abre a mesma janela de edição de hoje).
  3. Fluxo de Venda editável pelo canvas (criar, ligar, reordenar) + alternância
     "Lista | Canvas".

### Opção C — Canvas como modelo também no Fluxo de Venda
- **O que é:** o Fluxo de Venda passa a ser um fluxograma verdadeiro; o motor é
  reescrito para seguir as linhas.
- **Prós:** liberdade total e um único modelo mental.
- **Contras:** reescrever o motor de decisão e migrar o desenho de todas as
  contas; o Fluxo de Venda não é um fluxograma puro — a IA decide a fase a cada
  mensagem e os blocos de orientação influenciam o texto dela, não são "passos"
  que se executam em fila. Risco alto de regressão no que hoje funciona.
- **Esforço:** ~6 fases ou mais

## Porquê a Opção B

Dá o canvas livre onde ele é natural (workflows por gatilho, que
são fluxogramas de verdade) e o mesmo visual no Fluxo de Venda sem tocar no
motor. A limitação honesta: no Fluxo de Venda as fases continuam a ser molduras,
porque quem conduz a conversa de fase em fase é a IA — as linhas livres ficam
dentro de cada fase.

Sobre a prioridade: sozinho, o canvas não muda o que o cliente final recebe — o
que desbloqueia ligar a Lara são as mensagens (fase 1 dos workflows). Por isso a
ordem sugerida é: fase 1 dos workflows com formulários simples → canvas já como
editor dos workflows (fase 1 daqui) → Fluxo de Venda no canvas.

## Decisões do utilizador

Nenhuma pergunta pendente. Decisões (03/10/2026), já refletidas na Opção B:

| Tema | Decisão |
|---|---|
| Fases do Fluxo de Venda | Aceita como molduras fixas — os agentes já vêm com o seu modelo base, que é o Fluxo de Venda |
| Vista em lista | Mantida como alternativa ao canvas; telemóvel segue o padrão do ManyChat |
| Orientação | Da esquerda para a direita por omissão, com liberdade para pousar os nós |
| Alinhamento | Comando "Alinhar" que acerta margens e mantém linhas/colunas direitas no padrão do sistema |

## Em aberto

- Teste com um utilizador não técnico antes da fase 3, para confirmar que o
  canvas não piora a compreensão do Fluxo de Venda.
- Linhas-guia de alinhamento enquanto se arrasta um nó (além do comando
  "Alinhar") — não pedidas; avaliar o custo no Plan Mode.

## Próximo passo

Diagnóstico (Plan Mode) ainda não feito — seguir o Passo 0 de
`_guia-documentar-implementacao.md` antes de qualquer código. A fase 1 entra
junto com o editor dos workflows por gatilho (fase 2 de
[`feat-workflows-por-gatilho.md`](feat-workflows-por-gatilho.md)); as fases 2–3
(Fluxo de Venda no canvas) depois de os workflows estarem a funcionar com
clientes reais. Ordem completa nesse arquivo, secção "Próximo passo".

## Fontes

- [ManyChat — How to build a Manychat automation (Flow Builder)](https://help.manychat.com/hc/en-us/articles/14281166306332-How-to-build-a-Manychat-automation)
- [ManyChat — Smart Delay](https://help.manychat.com/hc/en-us/articles/14281197046812-Smart-Delay)
- [ManyChat — Manychat Mobile App](https://help.manychat.com/hc/en-us/articles/19858378137756-Manychat-Mobile-App)
- [ManyChat — Flow Builder: A Visual Editor (Basic Builder, Auto-Arrange)](https://manychat.com/blog/manychat-flow-builder-messenger-marketing/)
- [React Flow — The ReactFlow component (snapToGrid)](https://reactflow.dev/api-reference/react-flow)
- [xyflow — v11.5.0 Release (ligações em ecrã tátil)](https://xyflow.com/blog/react-flow-v-11-5)
- [React Flow — Pro Examples (helper lines)](https://reactflow.dev/pro/examples)
- [React Flow — Node-Based UIs in React](https://reactflow.dev/)
- [React Flow — Layouting overview (dagre, d3-hierarchy, elk)](https://reactflow.dev/learn/layouting/layouting)
- [xyflow/xyflow no GitHub (licença MIT)](https://github.com/xyflow/xyflow)
- [GoHighLevel Workflows: Triggers, Actions & Recipes](https://hlgrowthpartner.com/post/gohighlevel-workflows-triggers-actions-2026)
