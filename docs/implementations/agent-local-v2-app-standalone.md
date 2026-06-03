# agent-local v2 — App Standalone de Geração de Leads

**Branch:** `etapa-9-planos-limites`
**Status:** Em andamento

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

#### Cenário C1 — Novo utilizador (registo) — pendente validação UI
- [ ] Abrir app → inserir email não registado → sistema mostra formulário de registo
- [ ] Preencher nome, whatsapp, setor → "Criar conta e receber código"
- [ ] Confirmar: email recebido com código de 6 dígitos
- [ ] Inserir código → confirmar: sessão criada, entra no app

#### Cenário C2 — Utilizador existente (login)
- [x] `POST /auth/request-access` com email registado → `{"status":"existing_user"}` + OTP enviado via Resend
- [x] `POST /auth/verify-otp` com código correto → JWT gerado (183 chars)
- [ ] Testar via UI: abrir app, inserir email → ecrã OTP aparece → inserir código → entra no app
- **Validado em:** 03/06/2026 — API testada; email entregue via `noreply@danielfranca.pt` (Resend); OTP gravado em `auth_otps`

#### Cenário C3 — Código expirado / errado
- [x] `POST /auth/verify-otp` com código `000000` → 400 "Código inválido ou expirado"
- [x] `POST /auth/verify-otp` com código já utilizado → 400 (uso único confirmado)
- [ ] Testar expiração real (aguardar 15min)
- **Validado em:** 03/06/2026 — validação de código errado e uso único funcionam corretamente

#### Cenário C4 — Reenvio com countdown — pendente validação UI
- [ ] No ecrã OTP, clicar "Reenviar código" → confirmar: novo email enviado
- [ ] Confirmar: botão desabilitado com countdown de 60s

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `3d500a5` | Google Maps client (3 modos), export Excel, UI principal completa, settings screen |

### Fase 3 — Onboarding

**Objetivo:** Primeira abertura mostra wizard educativo diferenciado por perfil.

| Arquivo | O que muda |
|---|---|
| `agent-local/app/ui/onboarding_screen.py` | Implementar: wizard multi-step |
| `agent-local/app/session.py` | Usar flag `onboarding_done` |

### Fase 4 — Empacotamento (.exe)

**Objetivo:** `agent-local.exe` funciona numa máquina limpa com duplo clique.

| Arquivo | O que muda |
|---|---|
| `agent-local/agent-local.spec` | Novo: PyInstaller spec |
| `agent-local/build.bat` | Novo: script de build Windows |

---

## Checks de Validação

### Fase 2

#### Cenário B1 — Pesquisa com assinante (proxy)
- [ ] Login com assinante ativo
- [ ] Preencher nicho="dentistas", cidade="São Paulo", limite=10
- [ ] Confirmar: barra de progresso aparece durante pesquisa
- [ ] Confirmar: resultados aparecem em tabela (nome, telefone, website, avaliação)
- [ ] Confirmar: "Modo: Assinante — chave API incluída" no rodapé do formulário

#### Cenário B2 — Pesquisa com não-assinante (chave própria)
- [ ] Login com utilizador não-assinante
- [ ] Abrir ⚙ Configurações → inserir chave API do Google Maps → Guardar
- [ ] Executar pesquisa
- [ ] Confirmar: resultados retornados via Places API direta

#### Cenário B3 — Pesquisa sem chave (Selenium fallback)
- [ ] Login com utilizador não-assinante sem chave configurada
- [ ] Executar pesquisa
- [ ] Confirmar: Chrome abre e faz scraping; resultados aparecem

#### Cenário B4 — Export Excel
- [ ] Após pesquisa com resultados, clicar "Exportar Excel"
- [ ] Confirmar: filedialog abre para escolher destino
- [ ] Confirmar: ficheiro .xlsx criado com colunas: Nome, Telefone, Website, Endereço, Avaliação, Nº Avaliações, Link Google Maps
- [ ] Confirmar: linha 1 tem o texto da pesquisa, linha 2 tem a contagem de leads

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

- Modo offline: se backend não acessível e sessão existe, usar status em cache (Fase 2+)
- Reset de senha via app (actualmente só via API direta)
- Suporte macOS/Linux para o .exe (PyInstaller gera binário por plataforma)
