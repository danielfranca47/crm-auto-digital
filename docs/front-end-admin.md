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

**4. Agentes e prompts** — Visualização ao vivo da configuração de todos os agentes do sistema, lida diretamente do estado atual do backend (não estática). Os dados refletem o que está configurado no momento da consulta.

*Formato visual sugerido:* cards por tipo de agente (`agent_mode`), cada card expansível revelando um fluxo em colunas — uma coluna por estágio (`qualificação → apresentação → negociação → fechamento`), com o texto do prompt daquele estágio exibido abaixo do título. A cor do card segue a variante (`sales`, `scheduler`, `hybrid`). Ao clicar em um estágio, abre um drawer com o prompt completo e os metadados do estágio.

*Visão por usuário:* ao selecionar um usuário, a mesma estrutura de fluxo é exibida com os valores do AI profile daquele usuário sobrepostos aos padrões — destacando visualmente os campos que diferem do padrão (badge "personalizado" ou cor diferente nas células modificadas). Campos exibidos por usuário: `agent_mode`, `presentation_variant`, `hybrid_flow_style`, `offer_pack`, variáveis de qualificação mínima por modo.

*Campos capturados pelo painel (contrato):* ver [`docs/admin-agents-contract.md`](admin-agents-contract.md).

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

- [x] `backend-core`: variável `ADMIN_SECRET` lida do env.
- [x] `backend-core`: `POST /admin/login` — valida segredo, emite JWT com `role: admin` e expiração de 8h.
- [x] `backend-core`: middleware `require_admin` que valida esse JWT.
- [x] `frontend-crm`: `AdminLogin.tsx` — tela de login, armazena JWT no `sessionStorage`.
- [x] `frontend-crm`: `AdminGuard` — HOC/wrapper que redireciona para login se não houver JWT admin válido.
- [x] `frontend-crm`: `AdminLayout.tsx` — sidebar com links para as 7 seções + botão de logout.
- [x] Rota `/saas-admin` apontando para o layout, com subrotas para cada página.

### Fase 2 — Migrar o que existe
*Aproveitar o trabalho já feito, removendo o anti-pattern do service token no frontend.*

- [x] `AdminUsers.tsx`: absorver lógica de `Subscriptions.tsx` (lista de usuários + extensões), autenticando via JWT admin.
- [x] `backend-core`: rota `GET /admin/users` protegida por `require_admin` (substituindo a rota que usava service token).
- [x] `backend-core`: rota `PATCH /admin/users/{user_id}/extensions` protegida por `require_admin`.
- [x] Deprecar o padrão de service token no frontend — `Subscriptions.tsx` removido.

### Fase 3 — Dashboard e Instâncias (alto valor operacional)
*As duas seções mais úteis no dia-a-dia de operação.*

- [x] `backend-core`: `GET /admin/stats` — KPIs: total de usuários, instâncias online/offline, MRR estimado.
- [x] `backend-core`: `GET /admin/instances` — lista instâncias WhatsApp com status UazAPI.
- [x] `backend-core`: `POST /admin/instances/{id}/reconnect` — força reconexão remota.
- [x] `AdminDashboard.tsx`: KPIs + alertas de instâncias offline.
- [x] `AdminInstances.tsx`: tabela com status em tempo real, ação de reconexão.

### Fase 4 — Agentes e Configurações

#### 4a — Endpoint e contrato de dados
- [ ] `backend-crm`: `GET /admin/agents/overview` — retorna lista de `agent_mode` disponíveis, com seus estágios e os prompts ativos de cada estágio (lidos do estado real, não hardcoded).
- [ ] `backend-crm`: `GET /admin/agents/users` — retorna lista de usuários com os campos do AI profile: `agent_mode`, `presentation_variant`, `hybrid_flow_style`, `offer_pack`, limites de qualificação por modo.
- [ ] `backend-crm`: `GET /admin/agents/users/{user_id}` — detalhe do AI profile de um usuário, com diff em relação aos valores padrão do seu `agent_mode`.

#### 4b — Frontend `AdminAgents.tsx`
- [ ] Cards por `agent_mode`, expansíveis, com fluxo em colunas de estágios (shadcn/ui `Accordion` + layout flex).
- [ ] Cada coluna de estágio exibe título e prévia do prompt; clique abre `Sheet` (drawer lateral) com o prompt completo.
- [ ] Seletor de usuário (combobox) que sobrepõe os valores do AI profile do usuário ao fluxo padrão, destacando campos personalizados com badge ou cor distinta.
- [ ] Indicador de "última atualização" dos dados (timestamp da consulta) para deixar claro que são dados ao vivo.

#### 4c — Contrato e proteção contra mudanças futuras
- [ ] Criar `docs/admin-agents-contract.md` listando todos os campos do AI profile e estágios de agente que o painel captura, com tipo, origem (tabela/rota) e o que acontece no painel se o campo mudar ou for adicionado.
- [ ] Ao finalizar a implementação da Fase 4, adicionar regra no `CLAUDE.md`: *"Sempre que um novo campo for adicionado ao AI profile (`ai_profiles`) ou um novo estágio/variável de agente for introduzido no sistema, `docs/admin-agents-contract.md` deve ser atualizado e verificar se `AdminAgents.tsx` precisa capturar o novo campo."*

#### 4d — Configurações
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