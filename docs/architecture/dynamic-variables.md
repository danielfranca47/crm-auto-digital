# Variáveis Dinâmicas (`{{chave}}`)

Sistema de templating usado em campos de texto configuráveis do AI Profile e
do Fluxo de Venda, permitindo referenciar dados do lead/negócio/agente sem
hardcode. Sintaxe: `{{chave}}`.

---

## Motor de resolução

**Arquivo:** `backend-crm/automations/assistente_ia/variable_resolver.py`

```python
resolve_template(text: str, ctx: ResolutionContext) -> str
build_resolution_context_from_db(*, conn, lead_id, user_id, ai_profile) -> ResolutionContext
```

`ResolutionContext.resolve(key)` retorna o valor da chave ou `None`. Tokens
não resolvidos (chave desconhecida, ou valor vazio) são removidos do texto e
`_cleanup()` normaliza a pontuação/espaços deixados para trás (vírgula solta,
espaços duplos, linhas em branco em excesso) — nunca aparece um "`{{...}}`"
literal nem um "`, .`" residual no texto final.

### Catálogo de variáveis de sistema

| Chave | Resolve para | Fonte |
|---|---|---|
| `{{lead.nome}}` | `leads.contactName` | Lead |
| `{{lead.nome_whatsapp}}` | `leads.wa_display_name` (nome de perfil do WhatsApp) | Lead |
| `{{lead.empresa}}` | `leads.companyName` | Lead |
| `{{agente.nome}}` | `ai_profile.name` | AI Profile |
| `{{negocio.nome}}` | `ai_profile.brand_name` | AI Profile |
| `{{negocio.local}}` | `business_info` (`field_key='endereco'`) | Base de Conhecimento |
| `{{negocio.horario}}` | `business_info` (`field_key='horario'`) | Base de Conhecimento |
| `{{negocio.telefone}}` | `business_info` (`field_key='telefone'`) | Base de Conhecimento |
| `{{reuniao.horario}}` | Data/hora do próximo `appointment` `status='pending'` do lead, formatada no timezone do perfil (`dd/mm às HH:MM`) | Agenda |
| `{{reuniao.titulo}}` | Título do mesmo appointment | Agenda |
| `{{saudacao}}` | "Bom dia" / "Boa tarde" / "Boa noite" pelo `ai_profile.timezone` (default `America/Sao_Paulo`) | Calculado |

Catálogo espelhado no frontend em `frontend-crm/src/types/variables.ts`
(`SYSTEM_VARIABLES`) — usado só para o picker (label/descrição/exemplo);
`variable_resolver.py` é a única fonte de verdade da resolução real.

### Variáveis personalizadas

Qualquer chave em `ai_profile.custom_variables` (dict `{chave: valor}`)
resolve diretamente para o valor configurado. Editadas via `DrawerVariaveis`
em `CamadaIdentidade.tsx` (aba Identidade → "Variáveis Dinâmicas"),
persistidas no campo `custom_variables` do AI Profile (backend-core).

---

## Pontos de entrada (onde `{{}}` é resolvido)

Toda resolução acontece dentro de `enrich_context_bundle()`
(`backend-crm/services/ai_orchestrator/orchestrator.py`) — o único ponto
comum entre Playground e WhatsApp real (ver
[`playground-parity.md`](playground-parity.md)). Nenhum builder chama
`resolve_template()` diretamente.

| Função | O que resolve |
|---|---|
| `_resolve_profile_templates()` | 7 campos fixos do AI Profile: `origin_inbound_opener`, `origin_outbound_opener`, `handoff_custom_text`, `warming_social_proof`, `warming_session_preview` (raiz do profile) + `offer_pack.guarantee_text`, `offer_pack.upsell_message` |
| `_resolve_sales_flow_variables()` | Campo `content` de todo bloco `orientacao`/`mensagem` em `ai_profile.sales_flow.phases[].blocks[]` (Fluxo de Venda — ver [`sales-flow.md`](sales-flow.md)) |

Ambas alteram o dict `ai_profile` in-place, com `lead_id` resolvido de
`bundle.lead["id"]`; se o bundle ainda não tem lead (ex.: alguns cenários
sintéticos), a resolução é pulada. Falha (exceção) em qualquer uma é
capturada e logada — o texto original (com `{{}}` literal) segue em frente
em vez de quebrar o turno.

**Um novo campo de texto configurável que deve suportar `{{}}`** entra numa
dessas duas listas (`_TEMPLATE_FIELDS`/`_OFFER_PACK_TEMPLATE_FIELDS` no
primeiro caso) — nunca resolvido ad-hoc no builder do Playground ou do
executor.

---

## UI — atalho `/` e picker

**Componentes:** `frontend-crm/src/components/agente/VariableTextarea.tsx` +
`VariablePicker.tsx`.

- Digitar `/` num `VariableTextarea` abre o picker (portal para `document.body`,
  escapando de containers com `transform`/overflow). Digitar filtra a lista
  (`filterText`); `Esc`, clique fora, ou apagar até antes do `/` fecha.
  `Enter`/`Tab` seleciona.
- Ao selecionar, o `/` + filtro digitado é substituído pelo token `{{chave}}`
  e o cursor reposiciona depois dele.
- Enquanto o campo tem conteúdo, um preview somente-leitura abaixo do textarea
  (`TokenPreview`) renderiza cada `{{chave}}` como um badge colorido com o
  `label` amigável (ex. `{{lead.nome_whatsapp}}` → badge "Nome no WhatsApp").
- `buildVariableList(customVars)` (`types/variables.ts`) concatena
  `SYSTEM_VARIABLES` com as `custom_variables` do perfil — é essa lista
  combinada que cada `VariableTextarea` recebe via prop `variables`.

**Onde `VariableTextarea` é usado:**

| Componente | Campo(s) |
|---|---|
| `CamadaIdentidade.tsx` | `origin_inbound_opener`, `origin_outbound_opener`, `warming_social_proof`, `warming_session_preview`, e o gerenciamento de `custom_variables` (`DrawerVariaveis`) |
| `CamadaPipeline.tsx` | `handoff_custom_text` |
| `CamadaOferta.tsx` | `offer_pack.guarantee_text`, `offer_pack.upsell_message` |
| `CamadaFluxoVenda.tsx` | Campo `content` dos blocos `orientacao`/`mensagem` (via `BlockForm`, usado por `BlockModal`/`RuleBuilderModal`) — `customVars` propagado desde `config.custom_variables` até `BlockForm` |

---

## Arquivos críticos

| Arquivo | Responsabilidade |
|---|---|
| `backend-crm/automations/assistente_ia/variable_resolver.py` | `resolve_template()`, `ResolutionContext`, `build_resolution_context_from_db()`, catálogo de chaves resolvidas |
| `backend-crm/services/ai_orchestrator/orchestrator.py` | `_resolve_profile_templates()`, `_resolve_sales_flow_variables()`, ambas chamadas em `enrich_context_bundle()` |
| `frontend-crm/src/types/variables.ts` | `SYSTEM_VARIABLES`, `buildVariableList()` |
| `frontend-crm/src/components/agente/VariableTextarea.tsx` | Textarea com atalho `/`, preview de tokens |
| `frontend-crm/src/components/agente/VariablePicker.tsx` | Dropdown de seleção de variável |
| `frontend-crm/src/components/agente/CamadaIdentidade.tsx` | Campos de abertura/warming + `DrawerVariaveis` (CRUD de `custom_variables`) |
| `frontend-crm/src/components/agente/CamadaFluxoVenda.tsx` | Campos `orientacao`/`mensagem` do Fluxo de Venda |
