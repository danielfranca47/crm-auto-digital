# Logs INFO invisíveis em todo o backend-crm

**Branch:** `worktree-fix+logs-info-invisiveis-backend-crm`
**Status:** Todos os cenários validados (02/09/2026)

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`docs/implementations/alerta-desconexao-whatsapp.md`. Durante o teste ao vivo
dessa implementação (Cenário C3, 24/08/2026), descobriu-se que nenhum lugar do
`backend-crm` configura o nível do root logger (`logging.basicConfig` ou
equivalente) — todo `logger.info(...)` do código da aplicação (não só do
código daquela feature) fica invisível tanto em ambiente local quanto em
produção, mesmo rodando `uvicorn --log-level info` (essa flag só afeta os
loggers internos do uvicorn, não o root logger da aplicação).

Isto tem impacto directo em qualquer diagnóstico futuro: qualquer bug que
dependa de ler logs `INFO` (a maioria dos logs de negócio do sistema, ex.:
`uazapi webhook event=...`) é invisível hoje, obrigando a promover
temporariamente para `warning` sempre que se precisa de visibilidade (como foi
feito pontualmente na correção acima).

---

## Problemas Identificados (estado anterior)

1. **Root logger sem nível configurado:** `backend-crm` não tem nenhum
   `logging.basicConfig(level=...)` ou configuração equivalente no startup —
   confirmado durante o teste da implementação `alerta-desconexao-whatsapp.md`.

---

## Diagnóstico

- **Ponto de entrada:** `backend-crm/app.py` — chamado via `uvicorn app:app`
  (`Procfile`: `web: uvicorn app:app --host 0.0.0.0 --port $PORT`, sem flag de
  log-level da aplicação).
- **Nível escolhido:** `INFO`, configurável via env var `LOG_LEVEL` (default
  `INFO`) — mesmo padrão já usado em `backend-executors` (`.env.example` de
  lá já documenta `LOG_LEVEL=INFO`).
- **Dados sensíveis:** grep por `token|senha|password|secret|authorization|
  access_token` (case-insensitive) nas 121 chamadas de `logger.info` em 26
  arquivos do `backend-crm` — único hit é `services/efi_client.py:52`
  (`"efi_client: novo access_token obtido (sandbox=%s)"`), que loga apenas o
  booleano `sandbox`, nunca o token em si. Nenhum segredo exposto. Alguns
  logs incluem e-mail/charge_id (`admin_billing.py`, `webhooks.py`) — logs de
  negócio administrativos, considerados aceitáveis em produção.
- **Padrão de referência:** `backend-executors/app/core/logging.py` define
  `setup_logging(level)` (StreamHandler + formatter, `root.handlers = [...]`,
  `root.setLevel(level)`) chamado uma vez em `app/main.py`. Esse arquivo
  também tem `ContextFilter`/`log_ctx()` para campos estruturados
  (`job_id`, `lead_id`, etc.) via `LoggerAdapter` — não replicado aqui porque
  o `backend-crm` não usa esse padrão de adapter (os call sites já embutem os
  valores na própria string da mensagem, ex.: `"lead_category_skip
  lead_id=%s reason=..."`). Adicionar o filtro só resultaria em campos vazios
  (`-`) no formatter, sem ganho.
- **Achado relacionado:** o mesmo problema já estava registado em
  `docs/plans/observabilidade-logging-backend-crm-melhorias-futuras.md`
  (item M1, descoberto durante debug de `fix-qualification-score-gate-mode-off`,
  30/08/2026) — este item é resolvido por esta implementação.

---

## Abordagem

```
app.py (arranque)
  → load_dotenv()
  → setup_logging(os.getenv("LOG_LEVEL", "INFO"))   # novo, logging_setup.py
  → resto dos imports (routes/services) — loggers já criados por eles
    (via logging.getLogger(__name__)) propagam para o root já configurado
```

`setup_logging()` substitui `root.handlers` por um único `StreamHandler` com
formatter simples (`timestamp LEVEL logger.name mensagem`) e define
`root.setLevel(level)`. Como todo `logger.info(...)` do código já usa
`logging.getLogger(__name__)` (propaga para o root por padrão), não é preciso
tocar em nenhum dos 26 arquivos que já chamam `logger.info(...)` — a
mudança é centralizada no arranque da app.

---

## Plano de Implementação

### Fase 1 — Configurar root logger

**Objetivo:** fazer `logger.info(...)` aparecer nos logs (local e produção).

| Arquivo | O que muda |
|---|---|
| `backend-crm/logging_setup.py` | Novo. `setup_logging(level: str)` — StreamHandler + formatter, aplica no root logger. |
| `backend-crm/app.py` | Chama `setup_logging(os.getenv("LOG_LEVEL", "INFO"))` logo após `load_dotenv()`, antes dos imports de `routes`/`services`. |
| `backend-crm/.env.example` | Nova seção "LOGGING" documentando `LOG_LEVEL=INFO`. |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `4df7db4` | `logging_setup.py` novo + chamada em `app.py` + `.env.example` documentado |

### Relatório da Fase 1 — o que mudou na prática

**Antes:** os logs de negócio (`logger.info(...)`) do backend-crm — mudança de
categoria de lead, decisões de follow-up, eventos de webhook do WhatsApp, etc.
— nunca apareciam nem localmente nem em produção (Railway), mesmo forçando
`uvicorn --log-level info`. Só apareciam os logs automáticos do próprio
uvicorn (ex.: `INFO: GET /api/leads ...`).

**Agora:** o `backend-crm` configura o logger raiz no arranque da aplicação.
Todo `logger.info(...)` já existente no código passa a aparecer no terminal
(local) e nos logs do Railway (produção), com o nível controlável pela
variável de ambiente `LOG_LEVEL` (default `INFO`).

**Para validar:** Cenários C1 e C2 já validados nesta sessão (ver abaixo).
Cenário C3 (produção) fica pendente — depende de deploy.

---

## Checks de Validação

### Cenário C1 — Root logger emite INFO (unitário, sem app completa)
- [x] Rodar `python -c "..."` importando `logging_setup.setup_logging` e
  confirmar: antes de chamar `setup_logging('INFO')`, `logger.info(...)` não
  produz saída; depois de chamar, `logger.info(...)` e `logger.warning(...)`
  aparecem formatados (`timestamp LEVEL logger.name mensagem`).
  **Validado em:** 02/09/2026 — confirmado exatamente esse comportamento.

### Cenário C2 — App real, ambiente local
- [x] Rodar `uvicorn app:app` localmente (`.venv` criado e dependências
  instaladas nesta sessão) sem passar `--log-level`.
- [x] Disparar uma ação que já loga em INFO hoje — os schedulers de
  arranque (`_reconciler_loop`, `_spy_reconciler_loop`,
  `_spy_media_worker_loop`, `_knowledge_ingest_worker_loop`) logam
  imediatamente no startup, sem precisar de request externo.
- [x] Confirmar que a linha aparece no terminal com o novo formato.
  **Validado em:** 02/09/2026 — saída real do startup:
  ```
  2026-09-02 16:54:01,705 INFO app [reconciler] scheduler iniciado — intervalo=60s startup_delay=5s
  2026-09-02 16:54:01,705 INFO app [spy_reconciler] scheduler iniciado — intervalo=60s
  2026-09-02 16:54:01,705 INFO app [spy_media_worker] scheduler iniciado — intervalo=30s
  2026-09-02 16:54:01,706 INFO app [knowledge_ingest_worker] scheduler iniciado — intervalo=10s
  ```
  Antes desta mudança, nenhuma dessas linhas aparecia — só os logs
  automáticos do próprio uvicorn (`INFO:     Started server process...`).

### Cenário C3 — Produção (Railway)
- [x] Após deploy, os logs de produção devem mostrar linhas de negócio que
  antes não apareciam.
  **Validado em:** 02/09/2026 — `railway logs -s backend-crm --since 2h
  --filter "scheduler"` retornou:
  ```
  2026-09-02 16:05:42,747 INFO app [reconciler] scheduler iniciado — intervalo=60s startup_delay=5s
  2026-09-02 16:05:42,748 INFO app [spy_reconciler] scheduler iniciado — intervalo=60s
  2026-09-02 16:05:42,748 INFO app [spy_media_worker] scheduler iniciado — intervalo=30s
  2026-09-02 16:05:42,748 INFO app [knowledge_ingest_worker] scheduler iniciado — intervalo=10s
  ```
  Timestamp coincide com o deploy. Confirmado também que logs de terceiros
  (`httpx`) já apareciam em INFO — o que motivou a Fase 2 abaixo.

---

## Fase 2 — Silenciar httpx (02/09/2026)

### Problema identificado

Ao validar o Cenário C3, os logs de produção mostraram que o `httpx` também
passou a logar em `INFO` uma linha `HTTP Request: ...` por chamada externa
(UazAPI, OpenAI, backend-core) — isso já estava sinalizado como risco
conhecido na Fase 1 ("Ajustes Possíveis"), e o volume real em produção
confirmou o problema: linhas repetidas a cada poucos segundos só pelas
checagens de auth (`GET /users/me`, `GET /me/entitlements`), afogando os
logs de negócio que eram o objetivo desta implementação.

### Correção

`setup_logging()` agora também fixa `logging.getLogger("httpx").setLevel
(logging.WARNING)` — mantém erros de rede visíveis, remove o ruído de
requisições bem-sucedidas.

| Arquivo | Mudança |
|---|---|
| `backend-crm/logging_setup.py` | Adicionada `logging.getLogger("httpx").setLevel(logging.WARNING)` dentro de `setup_logging()`. |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | _(a preencher após commit)_ | Silenciar `httpx` para `WARNING` em `setup_logging()` |

### Relatório da Fase 2 — o que mudou na prática

**Antes:** com o root logger em `INFO` (Fase 1), o `httpx` também passou a
logar uma linha por cada chamada HTTP externa bem-sucedida — volume alto,
sem valor de diagnóstico na maioria dos casos.

**Agora:** `httpx` só loga em `WARNING` ou acima (erros de rede, por
exemplo) — os logs de negócio ficam limpos e legíveis.

**Para validar:** Cenário C4, abaixo — testado unitariamente nesta sessão.

### Cenário C4 — httpx silenciado, logs de negócio intactos (unitário)
- [x] Após `setup_logging('INFO')`: `logging.getLogger('httpx').info(...)`
  não produz saída; `logging.getLogger('httpx').warning(...)` aparece
  normalmente; `logging.getLogger('somemodule').info(...)` (simulando um
  logger de negócio) continua aparecendo sem alteração.
  **Validado em:** 02/09/2026 — confirmado exatamente esse comportamento.
