# Rotação do UAZAPI_ADMIN_TOKEN + secrets manager

**Branch:** `feat/uazapi-rotacao-token-secrets-manager`
**Status:** Em andamento

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`etapa-uazapi-migracao-plano-pago.md`. O `UAZAPI_ADMIN_TOKEN` é a credencial
mestre que controla todas as instâncias WhatsApp da conta paga na UazAPI.
Hoje vive em texto plano em `backend-core/.env` (local) e no equivalente em
produção, sem rotação periódica. Se vazar (commit acidental, log, máquina
comprometida), concede acesso administrativo total às instâncias até ser
revogado manualmente no painel da UazAPI.

Com clientes reais conectados, o custo de um vazamento deixa de ser teórico.

---

## Diagnóstico

### Já existe?

Não — não havia runbook de rotação nem decisão registrada sobre secrets
manager. O que já existia e foi confirmado nesta sessão:

- `.env` já está no `.gitignore` (`.gitignore:13`) — o token não está
  versionado hoje, sem vazamento ativo conhecido.
- O admin token só é lido em `backend-core`, nas rotas administrativas de
  `whatsapp_instances.py` (`/instance/init`, `/globalWebhook`) via
  `uazapi_admin.py`. `uazapi_client.py` (envio de mensagens) e
  `backend-executors` **não usam o admin token** — usam o token por
  instância. Rotacionar o admin token não derruba instâncias já conectadas
  nem interrompe envio de mensagens.
- O token já é mascarado em logs de erro — `_mask_token_in_text` em
  `uazapi_admin.py:137-140`, aplicado no corpo de resposta de erro logado
  por `_request` (linha ~170-177).

### O que precisava ser construído

- Um runbook de rotação documentando o processo passo a passo.
- Referência cruzada nos dois lugares onde `UAZAPI_ADMIN_TOKEN` é
  documentado (`.env.example`, `README.md`).

### Riscos e dependências

Nenhum — mudança é documentação + comentário de config, sem lógica nova.

### Decisão do utilizador (secrets manager e cadência)

- **Secrets manager:** sem ferramenta nova (Doppler/AWS Secrets Manager
  descartados por ora) — Railway continua sendo o cofre de fato, o token
  nunca é versionado.
- **Cadência de rotação:** sem calendário fixo — só sob suspeita de
  vazamento.

---

## Plano de Implementação

### Fase 1 — Runbook de rotação + referências

**Objetivo:** deixar o processo de rotação documentado e pronto para
execução rápida caso haja suspeita de vazamento.

| Arquivo | O que muda |
|---|---|
| `docs/ops/rotacao-uazapi-admin-token.md` (novo) | Runbook: gerar novo token no painel UazAPI → atualizar env var no Railway → atualizar `.env` local → verificar → revogar token antigo. Explica por que é seguro (admin token isolado de instâncias já conectadas). |
| `backend-core/.env.example` | Comentário acima de `UAZAPI_ADMIN_TOKEN` referenciando o runbook. |
| `backend-core/README.md` | Linha de `UAZAPI_ADMIN_TOKEN` linkando o runbook. |

---

## Checks de Validação

### Cenário C1 — Runbook é executável de ponta a ponta
- [ ] Ler o runbook (`docs/ops/rotacao-uazapi-admin-token.md`) do início ao
      fim como se fosse a primeira vez executando
- [ ] Confirmar que cada passo tem o local exato (painel UazAPI, nome da env
      var no Railway, comando de restart) sem ambiguidade
- [ ] Confirmar que a afirmação "instâncias conectadas não são afetadas"
      está clara e justificada no texto

Não é um cenário de browser/WhatsApp real — validação é revisão de leitura
do documento pelo utilizador (ops, não feature de produto).

---

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `779a353` | Runbook de rotação + referências cruzadas |

**Detalhes do commit `779a353`:**
- `docs/ops/rotacao-uazapi-admin-token.md` — runbook novo: quando executar,
  por que é seguro, passo a passo (gerar → Railway → `.env` local →
  verificar → revogar antigo), onde o token vive hoje.
- `backend-core/.env.example` — comentário referenciando o runbook.
- `backend-core/README.md` — link para o runbook na linha de
  `UAZAPI_ADMIN_TOKEN`.
- `docs/implementations/uazapi-rotacao-token-secrets-manager.md` —
  diagnóstico preenchido e Fase 1 registrada.

### Relatório da Fase 1 — o que mudou na prática

**Antes:** não existia nenhum processo escrito para trocar o token mestre
da UazAPI. Se fosse preciso rotacionar (ex.: suspeita de vazamento), seria
"descobrir na hora" — sem saber se ia derrubar as instâncias já conectadas.

**Agora:** existe um runbook (`docs/ops/rotacao-uazapi-admin-token.md`) com
o passo a passo completo, incluindo a confirmação de que trocar esse token
**não** afeta instâncias WhatsApp já conectadas nem interrompe o envio de
mensagens — só afeta a criação de instâncias novas até o token ser
atualizado. Não houve mudança de código: nenhuma lógica nova era
necessária.

**Para validar:** Cenário C1, acima — leitura do runbook.
