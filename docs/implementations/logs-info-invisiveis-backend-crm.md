# Logs INFO invisíveis em todo o backend-crm

**Branch:** `worktree-fix+logs-info-invisiveis-backend-crm`
**Status:** Em andamento

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

---

## Checks de Validação

### Cenário C1 — Root logger emite INFO (unitário, sem app completa)
- [ ] Rodar `python -c "..."` importando `logging_setup.setup_logging` e
  confirmar: antes de chamar `setup_logging('INFO')`, `logger.info(...)` não
  produz saída; depois de chamar, `logger.info(...)` e `logger.warning(...)`
  aparecem formatados (`timestamp LEVEL logger.name mensagem`).

### Cenário C2 — App real, ambiente local
- [ ] Rodar `uvicorn app:app --port 8000` localmente (com `.venv` e
  dependências instaladas) sem passar `--log-level`.
- [ ] Disparar uma ação que já loga em INFO hoje (ex.: tick do reconciler de
  follow-up, ou webhook inbound do WhatsApp).
- [ ] Confirmar que a linha aparece no terminal com o novo formato.

### Cenário C3 — Produção (Railway)
- [ ] Após deploy, `railway logs -s backend-crm --filter "lead_category"` (ou
  evento de negócio equivalente) deve retornar linhas que hoje não aparecem.

---

## Ajustes Possíveis Pós-Implementação

- **Bibliotecas de terceiros barulhentas (`httpx`, `openai`):** com o root em
  `INFO`, `httpx` loga uma linha `HTTP Request: ...` por chamada (UazAPI,
  OpenAI). `backend-executors` já roda assim e não silencia essas libs — por
  consistência, esta implementação também não silencia. Se o volume em
  produção for excessivo, ajustar depois com
  `logging.getLogger("httpx").setLevel(logging.WARNING)`.
