# Fix: Playground devolve 502 — "Connection refused" ao contactar backend-executors

**Branch:** `main`
**Status:** Em andamento — causa raiz ainda não confirmada

---

## Motivação

Em produção (Railway), ao enviar uma mensagem no Playground (`frontend-crm`), o pedido
`POST /api/playground/chat` no `backend-crm` devolve sempre **502 Bad Gateway** com:

```json
{"detail": "Falha ao contactar backend-executors: [Errno 111] Connection refused"}
```

O erro vem de `backend-crm/routes/playground.py:336-340`, que envolve qualquer
`httpx.RequestError` ao chamar `POST {EXECUTORS_BASE_URL}/api/internal/playground/decide`
(`backend-crm/routes/playground.py:321-328`). `Errno 111` é um erro de rede a nível de TCP —
indica que o pacote chegou a um host mas nada estava à escuta no destino (ou foi recusado
ativamente), não um problema de autenticação/token (esse daria uma mensagem diferente,
"Service token rejeitado").

`backend-executors` confirmadamente está online — `GET /health` no domínio público
(`https://backend-executors-production.up.railway.app/health`) sempre devolveu `200 OK`
durante toda a investigação.

---

## Problemas Identificados (estado anterior)

1. **Porta incorreta na variável** — `EXECUTORS_BASE_URL` no `backend-crm` usava a porta
   `8002` (valor de desenvolvimento local, de `.env.local`/`.env.example`), enquanto o
   Railway atribuía dinamicamente a porta `8080` ao processo `uvicorn` do `backend-executors`
   (confirmado via log: `Uvicorn running on http://0.0.0.0:8080`). **Corrigido** — não era a
   causa final, o erro persistiu mesmo com a porta certa.

2. **Domínio público vs. privado do Railway** — testado com `EXECUTORS_BASE_URL` apontando
   tanto para o domínio público (`https://backend-executors-production.up.railway.app`)
   quanto para o privado (`http://backend-executors.railway.internal:<porta>`). **Ambos
   falharam** com o mesmo erro, em várias combinações de porta.

3. **Bind IPv4-only do `backend-executors`** — o `Procfile` original usava
   `uvicorn app.main:app --host 0.0.0.0 --port $PORT` (só IPv4). A rede privada do Railway
   é IPv6. Tentativa de mudar para `--host ::` falhou no build (ver Fase 2). Depois de
   corrigido para escutar em IPv4 **e** IPv6 simultaneamente (dual-stack, ver Fase 3), o erro
   **persistiu** mesmo com o domínio privado configurado — eliminando IPv4/IPv6 como única
   causa.

---

## Abordagem

Investigação por eliminação, testando combinações de `EXECUTORS_BASE_URL` (domínio
público/privado, porta) cruzadas com a forma de bind do `backend-executors` (IPv4 / IPv6 /
dual-stack):

| # | `EXECUTORS_BASE_URL` | `backend-executors` escuta em | Resultado |
|---|---|---|---|
| 1 | público HTTPS | IPv4 só (`0.0.0.0`), porta 8080 | ❌ Connection refused |
| 2 | privado `:8080` | IPv4 só (`0.0.0.0`), porta 8080 | ❌ Connection refused |
| 3 | privado `:8002` | IPv4 só (`0.0.0.0`), porta 8002 | ❌ Connection refused |
| 4 | privado `:8002` | IPv6 só (`::` / `0:0:0:0:0:0:0:0`) | ⚠️ não testado — quebrou `/health` público, revertido antes de testar |
| 5 | público HTTPS | dual-stack (IPv4+IPv6) | ❌ Connection refused |
| 6 | privado `:8002` | dual-stack (IPv4+IPv6) | ❌ Connection refused |

Nenhuma combinação testada resolveu o problema. A hipótese de IPv4 vs. IPv6 explicava
parcialmente os sintomas mas o teste #6 (privado + dual-stack) refuta que seja a causa
única ou principal.

**Pista ainda não verificada:** nas configurações de rede do Railway (`Settings → Networking`)
existe uma secção/toggle **"Outbound IPv6"** ("Enable your service to make outbound
connections to IPv6 destinations") observada de forma incidental num print, na secção de
Private Networking. Este toggle é relativo ao serviço que **inicia** a chamada
(`backend-crm`), não ao que a recebe (`backend-executors`) — nunca foi verificado se está
ativo no `backend-crm`. Se estiver desligado, o `backend-crm` pode ser estruturalmente
incapaz de iniciar ligações de saída para qualquer destino IPv6 (privado ou público,
caso o DNS interno do Railway resolva ambos para o mesmo caminho IPv6) — o que seria
consistente com **todos** os resultados acima, incluindo o #6.

---

## Plano de Implementação

### Fase 1 — Corrigir porta da variável (sem código)

Apenas configuração Railway: `EXECUTORS_BASE_URL` corrigido de `:8002` para a porta real
detectada nos logs do `backend-executors`. Sem commit de código.

### Fase 2 — Bind em IPv6 (`--host ::`)

**Objetivo:** permitir que a rede privada do Railway (IPv6) alcance o `backend-executors`.

| Arquivo | O que muda |
|---|---|
| `backend-executors/Procfile` | `--host 0.0.0.0` → `--host ::` |

Build falhou: o sistema de build do Railway (Railpack) lê o `Procfile` como YAML, e `::`
(dois-pontos duplos) gera `Error reading Procfile as YAML: yaml: mapping values are not
allowed in this context`. Corrigido para a forma estendida `0:0:0:0:0:0:0:0` (equivalente a
`::`, sem colisão com o parser).

Build passou, mas o bind ficou **IPv6-only** neste runtime de container — `/health` no
domínio público (IPv4) passou a devolver `502 {"status":"error","message":"Application
failed to respond"}`. **Revertido para `0.0.0.0`** imediatamente para restaurar produção.

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `87de7e8` | fix: backend-executors escutar em `::` (build falhou, YAML) |
| 2 | `eb007dc` | fix: corrigir formato de host IPv6 (`0:0:0:0:0:0:0:0`) — build ok, mas IPv6-only |
| 3 | `1005b18` | revert: voltar a escutar em `0.0.0.0` (auto-commit do sistema) |

### Fase 3 — Dual-stack (dois sockets no mesmo processo)

**Objetivo:** escutar IPv4 e IPv6 simultaneamente sem depender do bind dual-stack do SO
(que não funciona neste runtime).

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/dualstack.py` | Novo entrypoint: arranca dois `uvicorn.Server` (um `host="0.0.0.0"`, outro `host="::"`) na mesma porta via `asyncio.gather` |
| `backend-executors/Procfile` | processo `web` passa a usar `python -m app.dualstack` em vez de invocar `uvicorn` diretamente |

```python
# backend-executors/app/dualstack.py
async def _serve() -> None:
    port = int(os.environ.get("PORT", "8002"))
    servers = [
        uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=port, log_level=log_level)),
        uvicorn.Server(uvicorn.Config(app, host="::", port=port, log_level=log_level)),
    ]
    await asyncio.gather(*(server.serve() for server in servers))
```

Deploy confirmado com sucesso, logs mostram os dois sockets activos:
```
Uvicorn running on http://0.0.0.0:8002
Uvicorn running on http://[::]:8002
```
`/health` público voltou a `200`. Apesar disso, com `EXECUTORS_BASE_URL` apontado para o
domínio privado, o erro de connection refused **persistiu** (teste #6 da tabela).

### Commits Fase 3

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `6c87cc9` | fix: backend-executors escutar em IPv4 e IPv6 simultaneamente (dual-stack) |

---

## Checks de Validação

### Cenário P1 — Playground envia mensagem e recebe resposta da IA
- [ ] Abrir Playground em produção, enviar mensagem de teste
- [ ] Confirmar: resposta da IA aparece sem erro 502
- **Pendente:** causa raiz ainda não identificada — todas as combinações testadas falharam

### Cenário C1 — `/health` público do backend-executors permanece estável
- [x] `curl https://backend-executors-production.up.railway.app/health` → `200`
- **Validado em:** 18/06/2026 — confirmado após cada deploy desta investigação

---

## Ajustes Possíveis Pós-Implementação / Próximos Passos

- **Verificar o toggle "Outbound IPv6" no `backend-crm`** (`Settings → Networking`) — pista
  não verificada que pode explicar por que tanto o domínio público quanto o privado falham
  da mesma forma.
- Caso o toggle esteja desligado e ligá-lo não resolva: considerar pedir suporte da Railway
  diretamente, citando que `GET /health` funciona externamente mas qualquer chamada
  server-to-server dentro do mesmo projeto (`backend-crm → backend-executors`) recebe
  `ECONNREFUSED`, independentemente do domínio (público/privado) ou da família de IP usada
  pelo destino.
- Alternativa de contorno caso a rede do Railway continue bloqueando: mover a lógica de
  `/api/internal/playground/decide` para dentro do próprio `backend-crm` (eliminando a
  chamada de rede entre serviços para este caminho específico) — maior invasão de
  arquitetura, considerar só se as opções de rede se esgotarem.
