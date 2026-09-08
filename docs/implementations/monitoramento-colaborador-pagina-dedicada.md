# Cadastro de colaboradores na própria página de Monitoramento

**Branch:** `feat/monitoramento-colaborador-pagina-dedicada`
**Status:** Em andamento

---

## Motivação

Usando o sistema, o utilizador percebeu que o cadastro/gerenciamento de
colaboradores monitorados (`MonitoramentoColaboradores.tsx`) estava
escondido numa aba "Monitoramento" dentro do AI Profile — enquanto quem
precisa gerenciar colaboradores já usa a página dedicada `/monitoramento`
(`CollabMonitorInbox.tsx`, onde lê as conversas capturadas). Fazia mais
sentido o cadastro estar ali.

Adicionalmente, o banner global "WhatsApp desconectado — reconecte para
continuar respondendo automaticamente." (`WhatsappDisconnectBanner.tsx`)
aparecia em `/monitoramento`. Esse alerta é sobre a conexão do **agente
principal** (`role="agent"`, via `GET /api/whatsapp/connection-alert`) —
sem relação com as instâncias de colaborador monitoradas, e confundia o
utilizador.

**Decisão validada com o utilizador:** mover de vez o cadastro (não
duplicar) — a aba "Monitoramento" saiu do AI Profile.

---

## Problemas Identificados (estado anterior)

1. `frontend-crm/src/pages/AiProfile.tsx` — aba "Monitoramento" escondida
   entre as abas de configuração de IA, sem relação direta com o resto do
   AI Profile.
2. `frontend-crm/src/components/agente/MonitoramentoColaboradores.tsx` —
   estilizado com o tema Orion (`--o-*`, específico do AI Profile),
   destoando do resto de `/monitoramento` (Tailwind/shadcn puro).
3. `frontend-crm/src/components/WhatsappDisconnectBanner.tsx` — renderizado
   globalmente pelo `AppShell`, sem checagem de rota; aparecia em
   `/monitoramento` mesmo sendo sobre outra instância.

---

## Abordagem

```
CollabMonitorInbox.tsx (header)
  → botão "Gerenciar colaboradores"
  → abre <ManageCollaboratorsDialog open={..} onOpenChange={..} onChanged={..} />
      → mesma lógica de MonitoramentoColaboradores.tsx (fetch/poll,
        criar, QR, reconectar, remover, toasts de erro), casca shadcn
      → onChanged invalida a query ["collab-monitor-conversations"]
```

`WhatsappDisconnectBanner.tsx` ganhou `useLocation()` e retorna `null` em
rotas que começam com `/monitoramento`.

---

## Plano de Implementação

### Fase 1 — Mover cadastro + suprimir banner

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/components/ManageCollaboratorsDialog.tsx` | Novo — Dialog shadcn com a lógica de `MonitoramentoColaboradores.tsx` |
| `frontend-crm/src/components/agente/MonitoramentoColaboradores.tsx` | Removido |
| `frontend-crm/src/pages/CollabMonitorInbox.tsx` | Botão "Gerenciar colaboradores" + dialog + invalidação de query |
| `frontend-crm/src/pages/AiProfile.tsx` | Remove aba/painel/import/tipo `monitoramento` |
| `frontend-crm/src/components/WhatsappDisconnectBanner.tsx` | Suprime em `/monitoramento` |
| `docs/architecture/collab-monitor.md` | Atualiza referências |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `e382e6b` | dialog novo, remoção da aba do AI Profile, supressão do banner, docs |

**Detalhes do commit `e382e6b`:**
- `frontend-crm/src/components/ManageCollaboratorsDialog.tsx` — novo, reescreve `MonitoramentoColaboradores.tsx` com `Dialog`/`Input`/`Button`/`Badge` shadcn, props `open`/`onOpenChange`/`onChanged`
- `frontend-crm/src/components/agente/MonitoramentoColaboradores.tsx` — removido
- `frontend-crm/src/pages/CollabMonitorInbox.tsx` — botão "Gerenciar colaboradores" no header; `useQueryClient().invalidateQueries(["collab-monitor-conversations"])` via prop `onChanged`
- `frontend-crm/src/pages/AiProfile.tsx` — remove `'monitoramento'` de `PanelId`, do array `navItems`, do bloco de painel e o import
- `frontend-crm/src/components/WhatsappDisconnectBanner.tsx` — `useLocation()`, `return null` se `pathname.startsWith('/monitoramento')`
- `docs/architecture/collab-monitor.md` — atualiza seções "Kanban — coluna Monitorado" e "Tela de leitura estilo WhatsApp Web"

---

## Checks de Validação

### Cenário 1 — Dialog funciona na página de Monitoramento (validado por Claude)
- [x] `npm run build` — typecheck limpo
- [x] Testado localmente (mesma técnica do fix `monitoramento-colaborador-toast-erro`:
      `.env.local` gitignored apontando pro backend de produção, `vite`
      numa porta isolada — chamadas falham por CORS nesse ambiente, mas
      confirmam que a UI renderiza e os handlers disparam)
  - Navegado a `/monitoramento`: botão "Gerenciar colaboradores" aparece no
    header, banner de WhatsApp desconectado **não** aparece (antes falhava
    a query de alerta por CORS de qualquer forma, mas a checagem de rota
    foi confirmada por leitura de código)
  - Clique no botão abre o dialog com o formulário, visual shadcn (não mais
    tema Orion)
  - Cadastro de colaborador de teste: toast "Erro ao cadastrar colaborador"
    apareceu (equivalente ao já validado no fix anterior), botão voltou ao
    normal
- **Validado em:** 08/09/2026

### Cenário 2 — Fluxo feliz completo (pendente, requer ambiente real)
- [ ] Em produção, abrir `/monitoramento` → "Gerenciar colaboradores" →
      cadastrar um colaborador com nome válido
- [ ] Confirmar: QR aparece, conecta, aparece na lista do dialog
- [ ] Fechar o dialog e confirmar que a lista de conversas à esquerda não
      quebra (mesmo sem conversas ainda para esse colaborador)
- [ ] Confirmar visualmente: aba "Monitoramento" não existe mais no AI
      Profile
- [ ] Em uma página **fora** de `/monitoramento` (ex.: Dashboard), com o
      agente principal desconectado de propósito, confirmar que o banner
      "WhatsApp desconectado" continua aparecendo normalmente ali (a
      supressão é só para `/monitoramento`)
- **Pendente:** requer sessão autenticada real em produção — Claude não
  alcança por CORS/sessão a partir do ambiente de desenvolvimento local

---

## Ajustes Possíveis Pós-Implementação

- Nenhum previsto — reorganização de UI, sem novo escopo funcional.
