# Corrigir workflow de deploy do frontend-admin (Pages -> Worker)

**Branch:** `fix/deploy-frontend-admin-worker`
**Status:** Em andamento

---

## Motivação

Durante a investigação do `CLOUDFLARE_API_TOKEN` inválido (corrigido
separadamente), descobriu-se que o deploy do `frontend-admin` falhava com
`Project not found` ao tentar `wrangler pages deploy --project-name=crm-admin`.

Causa raiz: `crm-admin` não é um projeto Cloudflare **Pages** — é um
Cloudflare **Worker com assets estáticos** (`frontend-admin/wrangler.jsonc`
já define `"name": "crm-admin"` com `"assets": {"directory": "./dist", ...}`),
confirmado no dashboard da Cloudflare (ícone de Worker, domínio
`crm-admin.autodigital157.workers.dev`, já a servir a página de login real do
painel admin). O workflow `.github/workflows/deploy-frontend-admin.yml`
estava a usar o comando errado (`pages deploy`) para este tipo de recurso.

O painel está no ar, mas parado numa versão antiga — publicado manualmente
em algum momento no passado (utilizador não lembra quando), sem receber
atualizações automáticas desde então, porque o workflow nunca funcionou
para este projeto.

---

## Problemas Identificados (estado anterior)

1. **Comando errado no workflow:**
   `.github/workflows/deploy-frontend-admin.yml:38` — `command: pages deploy
   frontend-admin/dist --project-name=crm-admin --branch=main` falha com
   `Project not found. The specified project name does not match any of your
   existing projects. [code: 8000007]`, porque `crm-admin` é um Worker, não
   um projeto Pages.

---

## Abordagem

Trocar o comando para `deploy` (Workers deploy simples), que lê
automaticamente `frontend-admin/wrangler.jsonc` (já correto) e publica os
assets estáticos configurados lá — igual ao que provavelmente foi feito
manualmente da última vez. Necessário passar `workingDirectory:
frontend-admin` explicitamente no passo do `wrangler-action` (o
`defaults.run.working-directory` do job só se aplica a passos `run:`, não a
`uses:`).

---

## Plano de Implementação

### Fase 1 — Corrigir o comando de deploy

| Arquivo | O que muda |
|---|---|
| `.github/workflows/deploy-frontend-admin.yml` | Troca `pages deploy ... --project-name=crm-admin --branch=main` por `deploy`, com `workingDirectory: frontend-admin` explícito |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | _(a preencher)_ | Ajuste do comando de deploy (Pages -> Worker) |

---

## Checks de Validação

### Cenário C1 — Deploy passa via workflow_dispatch
- [ ] Disparar `gh workflow run deploy-frontend-admin.yml --ref fix/deploy-frontend-admin-worker`
- [ ] Confirmar: job completa com sucesso, incluindo o passo do Cloudflare

### Cenário C2 — Painel admin reflete o build publicado
- [ ] Após o deploy, abrir `https://crm-admin.autodigital157.workers.dev/login`
- [ ] Confirmar: página carrega normalmente (sem regressão visual/funcional)
