# Toast de erro em MonitoramentoColaboradores

**Branch:** `fix/monitoramento-colaborador-toast-erro`
**Status:** Em andamento

---

## Motivação

O utilizador reportou que o botão "Cadastrar e Conectar" (aba Monitoramento
do AI Profile) não fazia nada ao clicar.

Investigação nos logs de produção (Railway) mostrou que a request estava
sendo feita e falhando:

```
backend-crm:   POST /api/collab-monitor/instances HTTP/1.1 429 Too Many Requests
backend-core:  event=uazapi_admin_retry attempt=1/3 status=429 delay=0.50
               event=uazapi_admin_retry attempt=2/3 status=429 delay=1.00
               POST /whatsapp-instances/init HTTP/1.1 429 Too Many Requests
```

Causa raiz do sintoma "nada acontece": a UazAPI está recusando a criação de
instância nova por rate limit (provável efeito colateral dos testes
recentes das duas implementações graduadas — muitas instâncias
criadas/removidas em pouco tempo). Isso tende a liberar sozinho, sem ação
necessária.

O problema de código: `MonitoramentoColaboradores.tsx` engolia todo erro de
rede em blocos `catch {}` vazios (create, reconnect, delete, load inicial)
— nenhum toast, nenhuma mensagem. Por isso, tanto este 429 quanto qualquer
erro futuro (token expirado, instância duplicada, etc.) sempre pareceriam
"o botão não faz nada".

---

## Problemas Identificados (estado anterior)

1. `frontend-crm/src/components/agente/MonitoramentoColaboradores.tsx:85-89`
   (`handleCreate`) — `catch {}` vazio, nenhum feedback ao utilizador em
   caso de falha (ex.: 429 da UazAPI).
2. Mesmo arquivo, `handleReconnect` e `handleDelete` — mesmo padrão de
   `catch {}` silencioso.
3. Mesmo arquivo, `loadInstances` (chamado na montagem do componente) —
   também engolia o erro sem distinguir a carga inicial do polling do QR.

---

## Abordagem

Reaproveitar o padrão de toast já usado em `AiProfile.tsx` (`handleSave`,
`useToast` de `@/hooks/use-toast`). `loadInstances()` passou a propagar o
erro (antes engolia internamente); quem decide se mostra toast ou fica
silencioso é o chamador — a carga inicial (montagem) mostra toast, o
polling do QR (`startPolling`, que já chamava `api.crm.collabMonitorList()`
diretamente, sem passar por `loadInstances()`) continua silencioso para não
gerar spam de toast a cada 3s.

Adicionado um helper `describeError()` que detecta `ApiError` com
`status === 429` (import de `@/lib/api-client`) e retorna uma mensagem
específica de rate limit; qualquer outro erro cai na mensagem genérica.

---

## Plano de Implementação

### Fase 1 — Toast de erro nos 4 pontos de falha silenciosa

**Objetivo:** qualquer falha de rede/API vira uma mensagem visível.

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/components/agente/MonitoramentoColaboradores.tsx` | `useToast` + helper `describeError`; toast destrutivo em `handleCreate`, `handleReconnect`, `handleDelete` e na carga inicial (`useEffect` de montagem); `loadInstances()` agora propaga erro em vez de engolir |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `9624805` | toast destrutivo em create/reconnect/delete/carga inicial; mensagem específica para 429 |

**Detalhes do commit `9624805`:**
- `frontend-crm/src/components/agente/MonitoramentoColaboradores.tsx` — import de `useToast` e `ApiError`; helper `describeError()`; `loadInstances()` sem try/catch interno (propaga); `handleCreate`/`handleReconnect`/`handleDelete` com toast destrutivo no `catch`; `useEffect` de montagem com `.catch()` próprio para toast de carga inicial

---

## Checks de Validação

### Cenário 1 — Fluxo feliz inalterado
- [ ] Com o rate limit da UazAPI já liberado, clicar "Cadastrar e Conectar"
      com um nome válido
- [ ] Confirmar: QR aparece normalmente, sem toast (comportamento igual ao
      anterior)

### Cenário 2 — Erro agora aparece
- [ ] Provocar uma falha (ex.: tentar cadastrar duas vezes rapidamente para
      reproduzir 429, ou qualquer outro erro de rede)
- [ ] Confirmar: toast destrutivo aparece com mensagem apropriada (mensagem
      de rate limit se for 429, genérica caso contrário) — em vez de nada
      acontecer

---

## Ajustes Possíveis Pós-Implementação

- Nenhum previsto — mudança pontual de UX/feedback, sem novo escopo.
