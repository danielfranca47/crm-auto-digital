# Correção de 2 achados críticos — auditoria de segurança

**Branch:** `main`
**Status:** Concluído

---

## Motivação

Auditoria de segurança pedida pelo utilizador (4 revisões paralelas: auth/senhas,
entitlements, agentes locais, injeção/CORS) encontrou 2 achados críticos,
confirmados manualmente linha a linha antes desta implementação.

---

## Problemas Identificados (estado anterior)

1. **Rotas de agendamento sem autenticação:** `backend-crm/routes/appointments.py`
   — `GET /lead/{lead_id}`, `POST ""`, `PUT /{id}`, `DELETE /{id}`,
   `POST /{id}/complete` e `POST /{id}/cancel` não tinham `Depends(require_crm_access)`
   nem checagem de dono. Qualquer chamada anónima na internet conseguia ler, criar,
   alterar ou apagar compromissos de qualquer tenant andando por IDs sequenciais.
   Rota legada/duplicada de `routes/leads.py` (que já tinha a proteção correta),
   mas montada e chamada ao vivo pelo `frontend-crm`.

2. **`SECRET_KEY` do JWT com fallback hardcoded:** `backend-core/app/config.py:8`
   — `SECRET_KEY: str = "changeme"`. Se a env var não estivesse definida em algum
   ambiente, a app assinava JWTs (incluindo tokens de admin) com esse segredo
   público e visível no repositório, sem nenhum aviso no arranque.

---

## Abordagem

```
Fase 1 — appointments.py: adicionar current_user (require_crm_access) às 6
  rotas desprotegidas + checagem de dono via _resolve_owner_user_id já
  existente no ficheiro. 404 (não 403) em caso de mismatch.

Fase 2 — config.py: remover o default "changeme" do SECRET_KEY, tornando o
  campo obrigatório — Settings() falha no arranque (fail-fast) se a env var
  não estiver definida, em vez de assinar tokens com um segredo público.
```

---

## Plano de Implementação

### Fase 1 — `backend-crm/routes/appointments.py`: autenticação + escopo por tenant

| Arquivo | O que muda |
|---|---|
| `backend-crm/routes/appointments.py` | 6 rotas ganham `current_user: CurrentUser = Depends(require_crm_access)` + checagem de dono (404 se não bater) |
| `backend-crm/tests/test_update_appointment_route.py` | Ajustado para passar `current_user` nas chamadas diretas à função da rota |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `6aebb6f` | 6 rotas de appointments.py passam a exigir `require_crm_access` + checagem de dono (404 em mismatch); testes ajustados |

---

### Fase 2 — `backend-core/app/config.py`: remover default inseguro do `SECRET_KEY`

| Arquivo | O que muda |
|---|---|
| `backend-core/app/config.py` | `SECRET_KEY: str = "changeme"` → `SECRET_KEY: str` (obrigatório, sem default) |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `02c3ca8` | `SECRET_KEY: str = "changeme"` → `SECRET_KEY: str` (obrigatório) |

---

---

## Fase 3 — Testes de regressão de dono/tenant (verificação ao vivo revelou lacuna)

Tentei verificar a Fase 1 ao vivo com os dois backends rodando e a conta de
teste local (`autodigital157@gmail.com`). O caso sem token (401) validou
como esperado, mas os casos de "dono" e "não-dono" esbarraram num bloqueio
não relacionado à correção: a assinatura dessa conta está `inactive` no
banco local, então `require_crm_access` já barra com 403 antes mesmo de
chegar na checagem de dono — confirma que o gate de autenticação está
realmente ativo agora (antes não existia nenhum), mas não permite validar a
lógica de escopo por tenant contra dados reais sem alterar o estado de
assinatura de uma conta (fora de escopo desta correção).

Em vez disso, adicionei testes automatizados no mesmo padrão já usado no
repositório (SQLite em memória/arquivo temporário, chamada direta da função
da rota, sem depender de entitlements reais) cobrindo o caso negativo
(usuário que não é dono → 404) e positivo (dono → sucesso) para as 6 rotas
corrigidas na Fase 1.

| Arquivo | O que muda |
|---|---|
| `backend-crm/tests/test_appointments_route_auth.py` | Novo arquivo — 11 testes cobrindo dono/não-dono nas 6 rotas |

### Commits Fase 3

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | _pendente_ | 11 novos testes de regressão (dono/não-dono) para as 6 rotas de appointments.py |

---

## Checks de Validação

### Cenário 1 — appointments.py exige autenticação
- [x] `GET /api/appointments/lead/1` sem `Authorization` → 401 — **Validado em:** 2026-07-15, ao vivo (backend-core:8001 + backend-crm:8000 rodando localmente)
- [x] Com token de utilizador que não é dono do lead → 404 — **Validado em:** 2026-07-15, via `test_appointments_route_auth.py` (não foi possível ao vivo — conta de teste local com assinatura inativa bloqueia em 403 antes da checagem de dono; ver Fase 3)
- [x] Com token do dono → sucesso — **Validado em:** 2026-07-15, via `test_appointments_route_auth.py` (mesmo motivo acima)
- [x] Suíte de testes existente (`test_update_appointment_route.py`, `test_appointments_conflict_by_professional.py`) passa — **Validado em:** 2026-07-15 (9/9 testes OK, incluindo os 2 ajustados para passar `current_user`)
- [x] Suíte de testes nova (`test_appointments_route_auth.py`, 11 testes) passa — **Validado em:** 2026-07-15
- [x] Suíte completa do backend-crm sem regressão — **Validado em:** 2026-07-15 (166 testes, mesmas 22 falhas pré-existentes de antes da mudança, 0 novas)

### Cenário 2 — SECRET_KEY obrigatório
- [x] `Settings()` sem `SECRET_KEY` no ambiente → levanta `ValidationError` — **Validado em:** 2026-07-15 (confirmado via `.env` renomeado temporariamente)
- [x] Com `.env` original (SECRET_KEY presente) → import normal — **Validado em:** 2026-07-15
- [x] `/auth/login` funciona ao vivo com servidor rodando — **Validado em:** 2026-07-15 (login real da conta de teste local retornou JWT normalmente)
- [x] Suíte de testes do backend-core não regrediu — **Validado em:** 2026-07-15 (mesmas 7 falhas pré-existentes com e sem a mudança, nenhuma nova; falhas são de encoding de emoji no console Windows e de uma assinatura de função desatualizada em teste não relacionado)
