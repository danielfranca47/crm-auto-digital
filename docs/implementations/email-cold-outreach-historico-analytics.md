# Histórico/analytics de emails enviados (cold outreach)

**Branch:** `main`
**Status:** Todos os cenários validados (10/08/2026) — pendente: decidir sobre a Fase F (resumo agregado), opcional

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`docs/implementations/etapa-agent-local-v3-email-cold-outreach.md` (email cold outreach v1,
SMTP-only). Hoje não existe nenhum registo ou estatística dos emails de prospecção fria já
enviados — o utilizador não tem forma de ver quantos emails foram disparados, para quem, quando,
nem o resultado (`sent`/`failed`) fora da tabela `jobs` bruta.

Contexto arquitectural relevante (ver
[`docs/architecture/auth-email.md`](../architecture/auth-email.md#conta-smtp-do-utilizador-cold-outreach-por-email)
e [`docs/architecture/agent-local-app.md`](../architecture/agent-local-app.md#conta-de-email-smtp)):
- Job type `email.send.cold`, processado por `backend-executors/app/workers/email_worker.py` +
  `app/runners/email.py`
- Painel "Histórico" do agent-local (`_build_historico` em `main_screen.py`) já existe para
  WhatsApp (`GET /api/prospeccao/history`, JOIN `prospection_logs` + `leads`)

---

## Problemas Identificados (estado anterior)

1. **Resultado do email nunca gravado:** `report_job` (`backend-crm/services/jobs_service.py:769-880`)
   só grava `sent`/`failed` em `prospection_logs` quando `job_type == TYPE_WHATSAPP_SEND` (linha 861,
   via `_handle_whatsapp_report`). Não existe equivalente para `TYPE_EMAIL_SEND_COLD` — o email cold
   outreach só grava `action="queued"` (em `enqueue_email_jobs`, linha 1541-1548); o desfecho real
   (`sent`/`failed`, reportado pelo worker em `backend-executors/app/runners/email.py:73-151`) não
   chega a `prospection_logs`.

2. **API esconde o canal e o destinatário de email:** `GET /api/prospeccao/history`
   (`backend-crm/routes/prospeccao.py:366-408`) já mistura entradas de todos os canais, mas o
   `SELECT` não inclui `pl.channel` nem nenhum campo de email — só `phone`. Os dois consumidores
   herdam a limitação: `agent-local/app/ui/main_screen.py:2916-3045` (`_build_historico`) e
   `frontend-crm/src/pages/Pesquisa.tsx:11-226` ("Leads do Agente").

---

## Abordagem

Reaproveitar a infraestrutura já existente para WhatsApp (`prospection_logs` +
`GET /api/prospeccao/history`) em vez de construir uma tabela/rota nova.

```
Job email.send.cold executado (backend-executors)
  → crm_client.complete_job / fail_job → report_job (backend-crm)
      ├─ job_type == whatsapp.send.local → _handle_whatsapp_report (já existe)
      └─ job_type == email.send.cold     → _handle_email_report (NOVO)
             → grava prospection_logs (channel="email", action=sent|failed, email=...)

GET /api/prospeccao/history?channel=email
  → SELECT ganha pl.channel + pl.email (fallback leads.email)
  → agent-local (_build_historico) e frontend-crm (Pesquisa.tsx) exibem coluna Canal + email
```

---

## Plano de Implementação

### Fase A — backend: gravar `sent`/`failed` de email em `prospection_logs`

**Objectivo:** o desfecho real do envio de email passa a ficar gravado, tal como já acontece para
`queued` e para WhatsApp.

| Arquivo | O que muda |
|---|---|
| `backend-crm/database.py` (~1164) | `ensure_column(conn, "prospection_logs", "email", "email TEXT")` |
| `backend-crm/services/jobs_service.py` (`_log_prospection`) | novo parâmetro opcional `email: Optional[str] = None`, incluído no `INSERT` |
| `backend-crm/services/jobs_service.py` (`enqueue_email_jobs`) | passa `email=email_addr` na chamada já existente a `_log_prospection` |
| `backend-crm/services/jobs_service.py` (nova função) | `_handle_email_report(conn, payload, status, result, error_txt, *, user_id=None)` — grava `action="sent"`/`"failed"` com `channel="email"`, sem a lógica de `apply_suggested_category`/`origin='outbound'` (específica do pipeline de IA do WhatsApp) |
| `backend-crm/services/jobs_service.py` (`report_job`) | `elif job_type == TYPE_EMAIL_SEND_COLD: _handle_email_report(...)` |
| `backend-crm/tests/test_jobs_service_email_report.py` (novo) | cobre `report_job` com `status=completed` e `status=failed` para um job de email |

### Commits Fase A

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `18bc282` | backend: `_handle_email_report` + coluna `prospection_logs.email` + testes |

**Detalhes do commit `18bc282`:**
- `backend-crm/database.py` — nova coluna `prospection_logs.email` (`ensure_column` idempotente)
- `backend-crm/services/jobs_service.py` — `_log_prospection` ganha parâmetro opcional `email`;
  nova função `_handle_email_report` (análoga a `_handle_whatsapp_report`, sem a lógica de
  categoria/`origin` específica do pipeline de IA do WhatsApp); `report_job` despacha jobs
  `email.send.cold` para ela; `enqueue_email_jobs` passa a gravar o email também no log de `queued`
- `backend-crm/tests/test_jobs_service_email_report.py` — cobre `sent`/`failed`/payload sem `lead_id`
- `backend-crm/tests/test_whatsapp_outbound_message_model.py`,
  `test_qualification_integrity_guardrails.py` — schema local de `prospection_logs` actualizado
  com a coluna `email` nova (mirror do schema real), evita regressão nos testes existentes

### Relatório da Fase A — o que mudou na prática

**Antes:** quando um email de prospecção fria era enviado (ou falhava), esse resultado nunca ficava
registado em lado nenhum visível — só o "enfileirado" inicial aparecia, o resto ficava só na tabela
`jobs` bruta.
**Agora:** o sucesso (`sent`) ou a falha (`failed`) do envio fica gravado em `prospection_logs`,
com o email do destinatário guardado explicitamente — a mesma base de dados que já serve o
histórico de WhatsApp passa a ter o retrato completo do email também. Esta fase só mexe no
backend; a rota `/api/prospeccao/history` e as telas (agent-local, "Leads do Agente" no CRM) ainda
não mostram essa informação nova — isso é a Fase B/C/D.
**Para validar:** Cenários C1 e C2, na secção "Checks de Validação" abaixo — exigem um envio real
de email (sucesso e falha) com conta SMTP conectada, e inspecionar a tabela `prospection_logs`
directamente (não há UI ainda para ver isto nesta fase).

### Fase B — backend: expor `channel` e `email` em `/api/prospeccao/history`

**Objectivo:** a rota deixa de esconder o canal e o destinatário de email.

| Arquivo | O que muda |
|---|---|
| `backend-crm/routes/prospeccao.py` (`get_history`) | SELECT ganha `pl.channel` e `COALESCE(pl.email, CASE WHEN pl.channel='email' THEN l.email END) AS email`; resposta ganha `"channel"` e `"email"`; novo parâmetro opcional `channel: Optional[str] = Query(None)` filtrado na `WHERE` antes do `LIMIT/OFFSET` |

### Commits Fase B

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `5f301b2` | backend: `channel`/`email` expostos em `/api/prospeccao/history` + filtro `?channel=` |

### Relatório da Fase B — o que mudou na prática

**Antes:** a rota que alimenta o painel Histórico devolvia todas as acções (WhatsApp e email)
misturadas, mas sem indicar qual era qual, e sem o endereço de email do destinatário — só o
telefone.
**Agora:** cada entrada devolvida traz `channel` (`"whatsapp"`/`"email"`) e `email` (quando
aplicável); a rota aceita `?channel=email` para filtrar só um canal directamente na base de dados.
Ainda não há UI a usar estes campos novos — isso é a Fase C (agent-local) e D (frontend-crm).
**Para validar:** Cenários C1 e C2 (agora possíveis de confirmar via a própria API, sem SQL bruto)
— ver "Checks de Validação".

### Fase C — agent-local: coluna de Canal em `_build_historico`

**Objectivo:** distinguir visualmente email de WhatsApp e mostrar o email quando aplicável.

| Arquivo | O que muda |
|---|---|
| `agent-local/app/ui/main_screen.py:2916-3045` | nova coluna "Canal" no cabeçalho e nas linhas; quando `channel == "email"`, mostra o email em vez de `phone`; mesmo tratamento no `_export_csv` |

### Commits Fase C

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `ef41d62` | agent-local: coluna Canal + Contacto (email/telefone) no Histórico + CSV |

**Detalhes:**
- `agent-local/app/ui/main_screen.py` (`_build_historico`) — coluna "Contacto" substitui "Telefone"
  (mostra email quando `channel == "email"`, telefone caso contrário); nova coluna "Canal"
  (rótulo "Email"/"WhatsApp"); registos sem `channel` (log local JSONL, não-assinante) caem no
  fallback `"—"` sem quebrar
- mesma função, `_export_csv` — CSV ganha as mesmas duas colunas

### Relatório da Fase C — o que mudou na prática

**Antes:** o painel Histórico do agent-local mostrava Data/Hora, Nome, Telefone, Estado, Notas —
uma entrada de email aparecia sem telefone (célula vazia) e sem forma de saber que era um email.
**Agora:** há uma coluna "Canal" (Email/WhatsApp) e a coluna de contacto mostra o email quando a
entrada é de email. O CSV exportado reflecte as mesmas colunas.
**Para validar:** Cenário P1, abaixo — requer abrir o app desktop (agent-local) com uma conta
assinante e histórico com pelo menos um email e um WhatsApp enviados.

### Fase D — frontend-crm: coluna de Canal + filtro em `Pesquisa.tsx`

**Objectivo:** paridade com a Fase C no CRM web.

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/pages/Pesquisa.tsx` (`HistoryEntry`) | `channel: string`, `email: string` |
| `frontend-crm/src/pages/Pesquisa.tsx` (filtro) | segundo `Select` "Canal" (Todos/Email/WhatsApp), refetch server-side |
| `frontend-crm/src/pages/Pesquisa.tsx` (tabela) | nova coluna "Canal"; célula mostra `entry.email || entry.phone || "—"` |
| `frontend-crm/src/services/api.ts` (`history`) | aceita `channel?: string` opcional, repassado como query param |

### Commits Fase D

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `75d3bed` | frontend-crm: coluna Canal/Contacto + filtro por canal em "Leads do Agente" |

**Detalhes:**
- `frontend-crm/src/services/api.ts` (`history`) — aceita `channel?: string`, repassado como query
  param
- `frontend-crm/src/pages/Pesquisa.tsx` — `HistoryEntry` ganha `channel`/`email`; novo `Select`
  "Todos os canais/Email/WhatsApp" (`channelFilter`, refetch server-side via `load()`); tabela
  ganha colunas "Canal" e "Contacto" (email quando `channel === "email"`, telefone caso contrário)

### Relatório da Fase D — o que mudou na prática

**Antes:** a página "Leads do Agente" no CRM mostrava as mesmas colunas do agent-local (sem canal,
sem email) e só filtrava por Estado (Todos/Enviados/Falhados).
**Agora:** há um filtro adicional por Canal (Todos os canais/Email/WhatsApp), que refaz o pedido à
API já filtrado no servidor, e a tabela mostra o canal e o email quando aplicável — igual ao
agent-local.
**Para validar:** Cenário P2, abaixo — requer `npm run dev` em `frontend-crm` e histórico com pelo
menos um email e um WhatsApp enviados.

---

## Fase E — Diagnóstico + Correção: `sent`/`failed` de email não chegavam a `prospection_logs` (10/08/2026)

### Problema identificado

Ao validar os Cenários C1/C2 ao vivo (enviar um email real e um email propositadamente inválido),
o job processava normalmente (`jobs.status` ia para `completed`/`failed`), mas **nenhuma linha
`sent`/`failed` aparecia em `prospection_logs`** — só o `queued` inicial.

Causa raiz: a Fase A ligou `handle_email_report` (então `_handle_email_report`) dentro de
`jobs_service.report_job` — a função por trás de `POST /agent/report`, usada exclusivamente pelo
fluxo de polling do **Agente Local** (agent_id/token), cujos únicos job types canónicos são
`whatsapp.send.local`, `whatsapp.followup.tick`, `maps.search.local`, `maps.enrich.local`
(`docs/architecture/agents.md#job-types-canônicos` — `email.send.cold` nunca esteve nessa lista).

O `email_worker` do `backend-executors` reporta resultado por um caminho completamente diferente:
`POST /api/internal/jobs/{id}/complete` e `/fail` em `backend-crm/routes/executor.py`
(autenticado por `X-Service-Token`, não por agente) — confirmado directamente no client
(`backend-executors/app/clients/crm_client.py:99-165`) e no log do worker durante o teste ao vivo.
Ou seja, a Fase A ligou o handler a um endpoint que os jobs de email nunca atravessam — código morto
para este job type, silenciosamente nunca executado.

### Correção

| Arquivo | Mudança |
|---|---|
| `backend-crm/services/jobs_service.py` | Removido o `elif job_type == TYPE_EMAIL_SEND_COLD: ...` dentro de `report_job` (inalcançável); função renomeada `_handle_email_report` → `handle_email_report` (deixa de ser "privada" do módulo, passa a ser usada por `routes/executor.py`) |
| `backend-crm/routes/executor.py` | Import de `TYPE_EMAIL_SEND_COLD`/`handle_email_report`; `complete_job_internal` ganha `elif job_type == TYPE_EMAIL_SEND_COLD: handle_email_report(..., JOB_STATUS_COMPLETED, ...)`; `fail_job_internal` chama `handle_email_report(..., final_status, ...)` **depois** de calcular `final_status` — só grava `failed` quando a falha é definitiva (esgotou tentativas), não em cada retry intermédio (melhor que o padrão do WhatsApp, que loga em cada tentativa) |
| `backend-crm/tests/test_jobs_service_email_report.py` | Só o `import` actualizado para `handle_email_report` — os testes em si continuam válidos, testavam a função directamente, não o ponto de chamada errado |

### Como foi detectado e confirmado

Teste ao vivo através do pipeline real (não só ao nível de unidade):
1. Criado lead 434 (`danielhsfranca@gmail.com`) e lead 435 (`nao-e-email-valido`) via `POST /api/leads`
2. Enfileirado email para cada um via `POST /api/prospeccao/email/enqueue`
3. Corrido `backend-executors/app/workers/email_worker.py` manualmente (bounded a N jobs)
4. **Antes da correção:** job completava/falhava normalmente na tabela `jobs`, mas
   `prospection_logs` não ganhava nenhuma linha nova de `sent`/`failed`
5. Aplicada a correção acima, backend-crm reiniciado, jobs reenfileirados e reprocessados
6. **Depois:** `prospection_logs` passou a ganhar as linhas correctas — ver Cenários C1/C2 abaixo

### Commits Fase E

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `<preencher após commit>` | fix: liga handle_email_report ao endpoint real usado pelo backend-executors |

---

## Checks de Validação

### Cenário C1 — Email completo grava `sent` em `prospection_logs`
- [x] Enviar um email cold outreach real (lead com email válido, conta SMTP conectada)
- [x] Confirmar: linha `action="sent" channel="email"` aparece em `prospection_logs`
- **Validado em:** 10/08/2026 — lead 434 (`danielhsfranca@gmail.com`), job 503 processado pelo
  `email_worker` real via Gmail SMTP (`autodigital157@gmail.com`). `prospection_logs` id 48214:
  `action=sent channel=email email=danielhsfranca@gmail.com`. Email chegou de facto à caixa de
  entrada (confirmado pelo utilizador ser o dono do endereço). Confirmado também visualmente no
  agent-local (Estado "Enviado", verde) e no frontend-crm (`Pesquisa.tsx`).

### Cenário C2 — Email falhado grava `failed`
- [x] Forçar falha (ex.: SMTP inválido) num envio de email
- [x] Confirmar: linha `action="failed" channel="email"` com nota de erro
- **Validado em:** 10/08/2026 — lead 435 com email propositadamente inválido
  (`nao-e-email-valido`, sem tocar em credenciais SMTP). Gmail rejeitou de forma síncrona
  (`553 5.1.3 ... not a valid RFC 5321 address`), `smtplib` levantou `SMTPRecipientsRefused`,
  job 502 esgotou as 3 tentativas (`JOB_MAX_ATTEMPTS`) e ficou `failed`. `prospection_logs` id
  48219: `action=failed channel=email email=nao-e-email-valido notes=<erro real do Gmail>`. A
  linha só é gravada na tentativa final (não em cada retry) — ver Fase E acima.

### Cenário P1 — Histórico agent-local mostra canal e email
- [x] Abrir painel Histórico no agent-local após enviar email(s) e WhatsApp(s)
- [x] Confirmar: coluna Canal distingue as entradas; linhas de email mostram o endereço
- [x] Exportar CSV e confirmar a coluna Canal
- **Validado em:** 10/08/2026 — via `computer-use`/`desktop-control` (app `Gerador de Leads —
  Digital Pro` já aberta, sessão `autodigital157`). App reiniciada para carregar a Fase C (não
  recarrega código Python a quente). Painel Histórico mostrou: linha C2 com Canal="Email",
  Contacto="nao-e-email-valido", Estado="Falhou" (vermelho); linha C1 com Canal="Email",
  Contacto="danielhsfranca@gmail.com", Estado="Enviado" (verde). "Exportar CSV" gerado com sucesso
  (`historico_test.csv`, apagado após inspecção) — cabeçalho `Data/Hora,Nome,Canal,Contacto,Estado,Notas`
  com as mesmas duas linhas confirmadas no conteúdo do ficheiro.

### Cenário P2 — "Leads do Agente" (frontend-crm) mostra canal, email e filtro
- [x] Abrir `Pesquisa.tsx` no frontend-crm
- [x] Confirmar: coluna Canal e filtro por canal funcionam
- [x] Confirmar email visível numa linha de email
- **Validado em:** 10/08/2026 (1ª parte, canal+filtro) e 10/08/2026 (2ª parte, email visível,
  reaproveitando os dados reais de C1/C2) — via browser (chrome-devtools MCP), conta de teste
  `autodigital157@gmail.com`. Página recarregada após os testes de C1/C2: linha C2 mostra
  Canal="Email", Contacto="nao-e-email-valido", Estado="Falhou"; linha C1 mostra Canal="Email",
  Contacto="danielhsfranca@gmail.com", Estado="Enviado". Filtro "Todos os canais → Email"
  confirmado a filtrar server-side (`?channel=email`). Sem erros de consola (só warnings
  pré-existentes do React Router, não relacionados).

---

## Ajustes Possíveis Pós-Implementação

- Leads de teste 434/435 (`Teste Historico Email C1`/`C2 (falha)`) ficaram na conta de teste
  `autodigital157@gmail.com` como evidência dos Cenários C1/C2 — podem ser apagados a pedido.
- **Fase F (não implementada nesta ronda):** resumo agregado ("X enviados / Y falharam / Z
  enfileirados") calculado client-side sobre a lista já carregada. Não é um total histórico exacto
  (limitado à janela de `limit=200`) — um total exacto exigiria uma rota nova com
  `GROUP BY channel, action`. O contador diário exacto (vs limite do plano) já existe em
  `GET /api/usage` (`max_email_send_daily`). Avaliar se vale a pena depois de ver o histórico em
  uso real.
