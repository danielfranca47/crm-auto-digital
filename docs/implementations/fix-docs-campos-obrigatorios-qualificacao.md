# Corrigir a documentação sobre campos obrigatórios de qualificação

**Branch:** `claude/fix-docs-campos-obrigatorios-qualificacao`
**Status:** Implementado de noite — por validar
**Origem:** este item surgiu como "Ajuste possível" na graduação de `fix-testes-backend-crm-a-falhar.md` (04/10/2026), marcado como urgente

---

## Motivação

Três documentos descrevem campos mínimos de qualificação fixos por tipo de
agente — consultivo 6 campos, agenda 4, direto 3:

- `CLAUDE.md:122` (secção "Serviços críticos de negócio",
  `services/qualification_guardrails.py`)
- `docs/architecture/pipeline-phases.md:92`
- `docs/architecture/agents.md:223`

No `backend-crm` isso já não é verdade desde o commit `13b826a`
(04/04/2026, "AI Profile como única fonte de verdade para qualificação"):
`required_fields_for_mode` em `backend-crm/services/qualification_guardrails.py`
devolve lista vazia quando o AI Profile da conta não configura
`qualification_required_fields`. Sem configuração, nenhum campo é obrigatório.

O `CLAUDE.md` é lido pelo Claude em todas as conversas, por isso a informação
errada entra em cada diagnóstico que toque em qualificação. Na correção dos
testes do `backend-crm` isto já custou tempo: um teste assumia os mínimos
fixos e a documentação dava-lhe razão.

Comportamento desejado: os três documentos descrevem o que o código faz
hoje.

## Área do sistema

- `CLAUDE.md` — linha sobre `services/qualification_guardrails.py`
- `docs/architecture/pipeline-phases.md` — secção de campos mínimos por modo
- `docs/architecture/agents.md` — tabela por modo
- Código a ler para confirmar o comportamento real, sem alterar:
  `backend-crm/services/qualification_guardrails.py`,
  `backend-executors/app/contracts/qualification_contract.py`

## Diagnóstico

- **Já existe?** O código não tem mínimos fixos: `required_fields_for_mode`
  (`backend-crm/services/qualification_guardrails.py`) e `compute_missing_fields`
  (`backend-executors/app/contracts/qualification_contract.py`) devolvem lista
  vazia sem configuração no AI Profile. O executor segue a mesma regra do CRM.
- Os números "6 / 4 / 3" não correspondem a nada. O que existe é uma
  sugestão inicial editável ao criar o perfil (`_DEFAULT_QUAL_FIELDS`,
  `backend-core/app/api/ai_profiles.py`): 2 a 3 campos por modo.
- Os campos `min_qualification_*` de `admin-agents-contract.md` não existem
  em nenhum código.
- **Riscos:** nenhum — só documentação.

## Fase 1 — Corrigir os documentos

Feito: `CLAUDE.md`, `docs/architecture/pipeline-phases.md`,
`docs/architecture/agents.md` (tabela passou a mostrar a sugestão inicial),
`docs/architecture/admin-agents-contract.md` (secção `min_qualification_*`
substituída), `docs/guia-campos-ai-profile.md` (linha 77).

**Em linguagem simples:** a documentação dizia que cada tipo de agente exigia
6, 4 ou 3 campos. Já não é assim: só é obrigatório o que o utilizador marca no
perfil de IA; sem nada marcado, nada é obrigatório. Os documentos agora dizem isto.

## Testes automáticos (turno da noite)

Alteração só de documentação (`.md`): não corri testes de código.

## Testes automáticos (turno do dia)

04/10/2026, já com `main` junto (sem conflitos): a branch só altera
documentação (seis ficheiros `.md`), por isso não corri testes de código.

## Checks de Validação

- [x] Abrir `CLAUDE.md` (linha ~122), `docs/architecture/pipeline-phases.md`
  (secção Qualification) e `docs/architecture/agents.md` (tabela `agent_mode`):
  confirmar que nenhum diz "6/4/3 campos" e que dizem "sem configuração = nenhum obrigatório".
  - **Validado em:** 04/10/2026 (turno do dia) — os três já não falam em 6, 4
    ou 3 campos. `CLAUDE.md` linha 122: "sem configuração, nenhum campo é
    obrigatório. Não há mínimos fixos por modo". `pipeline-phases.md` linha 92:
    "Sem configuração = lista vazia = nenhum campo obrigatório". `agents.md`
    linhas 219 a 227: a tabela passou a "sugestão inicial", e "vazio significa
    nenhum campo obrigatório".
- [ ] `grep -rn "min_qualification" docs frontend-admin/src backend-crm` não devolve nada.
  - **Não passou em:** 04/10/2026 (turno do dia) — o comando devolve quatro
    linhas: uma em `docs/architecture/admin-agents-contract.md:28`, escrita
    por esta branch ("Não há campos `min_qualification_*`"), e três neste
    próprio ficheiro. Em `frontend-admin/src` e `backend-crm` não há nada. O
    nome antigo já não aparece em código; a verificação, tal como está
    escrita, não consegue passar.

## Ajustes Possíveis

- `docs/guia-campos-ai-profile.md:242` e `docs/agente-1-sdr-alto-ticket.md`,
  `docs/agente-2-closer-agressivo.md`, `docs/agente-3-hibrido.md` ainda falam
  em "4 campos / 3 campos padrão" — rever se descrevem os defaults reais.
  (`**Prioridade: por definir**`)

**Aviso:** `CLAUDE.md` está alterado, categoria "sobe sempre" — precisa de decisão do utilizador.
