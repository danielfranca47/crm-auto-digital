# Fix: link de recuperação de senha cai em "Sessão expirada"

**Branch:** `fix/reset-senha-sessao-expirada`
**Status:** Em andamento

---

## Motivação

Usuário reportou (produção) que o link de "recuperar senha" do email leva para a tela de
login com o toast "Sessão expirada / Faça login novamente", em vez do formulário de nova
senha. Isso bloqueia totalmente o fluxo de reset de senha sempre que o navegador do
usuário tem um token JWT antigo/expirado salvo no `localStorage` de uma sessão anterior
no CRM — cenário comum para qualquer usuário que já usou o CRM nesse navegador antes.

Causa raiz identificada: `frontend-crm/src/contexts/LeadsContext.tsx` — o `useEffect`
global (linhas 292-302) roda em **toda** a árvore de rotas (`LeadsProvider` envolve
`/login`, `/forgot-password`, `/reset-password` também, não só as rotas protegidas). O
guard `if (!readAuthToken()) return;` só verifica se existe *algum* token salvo — não se
ele é válido. Quando existe um token expirado:

- `reloadAllLeads()` já trata 401/403 silenciosamente (fix anterior).
- `loadBotPauseStatus()` **não** tinha o mesmo tratamento — no `catch`, chamava
  `handleError()` incondicionalmente, que para 401/403 sempre dispara
  `toast("Sessão expirada")` + `navigate("/login")` (`useApiErrorHandler.ts:44-54`),
  chutando o usuário para fora de `/reset-password` antes de ele conseguir ver o
  formulário.

---

## Problemas Identificados (estado anterior)

1. **`frontend-crm/src/contexts/LeadsContext.tsx:264-272`** — `loadBotPauseStatus()`
   chama `handleError(error, {...})` sem checar `error.status` antes, diferente do
   padrão já usado em `reloadAllLeads()` logo acima.
2. **Mesmo `useEffect` (linha 298)** chama `loadBotPauseStatus()` no polling de 30s —
   então o redirect indesejado também pode disparar depois do mount inicial, em
   qualquer rota pública.

---

## Abordagem

Aplicar em `loadBotPauseStatus` o mesmo guard que `reloadAllLeads` já usa: silenciar
401/403 (esses casos já são tratados pelo componente `Protected` nas rotas privadas) em
vez de deixar cair no `handleError` genérico que redireciona.

---

## Plano de Implementação

### Fase 1 — Silenciar 401/403 em `loadBotPauseStatus`

**Objetivo:** parar de redirecionar para `/login` a partir de rotas públicas quando o
usuário tem um token expirado salvo.

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/contexts/LeadsContext.tsx` | `loadBotPauseStatus`: guard de 401/403 antes do `handleError`, igual ao já usado em `reloadAllLeads` |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `d3a47a9` | fix: silenciar 401/403 em loadBotPauseStatus (LeadsContext) |

---

## Checks de Validação

### Cenário P1 — Reset de senha com token expirado salvo no navegador
- [ ] Logar no CRM local para gravar um token válido no `localStorage`
- [ ] Invalidar esse token (esperar expirar, ou editar o valor salvo)
- [ ] Navegar direto para `/reset-password?token=<qualquer-valor>` sem passar por `/login`
- [ ] Confirmar: formulário "Nova senha" aparece normalmente, sem redirecionar para
  `/login` nem exibir o toast "Sessão expirada"

### Cenário P2 — `/forgot-password` e `/login` não afetados
- [ ] Mesmo cenário de token expirado, navegar para `/forgot-password` e `/login`
- [ ] Confirmar: nenhuma das duas dispara o toast/redirect indevido

### Cenário C1 — Rotas protegidas continuam pedindo login
- [ ] Com o mesmo token expirado, navegar para `/` (Kanban)
- [ ] Confirmar: `Protected` ainda redireciona para `/login` normalmente (guard não foi
  removido, só parou de ser duplicado por `loadBotPauseStatus`)
