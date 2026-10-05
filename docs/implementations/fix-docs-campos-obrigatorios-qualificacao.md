# Corrigir a documentação sobre campos obrigatórios de qualificação

**Branch:** `claude/fix-docs-campos-obrigatorios-qualificacao`
**Status:** À espera da tua decisão
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

### Correções feitas (noite de 05/10/2026)

1. Contrato do painel admin (linha 28) reescrito: só diz que os obrigatórios são `qualification_required_fields`; vazio = nenhum. Sem o nome antigo.
2. Corrigidos `_mapa-sistema.md` (linha 92) e `pipeline-phases.md` (linha 381).
3. Segundo check reescrito para procurar só em `docs/architecture`, `frontend-admin/src` e `backend-crm`.
4. Hashes: Fase 1 = `4424527`; correções = `957095c`.

Testes automáticos (turno da noite, 05/10/2026): só `.md` alterados, não corri testes de código; o `grep` do check dá 0 resultados.

---

## Relatório para decisão

_Turno do dia, 05/10/2026 — segunda passagem, depois das correções da noite._

**O que foi feito.** A documentação dizia que cada tipo de agente exigia
sempre 6, 4 ou 3 campos de qualificação. Isso deixou de ser verdade há meses:
só é obrigatório o que estiver marcado no perfil de IA da conta, e sem nada
marcado nada é obrigatório. A branch corrige essa informação em sete
documentos, incluindo o `CLAUDE.md`. Não mexe em código. Esta noite fez os
quatro acertos que pediste ontem ao devolvê-la.

**O que foi testado.** Juntei o trabalho mais recente de `main` a esta branch,
sem conflitos. Não havia testes de código a correr, porque só mudou texto. As
duas verificações do item passaram, repetidas hoje:

- os documentos principais dizem a coisa certa, incluindo os dois sítios que
  ontem ainda repetiam a ideia antiga;
- o nome antigo de um campo que nunca existiu já não aparece em nenhum
  documento de arquitetura nem em código.

Nada ficou por validar.

**Porque está à tua espera.** A branch altera o `CLAUDE.md`, que são regras do
próprio agente e sobem sempre para ti, seja qual for o veredito.

**Veredito do avaliador: não aprovado**, por um único motivo, pequeno — ficou
uma linha noutro documento de arquitetura (o da paridade entre o playground e
o WhatsApp real) a dizer que os campos obrigatórios vêm "do perfil ou do
default do tipo de agente", e esse default não existe. Confirmei que a linha
lá está. A avaliação de ontem não a tinha apanhado, por isso a noite não a
podia ter corrigido: fez tudo o que lhe foi pedido. O avaliador diz que tudo o
resto está certo e verdadeiro, e aponta mais três frases soltas, fora dos
documentos de arquitetura, com restos da mesma ideia. O detalhe está na secção
"Avaliação", no fim.

**O que podes responder.**

- **Juntar** — a correção vai para `main` como está. A linha que sobrou e as
  três frases soltas ficam anotadas como pendentes, para não se perderem.
- **Devolver com correções** — a noite seguinte retoma esta branch, corrige a
  linha (e as três frases, se quiseres) e ela volta aqui amanhã.
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

05/10/2026, depois das correções da noite e já com `main` junto (sem
conflitos): a branch só altera documentação (sete ficheiros `.md`), por isso
não corri testes de código. Em 04/10/2026, antes das correções, tinha sido
igual.

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
  - **Validado outra vez em:** 05/10/2026 (turno do dia, depois das correções)
    — as mesmas três passagens continuam certas. Os dois sítios que ainda
    repetiam a ideia antiga também já dizem a coisa certa: `_mapa-sistema.md`
    linha 92 e `pipeline-phases.md` linha 381 ("do AI Profile; vazio =
    nenhum").
- [x] `grep -rn "min_qualification" docs/architecture frontend-admin/src backend-crm` não devolve nada.
  - **Validado em:** 05/10/2026 (turno do dia) — zero resultados nas três
    pastas. Em todo o repositório, o nome antigo só aparece neste ficheiro.
  - _Histórico — versão anterior do check (procurava em `docs/` inteiro), não passou em:_ 04/10/2026 (turno do dia) — o comando devolve quatro
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

**Veredito:** não aprovado — 05/10/2026

**O que foi feito:** A branch só mexe em documentação: sete ficheiros de texto, nenhum código, nenhum teste. Os documentos diziam que cada tipo de agente exigia sempre 6, 4 ou 3 campos de qualificação. Isso já não é verdade: só é obrigatório o que estiver marcado no perfil de IA da conta, e sem nada marcado nada é obrigatório. A branch corrigiu essa ideia no CLAUDE.md, em quatro documentos de arquitetura (fases do pipeline, agentes, mapa do sistema e contrato do painel admin) e numa linha do guia de campos do perfil de IA.

Depois da primeira avaliação (04/10), a noite fez os quatro acertos pedidos: reescreveu a frase do contrato do painel admin sem o nome antigo, corrigiu as duas linhas que tinham sobrado, reescreveu a segunda verificação para conseguir passar, e registou os identificadores dos commits.

Conferi no código que o que ficou escrito é verdade: no CRM e no executor, sem configuração no perfil a lista de obrigatórios fica vazia; e a lista de campos sugeridos ao criar um perfil é exatamente a que a tabela nova mostra.

**Porque não passou:** Não passou por uma única razão, e pequena: ficou uma linha num documento de arquitetura a repetir a ideia antiga.

No documento da paridade entre o playground e o WhatsApp real, a tabela que explica o registo de qualificação diz que os campos obrigatórios vêm "do perfil ou do default do tipo de agente". Esse default por tipo de agente não existe — confirmei no código que, sem configuração no perfil, a lista fica vazia. É o mesmo erro que este item existe para eliminar, num documento que o agente é mandado ler antes de mexer no playground. A linha não foi corrigida nem está anotada como pendente. A primeira avaliação também não a tinha apanhado, por isso não fazia parte das correções pedidas à noite — a noite fez tudo o que lhe foi pedido.

Tudo o resto está bem: os três documentos apontados na Motivação estão certos, as duas verificações passam (repeti-as e vi o mesmo resultado), os identificadores dos commits estão registados, e a branch não fez mais do que o previsto.

Encontrei ainda três sítios fora dos documentos de arquitetura com restos da mesma ideia. Não pesaram no veredito, mas não estão na lista de pendentes do item:
- o guia de resolução de conflitos usa como exemplo "campos mínimos por tipo de agente" (duas passagens, uma delas a dizer para manter "os 6 campos mínimos");
- o guia de campos do perfil de IA, na mesma tabela que a branch corrigiu, ainda diz que o tipo de agente "determina os campos obrigatórios";
- o mapa de prompts descreve um ficheiro do executor como contendo "campos por modo".

Independentemente do veredito, esta branch altera o CLAUDE.md, que está na lista do que sobe sempre, por isso a decisão final é tua. Não corri o script que confirma isso (a minha sessão é só de leitura); cabe ao turno do dia.

**O que proponho a seguir:** Um acerto de uma frase na mesma branch, só de texto:

- No documento da paridade do playground, reescrever a descrição dos campos obrigatórios para dizer que vêm só do perfil de IA, e que vazio significa nenhum.

E acrescentar aos "Ajustes Possíveis" do item os três sítios que ficaram fora dos documentos de arquitetura (guia de resolução de conflitos, a outra linha do guia de campos do perfil, e o mapa de prompts), para não se perderem. Se for mais simples, podem ser corrigidos já na mesma passagem — são frases soltas.

Em alternativa, se preferires não gastar mais uma noite com isto, podes responder "Juntar": o essencial está certo e verdadeiro, e esta linha fica anotada como pendente. Como a branch toca no CLAUDE.md, precisa sempre do teu "sim" para ir para main.

**Como desfazer:** Nada foi para main, por isso não há nada a desfazer agora. Para deitar fora este trabalho, basta apagar a branch (no PC e no GitHub) e a pasta de trabalho dela. Se mais tarde for juntada, pede "desfaz o item fix-docs-campos-obrigatorios-qualificacao": é um commit novo que anula o merge, sem push forçado. Como são só documentos, não há risco para dados nem para o sistema em produção.

| # | Critério | Cumprido | Porquê |
|---|---|---|---|
| 1 | Resolve a dor descrita na Motivação | Sim | A dor era a documentação, sobretudo o CLAUDE.md, afirmar mínimos fixos de 6, 4 e 3 campos. Os três sítios apontados na Motivação foram corrigidos e o texto novo corresponde ao que o código faz no CRM, no executor e na criação do perfil. Não é uma versão mais fácil do problema. |
| 2 | Checks obrigatórios validados, com o que foi observado | Sim | As duas verificações estão marcadas como validadas, com data e com o que foi observado, e foram repetidas depois das correções. Repeti as duas por leitura e vi o mesmo: os três documentos principais dizem a coisa certa e o nome antigo já só aparece no próprio ficheiro do item. Nenhuma foi pulada. |
| 3 | Testes automáticos passam, nenhum apagado ou enfraquecido | Sim | A branch só altera ficheiros de documentação. Não há testes de código para esta mudança, o turno do dia registou isso mesmo, e nenhum teste foi apagado ou enfraquecido. |
| 4 | Não faz mais do que o plano dizia | Sim | Mexeu em sete ficheiros de texto: os três previstos, mais o contrato do painel admin, o mapa do sistema e uma linha do guia de campos, todos com a mesma afirmação errada — os dois últimos acertos foram pedidos na devolução. Nenhum código foi tocado. |
| 5 | Convenções do CLAUDE.md respeitadas | Sim | Os identificadores dos commits da fase e das correções estão registados no ficheiro do item, as mensagens de commit seguem o formato pedido, e a frase do contrato do painel admin passou a descrever só o que existe hoje. A regra do filtro por utilizador não se aplica, porque não há código. |
| 6 | Docs de arquitetura afetados atualizados | Não | Ficou uma linha num documento de arquitetura com a ideia antiga: o documento da paridade do playground diz que os campos obrigatórios vêm do perfil "ou do default do tipo de agente", e esse default não existe. Não foi corrigida nem anotada como pendente. Os outros quatro documentos de arquitetura estão certos. |

_Avaliador: sessão separada e só de leitura (modelo opus, sessão `8a711345-4823-4a89-a33e-87619ad546ec`, 28 turnos, 0.80 USD de referência, 0 ação(ões) recusada(s))._
