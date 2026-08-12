# Empacotamento do agent-local v2 (.exe)

**Branch:** `empacotamento-agent-local`
**Status:** Em andamento — pendente: Cenário C2 (máquina limpa sem Python) e C4 (fluxo Selenium/WhatsApp no .exe), ambos numa call real com cliente novo (ver `docs/ops/guia-teste-cliente-novo-exe-agent-local.md`)

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

### Fase 3 — Ícone/identidade visual

**Objetivo:** o `.exe` e a janela do app usarem a marca real da Digital Pro
em vez do ícone genérico do PyInstaller/Tkinter.

**Correção de rota em andamento:** a primeira tentativa reaproveitou
`website/public/favicon.ico` — mas esse arquivo é resíduo da pré-configuração
do Lovable (um ícone de coração colorido, nada a ver com a marca), não o
ícone real do site. O ícone correto é a marca "Lara by DigitalPro" — um
quadrado arredondado com gradiente azul e um recorte quadrado menor no
centro — visível no topo de `https://danielfranca.pt/lara-ia`. Esse mark
**não existe como arquivo de imagem** no repositório: é desenhado directo em
JSX/Tailwind em `website/src/pages/CRMLandingV2.tsx:266-269` (`accent-gradient`
+ `rounded-xl`/`rounded-sm`), sem PNG/SVG correspondente.

| Arquivo | O que muda |
|---|---|
| `agent-local/assets/icon.ico` | Novo — gerado programaticamente (Pillow) replicando o mark real: gradiente `linear-gradient(135deg, hsl(200 100% 70%), hsl(200 80% 60%))` (`website/src/index.css:48`) num quadrado `rounded-xl`, com recorte interno na cor `hsl(220 15% 5%)` (`--background`, `index.css:12`); multi-tamanho (16 a 256px) |
| `agent-local/agent-local.spec` | `EXE(..., icon="assets/icon.ico")`; `datas += [("assets/icon.ico", "assets")]` |
| `agent-local/main.py` | Helper `_resource_path()`; `iconphoto` (via Pillow `ImageTk`) no `__init__` de `AgentLocalApp` — mais fiável que `iconbitmap` nativo do Tk para `.ico` com frame comprimido em PNG |

**Nota técnica:** inicialmente usei `self.iconbitmap(...)` (API nativa do
Tk) para o ícone da janela — não funcionou (ícone genérico continuava a
aparecer, falha silenciosa, capturada pelo `try/except`). Troquei para
`iconphoto` com `PIL.ImageTk.PhotoImage`, que decodifica o `.ico` via
Pillow em vez de depender do parser de `.ico` nativo do Tk — resolveu.

### Relatório da Fase 3 — o que mudou na prática

**Antes:** o `.exe` e a janela abriam com o ícone genérico do
PyInstaller/Tkinter — nada identificava a app como sendo da Digital Pro.
**Agora:** o ícone do arquivo `.exe` (Explorer) e o ícone da janela/barra de
tarefas mostram o mesmo quadrado azul "Lara by DigitalPro" usado no site.
**Para validar:** confirmado nesta sessão via extração directa do ícone
embutido no `.exe` (`System.Drawing.Icon.ExtractAssociatedIcon`, bypassa
cache do Explorer) e screenshot da janela aberta (`desktop-control`) — ver
Cenário C5 abaixo.

### Fase 4 — Instalador (Inno Setup)

**Objetivo:** substituir o `.exe` avulso por um instalador de verdade — com
atalhos automáticos e desinstalador, sem pedir senha de administrador
(decisão confirmada com o utilizador: cliente pode não ser admin do próprio
PC).

| Arquivo | O que muda |
|---|---|
| `agent-local/agent-local-installer.iss` | Novo — script Inno Setup: `AppName="Gerador de Leads — Digital Pro"`, `AppVersion="2.0.0"`, `AppPublisher="Digital Pro"`, `PrivilegesRequired=lowest`, `DefaultDirName={localappdata}\DigitalPro\GeradorDeLeads`, idioma PT-BR, atalho Menu Iniciar sempre + Área de Trabalho via checkbox (`Flags: checkedonce`), `SetupIconFile` usa a mesma marca da Fase 3 |
| `agent-local/build-installer.bat` | Novo — chama `build.bat` primeiro (garante `.exe` actualizado), localiza `ISCC.exe` (tenta `%LOCALAPPDATA%\Programs\Inno Setup 6` e as duas pastas Program Files), roda a compilação |
| `agent-local/.gitignore` | Adiciona `installer_output/` (output do Inno Setup); o `.iss` em si é versionado |

**Ferramenta instalada nesta máquina** (build tool, não vai para o cliente):
`winget install --id JRSoftware.InnoSetup -e` → instalou em
`%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe` (per-user, sem admin —
coincidentemente o mesmo padrão do instalador que ele gera).

### Commits Fase 4

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `75ab91d` | .iss + build-installer.bat + gitignore |
| 2 | `c2bb965` | fix: pasta do Menu Iniciar usa o nome completo do app (era só "Digital Pro") |

**Detalhes do commit `c2bb965`:** `DefaultGroupName` estava fixo como
`"Digital Pro"` (só o publisher) — utilizador percebeu a inconsistência
(atalho e Adicionar/Remover Programas já diziam "Gerador de Leads — Digital
Pro", mas a pasta do Menu Iniciar não). Trocado para `{#MyAppName}`, mesmo
nome usado em todo o resto. Revalidado: pasta agora é
"Gerador de Leads — Digital Pro".

### Relatório da Fase 4 — o que mudou na prática

**Antes:** distribuir o app era entregar um `.exe` avulso — sem atalho
automático, sem entrada no Menu Iniciar, sem forma de desinstalar limpo.
**Agora:** rodando `build-installer.bat` gera
`installer_output\DigitalPro-GeradorDeLeads-Setup.exe` — um instalador
único que, ao rodar, **não pede senha de administrador**, cria atalho no
Menu Iniciar (grupo "Gerador de Leads — Digital Pro") sempre, atalho na
Área de Trabalho por padrão (desmarcável), e aparece em "Adicionar/Remover
Programas" com nome, versão e publisher corretos.

**Testado nesta sessão, nesta máquina** (instalação e desinstalação
silenciosas via PowerShell, mais verificação directa do sistema de arquivos
e do registro do Windows — não é o mesmo que o Cenário C2/C6 num PC de
cliente real, mas valida que o instalador funciona tecnicamente):
- Instalou sem prompt de UAC/admin.
- `agent-local.exe` instalado em `%LOCALAPPDATA%\DigitalPro\GeradorDeLeads\`,
  abriu normalmente a partir de lá.
- Atalho no Menu Iniciar (app + desinstalador) e na Área de Trabalho — confirmados.
- Registro em "Adicionar/Remover Programas" — `DisplayName`, `DisplayVersion`,
  `Publisher`, `UninstallString`, `InstallLocation` todos corretos.
- Desinstalação silenciosa removeu: pasta de instalação, ambos os atalhos,
  e a entrada do registro — nada ficou para trás.

**Para validar:** Cenário C6 abaixo, confirmado nesta máquina hoje. O teste
real num PC de cliente novo (parte do mesmo guia usado para C2/C4) fica
pendente — ver `docs/ops/guia-teste-cliente-novo-exe-agent-local.md`
(a ser actualizado com os passos do instalador).

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
- **Pendente:** só testado nesta máquina de dev (tem Python instalado) —
  será validado numa chamada real com um cliente novo, seguindo
  [`docs/ops/guia-teste-cliente-novo-exe-agent-local.md`](../ops/guia-teste-cliente-novo-exe-agent-local.md)

### Cenário C3 — Aponta para produção sem nenhuma configuração
- [x] Abrir o `.exe` sem `.env`/env vars setadas
- [x] Confirmar: autentica contra o backend de produção (Railway), não localhost
- **Validado em:** 12/08/2026 — `.exe` restaurou sessão salva e mostrou badge "Assinante" + "Modo: Assinante — chave API incluída" em tempo real, sem nenhuma env var/config.json presente; confirma que o fallback de produção da Fase 1 é usado pelo binário empacotado

### Cenário C4 — Fluxo básico funciona no executável
- [ ] Abrir Pesquisa/Prospecção no `.exe`
- [ ] Confirmar: Selenium abre o Chrome normalmente (sem erro de chromedriver)
- **Pendente:** mesma chamada com cliente novo do Cenário C2, ver
  [`docs/ops/guia-teste-cliente-novo-exe-agent-local.md`](../ops/guia-teste-cliente-novo-exe-agent-local.md)

### Cenário C5 — Ícone da marca aparece no .exe e na janela
- [x] Extrair o ícone embutido no `.exe` gerado e comparar com a marca real
- [x] Abrir o `.exe` e confirmar visualmente o ícone na janela/barra de tarefas
- **Validado em:** 12/08/2026 — ícone extraído via `ExtractAssociatedIcon`
  confere com o quadrado azul "Lara by DigitalPro"; screenshot da janela
  aberta confirma o mesmo ícone no título e na barra de tarefas

### Cenário C6 — Instalador instala/desinstala limpo, sem admin
- [x] Rodar o `Setup.exe` e confirmar que não pede senha de administrador
- [x] Confirmar atalho no Menu Iniciar e na Área de Trabalho
- [x] Confirmar entrada em "Adicionar/Remover Programas" com dados corretos
- [x] Desinstalar e confirmar que nada fica para trás (pasta, atalhos, registro)
- **Validado em:** 12/08/2026, nesta máquina (instalação/desinstalação
  silenciosa via PowerShell + inspeção directa do sistema de arquivos e do
  registro) — instalou sem UAC, todos os atalhos e o registro corretos,
  desinstalação removeu tudo. **Pendente:** repetir num PC de cliente real
  (não substitui isso — só confirma que o instalador funciona tecnicamente)

---

## Ajustes Possíveis Pós-Implementação

- `README.md` do agent-local (linhas 62-68) ficará desatualizado — descreve
  o agente "worker" antigo, não a GUI v2. Fora do escopo desta implementação.
- Build `--onefile` tem alguns segundos de atraso no arranque (extração para
  pasta temp a cada execução) — aceito como trade-off por "um arquivo só".
- Ícone gerado em 512×512 a partir de um mark CSS simples — se a Digital Pro
  criar um logo vetorial oficial no futuro, vale substituir `assets/icon.ico`
  por uma versão com mais detalhe/qualidade nos tamanhos maiores (128/256px).
- **Favicons do website e dos frontends ainda são resíduo do Lovable, não a
  marca Digital Pro** — descoberto ao investigar a Fase 3 desta
  implementação. Confirmado (não é suposição):
  - `website/public/favicon.ico` e `frontend-crm/public/favicon.ico` — mesmo
    arquivo (hash MD5 idêntico), o "coração" colorido genérico do Lovable.
  - `frontend-admin/public/favicon.svg` — outro ícone genérico do Lovable
    (fragmento/raio abstrato roxo-azul), também não é a marca.
  - `frontend-admin` já usa um SVG (não `.ico`) — trocar mantendo o formato
    ou migrar para `.ico`/`.png`, o que for mais simples de gerar a partir
    do novo asset.
  Trocar pelo mark real "Lara by DigitalPro" (quadrado arredondado,
  gradiente azul — mesmo desenhado em `website/src/pages/CRMLandingV2.tsx:266-269`
  e replicado como imagem em `agent-local/assets/icon.ico`, ver Fase 3
  acima). Item novo, fora do escopo do empacotamento do agent-local — afeta
  `website/`, `frontend-crm/` e `frontend-admin/`, não `agent-local/`.
