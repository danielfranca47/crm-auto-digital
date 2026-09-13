# Exigir login para upload de planilhas de leads

**Branch:** `fix/upload-planilhas-sem-auth`
**Status:** Em andamento
**Sprint:** `docs/plans/plano-sprint-2026-09-12.md` (item P3)
**Origem:** `docs/plans/seguranca-melhorias-futuras.md` (M2)

---

## Motivação

O endpoint que recebe arquivos Excel/CSV para importar leads aceita qualquer chamada
anónima, sem limite de tamanho nem de quantidade. Achado da auditoria de segurança de
15/07/2026, confirmado ainda sem correção na auditoria de 12/09/2026.

Comportamento anterior: `POST /api/uploads` (`backend-crm/routes/uploads.py:46`) não tinha
`Depends(require_crm_access)`. O arquivo era gravado em disco
(`data/uploads/ai/{uuid}.ext`) e processado com `pandas.read_excel`/`read_csv` sem
limite de tamanho nem cota por utilizador.

Comportamento desejado: só um utilizador autenticado do CRM consegue enviar arquivos
para importação, e os arquivos ficam associados/isolados por utilizador.

Risco concreto: superfície de negação de serviço num serviço exposto à internet — um
atacante pode mandar arquivos grandes ou em quantidade repetida até esgotar o disco do
servidor, ou explorar uma falha futura do parser do pandas, sem precisar de nenhuma
credencial.

---

## Diagnóstico (Passo 0)

### Já existe?

Não. Confirmado por leitura direta de `backend-crm/routes/uploads.py` (arquivo inteiro,
única rota `POST /uploads` nas linhas 46-76):
- Sem `Depends(require_crm_access)` nem qualquer outra auth — é a única rota do arquivo.
- Sem validação de tamanho — `content = await file.read()` (linha 56) lê o arquivo inteiro
  em memória, sem limite.
- Sem isolamento por utilizador — todos os uploads caem numa pasta plana
  `data/uploads/ai/`, distinguidos só por um `uuid.uuid4()` (linha 53).
- Validação de extensão já existe (`.xlsx`/`.csv`/`.xls`, linha 50).

### O que precisa ser construído

**backend-crm:**
1. `routes/uploads.py` — adicionar `Depends(require_crm_access)`, gravar em
   `data/uploads/ai/{user_id}/{uuid}.ext` (isolado por utilizador), e substituir a leitura
   integral em memória por leitura em streaming com corte no primeiro chunk que ultrapassar
   um limite de tamanho (`MAX_UPLOAD_BYTES`), apagando o arquivo parcial e retornando 413.
2. `routes/assistente_ia.py` — as rotas `/processar` (linha ~73) e `/preview` (linha ~265)
   já exigem `require_crm_access`, mas resolvem o arquivo só pelo `upload_id`, em
   `data/uploads/ai/{upload_id}.ext`, sem checar dono. Como o path de `uploads.py` passa a
   incluir `user_id`, essas duas rotas precisam mudar junto para
   `data/uploads/ai/{user_id}/{upload_id}.ext` — senão todo upload novo passa a dar 404
   nelas.
3. Testes — novo `backend-crm/tests/test_uploads_route_auth.py`, seguindo o padrão de
   `tests/test_appointments_route_auth.py` (chamada direta à função da rota, com
   `CurrentUser` "dono" e "intruso").

**Frontend:** nenhuma mudança. `frontend-crm/src/services/api.ts:938-944`
(`uploads.enviar`) já usa o `apiClient` central, que já envia o Bearer token em toda
chamada (confirmado por leitura do arquivo) — o token passa a ser aceito assim que o
backend exigir.

### Riscos e dependências

- **Risco de regressão:** `assistente_ia.py` precisa mudar junto com `uploads.py`, senão
  todo upload novo (feito por um utilizador autenticado) passa a ser "não encontrado" no
  processamento — mitigado por alterar os dois no mesmo commit/fase.
- **Sem dependência de outra feature.** Nenhum outro job assíncrono, worker ou serviço do
  backend-crm lê `data/uploads/ai/` (confirmado por busca no repo) — os workers registrados
  em `app.py` (spy_media, knowledge_ingest, collab_monitor, followup_reconciler) usam outros
  diretórios.
- **Limite de tamanho é construído do zero** — não havia nenhuma configuração de limite de
  request em lugar nenhum do projeto (nem middleware, nem proxy, nem env var).
- Uploads antigos que já estão na pasta plana `data/uploads/ai/` deixam de ser
  encontrados por `assistente_ia.py` depois da mudança (ficam órfãos). Aceitável: são
  arquivos temporários de importação (não é dado permanente do CRM), e qualquer upload em
  andamento nesse exato momento do deploy teria que ser refeito — risco mínimo, não requer
  migração.

### Proposta de fases

Fase 1 — Autenticação, isolamento por usuário e limite de tamanho — cobre os 3 pontos da
"entrega esperada" do sprint num único commit (item de baixo esforço, sem dependências
entre as partes).

---

## Problemas Identificados (estado anterior)

1. **Upload sem autenticação:** `POST /api/uploads` (`backend-crm/routes/uploads.py:46-47`)
   não tem `Depends(require_crm_access)` — qualquer chamada anónima é aceita.
2. **Sem limite de tamanho:** `content = await file.read()`
   (`backend-crm/routes/uploads.py:56`) lê o arquivo inteiro em memória sem nenhum limite,
   e não existe limite de tamanho de request configurado em nenhuma outra camada do
   projeto.
3. **Sem isolamento por utilizador:** arquivos gravados em `data/uploads/ai/{uuid}.ext`
   (`backend-crm/routes/uploads.py:11,53-54`), pasta plana compartilhada por todos os
   tenants — um `upload_id` (UUID) de outro utilizador pode ser usado em
   `POST /api/assistente-ia/processar` e `/preview` (`backend-crm/routes/assistente_ia.py:73-80,265-266`)
   para ler dados de outro tenant.

---

## Abordagem

```
POST /api/uploads (autenticado)
  → require_crm_access resolve current_user (.id)
  → grava em data/uploads/ai/{user_id}/{uuid}.ext, em streaming
      ├─ chunk a chunk ultrapassa MAX_UPLOAD_BYTES → apaga parcial, 413
      └─ dentro do limite → grava, lê amostra com pandas, retorna upload_id

POST /api/assistente-ia/processar | /preview (já autenticado)
  → resolve arquivo em data/uploads/ai/{current_user.id}/{upload_id}.ext
      ├─ upload_id pertence a current_user → processa normalmente
      └─ upload_id de outro utilizador (ou inexistente) → não encontrado (comportamento já existente, agora efetivo)
```

---

## Plano de Implementação

### Fase 1 — Autenticação, isolamento por usuário e limite de tamanho

**Objetivo:** fechar a superfície de DoS/vazamento cross-tenant exigindo login, isolando
arquivos por `user_id`, e limitando o tamanho aceito.

| Arquivo | O que muda |
|---|---|
| `backend-crm/routes/uploads.py` | `Depends(require_crm_access)`; grava em `data/uploads/ai/{user_id}/`; leitura em streaming com corte em `MAX_UPLOAD_BYTES` (413 se exceder) |
| `backend-crm/routes/assistente_ia.py` | `/processar` e `/preview` resolvem o arquivo em `data/uploads/ai/{current_user.id}/{upload_id}.ext` |
| `backend-crm/tests/test_uploads_route_auth.py` (novo) | Regressão: isolamento por usuário, corte por tamanho, extensão inválida |

```python
# ANTES (routes/uploads.py)
@router.post("/uploads")
async def upload_planilha(file: UploadFile = File(...)):
    ...
    uid = str(uuid.uuid4())
    dest = BASE / f"{uid}{ext}"
    content = await file.read()
    with open(dest, "wb") as f:
        f.write(content)

# DEPOIS
@router.post("/uploads")
async def upload_planilha(
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(require_crm_access),
):
    ...
    uid = str(uuid.uuid4())
    user_dir = BASE / str(current_user.id)
    user_dir.mkdir(parents=True, exist_ok=True)
    dest = user_dir / f"{uid}{ext}"
    size = 0
    with open(dest, "wb") as f:
        while True:
            chunk = await file.read(CHUNK_SIZE)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                f.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(413, f"Arquivo excede o limite de {MAX_UPLOAD_BYTES // (1024*1024)}MB")
            f.write(chunk)
```

---

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `d4ca522` | Auth + isolamento por usuário + limite de tamanho no upload de planilhas |

**Detalhes do commit `d4ca522`:**
- `backend-crm/routes/uploads.py` — `POST /uploads` passa a exigir `Depends(require_crm_access)`; arquivos gravados em `data/uploads/ai/{user_id}/` em vez da pasta plana; leitura trocada de `await file.read()` (buffer único) para streaming em chunks de 1MB, cortando e apagando o parcial com `HTTPException(413)` ao ultrapassar `MAX_UPLOAD_BYTES` (10MB).
- `backend-crm/routes/assistente_ia.py` — `/processar` e `/preview` passam a resolver o arquivo em `data/uploads/ai/{current_user.id}/{upload_id}.ext`, em paridade com o novo isolamento de `uploads.py`.
- `backend-crm/tests/test_uploads_route_auth.py` (novo) — 5 testes de regressão: extensão inválida (400), corte por tamanho (413 + sem arquivo parcial em disco), isolamento de upload entre usuários, e isolamento em `assistente_ia.preview` (dono consegue, intruso recebe 404).

### Relatório da Fase 1 — o que mudou na prática

**Antes:** qualquer pessoa na internet, sem login, conseguia enviar arquivos Excel/CSV
para o servidor — sem limite de tamanho, sem limite de quantidade, e todos os arquivos
ficavam misturados numa única pasta compartilhada entre todos os clientes do CRM.

**Agora:** só um utilizador autenticado do CRM (com assinatura ativa do produto) consegue
enviar arquivos. Cada arquivo enviado fica guardado numa pasta exclusiva desse
utilizador, e arquivos maiores que 10MB são recusados antes de terminar de gravar em
disco.

**Para validar:** Cenários P1, P2, P3, C1 e C2, abaixo.

---

## Checks de Validação

### Cenário P1 — Upload sem token é rejeitado
- [ ] Chamar `POST /api/uploads` sem header `Authorization`
- [ ] Confirmar: resposta 401

### Cenário P2 — Upload autenticado funciona normalmente
- [ ] Login no frontend-crm, ir em Assistente IA, enviar planilha válida (.xlsx ou .csv)
- [ ] Confirmar: upload aceito, amostra exibida, `upload_id` retornado

### Cenário P3 — Processamento após upload continua funcionando
- [ ] Usando o `upload_id` do Cenário P2, chamar `/api/assistente-ia/processar` (fluxo normal da página)
- [ ] Confirmar: processa normalmente (arquivo é encontrado na pasta do usuário)

### Cenário C1 — Arquivo acima do limite é rejeitado
- [ ] Enviar um arquivo maior que `MAX_UPLOAD_BYTES` via HTTP direto (curl/requests) com token válido
- [ ] Confirmar: resposta 413, e nenhum arquivo parcial fica em `data/uploads/ai/`

### Cenário C2 — Isolamento entre usuários
- [ ] Usuário A envia planilha, obtém `upload_id`
- [ ] Usuário B (autenticado, outro `user_id`) tenta `/api/assistente-ia/processar` ou `/preview` com esse `upload_id`
- [ ] Confirmar: "arquivo não encontrado" (404), não processa dado de outro tenant

---

## Ajustes Possíveis Pós-Implementação

- O limite de tamanho é aplicado na camada da aplicação (streaming), não numa camada de
  proxy/infra — um limite adicional em nginx/Railway (`client_max_body_size` ou
  equivalente) reforçaria a proteção contra corpos de request muito grandes antes mesmo de
  chegar ao processo Python, mas está fora do escopo deste fix (exigiria mudança de infra,
  não de código).
- Não foi implementada limpeza/expiração automática de arquivos antigos em
  `data/uploads/ai/{user_id}/` (mencionada como "limpar" no achado original) — os arquivos
  de upload são temporários por natureza (usados só durante o fluxo de importação), mas não
  há hoje nenhuma rotina que os apague depois de processados. Candidato a melhoria futura
  se o volume de disco se tornar um problema.
