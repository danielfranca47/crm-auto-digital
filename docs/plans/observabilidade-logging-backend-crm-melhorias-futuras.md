# Observabilidade — logging ausente no backend-crm

> Contexto: encontrado durante o diagnóstico de
> `fix-qualification-score-gate-mode-off` (30/08/2026) — ao tentar usar
> `railway logs -s backend-crm` para rastrear uma mudança de categoria de
> lead em produção, nenhum log de negócio apareceu, só os logs automáticos
> do `uvicorn`.

## M1 — Configurar logging real no backend-crm

**Prioridade: MÉDIA**

`backend-crm` nunca chama `logging.basicConfig()` nem configura nenhum
handler (confirmado por grep — zero ocorrências de `basicConfig`/
`StreamHandler` em todo o serviço). Sem handler configurado no logger raiz,
todo `logger.info(...)` emitido por módulos como `services/jobs_service.py`
(`lead_category_skip`, `lead_category_updated`,
`lead_category_blocked_incomplete_qualification`) é descartado
silenciosamente — não aparece em `railway logs -s backend-crm`, nem com
`--filter`.

Na prática, hoje só os logs automáticos do `uvicorn`
(`INFO:     GET /api/leads ...`) aparecem — qualquer log de decisão de
negócio (mudança de categoria, guardrails aplicados, etc.) é invisível,
tornando impossível depurar um caso real de produção sem reproduzir
manualmente no Playground (que já expõe `decision_trace` completo na
resposta, mas exige repetir a conversa passo a passo).

**Correção proposta:** adicionar uma função de setup de logging (mesmo
padrão já usado em `backend-executors/app/core/logging.py` —
`StreamHandler` + formatter estruturado com `job_id`/`lead_id`/`user_id`
quando disponíveis) chamada no arranque do `backend-crm` (`app.py`), com
nível configurável via env var (`LOG_LEVEL`, default `INFO`).

**Cenário de validação (não executado):** após a correção, `railway logs -s
backend-crm --filter "lead_category"` deve retornar as linhas de
`apply_suggested_category()` para eventos reais em produção.
