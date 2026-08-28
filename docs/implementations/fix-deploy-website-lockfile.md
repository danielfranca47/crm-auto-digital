# Corrigir workflow de deploy do website (lockfile removido)

**Branch:** `fix/deploy-website-lockfile`
**Status:** Em andamento

---

## Motivação

Durante a investigação de por que o `CLOUDFLARE_API_TOKEN` estava inválido
(corrigido separadamente), descobriu-se que o deploy do `website` falha
antes mesmo de chegar à Cloudflare — desde o commit `e98879d` ("fix(website):
remover package-lock.json gerado no Windows"), que removeu de propósito
`website/package-lock.json` (lockfile gerado no Windows causava problemas).

O workflow `.github/workflows/deploy-website.yml` nunca foi atualizado para
refletir essa remoção: ainda tinha `cache-dependency-path:
website/package-lock.json` (que o `actions/setup-node` não consegue
resolver, ficheiro inexistente) e `npm ci` (que exige um lockfile presente
para funcionar). Resultado: toda execução falha no passo de setup do Node,
antes mesmo de instalar dependências.

---

## Problemas Identificados (estado anterior)

1. **`cache-dependency-path` aponta para ficheiro inexistente:**
   `.github/workflows/deploy-website.yml:25` — `actions/setup-node@v4` falha
   com "Some specified paths were not resolved, unable to cache
   dependencies."
2. **`npm ci` exige lockfile que não existe:** mesmo arquivo, linha 27 —
   mesmo que o passo de cache não falhasse, `npm ci` falharia da mesma forma.

---

## Abordagem

Manter a decisão original (sem lockfile committado, por causar problemas
gerado no Windows) e ajustar o workflow para não depender dele: remover a
config de cache do `setup-node` e trocar `npm ci` por `npm install`.

---

## Plano de Implementação

### Fase 1 — Ajustar o workflow

| Arquivo | O que muda |
|---|---|
| `.github/workflows/deploy-website.yml` | Remove `cache: npm` / `cache-dependency-path`; troca `npm ci` por `npm install` |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | _(a preencher)_ | Ajuste do workflow de deploy do website |

---

## Checks de Validação

### Cenário C1 — Deploy do website passa via workflow_dispatch
- [ ] Disparar `gh workflow run deploy-website.yml --ref main`
- [ ] Confirmar: job completa com sucesso (todos os passos verdes)
- [ ] Confirmar: passo do Cloudflare (`wrangler pages deploy`) executa sem erro
