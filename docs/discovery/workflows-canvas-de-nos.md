# Os workflows devem ser editados numa tela de nós ligados livremente?

**Status:** Pronta para decisão
**Origem:** pedido do utilizador em conversa (03/10/2026), na sequência de `levantamentos/2026-10-03-acompanhamento-pos-agendamento.md` — "alterar a visualização desses workflows para algo de ligar nós, mais livre, tanto na horizontal como na vertical"
**Meta ligada:** M1 — Conquistar os primeiros clientes pagantes (clareza da configuração e impacto em demonstração); ligação indireta
**Área do sistema:** frontend-crm (Configurar Agente → Fluxo de Venda e novos workflows) / backend-core (onde o desenho é guardado)

---

## Pergunta a responder

Vale a pena trocar a tela atual do Fluxo de Venda (lista vertical de blocos por
fase) por um canvas ao estilo ManyChat — blocos soltos que o utilizador arrasta,
liga com linhas e organiza na horizontal ou na vertical — e usar essa mesma tela
nos novos workflows por gatilho?

## O que já se sabe

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
   têm motor — ver [`jornada-pos-agendamento.md`](jornada-pos-agendamento.md),
   "Evidência", ponto 6); arriscado para o Fluxo de Venda.

**Telemóvel.** A tela atual do Fluxo de Venda não tem nenhuma adaptação a ecrã
pequeno. Um canvas livre é ainda mais difícil de usar num telemóvel do que uma lista.

## Como o mercado faz

| Referência | Como resolve | Aplica-se a nós? |
|---|---|---|
| **ManyChat — Flow Builder** | Canvas livre: duplo clique cria um passo, arrasta-se do ponto de ligação de um passo até outro para os ligar; "passo inicial" concentra os gatilhos; passos: enviar mensagem, ações, espera inteligente, condição, iniciar outra automação | **Sim** — é a referência pedida. Funciona bem lá porque cada automação é um fluxograma verdadeiro (um passo leva ao seguinte), como serão os nossos workflows por gatilho |
| **React Flow** (`@xyflow/react`) | Biblioteca aberta (licença MIT) para editores de nós em React: nós personalizados, ligações, zoom, minimapa; organização automática com `dagre`/`elkjs`, com direção configurável (de cima para baixo ou da esquerda para a direita) | **Sim** — encaixa na nossa stack (React 18); o botão "horizontal / vertical" e o "arrumar automaticamente" vêm praticamente prontos |
| **GoHighLevel** | Construtor de fluxos em árvore vertical: gatilhos no topo, passos e ramos Se/Senão para baixo — menos livre, mais guiado | **Parcial** — mostra a alternativa "guiada": menos liberdade, menos formas de o utilizador se perder |

## Opções de solução

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
  - Em ambos: arrastar livre, zoom, minimapa, botão **horizontal / vertical**,
    "arrumar automaticamente", posições guardadas. A lista atual continua
    disponível como vista alternativa ("Lista | Canvas"), sobretudo para telemóvel.
- **Prós:** entrega o visual pedido nos dois sítios; risco baixo (o motor do
  Fluxo de Venda e os seus testes ficam intactos); a vista em lista serve de rede
  de segurança durante a transição.
- **Contras:** no Fluxo de Venda a liberdade de **ligar** é limitada pelas fases
  (não dá para puxar uma linha de um bloco da Qualificação para um do
  Fechamento) — é preciso deixar isso claro na tela para não frustrar; duas
  vistas do mesmo desenho para manter.
- **Esforço:** ~3 fases
  1. Canvas dos workflows por gatilho (criar/ligar nós, horizontal/vertical,
     arrumar, guardar posições) — é o editor da fase 2 de
     `jornada-pos-agendamento.md`, feito já neste formato em vez de em lista.
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

## Recomendação

**Opção B.** Dá o canvas livre onde ele é natural (workflows por gatilho, que
são fluxogramas de verdade) e o mesmo visual no Fluxo de Venda sem tocar no
motor. A limitação honesta: no Fluxo de Venda as fases continuam a ser molduras,
porque quem conduz a conversa de fase em fase é a IA — as linhas livres ficam
dentro de cada fase.

Sobre a prioridade: sozinho, o canvas não muda o que o cliente final recebe — o
que desbloqueia ligar a Lara são as mensagens (fase 1 dos workflows). Por isso a
ordem sugerida é: fase 1 dos workflows com formulários simples → canvas já como
editor dos workflows (fase 1 daqui) → Fluxo de Venda no canvas.

## Pontuação RICE

| R | I | C | E | Score |
|---|---|---|---|---|
| 3 | 1 | 0.5 | 3 | **0.50** |

- **R = 3:** todos os utilizadores configuram workflows.
- **I = 1:** melhora a clareza e a apresentação do produto, mas não muda diretamente o que o agente faz (M1 indireto).
- **C = 0.5:** hipótese — não há medição de que o canvas seja mais fácil do que a lista para um dono de negócio sem perfil técnico.
- **E = 3:** três fases; a primeira coincide com o editor que os workflows por gatilho precisam de qualquer forma.

## Veredito proposto

**Implementations, em sequência** — a fase 1 entra junto com o editor dos
workflows por gatilho; as fases 2–3 (Fluxo de Venda no canvas) depois de os
workflows estarem a funcionar com clientes reais.

## Perguntas ao utilizador

1. **Lista como alternativa:** concorda em manter a vista em lista ao lado do
   canvas (botão "Lista | Canvas")? Sugestão: sim — no telemóvel o canvas é
   difícil de usar.
2. **Fases como molduras:** no Fluxo de Venda, aceita que as fases apareçam como
   molduras fixas (Recepção, Qualificação, Apresentação…) e que as linhas livres
   fiquem dentro de cada uma? A alternativa (Opção C) é bem mais cara e arriscada.
3. **Orientação inicial:** ao abrir, prefere da esquerda para a direita (como o
   ManyChat) ou de cima para baixo (como hoje)? O botão para alternar existe nos
   dois casos.

## Em aberto

- Comportamento em telemóvel (só ver, ou também editar no canvas) — decidir no
  Plan Mode da fase 1, depois da resposta à pergunta 1.
- Teste com um utilizador não técnico antes da fase 3, para confirmar que o
  canvas não piora a compreensão do Fluxo de Venda.

## Fontes

- [ManyChat — How to build a Manychat automation (Flow Builder)](https://help.manychat.com/hc/en-us/articles/14281166306332-How-to-build-a-Manychat-automation)
- [ManyChat — Smart Delay](https://help.manychat.com/hc/en-us/articles/14281197046812-Smart-Delay)
- [React Flow — Node-Based UIs in React](https://reactflow.dev/)
- [React Flow — Layouting overview (dagre, d3-hierarchy, elk)](https://reactflow.dev/learn/layouting/layouting)
- [xyflow/xyflow no GitHub (licença MIT)](https://github.com/xyflow/xyflow)
- [GoHighLevel Workflows: Triggers, Actions & Recipes](https://hlgrowthpartner.com/post/gohighlevel-workflows-triggers-actions-2026)
