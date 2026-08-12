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
