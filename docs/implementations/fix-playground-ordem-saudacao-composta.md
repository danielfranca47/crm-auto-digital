# Fix: ordem invertida no Playground em "saudação composta"

**Branch:** `fix-knowledge-narrativo-repeticao`
**Status:** Em andamento

---

## Motivação

Ao testar o AI Profile local `id=5` (após a reconfiguração do Fluxo de Venda que adicionou
`phase_trigger` à fase p2), o utilizador enviou uma mensagem de saudação composta ("olá boa
tarde, quais massagens faz e valores") e viu a resposta de **apresentação** (tabela de
preços + 3 imagens) aparecer **antes** da resposta de **recepção** ("Boa tarde! Agradeço
pelo contato... Me conta o que você está buscando"). O esperado é o oposto: recepção
primeiro, apresentação depois — a mesma ordem que aconteceria no WhatsApp real.

Confirmado por rastreio de código (sem instrumentação, só leitura) que isto **não acontece
no WhatsApp real**: lá, `requeue_pending_message` cria um job assíncrono novo
(`backend-crm/routes/executor.py:403-431`), executado só depois que a 1ª resposta já foi
enviada — ordem cronológica correta por construção. O bug é exclusivo da simulação síncrona
do Playground, que viola o princípio de paridade Playground ↔ WhatsApp real
(`docs/architecture/playground-parity.md`).

---

## Problemas Identificados (estado anterior)

1. **Flag `phase_trigger_fired` contaminado entre duas decisões** (`backend-crm/routes/playground.py:878`):
   quando uma saudação composta dispara uma 2ª decisão reenfileirada (`_decision2`, tipicamente
   `apresentation`) e o `phase_trigger` dela dispara, o código sobrescreve a MESMA variável
   `phase_trigger_fired` usada pelo frontend para decidir a ordem da **1ª** decisão
   (`decision`, tipicamente `recepcao`).
2. **Itens das duas decisões misturados na mesma lista `auto_items`** (`backend-crm/routes/playground.py:838-869`):
   o texto e a mídia da 2ª decisão são anexados à mesma lista que já contém os itens da 1ª,
   sem nenhuma fronteira entre elas — não há como o frontend saber que parte da lista
   pertence a qual decisão.
3. **Frontend usa o flag contaminado para decidir ordem global** (`frontend-crm/src/pages/Playground.tsx`,
   5 call sites idênticos): como `phase_trigger_fired=True` (por causa do problema 1),
   `auto_items` (já contaminado pelo problema 2) é revelado **antes** de `message_to_send`
   (que é sempre o texto da 1ª decisão) — resultado: tudo da 2ª decisão aparece primeiro.

O WhatsApp real já implementa a regra de ordenação correta para uma única decisão em
`backend-executors/app/runners/whatsapp.py:817-822` e `1018-1024`: quando `phase_trigger_fired`,
os `send_actions` (mídia/mensagem automática) são enviados antes do texto LLM; senão, depois.
Falta aplicar essa mesma regra, isolada por decisão, à 2ª decisão do Playground.

---

## Abordagem

Tratar a 2ª decisão (reenfileirada) como um turno próprio e independente, com ordenação
interna correta (mesma regra do WhatsApp real), sempre renderizado **depois** que o turno
completo da 1ª decisão termina — nunca misturado com `auto_items`/`phase_trigger_fired` da 1ª.

```
Saudação composta → decide() [1ª decisão: recepcao]
  → requeue_pending_message → decide() [2ª decisão: apresentation]

Playground response:
  message_to_send / auto_items / phase_trigger_fired  → só da 1ª decisão
  requeue_items (novo, já pré-ordenado)                → só da 2ª decisão

Frontend: revela turno da 1ª decisão (como já fazia) → SÓ DEPOIS revela requeue_items
```

---

## Plano de Implementação

### Fase 1 — Backend: separar as duas decisões na resposta

**Objetivo:** parar de misturar os itens da 2ª decisão na lista/flag da 1ª; expor a 2ª
decisão em campo próprio, já pré-ordenado pela mesma regra do WhatsApp real.

| Arquivo | O que muda |
|---|---|
| `backend-crm/routes/playground.py` | Novo campo `requeue_items` no `PlaygroundChatResponse`; bloco "Passo 8b" para de escrever em `auto_items`/`auto_messages`/`phase_trigger_fired` compartilhados e monta `_requeue_items` própria, ordenada por `_phase_trigger_fired2` |

```python
# ANTES (linhas 838-844, 864-869, 878) — decision2 escreve nas listas da decision1
auto_items.append({"type": "text", "content": _message_to_send2, ...})
auto_messages.append(_message_to_send2)
...
auto_items.append({"type": "media", "media_url": action2["media_url"], ...})
...
elif atype2 == "mark_phase_triggered" and action2.get("phase_id"):
    _mark_phase_triggered(lead_id, user_id, action2["phase_id"])
    phase_trigger_fired = True   # contamina o flag da decision1

# DEPOIS — lista própria, ordenada pela mesma regra de whatsapp.py:817-822
_requeue_items: list[dict] = []
_requeue_text_item = {"type": "text", "content": _message_to_send2, "source": _source2, "source_label": _source_label2}
_requeue_media_items: list[dict] = []
# ... loop de action2 preenche _requeue_media_items em vez de auto_items ...
# mark_phase_triggered NÃO mexe mais em phase_trigger_fired
if _phase_trigger_fired2:
    _requeue_items = _requeue_media_items + [_requeue_text_item]
else:
    _requeue_items = [_requeue_text_item] + _requeue_media_items
```

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | *(pendente)* | backend: separar 2ª decisão (saudação composta) em `requeue_items` próprio |

---

### Fase 2 — Frontend: revelar `requeue_items` depois do turno principal

**Objetivo:** extrair a lógica de revelação (duplicada 5x) para uma função única, e revelar
`requeue_items` sempre depois do turno da 1ª decisão.

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/services/api.ts` | Novo campo `requeue_items?: PlaygroundAutoItem[]` no tipo `PlaygroundChatResponse` |
| `frontend-crm/src/pages/Playground.tsx` | Nova função `revealBotTurn()` substitui o bloco duplicado nos 5 call sites; revela `requeue_items` (via `revealAutoMessages` já existente) depois do turno principal |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | *(pendente)* | frontend: revealBotTurn() unificado + revelar requeue_items após o turno principal |

---

## Checks de Validação

### Cenário P1 — Saudação composta: recepção antes de apresentação
- [ ] No Playground local (perfil `id=5`), iniciar lead novo e enviar "olá boa tarde, quais massagens faz e valores"
- [ ] Confirmar: a resposta de recepção ("Boa tarde!... Me conta o que você está buscando") aparece **primeiro**
- [ ] Confirmar: a resposta de apresentação (tabela + 3 imagens) aparece **depois**

### Cenário P2 — Turno sem saudação composta continua igual
- [ ] Enviar uma mensagem comum (não composta) num lead já em conversa
- [ ] Confirmar: comportamento idêntico ao anterior à mudança (sem `requeue_items`, sem chamada extra)

---

## Ajustes Possíveis Pós-Implementação

- `suppress_llm_response` da 2ª decisão não foi tratado (fora de escopo — sem indício de que
  a rota `apresentation` alguma vez suprima a resposta da LLM na 2ª decisão).
- O salto de `leads.category` de `qualification` direto para `pre-agendamento` (achado
  separado, cosmético, já registado em investigação anterior desta sessão) continua fora do
  escopo deste fix.
