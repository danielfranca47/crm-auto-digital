# Nome do WhatsApp no lead + variáveis dinâmicas no Fluxo de Venda

**Branch:** `main`
**Status:** Em andamento

---

## Motivação

Quando um lead manda a primeira mensagem e ainda não tem `contactName`
preenchido no CRM, o agente de IA não tinha nenhum nome para usar — o lead
nascia com `contactName = <telefone>`. A UazAPI expõe o nome de exibição do
WhatsApp (pushName) no payload do webhook, mas nenhum código extraía isso —
era descartado antes de chegar ao lead.

Separadamente, a tela "Variáveis Dinâmicas" (Identidade do agente) já tem uma
infraestrutura pronta e reutilizável de variáveis `{{chave}}` com atalho `/`
(`VariableTextarea` + `VariablePicker` + `SYSTEM_VARIABLES`), mas só estava
ligada a 7 campos fixos do AI Profile (openers, handoff, warming). O Fluxo de
Venda (blocos `orientação`/`mensagem fixa`) usava `<textarea>` puro e o
`decision_engine.py` nunca resolvia `{{}}` nesses blocos — uma variável
digitada ali chegaria **literal** (`{{lead.nome}}`) ao lead.

O utilizador pediu os dois comportamentos combinados: captura + fallback
automático do nome do WhatsApp (sem exigir configuração), e esse nome (junto
com outras variáveis) disponível para reforço manual — instrução ou mensagem
fixa — no Fluxo de Venda, via o mesmo atalho `/` já existente.

---

## Problemas Identificados (estado anterior)

1. **Nome do WhatsApp descartado no primeiro contato:** `backend-crm/routes/webhooks.py` (`whatsapp_uazapi_webhook`) montava `inbound_payload` sem nenhum campo de nome, mesmo com `chat`/`message`/`data` disponíveis. `find_or_create_lead_by_phone()` (`services/whatsapp_inbound/guardrail.py:27-32`) até tinha um fallback (`payload.get("contact_name") or payload.get("sender_name") or payload.get("name")`), mas era código morto — essas chaves nunca existiam no payload. Documentado explicitamente em `docs/architecture/webhooks.md:80` (antes desta mudança).
2. **Variáveis `{{}}` não resolvidas no Fluxo de Venda:** `decision_engine.py` (blocos `orientacao`/`mensagem`, linhas ~467-502) nunca chamava `resolve_template()` — só 7 campos fixos do AI Profile passavam por essa resolução (`services/ai_orchestrator/orchestrator.py::_resolve_profile_templates()`).
3. **Playground não resolvia variáveis nesses 7 campos:** `build_context_bundle_for_playground()` nunca chamava `_resolve_profile_templates()` — só o caminho real do WhatsApp chamava. Achado lateral, corrigido junto na Fase 3 por tocar a mesma função.

---

## Abordagem

```
Webhook UazAPI (primeiro contato, lead novo)
  → routes/webhooks.py extrai wa_display_name do payload bruto
  → guardrail.find_or_create_lead_by_phone grava em leads.wa_display_name
       (nunca sobrescreve contactName)
  → decision_engine.py usa wa_display_name como fallback automático
       de "nome do lead" quando contactName/companyName vazios

Operador quer reforçar/usar explicitamente
  → variable_resolver.py expõe {{lead.nome_whatsapp}}
  → picker "/" já mostra a variável (infraestrutura existente)
  → Fluxo de Venda (orientação/mensagem) passa a resolver {{}} via
       enrich_context_bundle() — único ponto de paridade Playground↔Real
```

---

## Plano de Implementação

### Fase 1 — Captura automática do nome do WhatsApp

**Objetivo:** capturar o pushName da UazAPI na criação do lead e usar como
fallback automático de "nome do lead" em todos os prompts, sem exigir
configuração do operador. `contactName` continua tendo prioridade sempre que
preenchido manualmente.

| Arquivo | O que mudou |
|---|---|
| `backend-crm/database.py` | `ensure_column(conn, "leads", "wa_display_name", "wa_display_name TEXT NULL")` |
| `backend-crm/routes/webhooks.py` | Nova função `_resolve_wa_display_name()` (prioridade `message.senderName` → `chat.wa_name` → `chat.wa_contactName` → `chat.name` — ajustada na Fase 1.1); `inbound_payload["wa_display_name"]` adicionado |
| `backend-crm/services/whatsapp_inbound/guardrail.py` | `find_or_create_lead_by_phone()` lê `payload.get("wa_display_name")` e grava na criação do lead |
| `backend-executors/app/services/decision_engine.py` | 11 pontos que resolviam o nome do lead — substituídos por `_resolve_lead_name(lead)` na Fase 1.1 (ignora o telefone-placeholder, ver abaixo) |
| `docs/architecture/leads-schema.md` | Nova seção `wa_display_name` |
| `docs/architecture/webhooks.md` | Atualizado — nome do WhatsApp agora é capturado |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `33bcec8` | Captura automática do nome do WhatsApp + fallback no decision_engine |

**Detalhes do commit `33bcec8`:**
- `backend-crm/database.py` — `ensure_column(leads, wa_display_name)`
- `backend-crm/routes/webhooks.py` — `_resolve_wa_display_name()` + campo em `inbound_payload`
- `backend-crm/services/whatsapp_inbound/guardrail.py` — grava `wa_display_name` na criação do lead
- `backend-executors/app/services/decision_engine.py` — 11 pontos de fallback de nome atualizados
- `docs/architecture/leads-schema.md`, `webhooks.md` — documentação atualizada

### Relatório da Fase 1 — o que mudou na prática

**Antes:** quando um lead novo mandava a primeira mensagem sem estar salvo no CRM, o agente não sabia o nome dele — usava o próprio número de telefone como "nome" internamente e nunca cumprimentava a pessoa pelo nome.

**Agora:** o sistema captura o nome que aparece no WhatsApp da pessoa (o mesmo nome que aparece pra você na conversa) e passa a usar esse nome automaticamente nas respostas da IA, sem precisar configurar nada no perfil do agente. Se você já tiver preenchido manualmente o nome do lead no card do CRM, essa configuração manual continua tendo prioridade sempre.

**Para validar:** Cenário C1, acima — precisa de uma mensagem real de um número novo (o Playground não passa pelo webhook, então não serve pra testar esta fase específica).

---

## Fase 1.1 — Diagnóstico + Correção: nome errado capturado + fallback nunca acionado (20/08/2026)

Testado ao vivo (WhatsApp real, ambiente local + túnel ngrok). Dois problemas encontrados em sequência.

### Problema 1 — `contactName` (placeholder = telefone) sempre vencia o fallback

Primeira mensagem de um lead novo: IA cumprimentou usando o próprio telefone (`Olá, +5547992163692!`) e, ao ser perguntada "qual meu nome?", respondeu "seu nome não foi identificado" — mesmo com `wa_display_name` corretamente gravado no banco.

**Causa raiz:** `find_or_create_lead_by_phone()` sempre grava `contactName = phone_norm` quando nenhum nome é conhecido na criação — ou seja, `contactName` **nunca é `None`** para leads via WhatsApp, é o telefone como string. `_safe_get(lead, "contactName", "companyName", "wa_display_name", "name")` (Fase 1) para no primeiro valor não-nulo, então `wa_display_name` nunca era alcançado — `contactName` (= telefone) sempre "ganhava" antes.

### Correção 1

| Arquivo | Mudança |
|---|---|
| `backend-executors/app/services/decision_engine.py` | Nova função `_resolve_lead_name(lead)`: percorre `contactName → companyName → wa_display_name → name`, mas ignora qualquer candidato igual ao `lead.phone` (o placeholder), caindo para o próximo. Substituídos os 11 pontos que usavam `_safe_get(...)` diretamente. |
| `backend-crm/services/whatsapp_inbound/guardrail.py` | `contact_name` na criação do lead agora prioriza `wa_display_name` sobre `phone_norm` — o card do lead no CRM já nasce com o nome real, não só o telefone. |

### Problema 2 — Campo errado do payload UazAPI (nome da agenda do telefone, não do perfil do WhatsApp)

Apontado pelo utilizador: o nome capturado ("Daniel França (Filho)") era o nome salvo na lista de **contatos do telefone do bot**, não o nome de perfil que a pessoa define no próprio WhatsApp — que não existiria se o operador não tivesse esse número salvo manualmente no aparelho (caso da maioria dos leads reais).

**Verificação:** payload bruto real capturado via inspector do ngrok (`http://127.0.0.1:4040/api/requests/http`) durante o teste mostrou os dois campos lado a lado no mesmo evento:
- `chat.wa_contactName` / `chat.name` = `"Daniel França (Filho)"` — nome da agenda de contatos do telefone conectado.
- `chat.wa_name` / `message.senderName` = `"França"` — nome de perfil do WhatsApp do remetente.

Confirmado também contra documentação/comunidade da UazAPI: o merge-field consolidado `{{name}}` deles usa `wa_contactName` antes de `wa_name` — o oposto do que precisamos aqui, já que para uso automático de CRM queremos a fonte que existe *independente* de estar salva como contato.

### Correção 2

| Arquivo | Mudança |
|---|---|
| `backend-crm/routes/webhooks.py` | `_resolve_wa_display_name()`: prioridade trocada para `message.senderName` → `chat.wa_name` → `chat.wa_contactName` → `chat.name` (antes: `chat.name` → `chat.wa_name` → ...). Removidas as tentativas em `data.pushName`/`data.senderName` (payload real confirmado sem objeto `data` — só `chat`/`message`). |

### Reteste após as duas correções

Lead de teste resetado e mensagem reenviada:
- `wa_display_name` = `"França"` (nome de perfil, não mais o nome da agenda)
- `contactName` já nasceu como `"França"` (antes: telefone)
- Resposta da IA: **"Oi! Seja bem-vindo, França!"**

### Commits Fase 1.1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `eb0af94` | `_resolve_lead_name()` + prioridade correta de campo no payload UazAPI |

### Relatório da Fase 1.1 — o que mudou na prática

**Antes:** mesmo capturando um nome, a IA não usava — ou usava o nome errado (o da agenda de contatos do telefone do bot, que só existe se o operador salvou aquele número manualmente).

**Agora:** a IA usa corretamente o nome de perfil do WhatsApp da pessoa (que qualquer remetente tem, esteja ou não salvo como contato), com prioridade correta sobre o telefone-placeholder.

**Validado ao vivo em:** 20/08/2026 — ver Cenário C1 abaixo.

---

### Fase 2 — Variável de sistema `{{lead.nome_whatsapp}}` (planejada, não iniciada)

**Objetivo:** permitir referenciar o nome do WhatsApp explicitamente nos 7
campos de template existentes, distinto de `{{lead.nome}}` (contactName).

| Arquivo | O que muda |
|---|---|
| `backend-crm/automations/assistente_ia/variable_resolver.py` | Novo caso `lead.nome_whatsapp` → `_nonempty(lead.get("wa_display_name"))` |
| `frontend-crm/src/types/variables.ts` | Nova entrada em `SYSTEM_VARIABLES` |

---

### Fase 3 — Variáveis dinâmicas no Fluxo de Venda (planejada, não iniciada)

**Objetivo:** permitir `/` e `{{}}` nos blocos `orientação`/`mensagem fixa` do
Fluxo de Venda, com resolução real antes de chegar ao LLM ou ao lead.

| Arquivo | O que muda |
|---|---|
| `backend-crm/services/ai_orchestrator/orchestrator.py` (`enrich_context_bundle`) | Resolver `{{}}` nos blocos `orientacao`/`mensagem` de `ai_profile["sales_flow"]`, reaproveitando `resolve_template`/`build_resolution_context_from_db`. Também mover a chamada de `_resolve_profile_templates()` para cá, fechando o gap de paridade do Playground (achado lateral, problema 3 acima). |
| `frontend-crm/src/components/agente/CamadaFluxoVenda.tsx` | Trocar `<textarea>` dos blocos `orientacao`/`mensagem` por `<VariableTextarea>` |

---

## Checks de Validação

### Cenário C1 — Captura do nome no primeiro contato real (WhatsApp)
- [x] Enviar mensagem de um número novo (sem lead existente) para uma instância de teste
- [x] Confirmar em `leads.wa_display_name`: preenchido com o nome do WhatsApp
- [x] Confirmar que a resposta da IA cumprimenta pelo nome, sem nenhuma configuração no AI Profile
- **Validado em:** 20/08/2026 — ambiente local + túnel ngrok, instância `crm-15-88e456ef` (user_id=15). Duas rodadas de bug encontradas e corrigidas em Fase 1.1 (fallback nunca alcançava `wa_display_name`; campo errado do payload UazAPI). Após correção: `wa_display_name="França"`, `contactName="França"`, IA respondeu "Oi! Seja bem-vindo, França!".

### Cenário P1 — Variável `{{lead.nome_whatsapp}}` num campo de template (Fase 2)
- [ ] Lead de teste com `wa_display_name` já setado
- [ ] Configurar `origin_inbound_opener` com `{{lead.nome_whatsapp}}`
- [ ] Rodar Playground → confirmar que o texto final tem o nome resolvido

### Cenário P2 — Variáveis resolvidas em bloco do Fluxo de Venda (Fase 3)
- [ ] Adicionar bloco `mensagem` na fase Recepção com `{{lead.nome}}`
- [ ] Rodar Playground → confirmar que o texto enviado já veio resolvido
- [ ] Repetir com bloco `orientação` → confirmar que a instrução chega resolvida ao prompt filho

### Cenário P3 — Paridade de template no Playground (achado lateral, Fase 3)
- [ ] Configurar `handoff_custom_text` com `{{negocio.nome}}`
- [ ] Rodar Playground → confirmar que resolve (falhava antes da Fase 3)

---

## Ajustes Possíveis Pós-Implementação

- Leads já existentes não ganham `wa_display_name` retroativamente — só passa a ser gravado em leads novos a partir desta mudança.
- `wa_display_name` só é gravado na criação do lead; se a pessoa mudar o nome de perfil do WhatsApp depois, o valor gravado não é atualizado (mesmo comportamento de `contactName`, que também não sincroniza automaticamente).
