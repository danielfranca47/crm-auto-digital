## Protótipo visual de referência

O arquivo [`docs/admin-dashboard-prototype.jsx`](admin-dashboard-prototype.jsx) contém um protótipo funcional em React que serve como referência visual e de UX para o desenvolvimento do painel.

**O que o protótipo cobre:**
- Layout sidebar + main com navegação entre as 7 seções
- Design system: paleta dark, tokens CSS, tipografia
- Seção Dashboard: cards de KPIs, alertas ativos, tabela de instâncias com tabs de filtro, pipeline de agentes com expand/collapse, gráfico MRR e funil de onboarding
- Dados mock que ilustram os campos esperados de cada endpoint

**Como usar na implementação:**
- Usar como especificação visual de cada componente ao construir as páginas em `SaaSAdmin/`
- Os `MOCK_*` mostram a estrutura de dados esperada de cada endpoint admin
- **Design:** dar preferência aos componentes shadcn/ui e Tailwind já instalados no `frontend-crm` — não instalar novas bibliotecas de UI. O protótipo usa CSS-in-JS próprio apenas para facilitar a visualização; na implementação real, traduzir para as primitivas existentes (`Card`, `Badge`, `Button`, `Table` etc. de `src/components/ui/`).

---

## Objetivo

Implementar uma área administrativa isolada dentro do `frontend-crm`, acessível apenas pelo operador da plataforma (o dono do SaaS), que permita monitorar e controlar todos os aspectos do sistema sem depender de acesso direto ao banco de dados ou ao terminal.

A área de admin é a interface central de operação do dia a dia: ver quem está online, quais instâncias caíram, quanto está sendo gerado de receita, e agir diretamente sobre usuários, planos e configurações — tudo em um único painel autenticado, separado do fluxo normal de login dos clientes.

### Páginas previstas

**1. Dashboard** — Visão geral rápida. KPIs principais (usuários, instâncias online, MRR, churn), alertas ativos que precisam de ação imediata, e snapshot do funil de onboarding. É a primeira tela que você abre no dia.

**2. Instâncias** — Controle das conexões WhatsApp via Uazapi. Listar todas as instâncias, ver status em tempo real (online/offline/alerta), forçar reconexão remota, enviar notificação ao usuário pedindo reconexão, e ver logs de desconexão com histórico.

**3. Usuários** — Gestão completa de cada cliente. Lista com filtros por plano e status, visualização do perfil (plano, consumo, histórico de ações), capacidade de impersonar (ver o sistema como o usuário vê), e gerenciar plano/permissões manualmente.

**4. Agentes e prompts** — Overview hierárquico dos 3 modelos de agentes. Pipeline visual mostrando os estágios de cada agente, os prompts padrão de cada estágio, e a visão por usuário mostrando como o AI profile e o treinamento no playground alteraram os prompts em relação ao padrão.

**5. Crescimento** — Métricas de saúde do negócio. Churn rate por cohort mensal, funil trial → conversão, taxa de conclusão do onboarding (onde os usuários desistem), feature adoption (quais funcionalidades são usadas de fato), e NPS/satisfação.

**6. Financeiro** — Receita e cobrança. MRR e ARR com evolução mensal, receita segmentada por plano, consumo excedente (quem ultrapassou a franquia no modelo híbrido), inadimplência com status de pagamento, e estimativas de LTV e CAC.

**7. Configurações** — Controle do sistema. Feature flags (ligar/desligar funcionalidades por plano ou usuário), rate limiting, audit log (quem fez o quê e quando), gestão de API keys e webhooks, e broadcast de avisos/manutenções para os clientes.

---

## Autenticação do Admin — Análise e Decisão (MVP)

### Opções consideradas

| Método | Complexidade | Privacidade | Adequação MVP |
|---|---|---|---|
| `ADMIN_TOKEN` no `.env` (token estático) | Mínima | Alta | ✅ Ideal |
| `ADMIN_EMAIL` + `ADMIN_PASSWORD` no `.env` | Baixa | Alta | ✅ Viável |
| Reutilizar `CORE_SERVICE_TOKEN` | Mínima | Alta | ⚠️ Não recomendado¹ |
| Usuário admin no banco (flag `is_admin`) | Média | Alta | ❌ Excessivo para MVP |
| OAuth / SSO externo | Alta | Alta | ❌ Excessivo para MVP |

¹ O `CORE_SERVICE_TOKEN` é um segredo de comunicação server-to-server. Expô-lo no frontend (mesmo que colado manualmente) mistura responsabilidades e cria risco se o token precisar ser rotacionado.

### Decisão recomendada para MVP: `ADMIN_SECRET` no `.env`

**Como funciona:**
1. No `backend-core/.env`, uma variável `ADMIN_SECRET=<segredo-forte>` define a senha do admin.
2. O frontend tem uma tela de login simples (fora das rotas autenticadas normais). O admin digita o segredo.
3. O frontend faz `POST /admin/login` com o segredo. O backend valida contra o env var e retorna um JWT de curta duração com claim `role: admin`.
4. Esse JWT é armazenado no `sessionStorage` (não `localStorage` — expira ao fechar o browser).
5. Todas as rotas `/admin/*` no backend verificam esse JWT e o claim `role: admin`.

**Vantagens:**
- Zero banco de dados: não há tabela de admins para criar ou manter.
- Rotação simples: mudar o env var e reiniciar o serviço.
- Separado do `CORE_SERVICE_TOKEN` — cada segredo tem um propósito único.
- JWT permite expiração e logout limpo.

**Limitações aceitáveis no MVP:**
- Apenas um admin (sem multi-admin).
- Sem 2FA.
- Sem audit log de quem fez login (pode ser adicionado depois).

---

## Estado atual da codebase (diagnóstico)

### O que já existe em `SaaSAdmin/`

| Arquivo | O que faz | Encaixa em qual seção do painel |
|---|---|---|
| `Subscriptions.tsx` | Lista usuários + toggles de `enabled_extensions` | Seção 3 — Usuários |
| `Plans.tsx` | Gestão de planos SaaS | Seção 7 — Configurações |
| `AiAgentConfig.tsx` | Configuração de agentes | Seção 4 — Agentes e Prompts |

**Problema atual:** `Subscriptions.tsx` autentica colando o `CORE_SERVICE_TOKEN` manualmente — padrão que será substituído pelo fluxo de login com `ADMIN_SECRET`.

### O que precisa ser criado

**Backend (`backend-core`):**
- `POST /admin/login` — valida `ADMIN_SECRET`, retorna JWT admin.
- Middleware `require_admin` para proteger rotas `/admin/*`.
- Endpoints admin para cada seção (listados no plano abaixo).

**Frontend (`frontend-crm/src/pages/SaaSAdmin/`):**
- `AdminLogin.tsx` — tela de login com campo de senha.
- `AdminLayout.tsx` — layout com sidebar das 7 seções.
- `AdminDashboard.tsx` — seção 1.
- `AdminInstances.tsx` — seção 2.
- `AdminUsers.tsx` — seção 3 (absorve o que está em `Subscriptions.tsx`).
- `AdminAgents.tsx` — seção 4.
- `AdminGrowth.tsx` — seção 5.
- `AdminFinancial.tsx` — seção 6.
- `AdminSettings.tsx` — seção 7.

**Roteamento:** rota `/saas-admin/*` fora do `AuthGuard` normal, com seu próprio `AdminGuard` que verifica o JWT admin no `sessionStorage`.

---

## Plano de ação

### Fase 1 — Fundação de auth admin
*Pré-requisito de tudo. Sem isso o painel não tem segurança.*

- [ ] `backend-core`: variável `ADMIN_SECRET` lida do env.
- [ ] `backend-core`: `POST /admin/login` — valida segredo, emite JWT com `role: admin` e expiração de 8h.
- [ ] `backend-core`: middleware `require_admin` que valida esse JWT.
- [ ] `frontend-crm`: `AdminLogin.tsx` — tela de login, armazena JWT no `sessionStorage`.
- [ ] `frontend-crm`: `AdminGuard` — HOC/wrapper que redireciona para login se não houver JWT admin válido.
- [ ] `frontend-crm`: `AdminLayout.tsx` — sidebar com links para as 7 seções + botão de logout.
- [ ] Rota `/saas-admin` apontando para o layout, com subrotas para cada página.

### Fase 2 — Migrar o que existe
*Aproveitar o trabalho já feito, removendo o anti-pattern do service token no frontend.*

- [ ] `AdminUsers.tsx`: absorver lógica de `Subscriptions.tsx` (lista de usuários + extensões), autenticando via JWT admin.
- [ ] `backend-core`: rota `GET /admin/users` protegida por `require_admin` (substituindo a rota que usava service token).
- [ ] `backend-core`: rota `PATCH /admin/users/{user_id}/extensions` protegida por `require_admin`.
- [ ] Deprecar o padrão de service token no frontend — `Subscriptions.tsx` pode ser removido ou redirecionado.

### Fase 3 — Dashboard e Instâncias (alto valor operacional)
*As duas seções mais úteis no dia-a-dia de operação.*

- [ ] `backend-core`: `GET /admin/stats` — KPIs: total de usuários, instâncias online/offline, MRR estimado.
- [ ] `backend-core`: `GET /admin/instances` — lista instâncias WhatsApp com status UazAPI.
- [ ] `backend-core`: `POST /admin/instances/{id}/reconnect` — força reconexão remota.
- [ ] `AdminDashboard.tsx`: KPIs + alertas de instâncias offline.
- [ ] `AdminInstances.tsx`: tabela com status em tempo real, ação de reconexão.

### Fase 4 — Agentes e Configurações
- [ ] `AdminAgents.tsx`: overview dos prompts padrão por agente e desvios por usuário.
- [ ] `AdminSettings.tsx`: feature flags por plano/usuário (integra com `enabled_extensions`).

### Fase 5 — Crescimento e Financeiro
*Requerem dados históricos acumulados — deixar por último.*

- [ ] `AdminGrowth.tsx`: churn, funil trial→conversão, feature adoption.
- [ ] `AdminFinancial.tsx`: MRR/ARR, consumo excedente, inadimplência.

---

## Prioridade de implementação (resumo)

```
Fase 1 (auth)  →  Fase 2 (migrar)  →  Fase 3 (dashboard + instâncias)
     ↓
Fase 4 (agentes + config)  →  Fase 5 (métricas avançadas)
```

Fases 1–3 cobrem o uso operacional diário. Fases 4–5 são analytics e podem ser incrementais.