# Fix: fallback de mídia ignora a pausa do bot

**Branch:** `worktree-fix+media-fallback-respeita-pausa`
**Status:** Em andamento

---

## Motivação

O utilizador reportou que, mesmo pausando o bot para todos os leads (botão pause/play do
Kanban — feature `bot_global_pause`), quando um lead envia uma **imagem ou vídeo** para o
WhatsApp o bot continua enviando uma resposta automática padrão.

---

## Problemas Identificados (estado anterior)

1. **Fallback de mídia não consulta o estado de pausa:** em
   `backend-crm/services/whatsapp_inbound/inbound_handler.py`, a função `handle_inbound`
   tem duas checagens de pausa distintas para dois caminhos diferentes:
   - **Mensagens de texto normais** (linhas 480–510): checam `bot_global_pause_state.is_paused`
     e `leads.bot_disabled` antes de criar o job que dispara a resposta da IA. Funciona correto.
   - **Mídia não processável** (imagem, vídeo, sticker, documento, reação, ou áudio sem
     transcrição habilitada — linhas 291–347): o código chama `_apply_media_fallback(...)`
     e retorna imediatamente, muito antes de chegar às checagens de pausa acima.
2. **`_apply_media_fallback` envia sem checar pausa:** a função (linhas 187–235) lê
   `offer_pack.media_fallback` do AI Profile e, se o comportamento configurado for
   `"continuar"` ou `"pausar"`, envia a mensagem de fallback via `send_whatsapp_direct` sem
   nunca consultar `bot_global_pause_state` ou `leads.bot_disabled`.

Resultado: pausar o bot (globalmente ou por lead) não impedia o envio da resposta
automática de mídia — só afetava o fluxo de texto.

---

## Abordagem

```
Lead envia mídia não processável → _apply_media_fallback()
  ├─ behavior == "ignorar" → não envia nada (já existia)
  ├─ bot pausado (global ou por lead) → não envia nada (NOVO)
  └─ behavior == "continuar" ou "pausar", bot ativo → envia mensagem de fallback (já existia)
```

---

## Plano de Implementação

### Fase 1 — Checar pausa antes de enviar fallback de mídia

**Objetivo:** `_apply_media_fallback` respeitar a pausa global e a pausa por lead antes
de enviar qualquer mensagem.

| Arquivo | O que muda |
|---|---|
| `backend-crm/services/whatsapp_inbound/inbound_handler.py` | `_apply_media_fallback`: duas queries `SELECT` adicionadas antes do envio (mesmas tabelas já usadas na checagem de texto) |

```python
# ANTES
if behavior == "ignorar":
    return {"status": "ignored", "reason": "media_fallback_ignore"}

# "continuar" ou "pausar": enviar mensagem ao lead directamente (sem job queue)
if msg:
    ...

# DEPOIS
if behavior == "ignorar":
    return {"status": "ignored", "reason": "media_fallback_ignore"}

with get_connection() as _conn_pause:
    _pause_row = _conn_pause.execute(
        "SELECT is_paused FROM bot_global_pause_state WHERE user_id = ?", (user_id,)
    ).fetchone()
    if _pause_row and int(_pause_row["is_paused"] or 0) == 1:
        return {"status": "skipped", "reason": "global_pause"}

    _lead_row = _conn_pause.execute(
        "SELECT bot_disabled FROM leads WHERE user_id = ? AND phone = ? LIMIT 1",
        (user_id, phone),
    ).fetchone()
    if _lead_row and int(_lead_row["bot_disabled"] or 0) == 1:
        return {"status": "skipped", "reason": "bot_disabled"}

# "continuar" ou "pausar": enviar mensagem ao lead directamente (sem job queue)
if msg:
    ...
```

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `572b99c` | fix: `_apply_media_fallback` respeita pausa global e por lead |

**Detalhes do commit `572b99c`:**
- `backend-crm/services/whatsapp_inbound/inbound_handler.py` — `_apply_media_fallback`: duas queries `SELECT` (`bot_global_pause_state`, `leads.bot_disabled`) adicionadas antes do envio via `send_whatsapp_direct`

### Relatório da Fase 1 — o que mudou na prática

**Antes:** ao pausar o bot (globalmente pelo botão do Kanban, ou individualmente num lead), o bot ainda respondia sozinho com uma mensagem automática sempre que o lead enviava uma imagem, vídeo, figurinha, documento ou áudio não transcrito.
**Agora:** essa resposta automática de mídia só é enviada se o bot estiver realmente ativo — se estiver pausado (global ou naquele lead específico), nada é enviado.
**Para validar:** Cenário C1 e C2, abaixo.

---

## Checks de Validação

### Cenário C1 — Bot pausado globalmente não responde a imagem/vídeo
- [ ] Pausar o bot globalmente no Kanban
- [ ] Enviar uma imagem de um número de teste para o WhatsApp do utilizador
- [ ] Confirmar: nenhuma mensagem automática chega de volta
- [ ] Repetir com um vídeo

### Cenário C2 — Retomando o bot, fallback volta a funcionar (se configurado)
- [ ] Retomar o bot no Kanban
- [ ] Enviar uma imagem/vídeo do mesmo número de teste
- [ ] Confirmar: se `offer_pack.media_fallback` estiver como `"continuar"` ou `"pausar"`, a
      mensagem configurada é enviada normalmente

---

## Ajustes Possíveis Pós-Implementação

- Nenhum identificado no momento — correção pontual e isolada.
