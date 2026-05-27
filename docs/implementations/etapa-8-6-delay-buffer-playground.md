# Etapa 8.6 — Delay, Buffer e Modo Lote no Playground

## Contexto e motivação

O sistema já possuía configurações de temporização de resposta (delays e buffer de mensagens) funcionando no WhatsApp real, mas havia dois problemas:

1. **Buffer limitado na UI** — o slider de "Absorção de mensagens consecutivas" tinha máximo de 30 segundos, sem possibilidade de configurar intervalos maiores (ex.: 5 minutos de silêncio antes de responder).
2. **Buffer não testável no playground** — o playground usa chamada HTTP síncrona (1 mensagem → 1 resposta imediata), tornando impossível testar o comportamento de absorção de múltiplas mensagens sem usar o WhatsApp real.

## O que foi implementado

### 1. Slider do buffer estendido para 2 horas

**Ficheiro:** `frontend-crm/src/components/agente/CamadaPipeline.tsx`

- Slider de `multi_message_buffer_seconds`: max 30s → **max 7200s (2h)**, step 1 → **step 30**
- Formatter `fmtBuf` atualizado para mostrar tempo legível: "30s", "2min", "1h30min", "2h"
- Label do `bufferLabel` no card principal usa o mesmo formatter

### 2. Modo lote no Playground

**Ficheiro:** `frontend-crm/src/components/playground/PlaygroundChat.tsx`

Toggle "Modo lote" na barra de input do playground:
- Quando ativado: pressionar Enter acumula a mensagem numa fila local em vez de enviar
- Fila visível como chips/badges acima do textarea
- Cada chip tem botão X para remover da fila antes do envio
- Botão "Enviar lote (N)" concatena todas com `\n` e chama `onSend()` uma única vez
- O backend recebe o mesmo contexto que receberia via buffer real (mensagens acumuladas com `\n` entre elas)
- Quando desativado: comportamento original (Enter envia imediatamente)

**Backend:** nenhuma alteração necessária. O endpoint `/api/playground/chat` já aceita `message` multi-linha.

## Como testar

### Buffer estendido (CamadaPipeline)
1. Abrir configurações do agente → "Camada Pipeline" → "Delay de resposta"
2. Verificar que o slider "Absorção de mensagens consecutivas" vai de 0 até 2h
3. Mover o slider para valores como 60s → deve mostrar "1min", 90min → "1h 30min", 7200s → "2h"
4. Salvar e verificar que o AI Profile persiste o novo valor

### Modo lote (Playground)
1. Abrir Playground → iniciar sessão com qualquer agente
2. Clicar no ícone de pilha de mensagens para ativar "Modo lote"
3. Digitar "Oi" e pressionar Enter → aparece como chip (não envia)
4. Digitar "Preciso de ajuda" e pressionar Enter → segundo chip
5. Digitar "É urgente" e pressionar Enter → terceiro chip
6. Clicar "Enviar lote (3)" → bot responde considerando as 3 mensagens como contexto único
7. Verificar que a resposta do bot considera toda a sequência, não apenas a última mensagem
8. Clicar X em um chip para remover e confirmar que fica apenas os restantes
9. Desativar modo lote → Enter volta a enviar imediatamente

### Paridade WhatsApp real vs. playground (buffer)
- Configurar `multi_message_buffer_seconds = 30` no AI Profile
- WhatsApp real: enviar 3 mensagens em < 30s → bot responde 1 vez com contexto acumulado
- Playground (modo lote): escrever 3 mensagens, enviar lote → bot recebe contexto equivalente

## Arquivos alterados

| Arquivo | Descrição |
|---|---|
| `frontend-crm/src/components/agente/CamadaPipeline.tsx` | Slider buffer 2h + formatter legível |
| `frontend-crm/src/components/playground/PlaygroundChat.tsx` | Toggle modo lote + fila visual |
