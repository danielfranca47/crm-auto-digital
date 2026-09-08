# Re-resolução de URL de mídia expirada no monitoramento de colaborador

**Status:** Aguardando Plan Mode

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`monitoramento-colaborador-midia.md` (tratamento de áudio/imagem no
monitoramento de colaborador — ver
[`docs/architecture/collab-monitor.md`](../architecture/collab-monitor.md)).

`messages.media_url` hoje guarda a URL resolvida via UazAPI
(`/message/download`) para áudio, ou a URL crua do webhook (`fileURL`) para
imagem — mais confiável que a URL original do webhook, mas **não é
permanente**: pode expirar com o tempo (prazo exato desconhecido, depende da
política da UazAPI/WhatsApp). Se uma futura tela de mídia precisar tocar
áudio ou exibir imagem de mensagens antigas, a URL persistida pode já não
funcionar.

---

## Contexto técnico conhecido (para o diagnóstico de Plan Mode)

- Ponto de escrita: `services/collab_monitor/media_worker.py::_process_audio()`
  (usa `download_audio_url_from_uazapi()`, `services/audio_transcription.py`)
  e `handle_monitor_inbound()` (usa `fileURL` cru do webhook para imagem).
- Este item é diretamente relevante para
  `monitoramento-colaborador-tela-whatsapp-web.md` (tela estilo WhatsApp Web,
  "navegação de mídia") — provavelmente deveria ser resolvido junto dessa
  implementação, não isoladamente, já que é o consumidor da URL persistida.
- Precisa de decisão de produto: re-resolver a URL sob demanda (ex.: nova
  chamada a `/message/download` no momento em que a tela pede a mídia) exige
  ainda ter o `instance_token` acessível e a instância ainda conectada — o
  que acontece se a instância foi desconectada/removida nesse meio tempo?
  Precisa de um fallback de "mídia indisponível" na UI.

---

## Próximo passo

Plan Mode: diagnóstico completo (já existe / o que construir / riscos) antes
de qualquer código, seguindo
[`_guia-documentar-implementacao.md`](_guia-documentar-implementacao.md).
