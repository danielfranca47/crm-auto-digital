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
| `cliente-detalhe.html` | Atendente/balconista | Ficha do cliente: veículo (placa, marca/modelo/ano, km), fidelidade, histórico de peças |
| `agenda.html` | Dono da loja / atendente | Calendário mensal + lista do dia: retiradas, instalações, visitas técnicas |
| `regua-recompra.html` | Dono da loja | **Tela diferencial.** Lista de clientes com ciclo de peça vencido/vencendo, filtros, disparo de WhatsApp com preview da mensagem |
| `follow-up-center.html` | Dono da loja | Temperaturas: 🔥 Quente, 🌡 Morno, ❄ Frio, 🔁 Recompra |
| `playground.html` | Dono da loja (testando a IA) | Chat de teste da Lara (tema escuro do CRM) — não é o que o cliente vê, é a ferramenta interna de QA do agente |
| `ai-profile.html` | Dono da loja (configurando a IA) | Identidade da Lara em 3 camadas (Identidade, Conhecimento, Pipeline), shell visual Orion original |
| `whatsapp-cliente.html` | **Cliente final** | Mockup de celular: a tela real do WhatsApp do cliente recebendo o lembrete de recompra e fechando o agendamento |

`playground.html` e `whatsapp-cliente.html` mostram a mesma capacidade
(conversa com a Lara) de dois ângulos diferentes: um é a bancada de teste do
lojista, o outro é a experiência do cliente.

## Design system

### Tema CRM (`theme.css`)
Réplica dos tokens de `frontend-crm/src/index.css`: variáveis HSL
(`--background`, `--card`, `--primary`, `--border`, `--success`,
`--warning`, `--destructive`, gradientes, sombras). Tema dark por padrão;
existe suporte a `.light` na raiz `<html>` (toggle no topbar), igual ao
`ThemeContext` real. Fonte: Inter.

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
  `data-page` no `<body>`, toggle de sidebar mobile, toggle de tema
  (persistido em `localStorage`), helpers genéricos `openModal()`/`closeModal()`.
- **`regua-recompra.html`**: filtro client-side por status (`data-status`
  na `<tr>`), modal de disparo com preview de mensagem preenchido
  dinamicamente (`openDisparo(nome, peca)`).
- **`playground.html`**: conversa definida em array `CONVERSATION`, função
  `replayConversation()` re-renderiza com indicador de "digitando" e delay,
  simulando o agente respondendo em tempo real.
- **`whatsapp-cliente.html`**: mesmo padrão (`WA_CONVO` + `replayWA()`),
  com bolhas no estilo WhatsApp (verde/cinza, ✓✓ de leitura).
- **`ai-profile.html`**: troca de aba do subnav Orion (`switchTab()`) e
  drawers funcionais de exemplo (Nome do agente, Tom de voz) via
  `openDrawer()`/`closeDrawer()` — réplica do padrão `.o-drawer` real.

## Continuidade narrativa (dados mock)

Os dados são fixos (sem backend) mas consistentes entre páginas — o mesmo
cliente aparece com a mesma história em todas as telas, para a demo não
parecer um mosaico de exemplos soltos:

- **João Silva** — Honda Civic 2019, placa `BRA2E19`. Comprou filtro de óleo
  em 15/01/2026 (ciclo 6 meses → previsto 15/07/2026). Aparece no Kanban
  (coluna "Recompra agendada"), na régua de recompra, no perfil de cliente
  (`cliente-detalhe.html`), no Playground (pergunta sobre pastilha de freio)
  e no mockup do WhatsApp (recebe o lembrete proativo de recompra).
- Outros clientes recorrentes: Marcos Andrade (Strada, pastilha vencida),
  Patrícia Lima (Gol, bateria vencida há 97 dias), Eduardo Martins e Vanessa
  Oliveira (orçamentos "quentes" do dia), Beatriz Ramos e Rafael Costa
  (vendas fechadas hoje).
- Data de referência usada em todo o protótipo: **25/06/2026** (quinta-feira).

## Limitações conhecidas

- Sem persistência: nada digitado em formulários/modais é salvo; "Salvar"
  apenas fecha o modal/drawer.
- Sem roteamento por id: `clientes.html` → `cliente-detalhe.html` sempre
  abre o perfil de João Silva, independente do card clicado.
- Acessibilidade mínima: alguns inputs de filtro/busca não têm `<label>`
  associado (avisos de a11y no console, sem impacto visual ou funcional).
- Tema claro existe nos tokens (`theme.css`) mas não foi testado
  exaustivamente em todas as telas — o foco foi o dark, que é o padrão real
  da plataforma.

## Possíveis próximos passos

- Adicionar um segundo cenário de conversa em `whatsapp-cliente.html`
  (ex.: primeira compra, não só recompra).
- Parametrizar `cliente-detalhe.html` por query string para refletir o
  card clicado no Kanban.
- Tela de onboarding/setup inicial (import do catálogo de peças).
