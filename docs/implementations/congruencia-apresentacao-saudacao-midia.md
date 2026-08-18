# Congruência na apresentação: cumprimento duplicado + mídia depois da pergunta

**Branch:** `fix-intent-trigger-fase-entrada`
**Status:** Em andamento

---

## Motivação

Ao validar ao vivo a correção da mídia da tabela de preços (feature anterior, já
graduada), o usuário notou dois problemas de "humanização" na mesma conversa de
teste, exportada em `playground-2026-08-18_20-26-output.md`:

1. **Cumprimento duplicado:** o bot diz "Boa tarde!" na resposta de recepção, e
   segundos depois a resposta de apresentação (2ª chamada, mesmo turno) começa
   *de novo* com "Boa tarde!".
2. **Mídia chega depois da pergunta:** o bot diz "Aqui está a tabela de preços..." e
   "Dê uma olhada e me diga qual pacote chamou mais a sua atenção?" — e só *depois*
   dessas duas frases as 3 imagens realmente aparecem na conversa.

Ambas as causas foram diagnosticadas com logs de depuração temporários (revertidos
após o diagnóstico) contra o mesmo ambiente local usado para validar a implementação
anterior — são de sistema (prompt/código), não algo que o perfil do agente
(`custom_instructions`) consiga corrigir de forma confiável, pois afetam qualquer
perfil que use os mesmos caminhos de código.

---

## Problemas Identificados (estado anterior)

1. **Cumprimento duplicado
   (`decision_engine.py:968-974`, `_build_daughter_identity_block`):** a regra
   "REGRA ANTI-REPETIÇÃO" já existente falava de "frases, conteúdo ou informações"
   de forma genérica, mas não nomeava saudações — confirmado via log que a LLM
   repetiu "Boa tarde!" mesmo com a saudação anterior já visível no histórico
   (`next_action_hint='reply'`, não `'greet'`; não era primeiro contato).
2. **Mídia sem aviso de envio pendente
   (`decision_engine.py:469-494`, `_evaluate_sales_flow_phases`):** o aviso
   `[Mídia enviada automaticamente ao lead: ...]` só era injetado no prompt filho
   quando `phase_trigger_fired=True`. Para `intent_trigger`/`kw_trigger` — onde a
   ordem real de despacho (`whatsapp.py:1210`) manda a mídia **depois** do texto da
   LLM — esse aviso não existia, então a LLM escrevia como se a mídia já tivesse sido
   entregue ("aqui está").

---

## Abordagem

Duas correções pontuais de prompt, isoladas e de baixo risco — nenhuma mexe na lógica
de disparo de triggers nem na ordem real de despacho (decisão tomada com o usuário:
mudar a ordem afetaria todos os fluxos que já usam `intent_trigger`+mídia hoje,
incluindo casos onde a mídia é material de apoio pós-resposta). Ambas só mudam o
TEXTO que a LLM recebe/gera:

```
1. REGRA ANTI-REPETIÇÃO ganha uma linha nomeando saudações explicitamente.
2. midia/mensagem fora de phase_trigger alimentam uma lista _deferred_media_notes;
   ao final de _evaluate_sales_flow_phases, uma nota combinada avisa o que está
   pendente e instrui fraseado no futuro ("vou te mandar já") em vez de "aqui está".
```

---

## Plano de Implementação

### Fase única — Reforços de prompt para saudação e mídia pendente

**Objetivo:** conversa soar congruente — sem saudação repetida, sem prometer algo
antes de efetivamente enviar.

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/decision_engine.py` | `_build_daughter_identity_block()`: nova linha na REGRA ANTI-REPETIÇÃO nomeando saudações. `_evaluate_sales_flow_phases()`: nova lista `_deferred_media_notes`, populada quando `midia`/`mensagem` dispara sem `phase_trigger_fired`; injeção combinada antes do `return result` |
| `backend-executors/tests/test_sales_flow_intent_trigger_phase_entry.py` | 4 novos testes: regra anti-repetição de saudação; nota de mídia pendente via `intent_trigger`; regressão confirmando que `phase_trigger` continua usando o aviso "enviada automaticamente" (passado) |
| `docs/architecture/sales-flow.md` | Nova nota "Contexto para o LLM filho (quando midia/mensagem dispara SEM phase_trigger)" |

```python
# ANTES (decision_engine.py, _build_daughter_identity_block)
block += (
    "\nREGRA ANTI-REPETIÇÃO (obrigatória):\n"
    "- Leia o histórico antes de responder.\n"
    "- NUNCA repita frases, conteúdo ou informações já enviados nesta conversa.\n"
    "- NUNCA envie tabelas de preços ou imagens de forma repetida — se já foram enviadas, não mencione nem instrua o cliente a 'ver as informações'.\n"
    "- Cada resposta deve avançar a conversa, não repetir o turno anterior.\n"
)

# DEPOIS — nova linha entre a 3ª e a última
"- NUNCA repita saudações (Bom dia/Boa tarde/Boa noite/Olá/Oi): se o histórico já\n"
"  contém UMA mensagem tua nesta troca, não cumprimente de novo — vai direto ao\n"
"  conteúdo. Cumprimenta uma vez por conversa, não uma vez por resposta.\n"
```

```python
# ANTES (decision_engine.py, _evaluate_sales_flow_phases — midia/mensagem)
if result.get("phase_trigger_fired"):
    result["prompt_injections"].append(f"[Mídia enviada automaticamente ao lead: {_mtype}]")
# (sem else — nada acontecia para intent_trigger/kw_trigger)

# DEPOIS
if result.get("phase_trigger_fired"):
    result["prompt_injections"].append(f"[Mídia enviada automaticamente ao lead: {_mtype}]")
else:
    _deferred_media_notes.append(_mtype)
# ... (mesma lógica para "mensagem")
# ao final da função, se _deferred_media_notes:
result["prompt_injections"].append(
    f"[FLUXO DE VENDA — envio automático pendente: {_items}. Isto será enviado "
    "AUTOMATICAMENTE logo APÓS a tua resposta — ainda NÃO foi enviado.\n"
    "NÃO digas 'aqui está'/'segue' nem peças para o lead já ver/escolher agora;\n"
    "usa fraseado no futuro (ex.: 'vou te mandar já', 'te envio agora') e evita\n"
    "perguntas que dependam do lead já ter visto o conteúdo nesta mesma mensagem.]"
)
```

### Commits Fase única

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `83073d2` | fix: reforçar prompt contra saudação duplicada e mídia sem aviso de pendência |

**Detalhes do commit:**
- `backend-executors/app/services/decision_engine.py` — regra anti-repetição de saudação; nota combinada de mídia pendente
- `backend-executors/tests/test_sales_flow_intent_trigger_phase_entry.py` — 4 novos testes
- `docs/architecture/sales-flow.md` — nova nota sobre aviso de mídia pendente

### Relatório da Fase — o que mudou na prática

**Antes:** quando a apresentação acontecia logo após a recepção no mesmo turno (lead
manda saudação + pergunta comercial juntas), o bot cumprimentava duas vezes seguidas.
E quando o Fluxo de Venda tinha mídia configurada num gatilho de intenção, o texto do
bot prometia "aqui está" antes das imagens realmente chegarem — a mídia sempre chega
depois do texto nesse tipo de gatilho, mas o bot não sabia disso.

**Agora:** o prompt da LLM filha inclui uma regra explícita contra repetir saudações
já feitas na mesma troca, e um aviso claro quando há mídia/mensagem pendente de envio,
instruindo fraseado no futuro em vez de tratar como já entregue.

**Para validar:** Cenário P1, abaixo.

---

## Checks de Validação

### Cenário P1 — Reprodução da conversa relatada (Playground)
- [ ] Abrir Playground com o agente "Daniel" (ID 5, perfil Sensi Vitae, `agent_mode=agenda`), conta `autodigital157@gmail.com`
- [ ] Cenário Inbound: lead diz "olá boa tarde, gostaria de saber sobre as massagens"
- [ ] Confirmar: a resposta de apresentação (2ª bolha do bot, mesmo turno) NÃO abre com "Boa tarde"/"Olá" de novo
- [ ] Lead diz "sim, pode enviar" quando o bot oferecer a tabela de preços
- [ ] Confirmar: o texto da LLM não diz "aqui está"/"segue" antes das imagens — usa fraseado no futuro
- [ ] Confirmar: as 3 imagens continuam chegando corretamente (sem regressão da implementação anterior)

### Verificação automatizada (pytest — já executada nesta sessão, sem browser)
- [x] `pytest backend-executors/tests/test_sales_flow_intent_trigger_phase_entry.py -v` — 11/11 passaram
- **Validado em:** 18/08/2026 — suíte completa (`pytest tests/ -q`) confirmada sem
  regressão nova: as mesmas 22 falhas pré-existentes (não relacionadas)

---

## Ajustes Possíveis Pós-Implementação

- A Opção B (inverter a ordem de despacho para `intent_trigger`/`kw_trigger` enviarem
  mídia ANTES do texto, como `phase_trigger` já faz) foi conscientemente descartada
  nesta implementação por afetar todos os fluxos que já dependem da ordem atual — se
  no futuro isso se mostrar necessário, avaliar tornar a ordem configurável por bloco
  em vez de trocar o default global.
