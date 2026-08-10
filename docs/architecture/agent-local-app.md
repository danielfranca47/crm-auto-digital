# Agent-Local — App Desktop de Prospecção

**Versão documentada: v2.** Este doc é o espelho da v2 do agent-local (app
desktop CustomTkinter com auth, Kanban, Assistente IA e copy IA). O
empacotamento `.exe` da própria v2 está pronto para implementar — ver
`docs/implementations/agent-local-v2-empacotamento-exe.md`. Melhorias ainda
não implementadas (v3, incluindo o empacotamento da v3 como última fase) ficam
em `docs/plans/agent-local-melhorias-futuras-V3.md`. Quando a v3 for
implementada e graduada, este doc passa a reflectir v3 e a nota acima é
actualizada — não acumular "v2 vs v3" no corpo do texto, o doc é sempre um
espelho da versão mais recente já graduada.

App desktop standalone (CustomTkinter) para geração e prospecção de leads via
Google Maps + WhatsApp, com integração opcional ao backend-crm/backend-core
para utilizadores assinantes. Distinto do conceito "Agente Local" (worker de
polling de jobs) documentado em [`agents.md`](agents.md#agentes-locais-infrastructure-layer)
— este doc cobre a aplicação gráfica que o utilizador final abre; o worker de
jobs é infraestrutura separada, ainda usada pela automação do Kanban (ver
"Automação do Kanban" abaixo).

---

## Stack e arquivos principais

| Arquivo | Responsabilidade |
|---|---|
| `main.py` | Entry point; fluxo email → OTP/Registo → OTP → sessão |
| `app/auth.py` | `request_access()`, `register_passwordless()`, `verify_otp()`, `refresh_access_token()` |
| `app/session.py` | Persistência local em `~/.agent-local/session.json`; templates; `local_leads`; `local_copy_prompt` |
| `app/crm_client.py` | Cliente HTTP para backend-crm (JWT do utilizador); retry automático em 401 via refresh token |
| `app/maps_client.py` | Google Maps: proxy (assinante) / Places API directa (chave própria) / Selenium (fallback gratuito) |
| `app/whatsapp_client.py` | Wrapper singleton sobre `agent/whatsapp_runner.py`; mantém o Chrome vivo entre envios |
| `agent/whatsapp_runner.py` | Selenium: abre chat, digita, envia, detecta número inválido |
| `app/local_copy.py` | Geração de copy local via OpenAI directa (não-assinante) |
| `app/export.py` | Export `.xlsx` via openpyxl |
| `app/ui/main_screen.py` | Ecrã principal — sidebar + todos os painéis (Pesquisar, Assistente IA, Prospectar, Histórico, Conta) |
| `app/ui/login_screen.py`, `register_screen.py`, `otp_screen.py` | Fluxo de auth passwordless |
| `app/ui/onboarding_screen.py` | Wizard multi-step (3 passos assinante / 4 passos gratuito) |
| `app/ui/settings_screen.py` | Chave Google Maps própria (não-assinante) |
| `app/ui/prospect_dialog.py` | Diálogo de prospecção individual (3 passos) |
| `app/ui/bulk_prospect_dialog.py` | Diálogo de prospecção em lote |
| `app/ui/history_screen.py` | (classe legada, não usada — histórico real é `_build_historico` em `main_screen.py`) |
| `app/ui/business_profile_screen.py` | Modal de perfil de negócio local (não-assinante) |

**Config:** `~/.agent-local/session.json` (sessão, chaves, templates, leads locais, prompt custom). `BACKEND_URL` via `.env`.

---

## Autenticação (passwordless OTP)

Fluxo sem senha, backend-core:

```
Email screen → POST /auth/request-access
  ├─ existing_user → OTP screen
  └─ new_user → Register (nome, whatsapp, setor) → POST /auth/register-passwordless → OTP screen
OTP screen → POST /auth/verify-otp(email, code) → { access_token, refresh_token } → sessão
```

- Reenvio de código com countdown de 60s.
- `access_token` (24h TTL) + `refresh_token` (30d TTL, `type:"refresh"`).
- `crm_client._request()`: em 401, chama `POST /auth/token/refresh` silenciosamente, persiste a nova sessão via `save_session()` e repete o pedido original — sem interacção do utilizador. Sessões antigas sem `refresh_token` recebem 401 normal (login manual necessário uma vez).
- Modo offline: `_check_session` em `main.py` engole exceptions de rede e preserva o `subscription_status` em cache da última sessão válida.

---

## Ecrãs e navegação

Sidebar: Pesquisar · Assistente IA · Prospectar · Histórico · Conta.

Onboarding (primeira sessão, `onboarding_done` em `session.json`):
- Assinante: 3 passos (boas-vindas, como pesquisar, como exportar).
- Gratuito: 4 passos (boas-vindas, modo Selenium, upgrade pitch com link para landing page, como começar).

---

## Pesquisa Google Maps

Três modos, resolvidos por `maps_client.py`:

| Modo | Condição | Mecanismo |
|---|---|---|
| Proxy assinante | `subscription_status=active` | `POST /agent/maps-search` no backend-core — chave `GOOGLE_MAPS_API_KEY` do owner nunca sai do servidor |
| Chave própria | Não-assinante com chave configurada em ⚙ Configurações | Google Places API directa |
| Selenium (fallback) | Não-assinante sem chave | Scraping do Google Maps via Chrome; mais lento (30s–vários minutos conforme limite) e menos fiável |

`POST /agent/maps-search` (`backend-core/app/api/agent_proxy.py`) verifica assinatura **antes** de checar a chave configurada (403 para não-assinante, 503 se a chave do owner não estiver configurada).

Export: botão "📥 Exportar Excel" gera `.xlsx` com linha de título, contagem, cabeçalhos e dados via `openpyxl`.

---

## Prospecção WhatsApp (Selenium)

`whatsapp_client.py` mantém um `WhatsAppRunner` singleton vivo enquanto a app está aberta — o Chrome não reinicia entre envios. Primeiro uso aguarda scan manual do QR Code (até 120s).

### Envio individual (`prospect_dialog.py`)

```
Clica 📱 → formulário (telefone + mensagem, template opcional)
  → send_message() via Selenium
  → Assinante: cria/reutiliza lead via crm_client.create_lead() (dedupe por phone)
              + log_outbound() (prospection_logs, action='manual_outbound')
  → Não-assinante: sem chamada ao backend-crm; regista no Kanban local (ver abaixo)
```

`create_lead()` sempre envia `country_code="BR"`; o telefone deve ser normalizado
com `+` inicial antes de chamar (feito em `_phone_clean`) para não duplicar o
código de país na normalização E.164 do backend (`services/phone_normalizer.py`).

### Envio em lote (`bulk_prospect_dialog.py`)

Loop sequencial com delay configurável (5/10/15/30s) entre leads, checkbox
"Registar no CRM" (assinante), botão cancelar verificado a cada iteração.
Não editável a lista de números antes de enviar.

### Anti-detecção (Selenium)

`agent/whatsapp_runner.py::_type_and_send` divide o texto em parágrafos
(blocos separados por linha em branco — cada `\n` isolado seria interpretado
como Enter = enviar) e envia cada parágrafo como mensagem própria, com pausa
aleatória de 5–15s entre parágrafos (`PARAGRAPH_PAUSE_RANGE`). Entre leads
diferentes em envio em massa, pausa aleatória de 25–60s
(`_send_selected_local_leads`, Kanban local).

### Detecção de número inválido

`_detect_invalid_number` procura a frase "não está no whatsapp"/"is not on
whatsapp" (variantes) no texto visível de toda a página — o WhatsApp Web
sinaliza número inválido via popup modal, não via `[data-testid='alert']`.
Verificação corre logo após o carregamento da página, antes de esperar o
composer.

---

## Kanban de Prospecção (painel "Prospectar")

Duas implementações paralelas conforme `subscription_status`, mesma estrutura visual de 3 colunas (À Prospectar / Em Andamento / Qualificação).

### Assinante — Kanban remoto

Dados via `GET /api/leads` (filtro por categoria) + `PATCH /api/leads/{id}`
(`move_lead_category`). Origem: leads guardados via 💾 na Pesquisa ou criados
pelo Assistente IA aparecem automaticamente em "À Prospectar".

### Automação do Kanban (Fase 10)

Substitui os antigos botões manuais "→ Iniciar"/"→ Qualificar"/"📱" nos
cards por:

- **Checkboxes** por card em "À Prospectar" + "Seleccionar todos" no header da coluna
- **BulkActions inline**: mensagem partilhada (opcional — cai para a última mensagem salva do
  canal escolhido) + selector de canal **WhatsApp/Email** + botão "📤 Enfileirar" →
  `POST /api/prospeccao/whatsapp/enqueue` (cria jobs `whatsapp.send.local`, mesmo job type
  documentado em [`agents.md`](agents.md#job-types-canônicos)) ou `POST /api/prospeccao/email/enqueue`
  (cria jobs `email.send.cold` — ver [`plans-limits.md`](plans-limits.md) para o limite diário) —
  move os leads para "Em Andamento" imediatamente. Sem preferência de canal salva no perfil: a
  escolha é sempre por-lote, feita neste selector. Leads sem email cadastrado são
  automaticamente pulados ao escolher o canal Email (motivo `email_ausente` no resumo); leads
  sem mensagem salva no canal escolhido e sem mensagem digitada no campo opcional também são
  pulados (`sem_mensagem`)
- **Barra de estado**: badge "Agente Online/Offline" (`GET /api/agents/overview`) + contador "Pendentes: N"; não existe badge de conexão WhatsApp Web (ver `docs/plans/agent-local-melhorias-futuras-V3.md`, M8)
- **Polling + refluxo automático**: thread a cada 5–10s consulta `GET /api/prospeccao/whatsapp/recent` e move o lead conforme `jobs.status`: `"completed"` → `qualification`; `"failed"` → `to-prospect` de volta

Os jobs enfileirados por este mecanismo são processados pelo worker "Agente
Local" clássico (ver [`agents.md`](agents.md#agentes-locais-infrastructure-layer)),
não pela própria instância do app desktop — daí o badge "Agente
Online/Offline" poder mostrar offline mesmo com a app aberta.

**Conhecido:** sem guarda contra duplo-clique em "Enfileirar" (cria jobs
duplicados) e feedback de erro atrasado/enganoso por timeout agressivo no
cliente — ver `docs/plans/agent-local-melhorias-futuras-V3.md` (M1, M2).

### Não-assinante — Kanban local

Sem qualquer chamada ao backend-crm. Armazenamento em
`session["local_leads"]` (mesmos nomes de campo do Kanban remoto:
`companyName`/`phone`/`category`/`id`/`origin`/`customMessage`), via
`session.py`: `get_local_leads` / `upsert_local_lead` (idempotente por
telefone — usado ao *criar* leads a partir de resultados de pesquisa) /
`update_local_lead` (match por `id` — usado ao editar um lead já conhecido,
nunca `upsert_local_lead` para isso) / `move_local_lead` / `delete_local_lead`.

Movimentação mecânica após cada envio Selenium (espelha o refluxo remoto):
sucesso → `qualification`; falha → `to-prospect`.

Modal de detalhe do lead (`_show_local_lead_detail`): edição de
`companyName`/`contactName`/`phone`, mensagem editável, "✨ Gerar copy" (via
`local_copy.py`), "📱 Reenviar agora", "🗑 Eliminar lead" (com confirmação).

---

## Conta de Email (SMTP)

Card "📧 Conta de email (prospecção)" no painel "Conta" (`_build_smtp_card` em
`main_screen.py`), logo após o card "A minha conta". Visível para **todos os planos**, incluindo
`crm_free` — usuários gratuitos do agent-local nunca abrem o frontend-crm, então esta é a única
forma de conectarem uma conta de email.

- Campos: host, porta (default `587`), username, senha (toggle 👁 mostrar/ocultar), nome do
  remetente (opcional)
- Botão "?" ao lado do campo de senha abre popup com o passo-a-passo para gerar uma senha de app
  do Gmail (activar verificação em 2 etapas → `myaccount.google.com/apppasswords`) + atalho que
  abre essa página no browser (`webbrowser.open`)
- "Conectar" chama `PUT /users/me/smtp` (backend-core) — testa o login SMTP de verdade antes de
  salvar; erro amigável no card se falhar (nada é persistido)
- Status mostra "✓ Conectado — {username}" ou "Não conectado"; campos (excepto senha) são
  pré-preenchidos ao reabrir se já houver conta conectada (`GET /users/me/smtp/status`)
- "Desconectar" chama `DELETE /users/me/smtp`, limpa os campos do formulário

Ver [`auth-email.md`](auth-email.md#conta-smtp-do-utilizador-cold-outreach-por-email) para os
endpoints, o modelo de dados (colunas em `users`) e a encriptação da senha.

---

## Assistente IA (painel)

Espelha `frontend-crm/src/pages/AssistenteIA.tsx`, fluxo de 5 passos, 100% no agent-local:

```
Passo 1 — Fonte: upload de ficheiro (XLSX/CSV) ou "usar resultados da Pesquisa actual"
  → POST /uploads → upload_id + colunas detectadas
Passo 2 — Mapeamento de colunas (auto-detecção: empresa, contacto, telefone, notas)
Passo 3 — Prévia: POST /assistente-ia/preview → stats (total/criar/actualizar/pular) + amostra de 10 linhas
Passo 4 — Opções: criar cards? gerar copys com IA? canais (WhatsApp/Email/Instagram);
          marcar qualquer canal liga automaticamente "Gerar copys com IA"
          (não cobre o caso do canal já vir pré-marcado sem interacção — M6)
Passo 5 — POST /assistente-ia/processar → stats finais + prévia scrollável das
          mensagens geradas (GET /api/assistente-ia/messages/{lead_id})
```

Pontos de entrada:
- Botão "✨ Gerar copy com IA" no header dos resultados de Pesquisa (assinante) → navega directo para o Assistente IA com os resultados já convertidos e enviados.
- Botão "🔄 Gerar copys para leads sem copy" — busca leads do Kanban remoto sem mensagem gerada. `GET /api/leads` inclui `hasMessages` (via `LEFT JOIN` agregado em `msg_agg`) para filtrar client-side sem N+1 de `GET /api/assistente-ia/messages/{id}` por lead. Guarda `self._ai_existing_flow_running` impede reentrância.

Modal de detalhe do lead no Kanban remoto: mensagens por canal editáveis
(`CTkTextbox`), "Copiar" e "Guardar alteração" via
`POST /api/assistente-ia/messages/upsert`.

---

## Geração de Copy

Dois caminhos, ambos suportam prompt personalizado por variáveis.

### Remota (assinante) — `POST /api/prospeccao/generate-copy`

`backend-crm/routes/prospeccao.py` busca `ai_profile` via
`fetch_core_ai_profile` (fallback gracioso para `{}`) e monta `business_ctx`
(Empresa/Nicho/Oferta/Público-alvo) a partir de
`brand_name`/`niche`/`offer_description`/`target_audience`/`name`. Instrução
anti-placeholder (`[Seu Nome]`/`[Sua Empresa]` nunca literais). Se o
`ai_profile` estiver vazio, cai para o comportamento genérico (sem falhar) —
mas pode produzir gaps gramaticais nesse caso (ver M7 em
`docs/plans/agent-local-melhorias-futuras-V3.md`).

### Local (não-assinante) — `local_copy.py::generate_copy_local`

Chamada directa à OpenAI com `session["openai_api_key"]` do próprio
utilizador. Requer chave configurada e `session["local_business_profile"]`
(niche/offer_description/target_audience/brand_name, editado via
`BusinessProfileScreen`). Mesmo padrão `business_ctx` e instrução
anti-placeholder da geração remota. Nada disto passa pelo backend-crm.

Botão "✨ Gerar copies (local)" na Pesquisa (não-assinante): processa até
`_LOCAL_COPY_BATCH_LIMIT = 15` leads seleccionados sequencialmente, cria/actualiza
cards no Kanban local (`category="to-prospect"`).

### Prompt personalizado (`session["local_copy_prompt"]`)

Configurado em ⚙ Conta (visível a todos os planos), com variáveis
`[empresa]`/`[setor]`/`[contacto]`/`[canal]`/`[tom]`/`[nicho]`/`[oferta]`/`[marca]`.
Quando preenchido, o texto (com variáveis já substituídas pelos dados reais do
lead) é enviado como script de referência — a IA gera uma variação, não copia
literalmente.

Propagado como `custom_prompt_template` em toda a cadeia: `local_copy.py`
(caminho local) e `crm_client.generate_copy()` /
`crm_client.processar_assistente_ia()` → `backend-crm/routes/prospeccao.py` +
`routes/assistente_ia.py` → `automations/assistente_ia/processor.py` →
`automations/assistente_ia/llm.py::generate_for_lead()`. Todos os pontos de
entrada de geração (avulsa, lote, leads existentes) devem passar este campo —
se um novo botão de geração for adicionado, replicar o mesmo parâmetro.

---

## Histórico

Painel inline "Histórico" (`_build_historico` em `main_screen.py` — a classe
`HistoryScreen` existe no código mas não é usada). Duas fontes:
- Assinante: `GET /api/prospeccao/history` (JOIN `prospection_logs` + `leads`)
- Log local JSONL: `session.append_prospect_log`/`get_prospect_log`

Colunas da tabela: Data/Hora, Nome, **Canal** (`Email`/`WhatsApp`, a partir de
`prospection_logs.channel`), **Contacto** (email do destinatário quando `channel="email"`,
telefone caso contrário — `"—"` para entradas antigas sem o dado gravado), Estado
(`Enfileirado`/`Enviado`/`Falhou`, verde/vermelho por acção), Notas. Registos sem `channel`
(log local JSONL, não-assinante) caem no fallback `"—"` sem quebrar.

Cobertura do ciclo de vida do email cold outreach: `queued` é gravado ao enfileirar
(`enqueue_email_jobs`); `sent`/`failed` só depois de o `email_worker`
(`backend-executors`) reportar o resultado via `POST /api/internal/jobs/{id}/complete|fail`
— ver [`agents.md`](agents.md#fluxo-end-to-end-via-backend-executors-ex-email-cold-outreach).
`failed` só é gravado na tentativa definitiva (não em cada retry intermédio).

"Exportar CSV" usa a mesma lista já carregada para a tabela (`self._historico_entries`) — não deve re-buscar dados. Mesmas colunas do painel (incluindo Canal/Contacto).

**Segundo consumidor da mesma rota:** `frontend-crm/src/pages/Pesquisa.tsx` ("Leads do Agente")
mostra a mesma tabela (Data/Hora, Lead, Canal, Contacto, Estado, Notas) com um `Select` extra de
filtro por canal (`?channel=email|whatsapp`, refeito server-side) além do filtro de Estado
existente (Todos/Enviados/Falhados).

---

## Sessão local (`session.json`)

Campos relevantes: `access_token`, `refresh_token`, `subscription_status`,
`onboarding_done`, `google_maps_api_key`, `openai_api_key`,
`local_business_profile`, `local_copy_prompt`, `local_leads` (array),
`templates` (mensagens salvas), `prospect_log` (JSONL de auditoria bruta,
independente do Kanban local).

Guardado em texto simples em `~/.agent-local/session.json` — mesmo
precedente para `google_maps_api_key` e `openai_api_key`.
