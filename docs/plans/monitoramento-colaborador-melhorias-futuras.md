# Monitoramento de colaborador — melhorias futuras

> Contexto: item deixado de fora da graduação de
> `monitoramento-colaborador-paginacao.md` (paginação tradicional na tela de
> monitoramento de colaborador).

## M1 — Contagem total nos pagers ("Página N de M")

**Prioridade: BAIXA**

Os pagers de conversas e de mensagens em `CollabMonitorInbox.tsx` (ver
[`docs/architecture/collab-monitor.md`](../architecture/collab-monitor.md),
seção "Tela de leitura estilo WhatsApp Web") mostram só "Página N", com
Anterior/Próxima habilitados via um sinalizador `has_more` — não há total de
páginas. Mostrar "Página N de M" exigiria uma query `COUNT(*)` adicional nos
dois endpoints (`GET /collab-monitor/conversations` e
`GET /assistente-ia/messages/{lead_id}`), hoje evitada de propósito para não
pagar esse custo extra em cada chamada.
