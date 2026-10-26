# O Monitoramento de colaborador serve para "escutar" o WhatsApp da própria dona do negócio (terapeuta que atende sozinha)?

> Estrutura em `_template-investigacao.md`. Processo em `_guia-discovery.md`.

---

**Status:** Levantado
**Origem:** `levantamentos/2026-10-26-escuta-vendas-trafego-pago.md` — observações 1 e 5
**Meta ligada:** M1 — Conquistar os primeiros clientes pagantes (provável: o nicho inicial é massoterapia/terapeutas)
**Área do sistema:** backend-core (conexões WhatsApp) / backend-crm (collab_monitor) / frontend-crm (/monitoramento)

---

## Pergunta a responder (L)

Uma terapeuta que atende ela mesma pelo WhatsApp pode ligar o número dela ao
CRM só para registar as conversas e o estágio de cada cliente (sem o robô
responder), de forma segura para o número e aceitável em termos de privacidade?

## O que já se sabe (L)

**Confirmado no código:**
- A instância de monitor nunca envia: `backend-core/app/api/whatsapp_send.py:121` e `:218` respondem 403 `instance_not_allowed_to_send` para `role != "agent"`; a instância nasce com `role="monitor"` em `backend-crm/routes/collab_monitor.py:229`.
- O webhook captura as mensagens dos dois lados (antes do filtro `from_me`) e cria lead real com `bot_disabled=1`, `bot_disabled_reason='collab_monitor'`, `origin='whatsapp_inbound'`: `backend-crm/services/collab_monitor/monitor_inbound_handler.py:98-105`.
- Uma IA só de leitura classifica o estágio (`qualification` … `closing`, `client-list`, `prospect-refused`, `disqualified`), sem retroceder: `services/collab_monitor/classifier.py`, `classify_worker.py` (ver `docs/architecture/collab-monitor.md`).
- Áudio é transcrito (Whisper) e imagem descrita (GPT-4o-mini) via `media_worker.py`.

**Hipóteses a verificar:**
- O produto foi desenhado para colaborador de equipe (planos Scale/Enterprise); não sabemos se uma conta sem instância de agente e só com monitor funciona sem atritos (onboarding, plano, telas).
- Risco de bloqueio do número principal da terapeuta por usar UazAPI (não oficial).
- Privacidade: conversas de clientes de terapia na UE passam pela OpenAI — precisa de consentimento/aviso (GDPR); tema sensível do nicho.
- `client-list` pode servir como "venda" para fins de medição — a confirmar com conversas reais.
