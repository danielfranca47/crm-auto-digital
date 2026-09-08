# Tratamento de mídia (áudio/imagem) no monitoramento de colaborador

**Status:** Aguardando Plan Mode

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`monitoramento-colaborador-classificacao-ia.md` (classificação de estágio do
lead monitorado via IA — ver
[`docs/architecture/collab-monitor.md`](../architecture/collab-monitor.md)).

Hoje `services/collab_monitor/monitor_inbound_handler.py::handle_monitor_inbound()`
ignora mensagens sem texto (`message_text` vazio) — imagem, áudio, vídeo — desde
a base original do monitoramento (`monitoramento-colaborador-whatsapp.md`, já
graduado). Isso significa que:
- O histórico do lead monitorado fica incompleto (falta o que foi enviado por
  mídia).
- A classificação de estágio (IA mãe) não enxerga nada do que foi comunicado
  por áudio/imagem — pode perder sinais relevantes de avanço do funil.

---

## Contexto técnico conhecido (para o diagnóstico de Plan Mode)

- `handle_monitor_inbound()` (linhas ~137-140): retorna
  `{"status": "ignored", "reason": "missing_text"}` para qualquer mensagem sem
  `message_text`. Não há tratamento dedicado de mídia neste módulo.
- Já existe um pipeline equivalente para o Agente Espião:
  `services/spy_agent/media_processor.py::process_spy_media_job()` — áudio via
  Whisper, imagem via GPT-4o-mini com visão — processado assincronamente por
  um job (`spy.media.process`, worker em `spy_media_worker.py`). Provável
  candidato a reaproveitar o mesmo padrão (transcrição/descrição) para o
  monitoramento de colaborador, em vez de reinventar a chamada aos modelos.
- Precisa de decisão de produto: a transcrição/descrição de mídia entra como
  texto normal em `messages.body` (mesmo padrão do Agente Espião, que usa
  `[ÁUDIO: ...]`/`[IMAGEM: ...]`) para aparecer no histórico do lead e ser
  consumida pelo classificador de estágio (`classifier.py`)?
- Este item também foi citado como dependência (não bloqueante) da
  implementação `monitoramento-colaborador-tela-whatsapp-web.md` (tela estilo
  WhatsApp Web) — se aquela tela precisar exibir mídia, este item pode
  precisar ser resolvido antes ou em conjunto.

---

## Próximo passo

Plan Mode: diagnóstico completo (já existe / o que construir / riscos) antes
de qualquer código, seguindo
[`_guia-documentar-implementacao.md`](_guia-documentar-implementacao.md).
