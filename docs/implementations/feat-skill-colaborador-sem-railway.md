# Skill de configuração de agentes sem Railway (modo colaborador)

**Branch:** `worktree-feat+skill-colaborador-sem-railway`
**Status:** Em andamento
**Autonomia:** manual

---

## Motivação

Um colaborador do comercial (não técnico) correu a skill `configuracao-personalizada` e ela pediu-lhe
acesso ao Railway. O Daniel não quer dar Railway aos colaboradores: a skill tem de funcionar só com o
pedido e o login da conta de teste do colaborador (plano Interno).

---

## Problemas Identificados (estado anterior)

1. **Produção só por `railway ssh`:** `.claude/skills/diagnosticar-agente/scripts/simular.py::prod`
   corre `prod_turno.py` dentro do container do backend-core; `aplicar_producao.sh` faz backup e PATCH
   também por `railway ssh`. O teste real usa `railway logs`.
2. **Chaves locais:** o cliente simulado (`simular.py::cliente_ia`) lê `LLM_API_KEY` de um `.env`
   gitignored; a bancada local (`preparar_bancada.py`) precisa dos `.env` dos 3 backends.
3. **Leitura de outras contas:** as conversas de referência e o snapshot do cliente vinham do `crm.db`
   de produção.
4. **Código:** corrigir o sistema exige ambiente de dev e push — impossível para o colaborador.

Tudo o que a skill faz **na conta de trabalho** já existe como rota pública com o login normal:
`GET/PATCH /ai-profiles/me`, `/api/knowledge`, `/api/playground/chat`, `/api/playground/training*`,
`/api/appointments/*`, `/api/appointments/google-sync`, `/api/assistente-ia/messages/{lead_id}`.

---

## Abordagem

```
Colaborador: pedido + senha da conta de teste (uma vez)
  → simular.py (transporte http) — login próprio; trava: token.user_id == bancada.conta.prod_user_id
      → rotas públicas do core/CRM (perfil, conhecimento, playground, treino, agenda)
      → cliente simulado: POST /api/playground/simulated-client (chave do servidor)
  → o que é código: POST /api/suporte/pedidos-correcao → frontend-admin "Pedidos" → Daniel
```

---

## Plano de Implementação

### Fase 1 — Cliente simulado no servidor (backend-crm)

| Arquivo | O que muda |
|---|---|
| `backend-crm/services/playground_simulated_client.py` | novo: prompt (igual ao de `simular.py::cliente_ia`), gpt-4o-mini a 0.4, regra "FIM" |
| `backend-crm/routes/playground.py` | `POST /api/playground/simulated-client` (`require_crm_access`, limites de tamanho, 503 sem chave, 502 erro do LLM) |
| `backend-crm/tests/test_playground_simulated_client.py` | 7 testes com o LLM mockado |

### Fase 2 — Scripts da skill por HTTP
`simular.py` com `"transporte": "http"` (default `railway`), ações `perfil|conhecimento|chat|limpar|sync|aplicar|treino`
por rotas públicas, trava de `user_id`, cliente simulado pelo servidor; `preparar_bancada.py --colaborador`;
`verificar_ambiente.py` novo.

### Fase 3 — Skill e docs no modo colaborador
`configuracao-personalizada` (+ references) e `diagnosticar-agente/references/bancada.md`,
`extrair-conversas.md`; `docs/ops/diagnostico-agentes.md` sem Railway.

### Fase 4 — Pedidos de correção dentro do sistema
Tabela `agent_fix_requests`; `POST/GET /api/suporte/pedidos-correcao`; `GET/PATCH /admin/pedidos-correcao`;
página `AdminPedidos.tsx` no frontend-admin; leitura pelo lado do Daniel na skill.

---

## Checks de Validação

### Cenário C1 — Rota do cliente simulado
- [x] `pytest tests/` do backend-crm passa (16/11/2026: 294 passed)
- [x] chamada real à rota (local) devolve uma fala coerente com a persona e `fim: true` no fim (16/11/2026: 5 chamadas no cenário p-marcar)

### Cenário C2 — Bateria sem Railway
- [x] bancada `transporte: http` corre cenários contra o backend local, com o cliente simulado do servidor (16/11/2026: p-marcar, 5 turnos, marcação criada e limpa; `--aplicar-prod` com backup; `treino listar`)
- [x] a trava recusa uma bancada cujo `prod_user_id` não é o da conta com login (16/11/2026: conta 4 vs. login 15 → recusa, código 2)
- [x] `verificar_ambiente.py` num PC sem `.env` e sem `railway` dá o checklist em linguagem simples (16/11/2026: `DIAG_MODO_COLABORADOR=1`, com e sem `_acesso.json`)

### Cenário C3 — Produção (depois do deploy)
- [ ] a mesma bateria numa conta de teste de produção, sem `railway` no PATH, dá as mesmas rotas e categorias que pelo transporte `railway`

### Cenário C4 — Pedidos de correção
- [x] a skill cria um pedido; o Daniel vê-o e muda-lhe o estado no frontend-admin; a skill vê o estado novo
  (16/11/2026, local, por API: `--prod-acao pedido` → id 1 `novo`; `GET/PATCH /admin/pedidos-correcao` com
  JWT admin → `feito` + nota; `--prod-acao pedidos` vê `feito`; sem token → 401. Página `AdminPedidos.tsx`
  validada por `tsc -b`; o desenho no browser não foi visto)

---

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `b5b79c6` | rota e serviço do cliente simulado + testes |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `16a6cda` | transporte http nos scripts da skill, `verificar_ambiente.py`, `preparar_bancada.py --colaborador` |

### Relatório da Fase 2 — o que mudou na prática
A skill já consegue trabalhar sem Railway: com o email e a senha da conta de teste, lê e muda o perfil (com
cópia de segurança), corre conversas de teste com um cliente simulado gerado pelo próprio sistema e limpa as
marcações de teste. Se a bancada apontar para outra conta que não a do login, recusa. Falta pôr a skill a
usar este modo sozinha (Fase 3) e o caminho para pedir correções ao Daniel (Fase 4).

### Commits Fase 4 (feita antes da 3: a skill precisa da rota de pedidos)

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `9f10942` | tabela, serviço e rotas dos pedidos de correção; página no frontend-admin; ações `pedido`/`pedidos` |

### Relatório da Fase 4 — o que mudou na prática
Quando a configuração não chega, a skill do colega envia um pedido de correção ao sistema, com a evidência.
O Daniel vê-o no painel admin ("Pedidos de correção"), copia um prompt pronto para a sua conversa do Claude e
marca o estado; a skill do colega vê o estado e continua quando estiver "feito".

### Commits Fase 3

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | _(a registar)_ | skill `configuracao-personalizada` escolhe o modo sozinha; `modo-colaborador.md`; docs da bancada e guia da equipa sem Railway |

### Relatório da Fase 3 — o que mudou na prática
O primeiro passo da skill é um checklist do PC. Sem Railway, ela entra no modo colaborador: pede só o email e a
senha da conta de teste, monta a bancada pelas rotas públicas, testa no Playground dessa conta, e o que é
código vira pedido de correção. Nunca pede Railway, chaves nem acesso ao servidor.
