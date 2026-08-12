# Migração UazAPI: plano free → plano pago (até 3 dispositivos)

**Branch:** `feat/uazapi-adesao-plano-pago`
**Status:** Em andamento — bloqueado aguardando credenciais do utilizador

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

**Bloqueado em:** credenciais do servidor pago (URL base + admin token), que só o
utilizador pode obter assinando o plano no painel da UazAPI.

| Arquivo | O que muda |
|---|---|
| `backend-core/.env` | `UAZAPI_BASE_URL` e `UAZAPI_ADMIN_TOKEN` → valores do servidor pago |
| `backend-crm/.env` | `UAZAPI_BASE_URL` → mesmo valor de URL (sem token próprio) |
| `docs/diagnostico-uazapi.md` | Conclusão atualizada para refletir a migração concluída |

Nenhuma alteração de código — apenas configuração (`.env`, gitignored, não entra em
commit). O commit desta fase cobre só a atualização da doc.

### Commits Fase 1

_Pendente — aguardando credenciais para executar a troca e validar o fluxo antes de
commitar a atualização da doc._

---

## Checks de Validação

### Cenário C1 — Conectar WhatsApp do utilizador no servidor pago
- [ ] Backend-core e backend-crm reiniciados com as novas credenciais
- [ ] Disparar `/api/whatsapp/connect` via UI do frontend-crm
- [ ] QR code aparece
- [ ] Utilizador escaneia com o telemóvel
- [ ] Status muda para `connected`

### Cenário C2 — Envio de mensagem de texto
- [ ] Enviar mensagem de teste via CRM
- [ ] Confirmar recebimento no WhatsApp do destinatário

### Cenário C3 — Recebimento e transcrição de áudio
- [ ] Enviar um áudio (PTT) para o número conectado
- [ ] Confirmar que `audio_transcription.py` baixa o áudio do servidor pago (não do free)
- [ ] Confirmar que a transcrição chega corretamente no pipeline

---

## Ajustes Possíveis Pós-Implementação

- **Fase 2 (opcional, recomendada antes de conectar os 2 clientes):** backoff
  exponencial em 429/503 (`uazapi_admin.py:_request`) e validação E.164 do número de
  destino (`whatsapp_send.py`) — reduz risco operacional agora que há clientes reais
  envolvidos. A decidir com o utilizador após a Fase 1 validada.
- Rotação do admin token e proteção via secrets manager seguem como recomendação futura
  (já listadas em `docs/diagnostico-uazapi.md`), fora do escopo imediato.
