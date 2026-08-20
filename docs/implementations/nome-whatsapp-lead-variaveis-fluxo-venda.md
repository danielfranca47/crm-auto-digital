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
| `backend-crm/routes/webhooks.py` | Nova função `_resolve_wa_display_name()` (tenta `chat.name`/`chat.wa_name`/`message.senderName`/`message.pushName`/`data.pushName`/`data.senderName`, loga quando nenhuma bate); `inbound_payload["wa_display_name"]` adicionado |
| `backend-crm/services/whatsapp_inbound/guardrail.py` | `find_or_create_lead_by_phone()` lê `payload.get("wa_display_name")` e grava na criação do lead |
| `backend-executors/app/services/decision_engine.py` | 11 pontos `_safe_get(lead, "contactName", "companyName", "name")` → `_safe_get(lead, "contactName", "companyName", "wa_display_name", "name")` |
| `docs/architecture/leads-schema.md` | Nova seção `wa_display_name` |
| `docs/architecture/webhooks.md` | Atualizado — nome do WhatsApp agora é capturado |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | *(pendente — registrar após o commit)* | Captura automática do nome do WhatsApp + fallback no decision_engine |

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
- [ ] Enviar mensagem de um número novo (sem lead existente) para uma instância de teste
- [ ] Confirmar em `leads.wa_display_name`: preenchido com o nome do WhatsApp
- [ ] Confirmar que a resposta da IA cumprimenta pelo nome, sem nenhuma configuração no AI Profile

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

- Nome exato do campo UazAPI (`chat.name` vs outras variações) só será confirmado no Cenário C1 — se nenhuma das chaves tentadas bater, ajustar `_resolve_wa_display_name()` com o payload real capturado nos logs.
- Leads já existentes não ganham `wa_display_name` retroativamente — só passa a ser gravado em leads novos a partir desta mudança.
