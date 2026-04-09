# Guia de Uso — Playground IA (Interface Web)

Interface visual para simular conversas com o agente, registar feedback em tempo real e exportar para análise.
Acesso: menu lateral → **Playground IA** (ícone de frasco) ou diretamente em `/playground`.

---

## Ciclo de trabalho completo

```
1. Subir os serviços  →  2. Abrir /playground  →  3. Simular conversa
       ↓
4. Marcar mensagens com 🔖  →  5. Anotar feedback no painel direito
       ↓
6. Exportar .md  →  7. Colar na conversa com Claude Code
       ↓
8. Claude analisa traces + feedback  →  identifica causas  →  propõe plano
       ↓
9. Aprovação  →  implementação  →  novo ciclo de teste
```

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

- `agent-local` — só usado para prospecção/scraping
- `website` — site de marketing, independente
- WhatsApp / UazAPI conectado — o playground bypassa completamente o WhatsApp

---

## Pré-requisitos

**1. Variável de ambiente**

O `backend-crm` precisa saber onde está o `backend-executors`. Verificar que `backend-crm/.env` contém:

```
EXECUTORS_BASE_URL=http://localhost:8002
```

Se não existir, o playground retorna erro 503 ao tentar enviar uma mensagem.

**2. AI Profile configurado**

O utilizador autenticado precisa ter um AI Profile criado. Sem ele, o modal de configuração mostra erro.

Para verificar: `curl http://localhost:8001/ai-profiles/me -H "Authorization: Bearer <TOKEN>"`

Se retornar 404, criar o perfil em `/ai-profile` no frontend. Ver [instrucoes-playground.md](./instrucoes-playground.md) secção 5 se precisar criar via API.

---

## Fluxo de uso

### 1. Configurar a sessão

Ao abrir `/playground`, aparece um modal com:

- **Perfil de IA** — carregado automaticamente. Mostra nome, `agent_mode` e `template_key`.
- **Contexto do cenário** (opcional) — descreva o que está a testar. Ex: `"Testar comportamento passivo quando lead menciona preço antes de qualificar"`. Vai para o cabeçalho do markdown exportado.

Clicar **Iniciar Sessão**.

---

### 2. Simular a conversa (painel esquerdo)

Escreva como se fosse o lead:

- `Enter` → envia a mensagem
- `Shift + Enter` → nova linha sem enviar

As respostas do bot aparecem em bolhas cinzentas. Enquanto processa, aparece "Bot digitando…".

**Ver o trace de decisão:** cada resposta tem um link "Ver trace" por baixo. Ao expandir mostra `mother_route`, `effective_route`, `guardrails_applied`, `presentation_variant`, etc. O badge ao lado indica a rota e a confiança. Guardrails ativados aparecem em vermelho.

---

### 3. Marcar mensagens para feedback (em tempo real)

Ao passar o cursor sobre uma resposta do bot, aparece o ícone **🔖** à esquerda.

- **Clicar** → a mensagem fica destacada a âmbar e aparece no painel direito
- **Clicar novamente** → remove do painel

> Marcar no momento em que notar o comportamento — não é necessário esperar o fim da conversa.

---

### 4. Anotar o feedback (painel direito)

Para cada mensagem marcada:

| Elemento | O que fazer |
|---|---|
| **Tags** | Clicar para ativar: `Tom`, `Qualificação`, `Guardrail`, `Prompt`, `Outro` |
| **Textarea de notas** | Descrever o comportamento observado e o que era esperado |
| **× (remover)** | Remove do painel e desmarca a bolha |

---

### 5. Exportar e trazer para análise

Botão **"Exportar .md"** gera e faz download de um ficheiro `.md` com:

- Cabeçalho: perfil, contexto do cenário, lead ID
- Histórico completo da conversa com timestamps e traces por turno
- Todos os feedbacks anotados com tags e notas

**Para analisar com Claude Code:** colar o conteúdo do ficheiro diretamente nesta conversa. Claude irá:

1. Ler os `decision_trace` por turno — identifica onde o roteamento divergiu do esperado
2. Cruzar as anotações com os campos do trace (guardrails, mother_route, effective_route, confidence)
3. Localizar o ficheiro e função responsável pelo comportamento
4. Propor um plano de correção antes de implementar qualquer coisa

Junto com o `.md` exportado, pode também incluir o ficheiro `*-input.md` do cenário (se existir) para que Claude tenha os critérios de avaliação esperados.

---

### 6. Nova sessão

Botão **"Nova sessão"** limpa o histórico e o painel e reabre o modal de configuração.

> Exportar antes de iniciar uma nova sessão — o histórico não é recuperável depois de limpar.

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

Leads sandbox têm `is_playground=1` → não aparecem no Kanban, não consomem quota, não recebem follow-ups.

---

## Problemas comuns

| Sintoma | Causa provável | Solução |
|---|---|---|
| Modal mostra erro no perfil | AI Profile não criado | Criar em `/ai-profile` no frontend |
| Erro ao enviar mensagem | backend-crm ou backend-executors offline | Verificar os 3 serviços backend |
| Erro 503 na primeira mensagem | `EXECUTORS_BASE_URL` ausente no `.env` | Adicionar a variável e reiniciar o crm |
| Sessão expira durante uso | JWT expirou | Logout e login novamente no frontend |

---

## Referências

- [instrucoes-playground.md](./instrucoes-playground.md) — setup detalhado dos serviços e da conta de teste
- [test-playground/README.md](./test-playground/README.md) — convenções dos ficheiros e fluxo de análise
- [test-playground/otimizacao.md](./test-playground/otimizacao.md) — histórico de fixes e validações

---

*Atualizado em 2026-04-09.*
