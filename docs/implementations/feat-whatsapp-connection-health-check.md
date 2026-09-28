# Verificação periódica de saúde das conexões WhatsApp (a cada 6h)

---

**Branch:** `feat/whatsapp-connection-health-check` (Fases 1–3, já mergeada em `main`) · Fase 4: `fix/whatsapp-reconnect-email-polling`
**Status:** Em andamento

---

## Motivação

O backend-core só descobre que uma sessão WhatsApp morreu do lado da UazAPI
quando o webhook `connection` avisa. Essa limitação já estava documentada em
`docs/architecture/whatsapp-connection.md` ("Deteção de queda de sessão"):
*"depender da entrega do webhook, sem verificação periódica independente
ainda"*.

Isso causou um incidente real: a instância `crm-2-b089460e`
(`autodigital157@gmail.com`) morreu na UazAPI (401 em qualquer chamada) sem
nenhum webhook avisar — o banco continuou achando que estava tudo bem até o
usuário tentar reconectar manualmente e esbarrar num bug separado (fora
desta implementação). Pedido do usuário: um job que rode a cada 6 horas,
pergunte pra UazAPI se cada conexão marcada como ativa no nosso banco ainda
está viva de verdade, e corrija o status quando não estiver.

---

## Problemas Identificados (estado anterior)

1. **Sem verificação periódica:** `backend-core/app/main.py:67-81` — o único
   job agendado no sistema é o de expiração de assinaturas
   (`run_daily_subscription_jobs`). Nada verifica proativamente se as
   conexões WhatsApp continuam vivas na UazAPI.

2. **Lógica de email presa no webhook:** `backend-core/app/api/whatsapp_instances.py:356-463`
   (`connection_event`) — a detecção de transição ativo↔inativo, o cooldown
   de 30min e o disparo dos emails de desconexão/reconexão estão embutidos
   direto no handler da rota de webhook, sem forma de reaproveitar a partir
   de um contexto diferente (como um job agendado) sem duplicar ~70 linhas.

---

## Abordagem

```
APScheduler (a cada 6h, UTC 00/06/12/18)
  → run_whatsapp_connection_check()  [novo: app/jobs/whatsapp_connection_check_jobs.py]
      → busca todas as WhatsappConnection com status normalizado = "active"
      → para cada uma (com pausa de 0.3s entre chamadas):
          → decrypt_secret(instance_token_encrypted)
          → uazapi_admin.get_status(...)
              ├─ 401 (token morto)         → apply_connection_status_change(db, conn, "disconnected")
              ├─ status extraído da UazAPI → apply_connection_status_change(db, conn, status)
              └─ outro erro (timeout/5xx/429 esgotado) → loga e pula, tenta no próximo ciclo
      → retorna sumário {checked, marked_dead, errors, ran_at}

apply_connection_status_change(db, connection, new_status)  [novo, extraído do webhook]
  → em app/services/whatsapp_connections.py
  → detecta transição ativo↔inativo (normalize_connection_status_for_crm, já existe)
  → grava novo status, dispara email de desconexão/reconexão com o mesmo
    cooldown de 30min que já existe hoje
  → usado tanto pelo webhook (connection_event) quanto pelo job novo
```

---

## Plano de Implementação

### Fase 1 — Extrair lógica de status/email para função reutilizável

**Objetivo:** refactor puro, sem mudança de comportamento — pré-requisito para a Fase 2.

| Arquivo | O que muda |
|---|---|
| `backend-core/app/services/whatsapp_connections.py` | Nova função `apply_connection_status_change(db, connection, new_status)` — move a lógica de `whatsapp_instances.py:380-461` (transição, cooldown, os dois emails, updates de `disconnect_alert_sent_at`/`last_disconnect_email_at`) quase verbatim |
| `backend-core/app/api/whatsapp_instances.py` | `connection_event()` passa a só extrair `status_value` e chamar `connections_service.apply_connection_status_change(db, connection, status_value)` — remove ~70 linhas duplicadas |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `d344ffe` | Extraída `apply_connection_status_change()` para `whatsapp_connections.py`; `connection_event()` refatorado para delegar a ela |

### Fase 2 — Job periódico + registro no scheduler + trigger manual

**Objetivo:** rodar a verificação a cada 6h e permitir disparo manual para validar

| Arquivo | O que muda |
|---|---|
| `backend-core/app/jobs/whatsapp_connection_check_jobs.py` (novo) | `run_whatsapp_connection_check() -> dict` (síncrono, para o APScheduler) + `run_whatsapp_connection_check_async()` (para chamar de dentro de uma rota `async def` já rodando no event loop) — mesmo padrão de `run_daily_subscription_jobs`; erro tratado por conexão, não aborta o lote |
| `backend-core/app/main.py` | Registra `run_whatsapp_connection_check` no `_scheduler` já existente, `CronTrigger(hour="0,6,12,18", minute=0, timezone="UTC")` — sem chamada síncrona no startup |
| `backend-core/app/api/cron.py` | Nova rota `POST /admin/cron/whatsapp-connection-check` (mesmo padrão de `/admin/cron/daily`), usando `run_whatsapp_connection_check_async()` via `await` — para validar sem esperar 6h |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `67652ae` | Job periódico + registro no scheduler + rota de trigger manual |

**Bug encontrado e corrigido durante o teste local:** a primeira versão só
tinha `run_whatsapp_connection_check()` (síncrona, com `asyncio.run()` por
dentro) — funciona bem chamada pelo APScheduler (roda em thread própria, sem
event loop ativo), mas quebrava com `RuntimeError: asyncio.run() cannot be
called from a running event loop` ao ser chamada pela rota de trigger manual
(que já roda dentro do event loop do FastAPI). Corrigido expondo também
`run_whatsapp_connection_check_async()`, chamada com `await` diretamente pela
rota — a versão síncrona continua existindo só para o APScheduler.

**Teste local realizado** (worktree, `.env` copiado da pasta principal,
banco SQLite local descartável, contra a UazAPI e o serviço de email
**reais** de produção — nenhum dado de cliente real foi tocado):
1. Servidor local iniciado, rota `/admin/cron/whatsapp-connection-check`
   chamada com o banco vazio → `checked: 0`, sem erro.
2. Criado um usuário e uma conexão fake no banco local, com status
   `connected` e um `instance_token` inválido → trigger detectou 401 da
   UazAPI real, marcou a conexão como `disconnected`, tentou mandar o email
   de desconexão (rejeitado pelo provedor por ser um domínio de teste
   `example.com` — comportamento esperado, e o erro foi capturado sem
   derrubar o job, como projetado).
3. Conferido no banco: `status=disconnected`, `disconnect_alert_sent_at`
   preenchido, `last_disconnect_email_at` continua `None` (porque o envio
   falhou) — bate exatamente com o comportamento original do webhook.
4. Trigger chamado de novo → `checked: 0` (a conexão já não conta mais como
   "ativa", não é reprocessada) — confirma que não fica batendo na UazAPI
   pra sempre em cima da mesma conexão morta.

---

## Checks de Validação

### Cenário P1 — Webhook continua funcionando após o refactor da Fase 1
- [x] Desconectar e reconectar uma instância de teste (produção/playground)
- [ ] Confirmar: os dois emails (queda e retorno) continuam disparando, com o cooldown de 30min intacto
- **Resultado em:** 28/09/2026 — instância `crm-2-88ff58af` (conta de teste). Email de queda chegou (23:45, hora local); email de retorno **não saiu**. Causa: bug pré-existente no polling de status, não no refactor da Fase 1 — ver Fase 4. Este check fecha junto com o Cenário P2.

### Cenário C1 — Job não mexe em conexão saudável
- [x] Validado localmente de forma equivalente: rodar o trigger sem nenhuma conexão ativa não gera erro nem falso positivo (`checked: 0, marked_dead: 0`)
- [⏭️] Pendente em produção — pulado por ora: no momento do teste em produção (18/09/2026), **nenhuma das conexões WhatsApp existentes estava saudável** (as 3 contas de cliente já estavam mortas na UazAPI, achado do próprio teste — ver nota abaixo). Não há hoje uma conexão real "saudável" para servir de amostra positiva. Retomar este check assim que algum cliente reconectar com sucesso.
- **Validado em:** 18/09/2026 (local, caminho "sem conexão ativa") + 18/09/2026 (produção, ver nota)

### Cenário C2 — Job detecta conexão morta e dispara alerta
- [x] Chamar o trigger manual com uma conexão cujo token a UazAPI não reconhece mais (validado localmente com token fake, UazAPI real) → sumário mostrou `marked_dead: 1`, status virou `disconnected` no banco
- [x] Confirmado em produção com um caso real: `crm-3-5d90b405` (gabrielsmith.original@gmail.com) — job detectou 401, marcou `disconnected` no banco (conferido via `/admin/instances`), e o log não registrou falha de envio de email (diferente do teste local com domínio fake) — indício de que o email real foi enviado com sucesso
- **Validado em:** 18/09/2026 — local (token fake) + produção (caso real, ver nota abaixo)

### Cenário C3 — Agendamento automático funciona
- [x] Log do Railway confirma o job registrado no APScheduler ao subir (`Added job "run_whatsapp_connection_check" to job store "default"`) — mecanismo de agendamento funcionando
- [x] Confirmar uma execução automática real (sem trigger manual) em um dos horários 00:00/06:00/12:00/18:00 UTC
- **Validado em:** 28/09/2026 — logs do Railway mostram execuções automáticas às 00h, 06h, 12h e 18h UTC, todas `executed successfully` (`checked: 0` porque não havia conexão ativa naquele momento)

---

### ⚠️ Achado relevante durante a validação em produção (18/09/2026)

Ao rodar o trigger manual pela primeira vez em produção, o job encontrou
**apenas 1 conexão marcada como ativa no banco** (`crm-3-5d90b405`,
`gabrielsmith.original@gmail.com`) — e ela estava morta (401). Consultando
`/admin/instances` depois, as **3 contas de cliente existentes hoje**
(`autodigital157@gmail.com`, `aydebarbaraqod@gmail.com`,
`gabrielsmith.original@gmail.com`) estão **todas sem uma conexão WhatsApp
ativa** no momento — reforça a suspeita levantada durante o diagnóstico
original desta conversa de que a queda pode ter sido um evento mais amplo do
lado da UazAPI (não um caso isolado de um cliente só). `gabrielsmith` recebeu
agora o email real de alerta de desconexão — vale confirmar com ele/ela se
chegou e se o WhatsApp realmente está fora do ar do lado dele(a).

---

## Fase 3 — Diagnóstico + Fix: logs "info" não apareciam no Railway (18/09/2026)

### Problema identificado

Após o deploy da Fase 2, nenhum log `logger.info(...)` do serviço aparecia no
Railway — nem a linha de sucesso do APScheduler, nem os logs do job novo
(`whatsapp_connection_check_jobs.py`). `backend-core` nunca chamava
`logging.basicConfig()` em lugar nenhum — o logger raiz do Python fica no
nível padrão (`WARNING`), então `.info()` é descartado silenciosamente;
só `.warning()`/`.error()` apareciam. Isso é um gap pré-existente do
serviço (não introduzido por esta implementação), mas impedia justamente a
validação do Cenário C3.

### Correção

| Arquivo | Mudança |
|---|---|
| `backend-core/app/main.py` | `logging.basicConfig(level=logging.INFO)` adicionado no topo do módulo |

### Commits Fase 3

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `c09ff15` | fix: logging.basicConfig(INFO) para logs info aparecerem no Railway |

---

## Fase 4 — Diagnóstico + Fix: email de reconexão não saía ao reconectar pela tela do CRM (28/09/2026)

### Problema identificado

No teste P1 em produção, o email de queda chegou mas o de retorno não. A
ordem dos logs do Railway mostrou a causa: enquanto o QR está na tela, o
frontend consulta `GET /api/whatsapp/status` a cada 3s, que chega ao
backend-core em `GET /whatsapp-instances/status`
(`backend-core/app/api/whatsapp_instances.py`, `status_instance`). Essa rota
gravava `connection.status` **direto** no banco. O polling viu "connected"
antes do webhook; quando o webhook `connection=connected` chegou, a conexão
já constava como ativa → nenhuma transição → email de reconexão suprimido, e
`disconnect_alert_sent_at` ficou preso preenchido. Bug pré-existente (não
introduzido pelo refactor da Fase 1), mas atinge quase toda reconexão feita
pela tela do CRM.

### Correção

`status_instance` passa a chamar `apply_connection_status_change()` — a mesma
função do webhook e do job de 6h. Quem vê a transição primeiro manda o email;
os seguintes não repetem.

| Arquivo | Mudança |
|---|---|
| `backend-core/app/api/whatsapp_instances.py` | `status_instance`: troca a escrita direta de status por `connections_service.apply_connection_status_change(...)` |
| `backend-core/tests/test_connection_status.py` | 5 testes novos: queda+retorno mandam 2 emails; "connected" repetido não duplica; cooldown de 30min; queda após cooldown volta a avisar; regressão do polling (`status_instance` com UazAPI mockada) |
| `docs/architecture/webhooks.md` | Tabela dos 3 chamadores de `apply_connection_status_change()`; remove a "limitação conhecida" (o job de 6h já existe) |
| `docs/architecture/whatsapp-connection.md` | Seção "Deteção de queda de sessão" alinhada com os 3 caminhos |

Testes: `tests/test_connection_status.py` 7/7 passam. A suíte completa do
backend-core tem 8 falhas em `test_ai_profile_*`, **idênticas no `main`**
(pré-existentes, sem relação com esta fase).

### Commits Fase 4

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | _(pendente)_ | fix: polling de status passa por `apply_connection_status_change()` |

### Cenário P2 — Email de reconexão sai ao reconectar pela tela do CRM
- [ ] Após o deploy desta fase: com a instância de teste conectada, desconectar o aparelho no telemóvel
- [ ] Confirmar: chega o email "A tua Lara desconectou…"
- [ ] Reconectar pela tela Conexão (Reconectar QR)
- [ ] Confirmar: chega o email "A tua Lara reconectou…" (é este que falhava)

---

## Ajustes Possíveis Pós-Implementação

- `upsert_connection()` (chamado por `/whatsapp-instances/init` e `/connect`) ainda grava o status devolvido pela UazAPI direto, sem passar por `apply_connection_status_change()`. Hoje só grava `connecting`/"Already connected" — baixo risco. Não foi mudado na Fase 4 para não disparar um email de "desconectou" no exato momento em que o cliente clica "Reconectar QR".
- **Instâncias mortas nunca são apagadas na UazAPI (encontrado em 28/09/2026):** o plano UazAPI permite no máximo 6 instâncias criadas. Havia 6 fantasmas (todas `disconnected`, de testes antigos), e **nenhum cliente conseguia conectar WhatsApp** (`/instance/init` → 429 "Maximum number of instances reached"). Foram apagadas à mão no painel da UazAPI. O job de 6h marca a conexão como `disconnected` no banco, mas não apaga a instância. Candidato a correção própria: limpeza automática e/ou alerta quando estiver perto do limite.
- Hoje o job só detecta conexões que estavam "ativas" no banco e morreram — não tenta redescobrir conexões marcadas como `disconnected` que voltaram a ficar vivas sem passar pelo webhook. Se isso virar um problema real, dá pra estender o escopo da query.
