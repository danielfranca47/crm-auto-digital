# Playground — simular nome do WhatsApp do lead sandbox

**Branch:** `feat/playground-simular-nome-whatsapp`
**Status:** Em andamento

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

---

## Checks de Validação

### Cenário P1 — Bot reconhece o nome simulado no Playground
- [ ] No modal "Configurar Sessão", preencher o novo campo com um nome de teste
- [ ] Iniciar sessão, mandar mensagem inicial como lead
- [ ] Perguntar diretamente "qual é o meu nome?" e confirmar que o bot responde com o nome preenchido — sem editar o banco manualmente
- [ ] Confirmar no banco que `wa_display_name` foi persistido na criação do lead sandbox

---

## Ajustes Possíveis Pós-Implementação

- O campo só se aplica na criação do lead sandbox (primeira mensagem da sessão) — igual ao comportamento real. Se o utilizador mudar o campo no meio de uma sessão já iniciada, não terá efeito até uma nova sessão.
