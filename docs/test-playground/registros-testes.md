## Propósito

O propósito deste documento é anotar os comportamentos indesejados que estou tendo durante os testes. Este arquivo foi escrito por quem não entende de programação, mas que vai dar um feedback do comportamento atual vs desejado através dos testes do playgrond.

Este documento será útil para Daniel reler e revisar o aprendizado do funcionamento do sistema e acumular um histórico de comportamentos corrigidos e estado atual. 

## Quem irá atuar aqui:
- Daniel = É quem registra as anotações de testes e dá os feedbacks.
- Claude = Responsável por dar as explicações lógicas de maneira leiga e possibilidades de correções. 



## Testes:

## Teste dia 21/04/26 as 17:25

### Daniel:
- Problema identificado: Roteamento indesejado.

gostaria de fazer um diagnóstico do por que a llm mae está tomando decisões indesejadas para seu comportamento ideal de vendas. 

Este foi o teste que fiz. Quero que me apresente e justifique de maneira leiga o porque: 

- A mãe rotear a "mother_route": "qualification" e "effective_route": "apresentation" . 

Por que dois campos diferentes? Apenas explique-me sem fazer alterações no código. Que lógica que está configurada que leva a isto . É o sistema, guardrails, prompt , etc?

### Claude
Por que mother_route e effective_route são diferentes?
A metáfora
Imagine que o sistema tem dois funcionários:

A Mãe (LLM) — uma IA que lê a conversa e decide: "o que devo fazer agora?"
O Guardrail (código) — um supervisor automático que revisa a decisão da Mãe e pode vetar ou corrigir com base em regras de negócio fixas
O mother_route é o que a Mãe decidiu. O effective_route é o que o supervisor deixou passar (ou trocou).

O que aconteceu na mensagem 3
O lead disse: "quero experimentar a massagem relaxante de 45 min"

A Mãe viu: o campo de qualificação configurado (custom_precos_de_massagens) ainda estava na lista de campos a preencher no momento em que ela montou seu raciocínio. Então ela disse: "route = qualification" — faça mais uma pergunta de qualificação.

O supervisor rodou logo depois e percebeu: "espera — depois de analisar a mensagem do lead, não há mais nenhum campo faltante. A frase 'relaxante de 45 min' preencheu o campo de preferência de serviço/preço."

A regra é explícita no código (decision_engine.py:2955):


Se mãe disse "qualification" E não há campo faltante → override para "apresentation"
Então o supervisor trocou: effective_route = apresentation.

Por que a Mãe não viu isso sozinha?
Porque a Mãe recebe um "snapshot" do estado montado antes dela rodar. A extração automática dos campos (que detectou que o lead preencheu a preferência) acontece depois que a Mãe já tomou sua decisão. É uma questão de ordem de execução: a Mãe decide, depois o sistema extrai dados da mensagem, depois o supervisor compara e pode corrigir.

Resumo visual

Mensagem do lead
   ↓
[A Mãe lê o contexto antigo]  →  mother_route = "qualification"
   ↓
[Extração de campos da mensagem]  →  missing_fields = [] (vazio!)
   ↓
[Guardrail verifica]  →  "Mãe disse qual, mas não há campos faltantes"
   ↓
effective_route = "apresentation"  ← o que o bot realmente executa

---
## Sugestão de ajustes do claude:
Fix 1 — Ensinar o sistema a reconhecer "quero experimentar" como intenção de agendamento
O que existe hoje
O sistema tem uma lista de palavras-chave que definem intenção de agendamento leve (sem data confirmada). Quando detecta essas palavras numa mensagem, classifica como "o lead quer agendar, mas ainda não disse quando".

A lista atual (decision_engine.py:2732):


"vou ver", "vou tentar", "quero ir", "pretendo ir", 
"semana que vem", "quero sim", "tenho interesse", ...
O problema
A frase "quero experimentar a massagem relaxante" não tem nenhuma dessas palavras. O sistema não a reconhece como intenção de agendamento — lê como uma frase neutra.

O que muda
Adicionar à lista:


"quero experimentar", "quero tentar", "quero fazer a",
"vou experimentar", "gostaria de experimentar"
Efeito prático
Quando o lead disser "quero experimentar a massagem relaxante", a função _has_soft_scheduling_intent() passa a retornar True. Esse sinal é usado pelo Fix 2.

Fix 2 — Corrigir o guardrail que decide para onde vai depois da qualificação
O que existe hoje
Depois que a extração preenche o último campo faltante, existe um guardrail automático que diz:

"A Mãe disse qualification, mas não tem mais campos faltando — então promovo para apresentation."

Esse guardrail (decision_engine.py:2955) sempre vai para apresentation, sem verificar se a mensagem do lead indica intenção de agendamento.


# HOJE
if mother_decision.route_to == "qualification" and not current_field:
    effective_route_to = "apresentation"  ← sempre apresentation
    suggested_category = "apresentation"
O problema
"Quero experimentar a massagem de 45 min" completa a qualificação e demonstra intenção de agendar. Mas o guardrail manda para apresentation como se fosse uma pergunta de serviço normal, em vez de ir para pre-agendamento (etapa em que o bot pede o horário).

O que muda
O guardrail passa a verificar se a mensagem tem intenção de agendamento antes de decidir o destino:


# DEPOIS (simplificado)
if mother_decision.route_to == "qualification" and not current_field:
    if agente_de_agendamento AND sinal_forte_de_agendamento:
        effective_route_to = "agendamento"      ← lead deu dia/hora concretos
    elif agente_de_agendamento AND sinal_leve_de_agendamento:
        effective_route_to = "pre-agendamento"  ← lead escolheu serviço, sem data
    else:
        effective_route_to = "apresentation"    ← caso genérico, sem intenção de agendar
Efeito prático
"Quero experimentar a massagem relaxante de 45 min":

Fix 1 → detecta como sinal leve (soft_intent = True)
Fix 2 → ao completar qualificação, vai para pre-agendamento em vez de apresentation
Bot de pre-agendamento: "Para a massagem relaxante de 45 min, qual horário fica melhor para você?"
Fix 3 — Atualizar o "manual de instruções" da LLM Mãe
O que existe hoje
A Mãe recebe um prompt com as definições de cada rota. A definição de pre-agendamento hoje é (decision_engine.py:1190):

"Lead demonstra interesse tentativo sem data confirmada. Ex.: 'quero ir sim, vou tentar semana que vem', 'vou ver pra próxima semana'."

O problema
Todos os exemplos são de indecisão ("vou ver", "talvez"). A Mãe aprendeu que pre-agendamento = hesitação. Quando um lead confirma escolha de serviço sem dar data, a Mãe não associa isso a pre-agendamento — classifica como apresentation ou qualification.

O que muda
Acrescentar exemplos de seleção de serviço na definição:


PRÉ-AGENDAMENTO: lead demonstra interesse TENTATIVO sem data confirmada.
Inclui também: "quero experimentar [serviço]", "vou com a [serviço]",
"quero fazer a massagem X" — serviço escolhido, mas sem dia/hora.
Não confundir com dúvida sobre o serviço (essas vão para apresentation).
Efeito prático
Este fix é o que garante que — em situações onde a qualificação já estava completa desde a mensagem anterior — a Mãe roteie corretamente por conta própria, sem depender do guardrail do Fix 2 para corrigir.

Resumo visual dos 3 fixes trabalhando juntos

Lead: "quero experimentar a massagem relaxante de 45 min"
        │
        ▼
Fix 1: Detecta "quero experimentar" → soft_intent = TRUE
        │
        ▼
Mãe lê missing_fields=["custom_precos"] → força "qualification"
Extração LLM → preenche campo → missing_fields=[]
        │
        ▼
Fix 2: Guardrail vê missing_fields=[] + soft_intent=TRUE
       → effective_route = "pre-agendamento"  (não mais "apresentation")
        │
        ▼
Filha de pre-agendamento responde:
"Para a massagem relaxante de 45min, qual horário fica melhor?"
        │
        ▼
Lead diz "amanhã às 15h" → Fix 3 ajuda a Mãe a ir direto para "agendamento"
Fix 1 é o sensor (detecta a intenção), Fix 2 é a decisão (usa o sensor para rotear certo), Fix 3 é o aprendizado da Mãe (para casos futuros sem depender do guardrail).

## Argumentos Daniel:

sobre o fix 1: Não quero mais depender de palavras engessadas para tomar decisões de roteamento, pois no sistema terão muitos usuários de nichos e idiomas diferentes, nao vale a pena cadastrar todas as expressões do mundo para todos os nichos. Temos um problema crítico aqui.
Sugira uma solução inteligente,

Sobre fix 2: 
Assim como existe um guardrail para dizer que não ha mais nada pendente em qualificação. Não podemos criar um "guardrail" ou ajustar o existente para também reconhecer que a apresentação já foi feita e não há mais nenhuma pendência ali? Assim passaria automaticamente para pré-apresentação? Aqui se trata de em vez de captação de palavras uma questão lógica de fluxo, correto?

Sobre o fix 3: 
Prompt da mãe:

Além da linha do prompt para pré agendamento ser super curta eu vejo que o prompt contextualizado é muito abrangente e não aparenta envolver a especificidade das informações de ai-profile do usuário . 

Na própria introdução ele diz: Você é um roteador mae de um crm de vendas. Ele poderia dizer: Você é um supervisor de vendas de empresa [nicho do usuário] que vende [produto/serviço do usuário] . Sua missão é perceber o estado atual de cada cliente com base no estado atual da venda que ele se encotra. 
- Seria abordado o tipo de agente, estilo, tom de voz ( Tudo conforme ai-profile) 
- Seria ensinado as fases da pipeline configurado naquele agente.
- Seria dado exemplos não com palavras , mas com lógica de intenção dos leads e lógica de fluxo. 

Resume-se em ensinar o colaborador a trabalhar. Com prompt dinâmico acionando o necessário para cada template key. 

O agente 1 sdr padrao seria abordado a pipeline dele mais complexa e com as configurações e preferencias do ai profile.
Mesmo vale para o agente 2 closer agressivo e 3 hybrid_scheduler. 

Assim teríamos uma llm mais inteligente e um sistema que nao depende de palavras padroes engessadas. mas um verdadeiro profissional a cargo e inteligente para tomar as decisões de vendas. Percebe?

## Implementações
branch : etapa-8-5-ajustes
5c20308dfbf8bf4e80397c30ccef004c52a4a1b5

Aqui está o resumo do que foi implementado:

O que mudou em decision_engine.py:

_build_mother_identity_block() (nova) — a Mãe agora se apresenta como supervisora do negócio específico. Para a Cristina: "Você é supervisora de vendas da Cristina, um negócio no nicho de Massagens. Seu público-alvo: Homens e Mulheres de 30 a 65 anos. Tom: discreto, sutil meiga e persuasivo."

_build_mother_pipeline_block() (nova) — injeta as fases do funil em linguagem de negócio, específicas por template. Para hybrid_scheduler, o pré-agendamento agora tem a definição clara: "cliente fez uma escolha concreta de serviço... mas NÃO mencionou data. Não confundir com dúvida: dúvida vai para apresentação. Escolha feita vai aqui." — sem depender de palavras-chave.

_build_mother_prompt() (refatorada) — usa os dois helpers acima, injeta custom_instructions do AI Profile diretamente no prompt, expande ai_summary com brand_name, offer_description, goals e custom_instructions, e as regras de Prioridade 2 passam a descrever intenção lógica em vez de frases específicas.

Guardrail de apresentação (novo em compose_decision_output) — quando a Filha sinaliza did_complete_phase=True com recommended_next_category, o sistema avança automaticamente para pre-agendamento/agendamento/follow-up, fechando o mesmo loop lógico que já existia para qualificação.

Próximo passo: testar no playground com o perfil da Cristina — a mensagem "quero experimentar a massagem relaxante de 45 min" deve agora gerar mother_route=pre-agendamento diretamente

----

## Dia 22/08/26 

Testes após atualização anterior:

após as atualizações de ontem que fizemos em 5c20308dfbf8bf4e80397c30ccef004c52a4a1b5 eu declarei no histórico em C:\crm-auto-digital\docs\test-playground\registros-testes.md 

Estou agora tentando refazer o testes em playground. O resultado partilhei no documento.

Coisas que eu não gostei foi novamente a resposta não está vindo bem na saudação:
1- Ofereceu já a tabela de preços sendo que nao respondeu a saudação. 

2- Quando disse a massagem que gostaria de experimentar ou perguntei os horários que poderia marcar ele continuou mandando as tabelas de preços com uma mensagem aparentemente padronizada. De onde está vindo essa mensagem e por que ela se repete tanto?

3- Somente quando disse o horário ela redirecionou para agendamento, quando o correto seria no momento em que eu demosntrei o interesse em experimentar, mesmo que a mãe considere em qualificação, a filha de qualificação precisa ter a habilidade de reconhecer o interesse do cliente e preparar  uma resposta mais elaborada como capturar o dia e horario que o cliente pode e sugerir os 2 horarios para hoje. 

4- Penso que assim como fizemos uma restruturação no prompt da mãe podemos rever os prompts das filhas e ensinar quem elas são de verdade com prompts dinamicos, lógica do negócio, elas não seriam mais só "filhas" , mas seriam chamadas da "profissional" que caiba a elas de acordo com o template key do agente e o ai-profile de cada usuário.

5- Seria necessário também colocar uma regra ou lógica para não enviar a tabela repetidas vezes

6- Garantir que ela tenha acesso ao histórico das mensagens, compreenda o processo de vendas

7-  tenha acesso a base de conhecimento do ai-profile não para "copiar e colar" e seja repedidamente enviado, mas para lhe servir como conhecimento para ela aplicar no seu trabalho.

### Plano de Correção do Claude:
Reestruturação das LLMs Filhas — Personas Dinâmicas e Comportamento Corrigido
Contexto
Após o commit 5c20308 que tornou o prompt da mãe dinâmico por template_key e ai_profile, os testes em playground revelaram 6 problemas comportamentais nas LLMs filhas:

Bot respondeu à saudação com tabela de preços, ignorando o cumprimento
Enviou a tabela de preços/imagens repetidas vezes (sem deduplicação de mídia)
Não reconheceu interesse concreto em serviço como sinal de pré-agendamento
Daughters têm prompts estáticos, sem identidade derivada do negócio (niche, custom_instructions, template_key)
Knowledge base é "copiada e colada" no texto, não usada como conhecimento de fundo
Mothers já têm identidade dinâmica — Daughters precisam do mesmo tratamento
Arquivos Críticos
Arquivo	Papel
backend-executors/app/services/decision_engine.py	Prompt builders de todas as filhas (~3860 linhas)
backend-crm/services/ai_orchestrator/orchestrator.py	Monta ContextBundle, carrega history e knowledge_media
backend-crm/services/ai_playbooks/__init__.py	Definições de playbook por template_key
Mudanças Planejadas
1. Bloco de Identidade Dinâmica para as Filhas (decision_engine.py)
Criar _build_daughter_identity_block(ctx) — análogo ao _build_mother_identity_block() já existente.

Conteúdo do bloco:

Você é [name/persona contextual por template_key]:
  - hybrid_scheduler: "Você é [ai_profile.name], [niche] em [localização se disponível], falando diretamente com o cliente."
  - sdr_padrao: "Você é assistente de vendas da [brand_name]."
  - consultor_especialista: "Você é consultor(a) especialista de [brand_name]."
  - closer_agressivo: "Você é vendedor(a) direto(a) da [brand_name]."

Tom: [tone_of_voice]
Nicho: [niche]
Público-alvo: [target_audience]
Fase atual: [phase_name_human_readable]

INSTRUÇÕES DO NEGÓCIO (máxima prioridade):
[ai_profile.custom_instructions]
Injetar este bloco no início de cada prompt builder de filha:

_build_qualification_prompt()
_build_apresentation_prompt()
_build_followup_prompt()
_build_closing_prompt()
2. Knowledge Base como Conhecimento de Fundo (decision_engine.py)
Problema atual: knowledge items são injetados como conteúdo a ser enviado textualmente.

Mudança: alterar o cabeçalho e a instrução de uso nos builders de filhas:

# ANTES
"CONTEÚDO PARA USAR:\n{knowledge_text}"

# DEPOIS
"BASE DE CONHECIMENTO (use como referência — nunca copie textualmente):
{knowledge_text}

Regras de uso:
- Responda com suas próprias palavras, de forma natural e contextual
- Não repita informações que já foram mencionadas no histórico
- Só traga informações relevantes à mensagem atual do cliente"
3. Deduplicação de Mídia (orchestrator.py + decision_engine.py)
Onde implementar: em orchestrator.py, função que monta/enriquece o ContextBundle.

Lógica:

Percorrer history (já disponível no bundle) buscando URLs de mídia nos campos body (padrão: URLs de imagem na mensagem do bot)
Construir already_sent_media_urls: Set[str]
Adicionar ao metadata do ContextBundle
No decision_engine.py:

Na etapa de composição de pre_send_media, filtrar qualquer URL já presente em already_sent_media_urls
Regra adicional: nunca enviar mídia em turno de saudação (quando next_action_hint == "greet").

4. Tratamento Correto de Saudação (decision_engine.py)
Na _build_qualification_prompt():

Adicionar instrução condicional baseada em next_action_hint:

Se next_action_hint == "greet":
- PRIORIDADE MÁXIMA: responda ao cumprimento de forma calorosa e natural ANTES de qualquer outra ação
- NÃO faça perguntas de qualificação neste turno
- NÃO mencione preços, serviços ou tabelas
- Apenas acolha o cliente e convide-o a falar
5. Reconhecimento de Interesse Concreto pelas Filhas (decision_engine.py)
Problema: quando lead diz "quero experimentar a massagem X" ou "que horas posso marcar?", a filha de qualification/apresentation envia mensagem padronizada em vez de engajar com o interesse.

Na _build_qualification_prompt() e _build_apresentation_prompt():

Adicionar instrução de reconhecimento de intenção de agendamento:

RECONHECIMENTO DE INTENÇÃO DE AGENDAMENTO:
Se o cliente demonstrou interesse concreto em um serviço específico OU perguntou sobre disponibilidade/horários:
- NÃO continue o fluxo de qualificação padrão
- Reconheça o interesse com naturalidade
- Pergunte sobre data/horário preferencial de forma direta
- Sinalize did_complete_phase=true com recommended_next_category="pre-agendamento"

Exemplos que indicam essa intenção:
- "quero [serviço específico]"
- "que horas posso marcar?"
- "tem disponibilidade [dia/período]?"
- "quero agendar"
6. Anti-repetição de Conteúdo (decision_engine.py)
Adicionar instrução global em todos os builders de filha:

REGRA ANTI-REPETIÇÃO:
- Leia o histórico antes de responder
- Não repita informações, frases ou conteúdo já enviados nesta conversa
- Não envie a mesma mídia ou imagem mais de uma vez
- Cada resposta deve avançar a conversa, não repetir o mesmo passo
Escopo de Mudanças por Arquivo
backend-executors/app/services/decision_engine.py
 Criar _build_daughter_identity_block(ctx) (nova função)
 Modificar _build_qualification_prompt() — adicionar identity block, knowledge como fundo, greeting handler, interesse de agendamento, anti-repetição
 Modificar _build_apresentation_prompt() — idem
 Modificar _build_followup_prompt() — adicionar identity block, knowledge como fundo
 Modificar _build_closing_prompt() — adicionar identity block
 Filtrar pre_send_media por already_sent_media_urls e next_action_hint == "greet"
backend-crm/services/ai_orchestrator/orchestrator.py
 Extrair URLs de mídia já enviadas do histórico
 Adicionar already_sent_media_urls ao metadata do ContextBundle
Estratégia de Não-Quebrar
_build_daughter_identity_block() com fallbacks graceful para todos os campos opcionais do ai_profile
Deduplicação é additive (filtra a mais, não altera estrutura de dados)
Não alterar schema do ContextBundle — usar metadata dict existente para already_sent_media_urls
Não alterar retorno do decision engine — mesmo schema JSON
Verificação
Saudação: playground com "ola bom dia" → bot responde ao cumprimento, sem imagens, sem preços
Interesse concreto: "quero a massagem X" → bot reconhece, pede horário; did_complete_phase=true no trace
Mídia não repetida: segunda mensagem não reenvia imagens já enviadas
Knowledge como fundo: respostas usam palavras próprias baseadas no conhecimento, sem copiar texto
Identidade da profissional: trace e resposta refletem o nome/niche/tom do ai_profile, não identidade genérica
Custom instructions respeitadas: regras do ai_profile.custom_instructions aplicadas (ex.: não dizer "Posso ajudar")

