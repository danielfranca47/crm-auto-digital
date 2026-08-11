# Registrar interação passada (backfill manual de mensagens)

**Branch:** `main`
**Status:** Em andamento

---

## Motivação

Um lead às vezes já trocou mensagens no WhatsApp com o operador (humano) **antes** de o agente de IA ser ativado para aquele número/conta (ex.: cliente em processo de adesão ao plano Growth, que já vinha recebendo "oi, gostaria de saber mais informações" de leads antes de configurar o CRM).

Quando o agente é ligado e o lead escreve de novo, o sistema hoje sempre força uma fase de "recepção"/saudação no primeiro turno do bot — decisão baseada unicamente em `outbound_count == 0` (nenhuma linha `model='outbound'` na tabela `messages` daquele lead), em `_enforce_greeting_first` (`backend-executors/app/services/decision_engine.py:3895-3912`). Essa contagem vem de `get_recent_history()` (`backend-crm/services/ai_orchestrator/history.py:9-27`), que só lê `SELECT id, channel, body, model, createdAt FROM messages WHERE lead_id=?`.

Causa raiz: o CRM não tem nenhuma forma de registrar manualmente um histórico de conversa que aconteceu fora do pipeline automatizado — o campo `observations` do lead existe mas não é lido em nenhum lugar do prompt do LLM.

Comportamento desejado: o operador consegue pré-cadastrar esse histórico (pares "mensagem do lead" / "mensagem enviada por mim") antes do primeiro contato real, dando contexto ao LLM e evitando a saudação forçada indevida.

---

## Problemas Identificados (estado anterior)

1. **Sem forma de registrar histórico manual:** não existe endpoint para inserir mensagens retroativas na tabela `messages` — só o pipeline real (`inbound_handler.py`, `jobs_service.py`, `routes/executor.py`) grava lá.
2. **`observations` do lead não chega ao LLM:** campo existe em `models.py`/`routes/leads.py` mas não é consumido em `orchestrator.py` nem `decision_engine.py` — não é uma via alternativa viável para dar contexto.
3. **Saudação forçada é hardcoded e não configurável:** `_enforce_greeting_first` decide só por `outbound_count`, sem olhar `category` do lead nem qualquer configuração de `/ai-profile`.

---

## Abordagem

```
Operador cadastra lead manualmente (sem mensagens ainda)
  → abre o card do lead → seção "Registrar interação passada"
  → adiciona turnos (Lead / Eu) → Salvar
  → POST /api/leads/{id}/interactions/backfill
       ├─ lead já tem mensagens → 409, bloqueado
       └─ lead sem mensagens → insere cada turno em `messages`
            (model='inbound'|'outbound', createdAt sequencial no passado)
            + log em prospection_logs (action='manual_backfill')

Mais tarde, lead manda mensagem real via WhatsApp
  → inbound_handler → get_recent_history() já enxerga os turnos manuais
  → outbound_count >= 1 → _enforce_greeting_first NÃO força recepção
  → LLM responde já com contexto da conversa anterior
```

---

## Plano de Implementação

### Fase 1 — Backend: modelo e endpoint de backfill

**Objetivo:** permitir inserir manualmente um histórico de mensagens para um lead sem mensagens, com guardrail de 409 se já houver histórico real.

| Arquivo | O que muda |
|---|---|
| `backend-crm/models.py` | Novos modelos `BackfillTurn` e `BackfillInteractionsPayload`, após `MessageOut` |
| `backend-crm/routes/leads.py` | Novo endpoint `POST /{lead_id}/interactions/backfill`, após `get_lead_qualification_fields` |

```python
# models.py — novo
class BackfillTurn(BaseModel):
    sender: Literal["lead", "me"]
    body: str = Field(min_length=1, max_length=4000)
    occurred_at: Optional[datetime] = None

class BackfillInteractionsPayload(BaseModel):
    turns: List[BackfillTurn] = Field(min_length=1, max_length=40)
```

Guardrail central: `SELECT COUNT(*) FROM messages WHERE lead_id = ?` — se `> 0`, `409`. Timestamp artificial (quando `occurred_at` ausente) gerado a partir de `utcnow() - N segundos`, incrementando 1s por turno, sempre no passado. Cada turno grava em `messages` (`model='inbound'` se `sender='lead'`, `'outbound'` se `sender='me'`) e em `prospection_logs` (`action='manual_backfill'`) para auditoria — sem alterar o contrato de `model`, que precisa continuar exatamente `'inbound'`/`'outbound'` para o guardrail de saudação em `decision_engine.py` funcionar.

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `26ae7cb` | backend: modelos + endpoint de backfill com guardrail 409 e timestamps sequenciais |

**Detalhes do commit `26ae7cb`:**
- `backend-crm/models.py` — `BackfillTurn` e `BackfillInteractionsPayload` (após `MessageOut`)
- `backend-crm/routes/leads.py` — import dos novos modelos; endpoint `POST /{lead_id}/interactions/backfill` (após `get_lead_qualification_fields`)
- `docs/implementations/backfill-interacao-passada.md` — arquivo criado

### Relatório da Fase 1 — o que mudou na prática

**Antes:** não havia nenhuma forma de registrar no CRM uma conversa que já tinha acontecido no WhatsApp antes de o agente de IA ser ligado — o lead sempre nascia "zerado", sem histórico.

**Agora:** existe um endpoint (`POST /api/leads/{lead_id}/interactions/backfill`) que aceita uma lista de turnos passados ("mensagem do lead" / "mensagem enviada por mim") e grava isso na mesma tabela que o agente real lê. Só funciona em leads que ainda não têm nenhuma mensagem — se já tiverem, o pedido é recusado (código 409) para não bagunçar uma conversa real em andamento.

**Para validar:** Cenários P1, P2 e P3, na seção "Checks de Validação" abaixo — ainda pendentes de execução (não há UI nesta fase, só a API).

**Nota de ambiente:** não consegui rodar o backend localmente para testar ao vivo nesta máquina — não há virtualenv em `backend-crm/` e o Python global tem uma versão do FastAPI incompatível com o resto do projeto (erro em `routes/appointments.py`, arquivo não relacionado a esta mudança). Validei só sintaxe (`ast.parse`) e revisão manual do código. Recomendo testar Cenários P1-P3 no seu ambiente configurado.

### Fase 2 — Frontend: seção no LeadCardDialog

**Objetivo:** UI para o operador cadastrar os turnos sem precisar chamar a API manualmente.

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/services/api.ts` | Nova função `backfillLeadInteractions(leadId, turns)` |
| `frontend-crm/src/components/LeadCardDialog.tsx` | `useEffect` novo para detectar `hasExistingMessages`; nova seção "Registrar interação passada", visível só quando o lead não tem mensagens |

---

## Checks de Validação

### Cenário P1 — Backfill em lead sem mensagens (backend direto)
- [x] (2026-08-11) Criar lead de teste sem mensagens — lead id 436, conta de teste (`user_id=15`)
- [x] (2026-08-11) `POST /interactions/backfill` com 3 turnos (2 com `occurred_at` no passado, 1 sem) — `201`/`ok`, `created: [1861, 1863, 1862]`, `counts: {inbound: 2, outbound: 1}`
- [x] (2026-08-11) Confirmado via SQL direto em `messages`: 3 linhas, ordem cronológica correta por `createdAt` (turno sem `occurred_at` recebeu timestamp artificial = agora), `model` `inbound`/`outbound`/`inbound` batendo com o sender de cada turno, `body` preservado. 3 linhas espelhadas em `prospection_logs` com `action='manual_backfill'`.

### Cenário P2 — Guardrail de 409
- [x] (2026-08-11) Repetido o backfill no mesmo lead (id 436) — `409` confirmado
- [x] (2026-08-11) Contagem de `messages` para o lead permaneceu em 3 (nenhuma linha nova inserida)

### Cenário P3 — Leitura via endpoint real de mensagens
- [x] (2026-08-11) `GET /assistente-ia/messages/{lead_id}` após backfill retorna as mensagens do backfill
- [x] (2026-08-11) Nuance encontrada (comportamento pré-existente do endpoint, não é bug desta feature): o parâmetro `latest` é `True` por padrão e deduplica por `channel`, então com `latest=true` só o turno mais recente aparece (todos os turnos do backfill usam `channel='whatsapp'`). Com `?latest=false` os 3 turnos aparecem completos, na ordem esperada.

> Testado ao vivo com `backend-core` (8001) e `backend-crm` (8000) rodando via `.venv` de cada serviço (`PYTHONUTF8=1` no backend-crm por causa de um `print` com emoji em `database.py:23`, pré-existente). Lead de teste (id 436) removido ao final para não deixar resíduo na conta de teste.

### Cenário P4 — UI: seção aparece só quando aplicável
- [ ] Abrir card de lead sem mensagens → seção "Registrar interação passada" visível
- [ ] Adicionar 2 turnos, salvar → toast de sucesso, seção desaparece
- [ ] Reabrir o card → seção não reaparece (lead já tem mensagens)

### Cenário C1 — Bypass real da saudação forçada (fora do escopo desta iteração, validar depois)
- [ ] Conectar número de teste, fazer backfill de um lead, mandar mensagem real via WhatsApp
- [ ] Confirmar no trace do `decision_engine` que `reason` não contém `greeting_first_enforced`

---

## Ajustes Possíveis Pós-Implementação

- Extração automática de qualificação a partir do texto do backfill não foi incluída — qualificação continua 100% manual via "Critérios de Qualificação" (decisão consciente, ver Plan Mode).
- Sem lock/transação dedicada para a corrida entre o `SELECT COUNT(*)` e o `INSERT` — risco residual aceito dado o caso de uso (lead ainda não contactado de verdade).
