# Guia de Testes — WhatsApp Real (pós-implementações etapa 8.6 / 8.7)

**Última atualização:** 29/05/2026  
**Lido por:** Claude Code (MCP)  
**Objetivo:** validar no WhatsApp real todas as implementações feitas nas etapas 8.6 e 8.7, na ordem correta de dependências.

---

## Como usar este guia

1. Execute os grupos de teste **em ordem sequencial** — cada grupo depende do anterior.
2. Ao final de cada grupo, marque o checkbox `[x]` correspondente neste arquivo.
3. Se um cenário falhar e precisar de correção:
   - Leia o arquivo de origem da implementação (coluna "Referência")
   - Siga as orientações de `docs/implementations/_guia-documentar-implementacao.md`, com **uma adaptação**: em vez de criar um arquivo novo, **adicione uma nova fase ao arquivo de origem citado**, seguindo o padrão da seção "Quando um teste revelar um bug ou comportamento inesperado" do guia.
4. Após corrigir, revalide o cenário que falhou antes de avançar para o próximo grupo.
5. Grupos que exigem a participação do usuário estão marcados com `⚠️ Requer usuário`.

### Verificação obrigatória antes de pedir mensagem ao usuário

**Antes de solicitar ao usuário que envie qualquer mensagem do número do lead**, verificar se a instância WhatsApp está conectada:

```python
# Checar status da conexão no core.db
SELECT instance_id, status FROM whatsapp_connections WHERE user_id = 4 ORDER BY id DESC LIMIT 1;
```

Ou navegar em **AI Profile → aba CONEXÃO** e confirmar que o status é **CONECTADO** e a sessão está **Ativa**.

- Se **CONECTADO** → prosseguir com o teste.
- Se **DESCONECTADO** → avisar o usuário: *"A instância WhatsApp está desconectada. Por favor clique em 'Reconectar QR' e escaneie o QR com o WhatsApp do bot para restabelecer a sessão antes de continuar."*

> **Motivo:** A API gratuita UazAPI expira periodicamente; reinícios do backend-crm também podem quebrar a sessão. Se o webhook não receber mensagens, o teste falha silenciosamente sem erro óbvio.

---

## Pré-requisitos gerais

Antes de iniciar qualquer teste:

- [ ] `backend-core` rodando na porta 8001
- [ ] `backend-crm` rodando na porta 8000
- [ ] `backend-executors` rodando na porta 8002
- [ ] `frontend-crm` rodando (porta 5173)
- [ ] Variáveis de ambiente configuradas: `OPENAI_API_KEY`, `CRM_PUBLIC_BASE_URL`, `CRM_WEBHOOK_SECRET`
- [ ] Número WhatsApp de teste disponível para receber mensagens (número do lead de teste)

---

## Grupo 1 — Conexão WhatsApp QR Code

**Referência:** [`docs/implementations/fix-conexao-whatsapp-qr-code.md`](../implementations/fix-conexao-whatsapp-qr-code.md)  
**Dependências:** nenhuma — pode ser executado primeiro, sem número de lead  
**Participação do usuário:** ⚠️ P2 requer escanear o QR com o celular

### Por que começa aqui

Sem uma conexão WhatsApp funcional, todos os testes reais subsequentes são impossíveis. Este grupo valida a infraestrutura de conexão antes de qualquer outra coisa.

### Cenários

| # | Descrição | Exige participação | Validado |
|---|---|---|---|
| P1 | QR code exibido ao clicar "Reconectar QR" na aba Conexão do número | Não | [x] 29/05/2026 |
| P2 | Conexão detectada automaticamente após scan (polling 3s) | ⚠️ Escanear QR | [x] 29/05/2026 |
| P3 | QR expira após 90s sem scan → botão "Novo QR code" aparece e gera novo QR | Não | ⏭️ Pulado |
| P4 | `CRM_PUBLIC_BASE_URL` ausente → QR ainda aparece (webhook falha com warning) | Não | ⏭️ Pulado |

**Condição de avanço:** P1 e P2 validados. P3 e P4 são secundários mas recomendados.

---

## Grupo 2 — Fallback de Instance ID no Core Send

**Referência:** [`docs/implementations/fix-core-send-instance-fallback.md`](../implementations/fix-core-send-instance-fallback.md)  
**Dependências:** Grupo 1 (conexão funcional)  
**Participação do usuário:** ⚠️ C1 requer enviar mensagem real pelo número do lead

### Por que é o segundo

Valida que os jobs de envio sobrevivem a reconexões. Se este mecanismo estiver quebrado, todos os envios automáticos dos testes seguintes podem falhar silenciosamente por instance_id inválido — mascarando outros problemas.

### Cenários

| # | Descrição | Exige participação | Validado |
|---|---|---|---|
| C1 | Lead envia mensagem → job criado → reconectar WhatsApp antes do job executar → mensagem chega com `core_send_instance_fallback attempt=1` no log | ⚠️ Lead envia mensagem + reconexão | [x] 29/05/2026 — job 385 com instance_id=INVALIDTEST → fallback → status=sent, provider_msg_id confirmado |
| C2 | Job com instance_id inativo + sem conexão ativa → após 2 fallbacks, job falha com `retryable=false` | Não (simulação) | ⏭️ Edge case — pulado |
| C3 | Simular 403 no `core_send` (token inválido) → não entra no loop de fallback | Não (simulação) | ⏭️ Edge case — pulado |

**Condição de avanço:** C1 validado. C2 e C3 são validações de edge case.

---

## Grupo 3 — Buffer de Mensagens no WhatsApp Real

**Referência:** [`docs/implementations/etapa-8-6-delay-buffer-playground.md`](../implementations/etapa-8-6-delay-buffer-playground.md)  
**Dependências:** Grupo 1 (conexão funcional)  
**Participação do usuário:** ⚠️ Requer lead enviando mensagens consecutivas

### Por que é o terceiro

Teste simples e de curta duração. Valida a paridade de comportamento entre playground (modo lote, já validado) e WhatsApp real para a absorção de mensagens. Boa confirmação de que o pipeline básico de inbound está saudável antes dos testes mais complexos.

### Cenários

| # | Descrição | Exige participação | Validado |
|---|---|---|---|
| W1 | Configurar `multi_message_buffer_seconds = 30`; lead envia 3 mensagens em < 30s; bot responde **uma única vez** com contexto das 3 mensagens acumuladas | ⚠️ Lead envia 3 mensagens rapidamente | [x] 29/05/2026 — 3 msgs em 7s → 1 job criado → 1 resposta "Qual é o faturamento anual?" absorvendo contexto e-commerce |

**Condição de avanço:** W1 validado.

---

## Grupo 4 — Toggle Bot por Lead Individual

**Referência:** [`docs/implementations/etapa-8-7-toggle-bot-lead.md`](../implementations/etapa-8-7-toggle-bot-lead.md)  
**Dependências:** Grupo 1 (conexão funcional)  
**Participação do usuário:** ⚠️ Requer lead enviando mensagem após desativação

### Por que é o quarto

Todos os cenários de UI foram validados em playground (28/05/2026). Aqui o objetivo é confirmar que o flag `bot_disabled=true` realmente bloqueia o pipeline de inbound no WhatsApp real — não apenas a UI.

### Cenários

| # | Descrição | Exige participação | Validado |
|---|---|---|---|
| W1 | Desativar bot para lead via UI (checkbox confirmado) → lead envia mensagem real → bot **não responde** (job não é criado ou é descartado no guardrail) | ⚠️ Lead envia mensagem | [x] 29/05/2026 — inbound_handler retornou `skipped/bot_disabled` sem criar job, nenhum outbound gerado |
| W2 | Reativar bot via UI → lead envia mensagem → bot responde normalmente | ⚠️ Lead envia mensagem | [x] 29/05/2026 — job 388 criado, outbound 264 sent, bot respondeu next qualification question |

**Condição de avanço:** W1 e W2 validados.

---

## Grupo 5 — Transcrição de Áudio Inbound

**Referência:** [`docs/implementations/etapa-8-6-audio-transcricao-inbound.md`](../implementations/etapa-8-6-audio-transcricao-inbound.md)  
**Dependências:** Grupos 1 e 2 (conexão + instance fallback)  
**Participação do usuário:** ⚠️ Todos os cenários 1–8 requerem lead enviando PTT

### Por que é o quinto

Requer infraestrutura de conexão sólida (Grupos 1 e 2) e a `OPENAI_API_KEY` configurada no `backend-crm`. É a feature mais rica em cenários — 8 a validar — mas a lógica de inbound é agnóstica à Camada 7, tornando-a mais isolada do que o Grupo 6.

### Pré-requisito específico

- `OPENAI_API_KEY` configurada no ambiente do `backend-crm`
- AI Profile → Camada 3 → "Mídia inválida" configurado antes de cada cenário conforme descrito

### Cenários

Executar na ordem abaixo — alguns cenários alteram configuração do AI Profile para o próximo.

| # | Descrição | Configuração necessária | Validado |
|---|---|---|---|
| C1 | Toggle áudio **ligado** → lead envia PTT → bot transcreve e responde ao conteúdo | Toggle ON | [x] 30/05/2026 — inbound_event 274, job 391 `[Áudio]: E aí`, bot respondeu ao conteúdo transcrito |
| C2 | Toggle **desligado** + Mídia inválida = "Responder e continuar" → lead envia PTT → bot responde com `media_fallback_msg`, bot não desabilitado | Toggle OFF, fallback "continuar" | [x] 30/05/2026 — envio directo via send_whatsapp_direct (sem job queue), confirmado pelo utilizador |
| C3 | Toggle **desligado** + Mídia inválida = "Responder e pausar" → lead envia PTT → `media_fallback_msg` enviada + bot desabilitado para o lead | Toggle OFF, fallback "pausar" | [x] 30/05/2026 — "Não consigo processar áudios" enviado via send_whatsapp_direct, bot_disabled=1 confirmado no DB |
| C4 | Toggle **desligado** + Mídia inválida = "Ignorar" → lead envia PTT → nenhuma mensagem enviada, log mostra `media_fallback_ignore` | Toggle OFF, fallback "ignorar" | [x] 30/05/2026 — bot_disabled=0, zero outbound events, descarte silencioso confirmado |
| C5 | Regressão — lead envia **texto normal** → fluxo inalterado (sem impacto do sistema de áudio) | Toggle ON ou OFF | [x] 30/05/2026 — job 389 "Oi", job 391 com texto, fluxo normal inalterado |
| C6 | Falha de transcrição (simular `OPENAI_API_KEY` inválida ou ausente) → sistema aplica `media_fallback` em vez de quebrar | Toggle ON, key inválida | [ ] |
| C7 | Lead envia **vídeo ou figurinha** com fallback "continuar" → `media_fallback_msg` enviada, bot **não** tenta transcrever | Toggle ON ou OFF, fallback "continuar" | [ ] |
| C8 | Usuário existente sem campo `audio_transcription_enabled` no AI Profile → default `False` aplicado, sem erro | Usuário legacy | [ ] |

> **Nota C3:** após validar, reativar o bot manualmente antes de prosseguir para C4 e C5.

**Condição de avanço:** C1 e C5 obrigatórios. C2–C4 confirmam os fluxos de fallback. C6–C8 são edge cases.

---

## Grupo 6 — Camada 7: Modelo Sequencial de Gatilhos

**Referência:** [`docs/implementations/camada7-sequential-trigger-model.md`](../implementations/camada7-sequential-trigger-model.md)  
**Dependências:** Todos os grupos anteriores  
**Participação do usuário:** ⚠️ Todos os cenários requerem lead enviando mensagens

### Por que é o último

É o teste mais complexo. Depende de:
- Conexão estável (Grupo 1)
- Instance fallback funcional (Grupo 2)
- Pipeline de inbound saudável (Grupos 3 e 4)
- Configuração prévia dos blocos da Camada 7 no AI Profile do agente

### Pré-requisito específico

Configurar no AI Profile do agente (ex.: `sdr_scheduler`):
- **Fase Apresentação (p2):** `[PHASE TRIGGER → MENSAGEM "Olá, aqui estão os detalhes" → MIDIA [áudio] → MENSAGEM "Gostou?"]`
- **Fase com kw_trigger:** bloco com keyword de teste (ex.: "preço") e `fire_once=True`
- **Fase com intent_trigger:** bloco "demonstrar hesitação" e `fire_once=True`

### Cenários — Phase 10 (ordenação WhatsApp real)

| # | Descrição | Validado |
|---|---|---|
| W1 | Lead entra em qualificação → completa qualificação → transita para Apresentação → confirmar no WhatsApp real: mensagens automáticas chegam **antes** da resposta LLM (não depois) | [ ] |
| W2 | Verificar no DB: coluna `leads.phases_triggered` contém `["p2"]` após a primeira execução real | [ ] |
| W3 | 2ª mensagem do lead já em Apresentação → auto-mensagens **não repetem** (flag `phases_triggered` impede re-disparo) | [ ] |

### Cenários — Phase 6 (intent_trigger real, playground pendente)

Estes cenários estão listados como não validados em Fase 6 do arquivo de origem. Executar no playground antes de testar no WhatsApp real se ainda não feito.

| # | Descrição | Validado |
|---|---|---|
| P1 | Configurar `intent_trigger "demonstrar hesitação" → midia` numa fase; enviar mensagem neutra no playground → mídia **não** enviada | [ ] |
| P2 | Enviar mensagem com hesitação ("não sei se vale...") no playground → mídia **enviada** | [ ] |
| P3 | Fase sem `intent_trigger` → prompt da LLM mãe não inclui seção de detecção (verificar trace/log) | [ ] |

### Cenários — fire_once (kw_trigger e intent_trigger, já validados em playground)

Estes foram confirmados no playground. Validar no WhatsApp real como regressão:

| # | Descrição | Validado |
|---|---|---|
| W4 | `kw_trigger("preço") + fire_once=True` → lead menciona "preço" → dispara → lead menciona "preço" novamente → **não dispara** | [ ] |
| W5 | `intent_trigger("hesitação") + fire_once=True` → lead hesita → dispara → lead hesita novamente → **não dispara** | [ ] |

**Condição de avanço:** W1 e W2 obrigatórios para validar a implementação central da Fase 10.

---

## Resumo do estado de validação

| Grupo | Implementação | Status |
|---|---|---|
| 1 — QR Code | `fix-conexao-whatsapp-qr-code.md` | ⏳ Pendente |
| 2 — Instance Fallback | `fix-core-send-instance-fallback.md` | ⏳ Pendente |
| 3 — Buffer real | `etapa-8-6-delay-buffer-playground.md` | ⏳ Pendente (playground ✅) |
| 4 — Toggle Bot | `etapa-8-7-toggle-bot-lead.md` | ⏳ Pendente real (playground ✅) |
| 5 — Áudio Inbound | `etapa-8-6-audio-transcricao-inbound.md` | 🔶 Parcial — C1, C2, C5 ✅ / C3, C4, C6, C7, C8 pendentes |
| 6 — Camada 7 | `camada7-sequential-trigger-model.md` | ⏳ Pendente real (playground ✅) |

---

## Protocolo quando precisar de ajuda do usuário

Quando um cenário marcado com ⚠️ for atingido, parar e comunicar ao usuário:

> "Para validar o **[nome do cenário]**, preciso que você conecte o WhatsApp de um lead de teste. O número deve ser capaz de:
> - Enviar mensagens para o número conectado no sistema
> - Confirmar o recebimento de mensagens no celular do lead
>
> Quando estiver pronto, me avise e prossigo com a validação."

Aguardar confirmação do usuário antes de marcar o cenário como validado.

---

## Protocolo de correção

Se um cenário falhar:

1. Identificar o arquivo de origem na coluna "Referência" do grupo
2. Ler a seção de implementação relevante nesse arquivo
3. Seguir `docs/implementations/_guia-documentar-implementacao.md` para o diagnóstico
4. **Em vez de criar um arquivo novo**, adicionar uma nova seção ao final do arquivo de origem:
   ```markdown
   ## Fase N+1 — Diagnóstico + Correção (DD/MM/AAAA)
   ### Problema identificado
   <O que o teste real revelou. Causa raiz.>
   ### Correção
   | Arquivo | Mudança |
   |---|---|
   | ... | ... |
   ```
5. Após corrigir e commitar, revalidar o cenário que falhou
6. Só então avançar para o próximo grupo
