# Limpeza/expiração automática de uploads antigos

**Branch:** `feat/upload-limpeza-arquivos-antigos`
**Status:** Em andamento

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

---

## Checks de Validação

Lógica server-side pura, sem superfície de UI — validação via teste
automatizado (`unittest`), não via browser (MCP).

### Cenário A1 — Arquivo antigo é apagado
- [ ] Criar arquivo com `mtime` mais antigo que o limite configurado
- [ ] Rodar `cleanup_stale_uploads`
- [ ] Confirmar: arquivo foi removido e contabilizado em `deleted`

### Cenário A2 — Arquivo recente é mantido
- [ ] Criar arquivo com `mtime` recente (dentro do limite)
- [ ] Rodar `cleanup_stale_uploads`
- [ ] Confirmar: arquivo continua existindo

### Cenário A3 — Diretório de usuário vazio é removido
- [ ] Diretório de usuário só com arquivos antigos
- [ ] Rodar `cleanup_stale_uploads`
- [ ] Confirmar: diretório do usuário foi removido após ficar vazio

### Cenário A4 — Pasta base inexistente não gera erro
- [ ] Rodar `cleanup_stale_uploads` sem `data/uploads/ai` existir
- [ ] Confirmar: retorna contadores zerados, sem exceção

---

## Ajustes Possíveis Pós-Implementação

- Race condition teórica (arquivo apagado no meio de um `/processar` muito
  demorado) — risco desprezível com o default de 24h; não mitigado
  propositalmente (ver plano aprovado).
