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

### Fase 2 — Google Maps Integration + Export Excel

**Objetivo:** Pesquisa funciona, resultados aparecem, export Excel gerado.

| Arquivo | O que muda |
|---|---|
| `agent-local/app/maps_client.py` | Novo: Places API (proxy / direto / Selenium fallback) |
| `agent-local/app/export.py` | Novo: export .xlsx com openpyxl |
| `agent-local/app/ui/main_screen.py` | Completar: formulário + barra progresso + tabela + export |
| `agent-local/app/ui/settings_screen.py` | Novo: configuração de chave API própria |

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

### Fase 1

#### Cenário A1 — App abre com UI
- [ ] Executar `python main.py` na pasta `agent-local`
- [ ] Confirmar: janela CustomTkinter abre (não logs no CLI)
- [ ] Confirmar: ecrã de login aparece (sem sessão prévia)

#### Cenário A2 — Registo de novo utilizador
- [ ] Clicar "Criar conta grátis"
- [ ] Preencher Nome, Email (novo), Senha, WhatsApp
- [ ] Confirmar: utilizador criado no backend-core
- [ ] Confirmar: sessão persistida em `~/.agent-local/session.json`
- [ ] Confirmar: badge "Gratuito" visível no ecrã principal

#### Cenário A3 — Login de utilizador existente
- [ ] Inserir email + senha válidos
- [ ] Confirmar: login bem-sucedido, redireciona para ecrã principal
- [ ] Confirmar: badge "Assinante" se subscription_status == "active"

#### Cenário A4 — Sessão persistente
- [ ] Fechar e reabrir o app
- [ ] Confirmar: não pede login novamente
- [ ] Confirmar: vai direto para ecrã principal

#### Cenário A5 — Endpoint proxy no backend-core
- [ ] Com backend-core rodando, chamar `POST /agent/maps-search` com JWT de assinante
- [ ] Confirmar: retorna resultados (requer `GOOGLE_MAPS_API_KEY` no .env do backend-core)
- [ ] Chamar com JWT de não-assinante → confirmar: 403 Forbidden

---

## Ajustes Possíveis Pós-Implementação

- Modo offline: se backend não acessível e sessão existe, usar status em cache (Fase 2+)
- Reset de senha via app (actualmente só via API direta)
- Suporte macOS/Linux para o .exe (PyInstaller gera binário por plataforma)
