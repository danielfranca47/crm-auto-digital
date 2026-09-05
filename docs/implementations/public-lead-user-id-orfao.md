# Leads do formulário público do site ficam órfãos (user_id nulo)

**Branch:** `fix/public-lead-user-id-orfao`
**Status:** Todos os cenários validados (05/09/2026) — pendente: passo
operacional pós-merge (configurar `PUBLIC_LEAD_USER_ID` em produção)

---

## Motivação

O utilizador perguntou como os leads capturados pelo formulário de contato do
seu site de marketing chegam ao CRM, preocupado com possível partilha de
dados pessoais dos seus leads com outros utilizadores da plataforma.

---

## Problemas Identificados (estado anterior)

1. **`user_id` nulo no INSERT do formulário público:**
   `backend-crm/routes/public.py::create_public_lead()` (linhas 191-209) não
   inclui a coluna `user_id` no `INSERT INTO leads`. Como o schema
   (`database.py:1038`) declara `user_id INTEGER` sem `NOT NULL`/`DEFAULT`, o
   lead nasce com `user_id = NULL`. Toda listagem de leads no CRM filtra
   estritamente por `user_id = <utilizador autenticado>`, então esses leads
   nunca aparecem em nenhum Kanban — nem no do próprio dono do site. Só o
   e-mail de notificação (`EMAIL_TO`) e o auto-reply chegam a acontecer.
2. **`resolve_agent_type_for_user()` chamado sem `user_id`:**
   `public.py:206` chama a função sem argumentos, caindo sempre no fallback
   `"agent_1"` em vez de resolver o AI Profile real do dono da conta.

---

## Diagnóstico

- `POST /public/leads` (montado em `app.py:280`) é exclusivo do site do
  próprio utilizador — autenticado por um único `FORM_TOKEN` fixo, sem
  qualquer noção de multi-tenant. Não existe hoje uma versão desse formulário
  para outros clientes da plataforma usarem — **não há risco de partilha de
  dados entre utilizadores**, o problema é o oposto: o lead não aparece em
  lugar nenhum, nem para o dono.
- Padrão já existente no mesmo arquivo para configuração de destino único:
  `EMAIL_TO=contacto@danielfranca.pt` (`.env.example:130`) — o e-mail do
  próprio dono, fixo. O fix segue a mesma lógica: uma nova env var fixa
  aponta para a conta CRM de destino.
- Não existe teste automatizado para este endpoint hoje.

### Sobre o `user_id` de produção

Não é necessário para escrever o código — só é necessário depois, como passo
operacional, para configurar o valor real da env var no Railway (ver seção
final). O utilizador pode consultar o Painel SaaS Admin (Usuários → busca por
e-mail) para obter o `user_id` de `autodigital157@gmail.com`.

---

## Abordagem

Nova env var `PUBLIC_LEAD_USER_ID` (inteiro, obrigatória para o endpoint
funcionar) — mesmo padrão de `FORM_TOKEN`/`EMAIL_TO`: helper que lê do
ambiente e falha com 500 claro se ausente/inválida. Usada para:
1. Preencher `user_id` no `INSERT INTO leads`.
2. Passar para `resolve_agent_type_for_user(user_id=...)`, resolvendo o AI
   Profile real do dono em vez do fallback fixo.

Escopo é só este endpoint público — não altera nenhuma rota autenticada
normal do CRM nem a lógica multi-tenant existente.

---

## Plano de Implementação

### Fase 1 — `user_id` fixo via env var + teste automatizado

**Objetivo:** leads do formulário público passam a aparecer no Kanban da
conta configurada, com AI Profile correto resolvido.

| Arquivo | O que muda |
|---|---|
| `backend-crm/routes/public.py` | Nova `_get_public_lead_user_id()`; `create_public_lead()` inclui `user_id` no INSERT e chama `resolve_agent_type_for_user(user_id=...)` |
| `backend-crm/.env.example` | Adicionar `PUBLIC_LEAD_USER_ID=TO_DEFINE` |
| `backend-crm/tests/test_public_lead_user_id.py` (novo) | Cobre: INSERT grava `user_id` correto; 500 claro se env var ausente |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `e98079218d6861b3ee654c036aa5322f31e712c6` | `user_id` fixo via `PUBLIC_LEAD_USER_ID` + teste automatizado |

**Detalhes do commit `e980792`:**
- `backend-crm/routes/public.py` — `_get_public_lead_user_id()` (mesmo padrão de `_get_form_token()`); INSERT grava `user_id`; `resolve_agent_type_for_user(user_id=...)` resolve o AI Profile real
- `backend-crm/.env.example` — documenta `PUBLIC_LEAD_USER_ID`
- `backend-crm/tests/test_public_lead_user_id.py` — 2 testes (grava com `user_id` correto; falha 500 sem a env var, sem gravar lead órfão)

### Relatório da Fase 1 — o que mudou na prática

**Antes:** quando alguém preenchia o formulário de contato do seu site, o
lead era criado no banco mas ficava "invisível" — nenhuma tela do CRM
conseguia mostrá-lo, porque o registro não tinha dono (`user_id` vazio). A
única coisa que de fato acontecia era o envio de e-mails (notificação +
resposta automática).

**Agora:** o lead nasce já vinculado à conta configurada (via
`PUBLIC_LEAD_USER_ID`) e aparece normalmente no Kanban dessa conta, na coluna
"À Prospectar", com origem "Formulário Website". Se essa configuração faltar
no servidor, o formulário retorna um erro claro em vez de continuar gravando
leads órfãos silenciosamente.

**Para validar:** Cenário C1 e C2, abaixo — mas note que ainda falta o passo
operacional (definir a env var em produção) antes de fechar esta
implementação; ver seção final do arquivo.

---

## Checks de Validação

### Cenário C1 — Lead público aparece no Kanban do dono
- [x] Configurar `PUBLIC_LEAD_USER_ID` localmente com o `user_id` da conta de
      teste (15) e `FORM_TOKEN` local
- [x] `POST /public/leads` local com payload de teste + header `x-form-token`
- [x] Confirmar que o lead aparece em "À Prospectar" com origem "Formulário
      Website"
- **Validado em:** 05/09/2026 — `curl -X POST http://localhost:8000/public/leads`
  local retornou `201 {"id":512,"status":"created"}`. Confirmado via banco
  (`user_id=15`, `origin='Formulário Website'`, `category='to-prospect'`,
  `agent_type='agent_3'` — resolvido do AI Profile real do usuário 15, não
  mais o fallback fixo `agent_1`) e via `GET /api/leads` autenticado como o
  usuário 15: o lead 512 aparece na listagem normalmente.

### Cenário C2 — Falha clara sem a env var
- [x] Remover `PUBLIC_LEAD_USER_ID`, repetir o POST
- [x] Confirmar resposta 500 com mensagem clara
- **Validado em:** 05/09/2026 — com `PUBLIC_LEAD_USER_ID` removida do `.env`
  e `backend-crm` reiniciado, o mesmo POST retornou
  `500 {"detail":"PUBLIC_LEAD_USER_ID não configurado no servidor."}`.
  Confirmado via banco que nenhum lead órfão foi criado (0 leads com
  `user_id IS NULL`, 0 leads com o e-mail de teste usado neste cenário).

### Automatizado
- [x] `pytest backend-crm/tests/test_public_lead_user_id.py`
- **Validado em:** 05/09/2026 — `2 passed in 0.86s`.

---

## Passo operacional pós-merge (fora do código)

Depois de mergear e o Railway fazer deploy automático, configurar
`PUBLIC_LEAD_USER_ID` no serviço `backend-crm` do Railway com o `user_id`
real de produção de `autodigital157@gmail.com`. Sem isso, o endpoint em
produção responde 500 até a variável ser definida.

---

## Ajustes Possíveis Pós-Implementação

_Nenhum identificado até o momento._
