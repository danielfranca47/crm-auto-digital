# Lead — Schema de Nome (companyName / contactName) e Origem/Canal de Aquisição

## Regra central

`leads.companyName` e `leads.contactName` são ambos opcionais, mas **nunca os dois vazios ao mesmo tempo**. Pelo menos um deve estar preenchido.

## Onde a regra é garantida (3 camadas)

1. **Banco** (`backend-crm/database.py`) — CHECK constraint na tabela `leads`:
   ```sql
   companyName TEXT,   -- nullable (era NOT NULL)
   contactName TEXT,
   CHECK (TRIM(COALESCE(companyName,'')) != '' OR TRIM(COALESCE(contactName,'')) != '')
   ```
   Migração idempotente via `_migrate_leads_company_or_contact()`, chamada em `init_db()`. SQLite não suporta `ALTER COLUMN` — a migração faz rebuild de tabela (`CREATE ... _new` → `INSERT ... SELECT` → `DROP` → `RENAME`), desligando `PRAGMA foreign_keys` durante o rebuild (7 tabelas filhas com `ON DELETE CASCADE`).

2. **API** (`backend-crm/models.py`) — `Lead.companyName: Optional[str] = None`, com `model_validator(mode="after")` que recusa (`ValueError` → 422) quando os dois vêm vazios ou só espaço.

3. **Frontend** (`frontend-crm/src/components/NewLeadModal.tsx`) — telefone sempre obrigatório; Nome **OU** Empresa (botão "Salvar Lead" fica desabilitado e mostra dica visual até um dos dois ser preenchido).

`routes/leads.py` (`criar_lead` e `atualizar_lead_parcial`) captura `sqlite3.IntegrityError` da violação do CHECK e devolve `400` com mensagem clara (`"Informe ao menos o nome da empresa ou o nome do contato"`), em vez de deixar vazar um `500` com o erro cru do SQLite — relevante principalmente num `PATCH` parcial que zere o único nome que o lead tinha.

## Pontos de criação de lead e fallback quando o nome não é conhecido

| Ponto | Arquivo | `companyName` desconhecido | `contactName` desconhecido |
|---|---|---|---|
| Manual (formulário) | `NewLeadModal.tsx` | `NULL` | `NULL` (mas exige pelo menos um dos dois) |
| WhatsApp inbound | `services/whatsapp_inbound/guardrail.py` (`find_or_create_lead_by_phone`) | `NULL` | `wa_display_name` (nome de perfil do WhatsApp) se resolvido; senão telefone normalizado (`phone_norm`) |
| Planilha / Google Maps | `automations/assistente_ia/processor.py` (`map_row_to_lead`) | `NULL` | `NULL` (linha sem nenhum nome viola o CHECK; erro é reportado por linha, batch continua) |
| Playground (sandbox) | `routes/playground.py` (`_create_sandbox_lead`) | `NULL` | `"Lead de Teste"` (fixo) |
| Formulário público do site | `routes/public.py` (`create_public_lead`) | `payload.fullName` (mesmo valor do contato) | `payload.fullName` |

Nenhum ponto de criação inventa nome de empresa fabricado para contornar a obrigatoriedade (removidos: `"WhatsApp inbound"`, `"Sem nome"`, `"Empresa Teste"`).

### Formulário público do site — `user_id` fixo, não multi-tenant

`POST /public/leads` (montado sem prefixo `/api` — `app.py:280`, vira
`/public/leads`) é o endpoint que recebe o formulário de contato do site de
marketing (`website/src/components/CtaSection.tsx`). Autenticado por um único
token fixo (`FORM_TOKEN`) — não tem nenhuma noção de multi-tenant, é
exclusivo de uma única conta CRM de destino.

O `user_id` gravado no lead vem de `PUBLIC_LEAD_USER_ID` (env var,
`_get_public_lead_user_id()`), mesmo padrão de `FORM_TOKEN`/`EMAIL_TO`
(destino fixo, sem essa configuração o endpoint responde 500 em vez de gravar
um lead sem dono). `agent_type` também é resolvido a partir desse mesmo
`user_id` (`resolve_agent_type_for_user(user_id=...)`), refletindo o AI
Profile real da conta de destino em vez de um fallback fixo.

**Histórico:** antes desta implementação, o `INSERT` não incluía `user_id`,
gravando leads com `user_id NULL` — como toda listagem de leads no CRM filtra
por `user_id` exato, esses leads nunca apareciam em nenhum Kanban (nem no do
dono da conta configurada). Não havia risco de vazamento entre contas — só
inexistência de acesso a esses leads pelo próprio dono.

## Exibição (frontend)

Prioridade: nome do contato primeiro. Helper compartilhado:

```ts
// frontend-crm/src/utils/leadDisplayName.ts
leadDisplayName(lead) // "Empresa - Contato" se ambos existirem; senão o que existir; "Lead sem nome" se nenhum
```

Usado em: `LeadCard.tsx`, `KanbanBoard.tsx` (busca + `DragOverlay`), `SearchAutocomplete.tsx`, `components/prospection/ProspectionCard.tsx`, `pages/FollowUpCenter.tsx` (6 pontos: banner de autopausado, header do painel de detalhe, modal de confirmação, avatar de iniciais, label da linha, filtro de busca).

## `wa_display_name` — nome de exibição do WhatsApp (pushName)

Campo separado de `contactName`/`companyName`, nullable, gravado só na **criação** do lead via `find_or_create_lead_by_phone()` (`services/whatsapp_inbound/guardrail.py`). Extraído do payload bruto da UazAPI por `routes/webhooks.py::_resolve_wa_display_name()`, com prioridade `message.senderName` → `chat.wa_name` (nome de perfil do WhatsApp do remetente — existe para qualquer remetente, independente de estar salvo como contato no telefone do bot) → `chat.wa_contactName` → `chat.name` (nome da agenda de contatos do telefone do bot — só existe se o número foi salvo manualmente; usado como último recurso). Prioridade confirmada contra payload real capturado em teste — ver `docs/architecture/webhooks.md`.

**Por que separado de `contactName`:** `contactName` é o nome que o operador edita no card do lead — se `wa_display_name` sobrescrevesse esse campo depois de editado, uma correção manual do operador seria perdida no próximo inbound. Na criação do lead, `contactName` já nasce igual a `wa_display_name` quando disponível (só cai para o telefone-placeholder se nenhum nome for resolvido do payload); a partir daí os dois campos seguem independentes — o operador sempre tem a palavra final.

**Uso no prompt da IA:** `backend-executors/app/services/decision_engine.py::_resolve_lead_name(lead)` resolve o "nome do lead" percorrendo `contactName → companyName → wa_display_name → name`, mas ignora qualquer candidato igual a `lead.phone` (o placeholder gravado quando nenhum nome era conhecido na criação), caindo para o próximo. Não requer nenhuma configuração do operador.

Também exposto como variável de template `{{lead.nome_whatsapp}}` (`automations/assistente_ia/variable_resolver.py`), distinta de `{{lead.nome}}` (que resolve para `contactName`), para uso explícito em campos de template e blocos do Fluxo de Venda — ver [`dynamic-variables.md`](dynamic-variables.md).

**Simulação no Playground:** como `wa_display_name` só nasce naturalmente pelo webhook real da UazAPI, o Playground (`routes/playground.py::PlaygroundChatRequest.wa_display_name`) aceita um valor opcional vindo do `PlaygroundConfigModal` ("Nome do WhatsApp do lead — simulação") e grava-o em `_create_sandbox_lead()` no momento da criação do lead sandbox — mesma regra do mundo real, só na criação, nunca atualizado depois. Sem esse campo, o lead sandbox nasce sempre sem `wa_display_name`.

**Duas fontes de dados distintas no frontend, comportamento diferente:**
- **Via `LeadsContext.tsx`** (`mapRawLead`, usado pelo Kanban/Prospecção) — normaliza `companyName`/`contactName` de `null` (API) para `''` antes de expor como `Lead`. Por isso `Lead.companyName`/`contactName` em `types/crm.ts` permanecem tipados como `string` simples (nunca `null`), consistente com os demais campos do tipo (`phone`, `email`, `origin`, `observations`).
- **Fora de `LeadsContext`** (ex.: `FollowUpCenter.tsx`, via `api.followUps.listActive()`) — recebe `companyName`/`contactName` crus da API, sem essa normalização. `companyName` **pode ser `null` de verdade em runtime** aqui, mesmo que o tipo declarado (`FollowUpLead` em `services/api.ts`) diga `string`. Qualquer novo ponto de leitura de leads fora do `LeadsContext` deve tratar esse campo como potencialmente nulo (usar `leadDisplayName()` ou `?? ''`).

## `origin` (direção) x `acquisition_channel` (canal de marketing)

Dois campos separados, com responsabilidades distintas — não misturar:

- **`leads.origin`** — só a **direção** da conversa: quem falou primeiro. É o único dos dois lido
  pela IA (`_classify_lead_origin()` em `backend-crm/services/ai_orchestrator/orchestrator.py`,
  usado tanto pelo executor real quanto pelo playground): o literal `"outbound"` (após
  trim/lowercase) classifica como outbound; **qualquer outro valor** — incluindo os valores
  técnicos reais gravados pelo sistema (`whatsapp_inbound`, `Formulário Website`, `Manual`,
  `Planilha`, ou qualquer canal livre digitado) — é tratado como inbound por default seguro. Só
  dois pontos gravam `"outbound"` deliberadamente: `ProspectConfirmModal.tsx` (confirmação de
  prospecção fria no Kanban) e `agent-local/app/crm_client.py::log_outbound()`. Ver
  [`pipeline-phases.md`](pipeline-phases.md) para o uso no prompt (`origin_inbound_opener` /
  `origin_outbound_opener`).
- **`leads.acquisition_channel`** — canal de marketing (Facebook Ads, Google Ads, Indicação,
  Website...), texto livre, nullable. Preenchido na criação/edição manual do lead
  (`NewLeadModal.tsx`, `LeadCardDialog.tsx`) e na importação por planilha (Assistente IA — ver
  abaixo). **Não é lido por nenhuma lógica de IA** — puramente informativo/pesquisável (entra na
  busca do Kanban).

### Importação por planilha (Assistente IA)

`map_row_to_lead()` (`backend-crm/automations/assistente_ia/processor.py`) preenche
`acquisition_channel` a partir da planilha em duas camadas, na ordem:

1. **Mapeamento explícito de coluna** — o utilizador escolhe, na tela "1.5. Mapeamento de
   Colunas" do Assistente IA (`frontend-crm/src/pages/AssistenteIA.tsx`), qual coluna da
   planilha corresponde ao campo "Canal de aquisição"; enviado ao backend como
   `column_map["acquisition_channel"]`.
2. **Auto-detecção por nome de coluna** (fallback, usada quando o mapeamento explícito não
   resolve valor para a linha) — colunas literalmente chamadas `canal`, `canal_aquisicao` ou
   `fonte`. O frontend também pré-seleciona esses nomes automaticamente no select de mapeamento
   (`COLUMN_ALIASES` em `AssistenteIA.tsx`), mas o utilizador pode sempre sobrepor.

Colunas chamadas `origem`/`origin` **não** entram nesses fallbacks — esse nome já é reservado
para o campo `origin` (direção da conversa, acima), e um lead confundir os dois campos mudaria
comportamento de IA sem intenção. Planilha sem nenhuma coluna reconhecível deixa
`acquisition_channel = NULL` — mesmo comportamento de "não inventar valor" dos demais campos.

Em reimportações com `overwrite=update`, `update_lead_light()` só preenche
`acquisition_channel` se o lead existente ainda estiver com o campo vazio — um valor já
preenchido (manual ou de importação anterior) nunca é sobrescrito por uma nova planilha.

### Captura no frontend (`LEAD_DIRECTION_OPTIONS`, `frontend-crm/src/lib/lead-origin.ts`)

O Select de "Direção" só oferece 2 valores canônicos — `Manual` (rótulo "Inbound — o lead
procurou primeiro") e `outbound` ("Outbound — eu abordei primeiro"). Ele aparece condicionalmente
em `NewLeadModal.tsx`/`LeadCardDialog.tsx`:

- **Categoria "À Prospectar"** (fila de quem ainda não foi contatado): o Select não aparece —
  `origin` nasce `"Manual"` (inbound) sem perguntar nada. A direção real só é decidida depois,
  quando o card é arrastado para a próxima coluna: o `ProspectConfirmModal` pergunta "Já
  prospectou activamente?" — "Sim, já prospectei" grava `origin="outbound"` +
  `prospection_context`; "Não" mantém inbound.
- **Qualquer outra categoria**: o Select é obrigatório (bloqueia o submit sem escolha), porque o
  lead já está além da fila de prospecção — a direção precisa ser explícita no momento da
  criação/edição.

Um lead com `origin` gravado por um caminho técnico (`whatsapp_inbound`, `Formulário Website`,
`Planilha`) não bate em nenhuma das 2 opções do Select. Em `LeadCardDialog.tsx`, o Select injeta
dinamicamente um 3º `<SelectItem>` **desabilitado** no topo, com `value` = o próprio valor técnico
e label = `formatLeadOriginLabel(origin)` + sufixo " — atual" (ex.: "Inbound (WhatsApp) — atual")
— só quando `editedLead.origin` não bate com nenhum valor canônico. O Radix Select localiza esse
item pelo `value` e mostra seu texto como valor selecionado mesmo estando desabilitado, então o
campo nunca aparece em branco; como o item é `disabled`, ele não pode ser reselecionado — o
operador só muda a direção escolhendo "Inbound" ou "Outbound" explicitamente. O estado
`editedLead.origin` nasce como cópia exata do lead atual e só muda se o usuário efetivamente
escolher uma das 2 opções canônicas (`onValueChange`), então salvar sem tocar nesse campo preserva
o valor técnico original — isso é só sobre a edição; a exibição em modo leitura é tratada à parte,
abaixo. `NewLeadModal.tsx` (criação) não precisa desse item extra: `origin` nasce sempre `Manual`
ou vazio, nunca um valor técnico pré-existente.

### Labels amigáveis em modo leitura (`formatLeadOriginLabel()`)

`formatLeadOriginLabel()` (`frontend-crm/src/lib/lead-origin.ts`) é a única fonte de tradução de
`origin` para exibição — usada em todo ponto que mostra a origem de um lead: `LeadCardDialog.tsx`
(modo leitura), `KanbanBoard.tsx`, `LeadCard.tsx` (card do Kanban), `ProspectionCard.tsx` (card do
board de prospecção) e `SearchAutocomplete.tsx` (resultado da busca). Mapa:

| `origin` (normalizado: trim + lowercase) | Label exibido |
|---|---|
| `manual` | "Inbound" |
| `outbound` | "Outbound" |
| `whatsapp_inbound` | "Inbound (WhatsApp)" |
| `formulário website` | "Inbound (Formulário do site)" |
| `planilha` | "Inbound (Planilha)" |
| vazio / `null` | "—" |
| qualquer outro valor | `Inbound (<valor original>)` — fallback genérico |

O fallback genérico segue a mesma semântica default-safe do `_classify_lead_origin()` (tudo que
não é `outbound` é inbound): um valor técnico novo, ainda não mapeado nesta tabela, nunca aparece
cru na tela — sempre com o prefixo "Inbound (…)". Novo valor técnico gravado no sistema não exige
mudança aqui a menos que se queira um label mais específico do que o fallback genérico.
