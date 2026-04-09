# Guia de Uso — Playground IA (Interface Web)

Interface visual para simular conversas com o agente e registar feedback em tempo real.
Acesso: menu lateral → **Playground IA** (ícone de frasco) ou diretamente em `/playground`.

---

## O que precisa estar rodando

### Obrigatório

| Serviço | Porta | Como subir |
|---|---|---|
| **backend-core** | 8001 | `cd backend-core && PYTHONUTF8=1 .venv/Scripts/python -m uvicorn app.main:app --port 8001 --host 127.0.0.1` |
| **backend-crm** | 8000 | `cd backend-crm && PYTHONUTF8=1 .venv/Scripts/python -m uvicorn app:app --port 8000 --host 127.0.0.1` |
| **backend-executors** | 8002 | `cd backend-executors && PYTHONUTF8=1 .venv/Scripts/python -m uvicorn app.main:app --port 8002 --host 127.0.0.1` |
| **frontend-crm** | 8080 | `cd frontend-crm && npm run dev` |

> **Ordem importa:** core → executors → crm → frontend

### Não é necessário

- `agent-local` — só usado para prospecção/scraping, não afeta o playground
- `website` — site de marketing, independente
- WhatsApp / UazAPI conectado — o playground bypassa completamente o WhatsApp

---

## Pré-requisito: variável de ambiente

O `backend-crm` precisa saber onde está o `backend-executors`. Verificar que `backend-crm/.env` contém:

```
EXECUTORS_BASE_URL=http://localhost:8002
```

Se não existir, o playground retorna erro 503 ao tentar enviar uma mensagem.

---

## Pré-requisito: conta com perfil de IA configurado

O utilizador autenticado precisa ter um **AI Profile** criado. Sem ele, o modal de configuração mostra erro ao tentar carregar o perfil.

Para verificar se existe:
```bash
curl http://localhost:8001/ai-profiles/me -H "Authorization: Bearer <TOKEN>"
```

Se retornar 404, criar o perfil em `/ai-profile` no frontend ou via API — ver [instrucoes-playground.md](./instrucoes-playground.md) secção 5.

---

## Fluxo de uso

### 1. Configurar a sessão

Ao abrir `/playground`, aparece um modal com:

- **Perfil de IA** — carregado automaticamente do utilizador autenticado. Mostra nome, `agent_mode` e `template_key`.
- **Contexto do cenário** (opcional) — descrição livre do que está a testar. Vai para o cabeçalho do markdown exportado. Exemplo: `"Testar comportamento passivo quando lead menciona preço antes de qualificar"`

Clicar **Iniciar Sessão**.

---

### 2. Simular a conversa (painel esquerdo)

- **Você escreve como se fosse o lead** — o campo de texto simula as mensagens do contacto.
  - `Enter` → envia a mensagem
  - `Shift + Enter` → nova linha sem enviar
- As respostas do bot aparecem em bolhas cinzentas à esquerda.
- Enquanto o bot "pensa", aparece o indicador "Bot digitando…".

#### Ver o trace de decisão

Cada resposta do bot tem um link **"Ver trace"** por baixo. Ao expandir, mostra:

```
{
  "agent_mode": "agenda",
  "mother_route": "agenda_flow",
  "effective_route": "agenda_flow",
  "guardrails_applied": [],
  "presentation_variant": "scheduler",
  ...
}
```

O badge ao lado indica a rota da mãe e a confiança (ex: `agenda_flow · 87%`). Se houverem guardrails ativados, aparece badge vermelho com a contagem.

---

### 3. Marcar mensagens para feedback (em tempo real)

Ao passar o cursor sobre uma resposta do bot, aparece o ícone **🔖** à esquerda da bolha.

- **Clicar** → a mensagem fica destacada a âmbar e aparece no painel direito
- **Clicar novamente** → remove do painel de feedback

> Marcar no momento exato em que notou o comportamento — não é necessário esperar o fim da conversa.

---

### 4. Anotar o feedback (painel direito)

Para cada mensagem marcada, o painel direito mostra:

| Elemento | O que fazer |
|---|---|
| **Preview** (itálico) | Trecho dos primeiros 80 caracteres da mensagem do bot |
| **Tags** | Clicar para ativar: `Tom`, `Qualificação`, `Guardrail`, `Prompt`, `Outro` |
| **Textarea de notas** | Escrever a observação livremente |
| **× (remover)** | Remove do painel e desmarca a bolha |

As notas são guardadas em memória durante a sessão — não persistem se fechar a aba.

---

### 5. Exportar o feedback

Botão **"Exportar .md"** no topo do painel direito gera e faz download de um ficheiro `.md` com:

- Cabeçalho com nome do perfil, contexto do cenário e lead ID
- Histórico completo da conversa com timestamps e traces
- Secção de feedbacks anotados com tags e notas

O ficheiro é nomeado automaticamente: `playground-YYYY-MM-DD_HH-MM-output.md`

É compatível com o formato dos ficheiros `*-output.md` em `docs/test-playground/`.

---

### 6. Nova sessão

Botão **"Nova sessão"** no topo (ícone de refresh) → limpa o histórico e o painel de feedback e reabre o modal de configuração.

> Exportar o markdown antes de iniciar uma nova sessão — o histórico não é recuperável depois de limpar.

---

## O que acontece nos bastidores

```
Frontend /playground
  → POST /api/playground/chat (backend-crm:8000)
    → build_context_bundle_for_playground()
    → POST /api/internal/playground/decide (backend-executors:8002)
      → decision engine (síncrono, sem fila)
      → retorna DecisionOutput completo
    → persiste mensagens em crm.db (is_playground=1)
    → retorna PlaygroundChatResponse com trace completo
```

- Leads sandbox têm `is_playground=1` → **não aparecem no Kanban**, não consomem quota, não recebem follow-ups
- Cada sessão cria um lead novo (a não ser que reutilize o `lead_id` entre sessões — o playground mantém o ID na barra superior)

---

## Problemas comuns

| Sintoma | Causa provável | Solução |
|---|---|---|
| Modal carrega mas mostra erro no perfil | AI Profile não criado para este utilizador | Criar em `/ai-profile` no frontend |
| Mensagem enviada, erro "Erro ao chamar o playground" | backend-crm ou backend-executors offline | Verificar os 3 serviços backend |
| Erro 503 na primeira mensagem | `EXECUTORS_BASE_URL` ausente no `.env` do crm | Adicionar a variável e reiniciar o crm |
| Bot responde mas trace vazio | `decision_trace` não propagado | Inspecionar resposta bruta no DevTools → Network |
| Sessão expira durante uso | JWT do frontend expirou | Fazer logout e login novamente no frontend |

---

## Referências

- [instrucoes-playground.md](./instrucoes-playground.md) — guia da API curl (versão anterior, sem UI)
- [test-playground/README.md](./test-playground/README.md) — convenções dos ficheiros input/output
- [test-playground/template-input.md](./test-playground/template-input.md) — template para criar cenários
- [test-playground/otimizacao.md](./test-playground/otimizacao.md) — histórico de fixes e validações

---

*Criado em 2026-04-09 — após implementação da interface web do playground.*
