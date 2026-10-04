# Corrigir a documentação sobre campos obrigatórios de qualificação

**Branch:** `claude/fix-docs-campos-obrigatorios-qualificacao`
**Status:** Interrompido de noite — continuar
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

Diagnóstico (Plan Mode) ainda não feito — próximo passo é seguir o Passo 0 de
`_guia-documentar-implementacao.md`. A decidir nesse passo:

- Se o `backend-executors` segue a mesma regra do `backend-crm` ("sem
  configuração = nenhum obrigatório") ou ainda tem mínimos fixos por modo.
  `docs/plans/qualificacao-guardrails-testes-falhando-melhorias-futuras.md`
  regista um teste do executor que espera `price_acceptance` obrigatório no
  modo `direto` e recebe lista vazia — indício de que segue a mesma regra,
  por confirmar.
- Se os números "6 / 4 / 3" ainda correspondem a alguma coisa (por exemplo,
  os campos sugeridos por omissão ao criar um AI Profile) ou devem sair dos
  documentos por completo.
- Se há outros documentos com a mesma afirmação além destes três.
