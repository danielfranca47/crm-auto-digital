# Fix: Playground em produção (Railway) — Connection refused + resposta genérica da IA

**Branch:** `main`
**Status:** Todos os cenários validados (18/06/2026)

---

## Motivação

Em produção (Railway), o Playground (`frontend-crm`) apresentou dois problemas distintos e
sequenciais ao tentar enviar uma mensagem de teste:

1. `POST /api/playground/chat` devolvia sempre **502 Bad Gateway** —
   `"Falha ao contactar backend-executors: [Errno 111] Connection refused"`.
2. Depois de resolvido o problema 1, o Playground passou a responder, mas **sempre com a
   mesma mensagem genérica** ("Olá! Como posso ajudar?"), instantaneamente, sem variação —
   indicando que não estava a chamar a IA de verdade.

Os dois problemas eram de configuração de produção, não de lógica de negócio — mas levaram
bastante tempo a diagnosticar porque os sintomas (erro de rede, resposta "funcional" mas
fake) não apontavam directamente para a causa.

---

## Problemas Identificados (estado anterior)

### Problema 1 — Connection refused entre backend-crm e backend-executors

**Causa raiz:** `backend-crm/app.py:11-12` faz:
```python
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR / ".env.local", override=True)
```
`backend-crm/.env.local` estava **commitado no git** (não estava no `.gitignore`) com
`EXECUTORS_BASE_URL=http://localhost:8002` (valor de desenvolvimento local). Por estar
commitado, esse ficheiro ia para dentro do container de produção no Railway, e por ser
carregado com `override=True`, sobrepunha **sempre** a variável `EXECUTORS_BASE_URL`
configurada no dashboard do Railway — independentemente do valor lá definido.

Isto explicava por que nenhuma tentativa de correcção de rede (domínio público vs. privado,
IPv4 vs. IPv6, toggle "Outbound IPv6" do Railway, dual-stack no `backend-executors`) tinha
qualquer efeito: o processo do `backend-crm` nunca chegou a usar o valor configurado — tentava
sempre `localhost:8002` dentro do seu próprio container, onde nada está à escuta.

**Ficheiro:** `backend-crm/routes/playground.py:321-340` (`_call_executors_decide`) — é onde
o erro era levantado, envolvendo qualquer `httpx.RequestError` da chamada a
`{EXECUTORS_BASE_URL}/api/internal/playground/decide`.

### Problema 2 — Resposta sempre genérica ("Olá! Como posso ajudar?")

**Causa raiz:** `backend-executors/app/services/llm_service.py:73-75`:
```python
def generate_decision_text(prompt: str) -> str:
    if not settings.llm_api_key:
        return _stub_response()  # {"message_text": "Olá! Como posso ajudar?", "reason": "stub_no_key"}
```
A variável `LLM_API_KEY` (e `LLM_API_BASE`, cujo default é `http://localhost:8002` — outro
valor de placeholder local) **nunca tinham sido configuradas** no serviço `backend-executors`
no Railway. Isto fazia com que **todas** as chamadas à IA (rota mãe, resultado filho, texto de
decisão) caíssem no stub hardcoded, em vez de chamar a OpenAI de verdade — por isso a resposta
era sempre idêntica e instantânea.

Esta falha esteve sempre presente, mas só ficou visível depois de corrigido o Problema 1 — antes
disso, o pedido nunca chegava a alcançar este código (falhava na rede antes).

---

## Abordagem

```
Playground envia mensagem
  → backend-crm POST /api/playground/chat
      → _call_executors_decide() → POST {EXECUTORS_BASE_URL}/api/internal/playground/decide
          → backend-executors: playground_internal.py → decision engine
              → llm_service.generate_mother_route() / generate_decision_text() / generate_child_result()
                  ├─ settings.llm_api_key ausente → stub fixo (sintoma do Problema 2)
                  └─ settings.llm_api_key presente → chamada real à OpenAI (Responses API)
```

Diagnóstico do Problema 1 levou por várias hipóteses de rede do Railway (documentadas no
histórico de commits) até se confirmar, com um log de debug temporário, que o host realmente
contactado era `localhost:8002` — revelando o `.env.local` como causa.

Diagnóstico do Problema 2 foi mais direto: o texto da resposta ("Olá! Como posso ajudar?")
é literalmente hardcoded em `_stub_response()`, e o campo `reason: "stub_no_key"` no payload
de decisão confirmou a causa sem ambiguidade.

---

## Plano de Implementação

### Fase 1 — Corrigir override de `.env.local` (Problema 1)

| Arquivo | O que mudou |
|---|---|
| `backend-crm/.env.local` | Removido do git (`git rm --cached`) — mantido localmente para dev |
| `backend-crm/.gitignore` | Adicionado `.env.local` |
| `backend-crm/routes/playground.py` | Removido log de debug temporário usado no diagnóstico |
| `backend-executors/Procfile` | Simplificado de volta a `uvicorn app.main:app --host 0.0.0.0 --port $PORT` (revertendo tentativas anteriores de dual-stack IPv4/IPv6 que não eram a causa real) |
| `backend-executors/app/dualstack.py` | Removido (não era necessário) |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `7bab7d8` | fix: remover `.env.local` do git (causa raiz) |
| 2 | `9181b27` | chore: completar fix (.gitignore + remover debug log) |
| 3 | `37f9b68` | revert: simplificar backend-executors de volta a `uvicorn` 0.0.0.0 simples |

Configuração final no Railway: `EXECUTORS_BASE_URL=https://backend-executors-production.up.railway.app`
(domínio público) no `backend-crm`.

### Fase 2 — Configurar `LLM_API_KEY` / `LLM_API_BASE` no backend-executors (Problema 2)

| O que mudou | Onde |
|---|---|
| `LLM_API_KEY` definido (mesma chave OpenAI usada no `backend-crm`) | Variável Railway, serviço `backend-executors` |
| `LLM_API_BASE=https://api.openai.com/v1/responses` definido | Variável Railway, serviço `backend-executors` |

Sem alteração de código — só configuração de variáveis de ambiente em produção.

---

## Checks de Validação

### Cenário P1 — Playground envia mensagem e recebe resposta real da IA
- [x] Abrir Playground em produção, enviar mensagem de teste
- [x] Confirmar: resposta não é mais o texto fixo "Olá! Como posso ajudar?" / `stub_no_key`
- **Validado em:** 18/06/2026 — utilizador confirmou que o Playground "voltou a performar bem
  com as consultas às LLMs" e já não dá resposta genérica

### Cenário C1 — `/health` público do backend-executors permanece estável
- [x] `curl https://backend-executors-production.up.railway.app/health` → `200`
- **Validado em:** 18/06/2026 — confirmado após cada deploy desta investigação

---

## Ajustes Possíveis Pós-Implementação

- `backend-executors/.env.example` documenta `LLM_API_BASE=https://api.openai.com/v1`
  (sem `/responses`) — inconsistente com `README.md:146`, que tem o valor correto
  (`.../v1/responses`). Pequena divergência de documentação, não afecta produção
  (a variável Railway já está com o valor certo), mas vale corrigir o `.env.example` numa
  próxima alteração nesse ficheiro.
- Vale considerar adicionar uma verificação de startup (ou endpoint de health mais completo)
  no `backend-executors` que sinalize claramente quando está a operar em modo stub
  (`LLM_API_KEY` ausente) — hoje isso só é visível inspeccionando o campo `reason` da resposta.
