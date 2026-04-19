## Protótipo visual de referência

O arquivo [`docs/admin-dashboard-prototype.jsx`](admin-dashboard-prototype.jsx) contém um protótipo funcional em React que serve como referência visual e de UX para o desenvolvimento do painel.

**O que o protótipo cobre:**
- Layout sidebar + main com navegação entre as 7 seções
- Design system: paleta dark, tokens CSS, tipografia
- Seção Dashboard: cards de KPIs, alertas ativos, tabela de instâncias com tabs de filtro, pipeline de agentes com expand/collapse, gráfico MRR e funil de onboarding
- Dados mock que ilustram os campos esperados de cada endpoint

**Como usar na implementação:**
- Usar como especificação visual de cada componente ao construir as páginas em `frontend-admin/src/pages/`
- Os `MOCK_*` mostram a estrutura de dados esperada de cada endpoint admin
- **Design:** componentes shadcn/ui e Tailwind instalados no `frontend-admin` — não instalar novas bibliotecas de UI. O protótipo usa CSS-in-JS próprio apenas para facilitar a visualização; na implementação real, traduzir para as primitivas existentes (`Card`, `Badge`, `Button` etc. de `src/components/ui/`).

---

## Mudança arquitetural: frontend-admin/ independente

> **Introduzida em:** branch `etapa-8-5-ajustes`
> **Motivo:** bug crítico que impedia o login admin

### O problema

Ao acessar `/saas-admin` no `frontend-crm`, o `LeadsContext` — inicializado no topo da árvore de componentes, fora das rotas admin — disparava `GET /api/leads/` imediatamente via `useEffect`. Como o usuário visitando `/saas-admin` não tem token de usuário normal (só tem token de admin, ou não tem nenhum ainda), o backend retornava `401 Unauthorized`. O handler global de erros em `useApiErrorHandler.ts` capturava esse 401 e redirecionava para `/login` (login de usuário normal), **antes** que o `AdminGuard` tivesse chance de redirecionar para `/saas-admin/login`.

**Efeito prático:** era impossível acessar o painel admin a não ser que o operador estivesse simultaneamente logado como usuário normal — o que não faz sentido operacionalmente.

### A solução

Criação do serviço `frontend-admin/` como um app React/Vite **completamente independente** do `frontend-crm`. Benefícios:

- **Sem `LeadsContext`**, sem qualquer contexto de usuário normal — nenhuma chamada espúria a `/api/leads/`
- **Sem handler de 401 que redireciona para `/login`** do CRM
- `AdminGuard` usa `<Navigate replace to="/login" />` (React Router) em vez de `window.location.replace` — elimina a race condition de render
- Porta separada (5174 vs 5173), deploy e ciclo de vida independentes
- Isolamento total entre as sessões de usuário e de admin — o browser pode ter os dois abertos simultaneamente sem interferência

### O que mudou em relação à documentação anterior

| Aspecto | Antes (dentro do frontend-crm) | Agora (frontend-admin/) |
|---|---|---|
| Localização das páginas | `frontend-crm/src/pages/SaaSAdmin/` | `frontend-admin/src/pages/` |
| URL de login | `http://localhost:8080/saas-admin/login` | `http://localhost:5174/login` |
| Rotas das páginas | `/saas-admin`, `/saas-admin/usuarios`, … | `/`, `/usuarios`, … |
| Porta dev | 8080 (compartilhada com o CRM) | **5174** (exclusiva) |
| Serviço de API | `api.admin.*` em `frontend-crm/src/services/api.ts` | `api.*` em `frontend-admin/src/services/api.ts` |
| Dependências | Reutilizava deps do `frontend-crm` | `package.json` próprio |
| `AdminGuard` | `window.location.replace("/saas-admin/login")` | `<Navigate replace to="/login" />` |
| Conflito de auth | Sim — `LeadsContext` disparava 401 | Não — zero contexto de usuário |

As páginas no `frontend-crm/src/pages/SaaSAdmin/` continuam existindo mas **não são mais o canal de acesso operacional**. Podem ser removidas em uma próxima limpeza após validação em produção.

---

## Objetivo

Implementar uma área administrativa isolada, acessível apenas pelo operador da plataforma (o dono do SaaS), que permita monitorar e controlar todos os aspectos do sistema sem depender de acesso direto ao banco de dados ou ao terminal.

A área de admin é a interface central de operação do dia a dia: ver quem está online, quais instâncias caíram, quanto está sendo gerado de receita, e agir diretamente sobre usuários, planos e configurações — tudo em um único painel autenticado, separado do fluxo normal de login dos clientes.

### Páginas previstas

**1. Dashboard** — Visão geral rápida. KPIs principais (usuários, instâncias online, MRR, churn), alertas ativos que precisam de ação imediata, e snapshot do funil de onboarding. É a primeira tela que você abre no dia.

**2. Instâncias** — Controle das conexões WhatsApp via Uazapi. Listar todas as instâncias, ver status em tempo real (online/offline/alerta), forçar reconexão remota, enviar notificação ao usuário pedindo reconexão, e ver logs de desconexão com histórico.

**3. Usuários** — Gestão completa de cada cliente. Lista com filtros por plano e status, visualização do perfil (plano, consumo, histórico de ações), capacidade de impersonar (ver o sistema como o usuário vê), e gerenciar plano/permissões manualmente.

**4. Agentes e prompts** — Visualização ao vivo da configuração de todos os agentes do sistema, lida diretamente do estado atual do backend (não estática). Os dados refletem o que está configurado no momento da consulta.

*Formato visual:* cards por tipo de agente (`agent_mode`), cada card expansível revelando um fluxo em colunas — uma coluna por estágio (`qualificação → apresentação → negociação → fechamento`), com o texto do prompt daquele estágio exibido abaixo do título. Ao clicar em um estágio, abre um drawer com o prompt completo e os metadados.

*Visão por usuário:* ao selecionar um usuário, a mesma estrutura de fluxo é exibida com os valores do AI profile daquele usuário sobrepostos aos padrões — destacando campos personalizados com badge ou cor distinta.

*Campos capturados pelo painel (contrato):* ver [`docs/admin-agents-contract.md`](admin-agents-contract.md).

**5. Crescimento** — Métricas de saúde do negócio. Churn rate por cohort mensal, funil trial → conversão, taxa de conclusão do onboarding, feature adoption, e NPS/satisfação.

**6. Financeiro** — Receita e cobrança. MRR e ARR com evolução mensal, receita segmentada por plano, consumo excedente, inadimplência com status de pagamento, e estimativas de LTV e CAC.

**7. Configurações** — Controle do sistema. Feature flags (ligar/desligar funcionalidades por plano ou usuário), rate limiting, audit log, gestão de API keys e webhooks, e broadcast de avisos/manutenções.

---

## Autenticação do Admin

### Decisão: `ADMIN_SECRET` no `.env` do backend-core

**Como funciona:**
1. `backend-core/.env` define `ADMIN_SECRET=<segredo-forte>`.
2. O admin acessa `http://localhost:5174/login` e digita o segredo.
3. O frontend faz `POST http://localhost:8001/admin/login`. O backend valida e retorna um JWT com `role: admin` e validade de 8 horas.
4. Esse JWT é armazenado no `sessionStorage` (expira ao fechar o browser).
5. Todas as rotas `/admin/*` nos backends verificam esse JWT.

**Vantagens:**
- Zero banco de dados para admins.
- Rotação simples: editar o `.env` e reiniciar o `backend-core`.
- JWT permite expiração e logout limpo.
- Separado do `CORE_SERVICE_TOKEN` — cada segredo tem um propósito único.

**Limitações aceitáveis no MVP:**
- Apenas um admin (sem multi-admin).
- Sem 2FA.
- Sem audit log de quem fez login.

---

## Estrutura atual do frontend-admin/

```
frontend-admin/
├── .env                          # VITE_CORE_BASE e VITE_CRM_BASE
├── package.json                  # deps próprias (react-router, tanstack/query, radix…)
├── vite.config.ts                # porta 5174, alias @/
├── tsconfig.app.json
└── src/
    ├── main.tsx
    ├── App.tsx                   # BrowserRouter + QueryClient + rotas
    ├── index.css                 # tailwind + reset
    ├── lib/
    │   ├── admin-token.ts        # persist/read/clear/isValid do JWT admin
    │   └── utils.ts              # cn() helper
    ├── components/
    │   ├── AdminGuard.tsx        # <Navigate replace to="/login"> se token inválido
    │   ├── AdminLayout.tsx       # sidebar + <Outlet>
    │   └── ui/                   # accordion, badge, button, card, command,
    │                             # dialog, input, popover, scroll-area, sheet,
    │                             # skeleton, toast, toaster
    ├── hooks/
    │   └── use-toast.ts
    ├── services/
    │   └── api.ts                # coreGet/corePost/corePatch/crmGet com JWT injetado
    └── pages/
        ├── AdminLogin.tsx
        ├── AdminDashboard.tsx
        ├── AdminUsers.tsx
        ├── AdminInstances.tsx
        ├── AdminAgents.tsx
        ├── AdminGrowth.tsx       # placeholder — Fase 5
        ├── AdminFinancial.tsx    # placeholder — Fase 5
        └── AdminSettings.tsx    # placeholder — Fase 4d
```

### Endpoints consumidos pelo frontend-admin

| Método | Endpoint | Backend | Página |
|---|---|---|---|
| `POST` | `/admin/login` | core:8001 | AdminLogin |
| `GET` | `/admin/stats` | core:8001 | AdminDashboard |
| `GET` | `/admin/instances` | core:8001 | AdminDashboard, AdminInstances |
| `POST` | `/admin/instances/{id}/reconnect` | core:8001 | AdminInstances |
| `GET` | `/admin/users` | core:8001 | AdminUsers |
| `PATCH` | `/admin/users/{id}/extensions` | core:8001 | AdminUsers |
| `GET` | `/admin/agents/overview` | crm:8000 | AdminAgents |
| `GET` | `/admin/agents/users` | crm:8000 | AdminAgents |
| `GET` | `/admin/agents/users/{id}` | crm:8000 | AdminAgents |

---

## Plano de ação

### Fase 1 — Fundação de auth admin
- [x] `backend-core`: variável `ADMIN_SECRET` lida do env
- [x] `backend-core`: `POST /admin/login` — valida segredo, emite JWT (`role: admin`, 8h)
- [x] `backend-core`: middleware `require_admin` que valida esse JWT
- [x] `frontend-admin`: `AdminLogin.tsx` — tela de login, armazena JWT no `sessionStorage`
- [x] `frontend-admin`: `AdminGuard` — redireciona para `/login` se não houver JWT admin válido
- [x] `frontend-admin`: `AdminLayout.tsx` — sidebar com links para as 7 seções + botão de logout

### Fase 2 — Migrar o que existia no frontend-crm
- [x] `AdminUsers.tsx`: gestão de usuários + extensões, autenticando via JWT admin
- [x] `backend-core`: `GET /admin/users` protegida por `require_admin`
- [x] `backend-core`: `PATCH /admin/users/{user_id}/extensions` protegida por `require_admin`

### Fase 3 — Dashboard e Instâncias
- [x] `backend-core`: `GET /admin/stats`
- [x] `backend-core`: `GET /admin/instances`
- [x] `backend-core`: `POST /admin/instances/{id}/reconnect`
- [x] `AdminDashboard.tsx`: KPIs + alertas de instâncias offline
- [x] `AdminInstances.tsx`: tabela com status em tempo real, ação de reconexão

### Fase 4 — Agentes e Configurações

#### 4a — Endpoints de agentes
- [x] `backend-crm`: `GET /admin/agents/overview`
- [x] `backend-crm`: `GET /admin/agents/users`
- [x] `backend-crm`: `GET /admin/agents/users/{user_id}`

#### 4b — AdminAgents.tsx
- [x] Cards por `agent_mode` com Accordion, fluxo em colunas de estágios
- [x] Sheet (drawer lateral) com prompt completo ao clicar em estágio
- [x] Combobox de seleção de usuário com diff de AI profile

#### 4c — Contrato e proteção contra mudanças futuras
- [x] `docs/admin-agents-contract.md` com contrato completo de campos
- [x] Regra adicionada ao `CLAUDE.md`

#### 4d — Configurações
- [ ] `AdminSettings.tsx`: feature flags por plano/usuário (integra com `enabled_extensions`)

### Fase 5 — Crescimento e Financeiro
*Requerem dados históricos acumulados.*

- [ ] `AdminGrowth.tsx`: churn, funil trial→conversão, feature adoption
- [ ] `AdminFinancial.tsx`: MRR/ARR, consumo excedente, inadimplência

---

## Como acessar o painel admin

### Pré-requisitos

Quatro serviços precisam estar rodando:

| Serviço | Porta | Comando |
|---|---|---|
| `backend-core` | 8001 | `cd backend-core && uvicorn app.main:app --port 8001` |
| `backend-crm` | 8000 | `cd backend-crm && uvicorn app:app --port 8000` |
| `frontend-crm` | 5173 | `cd frontend-crm && npm run dev` *(opcional para uso admin)* |
| **`frontend-admin`** | **5174** | `cd frontend-admin && npm run dev` |

> O `backend-core` deve subir antes do `backend-crm`.
> O `frontend-crm` só é necessário para operação dos usuários normais — não é dependência do admin.

---

### Configurar a senha (uma vez)

A senha do admin é uma variável de ambiente no `backend-core`. Verifique ou defina em `backend-core/.env`:

```env
ADMIN_SECRET=<seu-segredo-forte>
```

Não há usuário de banco de dados — o `ADMIN_SECRET` é a única credencial. Para trocar a senha: edite o `.env` e reinicie o `backend-core`.

---

### Fazer login

1. Abra no browser: **`http://localhost:5174/login`**
2. Digite o valor de `ADMIN_SECRET` definido no `.env` do `backend-core`.
3. Clique em **Entrar**.

O frontend envia o segredo para `POST http://localhost:8001/admin/login`. Se correto, o backend-core retorna um JWT com `role: admin` e validade de **8 horas**. Esse JWT é armazenado no `sessionStorage` do browser (não persiste ao fechar a aba/janela).

---

### Navegar pelo painel

Após o login, você é redirecionado para `/` (Dashboard). A sidebar à esquerda dá acesso a todas as seções:

| Rota (frontend-admin) | Seção | Status |
|---|---|---|
| `/` | Dashboard — KPIs e alertas | ✅ Implementado |
| `/instancias` | Instâncias WhatsApp | ✅ Implementado |
| `/usuarios` | Usuários e extensões | ✅ Implementado |
| `/agentes` | Agentes e Prompts ao vivo | ✅ Implementado |
| `/crescimento` | Crescimento e métricas | 🔜 Fase 5 |
| `/financeiro` | Financeiro e receita | 🔜 Fase 5 |
| `/configuracoes` | Configurações e feature flags | 🔜 Fase 4d |

---

### Logout e expiração

- **Logout manual:** botão "Sair" no rodapé da sidebar — limpa o JWT do `sessionStorage` e redireciona para `/login`.
- **Expiração automática:** o JWT expira em 8 horas. Ao tentar acessar qualquer rota protegida com token expirado, o `AdminGuard` redireciona automaticamente para `/login`.
- **Fechar o browser:** o `sessionStorage` é limpo automaticamente — o próximo acesso exige novo login.

---

### Troubleshooting

| Problema | Causa provável | Solução |
|---|---|---|
| "Admin não configurado" no login | `ADMIN_SECRET` não definido no `.env` | Adicionar `ADMIN_SECRET=...` em `backend-core/.env` e reiniciar |
| "Credenciais inválidas" | Segredo digitado errado | Verificar o valor exato em `backend-core/.env` (case-sensitive) |
| Tela branca / redireciona para `/login` | JWT expirado ou `sessionStorage` limpo | Fazer login novamente em `http://localhost:5174/login` |
| Erro ao carregar dados de agentes | `backend-crm` offline ou token admin inválido para o CRM | Verificar se o `backend-crm` está rodando na porta 8000 |
| Dados de stats/instâncias não carregam | `backend-core` offline | Verificar se o `backend-core` está rodando na porta 8001 |
| Acessa `localhost:8080/saas-admin` e cai no login do CRM | Rota antiga no `frontend-crm` — bug que motivou a migração | Usar `localhost:5174/login` (frontend-admin) |
