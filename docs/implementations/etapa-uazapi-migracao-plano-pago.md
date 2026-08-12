# Migração UazAPI: plano free → plano pago (até 3 dispositivos)

**Branch:** `feat/uazapi-adesao-plano-pago`
**Status:** Todos os cenários validados

---

## Motivação

O sistema está prestes a conectar os primeiros WhatsApp reais: o do próprio utilizador
(para colocar o agente em prática) e, nos próximos dias, mais 2 clientes. Hoje toda a
integração aponta para `free.uazapi.com`, documentado em `docs/diagnostico-uazapi.md`
como best-effort/sem SLA — inadequado para uso com clientes reais.

O utilizador decidiu assinar o plano pago "até 3 dispositivos" da UazAPI, que cobre
exatamente o uso previsto (ele + 2 clientes). Como ainda não há nenhuma instância real
em produção conectada, este é o momento mais barato para migrar — não há reconexões de
clientes já ativos a gerir.

---

## Problemas Identificados (estado anterior)

1. **Servidor free em uso:** `backend-core/.env:9` — `UAZAPI_BASE_URL=https://free.uazapi.com`.
   Sem SLA, best-effort, inadequado para clientes pagantes.

2. **Segunda cópia da URL fora do escopo do diagnóstico original:**
   `backend-crm/.env:22` também define `UAZAPI_BASE_URL=https://free.uazapi.com`,
   consumida por `backend-crm/services/audio_transcription.py:18` para baixar áudio de
   mensagens de voz (PTT) antes da transcrição via Whisper
   (`download_audio_url_from_uazapi`, linha ~36). O diagnóstico de abril
   (`docs/diagnostico-uazapi.md`) só cobriu `backend-core` — se só essa variável for
   trocada, a transcrição de áudio continuaria batendo no servidor free (que não terá
   mais a instância do utilizador) e falharia silenciosamente para mensagens de voz.

3. **Sem melhorias de robustez pré-produção:** já identificadas no diagnóstico de abril
   e ainda não implementadas — retry/backoff em 429
   (`backend-core/app/services/uazapi_admin.py:_request`, linha ~168) e validação E.164
   do número de destino (`backend-core/app/api/whatsapp_send.py`, linha ~123). Tratadas
   como Fase 2 opcional deste arquivo.

---

## Abordagem

```
Utilizador assina plano pago em uazapi.dev
  → obtém URL base do novo servidor + admin token no painel deles
  → envia as duas credenciais (não commitadas, .env é gitignored)
      → Claude atualiza backend-core/.env (URL + admin token)
      → Claude atualiza backend-crm/.env (URL, mesma variável)
      → reinicia os dois serviços localmente
      → testa fluxo real: connect → QR → scan (utilizador) → status connected
      → testa envio de texto e de áudio (valida audio_transcription.py contra o novo servidor)
      → atualiza docs/diagnostico-uazapi.md (status → migrado)
```

---

## Plano de Implementação

### Fase 1 — Troca de credenciais e validação end-to-end

**Objetivo:** sair do servidor free e confirmar que a instância do utilizador conecta e
envia/recebe mensagens (texto + áudio) no servidor pago.

**Credenciais do servidor pago:** URL base `https://digitalpro.uazapi.com` e admin
token, obtidos pelo utilizador no painel da UazAPI e recebidos em 2026-08-12.

| Arquivo | O que mudou |
|---|---|
| `backend-core/.env` | `UAZAPI_BASE_URL` e `UAZAPI_ADMIN_TOKEN` → valores do servidor pago |
| `backend-crm/.env` | `UAZAPI_BASE_URL` → mesmo valor de URL (sem token próprio) |
| `docs/diagnostico-uazapi.md` | Conclusão e checklist atualizados para refletir a migração concluída |

Nenhuma alteração de código — apenas configuração (`.env`, gitignored, não entra em
commit). O commit desta fase cobre só a atualização da doc.

### Descoberta durante a validação: webhook precisa de URL pública

O webhook da UazAPI é registrado sempre com `CRM_PUBLIC_BASE_URL` (não `localhost`),
mesmo com tudo rodando localmente — a UazAPI não consegue entregar eventos a um
endereço não roteável. Isso não é um bug da migração, é como o sistema sempre
funcionou, mas exigiu ajuste na forma de validar:

1. Túnel ngrok exposto para `backend-crm` local (porta 8000)
2. `CRM_PUBLIC_BASE_URL` apontado temporariamente para o túnel
3. Webhook reconfigurado direto na UazAPI (`POST {UAZAPI_BASE_URL}/webhook` com o
   token da instância) para a URL do túnel
4. Após validar os 3 cenários, tudo revertido: `CRM_PUBLIC_BASE_URL` de volta para
   `https://api.danielfranca.pt`, webhook reapontado para produção, túnel encerrado

Também foi necessário subir `backend-executors` (`python -m app.workers.whatsapp_worker`),
que não estava rodando — é esse worker que consome os jobs `whatsapp.inbound.n8n` e
efetivamente decide e envia a resposta da IA. Sem ele, mensagens inbound criam o lead
mas nunca recebem resposta.

### Commits Fase 1

_Pendente — commit da atualização de docs será feito ao final desta fase._

---

## Checks de Validação

### Cenário C1 — Conectar WhatsApp do utilizador no servidor pago
- [x] Backend-core e backend-crm reiniciados com as novas credenciais (2026-08-12)
- [x] Disparar `/api/whatsapp/connect` via UI do frontend-crm (2026-08-12)
- [x] QR code aparece (2026-08-12)
- [x] Utilizador escaneia com o telemóvel (2026-08-12)
- [x] Status muda para `connected` (2026-08-12) — confirmado via `/instance/all` na UazAPI

### Cenário C2 — Envio de mensagem de texto
- [x] Enviar mensagem de teste via CRM (2026-08-12) — validado via fluxo inbound completo:
  mensagem enviada de um chip terceiro para o número conectado, processada pela IA e
  respondida automaticamente (3 balões) via `POST /whatsapp/send` no servidor pago
- [x] Confirmar recebimento no WhatsApp do destinatário (2026-08-12) — confirmado pelo utilizador

### Cenário C3 — Recebimento e transcrição de áudio
- [x] Enviar um áudio (PTT) para o número conectado (2026-08-12)
- [x] Confirmar que `audio_transcription.py` baixa o áudio do servidor pago, não do free (2026-08-12)
- [x] Confirmar que a transcrição chega corretamente no pipeline (2026-08-12) — histórico do
  job mostrou `inbound: [Áudio]: Opa, sim, gostaria de saber seu nome.`, e a IA respondeu
  coerentemente à pergunta transcrita

---

## Ajustes Possíveis Pós-Implementação

- **Fase 2 (opcional, recomendada antes de conectar os 2 clientes):** backoff
  exponencial em 429/503 (`uazapi_admin.py:_request`) e validação E.164 do número de
  destino (`whatsapp_send.py`) — reduz risco operacional agora que há clientes reais
  envolvidos. A decidir com o utilizador após a Fase 1 validada.
- Rotação do admin token e proteção via secrets manager seguem como recomendação futura
  (já listadas em `docs/diagnostico-uazapi.md`), fora do escopo imediato.
