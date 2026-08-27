# Aviso de sessão dupla (WhatsApp Web/Desktop) na página de Conexão

**Branch:** `fix/aviso-sessao-dupla-whatsapp`
**Status:** Todos os cenários validados (27/08/2026) — pronto para graduação

---

## Motivação

Investigação do problema "instância WhatsApp para de responder depois de ~1h,
como se caísse para o plano free" (relatado pelo utilizador para todas as
contas, não só a sua) levou à correção `alerta-desconexao-whatsapp.md`
(graduada) — que confirmou, com payload real capturado num teste ao vivo, que
a UazAPI reporta o motivo exato da queda:

```
"lastDisconnectReason": "401: logged out from another device"
```

Essa frase corresponde a um padrão bem documentado (confirmado por pesquisa
externa) em APIs não-oficiais de WhatsApp baseadas em Baileys (o motor por
trás da UazAPI): **conflito de sessão** — quando o mesmo número tem mais do
que um "aparelho companheiro" vinculado simultaneamente (ex.: WhatsApp
Web/Desktop no browser aberto ao mesmo tempo que a ligação feita pela API), o
WhatsApp pode expulsar um dos aparelhos vinculados.

O utilizador confirmou usar o mesmo número tanto na ligação do CRM como no
WhatsApp Web/Desktop em paralelo — hipótese ainda a validar como causa
principal (teste em curso, fora do escopo deste arquivo), mas já justifica
adicionar um aviso preventivo imediato para reduzir o risco em todas as
contas enquanto a causa é confirmada.

---

## Problemas Identificados (estado anterior)

1. **Nenhum aviso sobre uso simultâneo do WhatsApp Web/Desktop:**
   `frontend-crm/src/components/agente/ConexaoNumero.tsx` já tem um alerta
   sobre ritmo de disparo (`o-alert o-alert-warn`, linha ~334), mas nada
   avisa o utilizador para não usar o WhatsApp Web/Desktop no mesmo número
   ligado à API — hoje o utilizador não tem como saber que isso é um risco.

---

## Abordagem

Adicionar um segundo bloco de alerta (mesmo padrão visual do alerta de ritmo
já existente) na página **AiProfile → Conexão**, explicando o risco de
sessão dupla e recomendando não usar o WhatsApp Web/Desktop no número
conectado ao CRM.

---

## Plano de Implementação

### Fase 1 — Aviso visual na página de Conexão

**Objetivo:** reduzir o risco de queda por conflito de sessão em todas as
contas, com um aviso simples e imediato.

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/components/agente/ConexaoNumero.tsx` | Novo bloco `o-alert o-alert-warn` avisando para não usar WhatsApp Web/Desktop no número conectado |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `0faa89f` | Aviso de sessão dupla na página de Conexão |

### Relatório da Fase 1 — o que mudou na prática

**Antes:** a página de Conexão (AiProfile → Conexão) só avisava sobre ritmo de
disparo de mensagens — nada dizia ao utilizador que usar o WhatsApp Web ou
Desktop no mesmo número ligado ao CRM podia derrubar a sessão do agente.

**Agora:** aparece um segundo aviso, logo abaixo do de ritmo, explicando que
a ligação do agente já conta como um "aparelho vinculado" e que usar o
WhatsApp Web/Desktop no mesmo número em paralelo pode causar essa queda —
recomendando usar só o telemóvel para acompanhar as conversas.

**Para validar:** Cenário P1, abaixo.

---

## Checks de Validação

### Cenário P1 — Aviso aparece na página de Conexão
- [x] Abrir AiProfile → Conexão (frontend-crm)
- [x] Confirmar: bloco de aviso visível, abaixo do alerta de ritmo já existente
- [x] Confirmar: texto legível em light e dark mode
- **Validado em:** 27/08/2026 — testado ao vivo via browser (MCP chrome-devtools),
  stack local completa (backend-core:8001, backend-crm:8000, frontend-crm:8080)
  rodando na própria worktree, com utilizador de teste dedicado
  (`teste-visual-conexao@example.com`, criado só para este teste). Aviso
  confirmado visível e legível em dark mode e light mode, imediatamente
  abaixo do alerta de ritmo já existente, com o mesmo padrão visual.

---

## Ajustes Possíveis Pós-Implementação

- Se o teste confirmar a causa (sessão dupla), avaliar detetar
  programaticamente múltiplos aparelhos vinculados via UazAPI (se o payload
  expuser essa informação) e mostrar um aviso mais específico/dinâmico em vez
  de texto estático.
