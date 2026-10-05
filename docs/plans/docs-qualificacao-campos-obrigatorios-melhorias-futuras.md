# Documentação de qualificação — restos da ideia de "campos mínimos por modo"

> Contexto: itens deixados de fora da graduação de
> `fix-docs-campos-obrigatorios-qualificacao.md` (05/10/2026). Esse item
> corrigiu o `CLAUDE.md` e os documentos de arquitetura principais: os campos
> obrigatórios de qualificação vêm só de `qualification_required_fields` do AI
> Profile, e lista vazia significa nenhum obrigatório. Ficaram frases soltas
> com a ideia antiga. São só documentos — nenhum código envolvido.

## M1 — `playground-parity.md` ainda fala em default por `agent_mode`

**Prioridade: por definir**

`docs/architecture/playground-parity.md`, linha 191, descreve `required_fields`
como "override do perfil ou default do `agent_mode`". Esse default não existe.
Foi o motivo do "não aprovado" do avaliador em 05/10/2026.

**A fazer:** reescrever a célula para dizer que vêm só do AI Profile, e que
vazio significa nenhum.

## M2 — Guias dos três agentes e guia de campos do perfil de IA

**Prioridade: por definir**

- `docs/guia-campos-ai-profile.md`, linha 75 ("Determina os campos
  obrigatórios de qualificação") e linha 242 ("Os 4 campos padrão do modo
  `agenda`").
- `docs/agente-1-sdr-alto-ticket.md`, linhas 80 e 383.
- `docs/agente-2-closer-agressivo.md`, linhas 99 a 112, 298 e 434.
- `docs/agente-3-hibrido.md`, linhas 97 a 110 e 484.

**A fazer:** rever cada passagem contra o que existe hoje — a sugestão inicial
ao criar o perfil (`_DEFAULT_QUAL_FIELDS`, `backend-core/app/api/ai_profiles.py`)
tem 2 a 3 campos por modo, e é editável.

## M3 — Exemplo no guia de conflitos e linha do mapa de prompts

**Prioridade: por definir**

- `docs/implementations/_guia-resolucao-conflitos.md`, linhas 84 e 106: o
  exemplo de conflito usa "campos mínimos" de `qualification_guardrails.py`
  ("se uma branch exige 6 campos mínimos…"). É só um exemplo, mas descreve uma
  regra que não existe.
- `docs/prompts_llms.md`, linha 891: descreve `qualification_contract.py` como
  contendo "campos por modo".

**A fazer:** trocar o exemplo por outro que exista no código, e acertar a
descrição do ficheiro.
