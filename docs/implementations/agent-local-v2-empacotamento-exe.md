# Empacotamento do agent-local v2 (.exe)

**Branch:** `empacotamento-agent-local`
**Status:** Em andamento

---

## Motivação

Empacotamento é sempre a **última fase do ciclo de uma versão** do agent-local
— ver [`docs/plans/_versionamento-agent-local.md`](../plans/_versionamento-agent-local.md).
A v2 já está totalmente documentada e validada (ver
[`docs/architecture/agent-local-app.md`](../architecture/agent-local-app.md),
"Versão documentada: v2") — o único item pendente do ciclo v2 é gerar
`agent-local.exe`, para que utilizadores finais consigam abrir a app com
duplo clique, sem precisar de Python/venv instalados.

Este item nasceu originalmente como Fase 4 de
`docs/implementations/agent-local-v2-app-standalone.md` (já graduado e
removido) e foi adiado a pedido do utilizador até todos os cenários de teste
das Fases 5–10 estarem validados. Esse pré-requisito está cumprido — por
isso o item sai de `docs/plans/` e entra aqui como próximo a implementar.

---

## Problemas Identificados (estado anterior)

1. **Sem distribuição para utilizador final:** hoje `agent-local` só corre via
   `python main.py` dentro do `.venv` do projecto — inviável para distribuir
   a clientes/utilizadores finais sem conhecimento técnico.

2. **Fallback de URL aponta para localhost (`app/auth.py:30`,
   `app/crm_client.py:17`):** sem `.env`/env var, `_get_core_url()` cai para
   `http://localhost:8001` e `_base()` cai para `http://localhost:8000`. Em
   dev isso nunca é percebido porque há sempre `.env` local — mas um `.exe`
   distribuído a um cliente real não tem `.env` nenhum, e `localhost` não
   existe fora da máquina de quem tem o backend a correr. Descoberto durante
   a investigação desta implementação (o rascunho original só previa gerar
   o `.exe`, sem prever este pré-requisito).

---

## Abordagem

PyInstaller para gerar um binário Windows único (`--onefile`), com fallback
de URL corrigido para apontar para produção (Railway) em vez de localhost —
confirmado com o utilizador, ver `Plano de Implementação`.

**Notas:**
- Suporte por ora só Windows — PyInstaller gera binário por plataforma;
  macOS/Linux ficam fora deste item.
- `agent/config.py` (usado pelo worker clássico e pelo fallback Selenium de
  `maps_client.py`) não precisa de mudança — confirmado que
  `maps_research_runner.py` não usa `config.backend_url`.
- Pré-requisito de distribuição (inalterado, não resolvido pelo
  empacotamento): utilizador final precisa ter o Google Chrome instalado.

---

## Plano de Implementação

### Fase 1 — Fallback de URLs de produção

**Objetivo:** o `.exe` funcionar out-of-the-box no PC do cliente, sem
`.env`/env var, apontando para o backend real em produção.

| Arquivo | O que muda |
|---|---|
| `agent-local/app/auth.py` | `_get_core_url()`: fallback final `"http://localhost:8001"` → `"https://backend-core-production-863b.up.railway.app"` |
| `agent-local/app/crm_client.py` | `_base()`: fallback `"http://localhost:8000"` → `"https://backend-crm-production-a702.up.railway.app"` |

```python
# ANTES
return "http://localhost:8001"
# ...
return os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")

# DEPOIS
return "https://backend-core-production-863b.up.railway.app"
# ...
return os.getenv("BACKEND_URL", "https://backend-crm-production-a702.up.railway.app").rstrip("/")
```

Overrides via `CORE_BASE_URL`/`BACKEND_URL` continuam a funcionar
normalmente — comportamento em dev não muda (`.env` local sempre presente
sobrepõe o fallback).

### Fase 2 — Geração do executável (PyInstaller)

**Objetivo:** produzir `dist/agent-local.exe` distribuível por duplo clique.

| Arquivo | O que muda |
|---|---|
| `agent-local/agent-local.spec` | Novo — spec PyInstaller: onefile, `console=False`, `name="agent-local"`, inclui dados do customtkinter (tema/assets JSON — gotcha mais comum de build quebrado) |
| `agent-local/build.bat` | Novo — instala `pyinstaller` no `.venv` se ausente, roda `pyinstaller agent-local.spec --noconfirm`, imprime o caminho do `.exe` gerado |
| `agent-local/.gitignore` | Adiciona `build/` e `dist/` (output do PyInstaller); o `.spec` em si é versionado |

Sem mudança necessária em `requirements.txt` (PyInstaller é ferramenta de
build, não dependência de runtime) nem exclusão manual de `test.py`/
`rascunho.py`/`tests/` (fora do grafo de imports do `main.py`, o
PyInstaller já não os inclui).

---

## Checks de Validação

### Cenário C1 — Build gera o executável sem erros
- [ ] Rodar `build.bat` num `.venv` limpo
- [ ] Confirmar: `dist/agent-local.exe` é gerado sem erros/warnings críticos

### Cenário C2 — Executável abre sem Python instalado
- [ ] Copiar só o `.exe` para uma máquina/VM sem Python/`.venv`
- [ ] Duplo clique
- [ ] Confirmar: janela de login abre normalmente

### Cenário C3 — Aponta para produção sem nenhuma configuração
- [ ] Abrir o `.exe` sem `.env`/env vars setadas
- [ ] Fazer login/OTP
- [ ] Confirmar: autentica contra o backend de produção (Railway), não localhost

### Cenário C4 — Fluxo básico funciona no executável
- [ ] Abrir Pesquisa/Prospecção no `.exe`
- [ ] Confirmar: Selenium abre o Chrome normalmente (sem erro de chromedriver)

---

## Ajustes Possíveis Pós-Implementação

- Sem ícone customizado (não existe asset `.ico`/`.png` no projeto hoje) — o
  `.exe` sai com o ícone padrão do PyInstaller/Tkinter.
- `README.md` do agent-local (linhas 62-68) ficará desatualizado — descreve
  o agente "worker" antigo, não a GUI v2. Fora do escopo desta implementação.
- Build `--onefile` tem alguns segundos de atraso no arranque (extração para
  pasta temp a cada execução) — aceito como trade-off por "um arquivo só".
