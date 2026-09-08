# Paginação na tela de monitoramento de colaborador

**Status:** Aguardando Plan Mode

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`monitoramento-colaborador-tela-whatsapp-web.md` (tela de monitoramento
estilo WhatsApp Web — ver [`docs/architecture/collab-monitor.md`](../architecture/collab-monitor.md)).

A tela nova (`GET /api/collab-monitor/conversations` +
`GET /api/assistente-ia/messages/{lead_id}`) carrega hoje a lista completa de
conversas e o histórico completo de mensagens de uma vez, sem paginação nem
scroll infinito. Funciona bem com poucos leads/mensagens, mas não escala se
o volume de conversas monitoradas ou de mensagens por conversa crescer
muito.

---

## Contexto técnico conhecido (para o diagnóstico de Plan Mode)

- `backend-crm/routes/collab_monitor.py::list_collab_monitor_conversations`
  (`GET /conversations`) — hoje retorna todos os leads `category='monitoring'`
  do usuário numa query só, sem `LIMIT`/`OFFSET` nem cursor.
- `backend-crm/routes/assistente_ia.py::get_messages`
  (`GET /messages/{lead_id}`) — hoje retorna todas as mensagens do lead numa
  query só (`ORDER BY createdAt DESC`), também sem paginação. Esta rota é
  compartilhada com outros consumidores (preview de mensagens, `LeadCardDialog`)
  — qualquer mudança de contrato aqui precisa considerar esses outros usos.
- `frontend-crm/src/pages/CollabMonitorInbox.tsx` — lista de conversas e
  painel de mensagens usam `useQuery` simples (sem `useInfiniteQuery`).
- Decisão de produto em aberto: paginar por scroll infinito (carregar mais
  ao chegar no topo/fim) ou paginação tradicional? Isso muda a abordagem no
  frontend (React Query `useInfiniteQuery` vs. `useQuery` com página).

---

## Próximo passo

Plan Mode: diagnóstico completo (já existe / o que construir / riscos) antes
de qualquer código, seguindo
[`_guia-documentar-implementacao.md`](_guia-documentar-implementacao.md).
