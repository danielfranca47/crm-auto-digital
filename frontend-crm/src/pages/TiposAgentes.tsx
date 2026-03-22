import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { OrionShell } from '@/components/agente/OrionShell';

// ─── Tipos ───────────────────────────────────────────────────

type AgentId = 'a1' | 'a2' | 'a3';

interface QCard    { label: string; text: string }
interface TempCard { cls: 'hot' | 'warm' | 'cold' | 'done'; label: string; desc: string }
interface Bullet   { text: string }

interface Stage {
  icon: string;
  title: string;
  who: 'bot' | 'human' | 'collab';
  desc: string;
  bullets?: Bullet[];
  qCards?: QCard[];
  tempCards?: TempCard[];
  diffNote?: string; // comportamento específico no outbound — exibido no card expandido
}

interface AgentData {
  id: AgentId;
  chip: string;
  title: string;
  subtitle: string;
  desc: string;
  analogy: string;
  useCases: string[];
  splitIn: Stage[];    // etapas exclusivas do fluxo inbound
  splitOut: Stage[];   // etapas exclusivas do fluxo outbound
  mergeLabel: string;  // rótulo do ponto de convergência
  shared: Stage[];     // etapas compartilhadas pós-convergência
}

interface QuizOption   { label: string; agent: AgentId }
interface QuizQuestion { q: string; hint: string; options: QuizOption[] }
interface FaqItem      { q: string; a: string }
interface GlossItem    { term: string; def: string }

// ─── Dados dos agentes ────────────────────────────────────────

const AGENTS: AgentData[] = [
  {
    id: 'a1',
    chip: 'Agente 01 · Robusto',
    title: 'SDR de Alto Ticket',
    subtitle: '+ Follow-up Pós-Apresentação',
    desc: 'Qualifica profundamente antes de acionar o humano. A jornada diverge conforme a origem do lead: inbound entra pela dor já declarada; outbound entra pelo perfil presumido. Após o Filtro 3, ambos os caminhos são idênticos.',
    analogy: 'Imagine que você vende consultoria empresarial. O lead preenche o formulário do seu site. O agente verifica se a empresa tem o porte certo, descobre qual problema quer resolver, pergunta se há verba e quem toma a decisão. Só depois disso ele agenda a reunião com você — e te manda um resumo completo antes do encontro.',
    useCases: ['Imóveis · Advocacia', 'Clínicas estéticas', 'Consultorias B2B', 'Ciclo longo · Alto ticket'],
    splitIn: [
      { icon: 'IN', title: 'Entrada do Lead — Dor Declarada', who: 'bot',
        desc: 'O lead chega via formulário, anúncio ou link direto. Demonstrou interesse — sinal de dor ativa.',
        bullets: [
          { text: '<strong>Mensagem de boas-vindas:</strong> tom consultivo — "Obrigado pelo interesse! Para entender melhor como posso ajudar..."' },
          { text: '<strong>Registro de origem:</strong> qual campanha, anúncio ou keyword trouxe o lead.' },
          { text: '<strong>Captura da dor inicial:</strong> se o formulário já trouxe essa info, usa sem repetir a pergunta.' },
        ]},
      { icon: 'F1', title: 'Filtro 1 — Validação de Fit / Perfil', who: 'bot',
        desc: 'Como a dor já existe, o primeiro passo é verificar se o lead tem o perfil certo. Sem fit, não adianta aprofundar. 2–3 perguntas rápidas.',
        bullets: [
          { text: '<strong>Dados binários:</strong> faturamento, setor, porte, localização — confirmação ou descarte imediato.' },
          { text: '<strong>Score de fit automático:</strong> abaixo do mínimo — encerra gentilmente ou encaminha para nurture.' },
        ],
        qCards: [
          { label: 'Exemplo', text: '"Só para garantir que posso te ajudar da forma certa — sua empresa atua em qual setor?"' },
          { label: 'Exemplo', text: '"Vocês faturam acima de R$ 100 mil/mês atualmente?"' },
        ]},
    ],
    splitOut: [
      { icon: 'OUT', title: 'Prospecção Ativa — Fit Presumido', who: 'bot',
        desc: 'O agente inicia contato com leads selecionados por perfil externo. O Fit básico já foi presumido na seleção.',
        bullets: [
          { text: '<strong>Abordagem contextualizada:</strong> usa dados do lead (setor, cargo, empresa) para criar relevância.' },
          { text: '<strong>Sequência multi-canal:</strong> WhatsApp → e-mail → LinkedIn com espaçamento de 2–3 dias.' },
          { text: '<strong>Limite de tentativas:</strong> máximo configurável (ex: 4 touchpoints) antes de arquivar.' },
        ]},
      { icon: 'F2', title: 'Filtro 2 — Investigação de Dor', who: 'bot',
        desc: 'O lead não estava procurando por você — precisamos identificar ou despertar a dor. Perguntas abertas que instigam reflexão.',
        bullets: [
          { text: '<strong>Perguntas de escavação:</strong> "Como vocês estão lidando com X hoje?" / "Esse problema já custou oportunidades?"' },
          { text: '<strong>Desvio de escopo:</strong> se a dor não bate com a oferta, encerra educadamente.' },
        ],
        qCards: [
          { label: 'Despertar dor', text: '"Empresas do seu setor costumam ter dificuldade com X — isso é algo que vocês também enfrentam?"' },
          { label: 'Escavar impacto', text: '"Quanto tempo ou recurso vocês gastam hoje tentando resolver isso manualmente?"' },
        ]},
      { icon: 'F1', title: 'Filtro 1 — Reforço e Confirmação de Fit', who: 'bot',
        desc: 'Dor confirmada. O agente valida o fit com precisão — os dados presumidos na lista podem estar desatualizados.',
        bullets: [
          { text: '<strong>Confirmação de dados:</strong> verifica faturamento, porte, tomador de decisão — de forma natural.' },
          { text: '<strong>Descarte tardio:</strong> leads que passaram da dor mas falham no fit real são descartados aqui.' },
        ]},
    ],
    mergeLabel: 'Caminhos convergem → Filtro 3',
    shared: [
      { icon: 'F3', title: 'Filtro 3 — Poder, Prioridade, Preço, Timing', who: 'bot',
        desc: 'Qualificação profunda. O agente descobre quem decide, se é prioridade agora, se há verba e quando precisam resolver. Score abaixo do mínimo → nurture. Acima → agenda.',
        diffNote: 'No outbound, chegamos ao F3 com Dor e Fit já confirmados — o foco é verificar viabilidade de avanço imediato.',
        qCards: [
          { label: 'Poder',      text: '"Além de você, quem mais costuma participar da análise de soluções como essa?"' },
          { label: 'Prioridade', text: '"O que acontece com suas metas se esse problema não for resolvido nos próximos 60 dias?"' },
          { label: 'Preço',     text: '"Vocês já separaram uma verba para isso, ou ainda está em definição?"' },
          { label: 'Timing',    text: '"Existe alguma data ou evento que exige ter isso resolvido até lá?"' },
        ]},
      { icon: 'AG', title: 'Agendamento + Handoff para Humano', who: 'collab',
        desc: 'Lead aprovado nos filtros. O bot agenda a reunião e monta o dossiê completo para o vendedor.',
        diffNote: 'No outbound, o dossiê inclui também: canal de prospecção, touchpoints anteriores e dor despertada no F2.',
        bullets: [
          { text: '<strong>Calendário integrado:</strong> horários disponíveis em tempo real, confirmação automática.' },
          { text: '<strong>Dossiê automático:</strong> nome, empresa, dor declarada, score dos 4Ps, canal de origem.' },
          { text: '<strong>Lembretes ao lead:</strong> 24h e 1h antes da reunião para reduzir no-shows.' },
        ]},
      { icon: 'AP', title: 'Apresentação Comercial', who: 'human',
        desc: 'O vendedor conduz a reunião. O bot fica pausado. Após a apresentação, o vendedor registra a temperatura do lead no CRM — esse input ativa o fluxo certo de follow-up.',
        bullets: [
          { text: '<strong>Status pós-reunião:</strong> Quente / Morno / Frio / Perdido — cada status aciona um fluxo diferente.' },
          { text: '<strong>Proposta enviada?</strong> Flag que define se o follow-up referencia a proposta ou retoma a apresentação.' },
        ]},
      { icon: 'FU', title: 'Follow-up Pós-Apresentação por Temperatura', who: 'bot',
        desc: 'O bot retoma o contato com cadência baseada na temperatura definida pelo vendedor.',
        diffNote: 'No outbound frio: reconectar com a dor despertada na prospecção, não com a oferta.',
        bullets: [
          { text: '<strong>Escalada ao humano:</strong> se o lead responde com interesse alto, notifica o vendedor imediatamente.' },
          { text: '<strong>Sinal de compra detectado:</strong> keywords como "quanto custa", "como funciona o contrato" acionam alerta.' },
        ],
        tempCards: [
          { cls: 'hot',  label: '🔥 Quente', desc: 'Follow-up em 24h. Mensagens curtas, senso de urgência. Facilitação direta para assinar ou pagar.' },
          { cls: 'warm', label: '🌡 Morno',  desc: 'Sequência 5–7 dias. Casos de sucesso, conteúdo de valor, remoção de objeções específicas.' },
          { cls: 'cold', label: '❄ Frio',   desc: 'Resgata a dor original. Propõe nova conversa. Verifica mudança no timing ou budget.' },
          { cls: 'done', label: '✓ Perdido', desc: 'Move para nurture de longo prazo. Reativação automática em 30–60 dias com novo gatilho.' },
        ]},
      { icon: 'FC', title: 'Fechamento', who: 'human',
        desc: 'Conduzido pelo humano. O bot prepara o terreno e avisa o vendedor quando o lead dá sinal de compra.',
        bullets: [
          { text: '<strong>Facilitação opcional:</strong> bot pode enviar link de contrato, boleto ou agendamento de call de fechamento.' },
        ]},
      { icon: 'PV', title: 'Pós-Venda / Onboarding', who: 'collab',
        desc: 'Pagamento confirmado dispara onboarding automatizado: boas-vindas, checklist de início, kick-off com o time.',
        bullets: [
          { text: '<strong>Boas-vindas personalizada:</strong> nome, serviço contratado, próximos passos claros.' },
          { text: '<strong>Coleta de dados iniciais:</strong> formulário de onboarding enviado automaticamente.' },
          { text: '<strong>NPS automático:</strong> pesquisa de satisfação após período inicial definido.' },
        ]},
    ],
  },
  {
    id: 'a2',
    chip: 'Agente 02 · Direto',
    title: 'Vendedor Autônomo',
    subtitle: 'Low Ticket',
    desc: '100% automatizado — qualifica, apresenta e fecha sem intervenção humana. Inbound e outbound diferem apenas na velocidade da qualificação e no tom da abordagem inicial.',
    analogy: 'Você vende um curso online por R$ 197. O lead clica no anúncio e entra em contato. O agente faz 1–2 perguntas para confirmar que o curso resolve o problema dele, apresenta os benefícios, manda o link de pagamento — e se ele não pagar em 2h, manda um lembrete. Você só vê o dinheiro na conta.',
    useCases: ['Infoprodutos', 'E-commerce', 'Pedidos de lojas físicas', 'Cursos · Assinaturas'],
    splitIn: [
      { icon: 'IN', title: 'Entrada — Dor Implícita no Clique', who: 'bot',
        desc: 'O lead clicou no anúncio ou link — sinal de dor ou interesse. Recepção rápida e encaminhamento para confirmação de fit.',
        bullets: [
          { text: '<strong>Recepção rápida:</strong> mensagem curta de boas-vindas com referência ao que o lead clicou.' },
          { text: '<strong>Registro de origem:</strong> campanha, anúncio, canal — usado para personalizar o pitch.' },
        ]},
      { icon: 'FIT', title: 'Qualificação de Fit — 1 a 2 Perguntas', who: 'bot',
        desc: 'Para low ticket, o filtro de fit é mínimo. 1–2 perguntas para confirmar que o produto resolve o problema do lead.',
        qCards: [
          { label: 'Exemplo fit', text: '"Você está buscando emagrecer de forma saudável sem dietas restritivas?"' },
          { label: 'Exemplo fit', text: '"Você já tem uma loja e quer automatizar os pedidos pelo WhatsApp?"' },
        ]},
    ],
    splitOut: [
      { icon: 'OUT', title: 'Abordagem com Foco na Dor', who: 'bot',
        desc: 'Lista fria — seguidores, base de e-mail, retargeting. Abertura tocando no problema antes de mencionar o produto.',
        bullets: [
          { text: '<strong>Abertura por dor:</strong> mensagem que toca no problema antes de mencionar o produto.' },
          { text: '<strong>Volume:</strong> centenas de contatos/dia — sem personalização profunda, mas com segmentação por lista.' },
        ],
        qCards: [
          { label: 'Abertura exemplo', text: '"Você também sente que perde tempo tentando controlar os pedidos manualmente todo dia?"' },
        ]},
      { icon: 'DOR', title: 'Confirma a Dor — 1 Pergunta', who: 'bot',
        desc: '"Isso faz sentido para você?" Sim → pitch. Não → encerra ou nurture. Uma única pergunta direta para confirmar que a dor existe.',
        qCards: [
          { label: 'Confirmação', text: '"Esse é um problema que você enfrenta hoje?"' },
          { label: 'Alternativa',  text: '"Isso faz sentido para a sua situação atual?"' },
        ]},
    ],
    mergeLabel: 'Caminhos convergem → Pitch',
    shared: [
      { icon: 'PT', title: 'Pitch — Apresentação pelo Bot', who: 'bot',
        desc: 'Apresentação completa do produto: dor → solução → benefícios → prova social → oferta com urgência.',
        diffNote: 'No outbound: pitch abre espelhando a dor confirmada pelo lead — "E se houvesse uma forma de..." — antes de apresentar o produto.',
        bullets: [
          { text: '<strong>Estrutura:</strong> Solução direta → 3 benefícios concretos → prova social → oferta com urgência.' },
          { text: '<strong>Mídia rica:</strong> imagens, vídeo curto de demonstração, depoimentos em áudio/vídeo.' },
          { text: '<strong>FAQ automático:</strong> respostas para as 5 objeções mais comuns do produto.' },
        ]},
      { icon: 'OF', title: 'Oferta + Link de Pagamento', who: 'bot',
        desc: 'Apresenta o preço e envia o link de pagamento com mínimo atrito.',
        bullets: [
          { text: '<strong>Preço âncora:</strong> mostra valor "cheio" antes do preço real.' },
          { text: '<strong>Link direto:</strong> Pix, cartão, boleto — integração Hotmart, Stripe, PagSeguro.' },
          { text: '<strong>Urgência real:</strong> vagas limitadas, oferta expira, bônus exclusivo com prazo.' },
          { text: '<strong>Garantia:</strong> menciona política de devolução para reduzir risco percebido.' },
        ]},
      { icon: 'CA', title: 'Follow-up de Carrinho Abandonado', who: 'bot',
        desc: 'Lead recebeu o link mas não pagou. Sequência automática de 3 mensagens com abordagens diferentes.',
        diffNote: 'No outbound: a 2ª mensagem reconecta com a dor confirmada antes de reapresentar o produto.',
        bullets: [
          { text: '<strong>1ª tentativa (2h):</strong> lembrete simples — "Seu pedido ainda está reservado."' },
          { text: '<strong>2ª tentativa (24h):</strong> reforça benefício principal, remove objeção mais comum.' },
          { text: '<strong>3ª tentativa (48h):</strong> urgência máxima — "Últimas horas para garantir o preço especial."' },
          { text: '<strong>Sem resposta:</strong> move para lista de reativação de 30 dias.' },
        ]},
      { icon: 'PV', title: 'Confirmação + Upsell + Onboarding', who: 'bot',
        desc: 'Pagamento confirmado dispara entrega, boas-vindas, upsell e NPS automático.',
        bullets: [
          { text: '<strong>Entrega automática:</strong> acesso ao produto digital ou confirmação do pedido.' },
          { text: '<strong>Upsell imediato:</strong> "Clientes que compraram X também levaram Y com desconto exclusivo."' },
          { text: '<strong>NPS automático:</strong> após 7 dias do uso/recebimento.' },
        ]},
    ],
  },
  {
    id: 'a3',
    chip: 'Agente 03 · Híbrido',
    title: 'Assistente Comercial',
    subtitle: 'com Agendamento Inteligente',
    desc: 'Funciona como recepcionista comercial inteligente. Qualifica, agenda e entrega o lead preparado para o profissional. Não apresenta nem fecha — mas faz tudo antes e cuida do follow-up depois.',
    analogy: 'Você é coach e cobra R$ 800 por sessão. O lead te manda mensagem. O agente responde na hora, descobre o que ele está buscando, conta um resultado de outro cliente parecido, agenda a sessão e te manda o contexto antes do encontro. Você chega na sessão sabendo o nome, o problema e o que a pessoa espera.',
    useCases: ['Coaches · Terapeutas', 'Personal Trainers', 'Consultores solo', 'Serviços por hora'],
    splitIn: [
      { icon: 'IN', title: 'Entrada — Interesse Ativo Demonstrado', who: 'bot',
        desc: 'O lead entrou em contato ou clicou em um link. O agente se apresenta como assistente do profissional e acolhe com tom próximo.',
        bullets: [
          { text: '<strong>Apresentação do bot:</strong> "Oi! Aqui é a assistente da [Nome do profissional]. Vi que você tem interesse em..."' },
          { text: '<strong>Captura da dor inicial:</strong> se o lead veio de formulário com campos, já usa essas informações sem repetir.' },
        ]},
      { icon: 'F1', title: 'Confirma que é o Público Certo', who: 'bot',
        desc: '2–3 perguntas de contexto. Quem não se encaixa recebe uma indicação alternativa — ninguém fica sem resposta.',
        qCards: [
          { label: 'Coach exemplo',    text: '"Você está buscando desenvolvimento pessoal ou profissional no momento?"' },
          { label: 'Personal exemplo', text: '"Você treina atualmente ou está começando do zero?"' },
        ]},
    ],
    splitOut: [
      { icon: 'OUT', title: 'Prospecção com Tom Pessoal', who: 'bot',
        desc: '"O [Profissional] me pediu para entrar em contato..." — como se fosse o próprio profissional.',
        bullets: [
          { text: '<strong>Tom pessoal:</strong> "Oi [Nome], o [Profissional] me pediu para entrar em contato — ele viu seu perfil e achou que poderia te ajudar muito com..."' },
          { text: '<strong>Abertura por situação:</strong> menciona uma situação comum do público antes de fazer qualquer pergunta.' },
        ]},
      { icon: 'F2', title: 'Desperta a Dor com Pergunta Leve', who: 'bot',
        desc: 'Pergunta aberta e não intrusiva — convida à reflexão sem parecer venda.',
        bullets: [
          { text: '<strong>Pergunta de escavação leve:</strong> não intrusiva, convida à reflexão sem parecer venda.' },
          { text: '<strong>Sem mencionar serviço ainda:</strong> foco em identificar se a dor existe antes de qualquer oferta.' },
        ],
        qCards: [
          { label: 'Coach',    text: '"Como você está se sentindo em relação ao equilíbrio entre trabalho e vida pessoal ultimamente?"' },
          { label: 'Personal', text: '"Você sente que sua rotina de treino está te levando para onde você quer chegar?"' },
        ]},
      { icon: 'F1', title: 'Valida o Fit Dentro do Diálogo', who: 'bot',
        desc: 'Confirma o perfil de forma natural na conversa — não como formulário separado.',
        bullets: [
          { text: '<strong>Validação contextual:</strong> confirma aspectos do perfil de forma natural dentro do diálogo sobre o problema.' },
          { text: '<strong>Reposicionamento:</strong> se o fit não bater 100%, ajusta o ângulo da oferta antes de avançar.' },
        ]},
    ],
    mergeLabel: 'Caminhos convergem → Aprofundamento de Dor',
    shared: [
      { icon: 'DOR', title: 'Aprofunda a Dor + Coleta Contexto', who: 'bot',
        desc: 'Pergunta aberta para o lead descrever o problema com suas palavras. A resposta vira o briefing enviado ao profissional antes da sessão.',
        bullets: [
          { text: '<strong>Pergunta aberta:</strong> "Qual é seu principal desafio hoje em relação a X?" — resposta livre, sem menu.' },
          { text: '<strong>Registro da dor:</strong> a resposta compõe o briefing enviado ao profissional antes da sessão.' },
          { text: '<strong>Escuta ativa:</strong> o bot faz uma breve validação empática antes de avançar — não vai direto ao agendamento.' },
        ]},
      { icon: 'AQ', title: 'Aquecimento — Ancora Valor', who: 'bot',
        desc: 'Cita resultado de cliente com perfil similar. Explica o que vai acontecer na sessão para reduzir ansiedade. Conecta a dor do lead com o que o profissional resolve.',
        diffNote: 'No outbound: etapa crítica — leads prospectados friamente têm menor comprometimento inicial. Aumenta a taxa de comparecimento.',
        bullets: [
          { text: '<strong>Social proof:</strong> resultado de cliente com perfil similar ao lead, citado naturalmente.' },
          { text: '<strong>Preview da sessão:</strong> explica o que vai acontecer na consulta — reduz ansiedade e aumenta expectativa.' },
          { text: '<strong>Conexão dor → profissional:</strong> "Exatamente esse tipo de situação é o que [Nome] trabalha."' },
        ]},
      { icon: 'AG', title: 'Agendamento Automático', who: 'bot',
        desc: 'Mostra os horários disponíveis em tempo real, confirma por WhatsApp e e-mail, envia lembretes 24h e 2h antes. Profissional recebe o briefing do lead antes da sessão.',
        diffNote: 'No outbound: o lembrete de 2h é especialmente importante — leads prospectados friamente têm maior taxa de no-show.',
        bullets: [
          { text: '<strong>Calendário em tempo real:</strong> lê disponibilidade e apresenta opções (Google Calendar, Calendly).' },
          { text: '<strong>Confirmação dupla:</strong> WhatsApp + e-mail com detalhes da sessão.' },
          { text: '<strong>Lembretes anti-no-show:</strong> 24h e 2h antes da sessão.' },
          { text: '<strong>Briefing ao profissional:</strong> dor relatada + histórico da conversa enviados antes da sessão.' },
        ]},
      { icon: 'SS', title: 'Você Faz a Sessão', who: 'human',
        desc: 'Lead chegou aquecido e contextualizado. Você apresenta, diagnostica e pode fechar na mesma sessão. Depois, registra o resultado: fechou, não fechou ou precisa reagendar.',
        bullets: [
          { text: '<strong>Registro de resultado:</strong> Fechou / Não fechou / Reagendar — ativa o fluxo de follow-up correspondente.' },
        ]},
      { icon: 'FU', title: 'Follow-up Pós-Sessão', who: 'bot',
        desc: 'Fluxo automático baseado no resultado registrado pelo profissional.',
        diffNote: 'No outbound: leads que não fecharam recebem reforço da dor despertada originalmente — mais eficaz do que reapresentar a oferta.',
        bullets: [
          { text: '<strong>Escalada ao humano:</strong> resposta com alto interesse aciona notificação imediata ao profissional.' },
        ],
        tempCards: [
          { cls: 'done', label: '✓ Fechou',     desc: 'Onboarding imediato: boas-vindas, link de pagamento/contrato, próximos passos.' },
          { cls: 'warm', label: '💬 Não fechou', desc: 'Sequência 2–3 dias reforçando valor, removendo objeções levantadas na sessão.' },
          { cls: 'cold', label: '📅 Reagendar',  desc: 'Oferece nova data automaticamente. Mantém lead aquecido entre sessões.' },
        ]},
      { icon: 'PV', title: 'Retenção e Renovação de Pacote', who: 'collab',
        desc: 'Bot gerencia os agendamentos recorrentes, envia materiais antes de cada sessão e inicia o fluxo de renovação automático ao fim do pacote — sem você precisar lembrar.',
        bullets: [
          { text: '<strong>Agendamento recorrente:</strong> bot gerencia próximas sessões automaticamente.' },
          { text: '<strong>Materiais pré-sessão:</strong> formulários ou tarefas enviados automaticamente antes de cada encontro.' },
          { text: '<strong>Renovação de pacote:</strong> ao fim do pacote, inicia fluxo de recontratação sem o profissional precisar agir.' },
        ]},
    ],
  },
];

// ─── Quiz ─────────────────────────────────────────────────────

const QUIZ: QuizQuestion[] = [
  {
    q: '1. Qual é o ticket médio do que você vende?',
    hint: 'Selecione a opção mais próxima da sua realidade',
    options: [
      { label: '💼 Acima de R$ 2.000 por venda', agent: 'a1' },
      { label: '💳 Abaixo de R$ 500 por venda', agent: 'a2' },
      { label: '🕐 Cobro por sessão/hora (R$ 200–2.000)', agent: 'a3' },
      { label: '🤝 Contratos longos de serviços', agent: 'a1' },
    ],
  },
  {
    q: '2. Você precisa estar presente na apresentação/fechamento?',
    hint: 'Pense no seu processo atual',
    options: [
      { label: '✋ Sim, sempre fecho pessoalmente', agent: 'a1' },
      { label: '🤖 Não, o produto se vende sozinho', agent: 'a2' },
      { label: '📋 Sim, mas só na consulta agendada', agent: 'a3' },
      { label: '👥 Tenho um time de vendas para fechar', agent: 'a1' },
    ],
  },
  {
    q: '3. Que tipo de negócio você tem?',
    hint: 'Escolha o mais parecido com o seu caso',
    options: [
      { label: '🏢 Imobiliária, advocacia, clínica, consultoria', agent: 'a1' },
      { label: '🛒 E-commerce, loja física, infoproduto, curso', agent: 'a2' },
      { label: '🎯 Coach, terapeuta, personal, mentor', agent: 'a3' },
      { label: '📦 Produto com entrega automatizável', agent: 'a2' },
    ],
  },
];

// ─── Glossário ────────────────────────────────────────────────

const GLOSSARY: GlossItem[] = [
  { term: 'Lead',          def: 'Potencial cliente que entrou em contato ou foi prospectado. Ainda não comprou nada.' },
  { term: 'Pipeline',      def: 'A sequência de etapas que um lead percorre desde o primeiro contato até a compra.' },
  { term: 'Fit',           def: 'O quanto o lead se encaixa no perfil ideal do seu cliente. Setor, porte, faturamento, localização.' },
  { term: 'Dor',           def: 'O problema que o lead quer resolver. Sem dor, não há motivo de compra.' },
  { term: 'Filtro 1 / F1', def: 'Verificação de perfil: o lead tem o formato certo de cliente? Faturamento, setor, porte.' },
  { term: 'Filtro 2 / F2', def: 'Verificação de intenção: a dor que o lead quer resolver é o que você resolve?' },
  { term: 'F3 (4Ps)',      def: 'Qualificação profunda: Poder (quem decide), Prioridade (urgência), Preço (verba) e Timing (quando).' },
  { term: 'Handoff',       def: 'O momento em que o bot passa o lead para você, com um resumo completo da conversa.' },
  { term: 'Nurture',       def: 'Manter o lead aquecido com conteúdo e mensagens enquanto ele ainda não está pronto para comprar.' },
  { term: 'Follow-up',     def: 'Mensagem de acompanhamento enviada depois de um contato anterior — para retomar a conversa.' },
  { term: 'No-show',       def: 'Quando o lead agendou uma reunião ou sessão mas não apareceu.' },
  { term: 'NPS',           def: 'Pesquisa de satisfação automática enviada após a venda para medir a experiência do cliente.' },
];

// ─── FAQ ──────────────────────────────────────────────────────

const FAQ: FaqItem[] = [
  { q: 'O lead vai saber que está falando com um bot?', a: 'Depende do modo de identidade que você configurar. No modo Assistente Virtual, o bot se apresenta como IA. No modo Humano do Time, ele age como um colaborador da empresa sem revelar que é automático. No modo Clone, replica seu estilo de comunicação. A escolha é sua.' },
  { q: 'O que acontece se o lead fizer uma pergunta que o bot não sabe responder?', a: 'O agente identifica que precisa de intervenção humana e aciona você conforme a regra de comportamento configurada — pode manter o bot ativo e te notificar, ou pausar o bot e te passar a conversa.' },
  { q: 'Posso usar inbound e outbound ao mesmo tempo no mesmo agente?', a: 'Sim. O agente detecta automaticamente de onde o lead veio e ajusta o roteiro. Um lead que entrou por formulário recebe a jornada inbound; um lead prospectado em lista recebe a jornada outbound. O pipeline compartilhado se encarrega do restante.' },
  { q: 'Como sei se o Agente 1, 2 ou 3 é o melhor para mim?', a: 'Regra geral: se você precisa estar na venda e o ticket é alto, use o Agente 1. Se o produto se vende sozinho e é mais barato, use o Agente 2. Se você é profissional que cobra por sessão/hora e só quer aparecer na reunião preparado, use o Agente 3. Use o quiz acima para ter uma indicação personalizada.' },
  { q: 'Posso mudar de tipo de agente depois de criar?', a: 'Sim, você pode editar o agente a qualquer momento. A mudança de tipo afeta o pipeline e as regras de comportamento, mas não apaga o histórico de conversas anteriores.' },
  { q: 'O bot consegue agendar reuniões na minha agenda?', a: 'Sim, com integração ao Google Calendar ou Calendly. O bot vê seus horários disponíveis em tempo real, apresenta as opções ao lead e confirma o agendamento sem precisar da sua intervenção.' },
  { q: 'O que é o "dossiê" que o bot envia antes da reunião?', a: 'É um resumo completo da conversa com o lead: nome, empresa, problema relatado, respostas aos filtros de qualificação, canal de origem e score de qualificação. Você entra na reunião sabendo exatamente quem é o lead e o que ele precisa.' },
];

// ─── SplitStep ────────────────────────────────────────────────

function SplitStep({ stage, side }: { stage: Stage; side: 'in' | 'out' }) {
  const [open, setOpen] = useState(false);
  const mono = "'JetBrains Mono', monospace";
  const c = side === 'in' ? '#60c890' : '#e07060';
  const whoStyle =
    stage.who === 'bot'    ? { bg: 'rgba(96,176,255,0.12)', color: '#60b0ff' }
    : stage.who === 'human' ? { bg: 'rgba(255,154,96,0.12)', color: '#ff9a60' }
    : { bg: 'rgba(200,255,120,0.1)', color: '#c8ff78' };
  const whoLabel = stage.who === 'bot' ? 'BOT' : stage.who === 'human' ? 'HUMANO' : 'BOT+HUM';
  const hasDetail = !!(stage.bullets || stage.qCards);

  return (
    <div
      onClick={hasDetail ? () => setOpen(v => !v) : undefined}
      style={{ display: 'flex', gap: 10, alignItems: 'flex-start', padding: '8px 6px', borderRadius: 6, cursor: hasDetail ? 'pointer' : 'default', transition: 'background 0.15s' }}
      onMouseEnter={e => { if (hasDetail) e.currentTarget.style.background = 'rgba(255,255,255,0.03)'; }}
      onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
    >
      <div style={{ width: 30, height: 30, borderRadius: '50%', background: `${c}12`, border: `1.5px solid ${c}35`, color: c, fontFamily: mono, fontSize: 8, fontWeight: 600, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, marginTop: 2 }}>
        {stage.icon}
      </div>
      <div style={{ flex: 1 }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 6, marginBottom: 3 }}>
          <span style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--o-text)', lineHeight: 1.3 }}>{stage.title}</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexShrink: 0 }}>
            <span style={{ fontFamily: mono, fontSize: 7.5, letterSpacing: 1, textTransform: 'uppercase', padding: '2px 6px', borderRadius: 2, background: whoStyle.bg, color: whoStyle.color }}>{whoLabel}</span>
            {hasDetail && <span style={{ color: 'var(--o-dim)', fontSize: 10, display: 'inline-block', transform: open ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }}>▾</span>}
          </div>
        </div>
        <p style={{ fontSize: 11.5, color: 'var(--o-sub)', lineHeight: 1.55, margin: 0 }}>{stage.desc}</p>
        {open && (
          <div style={{ marginTop: 10, animation: 'o-fade-in 0.2s ease' }}>
            {stage.bullets && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 5, marginBottom: stage.qCards ? 10 : 0 }}>
                {stage.bullets.map((b, i) => (
                  <div key={i} style={{ display: 'flex', gap: 7, fontSize: 11.5, lineHeight: 1.55, color: 'var(--o-text)' }}>
                    <span style={{ color: 'var(--o-dim)', fontFamily: mono, fontSize: 10, flexShrink: 0, paddingTop: 1 }}>→</span>
                    <span dangerouslySetInnerHTML={{ __html: b.text }} />
                  </div>
                ))}
              </div>
            )}
            {stage.qCards && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
                {stage.qCards.map((q, i) => (
                  <div key={i} style={{ background: 'rgba(255,255,255,0.025)', border: '1px solid var(--o-b1)', borderRadius: 5, padding: '8px 10px' }}>
                    <div style={{ fontFamily: mono, fontSize: 7.5, letterSpacing: 2, textTransform: 'uppercase', color: 'var(--o-dim)', marginBottom: 4 }}>{q.label}</div>
                    <div style={{ fontSize: 11.5, color: 'var(--o-sub)', lineHeight: 1.55, fontStyle: 'italic' }}>{q.text}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── SharedCard ───────────────────────────────────────────────

function SharedCard({ stage }: { stage: Stage }) {
  const [open, setOpen] = useState(false);
  const mono = "'JetBrains Mono', monospace";
  const whoStyle =
    stage.who === 'bot'    ? { icon: { color: '#60b0ff', borderColor: 'rgba(96,176,255,0.35)', background: 'rgba(96,176,255,0.08)' }, tag: { background: 'rgba(96,176,255,0.1)', color: '#60b0ff' } }
    : stage.who === 'human' ? { icon: { color: '#ff9a60', borderColor: 'rgba(255,154,96,0.4)', background: 'rgba(255,154,96,0.08)' }, tag: { background: 'rgba(255,154,96,0.1)', color: '#ff9a60' } }
    : { icon: { color: '#c8ff78', borderColor: 'rgba(200,255,120,0.3)', background: 'rgba(200,255,120,0.06)' }, tag: { background: 'rgba(200,255,120,0.1)', color: '#c8ff78' } };
  const whoLabel = stage.who === 'bot' ? 'BOT' : stage.who === 'human' ? 'HUMANO' : 'BOT + HUMANO';

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '44px 1fr', gap: 14, alignItems: 'start', marginBottom: 6 }}>
      <div style={{ width: 44, height: 44, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: mono, fontSize: 11, fontWeight: 500, flexShrink: 0, position: 'relative', zIndex: 2, border: '1px solid', background: 'var(--o-bg)', ...whoStyle.icon }}>
        {stage.icon}
      </div>
      <div onClick={() => setOpen(v => !v)} style={{ background: 'var(--o-surface)', border: '1px solid var(--o-b1)', borderRadius: 8, cursor: 'pointer', overflow: 'hidden' }}>
        <div style={{ padding: '13px 16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--o-text)', flex: 1 }}>{stage.title}</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
            <span style={{ fontFamily: mono, fontSize: 9, letterSpacing: 1.5, textTransform: 'uppercase', padding: '3px 10px', borderRadius: 2, ...whoStyle.tag }}>{whoLabel}</span>
            <span style={{ color: 'var(--o-dim)', fontSize: 11, display: 'inline-block', transform: open ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }}>▾</span>
          </div>
        </div>
        {open && (
          <div style={{ padding: '0 16px 16px', borderTop: '1px solid var(--o-b1)', animation: 'o-fade-in 0.2s ease' }}>
            <p style={{ fontSize: 12.5, color: 'var(--o-sub)', fontWeight: 300, lineHeight: 1.75, margin: '14px 0' }}>{stage.desc}</p>
            {stage.diffNote && (
              <div style={{ background: 'rgba(224,112,96,0.06)', border: '1px solid rgba(224,112,96,0.2)', borderRadius: 5, padding: '7px 10px', marginBottom: 12, fontSize: 12, color: '#e07060', lineHeight: 1.55 }}>
                <span style={{ fontFamily: mono, fontSize: 8, letterSpacing: 1, textTransform: 'uppercase', marginRight: 6, opacity: 0.7 }}>outbound</span>
                {stage.diffNote}
              </div>
            )}
            {stage.bullets && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: stage.qCards || stage.tempCards ? 14 : 0 }}>
                {stage.bullets.map((b, i) => (
                  <div key={i} style={{ display: 'flex', gap: 10, fontSize: 12.5, lineHeight: 1.6, color: 'var(--o-text)' }}>
                    <span style={{ color: 'var(--o-dim)', fontFamily: mono, fontSize: 11, flexShrink: 0, paddingTop: 2 }}>→</span>
                    <span dangerouslySetInnerHTML={{ __html: b.text }} />
                  </div>
                ))}
              </div>
            )}
            {stage.qCards && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 10, marginTop: 12 }}>
                {stage.qCards.map((q, i) => (
                  <div key={i} style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid var(--o-b1)', borderRadius: 6, padding: 12 }}>
                    <div style={{ fontFamily: mono, fontSize: 8, letterSpacing: 2, textTransform: 'uppercase', color: 'var(--o-dim)', marginBottom: 6 }}>{q.label}</div>
                    <div style={{ fontSize: 12, color: 'var(--o-sub)', lineHeight: 1.6, fontStyle: 'italic' }}>{q.text}</div>
                  </div>
                ))}
              </div>
            )}
            {stage.tempCards && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 10, marginTop: 12 }}>
                {stage.tempCards.map((t, i) => {
                  const tc = t.cls === 'hot' ? '#ff6060' : t.cls === 'warm' ? '#ffaa40' : t.cls === 'cold' ? '#6090ff' : '#60c890';
                  return (
                    <div key={i} style={{ border: '1px solid var(--o-b1)', borderRadius: 6, padding: 12, background: 'rgba(255,255,255,0.02)' }}>
                      <div style={{ fontFamily: mono, fontSize: 9, letterSpacing: 2, textTransform: 'uppercase', color: tc, marginBottom: 8 }}>{t.label}</div>
                      <div style={{ fontSize: 12, color: 'var(--o-sub)', lineHeight: 1.6, fontWeight: 300 }}>{t.desc}</div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── PipelineLayout ───────────────────────────────────────────

function PipelineLayout({ agent }: { agent: AgentData }) {
  const mono = "'JetBrains Mono', monospace";

  return (
    <div style={{ border: '1px solid var(--o-b1)', borderRadius: 10, overflow: 'hidden' }}>
      {/* Header */}
      <div style={{ padding: '16px 22px', borderBottom: '1px solid var(--o-b1)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--o-text)' }}>Pipeline do {agent.title}</div>
          <div style={{ fontSize: 12, color: 'var(--o-dim)', marginTop: 3 }}>A jornada diverge conforme a origem do lead; após o ponto de convergência, o caminho é único</div>
        </div>
        <div style={{ display: 'flex', gap: 14 }}>
          {([{ color: '#60c890', label: 'Inbound' }, { color: '#e07060', label: 'Outbound' }]).map(item => (
            <div key={item.label} style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, color: 'var(--o-dim)', fontFamily: mono }}>
              <span style={{ width: 7, height: 7, borderRadius: '50%', background: item.color, display: 'inline-block' }} />
              {item.label}
            </div>
          ))}
        </div>
      </div>

      {/* Split columns */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr' }}>
        {/* Inbound */}
        <div style={{ padding: 20, borderRight: '1px solid var(--o-b1)' }}>
          <div style={{ fontFamily: mono, fontSize: 9.5, letterSpacing: 2, textTransform: 'uppercase', padding: '6px 12px', borderRadius: 5, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 7, background: 'rgba(96,200,144,0.07)', color: '#60c890', border: '1px solid rgba(96,200,144,0.2)' }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#60c890', flexShrink: 0 }} />
            Inbound — lead tem dor
          </div>
          {agent.splitIn.map((s, i) => (
            <div key={i}>
              <SplitStep stage={s} side="in" />
              {i < agent.splitIn.length - 1 && (
                <div style={{ paddingLeft: 21, marginBottom: 2, marginTop: 2 }}>
                  <div style={{ width: 1, height: 14, background: 'rgba(96,200,144,0.25)' }} />
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Outbound */}
        <div style={{ padding: 20 }}>
          <div style={{ fontFamily: mono, fontSize: 9.5, letterSpacing: 2, textTransform: 'uppercase', padding: '6px 12px', borderRadius: 5, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 7, background: 'rgba(224,112,96,0.07)', color: '#e07060', border: '1px solid rgba(224,112,96,0.2)' }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#e07060', flexShrink: 0 }} />
            Outbound — fit presumido
          </div>
          {agent.splitOut.map((s, i) => (
            <div key={i}>
              <SplitStep stage={s} side="out" />
              {i < agent.splitOut.length - 1 && (
                <div style={{ paddingLeft: 21, marginBottom: 2, marginTop: 2 }}>
                  <div style={{ width: 1, height: 14, background: 'rgba(224,112,96,0.25)' }} />
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Merge point */}
      <div style={{ borderTop: '1px solid var(--o-b1)', padding: '12px 22px', background: 'rgba(255,255,255,0.015)', display: 'flex', alignItems: 'center', gap: 14 }}>
        <span style={{ fontFamily: mono, fontSize: 9, letterSpacing: 1.5, textTransform: 'uppercase', padding: '4px 14px', borderRadius: 20, background: 'var(--o-bg)', border: '1px solid var(--o-b1)', color: 'var(--o-sub)', whiteSpace: 'nowrap' }}>
          ⋯ {agent.mergeLabel}
        </span>
        <span style={{ fontSize: 12, color: 'var(--o-dim)' }}>A partir daqui, inbound e outbound seguem o mesmo caminho</span>
      </div>

      {/* Shared steps */}
      <div style={{ padding: 20, borderTop: '1px solid var(--o-b1)' }}>
        <div style={{ fontFamily: mono, fontSize: 9, letterSpacing: 2, textTransform: 'uppercase', color: 'var(--o-dim)', marginBottom: 16 }}>
          Etapas compartilhadas — inbound e outbound
        </div>
        <div style={{ position: 'relative' }}>
          <div style={{ position: 'absolute', left: 21, top: 22, bottom: 22, width: 1, background: 'var(--o-b1)', pointerEvents: 'none' }} />
          {agent.shared.map((stage, i) => (
            <div key={i}>
              <SharedCard stage={stage} />
              {i < agent.shared.length - 1 && (
                <div style={{ display: 'grid', gridTemplateColumns: '44px 1fr', gap: 14, marginBottom: 6 }}>
                  <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 22 }}>
                    <span style={{ fontSize: 11, color: 'var(--o-dim)', background: 'var(--o-bg)', padding: '0 2px', zIndex: 2, position: 'relative' }}>↓</span>
                  </div>
                  <div />
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Legend */}
      <div style={{ borderTop: '1px solid var(--o-b1)', padding: '12px 20px', display: 'flex', flexWrap: 'wrap', gap: 18 }}>
        {[
          { color: '#60b0ff', label: 'Executado pelo BOT' },
          { color: '#ff9a60', label: 'Executado pelo HUMANO' },
          { color: '#c8ff78', label: 'Colaborativo' },
        ].map(item => (
          <div key={item.label} style={{ display: 'flex', alignItems: 'center', gap: 7, fontFamily: mono, fontSize: 10, color: 'var(--o-dim)', letterSpacing: 1 }}>
            <span style={{ width: 7, height: 7, borderRadius: '50%', background: item.color, display: 'inline-block', flexShrink: 0 }} />
            {item.label}
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Página ───────────────────────────────────────────────────

export default function TiposAgentes() {
  const [scrollPct, setScrollPct]     = useState(0);
  const [quizAnswers, setQuizAnswers] = useState<Record<number, AgentId | null>>({ 0: null, 1: null, 2: null });
  const [openFaqs, setOpenFaqs]       = useState<Set<number>>(new Set());

  useEffect(() => {
    const handler = () => {
      const total = document.documentElement.scrollHeight - window.innerHeight;
      if (total > 0) setScrollPct((window.scrollY / total) * 100);
    };
    window.addEventListener('scroll', handler, { passive: true });
    return () => window.removeEventListener('scroll', handler);
  }, []);

  const agentColor: Record<AgentId, string> = { a1: '#f0c060', a2: '#50d8c8', a3: '#b87fff' };
  const quizResults: Record<AgentId, { name: string; desc: string }> = {
    a1: { name: 'Agente 1 — Alto Ticket', desc: 'Processo de venda longo e personalizado. O agente qualifica com profundidade e você fecha pessoalmente.' },
    a2: { name: 'Agente 2 — Low Ticket',  desc: 'Produto de compra rápida. O agente vende sozinho, sem precisar de você.' },
    a3: { name: 'Agente 3 — Híbrido',     desc: 'Você precisa aparecer, mas só na hora certa. O agente cuida de tudo antes e depois da sua sessão.' },
  };

  const mono = "'JetBrains Mono', monospace";
  const sec: React.CSSProperties = { padding: '56px 0 48px', borderBottom: '1px solid var(--o-b1)' };
  const eyebrow: React.CSSProperties = { fontFamily: mono, fontSize: 9, letterSpacing: 3, textTransform: 'uppercase', color: 'var(--o-dim)', marginBottom: 10 };
  const sTitle: React.CSSProperties = { fontFamily: "'Playfair Display', serif", fontSize: 28, fontWeight: 400, lineHeight: 1.2, marginBottom: 14, color: 'var(--o-text)' };
  const sIntro: React.CSSProperties = { fontSize: 15, color: 'var(--o-sub)', lineHeight: 1.8, fontWeight: 300, maxWidth: 640, marginBottom: 28 };

  return (
    <OrionShell>
      {/* Scroll progress */}
      <div style={{ position: 'fixed', top: 0, left: 0, right: 0, height: 2, zIndex: 400 }}>
        <div style={{ height: '100%', background: 'var(--o-active)', width: `${scrollPct}%`, transition: 'width 0.05s linear' }} />
      </div>

      {/* Topbar */}
      <header className="o-topbar">
        <div className="font-mono-orion" style={{ fontSize: 11, letterSpacing: 3, textTransform: 'uppercase', color: 'var(--o-sub)', paddingRight: 24, borderRight: '1px solid var(--o-b1)', marginRight: 20, whiteSpace: 'nowrap' }}>
          Orion CRM
        </div>
        <div className="font-mono-orion" style={{ fontSize: 10, letterSpacing: '1.5px', color: 'var(--o-dim)', display: 'flex', alignItems: 'center', gap: 8 }}>
          <span>Identidade do Agente</span><span>›</span>
          <span style={{ color: 'var(--o-text)' }}>Tipos de Agentes</span>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 10 }}>
          <button onClick={() => document.getElementById('s-faq')?.scrollIntoView({ behavior: 'smooth' })}  className="o-btn" style={{ fontSize: 9 }}>Dúvidas frequentes</button>
          <button onClick={() => document.getElementById('s-quiz')?.scrollIntoView({ behavior: 'smooth' })} className="o-btn" style={{ fontSize: 9, color: 'var(--o-active)', borderColor: 'rgba(80,216,200,0.4)' }}>Qual agente é pra mim?</button>
          <Link to="/ai-profile" className="o-btn" style={{ fontSize: 9 }}>← Configuração</Link>
        </div>
      </header>

      <div style={{ maxWidth: 960, margin: '0 auto', padding: '0 48px 80px' }}>

        {/* ══ HERO ══ */}
        <section style={{ ...sec, paddingTop: 64 }}>
          <div style={{ ...eyebrow, marginBottom: 14 }}>Central de Ajuda · Orion CRM</div>
          <h1 style={{ fontFamily: "'Playfair Display', serif", fontSize: 40, fontWeight: 400, lineHeight: 1.1, marginBottom: 18, color: 'var(--o-text)' }}>
            Entenda os Agentes<br /><em style={{ fontStyle: 'italic', color: 'var(--o-sub)' }}>de Vendas com IA</em>
          </h1>
          <p style={{ ...sIntro, marginBottom: 40 }}>
            Um agente é um assistente virtual que conversa com seus leads automaticamente — pelo WhatsApp. Ele segue um roteiro de vendas configurado por você, filtra quem tem potencial real de compra e só chama você quando faz sentido.
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 14 }}>
            {AGENTS.map(a => {
              const c = agentColor[a.id];
              return (
                <button key={a.id} onClick={() => document.getElementById(`agent-${a.id}`)?.scrollIntoView({ behavior: 'smooth' })}
                  style={{ background: `${c}08`, border: `2px solid ${c}44`, borderRadius: 10, padding: '18px 16px', textAlign: 'left', cursor: 'pointer', transition: 'transform 0.2s' }}
                  onMouseEnter={e => (e.currentTarget.style.transform = 'translateY(-2px)')}
                  onMouseLeave={e => (e.currentTarget.style.transform = 'none')}
                >
                  <div style={{ fontFamily: mono, fontSize: 9, letterSpacing: 2, textTransform: 'uppercase', background: c, color: '#0d0e14', padding: '3px 9px', borderRadius: 2, marginBottom: 12, display: 'inline-block', fontWeight: 600 }}>{a.chip}</div>
                  <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--o-text)', marginBottom: 6 }}>{a.title}</div>
                  <div style={{ fontSize: 12.5, color: 'var(--o-sub)', lineHeight: 1.6, marginBottom: 12 }}>{a.desc.slice(0, 90)}…</div>
                  <div style={{ fontSize: 11, color: 'var(--o-dim)', fontFamily: mono, letterSpacing: 0.5 }}>{a.useCases.join(' · ')}</div>
                  <div style={{ fontSize: 12, fontWeight: 600, color: c, marginTop: 14 }}>Ver pipeline completo →</div>
                </button>
              );
            })}
          </div>
        </section>

        {/* ══ O QUE É UM AGENTE ══ */}
        <section id="s-intro" style={sec}>
          <div style={eyebrow}>Começando por aqui</div>
          <h2 style={sTitle}>O que é um Agente de Vendas com IA?</h2>
          <p style={sIntro}>Um agente é um assistente virtual que conversa com seus leads automaticamente. Ele segue um roteiro de vendas configurado por você, filtra quem tem potencial real de compra e só chama você quando faz sentido.</p>
          <div style={{ background: 'rgba(80,216,200,0.05)', border: '1px solid rgba(80,216,200,0.15)', borderRadius: 8, padding: '16px 20px', marginBottom: 24, display: 'flex', gap: 14, alignItems: 'flex-start' }}>
            <span style={{ fontSize: 20, flexShrink: 0 }}>💡</span>
            <p style={{ fontSize: 13.5, color: 'var(--o-sub)', lineHeight: 1.7 }}>
              <strong style={{ color: 'var(--o-text)' }}>Pense assim:</strong> é como contratar um vendedor que nunca dorme, responde na hora, faz as perguntas certas e te avisa quando o lead está pronto para fechar. A diferença é que ele é 100% automatizado e você configura como ele deve agir.
            </p>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 14, marginBottom: 24 }}>
            {[
              { icon: '⚡', title: 'Responde na hora',  desc: 'Sem lead esperando. O agente responde em segundos, 24h por dia, 7 dias por semana.' },
              { icon: '🎯', title: 'Filtra os leads',   desc: 'Identifica quem tem perfil e interesse real antes de te chamar. Você foca só em quem vale.' },
              { icon: '📅', title: 'Agenda reuniões',   desc: 'Marca horários direto na sua agenda e envia um resumo completo do lead antes do encontro.' },
            ].map(c => (
              <div key={c.title} style={{ background: 'var(--o-surface)', border: '1px solid var(--o-b1)', borderRadius: 8, padding: '18px 16px' }}>
                <div style={{ fontSize: 22, marginBottom: 12 }}>{c.icon}</div>
                <h3 style={{ fontSize: 14, fontWeight: 600, color: 'var(--o-text)', marginBottom: 8 }}>{c.title}</h3>
                <p style={{ fontSize: 13, color: 'var(--o-sub)', lineHeight: 1.7 }}>{c.desc}</p>
              </div>
            ))}
          </div>
          <div style={{ background: 'rgba(255,154,96,0.06)', border: '1px solid rgba(255,154,96,0.2)', borderRadius: 8, padding: '14px 18px', display: 'flex', gap: 12, alignItems: 'flex-start', fontSize: 13.5, color: 'var(--o-sub)', lineHeight: 1.65 }}>
            <span style={{ flexShrink: 0, fontSize: 16 }}>⚠️</span>
            <span><strong style={{ color: 'var(--o-text)' }}>Importante:</strong> o agente não substitui o relacionamento humano em vendas complexas. Ele prepara o terreno — você fecha. Nos processos mais simples (low ticket), ele fecha sozinho.</span>
          </div>
        </section>

        {/* ══ INBOUND vs OUTBOUND ══ */}
        <section id="s-inout" style={sec}>
          <div style={eyebrow}>Conceito fundamental</div>
          <h2 style={sTitle}>Inbound e Outbound: qual a diferença?</h2>
          <p style={sIntro}>Antes de escolher seu agente, você precisa entender de onde vêm seus leads. Isso muda completamente o caminho que o agente vai percorrer com cada pessoa.</p>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 24 }}>
            {[
              { side: 'in' as const, label: 'Inbound', title: 'O lead veio até você', desc: 'Ele já sente que tem um problema e está procurando solução. O clique no anúncio ou o preenchimento do formulário é a prova disso.', examples: ['Clicou num anúncio do Instagram','Preencheu um formulário no seu site','Enviou mensagem direto no WhatsApp','Chegou por indicação de um cliente'], c: '#60c890' },
              { side: 'out' as const, label: 'Outbound', title: 'Você foi até o lead', desc: 'O lead ainda não sabe que tem o problema — ou não te conhece. Você aborda primeiro, baseado no perfil que ele tem.', examples: ['Lista de empresas do LinkedIn','Base de contatos do seu setor','Ex-leads que não fecharam antes','Seguidores frios das redes sociais'], c: '#e07060' },
            ].map(({ side, label, title, desc, examples, c }) => (
              <div key={side} style={{ background: `${c}06`, border: `1px solid ${c}30`, borderRadius: 8, padding: '18px 20px' }}>
                <div style={{ fontFamily: mono, fontSize: 9, letterSpacing: 2, textTransform: 'uppercase', background: c, color: '#0d0e14', padding: '3px 9px', borderRadius: 2, marginBottom: 12, display: 'inline-block', fontWeight: 600 }}>{label}</div>
                <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--o-text)', marginBottom: 6 }}>{title}</div>
                <div style={{ fontSize: 13, color: 'var(--o-sub)', lineHeight: 1.7, marginBottom: 12 }}>{desc}</div>
                {examples.map(ex => (
                  <div key={ex} style={{ fontSize: 12.5, color: 'var(--o-dim)', padding: '5px 0', borderTop: `1px solid ${c}15`, display: 'flex', gap: 8 }}>
                    <span style={{ opacity: 0.5, fontSize: 11, flexShrink: 0, marginTop: 2 }}>→</span>{ex}
                  </div>
                ))}
              </div>
            ))}
          </div>
          <div style={{ background: 'rgba(80,216,200,0.05)', border: '1px solid rgba(80,216,200,0.15)', borderRadius: 8, padding: '16px 20px', display: 'flex', gap: 14, alignItems: 'flex-start' }}>
            <span style={{ fontSize: 20, flexShrink: 0 }}>🪟</span>
            <p style={{ fontSize: 13.5, color: 'var(--o-sub)', lineHeight: 1.7 }}>
              <strong style={{ color: 'var(--o-text)' }}>Analogia simples:</strong> Inbound é quando o cliente entra na loja porque viu a vitrine. Outbound é quando você vai até a rua oferecer o produto para quem passa. No inbound, a dor já existe — você valida o perfil. No outbound, o perfil é presumido — você precisa despertar a dor.
            </p>
          </div>
        </section>

        {/* ══ QUIZ ══ */}
        <section id="s-quiz" style={sec}>
          <div style={eyebrow}>Encontre o seu</div>
          <h2 style={sTitle}>Qual agente é o certo para o meu negócio?</h2>
          <p style={sIntro}>Responda as perguntas abaixo para descobrir qual tipo de agente se encaixa melhor na sua realidade.</p>
          {QUIZ.map((quiz, qi) => {
            const answer = quizAnswers[qi];
            return (
              <div key={qi} style={{ background: 'var(--o-surface)', border: '1px solid var(--o-b1)', borderRadius: 10, overflow: 'hidden', marginBottom: 20 }}>
                <div style={{ padding: '18px 22px', borderBottom: '1px solid var(--o-b1)' }}>
                  <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--o-text)', marginBottom: 4 }}>{quiz.q}</div>
                  <div style={{ fontSize: 12, color: 'var(--o-dim)', fontFamily: mono }}>{quiz.hint}</div>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr' }}>
                  {quiz.options.map((opt, oi) => {
                    const selected = answer === opt.agent;
                    const c = agentColor[opt.agent];
                    return (
                      <button key={oi} onClick={() => setQuizAnswers(prev => ({ ...prev, [qi]: opt.agent }))}
                        style={{ padding: '14px 18px', border: 'none', cursor: 'pointer', textAlign: 'left', borderRight: oi % 2 === 0 ? '1px solid var(--o-b1)' : undefined, borderBottom: oi < 2 ? '1px solid var(--o-b1)' : undefined, background: selected ? `${c}12` : 'transparent', color: selected ? c : 'var(--o-sub)', fontSize: 13, fontWeight: selected ? 600 : 400, transition: 'all .15s' }}>
                        {opt.label}
                      </button>
                    );
                  })}
                </div>
                {answer && (
                  <div style={{ padding: '16px 22px', borderTop: '1px solid var(--o-b1)', background: 'rgba(255,255,255,0.02)', animation: 'o-fade-in 0.3s ease' }}>
                    <div style={{ fontFamily: mono, fontSize: 9, letterSpacing: 2, textTransform: 'uppercase', color: 'var(--o-dim)', marginBottom: 6 }}>Sugestão</div>
                    <div style={{ fontSize: 14, fontWeight: 600, color: agentColor[answer], marginBottom: 4 }}>✓ {quizResults[answer].name}</div>
                    <div style={{ fontSize: 12.5, color: 'var(--o-sub)', lineHeight: 1.65 }}>{quizResults[answer].desc}</div>
                  </div>
                )}
              </div>
            );
          })}
        </section>

        {/* ══ PIPELINES ══ */}
        <section style={{ ...sec, borderBottom: 'none' }}>
          <div style={eyebrow}>Os 3 agentes em detalhe</div>
          <h2 style={sTitle}>Pipeline completo por tipo de agente</h2>
          <p style={sIntro}>As etapas exclusivas de cada jornada aparecem lado a lado. Após o ponto de convergência, o pipeline é único — sem duplicação. Clique em qualquer etapa para expandir.</p>
          {AGENTS.map((agent, ai) => {
            const color = agentColor[agent.id];
            return (
              <div key={agent.id} id={`agent-${agent.id}`} style={{ scrollMarginTop: 70, marginBottom: ai < 2 ? 72 : 0 }}>
                {/* Agent header */}
                <div style={{ marginBottom: 24, paddingBottom: 24, borderBottom: `1px solid ${color}33`, display: 'grid', gridTemplateColumns: '1fr auto', gap: 24, alignItems: 'start' }}>
                  <div>
                    <div style={{ fontFamily: mono, fontSize: 9, letterSpacing: 3, textTransform: 'uppercase', padding: '4px 12px', borderRadius: 3, marginBottom: 14, display: 'inline-block', color, background: `${color}18`, border: `1px solid ${color}55` }}>{agent.chip}</div>
                    <h3 style={{ fontFamily: "'Playfair Display', serif", fontSize: 30, fontWeight: 400, lineHeight: 1.15, marginBottom: 10, color: 'var(--o-text)' }}>
                      {agent.title}<br /><em style={{ fontStyle: 'italic', color: 'var(--o-sub)', fontSize: 26 }}>{agent.subtitle}</em>
                    </h3>
                    <p style={{ fontSize: 13.5, color: 'var(--o-sub)', lineHeight: 1.75, fontWeight: 300, maxWidth: 500, marginBottom: 16 }}>{agent.desc}</p>
                    <div style={{ background: `${color}06`, border: `1px solid ${color}20`, borderRadius: 8, padding: '14px 18px', display: 'flex', gap: 12, alignItems: 'flex-start' }}>
                      <span style={{ fontSize: 16, flexShrink: 0 }}>🎯</span>
                      <p style={{ fontSize: 13, color: 'var(--o-sub)', lineHeight: 1.7 }}><strong style={{ color: 'var(--o-text)' }}>Como funciona na prática:</strong> {agent.analogy}</p>
                    </div>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6, alignItems: 'flex-end' }}>
                    {agent.useCases.map(uc => (
                      <span key={uc} style={{ fontFamily: mono, fontSize: 10, color: 'var(--o-dim)', padding: '4px 12px', border: '1px solid var(--o-b1)', borderRadius: 3, whiteSpace: 'nowrap' }}>{uc}</span>
                    ))}
                  </div>
                </div>
                <PipelineLayout agent={agent} />
                {ai < 2 && <div style={{ marginTop: 56, borderTop: '1px solid var(--o-b1)' }} />}
              </div>
            );
          })}
        </section>

        {/* ══ GLOSSÁRIO ══ */}
        <section id="s-gloss" style={{ ...sec, marginTop: 56 }}>
          <div style={eyebrow}>Referência</div>
          <h2 style={sTitle}>Glossário — termos que você vai encontrar</h2>
          <p style={sIntro}>Definições simples para os termos técnicos usados nas configurações e pipelines.</p>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            {GLOSSARY.map(({ term, def }) => (
              <div key={term} style={{ background: 'var(--o-surface)', border: '1px solid var(--o-b1)', borderRadius: 8, padding: '14px 16px' }}>
                <div style={{ fontFamily: mono, fontSize: 11.5, fontWeight: 500, color: 'var(--o-active)', marginBottom: 5 }}>{term}</div>
                <div style={{ fontSize: 12.5, color: 'var(--o-sub)', lineHeight: 1.6 }}>{def}</div>
              </div>
            ))}
          </div>
        </section>

        {/* ══ FAQ ══ */}
        <section id="s-faq" style={sec}>
          <div style={eyebrow}>Dúvidas frequentes</div>
          <h2 style={sTitle}>Perguntas frequentes</h2>
          {FAQ.map((item, i) => (
            <div key={i} style={{ borderBottom: '1px solid var(--o-b1)' }}>
              <button onClick={() => setOpenFaqs(prev => { const s = new Set(prev); s.has(i) ? s.delete(i) : s.add(i); return s; })}
                style={{ width: '100%', padding: '16px 0', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, background: 'transparent', border: 'none', color: 'var(--o-text)', fontSize: 14, fontWeight: 500, cursor: 'pointer', textAlign: 'left' }}>
                {item.q}
                <span style={{ color: 'var(--o-dim)', fontSize: 12, flexShrink: 0, display: 'inline-block', transition: 'transform 0.2s', transform: openFaqs.has(i) ? 'rotate(180deg)' : 'none' }}>▾</span>
              </button>
              {openFaqs.has(i) && (
                <div style={{ padding: '0 0 18px', fontSize: 13.5, color: 'var(--o-sub)', lineHeight: 1.75, animation: 'o-fade-in 0.2s ease' }}>{item.a}</div>
              )}
            </div>
          ))}
        </section>

        {/* ══ CTA ══ */}
        <div style={{ background: 'var(--o-surface)', border: '1px solid var(--o-b1)', borderRadius: 12, padding: '36px 40px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 24, marginTop: 56 }}>
          <div>
            <h3 style={{ fontFamily: "'Playfair Display', serif", fontSize: 22, fontWeight: 400, color: 'var(--o-text)', marginBottom: 8 }}>Pronto para criar seu agente?</h3>
            <p style={{ fontSize: 14, color: 'var(--o-sub)', lineHeight: 1.65, maxWidth: 480 }}>Você já entende como cada tipo funciona. Agora é só configurar — leva menos de 10 minutos para ter seu agente ativo e respondendo leads.</p>
          </div>
          <Link to="/ai-profile" style={{ background: 'var(--o-active)', color: '#0d0e14', fontSize: 14, fontWeight: 600, padding: '12px 28px', borderRadius: 8, textDecoration: 'none', whiteSpace: 'nowrap', flexShrink: 0, display: 'inline-block' }}>
            Configurar meu agente →
          </Link>
        </div>

      </div>
    </OrionShell>
  );
}
