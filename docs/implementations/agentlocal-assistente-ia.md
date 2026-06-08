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

## Checks de Validação

### Cenário A1 — Upload de ficheiro CSV/XLSX funciona

- [ ] Abrir painel "Assistente IA" no agent-local
- [ ] Clicar "Escolher ficheiro" → seleccionar um CSV com colunas de empresa e telefone
- [ ] Confirmar: painel mostra nome do ficheiro + colunas detectadas

### Cenário A2 — Usar resultados da pesquisa actual

- [ ] Fazer uma pesquisa no painel Pesquisar (ex: "dentistas em Lisboa")
- [ ] Navegar para "Assistente IA"
- [ ] Confirmar: opção "Usar resultados da pesquisa (N leads)" aparece e está activa

### Cenário A3 — Mapeamento de colunas e preview

- [ ] Após upload, confirmar auto-detecção correcta das colunas
- [ ] Confirmar manualmente o mapeamento e clicar "Gerar Prévia"
- [ ] Confirmar: stats de dedupe aparecem (total, criar, actualizar, pular)
- [ ] Confirmar: tabela de amostra mostra as primeiras 10 linhas

### Cenário A4 — Processamento com criação de cards

- [ ] Seleccionar "Criar cards no CRM" + "Pular duplicados"
- [ ] Clicar "Confirmar e Processar"
- [ ] Confirmar: leads aparecem no painel Prospectar (coluna "À Prospectar")
- [ ] Confirmar: stats finais mostram N criados

### Cenário A5 — Processamento com geração de copy

- [ ] Seleccionar "Criar cards no CRM" + "Gerar copys com IA" + canal WhatsApp
- [ ] Processar planilha de 5 leads
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
- [ ] Confirmar: no Assistente IA o texto informativo mostra "N leads da pesquisa prontos"
- [ ] Confirmar: clicar "✨ Gerar copy com IA" no Assistente IA inicia o upload automático sem passo extra

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

---

## Ajustes Possíveis Pós-Implementação

- Para utilizadores não-assinantes: bloquear o painel com mensagem de upsell
  (idêntico ao que já existe no painel Prospectar).
- Pré-preenchimento do tom de voz a partir do AI Profile do utilizador
  (`GET /ai-profiles/me` no backend-core) pode ser adicionado numa fase posterior.
- Futuramente: integração directa com os resultados do agent Instagram/Maps
  sem precisar de exportar/importar ficheiro.
