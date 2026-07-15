# Correção de 2 achados críticos — auditoria de segurança

**Branch:** `main`
**Status:** Em andamento

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
| 1 | _pendente_ | _pendente_ |

---

### Fase 2 — `backend-core/app/config.py`: remover default inseguro do `SECRET_KEY`

| Arquivo | O que muda |
|---|---|
| `backend-core/app/config.py` | `SECRET_KEY: str = "changeme"` → `SECRET_KEY: str` (obrigatório, sem default) |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | _pendente_ | _pendente_ |

---

## Checks de Validação

### Cenário 1 — appointments.py exige autenticação
- [ ] `GET /api/appointments/lead/1` sem `Authorization` → 401
- [ ] Com token de utilizador que não é dono do lead → 404
- [ ] Com token do dono → 200 / comportamento normal
- [ ] Suíte de testes existente (`test_update_appointment_route.py`, `test_appointments_conflict_by_professional.py`) passa

### Cenário 2 — SECRET_KEY obrigatório
- [ ] `Settings()` sem `SECRET_KEY` no ambiente → levanta `ValidationError`
- [ ] Com `.env` original (SECRET_KEY presente) → import normal, `/auth/login` funciona
