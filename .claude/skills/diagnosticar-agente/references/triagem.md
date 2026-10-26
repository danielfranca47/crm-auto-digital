# Triagem de falhas — de onde vem cada comportamento errado

Antes de mexer na configuração, classifica a falha. A mesma resposta errada pode ter 5 causas, e só
uma delas se resolve com instruções.

| Classe | Sinal típico | Onde confirmar | Destino |
|---|---|---|---|
| **Modelo** | A resposta cai na frase de recurso de handoff; `llm_failure`/`child_validate` nos logs; valores fora do enum (ex.: a fase escrita em português) | logs do executor (local: `ambiente/executors.log`; produção: `railway logs -s "worker backend-executors"`) | trocar `llm_provider`/modelo (configuração) e, se persistir, plans (validação tolerante) |
| **Configuração** | A IA faz o que as instruções dizem, mas as instruções estão erradas, incompletas ou contraditórias | ler o prompt efetivo da fase (`decision_engine._build_child_prompt_<fase>`) com o perfil da bancada | nova versão `cNN` |
| **Configuração morta** | A instrução existe, mas a IA age como se não existisse | confirmar que o campo/bloco **chega** à fase: ver a tabela abaixo e o código | mover a instrução para um campo que chega; se nenhum chegar, é código |
| **Código** | A IA recebe a informação certa e o sistema estraga o resultado (grava outra data, compara mal, ignora o candidato); ou 3 formulações não resolvem | `decision_trace`, `appointment_event`, guardrails aplicados e código do guardrail/serviço | plans ou implementations |
| **Dados da conta** | Base de Conhecimento errada, agenda com eventos reais, Google sem permissão, mídia partida | snapshot, `prod_turno.py sync`/`conhecimento`, scopes do token | pedir à conta ou ao utilizador para corrigir |
| **Negócio** | Duas respostas possíveis e as conversas não dizem qual é a certa | conversas, site | pergunta ao utilizador com uma opção recomendada |

## O que chega a cada fase (verificar sempre no código)

O mapa geral está em `docs/architecture/pipeline-phases.md` ("Campos do AI Profile que chegam ao
LLM") e `docs/architecture/sales-flow.md` ("Fases (p0–p5)"). Os mais traiçoeiros:

- **Blocos `orientacao` do Fluxo de Venda:** chegam só às fases em que `_build_child_prompt_<fase>()`
  chama `_build_sales_flow_phases_block`. Confirma com grep no `decision_engine.py`; houve fases
  (pré-agendamento e agendamento) que não liam o Fluxo.
- **`custom_instructions`:** chega a todas as Filhas, mas compete com os roteiros fixos de cada fase.
  Quando um roteiro do código manda o contrário, normalmente vence o roteiro.
- **Campos de topo vs. `offer_pack`:** o ecrã grava alguns campos dentro de `offer_pack`, e o motor
  lê a coluna de topo (ver `docs/architecture/agents.md`, "Persistência via frontend-crm"). Confirma
  qual é que o motor lê.
- **Blocos `condicao` (ramificação):** a Mãe tem de escolher um caminho. Se nunca escolhe, as ações
  desse ramo nunca correm. Um `intent_trigger` com uma nota clara costuma ser mais fiável.
- **Campos com duplo sentido:** um campo lido com dois significados (ex.: "disponibilidade" como
  janela de resposta e como horário do profissional) faz a IA usar o significado errado.
- **Fases inativas para o `agent_mode`:** os blocos aí configurados nunca são avaliados.

Quando o doc e o código divergirem, vale o código. Corrige o doc (é a exceção permitida à regra "sem
código") e regista a correção no relatório.

## Procedimento para uma falha nova

1. Lê o `.json` desse turno: `mother_decision`, `child_result`, `decision_trace`
   (`mother_route → effective_route`, `guardrails_applied`, `missing_fields`), `appointment_event`
   e `auto_items`.
2. Se houver handoff de recurso ou uma resposta vazia, vai aos logs (classe Modelo).
3. Reproduz a falha 2 a 3 vezes com o mesmo cenário. Uma falha que não se repete mede-se em taxa
   antes de se corrigir.
4. Vê se `git log` ou uma worktree em curso já a corrige.
5. Classifica-a, escreve uma linha no README ("falha → classe → evidência → destino") e só depois
   age.
