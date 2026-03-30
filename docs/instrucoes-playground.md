# Instruções para Testar o Playground de IA

Guia prático para subir os serviços e executar testes no endpoint `POST /api/playground/chat`.

---

## 1. Pré-requisitos

Cada serviço tem o seu próprio `.venv`. Confirmar que existem:

```
backend-core/.venv/
backend-crm/.venv/
backend-executors/.venv/
```

Se algum estiver em falta:

```bash
cd backend-<serviço>
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt
```

---

## 2. Variável de ambiente obrigatória

O `backend-crm` precisa saber onde está o `backend-executors`. Confirmar que o ficheiro `backend-crm/.env` contém:

```
EXECUTORS_BASE_URL=http://localhost:8002
```

> Esta variável **não está no `.gitignore`** via `.env.example`, mas o `.env` real não é commitado. Verificar sempre antes de testar.

---

## 3. Subir os serviços

Usar **três terminais separados**, um por serviço. A ordem importa: o `backend-core` deve estar pronto antes do `backend-crm`.

### Terminal 1 — backend-core (porta 8001)

```bash
cd backend-core
PYTHONUTF8=1 .venv/Scripts/python -m uvicorn app.main:app --port 8001 --host 127.0.0.1
```

### Terminal 2 — backend-executors (porta 8002)

```bash
cd backend-executors
PYTHONUTF8=1 .venv/Scripts/python -m uvicorn app.main:app --port 8002 --host 127.0.0.1
```

### Terminal 3 — backend-crm (porta 8000)

```bash
cd backend-crm
PYTHONUTF8=1 .venv/Scripts/python -m uvicorn app:app --port 8000 --host 127.0.0.1
```

> **Nota:** `PYTHONUTF8=1` é obrigatório no Windows para evitar erros de encoding com emojis nos logs.

### Verificar que os 3 serviços estão online

```bash
curl http://localhost:8001/         # {"status":"ok"}
curl http://localhost:8002/health   # {"status":"ok","service":"executors",...}
curl http://localhost:8000/         # {"status":"API CRM rodando ..."}
```

---

## 4. Autenticação

### Utilizador de teste já existente (usar directamente)

Foi criado durante a Fase 6 (2026-03-30) um utilizador dedicado a testes do playground no `backend-core`:

| Campo | Valor |
|---|---|
| `user_id` | `3` |
| `name` | `Playground Tester` |
| `ai_profile_id` | `2` |
| `agent_mode` | `consultivo` |
| `template_key` | `sdr_padrao` |
| `agent_name` | `Lucas` |

As credenciais de acesso podem ser consultadas directamente no banco `backend-core/core.db` (tabela `users`, `id=3`).

Para obter um token fresco (expira em 120 minutos):

```bash
curl -X POST http://localhost:8001/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "playground_test@test.com", "password": "<ver banco>"}'
```

> Se receber `{"detail":"Token inválido ou expirado"}` nalgum teste, basta fazer novo login.

---

### Criar nova conta de teste (alternativa)

Caso o utilizador acima não exista ou seja necessário um novo ambiente limpo:

```bash
# 1. Registar conta
curl -X POST http://localhost:8001/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "test@test.com", "password": "testpass123", "name": "Tester"}'

# 2. Login
curl -X POST http://localhost:8001/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@test.com", "password": "testpass123"}'
```

Guardar o `access_token` da resposta.

---

## 5. Criar AI Profile (só se não existir)

O utilizador `user_id=3` já tem o `ai_profile_id=2` criado — pode usar directamente nos testes.

Para criar um novo perfil para outra conta, ver os `template_key` válidos:

```bash
curl http://localhost:8001/ai-templates
# Valores: sdr_padrao | consultor_especialista | closer_agressivo | hybrid_scheduler
```

Criar o perfil:

```bash
curl -X POST http://localhost:8001/ai-profiles \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Agente Teste",
    "brand_name": "Empresa Teste",
    "agent_name": "Lucas",
    "agent_mode": "consultivo",
    "tone_of_voice": "profissional",
    "niche": "Software B2B",
    "target_audience": "Pequenas e médias empresas",
    "offer_description": "CRM com automação WhatsApp",
    "goals": "Qualificar leads e fechar vendas",
    "template_key": "sdr_padrao"
  }'
```

Guardar o `id` retornado — será o `ai_profile_id` nos testes.

---

## 6. Criar subscrição activa (só na primeira vez)

Se o playground retornar `{"detail":"Assinatura do produto CRM ausente ou inativa"}`, inserir directamente no banco do `backend-core`:

```bash
cd backend-core
.venv/Scripts/python - <<'EOF'
import sqlite3
conn = sqlite3.connect('core.db')

# Descobrir IDs
user = conn.execute("SELECT id FROM users WHERE email='test@test.com'").fetchone()
product = conn.execute("SELECT id FROM products WHERE code='crm'").fetchone()
plan = conn.execute("SELECT id FROM plans WHERE code='crm_pro'").fetchone()

conn.execute(
    "INSERT INTO subscriptions (user_id, product_id, plan_id, status, created_at) VALUES (?, ?, ?, 'active', datetime('now'))",
    (user[0], product[0], plan[0])
)
conn.commit()
print(f"Subscricao criada para user_id={user[0]}")
EOF
```

---

## 7. Testes do Playground

Substituir `<TOKEN>` e `<AI_PROFILE_ID>` pelos valores obtidos acima.

### Teste 1 — Primeira mensagem (cria lead sandbox)

```bash
curl -X POST http://localhost:8000/api/playground/chat \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "ai_profile_id": <AI_PROFILE_ID>,
    "message": "Olá, vi o vosso anúncio e tenho interesse",
    "lead_id": null
  }'
```

Verificar na resposta:
- `lead_id` — guardar para as próximas chamadas
- `decision_trace.lead_is_sandbox: true`
- `lead_state.category: "qualification"`

Verificar no banco (confirmar `is_playground=1`):

```bash
cd backend-crm
.venv/Scripts/python -c "
import sqlite3
conn = sqlite3.connect('database/crm.db')
conn.row_factory = sqlite3.Row
r = conn.execute('SELECT id, is_playground, origin, phone, category FROM leads ORDER BY id DESC LIMIT 1').fetchone()
print(dict(r))
"
```

### Teste 2 — Mensagens sequenciais (histórico e qualificação evoluem)

```bash
# Segunda mensagem — mesmo lead_id
curl -X POST http://localhost:8000/api/playground/chat \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "ai_profile_id": <AI_PROFILE_ID>,
    "message": "Sou o dono e decido sozinho. Temos urgência para este mês.",
    "lead_id": <LEAD_ID>
  }'

# Terceira mensagem
curl -X POST http://localhost:8000/api/playground/chat \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "ai_profile_id": <AI_PROFILE_ID>,
    "message": "O orçamento é de 200 euros por mês.",
    "lead_id": <LEAD_ID>
  }'
```

Verificar histórico no banco:

```bash
cd backend-crm
.venv/Scripts/python -c "
import sqlite3
conn = sqlite3.connect('database/crm.db')
conn.row_factory = sqlite3.Row
rows = conn.execute('SELECT model, body FROM messages WHERE lead_id=<LEAD_ID> ORDER BY id').fetchall()
print(f'Total: {len(rows)} mensagens')
for r in rows:
    print(f'  [{r[\"model\"]}]: {r[\"body\"][:80]}')
qs = conn.execute('SELECT data_json FROM lead_qualification_state WHERE lead_id=<LEAD_ID>').fetchone()
print('QS:', qs[\"data_json\"] if qs else 'vazio')
"
```

### Teste 3 — Reset da conversa

```bash
curl -X POST http://localhost:8000/api/playground/chat \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "ai_profile_id": <AI_PROFILE_ID>,
    "message": "Olá, começo de novo",
    "lead_id": <LEAD_ID>,
    "reset": true
  }'
```

Após o reset, o banco deve mostrar:
- Apenas 2 mensagens (inbound + outbound da nova conversa)
- `qualification_state.data_json = {}`
- `leads.category = "qualification"`

### Teste 4 — Lead sandbox não aparece no Kanban

```bash
curl http://localhost:8000/api/leads \
  -H "Authorization: Bearer <TOKEN>"
```

O `lead_id` do sandbox **não deve aparecer** na lista retornada.

### Teste 5 — Rejeição de ai_profile_id de outro utilizador

```bash
# Usar um ai_profile_id que não pertence ao token autenticado
curl -X POST http://localhost:8000/api/playground/chat \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "ai_profile_id": 999,
    "message": "teste",
    "lead_id": null
  }'
# Esperado: 403 Forbidden
```

---

## 8. Inspecção rápida do banco

```bash
cd backend-crm
.venv/Scripts/python - <<'EOF'
import sqlite3
conn = sqlite3.connect('database/crm.db')
conn.row_factory = sqlite3.Row

# Todos os leads sandbox
rows = conn.execute(
    "SELECT id, user_id, phone, category, created_at FROM leads WHERE is_playground=1 ORDER BY id DESC LIMIT 10"
).fetchall()
print(f"Leads sandbox: {len(rows)}")
for r in rows:
    print(" ", dict(r))
EOF
```

---

## 9. Problemas comuns

| Erro | Causa | Solução |
|---|---|---|
| `EXECUTORS_BASE_URL não configurado` | Variável ausente no `.env` do CRM | Adicionar `EXECUTORS_BASE_URL=http://localhost:8002` ao `backend-crm/.env` |
| `Service token rejeitado pelo backend-executors` | Executors ainda com código antigo / `os.getenv` vazio | Confirmar que `backend-executors/app/api/playground_internal.py` usa `settings.*` para ler os tokens |
| `Assinatura do produto CRM ausente ou inativa` | Utilizador sem subscrição activa | Inserir subscrição no banco (ver secção 6) |
| `Token inválido ou expirado` | JWT expirou (120 min) | Fazer novo login e obter token fresco |
| `OperationalError: no such column: is_playground` | Bug na string `ensure_column` ou banco antigo sem a coluna | Reiniciar o `backend-crm` — o `init_db()` aplica a migração idempotente automaticamente |
| `UnicodeEncodeError` nos logs | Windows sem UTF-8 | Sempre usar `PYTHONUTF8=1` ao lançar uvicorn |
| `[WinError 10048]` porta em uso | Processo anterior ainda vivo | `taskkill /F /PID <pid>` ou fechar o terminal anterior |

---

## 10. Service tokens de referência (ambiente local)

| Token | Valor (dev local) | Usado por |
|---|---|---|
| `CORE_SERVICE_TOKEN` | Em `backend-core/.env` | backend-crm → backend-core e backend-crm → backend-executors |
| `CRM_SERVICE_TOKEN` | Em `backend-crm/.env` | backend-executors valida ambos |

O `backend-executors` aceita qualquer um dos dois tokens na header `X-Service-Token`.

---

*Documento criado em 2026-03-30, baseado nos testes da Fase 6 da Etapa 11.*
