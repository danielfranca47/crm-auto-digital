# Limpar instâncias mortas na UazAPI antes que o limite bloqueie novas conexões

**Branch:** `fix/limpeza-instancias-uazapi-fantasmas`
**Status:** Em andamento

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`feat-whatsapp-connection-health-check.md`. Antes disso, estava em
`docs/plans/whatsapp-connection-melhorias-futuras.md` como M4, com prioridade
BAIXA "a confirmar se é urgente". Foi promovido a urgente porque o risco se
confirmou em produção.

**Incidente real (28/09/2026):** nenhum utilizador conseguia conectar o
WhatsApp. `POST /instance/init` na UazAPI devolvia 429 com o corpo
`{"error":"Maximum number of instances reached","info":"Cannot create more
than 6 instances (current: 6, limit: 3)","max_instances":3,"double_limit":6}`.
O plano UazAPI tem **dois** limites: 3 conectadas ao mesmo tempo e **6
registadas no total, mesmo desconectadas**. As 6 existentes estavam todas
`disconnected` e sem número (4 `crm-2-*`, 1 `collab-2-*`, 1 `spy-6-*`, todas
de contas de teste). O nosso banco já não conhecia as `crm-2-*`. O utilizador
apagou-as à mão no painel da UazAPI para desbloquear.

Com clientes reais, poucas quedas e reconexões voltam a encher o limite. O
bloqueio atinge **a conta inteira** (todos os clientes), não só quem caiu.

---

## Problemas Identificados (estado anterior)

1. **Órfãs nascem por vários caminhos e nada as vê:**
   - O `DELETE /whatsapp-instances/{id}` (`backend-core/app/api/whatsapp_instances.py`)
     só apaga na UazAPI se a linha local existir e a UazAPI aceitar o token.
     Uma falha dá 502 e a instância fica.
   - O `DELETE /admin/instances/{id}` remove a linha local mesmo quando a
     UazAPI falha. É o perfil exato das 4 `crm-2-*`.
   - Não havia wrapper para `GET /instance/all`, por isso nada comparava a
     UazAPI com o banco.
2. **O job de 6h marca `disconnected` mas não liberta a vaga.**
3. **Botão mudo:** `frontend-crm/src/components/agente/ConexaoNumero.tsx`
   engole o erro do "Reconectar QR" com `catch {}`, com o comentário "o toast
   é gerido pelo hook global". Mas a chamada é direta, fora desse hook, por
   isso nenhum aviso aparecia.

---

## Abordagem

Em vez de tapar cada caminho que cria órfãs, reconciliar com a fonte de
verdade (`/instance/all`):

```
GET /instance/all  →  órfã (sem linha local, disconnected, >10 min)
                      morta (disconnected na UazAPI e inativa no banco)
                      viva/a conectar → nunca tocada

init → 429 "Maximum number of instances"
  → reclaim_instance_slots(needed=1): órfãs primeiro, depois mortas
  → repete o init 1 vez → cliente vê o QR
  → nada a libertar → 503 "Limite de conexões WhatsApp do servidor atingido…"

03:00 UTC diário → apaga só órfãs + loga ocupação
```

Trava de segurança: só apaga no Railway (`RAILWAY_ENVIRONMENT` /
`RAILWAY_ENVIRONMENT_NAME`, ou `UAZAPI_INSTANCE_CLEANUP_ENABLED=true`). Um
backend-core local aponta para a UazAPI de produção com um banco que não
conhece os clientes. Ali, todas as instâncias de produção pareceriam órfãs.

---

## Plano de Implementação

### Fase 1 — Reconciliação + auto-recuperação (backend-core)

**Objetivo:** libertar vaga sozinho quando o teto é atingido e limpar órfãs todos os dias.

| Arquivo | O que muda |
|---|---|
| `backend-core/app/services/uazapi_admin.py` | `list_instances()` (`GET /instance/all`) + `is_instance_limit_error()` |
| `backend-core/app/services/uazapi_capacity.py` (novo) | `classify_instances`, `reclaim_instance_slots`, `cleanup_orphans`, `cleanup_enabled` (trava de ambiente) |
| `backend-core/app/api/whatsapp_instances.py` | `init_instance`: 429 de teto → reclaim → retry único → senão 503 com mensagem clara |
| `backend-core/app/jobs/uazapi_cleanup_jobs.py` (novo) | Job de limpeza (sync para o APScheduler, async para o trigger) |
| `backend-core/app/main.py` | Regista o job às 03:00 UTC |
| `backend-core/app/api/cron.py` | `POST /admin/cron/uazapi-cleanup` |
| `backend-core/tests/test_uazapi_capacity.py` (novo) | 12 testes: classificação, ordem, nunca apaga vivas/a conectar, falha num delete segue para a próxima, limpeza diária só órfãs, trava de ambiente, retry do init, 503, 429 de rate limit sem limpeza |
| `docs/architecture/whatsapp-connection.md` | Nova secção "Capacidade de instâncias na UazAPI" |

Formato de `/instance/all` confirmado com uma leitura (só leitura) em
29/09/2026: lista de objetos com `name`, `token`, `status`, `created`,
`lastDisconnect` (datas `"2026-09-28 22:41:40.582Z"`).

Testes: `test_uazapi_capacity.py` + `test_connection_status.py` passam 19/19.
A suíte completa tem 8 falhas em `test_ai_profile_*`, idênticas no `main`
(pré-existentes).

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `192233c` | Reconciliação + auto-recuperação de vagas na UazAPI |

### Relatório da Fase 1 — o que mudou na prática

**Antes:** instâncias mortas ou esquecidas ficavam para sempre na UazAPI. Quando chegavam a 6, ninguém mais conseguia conectar WhatsApp até alguém as apagar à mão no painel.
**Agora:** se um cliente tentar conectar com o teto cheio, o sistema apaga sozinho uma instância morta (primeiro as esquecidas, que não pertencem a ninguém) e o QR aparece normalmente. Todos os dias às 03:00 UTC (04h em Lisboa) também apaga as esquecidas. Nunca toca num WhatsApp ligado nem num QR a ser lido, e só apaga em produção.
**Para validar:** Cenários C1, C2 e C3, abaixo, depois do deploy.

### Fase 2 — Erro visível na tela de Conexão (frontend-crm)

**Objetivo:** quando o "Reconectar QR" falhar, o cliente vê o motivo.

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/components/agente/ConexaoNumero.tsx` | `catch` de connect/refresh mostra toast com a mensagem do backend |

Type-check (`tsc -p tsconfig.app.json`): nenhum erro em `ConexaoNumero.tsx`;
o total de erros (86 linhas) é igual ao do `main` (pré-existentes).

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `b586945` | Toast com o motivo quando o "Reconectar QR" falha |

### Relatório da Fase 2 — o que mudou na prática

**Antes:** se o "Reconectar QR" falhasse, o botão simplesmente não fazia nada visível. O cliente ficava sem saber o que se passava.
**Agora:** aparece um aviso vermelho "Não foi possível gerar o QR code" com o motivo, por exemplo "Limite de conexões WhatsApp do servidor atingido. Contacte o suporte…".
**Para validar:** Cenário P1, abaixo.

---

## Checks de Validação

### Cenário C1 — Limpeza diária apaga órfã
- [ ] Setup: no painel da UazAPI, criar uma instância solta ("Nova Instância") e esperar 10 min
- [ ] Esperar pelas 03:00 UTC (ou acionar `POST /admin/cron/uazapi-cleanup`)
- [ ] Confirmar: a instância solta desaparece do painel; o log mostra `event=uazapi_capacity` com ela em `deleted_orphans`

### Cenário C2 — Teto atingido: o cliente conecta na mesma
- [ ] Setup: criar instâncias soltas no painel até o total chegar a 6; esperar 10 min
- [ ] Na tela Conexão do CRM (conta de teste), clicar em "Reconectar QR"
- [ ] Confirmar: o QR aparece; o painel mostra uma instância solta a menos; o log mostra `event=uazapi_reclaim` e `event=uazapi_instance_deleted ... reason=instance_limit`

### Cenário C3 — Nunca apaga uma conexão viva
- [ ] Setup: conta de teste com WhatsApp conectado
- [ ] Correr a limpeza (trigger ou 03:00 UTC)
- [ ] Confirmar: a conexão continua ativa no painel e no CRM

### Cenário P1 — Erro visível (Fase 2)
- [ ] Setup: teto cheio só com instâncias que não podem ser apagadas (conectadas / a ler QR)
- [ ] Clicar em "Reconectar QR"
- [ ] Confirmar: aparece um aviso na tela com a mensagem de limite atingido

---

## Ajustes Possíveis Pós-Implementação

- Alerta ativo ao admin (email/painel) quando o total estiver perto do teto. Hoje só há o log diário `event=uazapi_capacity`.
- `frontend-admin/src/pages/AdminInstances.tsx` continua a ver só o banco. Poderia listar também as órfãs de `/instance/all`.
- O "Apagar" do painel admin continua a remover a linha local mesmo quando a UazAPI falha. A limpeza diária apanha essa órfã depois; não foi mudado agora.
