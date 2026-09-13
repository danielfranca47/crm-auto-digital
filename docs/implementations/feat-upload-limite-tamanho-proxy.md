# Middleware de rejeição antecipada por Content-Length no upload de planilhas

**Branch:** `feat/upload-limite-tamanho-proxy`
**Status:** Em andamento

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`fix-upload-planilhas-sem-auth.md`. O limite de tamanho de upload
(`MAX_UPLOAD_BYTES = 10MB`, em `backend-crm/routes/uploads.py`) só é aplicado hoje na
camada da aplicação, via leitura em streaming (chunk a chunk) dentro da própria rota
`POST /api/uploads`.

A ideia original era reforçar esse limite também numa camada de proxy/infra
(`client_max_body_size` do nginx). **Diagnóstico:** isso não é viável sem uma migração
de infra desproporcional para o ganho. `backend-crm` roda na Railway via `Procfile` +
Nixpacks, sem `Dockerfile`; a Railway **não** tem nenhum equivalente a
`client_max_body_size` — confirmado e já documentado em
`docs/architecture/_mapa-sistema.md`, seção "Limites de rede/proxy (Railway)". Fazer
isso de verdade exigiria trocar o deploy actual por um container Docker customizado com
nginx/Caddy na frente — risco e esforço bem maiores que o ganho aqui, especialmente
porque a proteção real contra o risco original (esgotar disco com uploads grandes ou
repetidos) **já existe**: o corte em streaming já implementado nunca deixa a aplicação
gravar mais que 10MB em disco.

**Decisão (validada com o utilizador):** em vez da rota de infra, implementar um
middleware ASGI leve no próprio `backend-crm` que olha o header `Content-Length` da
requisição **antes** dela chegar à rota (e antes até do `Depends(require_crm_access)`) e
rejeita com `413` imediatamente quando o valor declarado excede o limite — evitando gastar
ciclos abrindo a conexão/lendo a rota para requests obviamente grandes demais, sem exigir
nenhuma mudança de infra.

Comportamento desejado: um request de upload que já declara, no próprio header, um
tamanho maior que o limite é rejeitado imediatamente, sem entrar na rota. Isto é um
reforço marginal (fail-fast para clientes bem-comportados que declaram `Content-Length`
correto) — **não substitui** o corte em streaming já existente, que continua sendo a
defesa real contra uploads sem `Content-Length`/chunked ou com header incorreto.

---

## Área do sistema

`backend-crm` — `routes/uploads.py` (novo middleware), `app.py` (registro do middleware).

---

## Abordagem

```
POST /api/uploads
  → UploadContentLengthGuardMiddleware.dispatch() [roda antes de qualquer Depends]
      ├─ path != /api/uploads OU método != POST → passa direto (call_next)
      ├─ sem header Content-Length → passa direto (corte em streaming da rota decide)
      ├─ Content-Length ≤ MAX_UPLOAD_BYTES + margem → passa direto
      └─ Content-Length > MAX_UPLOAD_BYTES + margem → 413 imediato, rota nunca roda
  → (se passou) require_crm_access → leitura em streaming com corte (já existente)
```

---

## Plano de Implementação

### Fase 1 — Middleware de guarda por Content-Length

**Objetivo:** rejeitar com `413`, antes da rota rodar, requests de upload cujo
`Content-Length` já declara um tamanho acima do limite.

| Arquivo | O que muda |
|---|---|
| `backend-crm/routes/uploads.py` | Nova constante `CONTENT_LENGTH_GUARD_MARGIN`; nova classe `UploadContentLengthGuardMiddleware(BaseHTTPMiddleware)` |
| `backend-crm/app.py` | Importa e registra `UploadContentLengthGuardMiddleware` via `app.add_middleware(...)`, ao lado do `CORSMiddleware` existente |
| `backend-crm/tests/test_uploads_content_length_guard.py` (novo) | Testes do middleware isolado via Starlette `TestClient` |

```python
# routes/uploads.py — adicionado ao lado de MAX_UPLOAD_BYTES
CONTENT_LENGTH_GUARD_MARGIN = 64 * 1024  # folga p/ overhead de headers/boundary do multipart

class UploadContentLengthGuardMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == "POST" and request.url.path == "/api/uploads":
            content_length = request.headers.get("content-length")
            if content_length is not None:
                try:
                    declared = int(content_length)
                except ValueError:
                    declared = None
                if declared is not None and declared > MAX_UPLOAD_BYTES + CONTENT_LENGTH_GUARD_MARGIN:
                    return JSONResponse(
                        {"detail": f"Arquivo excede o limite de {MAX_UPLOAD_BYTES // (1024*1024)}MB"},
                        status_code=413,
                    )
        return await call_next(request)
```

```python
# app.py — registrado junto ao CORSMiddleware (linha ~266)
from routes.uploads import UploadContentLengthGuardMiddleware
...
app.add_middleware(UploadContentLengthGuardMiddleware)
```

Escopo deliberadamente restrito a `POST /api/uploads` (`request.url.path`) — nenhum
outro endpoint do backend-crm recebe upload de arquivo.

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `2735f37` | Middleware `UploadContentLengthGuardMiddleware` + registro em `app.py` + 4 testes isolados |

**Detalhes do commit `2735f37`:**
- `backend-crm/routes/uploads.py` — nova constante `CONTENT_LENGTH_GUARD_MARGIN` (64KB) e classe `UploadContentLengthGuardMiddleware`, que intercepta `POST /api/uploads` e rejeita com `413` antes de qualquer `Depends` rodar, quando `Content-Length` > `MAX_UPLOAD_BYTES + margem`
- `backend-crm/app.py` — `app.add_middleware(uploads.UploadContentLengthGuardMiddleware)` ao lado do `CORSMiddleware` existente
- `backend-crm/tests/test_uploads_content_length_guard.py` (novo) — 4 testes contra uma app Starlette mínima isolada (não sobe o `app` completo do CRM): rejeita acima do limite, aceita dentro do limite, não bloqueia request sem `Content-Length`, não afeta outros paths

### Relatório da Fase 1 — o que mudou na prática

**Antes:** um upload maior que 10MB só era rejeitado depois de o processo Python
começar a ler o arquivo em streaming e contar os bytes até estourar o limite — a
conexão já tinha sido aceite e a rota já estava rodando (incluindo checar o token de
autenticação).

**Agora:** se o cliente já declara, no próprio header `Content-Length`, um tamanho
maior que o limite, a resposta `413` volta imediatamente, antes até de checar o
login — sem gastar nenhum ciclo lendo bytes do arquivo. Uploads sem esse header (ou
com o header errado) continuam protegidos do mesmo jeito de antes, pelo corte em
streaming dentro da rota.

**Para validar:** Cenários P1, P2, C1 e C2, abaixo.

---

## Checks de Validação

### Cenário P1 — Content-Length acima do limite é rejeitado antes da rota
- [ ] `POST /api/uploads` com header `Content-Length` acima de `MAX_UPLOAD_BYTES + margem` (sem token, sem body real)
- [ ] Confirmar: `413` imediato, `{"detail":"Arquivo excede o limite de 10MB"}`

### Cenário P2 — Upload normal continua funcionando
- [ ] `POST /api/uploads` autenticado, arquivo válido dentro do limite
- [ ] Confirmar: `200`, `upload_id` retornado (comportamento inalterado)

### Cenário C1 — Sem header Content-Length não é bloqueado pelo middleware
- [ ] `POST /api/uploads` com `Transfer-Encoding: chunked` (sem `Content-Length`), acima do limite
- [ ] Confirmar: middleware deixa passar; corte acontece no streaming da rota (já validado em `fix-upload-planilhas-sem-auth.md`, Cenário C1), não no middleware

### Cenário C2 — Outros endpoints não são afetados
- [ ] Requisição com `Content-Length` grande para outro path (ex.: `/api/leads`)
- [ ] Confirmar: middleware não intercepta — passa direto para a rota normal
