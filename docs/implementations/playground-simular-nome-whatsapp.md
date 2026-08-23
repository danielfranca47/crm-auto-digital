# Playground — simular nome do WhatsApp do lead sandbox

**Branch:** `feat/playground-simular-nome-whatsapp`
**Status:** Todos os cenários validados (23/08/2026)

---

## Motivação

Durante o teste ao vivo da feature "nome do WhatsApp no lead" (`docs/implementations/nome-whatsapp-lead-variaveis-fluxo-venda.md`), testamos no Playground se o bot reconhece corretamente o nome do lead vindo do WhatsApp (`wa_display_name`). Descobrimos que o Playground não tem como simular esse campo: ele sempre cria um lead sandbox "do zero" sem `wa_display_name`, porque esse campo hoje só é populado pelo caminho real (webhook da UazAPI). Para provar que o mecanismo funcionava, foi necessário editar o banco de dados manualmente por fora da interface — algo que o utilizador não consegue fazer sozinho.

O utilizador pediu um campo opcional na tela de configuração do Playground para preencher esse "nome do WhatsApp simulado" antes de iniciar uma sessão de teste.

---

## Problemas Identificados (estado anterior)

1. **Sem campo no request do Playground:** `backend-crm/routes/playground.py:78-87` (`PlaygroundChatRequest`) não tem nenhum campo para nome simulado.
2. **Lead sandbox nasce sem `wa_display_name`:** `backend-crm/routes/playground.py:247-260` (`_create_sandbox_lead`) insere o lead sandbox sem tocar essa coluna (que já existe desde a feature anterior).
3. **Sem UI para preencher:** `frontend-crm/src/components/playground/PlaygroundConfigModal.tsx` (modal "Configurar Sessão de Playground") não tem nenhum input relacionado; `frontend-crm/src/services/api.ts:1630-1639` (tipo do payload de `api.playground.chat`) também não tem esse campo.

---

## Abordagem

```
Modal "Configurar Sessão de Playground"
  → utilizador preenche opcionalmente "Nome do WhatsApp (simulação)"
  → PlaygroundSession.waDisplayName guardado no estado da sessão
  → toda chamada a api.playground.chat(...) repassa wa_display_name
  → backend: só usado no momento de criar o lead sandbox (_create_sandbox_lead)
       (mesma regra do mundo real: wa_display_name só é gravado na criação,
       nunca atualizado depois)
```

---

## Plano de Implementação

### Fase 1 — Campo opcional ponta a ponta

**Objetivo:** permitir simular `wa_display_name` no Playground, sem afetar o comportamento existente quando o campo fica vazio.

| Arquivo | O que muda |
|---|---|
| `backend-crm/routes/playground.py` | `PlaygroundChatRequest` ganha `wa_display_name: Optional[str] = None`; `_create_sandbox_lead()` ganha parâmetro `wa_display_name` e grava na coluna; chamada em `/playground/chat` passa `body.wa_display_name` |
| `frontend-crm/src/services/api.ts` | Tipo do payload de `playground.chat` ganha `wa_display_name?: string \| null` |
| `frontend-crm/src/components/playground/PlaygroundConfigModal.tsx` | `PlaygroundSession` ganha `waDisplayName?: string \| null`; novo `<Input>` opcional "Nome do WhatsApp do lead (simulação)" com texto de ajuda; valor incluído no `onStart(...)` |
| `frontend-crm/src/pages/Playground.tsx` | As 6 chamadas existentes a `api.playground.chat(...)` passam `wa_display_name: session.waDisplayName ?? null` |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `6fd3105` | Campo `wa_display_name` opcional ponta a ponta no Playground |

**Detalhes do commit `6fd3105`:**
- `backend-crm/routes/playground.py` — `PlaygroundChatRequest.wa_display_name`; `_create_sandbox_lead()` grava o valor na criação
- `frontend-crm/src/services/api.ts` — tipo do payload de `playground.chat` ganha o campo
- `frontend-crm/src/components/playground/PlaygroundConfigModal.tsx` — novo input "Nome do WhatsApp do lead (simulação)"
- `frontend-crm/src/pages/Playground.tsx` — repassado nas 6 chamadas a `api.playground.chat(...)`

### Relatório da Fase 1 — o que mudou na prática

**Antes:** o Playground não tinha nenhuma forma de simular o nome do WhatsApp de um lead de teste — esse campo só existia de verdade quando alguém mandava mensagem pelo WhatsApp real. Para testar se o bot reconhecia o nome, era preciso editar o banco de dados manualmente por fora da tela.

**Agora:** ao configurar uma nova sessão de Playground, existe um campo opcional "Nome do WhatsApp do lead (simulação)". Preenchendo-o antes de iniciar a conversa, o lead de teste já nasce com esse nome — e o bot deve reconhecê-lo e usá-lo normalmente, do mesmo jeito que reconheceria um nome vindo do WhatsApp real.

**Para validar:** Cenário P1, abaixo.

---

## Checks de Validação

### Cenário P1 — Bot reconhece o nome simulado no Playground
- [x] No modal "Configurar Sessão", preencher o novo campo com um nome de teste
- [x] Iniciar sessão, mandar mensagem inicial como lead
- [x] Confirmar que o valor chega resolvido (não literal) num bloco do Fluxo de Venda que usa `{{lead.nome_whatsapp}}`
- [x] Confirmar no banco que `wa_display_name` foi persistido na criação do lead sandbox
- **Validado em:** 23/08/2026 — via browser (chrome-devtools MCP). Preenchido "Marcos" no novo campo, sessão iniciada, mensagem "Oi!" enviada. Bloco de Recepção (`{{lead.nome_whatsapp}}`, criado durante o teste manual anterior) resolveu na primeira mensagem: *"Ola, seja bem-vindo! Vou te chamar de Marcos!"* — sem nenhuma edição manual no banco desta vez. Confirmado via `sqlite3`: lead sandbox 508 com `wa_display_name='Marcos'`.
- **Nota:** uma tentativa anterior (lead 507) caiu num fallback de `llm_failure` — o modelo respondeu `route_to="qualificacao"` (não é um dos valores aceites pelo enum) e o pipeline caiu em handoff. Não relacionado a esta feature (o payload confirmou `wa_display_name` enviado corretamente); ver "Achado lateral" abaixo.

---

## Ajustes Possíveis Pós-Implementação

- O campo só se aplica na criação do lead sandbox (primeira mensagem da sessão) — igual ao comportamento real. Se o utilizador mudar o campo no meio de uma sessão já iniciada, não terá efeito até uma nova sessão.

**Achado lateral, fora do escopo — Mãe pode retornar `route_to` fora do enum aceite:** durante o teste, a LLM Mãe respondeu `"route_to": "qualificacao"` (grafia com "ç", claramente uma alucinação de idioma) em vez de `"qualification"` (único valor aceite pelo `MotherDecision`). O Pydantic rejeitou a resposta (`ValidationError: literal_error`) e o pipeline caiu no fallback de `handoff` (`next_action=handoff, reason=llm_failure`), desabilitando o bot para aquele lead de teste. Não é causado por esta feature — o payload confirmou que `wa_display_name` chegou corretamente ao backend antes da falha. Reproduzido uma vez em várias tentativas (parece raro/esporádico). Vale abrir um item em `docs/plans/` para tornar a validação do `route_to` mais tolerante (ex.: normalizar/mapear variantes conhecidas antes de validar), se o utilizador quiser priorizar.
