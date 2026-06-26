# Protótipo Lara — AutoPeças

Protótipo navegável, estático, para apresentação comercial a uma loja de
autopeças (varejo independente). Demonstra como a Lara (agente de IA via
WhatsApp) preenche o gap que hoje só as grandes redes (AutoZone, O'Reilly,
NAPA) têm: cadastro de veículo por cliente, régua de recompra por ciclo de
peça, atendimento consultivo via WhatsApp e fidelização simples.

Não é uma feature do produto real — é um artefato de venda, isolado em
`prototipo-autopecas/`, fora da árvore das aplicações reais
(`backend-core/`, `backend-crm/`, `frontend-crm/` etc.). Reaproveita o design
system real da plataforma (tema CRM + Orion) para que a demo pareça o
produto de verdade.

## Como abrir

Sem build, sem servidor, sem dependências externas além de uma fonte do
Google Fonts (degrada bem offline — cai em Georgia/monospace do sistema).
Basta abrir `index.html` clicando duas vezes ou via `file://`:

```
file:///C:/crm-auto-digital/prototipo-autopecas/index.html
```

A navegação entre páginas é por link `<a href="...">` normal — qualquer
página pode ser aberta isoladamente.

## Estrutura de pastas

```
prototipo-autopecas/
├── README.md                     # este arquivo
├── index.html                    # Dashboard (home)
├── clientes.html                 # Kanban de clientes
├── cliente-detalhe.html          # Perfil do cliente + veículo + histórico
├── agenda.html                   # Retiradas / instalações / visitas técnicas
├── regua-recompra.html           # Painel de ciclo de recompra (diferencial)
├── follow-up-center.html         # Temperaturas de follow-up
├── playground.html               # Simulador interno de conversa com a IA
├── ai-profile.html               # Identidade/config da Lara (shell Orion)
├── whatsapp-cliente.html         # Mockup do celular do cliente final
└── assets/
    ├── css/
    │   ├── theme.css             # Tokens do tema CRM (dark/light) + utilitários
    │   ├── sidebar.css           # Sidebar de navegação
    │   ├── components.css        # Kanban, stat cards, chat, agenda, tabelas…
    │   └── orion.css             # Design system Orion (só ai-profile.html)
    └── js/
        ├── icons.js              # Dicionário de ícones SVG inline + renderIcons()
        └── app.js                # Sidebar ativa, toggle mobile/tema, modais
```

Cada página HTML é autocontida: inclui o mesmo bloco de sidebar duplicado
(não há include/template — `file://` não permite `fetch()` de fragmentos
locais sem servidor) e carrega os 3 CSS compartilhados (`theme`, `sidebar`,
`components`), exceto `ai-profile.html`, que troca `sidebar.css` por
`orion.css` porque a tela do agente tem layout próprio (sem sidebar),
réplica de `frontend-crm/src/styles/orion.css`.

## Mapa de páginas × persona

| Arquivo | Persona | O que demonstra |
|---|---|---|
| `index.html` | Dono da loja | Métricas do dia, funil, peças mais vendidas, recompra vencendo, estado da config. da Lara |
| `clientes.html` | Dono da loja / atendente | Kanban: Novo contato → Orçamento → Negociação → Venda fechada → Recompra agendada |
| `cliente-detalhe.html` | Atendente/balconista | Ficha do cliente: veículo (placa, marca/modelo/ano, km), fidelidade, histórico de peças. Conteúdo parametrizado por `?cliente=slug` (ver seção própria) |
| `agenda.html` | Dono da loja / atendente | Calendário mensal + lista do dia: retiradas, instalações, visitas técnicas |
| `regua-recompra.html` | Dono da loja | **Tela diferencial.** Lista de clientes com ciclo de peça vencido/vencendo, filtros, disparo de WhatsApp com preview da mensagem |
| `follow-up-center.html` | Dono da loja | Temperaturas: 🔥 Quente, 🌡 Morno, ❄ Frio, 🔁 Recompra |
| `playground.html` | Dono da loja (testando a IA) | Chat de teste da Lara (tema escuro do CRM) — não é o que o cliente vê, é a ferramenta interna de QA do agente |
| `ai-profile.html` | Dono da loja (configurando a IA) | Identidade da Lara em 3 camadas (Identidade, Conhecimento, Pipeline), shell visual Orion original |
| `whatsapp-cliente.html` | **Cliente final** | Mockup de celular com 2 cenários selecionáveis: "Recompra" e "Primeira compra" (ver seção própria) |

`playground.html` e `whatsapp-cliente.html` mostram a mesma capacidade
(conversa com a Lara) de dois ângulos diferentes: um é a bancada de teste do
lojista, o outro é a experiência do cliente.

## Design system

### Tema CRM (`theme.css`)
Réplica dos tokens de `frontend-crm/src/index.css`: variáveis HSL
(`--background`, `--card`, `--primary`, `--border`, `--success`,
`--warning`, `--destructive`, gradientes, sombras). Fonte: Inter.

Os tokens de tema claro (`.light`) continuam definidos no CSS, mas o botão
de alternância foi **removido do topbar de propósito** — a demo é
apresentada sempre no tema dark, para eliminar qualquer risco de algo
quebrar visualmente ao trocar de tema durante a apresentação ao vivo.

### Orion (`orion.css`, só em `ai-profile.html`)
Réplica de `frontend-crm/src/styles/orion.css`, escopado em `.orion-shell`.
Paleta hex própria (`--o-bg`, `--o-active` teal, `--o-warn`, `--o-hot`,
`--o-purple`), tipografia Playfair Display (display) + DM Mono (labels) +
Literata (corpo) — carregadas via Google Fonts no `theme.css`.

### Sidebar (`sidebar.css`)
Réplica de `AppSidebar.tsx`: grupos (Navegação / Cliente final / Conta),
item ativo destacado via `data-page` no `<body>` + JS (`app.js`).

### Componentes (`components.css`)
Kanban (`kanban-column`, `lead-card`), stat cards, funil de barras, tabelas
de dados, chat bubbles (playground), mockup de celular WhatsApp
(`phone-frame`, `wa-bubble`), calendário simplificado da agenda, ficha de
veículo (`vehicle-card`, `plate`).

## Ícones

Sem dependência de `lucide-react` (não há bundler). `icons.js` define um
dicionário `ICONS = { nome: '<svg>…</svg>' }` no estilo lucide (24×24,
stroke `currentColor`) e uma função `renderIcons()` que substitui qualquer
`<span data-icon="nome">` pelo SVG correspondente, rodando em
`DOMContentLoaded` e reaplicada manualmente após render dinâmico (chat do
playground/WhatsApp).

## Interatividade (JS)

- **`app.js`** (todas as páginas): marca o link ativo da sidebar via
  `data-page` no `<body>`, toggle de sidebar mobile, helpers genéricos
  `openModal()`/`closeModal()`. (O toggle de tema claro/escuro foi removido
  do topbar — ver "Design system" acima — mas o código de suporte a tema
  permanece em `app.js`/`theme.css` sem uso, inofensivo.)
- **`regua-recompra.html`**: filtro client-side por status (`data-status`
  na `<tr>`), modal de disparo com preview de mensagem preenchido
  dinamicamente (`openDisparo(nome, peca)`).
- **`cliente-detalhe.html`**: lê `?cliente=slug` da query string e
  renderiza toda a ficha (dados, veículo, fidelidade, histórico) a partir
  do objeto `CLIENTES` — ver seção "Perfis de cliente parametrizados".
- **`playground.html`**: conversa definida em array `CONVERSATION`, função
  `replayConversation()` re-renderiza com indicador de "digitando" e delay,
  simulando o agente respondendo em tempo real.
- **`whatsapp-cliente.html`**: dois cenários (`SCENARIOS.recompra` /
  `SCENARIOS.primeira`) selecionáveis por pill no topo; `selectScenario()`
  troca conversa + bullets explicativos, `replayWA()` reproduz a conversa
  do cenário ativo com indicador de "digitando" — ver seção própria.
- **`ai-profile.html`**: troca de aba do subnav Orion (`switchTab()`) e
  drawers funcionais de exemplo (Nome do agente, Tom de voz) via
  `openDrawer()`/`closeDrawer()` — réplica do padrão `.o-drawer` real.

## Perfis de cliente parametrizados (`cliente-detalhe.html`)

A ficha do cliente não é mais fixa em João Silva: lê o parâmetro
`?cliente=slug` da URL e busca os dados no objeto `CLIENTES` (definido no
próprio `cliente-detalhe.html`). Cada card do Kanban em `clientes.html` já
linka para o slug correto (`cliente-detalhe.html?cliente=marcos`, etc.).
Slug desconhecido ou ausente cai no padrão (`joao`).

| Slug | Cliente | Veículo | Situação |
|---|---|---|---|
| `joao` | João Silva | Honda Civic 2019 · `BRA2E19` | Perfil completo de referência — 4 compras, recompra de filtro de óleo prevista 15/07/2026 |
| `marcos` | Marcos Andrade | Fiat Strada 2021 · `STR2A21` | Pastilha de freio vencida há 17 dias, em negociação |
| `patricia` | Patrícia Lima | VW Gol 2017 · `GOL4P17` | Bateria vencida há 97 dias — voltou a contatar com bateria fraca |
| `lucas`, `eduardo`, `vanessa`, `camila`, `beatriz`, `rafael`, `fernanda` | — | — | Perfis leves (1–2 compras) para que todo card do Kanban abra uma ficha real, sem nenhum link morto durante a demo |

`lucas` é o único caso de cliente sem nenhuma compra ainda — serve para
mostrar o estado vazio da tabela de histórico ("Nenhuma compra registrada
ainda — cliente em prospecção").

## Continuidade narrativa (dados mock)

Os dados são fixos (sem backend) mas consistentes entre páginas — o mesmo
cliente aparece com a mesma história em todas as telas, para a demo não
parecer um mosaico de exemplos soltos:

- **João Silva** — Honda Civic 2019, placa `BRA2E19`. Comprou filtro de óleo
  em 15/01/2026 (ciclo 6 meses → previsto 15/07/2026). Aparece no Kanban
  (coluna "Recompra agendada"), na régua de recompra, no perfil de cliente
  (`cliente-detalhe.html?cliente=joao`), no Playground (pergunta sobre
  pastilha de freio) e no cenário "Recompra" do mockup de WhatsApp.
- **Carlos Mendes** — Fiat Strada 2021, placa `QRS3F45`. Cliente novo, sem
  cadastro prévio — só existe no cenário "Primeira compra" do mockup de
  WhatsApp, perguntando sobre amortecedor dianteiro.
- Outros clientes recorrentes: Marcos Andrade (Strada, pastilha vencida),
  Patrícia Lima (Gol, bateria vencida há 97 dias), Eduardo Martins e Vanessa
  Oliveira (orçamentos "quentes" do dia), Beatriz Ramos e Rafael Costa
  (vendas fechadas hoje) — todos com ficha própria em `cliente-detalhe.html`.
- Data de referência usada em todo o protótipo: **25/06/2026** (quinta-feira).

## Limitações conhecidas

- Sem persistência: nada digitado em formulários/modais é salvo; "Salvar"
  apenas fecha o modal/drawer. O modal "Editar veículo" em
  `cliente-detalhe.html` é pré-preenchido com os dados do cliente atual,
  mas salvar não altera a ficha.
- Acessibilidade mínima: alguns inputs de filtro/busca não têm `<label>`
  associado (avisos de a11y no console, sem impacto visual ou funcional).
- Tema fixo em dark: o toggle de tema claro foi removido do topbar de
  propósito para a apresentação (ver "Design system"); os tokens `.light`
  continuam no CSS mas não são exercitados em nenhuma tela.

## Possíveis próximos passos

- Tela de onboarding/setup inicial (import do catálogo de peças).
- Persistir as escolhas dos modais (Editar veículo / Registrar compra) em
  `localStorage` para a demo "lembrar" o que foi feito durante a apresentação.
