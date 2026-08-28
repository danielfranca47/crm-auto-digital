# Adicionar origem CORS do painel admin (workers.dev) no backend-core

**Branch:** `fix/cors-admin-workers-dev`
**Status:** Em andamento

---

## Motivação

Após corrigir o deploy do `frontend-admin` (ver `fix-deploy-frontend-admin-worker.md`,
já graduado) e proteger o acesso via Cloudflare Access, o utilizador tentou
fazer login no painel e recebeu `400 Bad Request` no preflight `OPTIONS
/admin/login`.

Causa raiz: `backend-core/app/main.py` tem a lista de origens CORS
hardcoded, e inclui `https://admin.danielfranca.pt` (o domínio próprio
originalmente pretendido para o painel admin) — mas esse domínio não está
configurado ainda (tentativa de o vincular ao Worker falhou por já ter
registos DNS externos, a investigar separadamente). O painel está
atualmente a correr em `https://crm-admin.autodigital157.workers.dev`, que
não estava na lista — o browser bloqueia o pedido antes de chegar à
verificação da senha.

---

## Problemas Identificados (estado anterior)

1. **Origem CORS em falta:** `backend-core/app/main.py:13-31` — lista
   `origins` não incluía `https://crm-admin.autodigital157.workers.dev`,
   bloqueando todos os pedidos do painel admin em produção (não só o
   login — qualquer chamada à API do core a partir desse domínio).

---

## Abordagem

Adicionar `https://crm-admin.autodigital157.workers.dev` à lista `origins`
existente em `backend-core/app/main.py`. Mantém `admin.danielfranca.pt` na
lista para quando o domínio próprio for configurado — não é mutuamente
exclusivo.

**Nota separada (fora do escopo deste fix):** `backend-crm` também tem uma
lista de origens CORS (`PRIVATE_ORIGINS`), mas essa é uma variável de
ambiente (não hardcoded no código) — configurada directamente no Railway.
Se o painel admin também chamar `backend-crm` (ex.: `routes/admin_agents.py`)
e voltar a bater em CORS, será preciso acrescentar lá também, directamente
no Railway (fora do escopo de um commit de código).

---

## Plano de Implementação

### Fase 1 — Adicionar a origem em falta

| Arquivo | O que muda |
|---|---|
| `backend-core/app/main.py` | Acrescenta `https://crm-admin.autodigital157.workers.dev` à lista `origins` |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | _(a preencher)_ | Adicionar origem CORS do painel admin |

---

## Checks de Validação

### Cenário C1 — Login no painel admin funciona em produção
- [ ] Após deploy do backend-core (Railway), tentar login em
      `https://crm-admin.autodigital157.workers.dev/login`
- [ ] Confirmar: sem erro de CORS na consola, login com a senha correta
      completa com sucesso
