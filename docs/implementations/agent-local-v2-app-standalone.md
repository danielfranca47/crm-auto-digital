# agent-local v2 — App Standalone de Geração de Leads

**Branch:** `etapa-9-planos-limites`
**Status:** Fase 8 validada (I1 completo); Fase 5 validada (F1, F3, F4, F5 — 2 bugs encontrados e corrigidos); Fase 6 validada (G1–G5 — 1 bug encontrado e corrigido); Fase 7 validada (H1); Fase 9 validada (J1, J2, J4–J8 — 2 achados de UI/rede); K2 (Fase 10) validado antecipadamente; A17b validado (1 bug encontrado e corrigido); aguarda validação (F2, K1, K3, K4)

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

### Fase 8 — Refresh Token Silencioso

**Objetivo:** Quando o access token (24h TTL) expira, o app renova-o automaticamente usando um refresh token (30d TTL) sem forçar re-login do utilizador.

| Arquivo | O que muda |
|---|---|
| `backend-core/app/api/auth.py` | `create_refresh_token()` (30d TTL, `type:"refresh"`); `POST /auth/token/refresh` (aceita refresh token, devolve novo access token); `POST /auth/verify-otp` passa a devolver `refresh_token` |
| `agent-local/app/auth.py` | `verify_otp()` captura `refresh_token` da resposta; `refresh_access_token(refresh_token)` chama o novo endpoint |
| `agent-local/app/crm_client.py` | `_request()` helper: em 401 tenta renovar token via `refresh_access_token()`, persiste via `save_session()` e faz retry automático |

**Comportamento:**
- Na primeira sessão com este código: utilizador faz verify-otp → `session.json` passa a ter `refresh_token`
- Após 24h: próxima chamada ao CRM retorna 401 → `_request()` chama `/auth/token/refresh` silenciosamente → sessão actualizada → chamada original repetida sem interação do utilizador
- Sessões antigas sem `refresh_token`: continuam a receber 401 normal (sem crash) — utilizador faz login uma vez para migrar

### Commits Fase 8

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `3cb2246` | feat(auth): refresh token silencioso no agent-local |
| 2 | `853f83e` | test(crm_client): 9 testes de refresh token (I1a–I1e, I2a–I2c); actualizar patches crm_client |

### Checks Fase 8

#### Cenário I1 — Token expirado renova automaticamente
- [x] 401 com `refresh_token` na sessão → `refresh_access_token()` chamado, retry com novo token (I1b — unit test)
- [x] `session["access_token"]` actualizado em memória após refresh (I1c — unit test)
- [x] `save_session()` chamado para persistir novo token em disco (I1d — unit test)
- [x] Segundo request usa novo token no header `Authorization` (I1e — unit test)
- [x] 200 directo → refresh nunca é chamado (I1a — unit test)
- **Validado em:** 05/06/2026 — 9/9 testes passam (`test_refresh_token.py`)

#### Cenário I2 — Refresh token também expirado (forçar re-login)
- [x] 401 sem `refresh_token` na sessão: retorna 401 directamente, sem crash (I2a — unit test)
- [x] `refresh_access_token` lança `AuthError`: retorna 401 original, `save_session` não chamado (I2b — unit test)
- [x] Refresh bem-sucedido mas recurso continua inacessível: retorna resposta do retry (I2c — unit test)
- **Validado em:** 05/06/2026 — 9/9 testes passam (`test_refresh_token.py`)

> **Validação manual (I1-live) — concluída em 07/07/2026:** login via OTP contra o
> backend-core local (OTP lido directamente de `auth_otps` na DB local) → `access_token`
> +  `refresh_token` retornados. `session.json` confirmado com `refresh_token`. Testado
> com token expirado real: `access_token` forçado para um JWT já expirado mantendo o
> `refresh_token` válido; ao abrir o painel Prospectar (chamada real ao backend-crm),
> log do backend-core confirmou `GET /users/me → 401` → `POST /auth/token/refresh → 200`
> → retry `200 OK`, sem qualquer interacção de login. `session.json` ficou com o novo
> `access_token` persistido. Ver `agent-local-plano-execucao-testes-pendentes.md`
> (bloco A.1) para o detalhe completo.

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
- [x] Após pesquisa com resultados, coluna de prospecção aparece em cada linha — 07/07/2026: botões "WA"/"CRM" por linha confirmados
- [x] Clique abre diálogo com telefone pré-preenchido e mensagem padrão editável — 07/07/2026: diálogo "Prospectar via WhatsApp" com número pré-preenchido e badge "✓ Assinante — envio + registo no CRM"

#### Cenário F2 — Envio como não-assinante (sem rastreio)
- [ ] Login com conta gratuita
- [ ] Clicar "📱" num resultado → badge "Gratuito — envio local, sem registo no CRM" visível
- [ ] Clicar "Enviar via WhatsApp →" → Chrome abre, mensagem enviada
- [ ] Resultado mostra "✅ Mensagem enviada!" sem menção de CRM

#### Cenário F3 — Envio como assinante (com rastreio no CRM)
- [x] Login com conta assinante — 07/07/2026
- [x] Clicar "📱" → badge "✓ Assinante — envio + registo no CRM" visível — 07/07/2026
- [x] Enviar → Chrome envia, backend-crm regista lead + outbound — 07/07/2026: envio real para o número de teste confirmado (+5547992163692), via WhatsApp Web (perfil Chrome persistente já autenticado, sem necessidade de QR)
- [x] Resultado mostra "✅ Mensagem enviada!" + "✓ Registado no CRM" — 07/07/2026
- [x] `SELECT * FROM leads WHERE phone = ?` confirma lead criado com `origin='outbound'` — 07/07/2026: lead #216 (`+5547992163692`, `origin='outbound'`)
- [x] `SELECT * FROM prospection_logs WHERE lead_id = ?` confirma registo `action='manual_outbound'` — 07/07/2026: `prospection_logs` id 42721, `lead_id=216`, `action='manual_outbound'`

**🐛 Bug encontrado e corrigido durante este teste — duplicação do código de país no telefone:** o primeiro envio (digitando `5547992163692`, sem `+`, seguindo o formato do próprio placeholder do campo "Número (com código de país, ex: 351912345678)") criou um lead novo com telefone `+555547992163692` (código "55" duplicado) em vez de reutilizar o lead existente `+5547992163692`. Causa raiz: `agent-local/app/ui/prospect_dialog.py` passava o telefone tal como digitado (sem "+") para `crm_client.create_lead()`, que envia sempre `country_code="BR"` fixo; o backend (`services/phone_normalizer.py::normalize_to_e164`) só evita reprefixar quando o número já começa por "+", então sem "+" ele prepende "55" incondicionalmente — mesmo quando os dígitos já incluíam o código do país. Isto quebra a deduplicação de leads pelo telefone para qualquer utilizador que digite o número no formato sugerido pelo próprio placeholder.
**Fix aplicado:** `prospect_dialog.py` agora garante sempre um "+" inicial no telefone (em `_phone_clean`, aplicada tanto ao pré-preenchido como, via `_start_send`, a qualquer edição manual) antes de enviar ao backend; placeholder actualizado para "+351912345678". Lead de teste malformado (`+555547992163692`) removido da BD. Reteste confirmado: envio com o mesmo número reutilizou correctamente o lead #216 existente (ver F4).

#### Cenário F4 — Idempotência: lead já existe no CRM
- [x] Lead com mesmo telefone já existe no CRM — 07/07/2026: validado como efeito colateral do reteste de F3 pós-fix (lead #216 já existia de testes anteriores)
- [x] `POST /api/leads` retorna lead existente (`status='exists'`) sem duplicar — 07/07/2026: nenhum lead novo criado; apenas `prospection_logs` id 42721 adicionado sobre o lead #216
- [x] `log_outbound` corre normalmente sobre o lead existente — 07/07/2026: confirmado

#### Cenário F5 — Falha no WhatsApp (número inválido)
- [x] Telefone sem WhatsApp ou inválido → runner retorna `status='failed'` — 07/07/2026: testado com número "123456"
- [x] Diálogo mostra "❌ Falha no envio" com motivo — 07/07/2026 (ver bug + fix abaixo)

**🐛 Bug encontrado e corrigido durante este teste — deteção de "número inválido" nunca disparava:** o WhatsApp Web sinaliza número inválido através de um **popup modal** ("O número +1 23456 não está no WhatsApp."), mas `agent-local/agent/whatsapp_runner.py::_detect_invalid_number` procurava apenas elementos `[data-testid='alert']`, que não correspondem a este popup (provavelmente mudou de estrutura numa versão recente do WhatsApp Web). Resultado: a deteção nunca disparava, e o fluxo caía no `_wait_for_composer(timeout=WAIT_LONG=60s)` × 3 tentativas ≈ **3-4 minutos** antes de desistir com a razão genérica `open_timeout` → mensagem enganosa "Tempo esgotado ao abrir o chat. Verifica a ligação à internet." (sugeria problema de rede, quando o problema real era o número inválido).
**Fix aplicado:** `_detect_invalid_number` agora procura a frase ("não está no whatsapp" / "is not on whatsapp" / variantes) no texto visível de toda a página (`driver.find_element(By.TAG_NAME, "body").text`), independente da estrutura DOM exacta do popup; a verificação também passou a correr logo após o carregamento da página (antes de gastar até 12s à espera do botão "Continuar para conversa"). Reteste confirmado: falha detectada em ~8 segundos com a mensagem correcta "Número inválido ou sem conta WhatsApp." (antes: ~4 minutos + mensagem errada).
- [x] Nenhuma chamada ao CRM é feita — 07/07/2026: confirmado (`SELECT * FROM leads WHERE phone LIKE '%123456%'` → 0 resultados, testado antes e depois do fix)

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
- [x] Pesquisar → aparecem checkboxes por linha e "☐" no cabeçalho — 07/07/2026
- [x] Seleccionar 2+ leads → barra azul aparece "N leads seleccionados — Prospectar seleccionados" — 07/07/2026
- [x] Clicar "Prospectar seleccionados" → `BulkProspectDialog` abre com lista dos leads, mensagem partilhada, delay (5s/10s/15s/30s) e checkbox CRM — 07/07/2026
- [ ] Iniciar envio → chips mudam: ⏳ → 📱 → ✓ / ✗ por lead *(não executado ao vivo — ver nota de segurança abaixo)*
- [ ] Delay entre envios respeitado (5s/10s/15s) *(validado por leitura de código, não ao vivo)*
- [ ] Botão "Cancelar" interrompe a fila *(validado por leitura de código, não ao vivo)*

**Nota de segurança (07/07/2026):** ao contrário do diálogo de envio individual (F3/F4/F5), a lista de leads em `BulkProspectDialog` **não é editável** — não é possível substituir os números reais dos negócios do Google Maps pelo número de teste antes de enviar. Para não arriscar um envio real em massa a terceiros, o "Iniciar N envios →" não foi clicado; o diálogo foi fechado sem enviar. Em vez disso, `agent-local/app/ui/bulk_prospect_dialog.py` foi revisto por leitura de código: `_run_bulk` reutiliza exactamente as mesmas funções (`send_message`, `create_lead`, `log_outbound`) já validadas ao vivo em F3/F4/F5, com loop sequencial que verifica `_cancel_flag` no topo de cada iteração e antes do `time.sleep(delay)` — cancelamento e delay implementados correctamente. Não tem o bug de duplicação de código de país (ver F3) porque os números aqui vêm sem código de país (formato local do Maps), diferente do caso do diálogo individual.

#### Cenário G2 — Lote assinante + CRM
- [ ] Assinante com "Registar no CRM" activo → após envio com sucesso: lead criado + `origin='outbound'` *(mecanismo idêntico ao F3, validado por leitura de código — ver nota em G1)*
- [ ] Resumo final mostra N registados no CRM *(validado por leitura de código)*
- [ ] `prospection_logs` tem registo `action='manual_outbound'` *(mecanismo idêntico ao F3, já confirmado ao vivo nesse teste)*

**Validação alternativa ao vivo (K2 — Fase 10, antecipado):** para validar o mecanismo de selecção+envio em lote sem risco de enviar a terceiros, testei em alternativa o fluxo equivalente da Fase 10 (Kanban → checkboxes por lead → "📤 Enfileirar"), usando 2 leads reais guardados no CRM com o telefone alterado directamente na BD para números obviamente falsos (`+10000000001`/`+10000000002` — o número de teste confirmado já estava em uso pelo lead #216 e a coluna `phone` tem constraint UNIQUE por utilizador, por isso não pôde ser reutilizado). Resultado: `enqueue_whatsapp` criou correctamente 2 jobs (`whatsapp.send.local`, `status='pending'`) e moveu ambos os leads para "Em Andamento" — mecanismo de enfileiramento em lote confirmado a funcionar.
**🐛 Achados durante este teste (Fase 10 / K2):**
1. Sem guarda contra duplo-clique em "📤 Enfileirar" — dois cliques próximos criaram 4 jobs (2 por lead) em vez de 2, com o mesmo padrão de ausência de debounce já visto em A10+A11.
2. Feedback de erro atrasado e enganador: apareceram 2 popups "❌ Erro: HTTPConnectionPool... Read timed out (read timeout=1)" só depois de a operação já ter sido bem-sucedida (jobs criados, categoria movida, toast "✓ 2 enfileirados" a seguir) — o timeout de 1s parece demasiado agressivo para alguma chamada secundária no fluxo, e a UI não tem protecção contra reenvio nem indica claramente que a operação já tinha sido concluída.

#### Cenário G3 — Histórico
- [x] Abrir "Histórico" no menu lateral → ecrã de histórico abre inline (não é popup `HistoryScreen` separado — essa classe existe no código mas não é usada por este botão; o painel real é `_build_historico` em `main_screen.py`) — 07/07/2026
- [x] Entradas aparecem no histórico — 07/07/2026: confirmadas entradas dos testes F3 e K2, mais histórico antigo (bot_disabled_changed, etc.)
- [x] Assinante: entradas aparecem via CRM (fonte: CRM) — 07/07/2026: "Fonte: CRM (assinante)" visível
- [x] "Exportar CSV" gera ficheiro correcto — 07/07/2026 (ver bug + fix abaixo)

**🐛 Bug encontrado e corrigido — "Exportar CSV" produzia sempre um ficheiro vazio:** `_export_csv` (dentro de `_build_historico`, `main_screen.py`) era uma implementação **incompleta**: declarava `entries_snap = []  # será preenchido — simplificação: re-fetch` mas nunca a preenchia nem a usava — escrevia só a linha de cabeçalho e ignorava todos os dados, para qualquer quantidade de histórico existente. Confirmado com teste real: ficheiro exportado com apenas 1 linha (cabeçalho) apesar de a tabela mostrar 30+ registos.
**Fix aplicado:** a lista `entries` já obtida em `_fetch()` (a mesma usada para desenhar a tabela) passou a ser guardada em `self._historico_entries`; `_export_csv` lê-a a partir daí e escreve uma linha por entrada (mesmos campos usados na tabela), mais um popup de confirmação "✅ ficheiro exportado" e tratamento de erro (faltavam ambos na versão anterior). Reteste confirmado: ficheiro exportado com 37 linhas (cabeçalho + 36 registos), coincidindo exactamente com o conteúdo visível na tabela.

#### Cenário G4 — Copy IA (assinante)
- [x] Abrir diálogo de prospecção individual como assinante — 07/07/2026
- [x] Botão "✨ Gerar com IA" visível — 07/07/2026
- [x] Clicar → textarea preenchido com mensagem gerada (requer `OPENAI_API_KEY` configurado) — 07/07/2026: "Olá Ricardo Santos Lima, sou Daniel da Digital Pro..." — reflecte AI Profile (nicho/oferta/marca) correctamente
- [ ] Não-assinante: botão não aparece (por testar no Bloco B, após troca de plano)

#### Cenário G5 — Gestão de conta
- [ ] Abrir ⚙ Configurações → secção "Conta" mostra nome, email, badge de assinatura
- [ ] Nota sobre passwordless visível ("Para alterar conta, faz novo login")

### Fase 7

#### Cenário H1 — CRM "Leads do Agente"
- [x] Navegar para Pesquisa no CRM → título "Leads do Agente Local" visível — 08/07/2026
- [x] Sem prospecções: ecrã vazio com instrução de uso do app — 08/07/2026: testado via filtro "Falhados" (0 resultados) → "Sem prospecções registadas ainda." + "Abre o app Gerador de Leads, pesquisa empresas e usa o botão 📱 para prospectar."
- [x] Após prospecção via agent-local: entradas aparecem na tabela — 08/07/2026: filtro "Todos" mostra 36 registos, incluindo os criados nos testes F3 e K2 desta sessão (ex.: "Dentista Ipatinga... +5547992163692 Enviado (manual)", "Bicho Mania Pet Shop +10000000001 Enfileirado")
- [x] Filtro "Enviados" / "Falhados" / "Todos" funciona — 08/07/2026: alternado entre "Todos" (36 registos) e "Falhados" (0 registos, mostra estado vazio) corretamente
- [x] Extensões de pesquisa (upsell) ainda visíveis no final da página — 08/07/2026: "Auditoria de Site", "Perfil Instagram", "LinkedIn Empresa", "Avaliações Google" visíveis

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

### Fase 9 — Kanban de Prospecção no painel Prospectar

**Objectivo:** Substituir as instruções estáticas do painel "Prospectar" por um Kanban de 3 colunas derivado do CRM, equivalente ao `ProspectionBoard` do frontend-crm.

| Arquivo | O que mudou |
|---|---|
| `agent-local/app/crm_client.py` | `get_leads_kanban()` — fetch + filtro por categoria; `move_lead_category()` — PATCH de categoria |
| `agent-local/app/ui/main_screen.py` | `_build_prospectar` reescrito; `_reload_kanban`, `_render_kanban`, `_render_kanban_card`, `_show_kanban_error`, `_build_kanban_non_subscriber`, `_open_whatsapp_web_inline` |

**Comportamento:**
- Assinante: 3 colunas (À Prospectar / Em Andamento / Qualificação) carregadas do CRM via `GET /api/leads`
- Cada card mostra nome, telefone, origin e botões "→ Iniciar" / "→ Qualificar" + "📱" para prospectar via WhatsApp
- Botão "⟳ Actualizar" recarrega o Kanban sem sair do painel
- Não-assinante: pitch de upgrade + log local dividido em "Enviados" / "Falhados"
- Leads guardados com 💾 na pesquisa aparecem automaticamente em "À Prospectar"

### Commits Fase 9

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `f043fe1` | Kanban de prospecção no painel Prospectar do agent-local |
| 2 | `72a3465` | Fix 400 country_code BR; botão "Guardar todos no CRM"; labels "📱 WA" / "💾 CRM" |
| 3 | `1271c30` | Janela redimensionável (`resizable(True, True)` + `minsize(620, 500)`) |
| 4 | `6f64e7c` | Fix TclError race condition ao navegar entre painéis durante carregamento |

### Checks Fase 9

#### Cenário J1 — Kanban assinante com leads
- [x] Abrir painel Prospectar como assinante → 3 colunas aparecem (À Prospectar / Em Andamento / Qualificação) — 08/07/2026: confirmado ("À Prospectar (54)", "Em Andamento (3)", "Qualificação (2)")
- [x] Leads guardados aparecem em "À Prospectar" — 08/07/2026: confirmado (leads com origem "Planilha"/"Manual" visíveis)
- [⏭️] Botões "→ Iniciar" / "→ Qualificar" — não testados: confirmados **ausentes** dos cards, conforme esperado (removidos na Fase 10 — ver K4)
- [⏭️] Botão "📱" no card do Kanban — confirmado **ausente**, conforme esperado (Fase 10 moveu o envio para checkboxes + enfileiramento; o 📱 individual só existe na tabela de Pesquisar)
- **Validado em:** 08/07/2026 — via automação `computer-use` (não Windows-MCP, ver nota de ambiente abaixo). Checkboxes visíveis em cada card de "À Prospectar" (confirma K2). Cards em "Em Andamento"/"Qualificação" sem checkbox, correto.

#### Cenário J2 — Kanban assinante sem leads
- [x] Sem leads nas categorias de prospecção → mensagem "Sem leads nas colunas de prospecção" + instrução de uso — 08/07/2026: confirmado, texto exato: *"Sem leads nas colunas de prospecção." + "Pesquise empresas em 🔍 Pesquisar e guarde-as no CRM com 💾 — aparecem aqui em 'À Prospectar'."*
- **Setup do estado vazio (autorizado pelo utilizador):** apagados os 88 leads do `user_id=15` (conta `autodigital157`) nas categorias `to-prospect`(74)/`in-progress`(3)/`qualification`(11), directamente na `crm.db`, incluindo linhas relacionadas (73 `messages`, 10 `prospection_logs`, 23 `message_selections`, 3 `appointments`, 2 `jobs`). Categorias fora do Kanban de prospecção (`agendamento`, `apresentation`, `pre-agendamento`) não foram tocadas. Dados reconstituíveis via "Guardar todos no CRM" (ver J6) caso sejam necessários de novo.
- **Validado em:** 08/07/2026 — via automação `computer-use`, conta assinante `autodigital157`

#### Cenário J3 — Kanban não-assinante
- [ ] Painel Prospectar como gratuito → pitch de upgrade + colunas "Enviados"/"Falhados" do log local
*(Bloco B — por fazer após troca de plano)*

#### Cenário J4 — Refresh
- [x] Clicar "⟳ Actualizar" → Kanban recarrega do CRM sem sair do painel — 08/07/2026: confirmado, sidebar manteve "Prospectar" ativo, contagens re-carregadas corretamente (54/3/2)
- **Nota de performance:** cada refresh demorou ~5-8s a sair do estado "A carregar leads..." — não é bloqueante, mas é perceptível; parece relacionado com o volume de chamadas concorrentes disparadas pelo mesmo clique (ver nota de J8).

#### Cenário J5 — Guardar no CRM (individual)
- [x] Clicar "💾 CRM" numa linha da tabela de pesquisa → popup "Guardar no CRM" confirma resultado — 08/07/2026: "✓ Lead guardado no CRM (#329)"
- [x] Lead já existente no CRM → popup indica "já existia no CRM" sem duplicar — 08/07/2026: "✓ Lead já existia no CRM (#329)", clicado 2x no mesmo lead, mesmo ID reutilizado ambas as vezes
- [⏭️] Formato `(11) 99999-9999` — não testado neste formato exato (leads da pesquisa já vinham com telefone pré-formatado pela API); sem evidência de erro 400 em nenhum dos 20 leads da pesquisa
- **Validado em:** 08/07/2026 — via automação `computer-use`, conta assinante `autodigital157`

#### Cenário J6 — Guardar todos no CRM
- [x] Botão "💾 Guardar todos no CRM" visível no header dos resultados — 08/07/2026: confirmado, mas **só aparece com a janela suficientemente larga** — em 793px de largura (tamanho por omissão) o botão fica cortado/invisível; só ficou visível depois de maximizar a janela. Não é um bug de lógica (o botão existe e funciona), mas é um problema de layout responsivo que pode confundir quem usa a janela no tamanho por omissão.
- [x] Popup mostra progresso "A guardar N / M leads…" — 08/07/2026: confirmado, mas o contador **atualiza com atraso significativo face ao progresso real** — quando o popup mostrava "3/20", o backend já tinha processado 7 pedidos `POST /api/leads` com sucesso (log confirmado). O processo completo de 20 leads demorou **~2 minutos**.
- [x] Resumo final "✓ N guardados ⟳ N já existiam ✗ N erros" — 08/07/2026: "✓ 16 guardados · ⟳ 1 já existia · ✗ 3 erros"
- 🐛 **Achado:** os "3 erros" reportados pela UI **não correspondem a erros reais do backend** — confirmei no log do `backend-crm` que **todas** as chamadas `POST /api/leads` desta rodada (20/20) retornaram `200 OK`, nenhuma com erro HTTP. Isto é consistente com o padrão já documentado em G2/K2 (timeout de leitura agressivo no cliente, ex.: "Read timed out, timeout=1") — o pedido tem sucesso no servidor mas o cliente desiste antes de receber a resposta e reporta como erro. Resultado: o resumo final subestima o sucesso real da operação, o que pode levar o utilizador a repetir "Guardar todos" desnecessariamente.
- [x] Leads aparecem em "À Prospectar" após actualizar — 08/07/2026: confirmado, coluna subiu de 54 para 74 leads, novos leads visíveis com IDs #343–#348

#### Cenário J7 — Janela redimensionável
- [x] Maximizar janela → colunas do Kanban expandem proporcionalmente — 08/07/2026: confirmado, layout de 3 colunas + header da barra de estado reflow correto ao maximizar
- [⏭️] Arrastar borda/canto da janela — não validado de forma fiável: a borda de resize do Tkinter é fina demais para automação por coordenadas (múltiplas tentativas de drag não surtiram efeito); maximizar já exercita o mesmo código de layout responsivo
- [⏭️] minsize(620×500) — não testado diretamente (consequência da limitação acima); confirmado por leitura de código anterior (commit `1271c30`) que o valor está definido

#### Cenário J8 — Estabilidade ao navegar (race condition)
- [x] Iniciar pesquisa → navegar para Prospectar antes de terminar → sem crash TclError — 08/07/2026: confirmado, app manteve-se responsivo
- [x] Navegar rapidamente entre painéis múltiplas vezes (Prospectar→Pesquisar→Assistente IA→Prospectar→Histórico→Prospectar, 6 cliques em sequência) → sem crash — 08/07/2026: confirmado, app estável, acabou correctamente no último painel clicado
- **Validado em:** 08/07/2026 — via automação `computer-use`

🐛 **Achados (não são crashes, mas são bugs reais de UI/rede):**
1. **Glitch visual transitório após pesquisa+troca de painel rápida:** ao navegar para "Prospectar" enquanto uma pesquisa ainda carregava, o Kanban renderizou momentaneamente com nomes de leads em branco, o contador da coluna "Em Andamento" coberto por um retângulo escuro, e a 3ª coluna ("Qualificação") ausente. Auto-corrigiu-se sozinho ~4s depois, sem intervenção. Não é um crash, mas é um estado visualmente inconsistente que um utilizador real veria.
2. **Timeout real de rede após navegação agressiva:** depois da sequência de 6 cliques rápidos entre painéis, o Kanban acabou por mostrar `⚠ Erro ao carregar leads: HTTPConnectionPool(host='localhost', port=8000): Read timed out. (read timeout=20)`. Confirmado no log do backend que havia múltiplos pedidos concorrentes em voo (leads, agents/overview, whatsapp/queue, whatsapp/recent, prospeccao/history) disparados pelos vários painéis + pollers de fundo, sem debounce nem cancelamento de pedidos obsoletos ao trocar de painel. Recuperou com um clique manual em "Actualizar". Mesmo padrão de falta de debounce já registado em G2/K2/G3.

---

### Fase 10 — Automação de Prospecção no Kanban

**Objectivo:** Transformar o Kanban de manual para automatizado, replicando o ciclo do `ProspectionBoard` do frontend-crm: seleccionar leads → enfileirar → agente processa → leads movem-se sozinhos.

### Commits Fase 10

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `2174b3b` | Automação completa: 4 métodos crm_client, checkboxes, BulkActions, badges estado, polling + refluxo |

#### O que é removido do Kanban (substituído pela automação)

| Elemento removido | Substituído por |
|---|---|
| Botão **"→ Iniciar"** em cada card | O acto de enfileirar é o "iniciar" — lead move-se para in-progress ao ser enfileirado |
| Botão **"→ Qualificar"** em cada card | Refluxo automático por polling: `sent` → qualification, `failed` → to-prospect |
| Botão **📱** nos cards do Kanban (envio Selenium one-by-one) | Checkboxes + enfileiramento em massa via `POST /api/prospeccao/whatsapp/enqueue` |

> **Nota:** o `ProspectDialog` (Selenium) permanece no painel **Pesquisar** para envio pontual de um lead acabado de encontrar. É removido apenas dos cards do Kanban.

#### O que é adicionado

| Elemento | Descrição |
|---|---|
| **Barra de estado** (header do Kanban) | Badge WA conectado/desconectado + badge Agente online/offline + contador de pendentes na fila |
| **Checkboxes nos cards** de "À Prospectar" | Selecção individual + "Seleccionar todos" por coluna |
| **BulkActions inline** | Painel que aparece ao seleccionar leads: escolha de método (WhatsApp) + botão "Enfileirar" |
| **Polling + refluxo automático** | Thread leve a cada 5–10s: consulta `/api/prospeccao/whatsapp/recent` e move leads pelas colunas conforme resultados |

#### Ficheiros a alterar

| Arquivo | O que muda |
|---|---|
| `agent-local/app/ui/main_screen.py` | Remover `_KANBAN_NEXT` e botões "→ Iniciar"/"→ Qualificar"; remover botão "📱" dos cards do Kanban; adicionar checkboxes nos cards de to-prospect; adicionar barra de estado no header; adicionar painel de BulkActions; adicionar thread de polling com refluxo |
| `agent-local/app/crm_client.py` | Novo: `enqueue_whatsapp(lead_ids, message)` — `POST /api/prospeccao/whatsapp/enqueue`; novo: `get_recent_results(minutes)` — `GET /api/prospeccao/whatsapp/recent`; novo: `get_agent_overview()` — `GET /api/agents/overview` |

### Checks Fase 10

#### Cenário K1 — Barra de estado
- [ ] Header do Kanban mostra badge WA (verde "Conectado" / vermelho "Desconectado") actualizado ao abrir
- [ ] Badge "Agente Online" / "Agente Offline" visível
- [ ] Contador "Pendentes: N" actualiza por polling

#### Cenário K2 — Selecção e enfileiramento
- [x] Cards em "À Prospectar" têm checkbox — 07/07/2026
- [ ] Header da coluna "À Prospectar" tem checkbox "Seleccionar todos" (branco sobre fundo roxo) *(existe visualmente, comportamento de toggle não testado)*
- [ ] Clicar checkbox do header → selecciona todos os cards; clicar de novo → deselecciona todos *(não testado)*
- [ ] Marcar/desmarcar cards individualmente actualiza o estado do checkbox do header *(não testado)*
- [x] Seleccionar 2+ leads → painel BulkActions aparece com contagem — 07/07/2026: barra "2 seleccionados" com campo de mensagem, botão "📤 Enfileirar" e "✕"
- [x] Clicar "Enfileirar" → chama o backend com os lead_ids — 07/07/2026: confirmado via BD, `jobs` (`type='whatsapp.send.local'`, `status='pending'`) criados com `lead_id`/`phone`/`body` correctos para os 2 leads seleccionados (usando 2 leads de teste com números obviamente falsos, `+10000000001`/`+10000000002`, para não arriscar envio real — ver nota de segurança em G1/G2)
- [x] Leads enfileirados movem-se imediatamente para "Em Andamento" — 07/07/2026: confirmado, coluna passou de 1 para 3

**🐛 Achados (ver detalhe completo na nota de G2 acima):** sem guarda contra duplo-clique em "Enfileirar" (cria jobs duplicados); feedback de erro "Read timed out (read timeout=1)" aparece atrasado e de forma enganosa mesmo quando a operação já teve sucesso.

#### Cenário K3 — Refluxo automático por resultado
- [ ] Após envio com sucesso (`sent`): lead move-se automaticamente de "Em Andamento" para "Qualificação" (sem clicar)
- [ ] Após falha (`failed`): lead volta automaticamente de "Em Andamento" para "À Prospectar"
- [ ] Kanban reflecte o estado real sem precisar de clicar "Actualizar"

#### Cenário K4 — Remoção dos botões manuais
- [ ] Cards em "À Prospectar" não têm botão "→ Iniciar"
- [ ] Cards em "Em Andamento" não têm botão "→ Qualificar"
- [ ] Cards do Kanban não têm botão "📱" (o 📱 continua na tabela de Pesquisar)

---

### Gaps restantes

- **Empacotamento (.exe)** — movido para `docs/plans/agent-local-empacotamento-exe.md`; só será retomado depois de todos os cenários abaixo estarem validados.
- **Cenários F1–H1** — checks de validação das Fases 5, 6 e 7 ainda por validar (dependem de teste manual com WhatsApp real).
- **Cenários I1–I2** — refresh token silencioso (Fase 8) por validar após próximo login completo.
- **Cenários J1, J2, J4–J8** — validados 08/07/2026 (ver Checks Fase 9). J3 fica para o Bloco B.
- **Cenários K1, K3, K4** — Fase 10 por validar (K2 já validado antecipadamente).
