# Deploy para Cloudflare (frontend-crm, frontend-admin, website)

Os 3 frontends publicam automaticamente a cada `git push` para `main`, via
GitHub Actions (`.github/workflows/deploy-*.yml`). Todos usam o mesmo
segredo `CLOUDFLARE_API_TOKEN` (GitHub → Settings → Secrets and variables →
Actions).

---

## Tipos de projeto (não são todos iguais)

| Serviço | Tipo Cloudflare | Nome do projeto/worker | Comando wrangler |
|---|---|---|---|
| `frontend-crm` | Pages | `crm-app` | `pages deploy frontend-crm/dist --project-name=crm-app` |
| `website` | Pages | `crm-website` | `pages deploy website/dist --project-name=crm-website` |
| `frontend-admin` | **Worker** (assets estáticos, sem `main`) | `crm-admin` | `deploy` (lê `frontend-admin/wrangler.jsonc`) |

`frontend-admin` é diferente dos outros dois — é um Worker com assets
estáticos (`frontend-admin/wrangler.jsonc`), não um projeto Pages. O comando
de deploy tem de ser `wrangler deploy`, não `wrangler pages deploy`. Um
Worker deste tipo (sem campo `main`) exige `wranglerVersion: "4"` no passo
do `cloudflare/wrangler-action@v3` — versões antigas (3.x) falham com
"Missing entry-point".

**Permissões necessárias no `CLOUDFLARE_API_TOKEN`:** `Cloudflare Pages:
Edit` (para `crm-app`/`crm-website`) **e** `Workers Scripts: Edit` (para
`crm-admin`) — um token só com permissão de Pages falha o deploy do
`frontend-admin` com erro de autenticação (código 10000), mesmo sendo um
token válido.

---

## Acesso protegido — painel admin (Cloudflare Access)

`crm-admin.autodigital157.workers.dev` está protegido por **Cloudflare
Access** (Zero Trust, plano Free) — antes de chegar à página de login da
aplicação (o "Segredo de acesso"), é preciso passar por um ecrã da própria
Cloudflare que pede um email autorizado e envia um código de acesso único
(One-Time PIN) para esse email.

**Configurado em:** Cloudflare dashboard → conta → **Zero Trust → Access
controls → Applications** → aplicação "CRM Admin" (tipo Self-hosted,
destino `crm-admin.autodigital157.workers.dev` via separador "Workers", não
"Public DNS" — não foi preciso domínio próprio).

**Política atual:** "Só eu" — `Allow` só para o email
`autodigital157@gmail.com`.

**Para adicionar outro email autorizado:** Zero Trust → Access controls →
Applications → "CRM Admin" → editar a política "Só eu" → acrescentar mais
uma linha de "Include" (Emails) com o novo endereço.
