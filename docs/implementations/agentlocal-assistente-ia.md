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

---

## Ajustes Possíveis Pós-Implementação

- Para utilizadores não-assinantes: bloquear o painel com mensagem de upsell
  (idêntico ao que já existe no painel Prospectar).
- Pré-preenchimento do tom de voz a partir do AI Profile do utilizador
  (`GET /ai-profiles/me` no backend-core) pode ser adicionado numa fase posterior.
- Futuramente: integração directa com os resultados do agent Instagram/Maps
  sem precisar de exportar/importar ficheiro.
