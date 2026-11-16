# Colaborador corrige o código sozinho (skill configuracao-personalizada)

**Branch:** `worktree-feat+colaborador-corrige-codigo`
**Status:** Em andamento
**Autonomia:** manual

---

## Motivação

O Daniel quer que o Gabriel (colaborador, não técnico) configure **e corrija** o agente de um cliente sem
depender dele: sem Railway, sem autorizações do Daniel. O modo colaborador já faz a configuração, o
treinamento, os testes e a entrega; o que era código ia para o Daniel como pedido de correção, e as
categorias que sobem esperavam o "sim" do Daniel.

Confirmado: o deploy dos 4 serviços vem do push no `main` (GitHub), não do Railway; o Gabriel
(`volkhartcorp-lab`) tem `write` no repositório e o `main` só proíbe push forçado; os testes do
backend-crm passam sem `.env` (299). Sem `.env`, há falhas pré-existentes no core (exige `SECRET_KEY`;
8–9 falhas já no `main`) e 2 no executors (dependem de configuração do `.env`).

---

## Problemas Identificados (estado anterior)

1. **Sem forma de ver o deploy sem Railway:** a skill confirmava o código novo "dentro do container"
   (`railway ssh`).
2. **Código só pelo Daniel:** `configuracao-personalizada` (modo colaborador) mandava o que é código para
   `/api/suporte/pedidos-correcao`.
3. **"Sim" do Daniel:** a regra 6 da skill exigia o Daniel para as categorias que sobem; o CLAUDE.md
   exige "o utilizador" — numa sessão do Gabriel, ele.
4. **"Testes passam" ambíguo sem `.env`:** falhas pré-existentes que não são do colaborador.

---

## Plano de Implementação

### Fase 1 — Versão em produção sem Railway
| Arquivo | O que muda |
|---|---|
| `backend-crm/services/deploy_version.py` | novo: `versoes()` = commit do crm + core `/version` + executors `/health` |
| `backend-crm/app.py` | `GET /version` (público, só hashes) |
| `backend-core/app/main.py` | `GET /version` → `RAILWAY_GIT_COMMIT_SHA` |
| `backend-executors/app/api/health.py` | `commit` no `/health` |
| `.claude/skills/diagnosticar-agente/scripts/prod_http.py` | ação `versao` (sem login) |
| `backend-crm/tests/test_deploy_version.py` | 2 testes |

### Fase 2 — Skill: o colaborador corrige o código
Modo colaborador da `configuracao-personalizada` faz a fase 6 completa; "sim" das categorias que sobem
dado por quem corre a sessão; regressão = testes antes/depois sem falhas novas + opt-in + bateria em
produção depois do deploy + revert; `verificar_ambiente.py` verifica Python, pacotes, git e permissão de push.

---

## Checks de Validação

### Cenário C1 — Versão
- [x] `pytest` do backend-crm passa com as rotas novas (16/11/2026: 301 passed)
- [ ] depois do deploy, `--prod-acao versao` mostra o commit publicado nos 3 serviços, sem Railway

### Cenário C2 — Checklist do colaborador
- [x] `verificar_ambiente.py` (`DIAG_MODO_COLABORADOR=1`) mostra Python, pacotes, git e permissão de push (16/11/2026: tudo ✅, conta 2 de produção; acesso ao GitHub por ls-remote — a escrita confirma-se na 1.ª publicação)

---

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `5b6be61` | `/version` no crm e no core, `commit` no `/health` do executors, ação `versao` |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `66c76f8` | skill: o colaborador corrige e publica código; checklist do PC; docs |
