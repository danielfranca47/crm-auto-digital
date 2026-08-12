# Empacotamento do agent-local v2 (.exe)

**Branch:** `empacotamento-agent-local`
**Status:** Em andamento — pendente: Cenário C2 (máquina limpa sem Python) e C4 (fluxo Selenium/WhatsApp no .exe)

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

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `efcf668` | fallback de URL de auth.py/crm_client.py aponta para produção |

**Detalhes do commit `efcf668`:**
- `agent-local/app/auth.py` — `_get_core_url()`: fallback final agora é `https://backend-core-production-863b.up.railway.app`
- `agent-local/app/crm_client.py` — `_base()`: fallback agora é `https://backend-crm-production-a702.up.railway.app`

### Relatório da Fase 1 — o que mudou na prática

**Antes:** se o `.exe` fosse aberto num PC sem nenhuma configuração extra, o
app tentava falar com `localhost` — um endereço que só existe na máquina de
quem tem o backend a correr, então não funcionaria em nenhum PC de cliente.
**Agora:** sem nenhuma configuração, o app já sabe falar com o backend real
em produção (Railway) — o mesmo que o site já usa hoje.
**Para validar:** confirmado por linha de comando (sem `.env`/env vars, o
código retorna as URLs de produção corretas) — não há Cenário de UI
associado a esta fase isoladamente; a validação visual completa acontece no
Cenário C3, depois do `.exe` existir (Fase 2).

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

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `afc89c5` | spec + build.bat + gitignore para gerar o .exe |

**Detalhes do commit:**
- `agent-local/agent-local.spec` — novo; onefile, `console=False`, inclui data files do customtkinter via `collect_data_files`
- `agent-local/build.bat` — novo; instala PyInstaller no `.venv` se ausente e roda o build
- `agent-local/.gitignore` — adiciona `build/` e `dist/`

**Nota de build:** aviso `Hidden import "tzdata" not found` apareceu no log
— vem de uma dependência (não do código do agent-local, que não usa
`zoneinfo`/`pytz` em lado nenhum) e não impediu o build nem o arranque do
app; risco considerado baixo, mas fica registado caso apareça algum erro de
timezone em teste futuro.

### Relatório da Fase 2 — o que mudou na prática

**Antes:** não existia nenhuma forma de gerar um `.exe` do agent-local —
só corria via `python main.py` dentro do `.venv`.
**Agora:** rodando `build.bat` (ou `pyinstaller agent-local.spec --noconfirm`)
gera `dist/agent-local.exe` (~36 MB), um único arquivo distribuível por
duplo clique.

**Testado nesta sessão, nesta máquina** (via `desktop-control`, screenshot
em anexo ao histórico da conversa):
- O `.exe` abriu a janela normalmente, sem consola atrás.
- Restaurou a sessão salva localmente e confirmou "Assinante" em tempo real
  — **sem `.env`, `config.json` ou env vars setadas** — prova de que o
  fallback de produção da Fase 1 está a ser usado de facto pelo binário
  empacotado.

**Não testado ainda (fica pendente para o utilizador ou uma sessão futura):**
- Esta máquina tem Python instalado — não prova o Cenário C2 (arranque numa
  máquina realmente limpa, sem Python/`.venv`). Precisa de um PC ou VM sem
  Python para validar isso de verdade.
- Cenário C4 (Selenium abrindo o Chrome real / envio WhatsApp) não foi
  exercitado nesta sessão — só o arranque e a autenticação foram testados.

**Para validar:** Cenários C1 (✅ hoje) e C3 (✅ hoje) já confirmados abaixo.
Faltam C2 e C4.

---

## Checks de Validação

### Cenário C1 — Build gera o executável sem erros
- [x] Rodar `build.bat` (equivalente: instalar PyInstaller + `pyinstaller agent-local.spec --noconfirm`)
- [x] Confirmar: `dist/agent-local.exe` é gerado sem erros/warnings críticos
- **Validado em:** 12/08/2026 — `dist/agent-local.exe` gerado, ~36 MB; único warning foi `Hidden import "tzdata" not found` (não bloqueante, ver nota acima)

### Cenário C2 — Executável abre sem Python instalado
- [ ] Copiar só o `.exe` para uma máquina/VM sem Python/`.venv`
- [ ] Duplo clique
- [ ] Confirmar: janela de login abre normalmente
- **Pendente:** só testado nesta máquina de dev (tem Python instalado) — precisa de máquina/VM limpa para validar de verdade

### Cenário C3 — Aponta para produção sem nenhuma configuração
- [x] Abrir o `.exe` sem `.env`/env vars setadas
- [x] Confirmar: autentica contra o backend de produção (Railway), não localhost
- **Validado em:** 12/08/2026 — `.exe` restaurou sessão salva e mostrou badge "Assinante" + "Modo: Assinante — chave API incluída" em tempo real, sem nenhuma env var/config.json presente; confirma que o fallback de produção da Fase 1 é usado pelo binário empacotado

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
