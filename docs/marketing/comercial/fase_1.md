FASE 1 — Manual de Execução (Seed Launch)
Consultei hormozi-launch (mecânica da fase), hormozi-closer (estrutura da demo + objeções) e confirmei no código (docs/guia-playground-ui.md) que você já tem uma ferramenta real para fazer a demo — o Playground da Lara (/playground). Isso muda a resposta de teórica para operacional.

🚀 HORMOZI LAUNCH — Por que você precisa de demo (e por que isso é bom)

Princípio: "Manual first, automate second."
Você AINDA não provou que a entrega funciona com cliente real.
A Fase 1 não é sobre vender — é sobre provar demanda E entrega ao mesmo tempo.

Por isso a demo não é opcional: é o próprio mecanismo de prova.
Sem demo, você está vendendo uma promessa. Com demo, você está vendendo
um resultado que o cliente literalmente VÊ acontecer na tela.
Boa notícia: o Bônus 04 da sua oferta (Sandbox Lara) já promete isso. A demo não é trabalho extra — é a entrega do bônus que você já vendeu.

🔧 A FERRAMENTA QUE VOCÊ JÁ TEM — Playground
Confirmei no seu próprio sistema (backend-crm/routes/playground.py + guia em docs/guia-playground-ui.md):


O que é:     Interface em /playground que simula conversas com a Lara
             SEM precisar de WhatsApp real conectado
Como funciona: Você digita COMO SE FOSSE o paciente → a Lara responde
             em tempo real, com o motor de decisão real (não é mockado)
Vantagem:    Leads de sandbox não aparecem no Kanban, não consomem quota —
             você pode simular infinitas vezes sem "sujar" o sistema
Isso resolve seu maior risco de demo: você não depende de configurar WhatsApp do cliente antes de vender. Você demonstra ao vivo, na call, sem nenhuma dependência externa.

Setup ANTES da primeira call (fazer hoje, uma vez só)

1. Acessar /ai-profile e criar um perfil "Híbrido Agendador — Massoterapia"
   → Definir tom de voz, nome do agente, especialização (confirmação de
     sessão, reagendamento, FAQ de horário/preço)

2. Abrir /playground e SIMULAR VOCÊ MESMO antes de mostrar a qualquer cliente:
   → Cenário 1: "Oi, queria saber se tem horário quinta às 15h"
   → Cenário 2: "Desculpa, vou ter que cancelar minha sessão de hoje"
   → Cenário 3 (silêncio de 2 dias, depois): "oi ainda quero remarcar"
   → Cenário 4: "quanto custa a sessão de massagem relaxante?"

3. Ajustar o perfil até as respostas saírem naturais — ISSO é o seu ensaio.
   Nunca faça a primeira simulação durante uma call de vendas.
Regra hormozi-closer: nunca demonstre algo que você não testou pelo menos 3 vezes sozinho primeiro. Falha ao vivo mata a Perceived Likelihood instantaneamente.

🤝 HORMOZI CLOSER — A demo dentro da estrutura CLOSER (15 minutos)
A demo não é um momento isolado — ela vive dentro do S (Sell) do CLOSER, depois que você já fez Clarify e Label. Cronometragem:


┌─────────────────────────────────────────────────────────┐
│ 0–4 min   C + L  → Perguntas diagnósticas (script já no   │
│                     plano tático). Anote as palavras       │
│                     exatas que o cliente usa.              │
│                                                             │
│ 4–6 min   O      → Overview: "quanto isso custa por mês?"  │
│                     Criar o contraste antes de mostrar nada│
│                                                             │
│ 6–11 min  S       → DEMO AO VIVO no /playground            │
│                     (estrutura detalhada abaixo)            │
│                                                             │
│ 11–13 min E       → Objeções (lista completa abaixo)       │
│                                                             │
│ 13–15 min R       → Fechamento + Campanha Fundador          │
└─────────────────────────────────────────────────────────┘
Como estruturar os 6-11 minutos da demo

1. Compartilhe a tela (WhatsApp call com compartilhamento, Zoom, ou Google Meet)

2. Abra o /playground já com o perfil "Híbrido Agendador" carregado

3. Diga ANTES de digitar — não digite calado:
   "Vou simular um paciente seu agora. Olha o que acontece."

4. Digite EM TEMPO REAL (não copie/cole pronto — a espontaneidade importa):
   → Mensagem 1: pergunta de horário (mostra resposta instantânea)
   → Mensagem 2: pedido de cancelamento (mostra como ela conduz
     o reagendamento sem perder a sessão)

5. Use a PALAVRA EXATA que o cliente disse no Clarify.
   Se ele disse "eu esqueço de confirmar com quem sumiu" → simule
   exatamente esse cenário na hora. Isso é "Sell the Vacation":
   resolver o problema DELE, não um problema genérico.

6. NÃO mostre o painel de "trace" (decision_trace, guardrails) —
   isso é debug técnico, não significa nada pro massoterapeuta e
   quebra o ritmo emocional da demo.

7. Encerre com uma frase ponte direto pro Explain:
   "É isso que ela faz pelos seus pacientes, 24 horas por dia,
   sem você tocar em nada. Faz sentido?"
🛡️ OBJEÇÕES — Lista completa (técnica Isolate & Overcome)
A técnica do hormozi-closer é sempre isolar antes de resolver: confirmar que aquela é a ÚNICA barreira antes de gastar energia resolvendo. Caso contrário você resolve uma objeção e uma nova aparece.


Padrão de isolamento (usar SEMPRE antes de responder):
"Entendo. Só pra eu não perder seu tempo — fora isso, tem mais
alguma coisa que te impediria de começar, ou é só essa questão?"
As 4 objeções universais
Objeção	Superfície	Real	Isolamento + Resposta
Preço	"Tá caro"	"Não tenho certeza que vale"	"Se você tivesse certeza que funciona, R$147 seria um problema?" → [Se não] → "Então a questão real é confiança no resultado, não o preço. Por isso a garantia dupla existe: se em 30 dias não eliminar 1 falta, devolvo tudo."
Tempo	"Não tenho tempo agora"	"Tenho medo de mais uma coisa pra gerenciar"	"Faz sentido — mas é o contrário: hoje você gasta tempo confirmando manualmente. A Lara devolve esse tempo. O Bônus 01 (Ativação Dia 1) significa que EU configuro, você só aprova."
Consultar alguém (sócio/parceiro)	"Preciso pensar/falar com alguém"	"Não estou 100% convencido ainda"	"Entendo. O que você acha que essa pessoa ia perguntar primeiro? [Responder isso agora]. Se isso estivesse resolvido, você fecharia hoje?"
Já me decepcionei antes	"Já tentei chatbot e foi horrível"	"Tenho medo de pagar de novo por algo que não funciona"	"Por isso te mostrei rodando AO VIVO, não um vídeo institucional. E por isso a garantia incondicional existe — o risco não é seu."
Objeções específicas do nicho (massoterapia)
Objeção	Isolamento	Resposta
"Meus pacientes são mais velhos, não usam tanto WhatsApp"	"Fora a idade dos pacientes, mais alguma coisa te preocupa?"	"97% dos brasileiros usam WhatsApp, em todas as idades. E ela manda áudio também, não só texto — muitos pacientes mais velhos preferem ouvir."
"Meu atendimento é pessoal, não quero parecer 'empresa grande'"	"Fora isso, mais alguma dúvida?"	"É exatamente o oposto — você define o tom, o nome, a forma de falar. Os pacientes recebem mensagem como se fosse você mesma respondendo, só que mais rápido e sem esquecer ninguém."
"Tenho poucos pacientes, não sei se compensa"	"Fora o volume atual, mais alguma coisa?"	"Justamente por ter poucos pacientes, cada falta pesa mais. Perder 1 sessão de R$200 já é mais do que o investimento de R$147. E a base qualificadora da oferta já considera isso — funciona a partir de 20 leads/mês."
"Não confio em deixar IA falando com meus pacientes sem supervisão"	"Fora a supervisão, mais alguma coisa?"	"Você tem o Sandbox pra testar à vontade antes de ativar com pacientes reais. E o Handoff Inteligente transfere pra você automaticamente quando o assunto sai do escopo dela."
Pergunta de fechamento pós-objeção (sempre)

Depois de resolver QUALQUER objeção:
"Isso resolve sua dúvida? Então, prefere ativar hoje ou na sessão
de onboarding de quinta?"
Nunca termine uma resposta de objeção sem reabrir o fechamento — senão você "ganha" o argumento e perde a venda por falta de próximo passo.

📋 CHECKLIST OPERACIONAL — O que fazer, nesta ordem exata

[ ] 1. Criar AI Profile "Híbrido Agendador — Massoterapia" em /ai-profile
[ ] 2. Testar VOCÊ MESMO no /playground — mínimo 4 cenários (lista acima)
[ ] 3. Ajustar tom/respostas até sair natural — repetir até confiar 100%
[ ] 4. Mandar mensagem de voz para o professor (script já no plano tático)
[ ] 5. Agendar a call — bloquear 20 min reais (15 de demo + 5 de buffer)
[ ] 6. Antes da call: abrir /playground, deixar a aba já carregada
[ ] 7. Durante a call: seguir cronometragem CLOSER (C+L → O → S/demo → E → R)
[ ] 8. Pós-call (independente do resultado): anotar objeções reais ouvidas
      → isso refina a lista de objeções acima com dados reais, não suposição
🐝 HORMOZI CHIEF — Resumo da resposta às suas dúvidas

"Vou precisar fazer demo?"        → SIM. É o bônus Sandbox que você já vendeu.
                                     Sem ela, Perceived Likelihood não sobe.

"Como faço a demo?"                → /playground — já existe, já funciona,
                                     não depende de WhatsApp real do cliente.

"Quais ações nesta fase?"          → Setup do AI Profile (1x) → outreach
                                     (professor + ex-clientes) → call de 20min
                                     com CLOSER → fechamento → pedir indicação.

"Quais objeções vou enfrentar?"    → 4 universais + 4 específicas do nicho,
                                     todas com isolamento antes da resposta.
Próxima ação concreta: monte o AI Profile e teste sozinho no Playground hoje — antes de mandar qualquer mensagem para o professor. Sem esse passo, você corre o risco de demonstrar algo que falha ao vivo na primeira call real.