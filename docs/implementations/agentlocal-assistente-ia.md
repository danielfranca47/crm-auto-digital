# Assistente IA no Agent-Local — Migração do Fluxo de Prospecção

**Branch:** `etapa-9-planos-limites`
**Status:** Em andamento

---

## Motivação

O fluxo de prospecção está actualmente fragmentado entre duas aplicações:

```
Agent-local: Pesquisar → exportar Excel
   ↓ trocar de app
Frontend-CRM: AssistenteIA → importar → gerar copy → criar cards
   ↓ trocar de app
Agent-local: Prospectar → enfileirar WhatsApp
```

O utilizador tem de alternar entre o agent-local e o frontend-crm apenas para
importar a planilha e gerar copy. O objectivo desta implementação é eliminar
essa fricção, tornando o agent-local autossuficiente para todo o ciclo de prospecção.

**Fluxo alvo (tudo no agent-local):**
```
Pesquisar → Assistente IA → Prospectar
```

Esta implementação é o passo central da migração do processo de prospecção para o agent-local.
A funcionalidade espelha `frontend-crm/src/pages/AssistenteIA.tsx`, adaptada para a stack
Python/customtkinter.

---

## Problemas Identificados (estado anterior)

1. **Sem painel "Assistente IA" no agent-local:** `agent-local/app/ui/main_screen.py:67-72` —
   o `nav_items` lista apenas pesquisa, prospectar, historico, conta. Não existe ponto de
   entrada para geração de copy em lote.

2. **`crm_client.py` sem suporte a upload em lote:** `agent-local/app/crm_client.py:123` —
   existe `generate_copy()` para geração individual, mas não há funções para
   `POST /uploads`, `POST /assistente-ia/preview` ou `POST /assistente-ia/processar`.

3. **Fluxo forçado a sair do agent-local:** o utilizador é obrigado a abrir o
   browser + frontend-crm para executar uma etapa intermédia do fluxo de prospecção.

---

## Abordagem

O novo painel "Assistente IA" é inserido entre Pesquisar e Prospectar na sidebar.
Segue o mesmo fluxo de 5 passos do `AssistenteIA.tsx`, adaptado ao customtkinter:

```
Passo 1: Escolher fonte
  ├─ Upload de ficheiro (XLSX/CSV via tkinter.filedialog)
  └─ Usar resultados actuais da Pesquisa (se self._results não for vazio)
         ↓ POST /uploads → upload_id + colunas detectadas

Passo 2: Mapeamento de colunas
  → Dropdowns com auto-detecção (empresa, contato, telefone, notas)
  → Confirmar mapeamento

Passo 3: Prévia
  → POST /assistente-ia/preview
  → Stats: total / criar / actualizar / pular
  → Tabela de amostra (10 linhas) com flags de duplicado

Passo 4: Opções de processamento
  → Criar cards no CRM? (checkbox)
  → Gerar copys com IA? (checkbox)
  → Canais: WhatsApp / Email / Instagram (checkboxes)
  → Tom de voz (entry — pré-preenchido do AI Profile)
  → Idioma (entry — default "pt-PT")
  → Duplicados: pular / actualizar / criar (OptionMenu)

Passo 5: Resultados
  → POST /assistente-ia/processar
  → Estatísticas finais: criados / actualizados / pulados / mensagens geradas
  → Botão "Ver no Prospectar" → switch_panel("prospectar")
```

O backend-crm já tem todos os endpoints necessários — sem alterações no backend.

---

## Plano de Implementação

### Fase 1 — Nav + painel + upload de ficheiro

**Objetivo:** Adicionar o item "Assistente IA" à sidebar e criar o painel com a etapa
de escolha de fonte (upload de ficheiro ou resultados da pesquisa actual).

| Arquivo | O que muda |
|---|---|
| `agent-local/app/ui/main_screen.py` | Adiciona `("assistente-ia", "✨", "Assistente IA")` ao `nav_items`; adiciona `"assistente-ia": self._build_assistente_ia` ao `builders`; implementa `_build_assistente_ia()` com Passo 1 e barra de progresso de upload |
| `agent-local/app/crm_client.py` | Nova função `upload_file(session, path)` → `POST /uploads` via `multipart/form-data`; stubs `preview_assistente_ia()` e `processar_assistente_ia()` |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `2c4bbdd` | Nav item + _build_assistente_ia + upload_file + documento de implementação |

---

### Fase 2 — Mapeamento de colunas + preview

**Objetivo:** Após upload bem-sucedido, mostrar dropdowns de mapeamento e gerar a
prévia de dedupe com stats e tabela de amostra.

| Arquivo | O que muda |
|---|---|
| `agent-local/app/ui/main_screen.py` | Passo 2: frame de mapeamento com `CTkOptionMenu` por campo; Passo 3: frame de preview com cards de stats e tabela de 10 linhas |
| `agent-local/app/crm_client.py` | Nova função `preview_assistente_ia(session, upload_id, overwrite, column_map)` → `POST /assistente-ia/preview` |

### Commits Fase 2 + Fase 3

*(Implementadas em conjunto no mesmo bloco de código)*

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `0693c18` | Passos 2-5 completos: mapeamento, preview, opções, resultados |

---

### Fase 3 — Opções de processamento + resultados

**Objetivo:** Ecrã de opções configuráveis (criar cards, gerar copys, canais, tom,
idioma) e ecrã de resultados com acesso directo ao painel Prospectar.

| Arquivo | O que muda |
|---|---|
| `agent-local/app/ui/main_screen.py` | Passo 4: frame de opções com checkboxes e entries; Passo 5: frame de resultados com stats finais e botão "Ver no Prospectar" |
| `agent-local/app/crm_client.py` | Nova função `processar_assistente_ia(session, upload_id, ...)` → `POST /assistente-ia/processar` |

*(Ver commit `0693c18` acima — implementada em conjunto com a Fase 2)*

---

### Fase 4 — Botão "Gerar copy com IA" no painel Pesquisar

*(ver secção de plano acima para contexto completo)*

### Commits Fase 4

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `769987d` | Botão "✨ Gerar copy com IA" em Pesquisar + `_ir_para_assistente_ia()` + fallback discreto no Assistente IA |

---

### Fase 4 — Plano (documentado anteriormente)

**Objetivo:** Eliminar o passo manual de "perceber que existe o botão no Assistente IA"
— o utilizador vê os resultados da pesquisa e tem um botão directo que o leva ao
Assistente IA com os dados já carregados.

**Problema identificado:** não existe nenhum ponto de entrada visível no painel Pesquisar
que ligue ao Assistente IA. O utilizador tem de navegar manualmente para o painel
Assistente IA e descobrir o botão "Usar pesquisa actual". O fluxo não é óbvio.

**O que muda:**

| Arquivo | O que muda |
|---|---|
| `agent-local/app/ui/main_screen.py` | Em `_show_results()`: adiciona botão `✨ Gerar copy com IA` no header dos resultados, ao lado de "📥 Excel" e "💾 Guardar todos no CRM"; ao clicar chama `self._switch_panel("assistente-ia")` |
| `agent-local/app/ui/main_screen.py` | Em `_build_assistente_ia()`: substitui o botão "🔍 Usar pesquisa actual (N leads)" por texto informativo discreto quando há resultados activos — o ponto de entrada passou a ser o botão em Pesquisar |

**Antes / Depois do fluxo:**

```
ANTES (confuso):
  Pesquisar → (exportar Excel?) → navegar para Assistente IA
  → descobrir botão "Usar pesquisa actual" → clicar

DEPOIS (directo):
  Pesquisar → ver resultados → clicar "✨ Gerar copy com IA"
  → Assistente IA com resultados já prontos
```

---

### Fase 5 — Prévia de mensagens geradas (Assistente IA + Prospectar)

**Objetivo:** Permitir ver e editar as copys geradas sem sair do agent-local — antes,
o utilizador não tinha forma de conferir o texto gerado nem corrigi-lo.

**Problema identificado:** o ecrã de resultados do Assistente IA mostrava apenas
estatísticas (criados/actualizados/mensagens), e os cards do Kanban em Prospectar
não davam acesso ao texto da copy gerada por canal.

**O que muda:**

| Arquivo | O que muda |
|---|---|
| `agent-local/app/crm_client.py` | Novas funções `get_lead_messages(session, lead_id)` → `GET /api/assistente-ia/messages/{lead_id}`; `upsert_lead_message(session, lead_id, channel, body, ...)` → `POST /api/assistente-ia/messages/upsert` |
| `agent-local/app/ui/main_screen.py` | `_ai_build_step5`: usa `result["lead_ids"]` para buscar e mostrar prévia scrollável das mensagens geradas, com botão "Copiar" por mensagem |
| `agent-local/app/ui/main_screen.py` | `_render_kanban_card`: cards tornam-se clicáveis; abre modal `_show_lead_detail` com dados do lead + mensagens por canal, cada uma editável (`CTkTextbox`) com "Copiar" e "Guardar alteração" |

### Commits Fase 5

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `d176fe0` | get_lead_messages + upsert_lead_message + prévia no Passo 5 + modal de detalhe do lead no Kanban |

---

## Fase 5.1 — Fix: "Gerar copys com IA" não activava ao seleccionar canal

### Problema identificado

No primeiro teste da Fase 5 (cenário A8), o utilizador pesquisou leads, foi ao
Assistente IA, marcou o canal "WhatsApp" no Passo 4 e processou — mas a resposta
voltou com `stats.messages = 0` e a prévia correctamente reportou "nenhuma mensagem
encontrada". A prévia funcionava bem; o problema era a configuração enviada ao backend.

Causa raiz: "Gerar copys com IA" e os checkboxes de canal são controlos independentes
no Passo 4 — `_ai_generate_copys_var` por defeito é `False`. O utilizador assumiu que
seleccionar um canal já activava a geração, sem perceber que precisava de marcar
também a checkbox principal.

### Correcção

| Arquivo | Mudança |
|---|---|
| `agent-local/app/ui/main_screen.py` | `_ai_build_step4`: checkboxes de canal passam a chamar `_ai_sync_generate_copys_with_channels`, que liga `_ai_generate_copys_var` automaticamente sempre que qualquer canal é marcado |

### Commits Fix

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `5f8071c` | fix: marcar canal activa automaticamente "Gerar copys com IA" |

---

## Fase 6 — Gerar copys para leads existentes sem copy

### Motivação

Até aqui, o Assistente IA só conseguia gerar copys a partir de uma nova pesquisa
ou da importação de uma planilha — leads já criados anteriormente no Kanban de
Prospectar (sem copy gerada) não podiam ser reaproveitados sem reimportação.
O utilizador pediu uma forma de gerar copys directamente para esses leads
existentes, evitando pesquisa duplicada.

### O que muda

| Arquivo | O que muda |
|---|---|
| `agent-local/app/ui/main_screen.py` | `_build_assistente_ia`: novo botão "🔄 Gerar copys para leads sem copy" no `btn_row`, ao lado de "Escolher ficheiro" |
| `agent-local/app/ui/main_screen.py` | Novo fluxo: `_ai_start_existing_leads_flow` (busca leads do Kanban via `get_leads_kanban` e filtra os que `get_lead_messages` devolve vazio), `_ai_existing_leads_err` (erro), `_ai_build_existing_leads_picker` (checklist de leads + canais + tom de voz), `_ai_toggle_all_existing` (seleccionar/desseleccionar todos), `_ai_generate_copys_for_existing` (loop `generate_copy` + `upsert_lead_message` por lead × canal), `_ai_update_existing_progress`, `_ai_on_existing_generation_done` (stats finais + reaproveita `_ai_load_messages_preview` da Fase 5 para mostrar prévia das copys geradas) |

Sem alterações no backend — reutiliza `get_leads_kanban`, `get_lead_messages`,
`generate_copy` e `upsert_lead_message`, todos já existentes em `crm_client.py`.

### Commits Fase 6

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `7633da8` | Botão + fluxo completo de geração de copys para leads existentes sem copy |

---

## Fase 7 — Prompt de copy ciente do nicho/oferta do utilizador

### Motivação

O utilizador reportou que as copys geradas eram genéricas e desalinhadas com o
negócio de quem prospecta — para leads de clínicas odontológicas, o texto falava
de "marketing digital", "parcerias com descontos" ou "limpeza e manutenção de
equipamentos", e ainda apareciam literalmente os placeholders `[Seu Nome]` /
`[Sua Empresa]` no resultado final.

### Causa raiz

`POST /api/prospeccao/generate-copy` (`backend-crm/routes/prospeccao.py`) — usado
pelo agent-local tanto na geração avulsa como no novo fluxo da Fase 6 — usava um
prompt **estático e genérico**, sem buscar o `ai_profile` do utilizador. O fluxo
de geração em lote (`automations/assistente_ia/llm.py`) já resolvia isto
correctamente, montando um bloco `business_ctx` (Empresa/Nicho/Oferta/Público-alvo)
a partir do `ai_profile` e instruindo a LLM a nunca usar placeholders.

Verificou-se também que não é preciso criar nenhuma tela nova: os campos `niche`,
`offer_description`, `target_audience` e `brand_name` já são configuráveis pelo
utilizador em "Configurar Agente de IA" (`AiProfile.tsx` → Camada Identidade), e
o endpoint `generate-copy` já exige assinatura activa do CRM (`require_crm_access`)
— logo, qualquer utilizador que consiga gerar copy também consegue preencher o
seu perfil de IA, sem qualquer bloqueio adicional para não-assinantes.

### O que muda

| Arquivo | O que muda |
|---|---|
| `backend-crm/routes/prospeccao.py` | `generate_copy`: busca o `ai_profile` via `fetch_core_ai_profile` (com fallback gracioso para `{}` se o perfil não existir/erro de rede); monta `business_ctx` (Empresa remetente / Nicho / Oferta / Público-alvo) e bloco "Remetente" a partir dos campos `brand_name`, `niche`, `offer_description`, `target_audience`, `name`; injecta esse contexto no prompt junto com instruções para a oferta reflectir o nicho real e nunca usar placeholders `[Seu Nome]`/`[Sua Empresa]` |

Sem novas rotas, modelos ou migrações — reaproveita 100% da infra existente
(`fetch_core_ai_profile`, campos do `AIProfile`, padrão `business_ctx` já validado
em `llm.py`). Se o perfil estiver vazio, o prompt cai de volta ao comportamento
genérico anterior, sem erro.

### Commits Fase 7

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `4b97bd3` | generate-copy passa a buscar ai_profile e a injectar contexto de negócio (nicho/oferta/público/marca) + instrução anti-placeholder no prompt |

---

## Fase 8 — Gerador de copy local para não-assinantes (chave OpenAI própria)

### Motivação

A Fase 7 corrigiu o prompt para assinantes (que têm `ai_profile` no core e usam o
`OPENAI_API_KEY` do servidor via `/api/prospeccao/generate-copy`, protegido por
`require_crm_access`). O utilizador pediu que **não-assinantes também consigam
gerar copys com IA**, trazendo a sua própria chave OpenAI e preenchendo um mínimo
de informação de negócio localmente — sem precisar de assinatura/CRM.

### Abordagem

Como `generate-copy` exige assinatura activa, a geração para não-assinantes
acontece **inteiramente no cliente** (chamada directa à OpenAI com a chave do
próprio utilizador), reaproveitando:
- a interface existente do Assistente IA (mesma página, sem painel paralelo)
- o local onde já se configura a chave Google Maps (página "⚙ Conta") para
  também guardar a chave OpenAI
- o padrão `business_ctx` (Empresa/Nicho/Oferta/Público-alvo) e a instrução
  anti-placeholder validados na Fase 7

### O que muda

| Arquivo | O que muda |
|---|---|
| `agent-local/app/ui/main_screen.py` | `_build_conta`: novo cartão "🔑 Chave OpenAI API" (clona o padrão da chave Google Maps — `CTkEntry` mascarado, toggle de visibilidade, "Guardar chave" → `session["openai_api_key"]` + `save_session`); `_build_assistente_ia`: nova secção `_build_free_copy_generator`, mostrada a não-assinantes logo após o cartão de upsell, com indicadores de estado (chave/perfil), formulário de lead avulso, geração assíncrona (thread + `self.after`) e prévia com botão "📋 Copiar" |
| `agent-local/app/ui/business_profile_screen.py` (novo) | `BusinessProfileScreen` — modal `CTkToplevel` com campos mínimos (`niche`, `offer_description`, `target_audience`, `brand_name`), persistidos em `session["local_business_profile"]` via `save_session` |
| `agent-local/app/local_copy.py` (novo) | `generate_copy_local` — chama a OpenAI directamente com a chave do utilizador (`session["openai_api_key"]`), monta o mesmo `business_ctx` e instrução anti-placeholder da Fase 7 a partir de `local_business_profile`, e levanta `LocalCopyError` com mensagens accionáveis se faltar chave ou perfil |
| `agent-local/requirements.txt` | adiciona `openai>=1.0.0` |

Nada disto passa pelo backend-crm — a chamada à LLM acontece localmente, em
paralelo ao padrão já usado por `prospect_dialog.py` para envio "no modo
gratuito, sem registo no CRM". A chave e o perfil ficam guardados em texto
simples em `~/.agent-local/session.json`, mesmo precedente de `google_maps_api_key`.

### Commits Fase 8

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `5cab054` | novo cartão de chave OpenAI em "Conta", `BusinessProfileScreen`, `local_copy.generate_copy_local` e secção "Gerador de copy (modo gratuito)" no painel Assistente IA |

---

## Fase 9 — Pipeline de prospecção (Kanban) local para não-assinantes

### Motivação

O painel "Prospectar" mostrava aos não-assinantes apenas um aviso de upsell +
um histórico simplificado em 2 colunas ("Enviados"/"Falhados", lido de
`prospect_log.jsonl`). O utilizador pediu que a prospecção funcionasse **da
mesma forma que para assinantes** — Kanban completo de 3 colunas ("À
Prospectar"/"Em Andamento"/"Qualificação") — com as excepções já estabelecidas
na Fase 8 (chave OpenAI e perfil de negócio próprios, configurados localmente).

### Abordagem

Análise do Kanban de assinante (`_render_kanban`/`_enqueue_selected_leads`/
`_poll_tick`) revelou que a movimentação entre colunas é **puramente mecânica**,
baseada no resultado real do envio — não em qualificação por IA:
`to-prospect → in-progress` ao enfileirar, depois `in-progress → qualification`
(sucesso) ou `in-progress → to-prospect` (falha). Como o agent-local já envia
mensagens localmente via Selenium/WhatsApp Web para ambos os fluxos
(`whatsapp_client.send_message`) e sabe de imediato se o envio teve sucesso,
um pipeline local pode mirror essa lógica de forma síncrona, sem CRM nem
polling remoto.

### O que muda

| Arquivo | O que muda |
|---|---|
| `agent-local/app/session.py` | novas funções `get_local_leads`/`upsert_local_lead`/`move_local_lead`/`update_local_lead`, mesmo padrão de `get_templates`/`save_template`, persistidas em `session["local_leads"]` com os mesmos nomes de campo do Kanban remoto (`companyName`/`phone`/`category`/`id`/`origin`/`customMessage`); `upsert_local_lead` é idempotente por telefone |
| `agent-local/app/ui/bulk_prospect_dialog.py` | `_run_bulk`: para não-assinantes, após cada envio chama `upsert_local_lead` movendo o lead mecanicamente (`sent → qualification`, `failed → to-prospect`) — espelha `_poll_tick` |
| `agent-local/app/ui/prospect_dialog.py` | `_do_send`: o mesmo registo/movimento mecânico para o envio avulso de não-assinantes |
| `agent-local/app/ui/main_screen.py` | substitui `_build_kanban_non_subscriber` (aviso de upsell + log 2 colunas) por um Kanban local real de 3 colunas: `_render_local_kanban`/`_render_local_kanban_card` (clonam a estrutura visual e a selecção em massa do Kanban remoto — `_kanban_selected`/`_kanban_card_vars`/`_on_kanban_check`/`_toggle_all_kanban` reaproveitados tal como estão) e `_show_local_lead_detail` (modal com mensagem editável, "✨ Gerar copy" via `local_copy.generate_copy_local` da Fase 8, e "📱 Reenviar agora"); novo `_send_selected_local_leads` (equivalente local de `_enqueue_selected_leads` — envio sequencial via Selenium com movimento mecânico); `_build_prospectar` escolhe entre `_enqueue_selected_leads`/`_send_selected_local_leads` consoante `is_subscriber`, e oculta os badges "Agente"/"Pendentes" (que reflectem fila/agente remoto do CRM) para não-assinantes |

Mantém-se `prospect_log`/`get_prospect_log` intacto como histórico bruto de
auditoria — o Kanban local é uma camada adicional, alimentada pelos mesmos
envios. Nada deste fluxo passa pelo backend-crm.

### Commits Fase 9

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `c8346ec` | armazém local de leads (session.py) + registo mecânico nos fluxos de envio existentes (bulk_prospect_dialog/prospect_dialog) |
| 2 | `1d35598` | Kanban local de 3 colunas, modal de detalhe (mensagem editável + copy local + reenvio), envio em massa local e ocultação de badges CRM-only para não-assinantes |

---

## Fase 9.1 — Fix: pausa aleatória entre envios em massa locais

### Problema identificado

Ao validar o envio em massa via "📤 Enfileirar" (Cenário A14), o utilizador
reparou que `_send_selected_local_leads` aguardava apenas 10 segundos fixos
entre cada envio sequencial — intervalo curto e previsível de mais para
WhatsApp Web/Selenium, com risco de o número ser bloqueado por comportamento
automatizado.

### Correcção

| Arquivo | Mudança |
|---|---|
| `agent-local/app/ui/main_screen.py` | `_send_selected_local_leads`: substitui `_time.sleep(10)` por `_time.sleep(_random.uniform(25, 60))` — pausa aleatória entre 25 e 60 segundos a cada envio (excepto o último), reduzindo o padrão previsível de envio |

### Commits Fix

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `67f61e8` | fix: pausa aleatória (25-60s) entre envios em massa locais |

---

## Fase 9.2 — Fix: pausa entre parágrafos enviados ao mesmo número

### Problema identificado

Ao confirmar a Fase 9.1, o utilizador reparou que uma copy com parágrafos
separados por linha em branco chegava ao destinatário como **3 mensagens
distintas** (3 balões com o mesmo timestamp), e perguntou se a pausa de
25-60s também se aplicava aí. Não se aplicava: a causa é que
`composer.send_keys(text)`, em `_type_and_send`
(`agent/whatsapp_runner.py`), envia o texto completo de uma vez — e o
Selenium traduz cada `\n` em tecla **Enter**, que o WhatsApp Web associa a
"enviar mensagem" (Shift+Enter é que insere quebra de linha). Cada parágrafo
acaba por ser disparado como mensagem própria, em rajada, sem qualquer
pausa — um padrão de envio tão ou mais "robótico" que enviar para vários
números em sequência rápida.

### Correcção

| Arquivo | Mudança |
|---|---|
| `agent-local/agent/whatsapp_runner.py` | `_type_and_send` passa a dividir o texto em parágrafos (`_PARAGRAPH_SPLIT_RE` — blocos separados por uma ou mais linhas em branco) e enviar cada um como mensagem própria via novo `_send_single_message` (mesma lógica de digitação/confirmação que existia antes), aguardando uma pausa aleatória `PARAGRAPH_PAUSE_RANGE = (5, 15)` segundos entre parágrafos consecutivos (excepto o último) |

Sem alteração de comportamento para mensagens de um único parágrafo —
continuam a ser enviadas exactamente como antes. Como `_type_and_send` é o
motor partilhado por todos os pontos de envio (avulso, em massa, local e do
CRM), a correcção cobre automaticamente todos os fluxos.

### Commits Fix

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `<pendente>` | fix: pausa aleatória (5-15s) entre parágrafos enviados como mensagens separadas |

---

## Fase 10 — Geração de copies em lote local a partir da Pesquisa

### Motivação

Ao validar o Cenário A14, o utilizador reparou que, na página "Pesquisa", os
assinantes têm dois botões que os não-assinantes não veem — "✨ Gerar copy com
IA" e "💾 Guardar todos no CRM" (`_show_results`, `if subscriber:`) — ambos
dependentes do backend-crm. Pediu uma "praticidade" equivalente, sem consultar
o CRM, com experiência semelhante à do plano pago — fechando o ciclo
"pesquisar → gerar copy → prospectar" de forma 100% local (custo das chamadas
OpenAI corre pela chave própria do utilizador).

### Abordagem

Clonado o padrão de progresso em lote já existente em
`_ai_generate_copys_for_existing` (botão desactivado + label "X/N" actualizado
via `self.after`, thread daemon, resumo final), mas a gerar com
`local_copy.generate_copy_local` (Fase 8) e a persistir directamente no
armazém local (`upsert_local_lead`, Fase 9) — em vez de `generate_copy`/
`upsert_lead_message` do CRM. Cada copy gerada já cria/actualiza o card
correspondente no Kanban local em `category="to-prospect"`, pronto a enviar.

### O que muda

| Arquivo | O que muda |
|---|---|
| `agent-local/app/ui/main_screen.py` | `_show_results`: novo botão "✨ Gerar copies (local)" (mesma posição/cor do equivalente do assinante, visível só para `not subscriber`); novo `_generate_local_copies_for_selected` — valida chave OpenAI/perfil de negócio antes de iniciar (mensagens accionáveis de `LocalCopyError`), processa no máximo `_LOCAL_COPY_BATCH_LIMIT = 15` leads seleccionados sequencialmente numa thread, gera copy com `generate_copy_local` e cria/actualiza o card via `upsert_local_lead` (`category="to-prospect"`, `customMessage=<texto>`), mostra progresso "X/N", resumo final via `_show_enqueue_toast` e recarrega o Kanban local (`_reload_kanban`) se estiver montado |

Sem novas rotas nem chamadas a `crm_client` — tudo local, sem alterar o
comportamento existente para assinantes.

### Commits Fase 10

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `b0ae7e0` | botão "✨ Gerar copies (local)" + `_generate_local_copies_for_selected` |

---

## Fase 11 — Eliminar leads do Kanban local de prospecção

### Motivação

Com a geração de copies em lote (Fase 10) e os fluxos de envio (Fase 9), o
Kanban local "Prospectar" acumula leads sem qualquer forma de remoção — o
utilizador pediu uma opção de eliminar leads individualmente.

### Abordagem

Nova função `delete_local_lead(session, lead_id)` em `session.py`, clonando o
padrão de `move_local_lead`/`update_local_lead` (encontra por `id`, filtra a
lista, persiste com `save_session`). No modal de detalhe do lead
(`_show_local_lead_detail`), novo botão "🗑 Eliminar lead" no `footer` (estilo
do botão de eliminar templates, vermelho `#7F1D1D`/`#991B1B`) que abre um
popup `CTkToplevel` ad-hoc de confirmação ("Eliminar este lead do Kanban
local? Esta acção não pode ser desfeita." + "Cancelar"/"Eliminar"). Ao
confirmar, remove o lead, fecha ambos os popups e recarrega o Kanban local
(`_reload_kanban`).

### O que muda

| Arquivo | O que muda |
|---|---|
| `agent-local/app/session.py` | nova função `delete_local_lead(session, lead_id)` — remove o lead da lista `local_leads` pelo `id` e persiste em `session.json` |
| `agent-local/app/ui/main_screen.py` | `_show_local_lead_detail`: novo botão "🗑 Eliminar lead" no footer + popup de confirmação ad-hoc (`_confirm_delete`); ao confirmar chama `delete_local_lead`, fecha o modal e recarrega o Kanban local via `_reload_kanban` |

Sem novas rotas nem chamadas a `crm_client` — opera apenas em
`session["local_leads"]`; o Kanban de assinante não é afectado.

### Commits Fase 11

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `3033b8c` | `delete_local_lead` + botão "🗑 Eliminar lead" com popup de confirmação |

---

## Checks de Validação

### Cenário A1 — Upload de ficheiro CSV/XLSX funciona

- [ ] Abrir painel "Assistente IA" no agent-local
- [ ] Clicar "Escolher ficheiro" → seleccionar um CSV com colunas de empresa e telefone
- [ ] Confirmar: painel mostra nome do ficheiro + colunas detectadas

### Cenário A2 — Usar resultados da pesquisa actual

- [ ] Fazer uma pesquisa no painel Pesquisar (ex: "dentistas em Lisboa")
- [ ] Navegar para "Assistente IA"
- [ ] Confirmar: aparece o texto "N lead(s) da pesquisa:" com botão "Usar"
      activo no Passo 1 (fallback — o ponto de entrada principal é o botão
      "✨ Gerar copy com IA" em Pesquisar, ver Cenário A7)

### Cenário A3 — Mapeamento de colunas e preview

- [ ] Após upload, confirmar auto-detecção correcta das colunas
- [ ] Confirmar manualmente o mapeamento e clicar "✓ Confirmar mapeamento →"
- [ ] Confirmar: stats de dedupe aparecem (total, criar, actualizar, pular)
- [ ] Confirmar: tabela de amostra mostra as primeiras 10 linhas

### Cenário A4 — Processamento com criação de cards

- [ ] No Passo 2, escolher "Pular" como opção de duplicados; no Passo 4,
      manter "Criar cards no CRM" seleccionado
- [ ] Clicar "🚀 Confirmar e Processar"
- [ ] Confirmar: leads aparecem no painel Prospectar (coluna "À Prospectar")
- [ ] Confirmar: stats finais mostram N criados

### Cenário A5 — Processamento com geração de copy

- [ ] No Passo 4, manter "Criar cards no CRM" seleccionado, marcar "Gerar
      copys com IA" (ou apenas marcar o canal WhatsApp — activa-a automaticamente)
- [ ] Clicar "🚀 Confirmar e Processar" numa planilha de 5 leads
- [ ] Confirmar: no CRM, os leads têm mensagem gerada disponível no diálogo de prospecção

### Cenário A6 — Fluxo completo (Pesquisar → Assistente IA → Prospectar)

- [ ] Pesquisar empresas → ir para Assistente IA → usar resultados actuais
- [ ] Mapear colunas → gerar prévia → processar (criar cards + gerar copys)
- [ ] Clicar "Ver no Prospectar" → confirmar leads na coluna "À Prospectar"
- [ ] Seleccionar leads em massa → enfileirar WhatsApp → confirmar jobs criados

### Cenário A7 — Botão "Gerar copy com IA" no painel Pesquisar (Fase 4)

- [ ] Pesquisar empresas → aguardar resultados aparecerem
- [ ] Confirmar: botão "✨ Gerar copy com IA" aparece no header dos resultados
- [ ] Clicar o botão → confirmar que navega directamente para o painel Assistente IA
- [ ] Confirmar: o painel Assistente IA abre e converte/envia automaticamente
      os resultados da pesquisa (label "N resultados da pesquisa — a
      converter…" + barra de progresso), sem qualquer clique adicional

### Cenário A8 — Prévia de mensagens no Passo 5 (Fase 5)

- [ ] Processar planilha com "Gerar copys com IA" activo
- [ ] No Passo 5 (resultados), confirmar: secção "✨ Mensagens geradas — prévia" aparece
- [ ] Confirmar: lista mostra `Lead #N · Canal` + texto da copy (truncado)
- [ ] Clicar "📋 Copiar" → confirmar que o texto fica na área de transferência

### Cenário A9 — Detalhe do lead com copy editável no Kanban (Fase 5)

- [ ] No painel Prospectar, clicar num card de lead com copy gerada
- [ ] Confirmar: modal abre com nome, telefone, origem e mensagens por canal
- [ ] Editar o texto de uma mensagem → clicar "💾 Guardar alteração"
- [ ] Reabrir o modal → confirmar que o texto editado persiste
- [ ] Clicar "📋 Copiar" numa mensagem → confirmar que o texto fica na área de transferência

### Cenário A10 — Detectar leads sem copy (Fase 6)

- [x] No painel Assistente IA, clicar "🔄 Gerar copys para leads sem copy" — validado em 2026-06-08
- [x] Confirmar: aparece "A procurar leads sem copy gerada…" e depois a lista — validado em 2026-06-08
- [x] Confirmar: apenas leads do Kanban (to-prospect/in-progress/qualification) **sem** mensagens geradas aparecem na lista — validado em 2026-06-08
- [ ] Se todos os leads já têm copy, confirmar mensagem "Todos os leads no Kanban já têm copy gerada. 🎉"

### Cenário A11 — Gerar copys para leads seleccionados (Fase 6)

- [x] Seleccionar/desseleccionar leads individualmente e via "Seleccionar todos" — validado em 2026-06-08
- [x] Escolher canal(is) (WhatsApp/Email/Instagram) e ajustar tom de voz — validado em 2026-06-08
- [x] Clicar "✨ Gerar copys para seleccionados" — validado em 2026-06-08
- [x] Confirmar: progresso "A gerar copys… N/M" actualiza durante o processo — validado em 2026-06-08
- [x] Confirmar: ao concluir, aparecem stats (`X copy(s) gerada(s) para Y lead(s)`) e prévia das mensagens (reaproveitando o componente da Fase 5) — validado em 2026-06-08
- [ ] Abrir um dos leads no Kanban → confirmar que a copy gerada aparece no modal de detalhe

### Cenário A12 — Copy reflecte o nicho/oferta do utilizador (Fase 7)

- [ ] Confirmar que o utilizador tem `Nicho de mercado`, `Produto/Serviço` e
      `Público-alvo` preenchidos em "Configurar Agente de IA" (frontend-crm → AiProfile)
- [ ] Gerar copy para um lead (fluxo normal ou "Gerar copys para leads sem copy")
- [ ] Confirmar: o texto reflecte o nicho/oferta reais do utilizador — não temas
      aleatórios (ex.: "marketing digital", "limpeza de equipamentos") sem relação
      com o que o utilizador realmente vende
- [ ] Confirmar: o texto NÃO contém `[Seu Nome]` / `[Sua Empresa]`
- [ ] Testar também com um utilizador sem perfil de IA preenchido → confirmar que
      a geração não falha (cai para o comportamento genérico anterior)

### Cenário A13 — Gerador de copy local para não-assinantes (Fase 8)

- [x] Com uma conta **gratuita** (sem assinatura activa): abrir "⚙ Conta" →
      confirmar novo campo "🔑 Chave OpenAI API", inserir uma chave válida,
      guardar, reabrir o painel e confirmar que a chave persiste
- [x] Abrir "Assistente IA" → confirmar a nova secção "✨ Gerador de copy (modo
      gratuito)" logo abaixo do cartão "🔒 Disponível para Assinantes", com os
      indicadores "🔑 Chave OpenAI" e "📋 Perfil de negócio" reflectindo o estado real
- [x] Clicar "Preencher informações de negócio" → preencher nicho, oferta,
      público-alvo e marca → guardar → confirmar que o indicador muda para
      "preenchido" e que reabrir o ecrã mostra os valores guardados
- [x] Preencher o formulário do lead avulso (empresa, sector, contacto, canal,
      tom) e clicar "✨ Gerar copy" → confirmar que o texto gerado reflecte o
      nicho/oferta configurados, sem placeholders `[Seu Nome]`/`[Sua Empresa]`,
      e que "📋 Copiar" copia o texto para a área de transferência
- [x] Remover a chave OpenAI e tentar gerar → confirmar mensagem clara pedindo
      para configurar a chave em "⚙ Conta" (sem crash). Repetir limpando o
      perfil de negócio → confirmar mensagem a pedir o preenchimento do perfil
- [x] Confirmar que nada deste fluxo chama o backend-crm (sem erros 403, sem
      necessidade de assinatura/CRM activos)

### Cenário A14 — Kanban de prospecção local para não-assinantes (Fase 9)

- [ ] Com uma conta **gratuita**: ir a "🔍 Pesquisar", seleccionar leads e enviar
      (avulso ou em massa) → confirmar que cada lead aparece no painel
      "Prospectar": sucesso em "Qualificação", falha em "À Prospectar"
- [ ] Confirmar: o aviso de upsell desapareceu e o Kanban mostra as 3 colunas
      ("À Prospectar"/"Em Andamento"/"Qualificação") com contagens correctas
- [x] Em "À Prospectar": seleccionar um lead individualmente (com mensagem
      editada/guardada) e clicar "📤 Enfileirar" sem escrever na barra de
      acções (usa a mensagem guardada) → confirmar que abre o Chrome com
      WhatsApp Web e envia a mensagem em sequência, preservando as quebras
      de linha — validado em 2026-06-08
- [ ] Repetir seleccionando vários leads via "seleccionar todos" e escrevendo
      uma mensagem na barra de acções em massa → confirmar que essa mensagem
      substitui a guardada para os leads enviados
- [ ] Confirmar: indicador de progresso durante o envio sequencial e
      movimento correcto dos cards consoante sucesso/falha ("Qualificação"
      vs "À Prospectar")
- [x] Clicar num card → modal de detalhe → editar a mensagem e clicar
      "💾 Guardar mensagem" → reabrir o card e confirmar que o texto editado
      persiste — validado em 2026-06-08
- [ ] No mesmo modal, gerar copy com IA local ("✨ Gerar copy") → confirmar
      que o texto gerado substitui correctamente a mensagem
- [ ] Reenviar individualmente ("📱 Reenviar agora") → confirmar o movimento
      do card consoante sucesso/falha do envio
- [ ] Confirmar que os badges "● Agente"/"Pendentes" não aparecem no painel
      Prospectar para não-assinantes
- [ ] Confirmar que nada deste fluxo chama o backend-crm (sem 403, sem
      necessidade de assinatura activa)
- [ ] Repetir com uma conta **assinante** → confirmar que o Kanban remoto, o
      polling, os badges e o "Enfileirar" continuam a funcionar como antes

### Cenário A15 — Geração de copies em lote local a partir da Pesquisa (Fase 10)

- [ ] Com uma conta **gratuita** sem chave OpenAI/perfil de negócio configurados:
      pesquisar, seleccionar leads e clicar "✨ Gerar copies (local)" →
      confirmar mensagem accionável imediata (chave/perfil em falta), sem
      disparar chamadas
- [ ] Configurar chave OpenAI + perfil de negócio (Fase 8), seleccionar alguns
      leads (ex.: 5) e clicar "✨ Gerar copies (local)" → confirmar progresso
      "X/N" a actualizar e o botão desactivado durante o processamento
- [ ] No fim: confirmar o resumo (✓ geradas / ⚠ falhas) e que os leads aparecem
      no painel "Prospectar", coluna "À Prospectar", já com a mensagem
      (`customMessage`) preenchida — abrir o card e confirmar que o texto
      reflecte o nicho/oferta do perfil, sem placeholders `[Seu Nome]`/`[Sua Empresa]`
- [ ] Seleccionar mais de 15 leads → confirmar que apenas os primeiros 15 são
      processados e que o resumo indica quantos ficaram de fora
- [ ] Confirmar que nada deste fluxo chama o backend-crm (sem 403, sem
      necessidade de assinatura activa)
- [ ] Repetir com uma conta **assinante** → confirmar que o botão "✨ Gerar
      copy com IA" continua a funcionar como antes (sem alterações)

### Cenário A16 — Eliminar leads do Kanban local de prospecção (Fase 11)

- [ ] Com uma conta **gratuita**: abrir um card no Kanban local "Prospectar" →
      modal de detalhe → clicar "🗑 Eliminar lead" → confirmar que aparece o
      popup de confirmação
- [ ] Clicar "Cancelar" → confirmar que o lead permanece no Kanban e o modal
      continua aberto
- [ ] Clicar "🗑 Eliminar" → confirmar que ambos os popups fecham, o card
      desaparece do Kanban e a contagem da coluna actualiza
- [ ] Mudar de painel e voltar (ou reabrir a app) → confirmar que o lead
      eliminado não reaparece (persistência em `session.json`)
- [ ] Confirmar que nada deste fluxo chama o backend-crm e que o Kanban de
      assinante não é afectado

---

## Ajustes Possíveis Pós-Implementação

- Pré-preenchimento do tom de voz a partir do AI Profile do utilizador
  (`GET /ai-profiles/me` no backend-core) pode ser adicionado numa fase posterior.
- Futuramente: integração directa com os resultados do agent Instagram/Maps
  sem precisar de exportar/importar ficheiro.
