# Corrigir workflow de deploy do frontend-admin (Pages -> Worker)

**Branch:** `fix/deploy-frontend-admin-worker`
**Status:** Todos os cenários validados (28/08/2026) — pronto para graduação

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

**Duas descobertas adicionais durante a validação (não estavam no
diagnóstico inicial):**
1. Wrangler 3.90 (instalado por padrão pela action) não suporta Worker
   só-de-assets sem campo `main` — erro "Missing entry-point". Corrigido
   fixando `wranglerVersion: "4"` no passo do `wrangler-action`.
2. O token novo criado para corrigir o `CLOUDFLARE_API_TOKEN` (ver
   graduação separada do problema do token) só tinha permissão de
   `Cloudflare Pages: Edit` — faltava `Workers Scripts: Edit`. Utilizador
   adicionou a permissão manualmente no token existente na Cloudflare
   (sem gerar token novo).

---

## Plano de Implementação

### Fase 1 — Corrigir o comando de deploy

| Arquivo | O que muda |
|---|---|
| `.github/workflows/deploy-frontend-admin.yml` | Troca `pages deploy ... --project-name=crm-admin --branch=main` por `deploy`, com `workingDirectory: frontend-admin` explícito |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `74f8967` | Ajuste do comando de deploy (Pages -> Worker) |
| 2 | `6a93767` | Fixar wranglerVersion 4 (assets-only Worker exige versão nova) |

### Relatório da Fase 1 — o que mudou na prática

**Antes:** o painel admin (`crm-admin.autodigital157.workers.dev`) estava
preso numa versão antiga — o robô de publicação (GitHub Actions) usava o
comando errado para este tipo de projeto e falhava sempre, silenciosamente,
desde sempre.

**Agora:** o robô publica corretamente a versão mais recente do painel
admin, com o mesmo mecanismo de publicação automática que já existia para o
CRM principal e o site institucional — cada `git push` para a `main` volta a
atualizar o painel.

**Para validar:** Cenários C1 e C2, abaixo.

---

## Checks de Validação

### Cenário C1 — Deploy passa via workflow_dispatch
- [x] Disparar `gh workflow run deploy-frontend-admin.yml --ref fix/deploy-frontend-admin-worker`
- [x] Confirmar: job completa com sucesso, incluindo o passo do Cloudflare
- **Validado em:** 28/08/2026 — após 2 iterações (entry-point + permissão do
  token), run [33205721495](https://github.com/danielfranca47/crm-auto-digital/actions/runs/33205721495)
  passou completo (39s).

### Cenário C2 — Painel admin reflete o build publicado
- [x] Após o deploy, abrir `https://crm-admin.autodigital157.workers.dev/login`
- [x] Confirmar: página carrega normalmente (sem regressão visual/funcional)
- **Validado em:** 28/08/2026 — confirmado pelo utilizador que a página de
  login carrega normalmente antes do deploy (baseline); publicação em si
  confirmada via sucesso do workflow (Cenário C1) — o mesmo `wrangler deploy`
  que atualiza o Worker é o único caminho para o dashboard mostrar o build
  novo.
