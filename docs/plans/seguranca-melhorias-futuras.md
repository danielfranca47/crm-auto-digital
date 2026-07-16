# Segurança — Melhorias Futuras

> Contexto: itens levantados pela auditoria de segurança pedida em 2026-07-15
> (4 revisões paralelas: auth/senhas, entitlements, agentes locais,
> injeção/CORS). Os 2 achados **críticos** dessa auditoria (rotas de
> `appointments.py` sem autenticação e `SECRET_KEY` com fallback hardcoded)
> já foram corrigidos e graduados — ver `docs/architecture/agenda.md` e
> `docs/architecture/auth-email.md`. Este arquivo cobre o que ficou de fora:
> os achados Altos, Médios e Baixos, para corrigir por prioridade quando fizer
> sentido no roadmap.

---

## M1 — Código de verificação (OTP) pode ser adivinhado por força bruta

**Em palavras simples:** o login por OTP manda um código de 6 dígitos por
15 minutos, mas o sistema não conta quantas vezes alguém errou. Um atacante
pode simplesmente tentar todas as combinações possíveis nesse intervalo e,
mais cedo ou mais tarde, acertar — sem nenhum alarme disparar.

**Prioridade: ALTA** (caminho direto para tomar conta de um utilizador,
sem precisar de mais nenhuma falha)

**Estado actual:** `POST /auth/verify-otp` (`backend-core/app/api/auth.py`)
gera o código com `secrets.randbelow(900_000) + 100_000` — só 1 milhão de
combinações — e valida contra o valor guardado sem nenhum contador de
tentativas falhas nem limite por IP/conta.

**Risco concreto:** um script simples, sem rate limit para o travar, tem
tempo de sobra dentro da janela de 15 minutos para tentar todas as
combinações e assumir a conta de qualquer utilizador.

**O que precisaria existir:** um contador de tentativas falhas por
utilizador/OTP (bloquear depois de N erros) e rate limit por IP nesse
endpoint especificamente.

---

## M2 — Upload de planilhas aceita qualquer chamada anónima

**Em palavras simples:** o endpoint que recebe arquivos Excel/CSV para
importar leads não pede login nenhum. Qualquer pessoa na internet pode
mandar arquivos para o servidor, sem limite de tamanho nem de quantidade.

**Prioridade: ALTA** (superfície de negação de serviço num serviço exposto
à internet, sem nenhuma barreira)

**Estado actual:** `POST /api/uploads` (`backend-crm/routes/uploads.py:46`)
não tem `Depends(require_crm_access)`. O arquivo é gravado em disco
(`data/uploads/ai/{uuid}.ext`) e processado com `pandas.read_excel`/
`read_csv` sem limite de tamanho nem cota por utilizador.

**Risco concreto:** um atacante pode mandar arquivos grandes ou em
quantidade repetida até esgotar o disco do servidor, ou explorar uma falha
futura do parser do pandas — sem precisar de nenhuma credencial.

**O que precisaria existir:** exigir `require_crm_access`, limitar o
tamanho do arquivo aceite, e isolar/limpar os arquivos por `user_id`.

---

## M3 — Endpoints de login e recuperação de senha não travam tentativas repetidas

**Em palavras simples:** tentar logar, criar conta, pedir recuperação de
senha ou trocar a senha — nenhuma dessas ações tem limite de quantas vezes
alguém pode tentar. Um atacante pode ficar tentando senhas sem parar.

**Prioridade: MÉDIA** (mitigado em parte pelo custo do hash da senha, mas
sem nenhuma barreira dedicada)

**Estado actual:** `POST /auth/login`, `/register`, `/forgot-password`,
`/reset-password` e `/change-password` (`backend-core/app/api/auth.py`) não
têm rate limiting, contador de tentativas nem CAPTCHA.

**Risco concreto:** ataque de força bruta contra a senha de uma conta
específica, ou uso do `/register` para spam de contas.

**O que precisaria existir:** rate limiting por IP/conta (ex.: `slowapi`)
nesses 5 endpoints.

---

## M4 — Limite diário de envio de WhatsApp tem um caminho que ignora a contagem

**Em palavras simples:** o plano do utilizador define quantas mensagens de
WhatsApp ele pode mandar por dia, e isso é respeitado na maioria dos
lugares — menos num. Um botão específico ("enviar follow-up agora") deixa
passar sem contar para o limite.

**Prioridade: MÉDIA** (não é falha de isolamento entre contas, é um
utilizador conseguindo exceder o próprio limite contratado)

**Estado actual:** `max_whatsapp_send_daily` é aplicado corretamente em
`routes/prospeccao.py` (envio em lote) e `routes/agents.py` (envio manual),
mas `send_followup_now` (`backend-crm/routes/leads.py:1573`) insere o job
direto via SQL sem passar por `rate_limit_service.ensure_daily_limit`.

**Risco concreto:** um utilizador do plano Start (limite de 50/dia) pode
mandar mensagens ilimitadas usando só esse botão.

**O que precisaria existir:** chamar `rate_limit_service.ensure_daily_limit(...)`
antes do insert em `send_followup_now`, igual às outras duas rotas.

---

## M5 — Rota de perfil antiga (pré-multitenancy) continua acessível sem login

**Em palavras simples:** existe uma tela de "perfil" antiga, de antes do
sistema suportar várias contas, que ainda está ligada no servidor sem pedir
login. Parece não ser mais usada pelo frontend actual, mas continua lá,
respondendo a quem chamar.

**Prioridade: MÉDIA** (provável código morto, mas ainda exposto)

**Estado actual:** `GET/PUT /api/profile` (`backend-crm/routes/profile.py:37`)
não tem `Depends`, e opera sobre uma linha fixa (`id=1`) no banco. Sem
referências encontradas em `frontend-crm/src` actual.

**Risco concreto:** qualquer chamada anónima pode ler ou sobrescrever esses
dados (nome do remetente, assinatura, etc.), mesmo sem uso aparente hoje.

**O que precisaria existir:** confirmar que está mesmo sem uso e remover o
router, ou adicionar auth + escopo por `user_id` se ainda for necessário.

---

## M6 — Segredos sensíveis trafegando na URL em vez de no cabeçalho

**Em palavras simples:** dois lugares do sistema aceitam um "código secreto"
como parte do link (depois do `?`) em vez de escondido no cabeçalho da
requisição. Links completos costumam ficar guardados em logs de servidor,
histórico de navegador e cabeçalhos de encaminhamento — o que pode vazar
esse segredo sem ninguém perceber.

**Prioridade: MÉDIA**

**Estado actual:**
- `POST /webhooks/payment/{gateway}` (`backend-crm/routes/webhooks.py:489`)
  aceita o segredo por `X-Webhook-Secret` (cabeçalho, correcto) **ou**
  `?token=` (query string, arriscado) — o caminho por header já é
  suficiente sozinho.
- `GET /api/agents/next-job` (`backend-crm/routes/agents.py:111`) recebe
  `agent_id` e `token` via `Query(...)`, diferente de `register` e `report`
  no mesmo arquivo, que recebem no corpo do POST.

**Risco concreto:** vazamento do segredo em logs de acesso/proxy ou em
histórico, permitindo a alguém com acesso a esses logs reusar o segredo.

**O que precisaria existir:** remover o fallback `?token=` do webhook de
pagamento, e mudar `next-job` para POST com o token no corpo (ou header
`Authorization: Bearer`), igual às outras duas rotas do agente.

---

## M7 — Agente local pode fazer polling sem limite e travar o banco do tenant

**Em palavras simples:** o robô que roda no computador do utilizador fica
perguntando ao servidor "tem trabalho novo pra mim?" repetidamente. Não há
nenhum limite de quantas vezes por segundo ele pode perguntar isso — e como
o banco de dados é de escritor único, perguntas demais podem travar as
escritas de todo mundo daquela conta.

**Prioridade: MÉDIA**

**Estado actual:** `provision` (criação de agente) já é limitado via
`ensure_max_agents_local`, mas `GET /next-job`, `POST /register` e
`POST /report` (`backend-crm/routes/agents.py`) não têm nenhum throttle.
Cada chamada abre uma transacção `BEGIN IMMEDIATE` no SQLite.

**Risco concreto:** um token de agente comprometido, ou um bug no próprio
agente local causando polling agressivo, pode travar a fila de jobs
daquele tenant.

**O que precisaria existir:** aplicar um intervalo mínimo de poll
(token-bucket) por `agent_id` nessas três rotas.

---

## M8 — Comparações de segredo não usam tempo constante

**Em palavras simples:** quando o sistema confere se um "código secreto"
bate (token de serviço, senha de admin, token de agente), ele usa uma
comparação comum (`==`/`!=`) em vez de uma comparação "à prova de
cronómetro". Na teoria, isso permite a alguém descobrir o segredo
cronometrando quanto tempo cada tentativa demora — na prática, é um risco
baixo aqui porque os segredos envolvidos já são bem compridos.

**Prioridade: MÉDIA** (correcção barata, risco teórico)

**Estado actual:** 7 ocorrências entre `backend-core` (comparação de
service-tokens e do segredo de admin) e `backend-crm` (token de agente,
report de job, segredo de webhook) usam `!=`/`==` directo. O padrão
correcto (`hmac.compare_digest`) já existe no próprio código
(`auth_google.py:54`), só não foi aplicado nesses outros pontos.

**Risco concreto:** teórico — canal lateral de tempo, exploração pouco
prática dado o tamanho dos tokens envolvidos (a maioria com 256 bits de
entropia).

**O que precisaria existir:** padronizar todas as comparações de
segredo/token com `secrets.compare_digest`.

---

## M9 — Token de sessão comprometido continua válido por até 30 dias

**Em palavras simples:** se alguém roubar o "token de renovação" de um
utilizador, esse token continua funcionando por até 30 dias — mesmo que o
utilizador troque a senha logo depois, achando que resolveu o problema.

**Prioridade: MÉDIA**

**Estado actual:** `POST /auth/token/refresh` (`backend-core/app/api/auth.py:71`)
não mantém lista de revogação. `change_password` actualiza o `password_hash`
mas não invalida tokens de refresh já emitidos.

**Risco concreto:** troca de senha após suspeita de comprometimento não
encerra sessões já abertas via refresh token.

**O que precisaria existir:** reduzir o TTL do refresh token, e/ou
implementar invalidação na troca de senha (ex.: versionar o token com um
campo que muda a cada troca de senha).

---

## M10 — Custo do hash de senha desactualizado + sem tamanho mínimo

**Em palavras simples:** a senha nunca é guardada em texto puro — isso está
certo. Mas o "quanto custa" para testar uma senha por força bruta (caso o
banco vaze um dia) está configurado com um valor antigo, bem abaixo do que
se recomenda hoje. Também não existe exigência de tamanho mínimo — hoje dá
para criar conta com senha de 1 caractere.

**Prioridade: BAIXA** (não é vazamento activo, é hardening preventivo)

**Estado actual:** `backend-core/app/api/auth.py:19` — `CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")`
sem `pbkdf2_sha256__rounds` configurado, usa o default legado do passlib
(29 mil iterações; recomendação actual da OWASP é 600 mil+). `UserCreate.password`
e `ResetPasswordRequest.new_password` não têm `min_length`.

**Risco concreto:** se o `password_hash` vazar algum dia, o custo de
quebra por força bruta offline fica ~20x menor do que deveria.

**O que precisaria existir:** configurar `pbkdf2_sha256__rounds=600_000`
(ou migrar para `bcrypt`/`argon2`), e adicionar `Field(min_length=8)` nos
dois campos de senha.

---

## M11 — `.gitignore` só protege o nome exacto `.env`

**Em palavras simples:** a regra que impede segredos de irem parar no
repositório só reconhece o nome exacto `.env`. Três arquivos
`.env.production` (frontend-admin, frontend-crm, website) escapam dessa
regra e estão versionados — hoje só têm valores públicos, mas a regra é
frágil.

**Prioridade: BAIXA**

**Estado actual:** `.gitignore:13` tem uma entrada literal `.env`. Inspeção
confirmou que os 3 `.env.production` versionados só contêm valores públicos
`VITE_*` (URLs de backend, um placeholder de form token) — nenhum segredo
real vazado hoje.

**Risco concreto:** qualquer `.env.*` com nome diferente do padrão escapa
silenciosamente da protecção, e um segredo real colocado ali um dia
acabaria commitado sem aviso.

**O que precisaria existir:** trocar a regra para `.env*` com allowlist
explícito de `!.env.example`.

---

## M12 — CORS do backend-core confia em origens de desenvolvimento permanentemente

**Em palavras simples:** a lista de "sites que podem chamar este servidor"
mistura endereços de desenvolvimento local com os domínios reais de
produção, sem separar os dois por ambiente.

**Prioridade: BAIXA** (não é a combinação crítica wildcard+credenciais —
essa foi verificada e não ocorre em nenhum dos três backends)

**Estado actual:** `backend-core/app/main.py:13` tem uma lista hardcoded
que inclui portas de `localhost` junto dos domínios de produção.

**Risco concreto:** falta de higiene entre ambientes, não uma
vulnerabilidade activa por si só.

**O que precisaria existir:** condicionar as origens de dev a uma env flag,
deixando produção só com os domínios reais.

---

## M13 — Leads criados pelo formulário público ficam sem dono

**Em palavras simples:** o formulário público do site cria leads no CRM,
mas esses leads não ficam vinculados a nenhuma conta — viram registos
"órfãos" que o resto do sistema não sabe a quem pertencem.

**Prioridade: BAIXA** (bug funcional mais do que de segurança — o endpoint
já é protegido por `FORM_TOKEN`)

**Estado actual:** `POST /public/leads` (`backend-crm/routes/public.py:191`)
insere na tabela `leads` sem preencher `user_id`.

**Risco concreto:** esses leads não aparecem nas queries multitenant
normais (todas filtram por `user_id`), ficando efectivamente invisíveis no
Kanban do dono a quem deveriam pertencer.

**O que precisaria existir:** decidir a quem esses leads devem pertencer
(conta fixa? campo no formulário?) e preencher `user_id` na inserção.

---

## M14 — Script de desenvolvimento do agent-local usa `pickle` para ler seus próprios dados

**Em palavras simples:** um script usado só durante o desenvolvimento do
agente de prospecção lê de volta um arquivo que ele mesmo escreveu, usando
um formato (`pickle`) que não é seguro para ler dados de origem
desconhecida. Hoje não há risco real porque o arquivo é sempre gerado pelo
próprio script — mas é um hábito arriscado de manter.

**Prioridade: BAIXA**

**Estado actual:** `agent-local/test.py:373` — `pickle.load(f)` lendo
`collected_posts.pkl`, gerado pelo mesmo script numa etapa anterior. Não é
endpoint de rede, sem input externo.

**Risco concreto:** nenhum hoje; vira risco se a proveniência desse
arquivo mudar no futuro (ex.: passar a vir de outra fonte).

**O que precisaria existir:** trocar por JSON — os dados são só uma lista
de links, não precisam de `pickle`.

---

## Relação com outros documentos

- Os 2 achados críticos da mesma auditoria (rotas de `appointments.py` sem
  autenticação, `SECRET_KEY` hardcoded) já estão corrigidos e documentados
  em `docs/architecture/agenda.md` e `docs/architecture/auth-email.md`.
- Nenhum destes itens foi encontrado como SQL injection, command injection,
  CORS crítico (wildcard+credenciais) ou segredo versionado no repo — essas
  classes vieram limpas na auditoria e não precisam de item aqui.
