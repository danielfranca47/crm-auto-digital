---
name: diagnosticar-agente
description: Porta de entrada para diagnosticar e afinar o agente de IA de WhatsApp de QUALQUER conta de cliente (qualquer empresa, nicho ou tipo de venda) a partir de conversas reais de referência. Lê as conversas (CRM ou WhatsApp Web), extrai o comportamento esperado, identifica qual dos 3 agentes da página Tipos de Agentes (/agentes-info) corresponde ao processo do cliente — Agente 01 SDR de Alto Ticket, Agente 02 Vendedor Autônomo, Agente 03 Assistente Comercial — e se o lead é inbound ou outbound, compara com o agente configurado e passa o trabalho à skill desse agente (agente-01-sdr-alto-ticket, agente-02-vendedor-autonomo, agente-03-assistente-comercial). Monta uma bancada isolada com cliente simulado por IA, mede cada versão de configuração, testa no Playground de produção e encaminha o que é código para docs/plans e docs/implementations. Use sempre que o utilizador disser que o agente de uma conta "não atende como devia" ou "não performa como na conversa X", pedir para "configurar/afinar o agente do cliente Y com base nestas conversas", der números de telefone de conversas de referência, ou pedir para retomar uma bancada em .claude/agentes/<cliente>/.
---

# Diagnosticar um agente a partir de conversas reais (skill primária)

O sistema é multi-empresa e multi-agente. Esta skill **não assume nicho nem tipo de venda**: descobre-os
nas conversas de referência e no perfil configurado. Depois passa o trabalho à skill do agente certo,
que sabe o que medir e onde o sistema falha nesse agente.

**Vocabulário obrigatório:** o da página Tipos de Agentes (`https://crmapp.danielfranca.pt/agentes-info`,
código em `frontend-crm/src/pages/TiposAgentes.tsx`):
- os agentes: Agente 01 · Robusto — SDR de Alto Ticket; Agente 02 · Direto — Vendedor Autônomo;
  Agente 03 · Híbrido — Assistente Comercial;
- os conceitos: Inbound/Outbound, Fit, Dor, Filtro 1/2/3 (4Ps: Poder, Prioridade, Preço, Timing),
  Handoff, Dossiê/Briefing, Aquecimento, Nurture, Follow-up, No-show.

Usa estes nomes com o utilizador, no README e nos itens de plans. Os nomes técnicos (`template_key`,
`agent_mode`, p0–p5) ficam só entre parênteses ou nos ficheiros técnicos.

**Resultado:** o agente da conta segue, no Playground de produção, o comportamento das conversas de
referência, com a taxa de acerto medida. O que só o código resolve fica registado em plans ou
implementations, com a evidência medida, a ordem de execução e prompts prontos. O utilizador recebe um
relatório em linguagem simples e um prompt de retomada.

O utilizador não é programador. Fala com ele em linguagem simples. A mecânica (rotas, campos,
guardrails) fica nos ficheiros da bancada e nos `.md` de plans e implementations.

## Mapa

| Ficheiro | Para quê |
|---|---|
| esta skill | entrada, regras fixas, fases comuns, classificação, encaminhamento |
| [references/extrair-conversas.md](references/extrair-conversas.md) | ler conversas (CRM → WhatsApp Web) e escrever o "comportamento esperado" |
| [references/classificar-processo.md](references/classificar-processo.md) | identificar o agente (01/02/03) e a origem (inbound/outbound) pelas conversas e cruzar com o preset configurado |
| [references/bancada.md](references/bancada.md) | ambiente isolado, cenários, cliente simulado, Playground de produção |
| [references/triagem.md](references/triagem.md) | classificar cada falha: configuração, código, modelo, dados ou negócio |
| [references/entregas.md](references/entregas.md) | plans e implementations, quadro de sobreposição, prompts, relatório, retomada |
| `scripts/` | `preparar_bancada.py`, `simular.py`, `prod_turno.py`, `aplicar_producao.sh`, `wa_extract.js` |
| skills `agente-01-sdr-alto-ticket`, `agente-02-vendedor-autonomo`, `agente-03-assistente-comercial` | etapas da página → sistema → critérios; cenários; campos; prometido na página vs. código; limites medidos |

Os scripts são genéricos: tudo o que é próprio de uma conta vive em
`.claude/agentes/<slug>/bancada.json`.

## Entrada

Precisas de: **conta** (email), **números das conversas de referência** (as que correram bem, feitas por
um humano ou por uma versão anterior do agente) e o **objetivo** (ex.: "da abordagem até ao
agendamento e confirmação", "até o cliente pagar"). Se faltar alguma coisa, pede tudo numa única
pergunta. Se a pasta `.claude/agentes/<slug>/` já existir, **é uma retomada**: lê o `README.md` dela
(secções "Estado atual" e "Onde retomamos") e salta para a fase indicada lá.

## Regras fixas

1. **Produção só em leitura** até um "sim" explícito para aplicar. Antes de aplicar, faz backup; depois,
   verifica.
2. **Nunca enviar WhatsApp.** O WhatsApp Web é só para ler. Os testes correm no Playground (local ou de
   produção). O webhook inbound em produção é proibido.
3. **Sem alterações de código nesta skill.** O que é código vai para plans ou implementations. A
   exceção é a documentação de arquitetura que contradiga o código; essa corrige-se.
4. **Dados de clientes reais** ficam em `.claude/agentes/<slug>/`, que está no gitignore. Nos
   ficheiros versionados entram só números agregados e exemplos anonimizados.
5. **Segredos nunca saem do container.** O `prod_turno.py` cria o token dentro do `railway ssh`, usa-o
   lá e não o imprime.
6. **Não afrouxar critérios para fazer passar uma versão.** Se um critério estiver errado, isso é uma
   decisão do utilizador.

## Fases

### 0. Estado do repositório
- Ler `docs/implementations/` e correr `git worktree list`. Aplica a limpeza automática do CLAUDE.md.
- Correr `git log --oneline -30` e listar os fixes recentes ou em curso que mexem no comportamento que
  vais testar. Entram na triagem (o problema pode já estar corrigido) e no quadro de sobreposição.

### 1. Perfil atual (produção, só leitura)
- `python scripts/preparar_bancada.py <slug> --so-snapshot ...` grava `ambiente/prod_ai_profile.json`
  e `ambiente/prod_knowledge.json`.
- Resume ao utilizador o que está configurado: `agent_mode`, `template_key`, `presentation_variant`,
  modelo, fases do Fluxo de Venda preenchidas ou vazias, campos obrigatórios, horários e handoff.
  Anota o `updated_at`, que serve para detetar edições do cliente antes de aplicar.

### 2. Conversas de referência → comportamento esperado
Segue [references/extrair-conversas.md](references/extrair-conversas.md). O resultado vai para o
README da bancada:
- **Roteiro observado:** passos, frases e formatos exatos.
- **Factos do negócio.**
- **Limites:** o que o atendimento recusou e como.
- **Divergências** com a Base de Conhecimento ou o site.
- **Critérios de sucesso:** uma checklist verificável.

### 3. Identificar o agente e encaminhar
Segue [references/classificar-processo.md](references/classificar-processo.md):
1. Identifica, pelas conversas, **qual dos 3 agentes** corresponde ao processo real. Usa o quiz da
   página (ticket médio, quem apresenta e fecha, tipo de negócio) e o fim das conversas que correram
   bem. Identifica também a **origem** de cada conversa (inbound ou outbound).
2. Cruza com o **preset configurado** (`template_key` + `agent_mode`) ou regista que é uma combinação
   personalizada.
3. Se não baterem, isso é um achado de primeira ordem. Explica a consequência em linguagem simples e
   pergunta se muda o agente antes de afinar o resto. Afinar instruções em cima do agente errado é
   trabalho perdido.
4. **Invoca a skill do agente** (Skill tool): `agente-01-sdr-alto-ticket`,
   `agente-02-vendedor-autonomo` ou `agente-03-assistente-comercial`. Ela traz as etapas da página
   ligadas ao que o sistema faz em cada uma, os critérios, os cenários inbound e outbound, os campos e
   a tabela "prometido na página vs. código". Junta os critérios dela aos da fase 2.
5. Se as conversas misturam processos, segue a skill do agente dominante e usa da outra só os cenários
   que se aplicam.
6. **Análise do sistema em paralelo:** cada etapa da página que o código não cumpre (marcada ❌ ou ❓
   e confirmada) é um achado de produto. Vai para `docs/discovery/` ou plans; nunca se tenta compensar
   com configuração.

### 4. Bancada e linha de base
- `python scripts/preparar_bancada.py <slug> ...` monta a bancada (ver
  [references/bancada.md](references/bancada.md)).
- Escreve os cenários em `cenarios.json`: um fixo e uma persona `p-*` por conversa real, mais os
  cenários-limite que a skill do agente indicar.
- Corre a **linha de base (`c00`)** com a configuração atual, sem mudar nada. Abre o `.json` bruto
  quando algo parecer estranho e classifica cada falha com a [triagem](references/triagem.md). A
  primeira falha pode nem ser de configuração.

### 5. Ciclo de versões (configuração)
- Lê `docs/architecture/prompt-engineering-principles.md` e `docs/prompts_llms.md` antes de escrever
  instruções.
- **Uma hipótese por versão** (`cNN-<o-que-muda>` em `gerar_config.py`). Por cada versão, regista uma
  linha no README: versão, o que mudou e o resultado medido.
- Antes de pôr uma instrução num campo, **confirma no código que esse campo chega à fase que a
  usa**. A skill do agente tem o mapa, e o código é a verdade se divergirem.
- **Regra das 3 formulações:** se 3 formulações não eliminam o comportamento, é código. Regista-o e
  deixa de gastar tentativas.
- **Paragem:** todos os critérios de sucesso cumpridos na bateria, ou o que falta é só código ou
  negócio.

### 6. Medir em taxa e perguntar o que é de negócio
- Mede em taxa: `simular.py --bateria` corre em sequência e `--resumo` tabula. Um único caso não chega
  para concluir.
- O local e a produção divergem (modelo, latência, dados reais). Antes de dar uma versão como boa,
  confirma-a no **Playground de produção** (`--prod`).
- Pergunta ao utilizador só o que muda a configuração, com uma opção recomendada e o porquê.

### 7. Aplicar em produção (só com "sim")
- `bash scripts/aplicar_producao.sh <pasta> configs/cNN.json` faz o backup e depois o PATCH dentro do
  container.
- Verifica os campos só em leitura e compara o backup com o snapshot da fase 1. Se o cliente editou
  algo entretanto, avisa antes de sobrescrever.
- Avisa que um separador antigo do ecrã de configuração, se for gravado, repõe a versão anterior.
- Corre a bateria `--prod` com a versão aplicada.

### 8. Encaminhar o que é código
Segue [references/entregas.md](references/entregas.md):
- Procura duplicados em `docs/plans/` antes de criar um item novo.
- O que é urgente (dano ao cliente final) vai para `docs/implementations/` com
  `Status: Aguardando Plan Mode` e `Autonomia: manual`.
- **Se 2 ou mais correções tocam o mesmo código, gera primeiro um prompt de investigação com quadro
  de sobreposição** e só depois os prompts de implementação, numa ordem fixa.
- Faz um commit só com os docs, local e sem push.

### 9. Entrega e retomada
Entrega o relatório em linguagem simples, os prompts para as conversas paralelas e o **prompt de
retomada** com "Onde retomamos". Atualiza as mesmas secções no README da bancada.

## Retomar depois de correções feitas noutras conversas
1. Confirma que as correções estão em `main`/`origin` **e a correr em produção**: procura o
   ficheiro ou a função nova dentro do container de cada serviço tocado.
2. Corre a bateria completa com `--prod` e compara-a, cenário a cenário, com a última bateria do
   README.
3. Antes de concluir, procura sobras de outras conversas em produção: eventos de teste na agenda,
   leads de teste, configuração alterada.
4. Valida os checks de produção (`C1`) das implementações correspondentes.
5. Volta à fase 5, ou à 8, ou passa ao teste no WhatsApp real. Esse teste é feito pelo utilizador, a
   partir de um número que nunca falou com a conta.
