# agent-local v2 — App Standalone de Geração de Leads

**Branch:** `etapa-9-planos-limites`
**Status:** Fase 6 concluída — aguarda validação (F1–F8); Fase 4 (empacotamento .exe) pendente

---

## Motivação

O agent-local era um worker CLI que fazia polling do backend-CRM para executar automações Selenium. O objetivo é transformá-lo num app desktop standalone para geração de leads via Google Maps, com UI gráfica, auth de utilizador, controlo de acesso (assinante vs não-assinante), export Excel e onboarding educativo, empacotado como .exe via PyInstaller.

Comportamento desejado: utilizador clica no .exe → vê ecrã de login/registo → pesquisa leads por nicho e cidade → exporta Excel para a sua máquina.

---

## Problemas Identificados (estado anterior)

1. **Sem UI**: app era CLI puro — sem interface para utilizadores finais
2. **Sem auth**: nenhum sistema de identificação de utilizador
3. **Sem controlo de acesso**: sem distinção assinante vs não-assinante
4. **Sem export Excel**: resultados só eram retornados como JSON para o backend-CRM
5. **Arquitetura worker-only**: dependia do backend-CRM estar online para funcionar
6. **Chave API não segura**: não havia mecanismo para usar a chave do owner sem a expor no exe

---

## Abordagem

```
App abre
  └─ Existe session.json válido?
       ├─ Sim → verifica entitlements → ecrã principal
       └─ Não → ecrã de login/registo

Ecrã principal
  └─ Preenche nicho + cidade + limite → Pesquisar
       ├─ Assinante → POST /agent/maps-search (proxy backend-core, chave API segura)
       └─ Não-assinante
            ├─ Tem chave API própria → Google Maps Places API direto
            └─ Não tem chave → Selenium scraping (fallback)
  └─ Resultados em tabela → Exportar Excel

Primeira abertura → Onboarding wizard
  ├─ Assinante: tutorial de uso
  └─ Não-assinante: tutorial + pitch + link landing page
```

**Decisão de segurança:** a chave Google Maps API do owner nunca entra no .exe. Assinantes chamam um endpoint proxy no backend-core que faz a chamada à API server-side.

---

## Plano de Implementação

### Fase 1 — Auth + Estrutura base

**Objetivo:** App abre com UI CustomTkinter, utilizador faz login/registo, sistema identifica se é assinante.

| Arquivo | O que muda |
|---|---|
| `backend-core/app/config.py` | Adicionar campo `GOOGLE_MAPS_API_KEY` |
| `backend-core/app/api/agent_proxy.py` | Novo: endpoint `POST /agent/maps-search` |
| `backend-core/app/api/__init__.py` | Registar novo router |
| `agent-local/main.py` | Reescrever: entry point CustomTkinter |
| `agent-local/app/__init__.py` | Novo |
| `agent-local/app/auth.py` | Novo: login, registo, check entitlements |
| `agent-local/app/session.py` | Novo: persistência JWT local em ~/.agent-local/session.json |
| `agent-local/app/ui/__init__.py` | Novo |
| `agent-local/app/ui/login_screen.py` | Novo: ecrã de login |
| `agent-local/app/ui/register_screen.py` | Novo: ecrã de registo (nome, email, password, whatsapp) |
| `agent-local/app/ui/main_screen.py` | Novo: placeholder com badge de assinatura (Fase 2 preenche) |
| `agent-local/app/ui/onboarding_screen.py` | Novo: placeholder (Fase 3 implementa) |
| `agent-local/requirements.txt` | Adicionar: customtkinter, openpyxl, Pillow |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `87bb5f8` | Auth + UI base CustomTkinter (login, registo, sessão, ecrã principal placeholder, onboarding placeholder, endpoint proxy backend-core) |
| 2 | `db375af` | Fix: verificar assinatura antes da API key em `/agent/maps-search` (bug detectado nos testes) |

### Fase 2 — Google Maps Integration + Export Excel

**Objetivo:** Pesquisa funciona, resultados aparecem, export Excel gerado.

| Arquivo | O que muda |
|---|---|
| `agent-local/app/maps_client.py` | Novo: Places API (proxy / direto / Selenium fallback) |
| `agent-local/app/export.py` | Novo: export .xlsx com openpyxl |
| `agent-local/app/ui/main_screen.py` | Completar: formulário + barra progresso + tabela + export |
| `agent-local/app/ui/settings_screen.py` | Novo: configuração de chave API própria |

### Fase 1b — Auth Passwordless (OTP por email)

**Objetivo:** Eliminar senha do fluxo. Utilizador entra com email → recebe código por email → acede.

| Arquivo | O que muda |
|---|---|
| `backend-core/app/db.py` | `ensure_auth_otps_table()` + `ensure_user_extra_columns()` (whatsapp, sector) |
| `backend-core/app/main.py` | Chamar novas funções `ensure_` no startup |
| `backend-core/app/api/auth.py` | `POST /auth/request-access`, `/register-passwordless`, `/verify-otp` |
| `backend-core/app/services/email_service.py` | `render_otp_email()` — template de código de acesso |
| `agent-local/app/auth.py` | `request_access()`, `register_passwordless()`, `verify_otp()` |
| `agent-local/app/ui/login_screen.py` | Redesign — só campo email, sem senha |
| `agent-local/app/ui/register_screen.py` | Redesign — nome, whatsapp, setor de atuação (sem senha) |
| `agent-local/app/ui/otp_screen.py` | Novo — campo 6 dígitos, reenvio com countdown 60s |
| `agent-local/main.py` | Novo fluxo: email → OTP ou Registo → OTP → auth |

**Fluxo novo:**
```
Email screen → request_access(email)
  ├─ existing_user → OTP screen
  └─ new_user → Register screen (nome, whatsapp, setor)
                    └─ register_passwordless() → OTP screen
OTP screen → verify_otp(email, code) → JWT → main/onboarding
```

### Commits Fase 1b

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `2293046` | Auth passwordless completo: endpoints OTP backend-core + UI redesign agent-local |
| 2 | `cc9de6d` | Fix: corrigir acentos no template OTP e assunto do email |
| 3 | `50a6b22` | Fix: importar `text` do sqlalchemy em auth.py (NameError nos endpoints OTP) |

### Checks Fase 1b

#### Cenário C1 — Novo utilizador (registo)
- [x] Abrir app → inserir email não registado → sistema mostra formulário de registo
- [x] Preencher nome, whatsapp, setor → "Criar conta e receber código"
- [x] OTP gerado na DB (`245912`) → ecrã "Verifique o seu email" aparece
- [x] Inserir código → botão "Verificando..." → sessão criada
- **Validado em:** 03/06/2026 — teste automatizado via pyautogui; screenshots confirmam toda a navegação: email screen → register screen (nome="Joao Teste C1", whatsapp="11999990001") → OTP screen → "Verificando..."

#### Cenário C2 — Utilizador existente (login)
- [x] `POST /auth/request-access` com email registado → `{"status":"existing_user"}` + OTP enviado via Resend
- [x] `POST /auth/verify-otp` com código correto → JWT gerado (183 chars)
- [x] Via UI: abrir app, inserir `testverify@gmail.com` → ecrã OTP aparece diretamente (sem registo)
- [x] OTP `646966` entrado → "Verificando..." → onboarding com badge "✓ Assinante"
- **Validado em:** 03/06/2026 — API + UI testadas; email entregue via `noreply@danielfranca.pt` (Resend)

#### Cenário C3 — Código expirado / errado
- [x] `POST /auth/verify-otp` com código `000000` → 400 "Código inválido ou expirado"
- [x] `POST /auth/verify-otp` com código já utilizado → 400 (uso único confirmado)
- [⏭️] Expiração real (15 min) — não testado; TTL correto confirmado pelo campo `expires_at` na DB
- **Validado em:** 03/06/2026 — validação de código errado e uso único confirmados via API

#### Cenário C4 — Reenvio com countdown
- [x] Botão "Reenviar código" visível no ecrã OTP
- [x] Após clique: botão fica desabilitado com countdown decrescente (60s → 0s)
- [x] Após 60s: botão volta a ficar ativo com texto "Reenviar código"
- [x] Novo email enviado com novo código
- **Validado em:** 03/06/2026 — teste manual; comportamento confirmado pelo utilizador

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `3d500a5` | Google Maps client (3 modos), export Excel, UI principal completa, settings screen |

### Fase 3 — Onboarding wizard

**Objetivo:** Substituir o placeholder actual por um wizard educativo multi-step, diferenciado por perfil (assinante vs gratuito).

**Estado actual do placeholder** (`agent-local/app/ui/onboarding_screen.py`):
- Mostra badge + mensagem "em breve" + botão "Continuar →"
- Marca `onboarding_done=True` na sessão e avança imediatamente para o ecrã principal
- Não é educativo nem diferenciado

**O que a Fase 3 deve construir:**

```
Onboarding — Assinante (3 passos)
  Passo 1: Boas-vindas — "Olá, {nome}! Bem-vindo ao Gerador de Leads."
  Passo 2: Como pesquisar — demonstração do formulário (nicho, cidade, limite)
  Passo 3: Como exportar — mostrar o botão Exportar Excel e o que esperar

Onboarding — Gratuito (4 passos)
  Passo 1: Boas-vindas — "Olá, {nome}! A tua conta gratuita está pronta."
  Passo 2: Modo Selenium — explicar que usa o Chrome (mais lento, mas funciona)
  Passo 3: Upgrade pitch — listar benefícios do plano pago; botão → landing page
  Passo 4: Como começar — formulário de pesquisa
```

**Requisitos funcionais:**
- Navegação com botões "← Anterior" / "Próximo →" e indicador de progresso (passo X de Y)
- No último passo: botão "Começar a pesquisar →" (chama `on_done`)
- Passo de upgrade (gratuito) deve ter link/botão para a landing page (URL configurável)
- Ao fechar/concluir: `onboarding_done=True` gravado em `session.json`
- Deve funcionar bem na janela de 620×720 (não fazer scroll)

**Ficheiros a alterar:**

| Arquivo | O que muda |
|---|---|
| `agent-local/app/ui/onboarding_screen.py` | Reescrever: wizard multi-step diferenciado |
| `agent-local/app/session.py` | Já tem `onboarding_done` — sem alteração |

### Commits Fase 3

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `ae5ca78` | Onboarding wizard multi-step completo (assinante 3 passos, gratuito 4 passos) |

### Checks Fase 3

#### Cenário D1 — Onboarding assinante
- [x] Fazer login com conta assinante pela primeira vez (limpar `~/.agent-local/session.json` antes)
- [x] Confirmar: 3 passos de onboarding (boas-vindas, como pesquisar, como exportar)
- [x] Confirmar: indicador de progresso visível (ex: "1 / 3")
- [x] Confirmar: botão "← Anterior" desabilitado no passo 1
- [x] Confirmar: botão "Começar a pesquisar →" no último passo navega para ecrã principal
- **Validado em:** 04/06/2026 — 3 passos confirmados, UI aprovada pelo utilizador

#### Cenário D2 — Onboarding gratuito com pitch
- [x] Fazer login com conta gratuita pela primeira vez
- [x] Confirmar: 4 passos (boas-vindas, modo Selenium, upgrade pitch, como começar)
- [x] Confirmar: passo de upgrade mostra benefícios do plano pago e link para landing page
- [x] Confirmar: link/botão da landing page abre no browser externo
- **Validado em:** 04/06/2026 — 4 passos confirmados; URL corrigida para `danielfranca.pt/lara-ia` (fix commit 3e66b04)

#### Cenário D3 — Onboarding não repete
- [x] Após completar o onboarding, fechar e reabrir o app
- [x] Confirmar: vai direto para ecrã principal (onboarding não aparece de novo)
- **Validado em:** 04/06/2026 — comportamento confirmado pelo utilizador

### Fase 4 — Empacotamento (.exe)

**Objetivo:** `agent-local.exe` funciona numa máquina limpa com duplo clique.

| Arquivo | O que muda |
|---|---|
| `agent-local/agent-local.spec` | Novo: PyInstaller spec |
| `agent-local/build.bat` | Novo: script de build Windows |

---

### Fase 5 — Prospecção WhatsApp na UI (individual)

**Objetivo:** Botão "📱 Prospectar" em cada resultado da tabela. Abre diálogo com telefone e mensagem. Envia via WhatsApp Web. Assinante: regista lead + outbound no CRM automaticamente. Não-assinante: envio local sem rastreio.

| Arquivo | O que muda |
|---|---|
| `agent-local/app/crm_client.py` | Novo: `create_lead()` e `log_outbound()` via JWT do utilizador |
| `agent-local/app/whatsapp_client.py` | Novo: wrapper fino sobre `WhatsAppRunner` sem `AgentConfig` completo |
| `agent-local/app/ui/prospect_dialog.py` | Novo: diálogo 3 passos (formulário → enviando → resultado) |
| `agent-local/app/ui/main_screen.py` | Adicionar coluna "📱" por linha de resultado; método `_open_prospect_dialog` |

**Fluxo não-assinante:**
```
Clica 📱 → preenche telefone + mensagem
  → WhatsApp Web (Selenium) envia
  → Resultado: enviado ✓ / falhou ✗
  → Badge: "Gratuito — envio local, sem registo no CRM"
```

**Fluxo assinante:**
```
Clica 📱 → preenche telefone + mensagem
  → WhatsApp Web (Selenium) envia
  → POST /api/leads (cria lead se não existir, ou usa existente pelo phone)
  → PATCH /api/leads/{id} (origin=outbound + prospection_context=mensagem)
  → Resultado: enviado + registado ✓  /  enviado mas CRM falhou ⚠
  → Badge: "✓ Assinante — envio + registo no CRM"
```

**Nota de segurança:** usa `BACKEND_URL` do `.env` (já configurado) + JWT da sessão activa. Não requer credenciais de agente.

### Commits Fase 5

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `4f65ac3` | feat(agent-local): prospecção WhatsApp na UI com distinção assinante/gratuito |

### Checks Fase 5

#### Cenário F1 — Botão "📱" visível na tabela de resultados
- [ ] Após pesquisa com resultados, coluna de prospecção aparece em cada linha
- [ ] Clique abre diálogo com telefone pré-preenchido e mensagem padrão editável

#### Cenário F2 — Envio como não-assinante (sem rastreio)
- [ ] Login com conta gratuita
- [ ] Clicar "📱" num resultado → badge "Gratuito — envio local, sem registo no CRM" visível
- [ ] Clicar "Enviar via WhatsApp →" → Chrome abre, mensagem enviada
- [ ] Resultado mostra "✅ Mensagem enviada!" sem menção de CRM

#### Cenário F3 — Envio como assinante (com rastreio no CRM)
- [ ] Login com conta assinante
- [ ] Clicar "📱" → badge "✓ Assinante — envio + registo no CRM" visível
- [ ] Enviar → Chrome envia, backend-crm regista lead + outbound
- [ ] Resultado mostra "✅ Mensagem enviada!" + "✓ Registado no CRM"
- [ ] `SELECT * FROM leads WHERE phone = ?` confirma lead criado com `origin='outbound'`
- [ ] `SELECT * FROM prospection_logs WHERE lead_id = ?` confirma registo `action='manual_outbound'`

#### Cenário F4 — Idempotência: lead já existe no CRM
- [ ] Lead com mesmo telefone já existe no CRM
- [ ] `POST /api/leads` retorna lead existente (`status='exists'`) sem duplicar
- [ ] `log_outbound` corre normalmente sobre o lead existente

#### Cenário F5 — Falha no WhatsApp (número inválido)
- [ ] Telefone sem WhatsApp ou inválido → runner retorna `status='failed'`
- [ ] Diálogo mostra "❌ Falha no envio" com motivo
- [ ] Nenhuma chamada ao CRM é feita

---

### Fase 6 — Prospecção em lote, histórico, conta, copy IA

**Commits:**

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `ec6ff97` | Backend: `POST /api/prospeccao/generate-copy` + `GET /api/prospeccao/history` |
| 2 | `e73c4fb` | agent-local: lote + histórico + conta + copy IA (44 testes passam) |

**Ficheiros alterados/criados:**

| Arquivo | O que mudou |
|---|---|
| `backend-crm/routes/prospeccao.py` | +`generate-copy` (LLM copy para lead avulso) + `history` (JOIN logs+leads) |
| `agent-local/app/ui/main_screen.py` | Checkboxes por linha, select-all, barra de selecção em lote, botão "📋 Histórico" |
| `agent-local/app/ui/bulk_prospect_dialog.py` | Novo: diálogo 3 passos com progresso por lead, delay, cancel, sync CRM |
| `agent-local/app/ui/history_screen.py` | Novo: janela de histórico (log local + CRM), export CSV |
| `agent-local/app/ui/prospect_dialog.py` | Botão "✨ Gerar com IA" (assinante) — chama `generate-copy` |
| `agent-local/app/ui/settings_screen.py` | Secção "Conta" com nome/email/badge/nota passwordless |
| `agent-local/app/session.py` | `append_prospect_log` / `get_prospect_log` (JSONL local) |
| `agent-local/app/crm_client.py` | `get_prospect_history()` + `generate_copy()` |
| `agent-local/tests/test_bulk_prospect.py` | 6 testes (loop, cancel, CRM, log) |
| `agent-local/tests/test_history.py` | 10 testes (JSONL, CRM history, generate_copy) |

### Fase 7 — CRM: Pesquisa → "Leads do Agente"

**Commit:** `db96007`

| Arquivo | O que mudou |
|---|---|
| `frontend-crm/src/pages/Pesquisa.tsx` | Formulário de search removido; tabela de histórico de prospecções do agent-local; extensões upsell mantidas |
| `frontend-crm/src/services/api.ts` | `api.prospeccao.history(limit, offset)` adicionado |

---

## Checks de Validação

### Fase 6

#### Cenário G1 — Prospecção em lote
- [ ] Pesquisar → aparecem checkboxes por linha e "☐ Todos" no cabeçalho
- [ ] Seleccionar 2+ leads → barra azul aparece "N leads seleccionados — 📱 Prospectar todos"
- [ ] Clicar "Prospectar todos" → `BulkProspectDialog` abre com lista dos leads
- [ ] Iniciar envio → chips mudam: ⏳ → 📱 → ✓ / ✗ por lead
- [ ] Delay entre envios respeitado (5s/10s/15s)
- [ ] Botão "Cancelar" interrompe a fila

#### Cenário G2 — Lote assinante + CRM
- [ ] Assinante com "Registar no CRM" activo → após envio com sucesso: lead criado + `origin='outbound'`
- [ ] Resumo final mostra N registados no CRM
- [ ] `prospection_logs` tem registo `action='manual_outbound'`

#### Cenário G3 — Histórico
- [ ] Clicar "📋" no header → `HistoryScreen` abre
- [ ] Após lote: entradas aparecem no histórico (log local)
- [ ] Assinante: entradas aparecem via CRM (fonte: CRM)
- [ ] "Exportar CSV" gera ficheiro correcto

#### Cenário G4 — Copy IA (assinante)
- [ ] Abrir diálogo de prospecção individual como assinante
- [ ] Botão "✨ Gerar com IA" visível
- [ ] Clicar → textarea preenchido com mensagem gerada (requer `OPENAI_API_KEY` configurado)
- [ ] Não-assinante: botão não aparece

#### Cenário G5 — Gestão de conta
- [ ] Abrir ⚙ Configurações → secção "Conta" mostra nome, email, badge de assinatura
- [ ] Nota sobre passwordless visível ("Para alterar conta, faz novo login")

### Fase 7

#### Cenário H1 — CRM "Leads do Agente"
- [ ] Navegar para Pesquisa no CRM → título "Leads do Agente Local" visível
- [ ] Sem prospecções: ecrã vazio com instrução de uso do app
- [ ] Após prospecção via agent-local: entradas aparecem na tabela
- [ ] Filtro "Enviados" / "Falhados" / "Todos" funciona
- [ ] Extensões de pesquisa (upsell) ainda visíveis no final da página

### Fase 2

#### Cenário B1 — Pesquisa com assinante (proxy)
- [x] Login com assinante ativo (`autodigital157@gmail.com`, plano `crm_growth`)
- [x] Barra de progresso visível durante pesquisa
- [x] Resultados aparecem em tabela (nome, telefone, website, avaliação)
- [x] Badge "Modo: Assinante — chave API incluída" visível
- [x] Botão "📥 Exportar Excel" aparece
- **Validado em:** 04/06/2026 — teste manual confirmado pelo utilizador

#### Cenário B2 — Pesquisa com não-assinante (chave própria)
- [x] Campo de chave API visível nas ⚙ Configurações (só para não-assinantes)
- [x] Após guardar, modo muda para "Chave API própria configurada"
- [x] Pesquisa retorna resultados via Places API direta
- **Validado em:** 04/06/2026 — teste manual confirmado pelo utilizador

#### Cenário B3 — Pesquisa sem chave (Selenium fallback)
- [x] Chrome abre e navega para Google Maps
- [x] Query "dentista em sao paulo" retornou 10 leads de SP
- [x] Tabela mostra nome, telefone, website, avaliação
- [x] Chrome fecha sozinho após terminar
- **Validado em:** 04/06/2026 — 10 leads encontrados via Selenium fallback (tecla '/')

**Bugs corrigidos durante testes B3 (commits 8dce5f8 → 48f1167):**
1. Chrome off-screen (`--window-position=-32000,-32000`) não renderizava DOM → removido
2. Google Maps migrou `#searchboxinput` para Shadow DOM → fallback via tecla `/` + `document.activeElement`
3. Duas pesquisas sequenciais (location + term) falhavam após "place details" → unificadas numa query
4. URL inicial centrava no IP do utilizador → corrigido para `@0,0,3z` (neutro)

#### Cenário B4 — Export Excel
- [x] Ficheiro `.xlsx` gerado corretamente
- [x] Linha 1: título da pesquisa ✓
- [x] Linha 2: contagem de leads ✓
- [x] Cabeçalhos linha 4: Nome, Telefone, Website, Endereço, Avaliação, Nº Avaliações, Link Google Maps ✓
- [x] Dados dos leads corretos (incluindo campos em branco)
- [x] Filedialog abre → ficheiro guardado → popup de confirmação → dados visíveis no Excel
- **Validado em:** 03/06/2026 (automático com 3 leads mock) + 04/06/2026 (manual — ficheiro descarregado e dados visualizados no Excel após pesquisa B3)

### Fase 1

#### Cenário A1 — App abre com UI
- [x] Executar `python main.py` na pasta `agent-local`
- [x] Confirmar: janela CustomTkinter abre (não logs no CLI)
- [x] Confirmar: ecrã de login aparece (sem sessão prévia)
- **Validado em:** 03/06/2026 — janela CustomTkinter abre corretamente com ecrã de login (logo, campos email/senha, botão Entrar, link Criar conta grátis)

#### Cenário A2 — Registo de novo utilizador
- [x] Clicar "Criar conta grátis"
- [x] Preencher Nome, Email (novo), Senha, WhatsApp
- [x] Confirmar: utilizador criado no backend-core
- [x] Confirmar: sessão persistida em `~/.agent-local/session.json`
- [x] Confirmar: badge "Gratuito" visível no ecrã principal
- **Validado em:** 03/06/2026 — uitest2@gmail.com criado com subscription_status=inactive; sessão guardada com access_token

#### Cenário A3 — Login de utilizador existente
- [x] Inserir email + senha válidos
- [x] Confirmar: login bem-sucedido, redireciona para ecrã principal
- [x] Confirmar: badge "Assinante" se subscription_status == "active"
- **Validado em:** 03/06/2026 — testverify@gmail.com (assinante ativo) retorna subscription_status=active; onboarding mostra badge "✓ Assinante" (verde)

#### Cenário A4 — Sessão persistente
- [x] Fechar e reabrir o app
- [x] Confirmar: não pede login novamente
- [x] Confirmar: vai direto para ecrã principal
- **Validado em:** 03/06/2026 — app reiniciado com session.json existente (onboarding_done=true) → foi direto para ecrã principal sem pedir login

#### Cenário A5 — Endpoint proxy no backend-core
- [x] Com backend-core rodando, chamar `POST /agent/maps-search` com JWT de assinante
- [x] Confirmar: retorna resultados (requer `GOOGLE_MAPS_API_KEY` no .env do backend-core)
- [x] Chamar com JWT de não-assinante → confirmar: 403 Forbidden
- **Validado em:** 03/06/2026 — não-assinante → 403 "Funcionalidade exclusiva para assinantes ativos"; assinante sem API key → 503 "Google Maps API não configurada" (comportamento correto)
- **Bug corrigido:** commit db375af — verificação de assinatura estava após verificação da API key; corrigido para garantir 403 correto para não-assinantes

---

## Ajustes Possíveis Pós-Implementação

### Ajustes implementados (commit `7079a15`)

- **QR Code WhatsApp Web** — `whatsapp_runner._open_chat` aguarda scan do utilizador (até 120s) em vez de retornar erro imediatamente. Chrome mantém-se aberto para o scan.
- **Chrome singleton** — `whatsapp_client.py` mantém um runner activo enquanto o app estiver aberto. Chrome não é reiniciado entre envios. `main.py` fecha o singleton no quit via `WM_DELETE_WINDOW`.
- **"Guardar no CRM" sem prospectar** — botão "💾" por linha (visível só a assinantes). Chama `create_lead()` directamente; popup confirma resultado. Idempotente: usa lead existente se phone duplicado.
- **Templates de mensagem** — `session.py` expõe `get_templates/save_template/delete_template`. `prospect_dialog.py` mostra selector de templates e botão "💾 Guardar template".
- **Modo offline** — já funcionava: `_check_session` em `main.py` tem `except Exception: pass` que preserva o `subscription_status` em cache da sessão anterior.

### Testes (commit `7079a15`)

- `agent-local/tests/test_crm_client.py` — 10 testes (`create_lead`, `log_outbound`) com mock de requests
- `agent-local/tests/test_whatsapp_client.py` — 15 testes (singleton, send, templates) sem Selenium real
- **Total: 25 testes — todos passam**

### Ajustes implementados em Fases 6+7 (commits `ec6ff97`, `e73c4fb`, `db96007`)

- **Prospecção em lote** — checkboxes + `BulkProspectDialog` com progresso, delay, cancel, sync CRM
- **Histórico de prospecções** — `HistoryScreen` + log local JSONL + `GET /api/prospeccao/history`
- **Gestão de conta** — settings mostra nome/email/badge/nota passwordless
- **Copy IA** — `POST /api/prospeccao/generate-copy` + botão "✨ Gerar com IA" no diálogo
- **CRM Pesquisa → "Leads do Agente"** — tabela de histórico via endpoint; upsell mantido
- **Testes adicionais** — 44 testes passam (6 bulk + 10 history + 25 anteriores + 3 outros)

### Gaps restantes

- **Fase 4 (empacotamento .exe)** — `agent-local.spec` e `build.bat` ainda não criados. Próxima fase obrigatória antes de distribuição.
- **Suporte macOS/Linux** — PyInstaller gera binário por plataforma; a Fase 4 será só para Windows por ora.
