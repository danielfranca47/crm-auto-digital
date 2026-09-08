# Captura e exibição de mídia no monitoramento de colaborador

**Status:** Aguardando Plan Mode

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`monitoramento-colaborador-tela-whatsapp-web.md` (tela de monitoramento
estilo WhatsApp Web — ver [`docs/architecture/collab-monitor.md`](../architecture/collab-monitor.md)).

Hoje toda mensagem de mídia (imagem, áudio, vídeo, sticker, documento)
recebida por uma instância de monitoramento é descartada silenciosamente —
nem chega a ser gravada em `messages`. A tela de monitoramento só exibe
texto. O utilizador quer ver a mídia trocada nas conversas monitoradas.

---

## Contexto técnico conhecido (para o diagnóstico de Plan Mode)

- `services/collab_monitor/monitor_inbound_handler.py::handle_monitor_inbound`
  descarta qualquer mensagem sem `message_text`
  (`{"status": "ignored", "reason": "missing_text"}`).
- `routes/webhooks.py` não extrai `media_url` no bloco que monta o payload do
  monitor (`monitor_payload`) — diferente do bloco vizinho do Agente Espião
  (`spy_payload`), que já faz essa extração.
- A tabela `messages` não tem coluna de mídia (`media_url`, `message_type`
  já existe mas não é populado). A tabela `spy_agent_messages` (Agente
  Espião) já tem esse schema: `body, message_type, media_url, transcription,
  external_message_id, received_at, processed_at`.
- O único pipeline de download/processamento de mídia que já existe no
  sistema é o do Agente Espião: `services/spy_agent/spy_inbound_handler.py`
  grava `media_url`/`message_type` e, se for áudio/imagem, cria um job
  assíncrono `spy.media.process` processado por
  `services/spy_agent/spy_media_worker.py` (Whisper para áudio, visão para
  imagem). É o padrão mais próximo a replicar.
- Decisões de produto em aberto que o Plan Mode precisa resolver: a mídia
  baixada fica armazenada onde (custo/retenção)? A "imagem" exibida na
  bolha é a mídia bruta (URL assinada da UazAPI) ou uma descrição textual
  gerada por IA? Isso muda a UX da bolha de chat na tela de monitoramento.

---

## Próximo passo

Plan Mode: diagnóstico completo (já existe / o que construir / riscos) antes
de qualquer código, seguindo
[`_guia-documentar-implementacao.md`](_guia-documentar-implementacao.md).
