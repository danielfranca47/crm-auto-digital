# Corrigir a documentação sobre campos obrigatórios de qualificação

**Branch:** `claude/fix-docs-campos-obrigatorios-qualificacao`
**Status:** Interrompido de noite — continuar
**Origem:** este item surgiu como "Ajuste possível" na graduação de `fix-testes-backend-crm-a-falhar.md` (04/10/2026), marcado como urgente

---

## Correções pedidas

_04/10/2026 — o utilizador devolveu a branch com as correções que o avaliador
propôs (secção "Avaliação", no fim). A noite começa por aqui e regista por
baixo de cada ponto o que fez._

1. `docs/architecture/admin-agents-contract.md`, linha 28: reescrever a frase
   para descrever só o que existe hoje (os obrigatórios são
   `qualification_required_fields` do AI Profile; lista vazia = nenhum
   obrigatório), sem mencionar o nome antigo `min_qualification_*`.
2. Corrigir os dois sítios que ainda repetem a ideia de mínimos por tipo de
   agente: `docs/architecture/_mapa-sistema.md`, linha 92 ("campos mínimos por
   agent_mode"), e `docs/architecture/pipeline-phases.md`, linha 381 ("Campos
   obrigatórios por modo").
3. Reescrever o segundo check de validação para que consiga passar: procurar o
   nome antigo só em `docs/architecture`, `frontend-admin/src` e
   `backend-crm`, não em `docs/` inteiro (que inclui este ficheiro).
4. Registar neste ficheiro o hash do commit da Fase 1 (`4424527`) e o do
   commit destas correções, como manda o guia de implementações.

Fora deste pedido, e já anotado em "Ajustes Possíveis": os guias dos três
agentes e a linha 242 do guia de campos do perfil de IA.

---

## Relatório para decisão

_Turno do dia, 04/10/2026._

**O que foi feito.** A documentação dizia que cada tipo de agente exigia
sempre 6, 4 ou 3 campos de qualificação. Isso deixou de ser verdade há meses:
só é obrigatório o que estiver marcado no perfil de IA da conta, e sem nada
marcado nada é obrigatório. A noite corrigiu essa informação em cinco
documentos, incluindo o `CLAUDE.md`. Não mexeu em código.

**O que foi testado.** Juntei o trabalho mais recente de `main` a esta branch,
sem conflitos. Não havia testes de código a correr, porque só mudou texto. Das
duas verificações do item:

- a primeira passou — os três documentos principais já dizem a coisa certa;
- a segunda não passou, e não consegue passar tal como está escrita: pede que
  um nome antigo não apareça em lado nenhum, mas a própria branch voltou a
  escrevê-lo numa frase a dizer que esse campo não existe.

**Porque está à tua espera.** Por duas razões, e qualquer uma bastava: a
branch altera o `CLAUDE.md`, que são regras do próprio agente e sobem sempre
para ti; e ficou uma verificação por validar.

**Veredito do avaliador: não aprovado**, por três motivos pequenos — a
verificação que não consegue passar, dois sítios nos documentos de arquitetura
que ainda repetem a ideia antiga, e o número do commit por registar. Diz também
que o essencial está bem feito: a correção é verdadeira e não faz mais do que
o previsto. O detalhe está na secção "Avaliação", no fim.

**O que podes responder.**

- **Juntar** — a correção vai para `main` como está. Os dois sítios por
  corrigir e a verificação mal escrita ficam anotados como pendentes.
- **Devolver com correções** — a noite seguinte retoma esta branch e faz os
  acertos que o avaliador propõe (ou outros que indiques); depois volta aqui.
- **Fechar** — a branch é apagada e o item fica marcado para a noite não o
  refazer igual.
- **Decidir depois** — fica como está e conta para o limite de 3 branches à
  espera.

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

## Avaliação

**Veredito:** não aprovado — 04/10/2026

**O que foi feito:** A branch só mexe em documentação (seis ficheiros de texto, nenhum código). Os documentos diziam que cada tipo de agente exigia sempre 6, 4 ou 3 campos de qualificação. Isso já não é verdade: só é obrigatório o que estiver marcado no perfil de IA da conta, e sem nada marcado nada é obrigatório. A branch corrigiu essa frase no CLAUDE.md, em dois documentos de arquitetura (fases do pipeline e agentes), no contrato do painel admin e numa linha do guia de campos do perfil de IA. Confirmei no código que o que ficou escrito está certo, incluindo a lista de campos sugeridos ao criar um perfil.

**Porque não passou:** Não passou por três razões, todas pequenas.

1. Uma das duas verificações ficou por validar. Pedia que um nome antigo de campo deixasse de aparecer em qualquer lado, mas a própria branch escreveu esse nome no contrato do painel admin ("não há campos com este nome") e no ficheiro do item. Tal como está escrita, a verificação nunca consegue passar.
2. Ficaram dois sítios nos documentos de arquitetura a repetir a ideia errada de "campos mínimos por tipo de agente": uma linha no mapa do sistema e uma linha na tabela final do documento das fases do pipeline. Nenhum dos dois está na lista de pendentes do item.
3. Faltou registar no ficheiro do item o identificador do commit da fase, que é regra do processo.

O essencial está bem feito: a correção é verdadeira, não inventa nada e não faz mais do que o previsto. Não havia testes de código a correr, e nenhum foi tocado.

Independentemente do veredito, esta branch altera o CLAUDE.md, que está na lista do que sobe sempre, por isso a decisão final é tua. Não consegui correr o script que confirma isso (a minha sessão não teve permissão); cabe ao turno do dia corrê-lo.

**O que proponho a seguir:** Um pequeno acerto na mesma branch, só de texto, e depois nova avaliação:

- Reescrever a frase do contrato do painel admin para dizer só o que existe hoje, sem mencionar o nome antigo.
- Reescrever a segunda verificação para procurar o nome antigo apenas nos documentos de arquitetura e no código, e não no próprio ficheiro do item.
- Corrigir as duas linhas que sobraram (mapa do sistema e tabela final das fases do pipeline).
- Registar no ficheiro do item o identificador do commit da fase.

Os guias dos três agentes e outra linha do guia de campos, que ainda falam em "4 campos / 3 campos padrão", já estão anotados como pendentes e podem ficar para depois.

Como a branch toca no CLAUDE.md, mesmo depois do acerto precisa do teu "sim" para ir para main.

**Como desfazer:** Nada foi para main, por isso não há nada a desfazer agora. Para deitar fora este trabalho, basta apagar a branch (no PC e no GitHub) e a pasta de trabalho dela. Se mais tarde for aprovada e mergeada, pede "desfaz o item fix-docs-campos-obrigatorios-qualificacao": é um commit novo que anula o merge. Como são só documentos, não há risco para dados nem para o sistema em produção.

| # | Critério | Cumprido | Porquê |
|---|---|---|---|
| 1 | Resolve a dor descrita na Motivação | Sim | A dor era a documentação, sobretudo o CLAUDE.md, afirmar mínimos fixos de 6, 4 e 3 campos. Os três sítios apontados na Motivação foram corrigidos e o novo texto corresponde ao que o código faz no CRM, no executor e na criação do perfil. Não é uma versão mais fácil do problema. |
| 2 | Checks obrigatórios validados, com o que foi observado | Não | Só uma das duas verificações está validada. A segunda está em aberto e marcada como "não passou": a própria branch escreveu o nome antigo que a verificação diz que não pode aparecer, por isso não consegue passar tal como está. |
| 3 | Testes automáticos passam, nenhum apagado ou enfraquecido | Sim | A branch só altera ficheiros de documentação. Não há testes de código a correr para esta mudança, e nenhum teste foi apagado ou enfraquecido. |
| 4 | Não faz mais do que o plano dizia | Sim | Além dos três documentos previstos, corrigiu a mesma afirmação em mais dois (contrato do painel admin e guia de campos). O item já deixava em aberto procurar outros documentos com o mesmo erro, por isso está dentro do plano. Nenhum código foi tocado. |
| 5 | Convenções do CLAUDE.md respeitadas | Não | O identificador do commit da fase não foi registado no ficheiro do item, como o processo exige. Além disso, a frase nova do contrato do painel admin descreve o que deixou de existir, quando a regra dos documentos de arquitetura é descrever só o estado atual. A regra do filtro por utilizador não se aplica, porque não há código. |
| 6 | Docs de arquitetura afetados atualizados | Não | Ficaram dois sítios nos documentos de arquitetura com a ideia antiga de campos mínimos por tipo de agente: uma linha no mapa do sistema e uma linha na tabela final do documento das fases do pipeline. Não foram corrigidos nem listados como pendentes. |

_Avaliador: sessão separada e só de leitura (modelo opus, sessão `7c1e9d68-0b69-4dd1-bf0b-6fe014131bb4`, 22 turnos, 0.58 USD de referência, 1 ação(ões) recusada(s))._
