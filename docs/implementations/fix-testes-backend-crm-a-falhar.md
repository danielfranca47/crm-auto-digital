# Corrigir os 18 testes do backend-crm que falham

**Branch:** `worktree-fix+testes-backend-crm-a-falhar` (worktree `.claude/worktrees/fix+testes-backend-crm-a-falhar`)
**Status:** Em andamento
**Origem:** este item surgiu como "Ajuste possível" na graduação de `fix-limpeza-regras-permitir-sempre.md` (04/10/2026), marcado como urgente pelo utilizador

---

## Motivação

Ao correr a suíte completa do `backend-crm` sobre o código de `main`
(04/10/2026, `python -m pytest tests/ -q`, Python global 3.13.1), o resultado
foi **224 aprovados e 18 falhados**. O resultado é igual a partir da raiz do
repositório e a partir da pasta `backend-crm`.

Uma suíte que falha sempre deixa de avisar: uma regressão nova fica escondida
no meio de falhas já conhecidas, e os testes automáticos deixam de servir de
portão para o que entra em `main`.

Comportamento desejado: a suíte do `backend-crm` passa por inteiro em `main`,
em conjunto e ficheiro a ficheiro, sem depender da ordem em que os testes
correm.

Respostas às três perguntas que estavam em aberto:

- **A causa é dos testes, do ambiente ou do código do backend?** Dos testes,
  nos 18 casos. Nenhum ficheiro de código de produção precisou de mudar.
- **Acontece fora desta máquina?** Não há outro sítio onde estes testes
  corram — `.github/workflows/` só tem os 3 deploys de frontend. 13 das 18
  falhas não dependem da máquina; as 5 de grupos de WhatsApp são específicas
  do Windows quando a suíte corre inteira.
- **Há defeito real em produção nas áreas cobertas?** Não. Depois de
  desbloqueados, todos os testes passam nas suas verificações de
  comportamento originais contra o código atual.

---

## Problemas Identificados (estado anterior)

1. **`fastapi`/`pydantic`/`httpx` de faz-de-conta (causa de fundo da
   dependência da ordem):** 8 ficheiros em `backend-crm/tests/` instalavam uma
   versão falsa destes pacotes em `sys.modules`, mas só se o verdadeiro ainda
   não tivesse sido importado. Na suíte inteira o verdadeiro já estava
   carregado e o falso ficava inerte; com o ficheiro sozinho entrava o falso,
   desatualizado (ex.: sem `Request`, que `routes/webhooks.py:12` importa
   desde `731bd1b`; sem `Depends`, que `core_client.py:6` importa).

2. **Módulo carregado "à mão" sem registo (6 falhas —
   `test_meeting_management_gate.py`, `test_inbound_orchestrator_flag.py`):**
   `inbound_handler.py` era carregado com `spec_from_file_location` sem
   entrar em `sys.modules`. Com o `pydantic` verdadeiro, `InboundWebhookPayload`
   não consegue resolver `Optional` (o ficheiro usa
   `from __future__ import annotations`) → "is not fully defined".

3. **Limpeza de pasta temporária no Windows (5 falhas —
   `test_whatsapp_group_ignore.py`):** o corpo dos testes passava, mas
   `TemporaryDirectory().cleanup()` rebentava com `PermissionError` porque o
   `.db` ainda estava aberto pela ligação que o próprio teste abre
   (`with get_connection() as conn` não fecha a ligação, só faz commit).

4. **Testes desatualizados em relação ao código (7 falhas):**
   - `test_start_followup_transition.py` (5): utilizador de teste sem
     `entitlements` (a rota chama `check_follow_up_enabled` desde `21635a2`);
     tabela de teste sem `qualification_total_score` (lida desde `f872662`);
     a rota passou a consultar o AI Profile no core e a enfileirar um job de
     pré-geração (`b7d47b3`) — o teste não substituía nenhum dos dois; e o
     teste de "qualificação incompleta" assumia campos obrigatórios fixos por
     modo, quando desde `13b826a` (04/04/2026) eles vêm só do AI Profile.
   - `test_outbound_does_not_persist_outcome.py` (1): tabelas de teste sem
     `prospection_logs.email` (`18bc282`) nem `leads.origin` (`1a5527c`).
   - `test_lead_delete.py` (1): defeito do teste desde que foi criado — a
     rota fecha a ligação no `finally` e o teste verificava o resultado pela
     mesma ligação, já fechada.

---

## Abordagem

Só `backend-crm/tests/` e documentação mudam. Regra seguida: **nenhuma
verificação (`assert`) é enfraquecida para o teste ficar verde** — só se
corrige a preparação do teste (esquema, utilizador, substituições, forma de
carregar o módulo).

```
Teste carrega módulo de produção
  ├─ antes: fastapi/pydantic falsos (se chegasse primeiro) + módulo fora de sys.modules
  └─ agora: pacotes verdadeiros sempre + módulo registado em sys.modules com nome único
             (cópia privada → substituições de funções não vazam para outros testes)

Teste precisa de banco
  ├─ rota fecha a ligação → banco em ficheiro temporário + ligação separada para verificar
  └─ pasta temporária → ignore_cleanup_errors=True + ligações do teste fechadas com closing()
```

Padrões reaproveitados (já existiam em testes mais recentes):
`test_media_fallback_pause.py` (nome único + `ignore_cleanup_errors`) e o
próprio `test_start_followup_transition.py` (banco em ficheiro + `check_conn`).

Abordagem descartada: importar os módulos normalmente
(`from services.whatsapp_inbound import inbound_handler`) em vez de carregar
uma cópia por ficheiro — os testes substituem funções do módulo
(`decide_next_action`, `build_context_bundle_from_inbound`) sem as repor, e
isso passaria a afetar os outros testes.

---

## Plano de Implementação

### Fase 1 — Pôr os 18 testes a passar

**Objetivo:** suíte inteira verde, sem tocar em código de produção.

| Arquivo (`backend-crm/tests/`) | O que muda |
|---|---|
| `test_start_followup_transition.py` | Helper `_current_user()` com `entitlements`; coluna `qualification_total_score` nos dois esquemas de teste; `setUp` substitui `_fetch_ai_profile`, `fetch_core_ai_profile` e `create_job` (sem rede, sem escrita no banco real); teste de qualificação incompleta configura `qualification_required_fields` no perfil |
| `test_outbound_does_not_persist_outcome.py` | Colunas `prospection_logs.email` e `leads.origin` no esquema de teste; `fastapi` falso removido |
| `test_lead_delete.py` | Banco em ficheiro temporário; verificação por ligação separada |
| `test_meeting_management_gate.py` | Falsos removidos; módulo registado em `sys.modules` como `inbound_handler_meeting_gate` |
| `test_inbound_orchestrator_flag.py` | Idem (`inbound_handler_orchestrator_flag`); `ignore_cleanup_errors=True` |
| `test_whatsapp_group_ignore.py` | Falsos removidos; módulos registados com nome único; `ignore_cleanup_errors=True`; `closing(get_connection())` |

### Fase 2 — Tirar a causa de fundo e deixar escrito

**Objetivo:** nenhum teste depende de pacotes de faz-de-conta; cada ficheiro
passa sozinho; fica escrito como correr a suíte.

| Arquivo | O que muda |
|---|---|
| `tests/test_followup_channel_context.py` | Remover `fastapi`/`httpx` falsos (hoje falha sozinho: 4 falhados — o falso não tem `Depends`) |
| `tests/test_outcome_persistence.py`, `tests/test_media_fallback_pause.py`, `tests/test_whatsapp_outbound_message_model.py` | Remover os falsos (hoje passam, mas são a mesma armadilha) |
| `docs/ops/local-dev.md` | Secção: como correr a suíte do `backend-crm`, resultado esperado, e a regra de não usar pacotes de faz-de-conta |

---

## Checks de Validação

Prefixo `A` = automático, corrido por Claude a partir de `backend-crm/` na
worktree.

### Cenário A1 — Suíte inteira passa
- [x] `python -m pytest tests/ -q`
- [x] Confirmar: 0 falhados
- **Validado em:** 04/10/2026 (após Fase 1) — `242 passed`

### Cenário A2 — Cada ficheiro passa sozinho
- [ ] Correr os 40 ficheiros `tests/test_*.py` um a um
- [ ] Confirmar: todos aprovados, nenhum erro de carregamento
- Estado após Fase 1 (04/10/2026): 39 de 40. Falta
  `test_followup_channel_context.py` (4 falhados sozinho) — coberto pela Fase 2.

### Cenário A3 — Os 6 ficheiros originais em ordem inversa
- [x] Correr os 6 ficheiros que falhavam, na mesma chamada, em ordem inversa
- [x] Confirmar: todos aprovados
- **Validado em:** 04/10/2026 (após Fase 1) — `21 passed`

### Cenário A4 — Nada de produção mudou
- [ ] `git diff main --stat` só mostra `backend-crm/tests/` e `docs/`

---

## Ajustes Possíveis Pós-Implementação

- **Correr os testes automaticamente no GitHub a cada envio.** Hoje nada
  corre testes de backend fora desta máquina. Decidir junto com o "agente
  avaliador como portão para `main`".
- **Documentação desatualizada sobre campos obrigatórios de qualificação.**
  `CLAUDE.md:122`, `docs/architecture/pipeline-phases.md:92` e
  `docs/architecture/agents.md:223` ainda descrevem mínimos fixos por modo
  (consultivo 6, agenda 4, direto 3). No `backend-crm`, desde `13b826a`
  (04/04/2026), `required_fields_for_mode` devolve lista vazia quando o AI
  Profile não configura nada. Falta confirmar o lado do `backend-executors`
  antes de reescrever os docs.
- **`backend-crm/scripts/test_*.py`** (2 ficheiros) têm o mesmo `fastapi`
  de faz-de-conta; não fazem parte de `pytest tests/`.
- **`pytest` não está em `backend-crm/requirements.txt`** — só existe no
  Python global.
- **Vários testes mudam `database.DB_PATH` e não o repõem** no fim; não
  causa falha hoje, mas é estado partilhado entre testes.
- **Avisos de `datetime.utcnow()` obsoleto** (`database.py:899`,
  `services/followup_reconciler.py:23`) — não são falhas.
