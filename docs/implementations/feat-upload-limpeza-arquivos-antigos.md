# Limpeza/expiração automática de uploads antigos

**Branch:** `feat/upload-limpeza-arquivos-antigos`
**Status:** Todos os cenários validados (13/09/2026)

---

## Motivação

Desde `fix-upload-planilhas-sem-auth.md`, cada upload de planilha (fluxo de
importação de leads do Assistente IA) fica isolado por usuário em
`data/uploads/ai/{user_id}/{uuid}.{ext}`, mas nenhuma rotina apaga esses
arquivos depois — eles são temporários por natureza (usados só durante o
fluxo de upload → preview → processar) e crescem indefinidamente em disco.

Comportamento desejado: uma rotina periódica apaga arquivos de upload
suficientemente antigos, sem depender de rastrear se já foram "processados"
(hoje não existe nenhum registro em banco do upload).

---

## Problemas Identificados (estado anterior)

1. **Uploads nunca são apagados:** `routes/uploads.py` grava o arquivo em
   `BASE / {user_id} / {uuid}.{ext}` (`routes/uploads.py:15-16,86-89`) e nada
   no sistema jamais remove esse arquivo — nem `routes/assistente_ia.py`
   (`/preview` e `/processar`, que só leem o arquivo), nem nenhum worker
   periódico existente.

---

## Abordagem

Worker periódico assíncrono, seguindo o mesmo padrão já usado pelos outros
loops de `app.py` (`_reconciler_loop`, `_spy_media_worker_loop`, etc.):
varre `data/uploads/ai/<user_id>/*`, apaga arquivos com `mtime` mais antigo
que um limite configurável, e remove diretórios de usuário que ficarem
vazios.

```
Loop periódico (a cada UPLOAD_CLEANUP_INTERVAL_SECONDS)
  → cleanup_stale_uploads(max_age_hours=UPLOAD_MAX_AGE_HOURS)
      ├─ arquivo com mtime > limite → apaga
      ├─ diretório de usuário vazio após limpeza → remove
      └─ erro num arquivo individual → conta em "errors", segue para os demais
```

Limpeza por **idade do arquivo**, não por "já processado" — decisão
detalhada no plano aprovado (ver commit da Fase 1): não há hoje nenhum
registro em banco do upload, e o mesmo `upload_id` é legitimamente lido mais
de uma vez no fluxo real (preview → ajustar column_map → preview de novo →
processar), então apagar "logo após processar" arriscaria quebrar esse
fluxo. Idade cobre tanto uploads processados com sucesso quanto abandonados
no meio do fluxo.

---

## Plano de Implementação

### Fase 1 — Worker de limpeza periódica

**Objetivo:** apagar automaticamente uploads antigos sem exigir intervenção manual.

| Arquivo | O que muda |
|---|---|
| `backend-crm/services/upload_cleanup.py` | Novo — `cleanup_stale_uploads(max_age_hours)` |
| `backend-crm/app.py` | Novo `_upload_cleanup_loop()` + registro em `lifespan()` |
| `backend-crm/tests/test_upload_cleanup.py` | Novo — testes automatizados |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `a8528e8` | Worker de limpeza periódica + testes |

**Detalhes do commit `a8528e8`:**
- `services/upload_cleanup.py` — `cleanup_stale_uploads(max_age_hours)`: varre
  `data/uploads/ai/<user_id>/*`, apaga arquivos com `mtime` além do limite,
  remove diretório de usuário se ficar vazio, conta erros individuais sem
  interromper o loop
- `app.py` — novo `_upload_cleanup_loop()` (mesmo padrão dos outros workers:
  `asyncio.sleep` + `while True` + `asyncio.to_thread` + log + stagger de
  startup), registrado em `lifespan()`; env vars
  `UPLOAD_CLEANUP_INTERVAL_SECONDS` (default 3600s) e `UPLOAD_MAX_AGE_HOURS`
  (default 24h)
- `tests/test_upload_cleanup.py` — 5 testes cobrindo os 4 cenários abaixo

### Relatório da Fase 1 — o que mudou na prática

**Antes:** os arquivos de planilha enviados para importar leads ficavam
salvos no servidor para sempre — nada os apagava, mesmo depois de já terem
sido usados ou abandonados.

**Agora:** a cada hora, o sistema verifica automaticamente esses arquivos e
apaga os que têm mais de 24h, liberando espaço em disco sem precisar de
intervenção manual.

**Para validar:** Cenários A1–A4, abaixo — já executados via teste
automatizado (`pytest`), sem necessidade de teste via browser (é lógica
interna do servidor, sem tela).

---

## Checks de Validação

Lógica server-side pura, sem superfície de UI — validação via teste
automatizado (`unittest`), não via browser (MCP).

### Cenário A1 — Arquivo antigo é apagado
- [x] Criar arquivo com `mtime` mais antigo que o limite configurado
- [x] Rodar `cleanup_stale_uploads`
- [x] Confirmar: arquivo foi removido e contabilizado em `deleted`
- **Validado em:** 13/09/2026 — `pytest tests/test_upload_cleanup.py::UploadCleanupTest::test_old_file_is_deleted` (PASSED)

### Cenário A2 — Arquivo recente é mantido
- [x] Criar arquivo com `mtime` recente (dentro do limite)
- [x] Rodar `cleanup_stale_uploads`
- [x] Confirmar: arquivo continua existindo
- **Validado em:** 13/09/2026 — `pytest tests/test_upload_cleanup.py::UploadCleanupTest::test_recent_file_is_kept` (PASSED)

### Cenário A3 — Diretório de usuário vazio é removido
- [x] Diretório de usuário só com arquivos antigos
- [x] Rodar `cleanup_stale_uploads`
- [x] Confirmar: diretório do usuário foi removido após ficar vazio
- **Validado em:** 13/09/2026 — `pytest tests/test_upload_cleanup.py::UploadCleanupTest::test_empty_user_dir_is_removed_after_cleanup` (PASSED), incluindo caso complementar `test_user_dir_kept_when_a_recent_file_remains` (diretório mantido quando sobra arquivo recente)

### Cenário A4 — Pasta base inexistente não gera erro
- [x] Rodar `cleanup_stale_uploads` sem `data/uploads/ai` existir
- [x] Confirmar: retorna contadores zerados, sem exceção
- **Validado em:** 13/09/2026 — `pytest tests/test_upload_cleanup.py::UploadCleanupTest::test_missing_base_dir_returns_zeroed_counters_without_error` (PASSED)

---

## Ajustes Possíveis Pós-Implementação

- Race condition teórica (arquivo apagado no meio de um `/processar` muito
  demorado) — risco desprezível com o default de 24h; não mitigado
  propositalmente (ver plano aprovado).
