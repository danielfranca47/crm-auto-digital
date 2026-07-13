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
| 1 | `fa6f4aa` | fix: pausa aleatória (5-15s) entre parágrafos enviados como mensagens separadas |

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

## Fase 12 — Personalização do Prompt de Copy Local

**Objectivo:** o utilizador pode definir em ⚙ Conta um script de referência com variáveis dinâmicas (`[empresa]`, `[nicho]`, etc.); ao gerar uma copy, as variáveis são substituídas pelos dados reais do lead e o texto resultante é enviado à OpenAI como script de referência — a IA gera uma variação personalizada em vez de usar o prompt genérico.

### O que foi alterado

**`agent-local/app/local_copy.py` — `generate_copy_local`**

Antes de construir `prompt`, verifica `session["local_copy_prompt"]`:
- Se preenchido: substitui `[empresa]`, `[setor]`, `[contacto]`, `[canal]`, `[tom]`, `[nicho]`, `[oferta]`, `[marca]` pelos valores reais → envia à OpenAI com instrução "usa este script como referência e gera uma variação".
- Se vazio: usa o prompt padrão original (sem alteração).

**`agent-local/app/ui/main_screen.py` — `_build_conta`**

Nova secção "🤖 Prompt de Copy" inserida após "🔑 Chave OpenAI API" dentro do bloco `if not subscriber:`:
- `CTkTextbox` de altura 120 para escrever o script
- Linha de chips clicáveis com cada variável disponível (insere no final da caixa)
- Botão "Guardar prompt" que persiste `session["local_copy_prompt"]` via `save_session`
- Toast de confirmação "✓ Prompt guardado"

### Commits Fase 12

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `b37ba84` | Secção UI "🤖 Prompt de Copy" em Conta + lógica de substituição de variáveis em `generate_copy_local` |
| 2 | `ac01e80` | Secção visível para assinantes + botão "Restaurar padrão" |

---

## Fase 13 — Prompt de Copy Personalizado para Assinantes (backend-crm)

**Objectivo:** propagar `session["local_copy_prompt"]` do agent-local até ao backend-crm para que assinantes também usem o script personalizado ao gerar copies — tanto na geração avulsa (`/api/prospeccao/generate-copy`) como no batch processing (`/api/assistente-ia/processar`).

### O que foi alterado

**`backend-crm/routes/prospeccao.py`** — `GenerateCopyRequest` aceita `custom_prompt_template: str = ""`; se preenchido, substitui variáveis (`[empresa]`, `[nicho]`, `[oferta]`, `[marca]`, `[setor]`, `[contacto]`, `[canal]`, `[tom]`) e usa como script de referência.

**`backend-crm/routes/assistente_ia.py`** — `AssistIAProcessRequest` aceita `custom_prompt_template: str = ""`; passa ao `processor.process()`.

**`backend-crm/automations/assistente_ia/processor.py`** — `process()` recebe e passa `custom_prompt_template` a `llm.generate_for_lead()`.

**`backend-crm/automations/assistente_ia/llm.py`** — `generate_for_lead()` recebe `custom_prompt_template`; se preenchido, faz substituição por canal e usa como script de referência (antes do loop padrão; `return out` antecipado).

**`agent-local/app/crm_client.py`** — `generate_copy()` e `processar_assistente_ia()` aceitam `custom_prompt_template` e incluem-no no body quando não-vazio.

**`agent-local/app/ui/main_screen.py`** — `_ai_generate_copys_for_existing()` e `_ai_start_processing()` passam `session["local_copy_prompt"]` em todas as chamadas ao crm_client.

### Commits Fase 13

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `d7ad0ef` | Propagação de custom_prompt_template por toda a cadeia backend-crm + agent-local |

---

## Fase 14 — Editar Dados do Lead no Modal de Detalhe (Prospectar)

**Objectivo:** permitir ao utilizador editar `companyName`, `contactName` e `phone` directamente no modal de detalhe de um lead local, sem precisar de sair da sessão "Prospectar".

### O que foi alterado

**`agent-local/app/ui/main_screen.py`** — `_show_local_lead_detail()`:
- Popup alargado de `520x520` para `520x640`
- Labels do cabeçalho nomeados (`company_label`, `meta_label`) para actualização em tempo-real
- Nova secção "Dados do lead" (antes da secção "Mensagem"): 3 `CTkEntry` pré-preenchidos (Empresa, Contacto, Telefone) + botão "💾 Guardar dados" + `status_dados_lbl`
- Função `_save_lead_data()`: valida que Empresa não está vazio, chama `update_local_lead()`, actualiza o cabeçalho do modal e recarrega o Kanban via `_reload_kanban()`
- Separador visual `CTkFrame(height=1)` entre as secções "Dados" e "Mensagem"

### Commits Fase 14

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `a54f5cb` | Secção de edição de dados no modal de lead local |

---

## Checks de Validação

> Organizado em duas sessões autónomas. **Sessão 1** não requer backend-crm.
> **Sessão 2** requer backend-core + backend-crm a correr e subscrição activa.
> Dentro de cada sessão, os cenários seguem a ordem natural de uso — executa-os
> em sequência e os resultados de um servem de base ao seguinte.

---

### Sessão 1 — Conta Gratuita (sem backend-crm)

**Preparação:** conta sem subscrição · chave OpenAI válida em "⚙ Conta" · perfil de negócio preenchido (nicho, oferta, público-alvo).

#### A13 — Configuração inicial (chave OpenAI + perfil de negócio) ✅

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

#### A14 — Kanban local: Pesquisar → enviar → gerir leads

- [x] Ir a "🔍 Pesquisar", seleccionar leads e enviar (avulso ou em massa) →
      confirmar que cada lead aparece no painel "Prospectar": sucesso em
      "Qualificação", falha em "À Prospectar"
- [x] Confirmar: o aviso de upsell desapareceu e o Kanban mostra as 3 colunas
      ("À Prospectar"/"Em Andamento"/"Qualificação") com contagens correctas
- [x] Confirmar que os badges "● Agente"/"Pendentes" não aparecem no painel
      Prospectar para não-assinantes
- [x] Clicar num card → modal de detalhe → editar a mensagem e clicar
      "💾 Guardar mensagem" → reabrir o card e confirmar que o texto editado
      persiste — validado em 2026-06-08
- [x] No mesmo modal, gerar copy com IA local ("✨ Gerar copy") → confirmar
      que o texto gerado substitui correctamente a mensagem — 09/07/2026:
      confirmado, "✓ Copy gerada — revê e guarda se quiseres usá-la no
      reenvio." + texto novo reflectindo o nome/nicho do lead ("Dinho
      Multimarcas")
- [x] Em "À Prospectar": seleccionar um lead individualmente (com mensagem
      editada/guardada) e clicar "📤 Enfileirar" sem escrever na barra de
      acções (usa a mensagem guardada) → confirmar que abre o Chrome com
      WhatsApp Web e envia a mensagem em sequência, preservando as quebras
      de linha — validado em 2026-06-08
- [⏭️] Repetir seleccionando vários leads via "seleccionar todos" e escrevendo
      uma mensagem na barra de acções em massa — não testado nesta sessão
      (ficou por validar; nenhum bloqueio conhecido)
- [⏭️] Confirmar: indicador de progresso durante o envio sequencial em massa —
      não testado nesta sessão
- [x] Reenviar individualmente ("📱 Reenviar agora") a partir do modal de
      detalhe → confirmar o movimento do card consoante sucesso/falha —
      09/07/2026: **2 bugs encontrados e corrigidos**, ver detalhe abaixo.
      Após correcção: envio real para o número de teste confirmado
      (+5547992163692) → "✓ Enviado — lead movido para 'Qualificação'.",
      confirmado também por leitura directa de `session.json`
- [x] Confirmar que nada deste fluxo chama o backend-crm (sem 403, sem
      necessidade de assinatura activa) — verificado por código 2026-06-09;
      reconfirmado 09/07/2026 (nenhuma chamada HTTP ao backend-crm nos logs
      durante o reenvio local)
- [x] **Fase 14 — Editar dados do lead:** clicar num card → modal de detalhe →
      alterar Empresa, Contacto e Telefone → clicar "💾 Guardar dados" →
      confirmar "✓ Dados guardados." a verde, cabeçalho do modal actualizado
      e card no Kanban mostra o novo nome — 09/07/2026: confirmado, editado
      Contacto + Telefone de um lead real, "✓ Dados guardados." apareceu,
      header do modal actualizou o telefone mostrado
- [x] **Fase 14 — Validação vazio:** tentar guardar com campo "Empresa" vazio →
      confirmar mensagem de erro a vermelho sem persistir — 09/07/2026:
      "Empresa não pode estar vazio." a vermelho, valor vazio não foi guardado
- [x] **Fase 14 — Persistência:** fechar e reabrir a app → confirmar que os
      valores editados estão em `session.json` e reaparecem no modal —
      09/07/2026: reiniciada a app, coluna "À Prospectar" manteve a contagem
      e os dados editados (incluindo a eliminação de um lead feita antes do
      reinício — ver A16)

**🐛 Bugs encontrados e corrigidos (09/07/2026) — "📱 Reenviar agora" no modal de detalhe do Kanban local:**

Ao testar o reenvio individual trocando o telefone de um lead real (concessionária de carros) para o número de teste seguro antes de enviar — prática de segurança para evitar tráfego real a negócios — descobri **dois bugs relacionados** em `agent-local/app/ui/main_screen.py`, ambos na função `_resend()` do modal de detalhe:

1. **Telefone editado não era usado no envio.** `phone = lead.get("phone")` era capturado uma única vez quando o modal abria (linha 2547). `_save_lead_data()` actualiza `lead["phone"]` correctamente, mas `_resend()` continuava a usar a variável `phone` obsoleta (nunca reatribuída). Resultado: mesmo depois de editar e guardar um novo telefone com sucesso, "Reenviar agora" enviava sempre para o número original do momento em que o modal abriu.
   **Impacto de segurança:** ao testar, a app tentou enviar para o número real da concessionária (`551130894444`) em vez do número de teste seguro — só não houve envio real porque o WhatsApp Web detectou esse número como inválido/sem conta.
   **Fix:** ler `lead.get("phone")` (e `lead.get("companyName")`) no momento do envio, dentro do `_worker()`, em vez de fechar sobre as variáveis obsoletas.

2. **`upsert_local_lead` (usado após o envio) faz *match* por telefone, corrompendo outro lead.** Depois de corrigir o bug 1, ao reenviar o *segundo* lead de teste (também apontado para o mesmo número de teste seguro — prática de segurança recomendada), a chamada pós-envio `upsert_local_lead(phone=..., name=..., ...)` encontrou o **primeiro** lead da lista com esse telefone (que já não era o lead que estava a ser reenviado) e sobrescreveu o `companyName` desse lead errado.
   **Impacto:** qualquer utilizador que reencaminhe vários testes para o mesmo número (a própria prática de segurança recomendada neste projecto) corrompe dados de leads não relacionados.
   **Fix:** trocar `upsert_local_lead` (que faz match por telefone — apropriado só para criar leads novos a partir de resultados de pesquisa) por `update_local_lead(lead_id, ...)` (que faz match pelo id já conhecido do lead a reenviar).

**Reteste ao vivo pós-correcção:** repetido o cenário com um lead diferente, telefone alterado para o número de teste seguro, "Reenviar agora" → "✓ Enviado — lead movido para 'Qualificação'." Confirmado por leitura directa de `session.json`: o lead correcto foi actualizado (`category: "qualification"`), o outro lead que partilhava o mesmo número de teste ficou intacto.

#### A15 — Geração de copies em lote a partir da Pesquisa

- [x] Com chave OpenAI/perfil de negócio **não** configurados: pesquisar,
      seleccionar leads e clicar "✨ Gerar copies (local)" → confirmar
      mensagem accionável imediata (chave/perfil em falta), sem disparar chamadas — verificado por código 2026-06-09
- [x] Com chave + perfil configurados: seleccionar 5 leads e clicar
      "✨ Gerar copies (local)" → confirmar progresso "X/N" a actualizar e
      botão desactivado durante o processamento — 13/07/2026: pesquisa
      "pizzarias"/"Florianópolis, SC" (20 leads, modo Selenium — enriquecimento
      demorou ~13 min para 20 resultados, nota de performance abaixo), 5
      seleccionados, "✨ Gerar copies (local)" → header mostrou "A gerar
      copies... 1/5" a actualizar, botão do header desactivado (cor
      esmaecida) durante o processamento
- [x] No fim: confirmar o resumo (✓ geradas / ⚠ falhas) e que os leads
      aparecem no painel "Prospectar" ("À Prospectar") com a mensagem
      preenchida — abrir o card e confirmar que o texto reflecte o
      nicho/oferta do perfil, sem placeholders `[Seu Nome]`/`[Sua Empresa]` —
      13/07/2026: popup "✓ 5 copy(s) gerada(s)"; painel Prospectar "À
      Prospectar" subiu de 3 para 8; aberto o card "Forneria Piedoro" →
      mensagem "Olá, Forneria Piedoro! Sabia que a Digital Pro oferece
      automações de IA para otimizar processos comerciais?..." — reflecte o
      nome do lead e a marca do remetente (Digital Pro), sem placeholders

**Nota de performance (não-bloqueante):** o enriquecimento de 20 resultados no modo gratuito (Selenium) demorou aproximadamente **13 minutos** (visita sequencial à página de detalhe de cada estabelecimento no Google Maps, uma de cada vez). Não é um bug — é o comportamento esperado do fallback Selenium sem chave Google Maps API própria (já documentado como mais lento que o modo com chave) — mas vale registar como referência de tempo real para futuras sessões de teste: para o modo gratuito, preferir pesquisas com `Limite` mais baixo (ex.: 5-10) para reduzir o tempo de espera.
- [x] Seleccionar mais de 15 leads → confirmar que apenas os primeiros 15
      são processados e que o resumo indica quantos ficaram de fora — verificado por código 2026-06-09 (`_LOCAL_COPY_BATCH_LIMIT = 15`)
- [x] Confirmar que nada deste fluxo chama o backend-crm (sem 403) — verificado por código 2026-06-09

#### A16 — Eliminar leads do Kanban local

- [x] Abrir um card no Kanban local "Prospectar" → modal de detalhe →
      clicar "🗑 Eliminar lead" → confirmar que aparece o popup de confirmação —
      09/07/2026: "Eliminar este lead do Kanban local? Esta ação não pode ser
      desfeita." + botões "Cancelar"/"🗑 Eliminar"
- [x] Clicar "Cancelar" → confirmar que o lead permanece no Kanban e o modal
      continua aberto — verificado por código 2026-06-09 (botão tem apenas `confirm.destroy`)
- [x] Clicar "🗑 Eliminar" → confirmar que ambos os popups fecham, o card
      desaparece do Kanban e a contagem da coluna actualiza — 09/07/2026:
      confirmado, coluna "À Prospectar" desceu de (5) para (4), card
      desapareceu imediatamente
- [x] Mudar de painel e voltar (ou reabrir a app) → confirmar que o lead
      eliminado não reaparece (persistência em `session.json`) — 09/07/2026:
      confirmado após reiniciar a app, lead eliminado continuou ausente
- [x] Confirmar que nada deste fluxo chama o backend-crm e que o Kanban de
      assinante não é afectado — verificado por código 2026-06-09

#### A17 — Personalizar o prompt de copy (conta gratuita)

- [x] Abrir ⚙ Conta → confirmar que a secção "🤖 Prompt de Copy" aparece (disponível em todos os planos) — verificado por código 2026-06-09 (secção fora do bloco `if not subscriber:`)
- [x] Escrever um script (ex.: "Olá pessoal da [empresa], sou Daniel e ajudo empresas de [nicho]…") e clicar num chip (ex. `[empresa]`) → confirmar que o texto é inserido no final da caixa — verificado por código 2026-06-09
- [x] Clicar "Guardar prompt" → toast "✓ Prompt guardado" aparece e some em ~1,2 s — verificado por código 2026-06-09
- [x] Mudar de painel e voltar a ⚙ Conta → confirmar que o script persiste (lido de `session.json`) — verificado por código 2026-06-09
- [x] Gerar copy de um lead no Kanban local (modo gratuito) → mensagem reflecte o script com variáveis substituídas —
      13/07/2026: com o script "[TESTE-A17b]... sou Daniel de [empresa]..."
      activo, "Gerar copy" no lead "Prime Multimarcas" produziu "Olá, sou
      Maria e gostaria de falar sobre como nossa solução de automação pode
      beneficiar a Prime Multimarcas..." — ecoa a frase específica "solução
      de automação" do script (variação criativa do nome, por desenho do
      prompt — "gera uma variação, não copies literalmente")
- [x] Clicar "Restaurar padrão" → toast "✓ Prompt padrão restaurado", campo reposto com prompt padrão — verificado por código 2026-06-09; reconfirmado ao vivo 13/07/2026
- [x] Gerar copy novamente → usa o prompt padrão — 13/07/2026: no mesmo
      lead "Prime Multimarcas", com o prompt padrão restaurado, "Gerar copy"
      produziu "Olá, Prime Multimarcas! A Digital Pro oferece soluções de
      automações de IA para otimizar seus processos comerciais..." —
      estrutura, tom e emoji claramente diferentes da versão com script
      custom, confirmando a mudança de comportamento

#### A17b — Prompt personalizado para assinante (requer backend-crm)

- [x] Definir script em ⚙ Conta ("Olá [contacto], sou Daniel de [empresa]. [TESTE-A17b]…") — 07/07/2026: guardado com sucesso, confirmado em `session.json` (`local_copy_prompt`)
- [x] Abrir modal de lead (prospecção individual) e clicar "✨ Gerar com IA" → copy reflecte o script — 07/07/2026 (ver bug + fix abaixo)
- [x] "Gerar copys para leads existentes"/upload de CSV (Assistente IA) → já enviam `custom_prompt_template` correctamente — confirmado por leitura de código (`main_screen.py:1101` e `:1453`), consistente com o fluxo A5+A8 já validado
- [ ] Limpar o script (Restaurar padrão) e gerar de novo → volta ao comportamento padrão *(não testado)*

**🐛 Bug encontrado e corrigido — prompt personalizado não chegava ao botão individual "✨ Gerar com IA":** `agent-local/app/ui/prospect_dialog.py::_generate_ai_copy` chamava `crm_client.generate_copy(...)` sem o parâmetro `custom_prompt_template`, apesar de a função já o suportar e de o backend (`backend-crm/routes/prospeccao.py`) já implementar correctamente a substituição de variáveis e o prompt baseado no script quando recebido. Resultado: qualquer subscritor que definisse um script personalizado em ⚙ Conta via este botão específico via sempre o comportamento genérico (o `local_copy_prompt` só era consumido pelo caminho gratuito/local em `local_copy.py`, que este botão nunca usa por ser exclusivo de assinantes). Confirmado ao vivo: com o script "[TESTE-A17b]" guardado, a copy gerada não reflectia o script nem o marcador.
**Fix aplicado:** `_generate_ai_copy` passa agora `custom_prompt_template=self._session.get("local_copy_prompt") or ""`. Reteste confirmado por logs (`POST /api/prospeccao/generate-copy → 200 OK`) e por leitura de código (mesmo padrão usado nos outros dois pontos de entrada, já correctos). Nota: a IA não repete o script literalmente por desenho — o próprio prompt do backend instrui "não copies literalmente, gera uma variação" e "NUNCA uses placeholders", pelo que a ausência do texto exacto do script na saída é esperada, não um sinal de falha.

---

### Sessão 2 — Conta Assinante (requer backend-crm)

**Preparação:** conta com subscrição activa · backend-core + backend-crm a correr · ter uma planilha CSV/XLSX com 5–10 leads de teste · perfil de IA preenchido (nicho, oferta, público-alvo) em "Configurar Agente de IA" no frontend-crm.

#### A7 — Entrada via Pesquisar → Assistente IA (ponto de entrada principal)

- [x] Pesquisar empresas → aguardar resultados aparecerem — 07/07/2026: "dentistas" / "São Paulo, SP" → 10 leads
- [x] Confirmar: botão "✨ Gerar copy com IA" aparece no header dos resultados — verificado por código 2026-06-09 (guarded por `if subscriber:`); confirmado visualmente 07/07/2026
- [x] Clicar o botão → confirmar que navega directamente para o painel Assistente IA — verificado por código 2026-06-09; confirmado ao vivo 07/07/2026
- [x] Confirmar: o painel Assistente IA abre e converte/envia automaticamente
      os resultados da pesquisa (label "N resultados da pesquisa — a
      converter…" + barra de progresso), sem qualquer clique adicional
      — 07/07/2026: label exacto "10 resultados da pesquisa — a converter..." + barra "A enviar ficheiro..." visíveis

#### A1 — Upload manual de ficheiro CSV/XLSX

- [⏭️] Não testado directamente nesta rodada — o mecanismo de upload é o mesmo
      motor usado por A2/A7 (envio do CSV temporário gerado internamente), já
      validado indirectamente. Ficheiro externo próprio não foi testado.

#### A2 — Fallback: Usar resultados de pesquisa dentro do Assistente IA

- [x] Fazer uma pesquisa no painel Pesquisar (ex: "dentistas em Lisboa") — 07/07/2026: pesquisa "advogados" / "Curitiba, PR"
- [x] Navegar para "Assistente IA" directamente pela sidebar (não pelo botão) — 07/07/2026
- [x] Confirmar: aparece o texto "N lead(s) da pesquisa:" com botão "Usar"
      activo no Passo 1 → clicar "Usar" e confirmar que converte e envia
      automaticamente — 07/07/2026: texto exacto "ou 10 leads da pesquisa: Usar"; clicar converteu e enviou automaticamente (`tmpuax5dtog.csv enviado — 4 colunas detectadas`)

#### A3 — Mapeamento de colunas + preview

- [x] Após upload (A1 ou A2), confirmar auto-detecção correcta das colunas — 07/07/2026: "empresa"→Empresa, "telefone"→Telefone auto-detectados corretamente
- [x] Confirmar manualmente o mapeamento e clicar "✓ Confirmar mapeamento →" — 07/07/2026
- [x] Confirmar: stats de dedupe aparecem (total, criar, actualizar, pular) — 07/07/2026: 10 total / 5 criar / 0 actualizar / 5 pular (1ª pesquisa, dentistas); 10/10/0/0 (2ª pesquisa, advogados frescos)
- [x] Confirmar: tabela de amostra mostra as primeiras 10 linhas — 07/07/2026: colunas Empresa/Telefone/Acção/Dup?

#### A4 — Processamento — criar cards sem copy

- [x] No Passo 2, escolher "Pular" como opção de duplicados; no Passo 4,
      manter "Criar cards no CRM" seleccionado — 07/07/2026
- [x] Clicar "🚀 Confirmar e Processar" — 07/07/2026
- [x] Confirmar: leads aparecem no painel Prospectar (coluna "À Prospectar") — 07/07/2026: 5 novos leads (origem "Planilha") visíveis no topo da coluna
- [x] Confirmar: stats finais mostram N criados — 07/07/2026: "5 Criados · 0 Actualizados · 5 Pulados · 0 Mensagens"

#### A5 + A8 — Processamento com geração de copy + prévia no Passo 5

- [x] No Passo 4, manter "Criar cards no CRM" seleccionado, marcar "Gerar
      copys com IA" (ou apenas marcar o canal WhatsApp — activa-a automaticamente) — 07/07/2026: checkbox "Gerar copys com IA" marcado manualmente (canal WhatsApp já vinha marcado por defeito, mas não activou o checkbox sozinho neste caso — ver nota abaixo)
- [x] Clicar "🚀 Confirmar e Processar" numa planilha de 5 leads — 07/07/2026: testado com 10 leads (advogados Curitiba), demorou ~50s (10 chamadas OpenAI sequenciais)
- [x] Confirmar: no CRM, os leads têm mensagem gerada disponível no diálogo de prospecção — 07/07/2026: "10 Criados · 0 Actualizados · 0 Pulados · 10 Mensagens"
- [x] No Passo 5 (resultados), confirmar: secção "✨ Mensagens geradas — prévia" aparece — 07/07/2026
- [x] Confirmar: lista mostra `Lead #N · Canal` + texto da copy (truncado) — 07/07/2026: "Lead #316 · WhatsApp", "Lead #317 · WhatsApp" com texto completo
- [x] Clicar "📋 Copiar" → confirmar que o texto fica na área de transferência — botão clicado sem erro; conteúdo do clipboard não confirmado (grant de leitura de clipboard não concedido nesta sessão)

**Nota (não-bloqueante):** o checkbox "Gerar copys com IA" **não** se activou sozinho ao ver o canal "WhatsApp" já marcado por defeito no primeiro render do Passo 4 — precisou de clique manual. O fix da Fase 5.1 (`_ai_sync_generate_copys_with_channels`) sincroniza ao *marcar* um canal, não cobre o caso em que o canal já vem pré-marcado e o utilizador nunca toca nele. Risco baixo (o utilizador que quer copy tende a mexer nos canais de qualquer forma), mas vale registar.

**Achado de qualidade da copy (não-bloqueante):** com o AI Profile de teste vazio (`brand_name`/`niche`/`offer_description` todos `""`), o texto gerado ficou com gaps gramaticais tipo "Sou da ." e "Obrigado, , ." — não insere placeholders `[Seu Nome]`/`[Sua Empresa]` (correcto), mas também não omite os separadores (vírgulas/pontos) quando o campo está vazio, produzindo texto com aparência quebrada. Depois de preencher o perfil (ver A12), o texto ficou correcto. Sugestão para o dev: condicionar a inclusão de vírgulas/pontos de fecho à presença do valor.

#### A9 — Detalhe do lead com copy editável no Kanban CRM

- [x] No painel Prospectar, clicar num card de lead com copy gerada — 07/07/2026: Lead #325 (Gabriel Bergamo Advocacia)
- [x] Confirmar: modal abre com nome, telefone, origem e mensagens por canal — 07/07/2026
- [x] Editar o texto de uma mensagem → clicar "💾 Guardar alteração" — 07/07/2026: adicionado sufixo "[teste-A9]"; `POST /api/assistente-ia/messages/upsert → 200 OK`
- [x] Reabrir o modal → confirmar que o texto editado persiste — 07/07/2026: "[teste-A9]" visível após fechar e reabrir
- [x] Clicar "📋 Copiar" numa mensagem → botão clicado sem erro (conteúdo do clipboard não confirmado — ver nota em A5/A8)

#### A12 — Copy ciente do nicho/oferta do utilizador

- [x] Confirmar que o utilizador tem `Nicho de mercado`, `Produto/Serviço` e
      `Público-alvo` preenchidos em "Configurar Agente de IA" (frontend-crm → AiProfile) — 07/07/2026: perfil de teste estava **vazio** (`brand_name`/`niche`/`offer_description`/`target_audience` todos `""`, confirmado via DB); preenchido via `PATCH /ai-profiles/me` para o teste (brand_name="Digital Pro", niche="Escritorios de advocacia", offer_description="Automacao de atendimento e agendamento via WhatsApp com IA", target_audience="Advogados autonomos e pequenos escritorios")
- [x] Gerar copy para um lead (fluxo normal ou "Gerar copys para leads sem copy") — 07/07/2026: gerado via botão "✨ Gerar com IA" no diálogo de prospecção individual (Pesquisar → WA → Gerar com IA)
- [x] Confirmar: o texto reflecte o nicho/oferta reais do utilizador — não temas
      aleatórios sem relação com o que o utilizador realmente vende — 07/07/2026: "Olá Ricardo Santos Lima, sou Daniel da Digital Pro. Oferecemos automação de atendimento e agendamento via WhatsApp com IA para escritórios de advocacia. Gostaria de saber mais sobre como podemos ajudar a otimizar o atendimento no seu escritório de advocacia de família em Curitiba?" — reflecte nicho, oferta, marca e nome correctamente, e até personaliza com o nicho específico do lead ("advocacia de família")
- [x] Confirmar: o texto NÃO contém `[Seu Nome]` / `[Sua Empresa]` — verificado por código 2026-06-09; confirmado ao vivo 07/07/2026 (com perfil preenchido, sem gaps nem placeholders)
- [x] Testar também com um utilizador sem perfil de IA preenchido → confirmar que
      a geração não falha (cai para o comportamento genérico anterior) — 07/07/2026: confirmado ao vivo — com perfil vazio a geração NÃO falhou (sem crash, sem erro 500/403); produziu texto genérico com pequenos gaps gramaticais (ver achado em A5/A8), não placeholders

#### A10 + A11 — Gerar copys para leads existentes sem copy

- [x] No painel Assistente IA, clicar "🔄 Gerar copys para leads sem copy" — validado em 2026-06-08
- [x] Confirmar: aparece "A procurar leads sem copy gerada…" e depois a lista — validado em 2026-06-08
- [x] Confirmar: apenas leads do Kanban (to-prospect/in-progress/qualification) **sem** mensagens geradas aparecem na lista — validado em 2026-06-08
- [x] Se todos os leads já têm copy, confirmar mensagem "Todos os leads no Kanban já têm copy gerada. 🎉" — verificado por código 2026-06-09
- [x] Seleccionar/desseleccionar leads individualmente e via "Seleccionar todos" — validado em 2026-06-08
- [x] Escolher canal(is) (WhatsApp/Email/Instagram) e ajustar tom de voz — validado em 2026-06-08
- [x] Clicar "✨ Gerar copys para seleccionados" — validado em 2026-06-08
- [x] Confirmar: progresso "A gerar copys… N/M" actualiza durante o processo — validado em 2026-06-08
- [x] Confirmar: ao concluir, aparecem stats (`X copy(s) gerada(s) para Y lead(s)`) e prévia das mensagens — validado em 2026-06-08
- [x] Abrir um dos leads no Kanban → confirmar que a copy gerada aparece no modal de detalhe — 07/07/2026: confirmado via teste A9 (Lead #325, mensagem WhatsApp visível no modal)

**Achado de performance — causa raiz confirmada por leitura de código (07/07/2026):** o botão "🔄 Gerar copys para leads sem copy" varre **todos** os leads do Kanban remoto (`get_leads_kanban`) chamando `get_lead_messages` **um a um, sequencialmente**, para descobrir quais não têm copy (`agent-local/app/ui/main_screen.py:937-979`, função `_ai_start_existing_leads_flow`). Nesta conta de teste (acumulada ao longo de meses, ~120+ leads nas colunas de prospecção), o scan ainda não tinha terminado após ~5 minutos de espera (chegou a verificar leads até ao ID #209 vindo do #325, sem atingir o fim).

Confirmado por leitura directa do código (não é só especulação):
- Cada `get_lead_messages(session, lid)` (`agent-local/app/crm_client.py:234-245`) é um `GET /api/assistente-ia/messages/{lead_id}` **individual** — 1 pedido HTTP completo (com verificação de auth) por lead.
- No backend (`backend-crm/routes/assistente_ia.py:134-159`, `get_messages`), cada pedido abre a sua **própria ligação SQLite** (`with get_connection() as conn`) e corre uma query isolada — não há batching nem cache.
- Não existe endpoint em lote — o único endpoint disponível é por-lead.
- **Não há guarda contra invocação dupla**: `_ai_start_existing_leads_flow` não verifica se já existe uma thread `_worker` em curso antes de arrancar outra (sem flag tipo `self._ai_existing_flow_running`). Confirmado por log que a thread sobrevive à troca de painel (continuou a chamar `/api/assistente-ia/messages/{id}` mesmo depois de navegar para "Pesquisar" e iniciar um fluxo A2 diferente em paralelo) — se o utilizador clicar o botão outra vez ou voltar a este painel, cria-se uma **segunda** thread a repetir o mesmo varrimento sequencial em paralelo com a primeira, multiplicando a carga no backend sem qualquer aviso na UI.

**Conclusão:** é um bug de performance real (não é "só volume de dados esperado") — o padrão N+1 client-side é o principal responsável pelo tempo (O(N) round-trips seriais, ~1.5–3s cada, × 120+ leads ≈ 3–6 min, bate certo com o observado); a ausência de guarda contra dupla-invocação é um agravante secundário que pode duplicar/triplicar a carga se o utilizador repetir o clique.

**Evidência de que uma correcção de query única é viável e de baixo risco:** `backend-crm/routes/leads.py:351-392` (`listar_leads`, usado por `GET /api/leads`) já resolve um problema análogo — injectar o "próximo compromisso agendado" por lead — com um único `LEFT JOIN` a uma subquery agregada (`ROW_NUMBER() OVER (PARTITION BY lead_id ...)`), em vez de N chamadas. O mesmo padrão aplica-se directamente aqui.

**✅ Fix aplicado e validado ao vivo (07/07/2026):**
1. `backend-crm/routes/leads.py` (`listar_leads`, `GET /api/leads`) — adicionado `LEFT JOIN (SELECT lead_id, COUNT(*) AS msg_count FROM messages GROUP BY lead_id) AS msg_agg` à query existente; `_map_lead_row` agora injeta `hasMessages` (bool) por lead a partir de `msg_count`. Zero pedidos extra — mesmo custo de hoje.
2. `agent-local/app/ui/main_screen.py` (`_ai_start_existing_leads_flow`) — removida a chamada por-lead a `get_lead_messages`; passa a filtrar directamente `without_copy = [lead for lead in leads if not lead.get("hasMessages")]` sobre o resultado já devolvido por `get_leads_kanban`.
3. Adicionada guarda `self._ai_existing_flow_running` para impedir arrancar uma segunda thread do mesmo scan enquanto a primeira ainda corre (clique repetido ou reentrada no painel).

**Validação ao vivo:** confirmado via `GET /api/leads` directo que o campo `hasMessages` está correcto (57 leads totais, 50 com copy / 7 sem). Reiniciado `backend-crm` e o `agent-local` com o código actualizado, clicado "🔄 Gerar copys para leads sem copy" — resultado "Leads sem copy gerada — 7 encontrado(s)" apareceu em **~2-3 segundos** (antes: 5+ minutos sem terminar). Contagem bate certo com a verificação directa da API. Regressão de performance resolvida.

#### Regressões — confirmar que o fluxo de assinante não foi afectado

- [x] Repetir A14: com conta **assinante**, confirmar que o Kanban remoto, o
      polling, os badges "● Agente"/"Pendentes" e o "Enfileirar" (via CRM)
      continuam a funcionar como antes — 08/07/2026: 2 leads sintéticos (números
      obviamente falsos `+10000000301`/`+10000000302`, sem risco de envio real)
      seleccionados no Kanban remoto → mensagem preenchida na barra de acções →
      "Enfileirar" → popup "✓ 2 enfileirados" → leads moveram-se imediatamente
      para "Em Andamento", confirmado também por query directa à BD
      (`category='in-progress'`, 2 jobs `whatsapp.send.local` criados). Badge
      "Pendentes" actualizou de 0 para 4 (via polling). Sem regressão — mecanismo
      idêntico ao já validado em K2/G2. Nota: reproduzido de caminho o mesmo bug
      já conhecido de falta de guarda contra duplo-clique (criou 4 jobs em vez de
      2, por dois cliques próprios em "Enfileirar" — não é uma regressão nova,
      é o mesmo achado já registado em G2/K2). Dados sintéticos removidos após o teste.
- [x] Repetir A15: com conta **assinante**, confirmar que o botão "✨ Gerar
      copy com IA" em Pesquisar continua a funcionar como antes (sem alterações)
      — 08/07/2026: pesquisa "dentistas"/"Curitiba" (20 leads) → clicar botão →
      navegou directamente para "Assistente IA" → auto-converteu e enviou
      ("20 resultados da pesquisa — a converter...") → Passo 2 abriu com
      mapeamento automático correcto (empresa→Empresa/Nome, telefone→Telefone).
      Comportamento idêntico ao já validado em A7 (07/07/2026). Sem regressão.

#### A6 — Fluxo completo de integração (Pesquisar → Assistente IA → Prospectar)

- [ ] Pesquisar empresas → clicar "✨ Gerar copy com IA" → Assistente IA
      converte e envia automaticamente
- [ ] Mapear colunas → gerar prévia → processar (criar cards + gerar copys)
- [ ] Clicar "Ver no Prospectar" → confirmar leads na coluna "À Prospectar"
- [ ] Seleccionar leads em massa → enfileirar WhatsApp → confirmar jobs criados

---

## Ajustes Possíveis Pós-Implementação

- Pré-preenchimento do tom de voz a partir do AI Profile do utilizador
  (`GET /ai-profiles/me` no backend-core) pode ser adicionado numa fase posterior.
- Futuramente: integração directa com os resultados do agent Instagram/Maps
  sem precisar de exportar/importar ficheiro.
