# Persistência do banco de dados do backend-crm em produção (Railway)

**Branch:** `verificacao-banco-dados-producao`
**Status:** Em andamento

---

## Motivação

O utilizador reportou que leads cadastrados dias atrás não aparecem mais no
Kanban de produção (`crmapp.danielfranca.pt`). Investigação nesta mesma
conversa confirmou a causa raiz:

`backend-crm/database.py:10-12` define o caminho do SQLite de forma fixa,
relativa à própria pasta do código (`<repo>/database/crm.db`) — a variável
`CRM_DB_PATH` (já documentada em `.env.example`/`CLAUDE.md`) **nunca é lida
pelo código**, é uma configuração morta.

O serviço `backend-crm` no Railway **tem** um volume persistente
(`backend-crm-volume`, montado em `/data`, confirmado via `railway volume
list`), mas como o código nunca aponta para lá, o SQLite real vive dentro do
filesystem efémero do container. A cada deploy, `database/crm.db` nasce
vazio de novo (schema recriado do zero), enquanto `/data` fica intocado.

Confirmado por SSH em modo leitura (`railway ssh -s backend-crm -- ls -la
/data`, executado pelo utilizador): `/data` só contém `lost+found` (pasta
automática do sistema de ficheiros) — **não há nenhuma cópia dos leads
perdidos para recuperar**. A perda já ocorrida é permanente.

Comparação com `backend-core/app/config.py:11` (`DATABASE_URL: str =
"sqlite:///./core.db"`, lido de env var via Pydantic `Settings`) mostra o
padrão correto — é por isso que o login/utilizador sobrevive a updates,
enquanto os leads não.

`backend-crm/.env.example:71-73` tem um comentário enganoso: diz para usar
em Railway um caminho relativo (`database/crm.db`) — isso não resolveria
nada, pois um caminho relativo dentro do container continua efémero.
Provavelmente a origem do erro original.

---

## Problemas Identificados (estado anterior)

1. **`CRM_DB_PATH` é configuração morta:** `backend-crm/database.py:10-12` —
   caminho do SQLite hardcoded, ignora a env var já documentada.
2. **Volume persistente desconectado:** `backend-crm-volume` existe no
   Railway (montado em `/data`) mas o código nunca escreve lá.
3. **Comentário enganoso em `.env.example:71-73`:** instrui usar caminho
   relativo em Railway, o que não resolve a efemeridade do container.
4. **`.env` local (gitignored) com `CRM_DB_PATH` duplicada e conflitante:**
   linha 46 correta (`database/crm.db`), linha 75 errada
   (`backend/database/crm.db`, assume CWD na raiz do repo) — inofensivo hoje
   porque a variável é ignorada, mas quebraria o dev local assim que o
   código passasse a lê-la.

---

## Abordagem

Reaproveitar a variável `CRM_DB_PATH` já documentada (em vez de criar uma
nova), com fallback para o caminho relativo atual — mesmo padrão que
`backend-core` já usa com `DATABASE_URL`.

```
get_connection() é chamado
  → DB_PATH = os.environ.get("CRM_DB_PATH") ou caminho relativo padrão
       ├─ local dev (sem env var) → backend-crm/database/crm.db (igual a hoje)
       └─ produção (CRM_DB_PATH=/data/crm.db definida no Railway)
            → SQLite vive no volume persistente → sobrevive a deploys
```

Sem mudança em `ensure_db_dir()`/`get_connection()` — continuam a usar
`DB_DIR`/`DB_PATH` como globals do módulo, exatamente como hoje. `jobs_service.py`
só usa `DB_PATH` para log (sem impacto). Os 4 testes que fazem
`database.DB_PATH = self.db_path` continuam a funcionar (mesmo padrão de
monkeypatch, comportamento inalterado).

`app.py` já chama `load_dotenv(BASE_DIR / ".env")` (linha 11) antes de
`from database import init_db` (linha 18) — a env var, se definida, estará
disponível a tempo tanto localmente quanto em produção (onde a Railway
injeta env vars diretamente, sem `.env`).

**Fora do escopo desta fase (ação manual do utilizador):** definir
`CRM_DB_PATH=/data/crm.db` nas variáveis de ambiente do serviço `backend-crm`
no Railway. Esta é a etapa que efetivamente ativa a persistência — sem ela,
o código corrigido continua a cair no valor padrão (caminho
relativo/efémero) em produção. Ação de escrita direta em infraestrutura de
produção, fora do que o Claude tem permissão para executar (a leitura via
SSH já foi bloqueada pelo classifier de auto-mode).

---

## Plano de Implementação

### Fase 1 — Ler CRM_DB_PATH do ambiente com fallback

**Objetivo:** tornar o caminho do SQLite configurável via env var, sem mudar
o comportamento padrão do dev local.

| Arquivo | O que muda |
|---|---|
| `backend-crm/database.py` | `DB_PATH`/`DB_DIR`: lê `CRM_DB_PATH` do ambiente, fallback para o caminho relativo atual |
| `backend-crm/.env.example` | Comentário corrigido: em Railway, apontar para o volume persistente montado (ex.: `/data/crm.db`), não para um caminho relativo |

```python
# ANTES
BASE_DIR = os.path.dirname(__file__)
DB_DIR = os.path.join(BASE_DIR, "database")
DB_PATH = os.path.join(DB_DIR, "crm.db")

# DEPOIS
BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.environ.get("CRM_DB_PATH") or os.path.join(BASE_DIR, "database", "crm.db")
DB_DIR = os.path.dirname(DB_PATH)
```

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `647538e` | backend: `CRM_DB_PATH` lido do ambiente com fallback; comentário corrigido no `.env.example` |

**Detalhes do commit `647538e`:**
- `backend-crm/database.py` — `DB_PATH` passa a ler `os.environ.get("CRM_DB_PATH")`, com fallback para o caminho relativo atual
- `backend-crm/.env.example` — comentário corrigido: em Railway, apontar para o volume persistente montado, não para um caminho relativo
- `backend-crm/.env` (local, gitignored, fora do commit) — removida a linha duplicada/errada `CRM_DB_PATH=backend/database/crm.db` (linha 75), mantida só a correta

### Relatório da Fase 1 — o que mudou na prática

**Antes:** o caminho do banco de dados dos leads estava fixo no código,
sempre dentro da própria pasta da aplicação — não havia como redirecioná-lo
para um local duradouro, mesmo já existindo um espaço reservado para isso em
produção.

**Agora:** o código passa a olhar primeiro para a variável de ambiente
`CRM_DB_PATH`; se ela não estiver definida, usa exatamente o mesmo caminho
de sempre (nada muda no teu ambiente local). Em produção, assim que essa
variável for definida a apontar para o espaço reservado (`/data/crm.db`), o
banco de dados dos leads passa a sobreviver às atualizações, tal como já
acontece hoje com a tua conta de utilizador.

**Importante — isto ainda não está ativo em produção.** O código já está
pronto, mas falta o passo manual de definir `CRM_DB_PATH=/data/crm.db` nas
variáveis do serviço `backend-crm` no Railway (não consigo fazer essa parte
— é uma escrita direta em infraestrutura de produção). Instruções abaixo.

**Para validar:** Cenários P1 e P2 (já executados por mim, nesta sessão) e
C1 (ativação em produção, requer a tua ação), na seção "Checks de
Validação" abaixo.

---

## Checks de Validação

### Cenário P1 — Comportamento local inalterado (regressão)
- [x] (2026-08-12) Sem `CRM_DB_PATH` definida: `database.DB_PATH` resolve para `backend-crm/database/crm.db` (igual a antes da mudança)
- [x] (2026-08-12) Suite de testes existente que faz `monkeypatch` de `database.DB_PATH` (`test_leads_company_or_contact_migration`, `test_meeting_management_gate`, `test_inbound_orchestrator_flag`) — mesmos resultados antes/depois da mudança (3 erros pré-existentes, reproduzidos também no código original via `git stash`; nada causado por esta mudança — `test_whatsapp_group_ignore`: import do FastAPI quebrado num módulo não relacionado; `test_inbound_orchestrator_flag` ×2: falha de limpeza de pasta temporária no Windows, não na lógica do teste)
- [x] (2026-08-12) Servidor local subido normalmente (`GET /docs` → `200`), banco criado em `backend-crm/database/crm.db` como sempre

### Cenário P2 — `CRM_DB_PATH` redireciona o banco (nova funcionalidade)
- [x] (2026-08-12) Com `CRM_DB_PATH` apontando para uma pasta temporária: `database.DB_PATH`/`DB_DIR` resolvem para lá
- [x] (2026-08-12) Servidor local subido com a variável definida — `GET /docs` → `200`, ficheiro `crm.db` criado exatamente no caminho indicado pela variável, schema inicializado normalmente

### Cenário C1 — Ativação em produção (ação manual do utilizador)
- [ ] Definir `CRM_DB_PATH=/data/crm.db` nas variáveis de ambiente do serviço `backend-crm` no Railway
- [ ] Aguardar/forçar um novo deploy do `backend-crm`
- [ ] Confirmar via `railway ssh -s backend-crm -- ls -la /data` que `crm.db` passou a existir em `/data`
- [ ] Criar um lead de teste em produção, forçar outro redeploy (ex.: `railway redeploy` ou um commit vazio), confirmar que o lead sobrevive
