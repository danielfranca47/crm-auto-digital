# Contrato — Campos capturados pelo AdminAgents

Este arquivo lista todos os campos do sistema de agentes e AI profiles que o painel admin (`AdminAgents.tsx`) lê e exibe. Serve como contrato entre o backend e o frontend admin.

**Regra:** sempre que um novo campo for adicionado ao AI profile, a um estágio de agente, ou a qualquer variável que afete o comportamento do LLM, este arquivo deve ser atualizado. Se o campo for relevante para o operador enxergar no painel, `AdminAgents.tsx` também deve ser atualizado.

---

## Campos do AI Profile por usuário

Origem: tabela `ai_profiles` em `backend-core` (via `GET /admin/agents/users/{user_id}`)

| Campo | Tipo | O que representa | Exibido no painel como |
|---|---|---|---|
| `agent_mode` | string | Modo principal do agente | Label do card / seletor de modo |
| `presentation_variant` | string | Variante de apresentação (`sales`, `scheduler`, `hybrid`) | Badge colorido no card |
| `hybrid_flow_style` | string | Estilo do fluxo híbrido (quando `presentation_variant = hybrid`) | Campo detalhado no drawer |
| `offer_pack` | string | Pack de oferta configurado | Campo detalhado no drawer |

### Campos de qualificação mínima por modo

| Campo | Tipo | Modo ao qual se aplica |
|---|---|---|
| `min_qualification_consultivo` | int / lista | `consultivo` — mínimo 6 campos |
| `min_qualification_agenda` | int / lista | `agenda` — mínimo 4 campos |
| `min_qualification_direto` | int / lista | `direto` — mínimo 3 campos |

---

## Estágios de agente por `agent_mode`

Origem: definição em `backend-crm/services/ai_playbooks/` (via `GET /admin/agents/overview`)

| `agent_mode` | Estágios esperados |
|---|---|
| `consultivo` | Qualificação → Apresentação → Negociação → Fechamento |
| `agenda` / `sdr_scheduler` | Captação → Verificação de disponibilidade → Confirmação |
| `direto` / `closer` | Qualificação → Fechamento |

Cada estágio expõe:
- `label` — nome do estágio
- `prompt` — texto do prompt ativo naquele estágio
- `source` — se é padrão do sistema ou personalizado pelo usuário

---

## O que fazer quando o sistema mudar

### Novo campo adicionado ao `ai_profiles`
1. Adicionar linha na tabela "Campos do AI Profile" acima.
2. Verificar se o campo afeta o comportamento do LLM — se sim, ele deve aparecer no painel.
3. Atualizar `GET /admin/agents/users/{user_id}` para retornar o novo campo.
4. Atualizar `AdminAgents.tsx` para exibir o novo campo no drawer ou no card.

### Novo estágio ou `agent_mode` adicionado
1. Adicionar na tabela "Estágios de agente" acima.
2. Verificar se o endpoint `GET /admin/agents/overview` está hardcoded ou lê do playbook real.
3. O frontend deve renderizar o novo estágio sem precisar de alteração se seguir o padrão dinâmico (iterar sobre estágios retornados pela API).

### Campo renomeado ou removido
1. Remover ou atualizar a linha neste contrato.
2. Verificar se `AdminAgents.tsx` quebra — campo ausente na resposta da API não deve gerar erro visual, apenas omitir o campo.
