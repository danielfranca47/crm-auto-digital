import { useState } from 'react';
import {
  ArrowRight, Bot, Zap, Clock, Users, TrendingUp,
  CheckCircle, MessageSquare, Phone, ChevronDown,
  BarChart2, BellRing, Volume2, ImageIcon, Plug,
  Play, Check, X, ChevronRight, ArrowUp, Mail, Kanban, Shield,
} from 'lucide-react';

/* ─── Data ──────────────────────────────────────────────────── */

const sectors = [
  {
    label: 'Infoprodutos', icon: '📚',
    description:
      'A Lara recupera alunos que abandonaram o checkout, qualifica leads de cursos e envia provas sociais automaticamente. Ela conduz o lead do anúncio ao pagamento — sem você tocar.',
  },
  {
    label: 'Serviços', icon: '🛠️',
    description:
      'A Lara agenda consultas, confirma horários e faz follow-up de clientes que pediram orçamento mas sumiram. Ela nunca deixa um agendamento escapar.',
  },
  {
    label: 'E-commerce', icon: '🛒',
    description:
      'A Lara recupera carrinhos abandonados, envia rastreamento de pedido e responde dúvidas com fotos e vídeos do produto — tudo no automático.',
  },
  {
    label: 'Saúde & Estética', icon: '💆',
    description:
      'Triagem, agendamento, confirmação e follow-up pós-consulta. A Lara reduz faltas e mantém sua agenda sempre cheia — sem precisar de recepcionista.',
  },
  {
    label: 'Imóveis', icon: '🏠',
    description:
      'A Lara qualifica compradores com perguntas estratégicas, envia fotos automaticamente e agenda visitas — entregando apenas leads quentes pro corretor fechar.',
  },
  {
    label: 'Educação', icon: '🎓',
    description:
      'Matrículas, cobranças, dúvidas de alunos e lembretes de aula. A Lara atua como assistente acadêmica disponível 24h, sem custo de equipe.',
  },
];

const steps = [
  { num: '01', title: 'Conecte seu WhatsApp', desc: 'Via QR Code em segundos. Sem código, sem técnico.' },
  { num: '02', title: 'Apresente seu negócio à Lara', desc: 'Ela aprende sobre sua empresa, seus produtos e como você gosta de atender.' },
  { num: '03', title: 'Leads entram no funil', desc: 'Importe contatos ou receba leads direto do WhatsApp — a Lara assume na hora.' },
  { num: '04', title: 'A Lara qualifica e conversa', desc: 'Faz as perguntas certas, identifica intenção de compra e avança o lead no pipeline.' },
  { num: '05', title: 'A Lara faz o follow-up', desc: 'Quem não respondeu? No Growth, a Lara retoma automaticamente no momento certo — sem parecer chato, sem você tocar.' },
  { num: '06', title: 'Você fecha as vendas quentes', desc: 'Receba apenas os leads prontos para fechar. A Lara já fez o trabalho pesado.' },
];

const features = [
  { Icon: MessageSquare, title: 'Atendimento 24/7', desc: 'A Lara responde dúvidas, status e suporte enquanto você dorme — sem perder nenhum lead.' },
  { Icon: Kanban,        title: 'CRM com Pipeline Kanban', desc: 'Visualize onde está cada lead no funil. Mova, filtre e acompanhe em tempo real.' },
  { Icon: BellRing,      title: 'Follow-up que nunca esquece', desc: 'A Lara retoma conversas paradas no momento certo, sem parecer spam.' },
  { Icon: Users,         title: 'Qualificação de Leads', desc: 'A Lara identifica intenção de compra e entrega apenas oportunidades quentes.' },
  { Icon: Volume2,       title: 'Áudio na Voz da Lara', desc: 'Grave uma vez. A Lara envia como mensagem de voz nova para cada cliente.' },
  { Icon: ImageIcon,     title: 'Imagens e Vídeos', desc: 'A Lara envia catálogos, provas sociais e materiais de venda automaticamente.' },
  { Icon: BarChart2,     title: 'Modos de Venda', desc: 'Consultivo, agendamento ou direto — configure o jeito que a Lara deve vender.' },
  { Icon: Plug,          title: 'Integrações via API', desc: 'Hotmart, Kiwify e mais — a Lara conectada com as ferramentas que você já usa. (Em breve)' },
];

const differentials = [
  {
    Icon: Kanban, tag: 'Exclusivo', title: 'CRM nativo — tudo num lugar só',
    desc: 'Todos os seus leads organizados em um pipeline visual. Veja em qual etapa cada cliente está, o histórico completo da conversa e qual é a próxima ação — sem abrir outra ferramenta.',
  },
  {
    Icon: BellRing, tag: 'Diferencial', title: 'A Lara nunca esquece um follow-up',
    desc: 'Se o lead não respondeu, a Lara retoma automaticamente no melhor momento. Ela recupera vendas que pareciam perdidas — sem você fazer absolutamente nada. Incluso no plano Growth.',
  },
  {
    Icon: Volume2, tag: 'Único', title: 'Áudio como se fosse na hora',
    desc: 'Grave seu áudio uma vez. A Lara envia para cada cliente como mensagem de voz nova, humanizando o atendimento. Voz clonada em tempo real disponível no plano Growth.',
  },
  {
    Icon: BarChart2, tag: 'Flexível', title: 'A Lara vende do seu jeito',
    desc: 'Consultivo (aprofunda qualificação), agendamento (foca em marcar reunião) ou direto (vai reto ao fechamento). Você define a estratégia, a Lara executa.',
  },
];

const bonuses = [
  {
    num: '✦', title: 'Lara 24/7 — IA que atende, qualifica e fecha', value: 'vs R$3.500+/mês de SDR',
    desc: 'Atendimento automático 24h pelo WhatsApp, qualificação com score, follow-up sequencial e CRM com pipeline Kanban — 500 conversas/mês incluídas. A Lara nunca para.',
    highlight: true,
  },
  {
    num: '01', title: 'Ativação ao Vivo 1:1', value: 'R$297',
    desc: 'Sessão de 1h com o time para sair com tudo configurado e ativo no dia 1 — atendimento, qualificação e follow-up rodando. Start: sessão semanal em grupo.',
  },
  {
    num: '02', title: 'Playbook de 15 Scripts Prontos', value: 'R$197',
    desc: '15 scripts testados para qualificação, follow-up e recuperação de carrinho — copia, cola na Lara e funciona no dia 1. Zero tempo de criação.',
  },
  {
    num: '03', title: 'Suporte Diário ao Vivo por 30 dias', value: 'R$147',
    desc: 'Sessão diária às 15h com o time. Tire dúvidas, veja demos e otimize sua Lara em tempo real — sem ficar perdido.',
  },
  {
    num: '04', title: 'Playground de Testes', value: 'R$97',
    desc: 'Simule conversas reais antes de ligar para leads. Teste a Lara, ajuste respostas e ative com confiança — sem risco de erro com cliente de verdade.',
  },
];

const agents = [
  {
    emoji: '🎯',
    name: 'Agente SDR',
    badge: 'Alto Ticket',
    badgeColor: '#F59E0B',
    sectors: ['Imóveis', 'Consultoria', 'Coaching', 'Assessoria'],
    outcome: 'Agenda reuniões com leads quentes de alto ticket — enquanto você está em outras reuniões.',
    anchor: 'SDR humano custa R$3.500/mês. A Lara SDR custa R$297.',
    detail: 'Qualifica compradores, filtra curiosos e entrega apenas leads prontos para conversar negócio.',
  },
  {
    emoji: '💳',
    name: 'Agente Closer',
    badge: 'Baixo Ticket',
    badgeColor: '#10B981',
    sectors: ['Infoprodutos', 'E-commerce', 'Lojas Físicas'],
    outcome: 'Converte do primeiro "oi" até o pagamento — sem você precisar estar online.',
    anchor: '1 venda extra por mês paga o mês inteiro da Lara.',
    detail: 'Recupera carrinhos abandonados, converte leads que responderam tarde e faz follow-up de quem sumiu.',
  },
  {
    emoji: '📅',
    name: 'Agente Híbrido',
    badge: 'Serviços',
    badgeColor: '#8B5CF6',
    sectors: ['Psicólogos', 'Dentistas', 'Terapeutas', 'Clínicas'],
    outcome: 'Agenda sempre cheia, faltas eliminadas — sem precisar de recepcionista.',
    anchor: 'Recepcionista custa R$2.200/mês. A Lara Híbrido custa R$297 e trabalha 24/7.',
    detail: 'Responde dúvidas, confirma sessões com antecedência e faz follow-up de pacientes que sumiram.',
  },
];

const testimonials = [
  {
    quote: 'A Lara recuperou 3 leads que eu tinha dado como perdidos na primeira semana. Foram R$1.800 que eu não esperava mais.',
    name: 'Mariana S.',
    role: 'Infoprodutora — São Paulo',
    initial: 'M',
  },
  // Adicionar aqui quando CS trouxer o 2º depoimento
  // {
  //   quote: '',
  //   name: '',
  //   role: '',
  //   initial: '',
  // },
];

/* MUDANÇA 1 — Growth: badge + campaignPrice + features com 🔒 */
const plans = [
  {
    name: 'Start', price: '97', highlight: false, badge: null, comingSoon: false,
    campaignPrice: undefined as string | undefined,
    description: 'Para negócios com 20–100 leads/mês que querem o sistema rodando antes de escalar.',
    features: [
      '250 conversas IA/mês',
      '1 WhatsApp conectado',
      'Até 500 contatos no CRM',
      'CRM com pipeline Kanban',
      '🤖 Agente Closer — conversão de baixo ticket',
      'Qualificação automatizada',
      'Dashboard básico',
      '✦ Onboarding em grupo semanal',
      'Suporte por chat',
    ],
    footer: 'Excedente: R$0,60/conversa — upgrade natural para Growth',
    cta: 'Ativar minha Lara →',
  },
  {
    name: 'Growth', price: '297', highlight: true, badge: 'CAMPANHA FUNDADOR', comingSoon: false,
    campaignPrice: '147' as string | undefined,
    description: 'Para quem quer escalar — 100+ leads/mês',
    features: [
      '🔒 Preço de Fundador — travado para sempre',
      '✦ Ativação 1:1 + 15 Scripts + 30 dias ao vivo (R$641 em bônus)',
      '500 conversas IA/mês',
      '1 WhatsApp conectado',
      'Até 1.500 contatos no CRM',
      '✦ Follow-up automático',
      '✦ Playground de testes',
      '✦ Analytics avançados',
      'Dashboard completo',
      'Suporte prioritário',
    ],
    footer: 'Excedente: R$0,50/conversa',
    cta: 'Ativar minha Lara →',
  },
  {
    name: 'Scale', price: '397', highlight: false, badge: 'EM BREVE', comingSoon: true,
    campaignPrice: undefined as string | undefined,
    description: '',
    features: [
      '1.500 conversas IA/mês',
      'Até 3 WhatsApps',
      'Até 5.000 contatos',
      'Tudo do Growth',
      'Suporte prioritário',
      'Instância adicional: R$99/mês',
    ],
    footer: 'Excedente: R$0,40/conversa',
    cta: 'Entrar na lista →',
  },
  {
    name: 'Enterprise', price: '697', highlight: false, badge: 'EM BREVE', comingSoon: true,
    campaignPrice: undefined as string | undefined,
    description: '',
    features: [
      '5.000 conversas IA/mês',
      'Até 5 WhatsApps',
      'Até 15.000 contatos',
      'Tudo do Scale',
      'Onboarding dedicado',
      'Instância adicional: R$89/mês',
    ],
    footer: 'Excedente: R$0,30/conversa',
    cta: 'Entrar na lista →',
  },
];

const comparisonRows = [
  { label: 'Responde no WhatsApp 24/7',        ours: true,  theirs: true  },
  { label: 'CRM nativo embutido',              ours: true,  theirs: false },
  { label: 'Follow-up automático de inativos', ours: true,  theirs: false },
  { label: 'Recuperação de vendas perdidas',   ours: true,  theirs: false },
  { label: 'Pipeline visual de leads',         ours: true,  theirs: false },
  { label: 'Envio de áudio personalizado',     ours: true,  theirs: false },
  { label: 'Envio de imagens e vídeos',        ours: true,  theirs: false },
  { label: 'Múltiplos modos de venda',         ours: true,  theirs: false },
  { label: 'Playground de testes antes de ativar', ours: true,  theirs: false },
];

const faqs = [
  { q: 'A Lara precisa de WhatsApp Business API?', a: 'Não obrigatoriamente. Você começa com o WhatsApp Business comum via QR Code. A API oficial fica disponível para volumes maiores.' },
  { q: 'Quanto tempo para a Lara estar ativa?', a: 'Em menos de 30 minutos a Lara já está atendendo. Conecte o WhatsApp, apresente seu negócio a ela e ative.' },
  { q: 'A Lara soa natural ou parece robô?', a: 'A Lara é configurada com a personalidade da sua marca. Você controla o tom, as respostas e o fluxo — ela soa como alguém da sua equipe.' },
  { q: 'O que acontece quando o cliente precisa de humano?', a: 'A Lara transfere automaticamente com o contexto completo da conversa. Quem assumir já sabe tudo que foi discutido.' },
  { q: 'A Lara funciona para qualquer tipo de negócio?', a: 'Sim. Infoprodutos, serviços, e-commerce, saúde, imóveis, educação — a Lara se adapta ao seu setor.' },
  { q: 'Posso cancelar quando quiser?', a: 'Sim. Sem fidelidade, sem multa. Cancele com 1 clique a qualquer momento.' },
  { q: 'Como funciona a garantia de 30 dias?', a: 'É uma garantia dupla. Camada 1 (incondicional): ativou a Lara, usou por 30 dias, não gostou por qualquer motivo — devolvemos 100%. Sem perguntas, só manda uma mensagem. Camada 2 (performance): se você ativar, seguir o onboarding e em 30 dias não recuperar pelo menos 1 venda que daria como perdida, devolvemos o dinheiro E fazemos 1 sessão extra 1:1 de graça para entender o que aconteceu.' },
];

const waveformHeights = [3, 5, 7, 4, 6, 8, 3, 5, 7, 4, 6, 3, 5, 8, 4, 6, 5, 3];

/* ─── Component ─────────────────────────────────────────────── */

export default function CRMLandingV2({ lang: _lang = 'pt' }: { lang?: string }) {
  const [activeSector, setActiveSector] = useState(0);
  const [activeFaq, setActiveFaq] = useState<number | null>(null);

  return (
    <div className="min-h-screen bg-background text-foreground font-montserrat">

      {/* ── MUDANÇA 4 — CAMPAIGN BAR (novo, acima do navbar) ── */}
      <div
        className="fixed top-0 inset-x-0 z-[60] py-1.5 px-4 text-center text-xs font-semibold"
        style={{ background: '#4DD4FF', color: '#0D0A17' }}>
        🔒 Campanha Fundador ativa — 5 vagas a R$147/mês.{' '}
        <a href="#planos" className="underline font-bold">Garantir minha vaga →</a>
      </div>

      {/* ── NAVBAR — top-8 para não sobrepor a campaign bar ── */}
      <header className="fixed top-8 inset-x-0 z-50 bg-background/95 backdrop-blur-md border-b border-border">
        <div className="container mx-auto px-4 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <a href="#home" className="flex items-center">
              <div className="w-10 h-10 rounded-xl accent-gradient flex items-center justify-center mr-3">
                <div className="w-6 h-6 bg-background rounded-sm" />
              </div>
              <div>
                <span className="text-xl font-bold leading-none">Lara</span>
                <span className="block text-xs text-muted-foreground leading-none -mt-0.5">by DigitalPro</span>
              </div>
            </a>

            <nav className="hidden md:flex items-center space-x-7 text-sm">
              <a href="#funcionalidades" className="text-muted-foreground hover:text-foreground transition-smooth">Funcionalidades</a>
              <a href="#como-funciona"   className="text-muted-foreground hover:text-foreground transition-smooth">Como funciona</a>
              <a href="#planos"          className="text-muted-foreground hover:text-foreground transition-smooth">Planos</a>
              <a href="#faq"             className="text-muted-foreground hover:text-foreground transition-smooth">FAQ</a>
            </nav>

            <div className="flex items-center gap-3">
              <a href="#" className="hidden md:inline text-sm text-muted-foreground hover:text-foreground transition-smooth">Entrar</a>
              <a href="#planos" className="btn-hero text-sm px-5 py-2.5">Ativar agora →</a>
            </div>
          </div>
        </div>
      </header>

      {/* ── HERO — pt-24 para compensar campaign bar (2rem) + navbar (4rem) ── */}
      <section
        id="home"
        className="relative min-h-screen flex items-center pt-24 overflow-hidden"
        style={{
          backgroundImage: 'url(/hero-mascot.jpeg)',
          backgroundSize: 'cover',
          backgroundPosition: 'center right',
          backgroundRepeat: 'no-repeat',
        }}
      >
        <div className="absolute inset-0 pointer-events-none"
          style={{
            background: 'linear-gradient(to right, #0D0A17 30%, rgba(13,10,23,0.85) 55%, rgba(13,10,23,0.2) 100%)',
          }} />
        <div className="absolute bottom-0 inset-x-0 h-32 pointer-events-none"
          style={{ background: 'linear-gradient(to top, #0D0A17, transparent)' }} />

        <div className="container mx-auto px-4 lg:px-8 py-20 relative z-10">
          <div className="max-w-xl">

            {/* badge */}
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full border text-sm font-medium mb-7 animate-fade-in"
              style={{ background: 'rgba(77,212,255,0.1)', borderColor: 'rgba(77,212,255,0.3)', color: '#4DD4FF' }}>
              <Bot className="w-4 h-4" />
              Conheça a Lara — IA + CRM + Follow-up
            </div>

            {/* H1 */}
            <h1 className="text-hero mb-6 animate-fade-in animate-delay-100">
              Recupere sua primeira venda perdida em 7 dias —{' '}
              <span className="bg-gradient-to-r from-accent to-primary bg-clip-text text-transparent">
                ou devolvemos tudo, sem perguntas.
              </span>
            </h1>

            {/* sub */}
            <p className="text-xl text-muted-foreground mb-10 max-w-lg leading-relaxed animate-fade-in animate-delay-200">
              Para empreendedores que vendem pelo WhatsApp e perdem vendas toda semana por demora no atendimento ou falta de follow-up. A Lara resolve — com CRM nativo integrado, sem precisar de ferramenta extra.
            </p>

            {/* CTAs */}
            <div className="flex flex-col sm:flex-row gap-4 mb-14 animate-fade-in animate-delay-300">
              <a href="#planos" className="btn-hero flex items-center justify-center gap-2">
                Ativar minha Lara agora <ArrowRight className="w-4 h-4" />
              </a>
              <a href="#como-funciona"
                className="flex items-center justify-center gap-2 px-8 py-4 rounded-xl font-semibold border border-white/20 hover:bg-white/10 transition-smooth">
                <Play className="w-4 h-4" /> Ver como funciona
              </a>
            </div>

            {/* guarantee badge no hero */}
            <div className="flex items-center gap-3 animate-fade-in animate-delay-400">
              <Shield className="w-5 h-5 flex-shrink-0" style={{ color: '#4DD4FF' }} />
              <span className="text-sm text-muted-foreground">
                <strong style={{ color: '#4DD4FF' }}>Garantia incondicional de 30 dias</strong> — usou, não gostou por qualquer motivo, devolvemos tudo. Sem perguntas.
              </span>
            </div>
          </div>
        </div>

        <div className="absolute bottom-8 inset-x-0 flex justify-center animate-bounce text-muted-foreground z-10">
          <ChevronDown className="w-5 h-5" />
        </div>
      </section>

      {/* ── LOGO BAR ── */}
      <section className="py-8 border-y border-border bg-card/40">
        <div className="container mx-auto px-4 lg:px-8">
          <p className="text-center text-xs text-muted-foreground mb-5 uppercase tracking-widest font-semibold">
            A LARA JÁ TRABALHA EM NEGÓCIOS COMO
          </p>
          <div className="flex flex-wrap justify-center items-center gap-6 opacity-50">
            {['Infoprodutos', 'E-commerce', 'Saúde', 'Imóveis', 'Educação', 'Serviços', 'Beleza'].map(s => (
              <span key={s}
                className="text-xs font-bold text-muted-foreground px-5 py-2 rounded-full border border-border uppercase tracking-wide">
                {s}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* ── PROBLEM AGITATION ── */}
      <section className="py-16 px-4">
        <div className="container mx-auto max-w-3xl">
          <div className="text-center mb-10">
            <h2 className="text-2xl font-bold">Reconhece alguma dessas situações?</h2>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-8">
            {[
              'Você responde o WhatsApp o dia todo mas ainda perde leads quando está ocupado',
              'Você sabe que deveria fazer follow-up mas o dia passa e não fez',
              'Você tem contatos espalhados, não sabe quais são quentes, quais desistiram',
              'Já tentou um chatbot genérico mas ele parecia robótico e não qualificava',
            ].map(item => (
              <div key={item} className="portfolio-card flex items-start gap-3">
                <div className="w-5 h-5 rounded border-2 flex-shrink-0 mt-0.5"
                  style={{ borderColor: 'rgba(77,212,255,0.5)' }} />
                <span className="text-sm text-muted-foreground leading-relaxed">{item}</span>
              </div>
            ))}
          </div>
          <p className="text-center text-sm font-semibold" style={{ color: '#4DD4FF' }}>
            Se você se identificou com pelo menos 2: a Lara foi feita pra resolver isso.
          </p>
        </div>
      </section>

      {/* ── SECTOR TABS ── */}
      <section className="py-20 px-4">
        <div className="container mx-auto max-w-5xl">
          <div className="text-center mb-12">
            <span className="text-accent text-sm font-semibold uppercase tracking-widest">Qualquer setor</span>
            <h2 className="text-heading mt-2">Se você vende pelo WhatsApp, a Lara trabalha por você</h2>
          </div>

          <div className="flex flex-wrap justify-center gap-2 mb-10">
            {sectors.map((s, i) => (
              <button key={s.label} onClick={() => setActiveSector(i)}
                className="flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium transition-smooth border"
                style={activeSector === i
                  ? { background: 'rgba(77,212,255,0.15)', borderColor: '#4DD4FF', color: '#4DD4FF' }
                  : { borderColor: 'hsl(var(--border))', color: 'hsl(var(--muted-foreground))' }}>
                <span>{s.icon}</span> {s.label}
              </button>
            ))}
          </div>

          <div className="portfolio-card p-10 text-center max-w-2xl mx-auto">
            <div className="text-5xl mb-4">{sectors[activeSector].icon}</div>
            <h3 className="text-xl font-bold mb-3">{sectors[activeSector].label}</h3>
            <p className="text-muted-foreground leading-relaxed">{sectors[activeSector].description}</p>
            <a href="#planos" className="btn-hero inline-flex items-center gap-2 mt-7 text-sm px-6 py-3">
              Quero ativar a Lara <ArrowRight className="w-4 h-4" />
            </a>
          </div>
        </div>
      </section>

      {/* ── AGENTS — Os 3 agentes especializados ── */}
      <section className="py-20 px-4">
        <div className="container mx-auto max-w-5xl">
          <div className="text-center mb-12">
            <span className="text-accent text-sm font-semibold uppercase tracking-widest">
              Especializado no seu tipo de venda
            </span>
            <h2 className="text-heading mt-2">
              Não é um chatbot genérico.<br />
              É um agente treinado pro seu negócio.
            </h2>
            <p className="text-muted-foreground mt-3 max-w-xl mx-auto">
              Qual é o seu? Escolha o agente e a Lara já sabe como vender do seu jeito.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {agents.map((agent) => (
              <div key={agent.name}
                className="portfolio-card flex flex-col border"
                style={{ borderColor: `${agent.badgeColor}33` }}>

                <div className="flex items-center gap-3 mb-4">
                  <div className="text-4xl">{agent.emoji}</div>
                  <div>
                    <div className="font-bold text-base">{agent.name}</div>
                    <span
                      className="text-xs px-2 py-0.5 rounded-full font-semibold"
                      style={{
                        background: `${agent.badgeColor}22`,
                        color: agent.badgeColor,
                      }}>
                      {agent.badge}
                    </span>
                  </div>
                </div>

                <div className="flex flex-wrap gap-1.5 mb-4">
                  {agent.sectors.map(s => (
                    <span key={s}
                      className="text-xs px-2 py-0.5 rounded-full border text-muted-foreground"
                      style={{ borderColor: 'hsl(var(--border))' }}>
                      {s}
                    </span>
                  ))}
                </div>

                <p className="text-sm font-semibold mb-2 leading-snug flex-1">
                  {agent.outcome}
                </p>

                <p className="text-xs text-muted-foreground leading-relaxed mb-4">
                  {agent.detail}
                </p>

                <div
                  className="text-xs px-3 py-2 rounded-lg font-medium mt-auto"
                  style={{
                    background: `${agent.badgeColor}11`,
                    color: agent.badgeColor,
                    borderLeft: `3px solid ${agent.badgeColor}`,
                  }}>
                  {agent.anchor}
                </div>
              </div>
            ))}
          </div>

          <div className="text-center mt-10">
            <p className="text-sm text-muted-foreground mb-4">
              Todos os 3 agentes estão incluídos no plano{' '}
              <strong style={{ color: '#4DD4FF' }}>Growth</strong>.
              O Start inclui o Agente Closer.
            </p>
            <a href="#planos" className="btn-hero inline-flex items-center gap-2">
              Ver planos e escolher meu agente <ArrowRight className="w-4 h-4" />
            </a>
          </div>
        </div>
      </section>

      {/* ── HOW IT WORKS ── */}
      <section id="como-funciona" className="py-20 px-4 bg-secondary/30">
        <div className="container mx-auto max-w-5xl">
          <div className="text-center mb-14">
            <span className="text-accent text-sm font-semibold uppercase tracking-widest">Simples assim</span>
            <h2 className="text-heading mt-2">Do primeiro contato ao fechamento — a Lara no comando</h2>
            <p className="text-muted-foreground mt-3">Configure uma vez. A Lara trabalha para sempre.</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {steps.map((step, i) => (
              <div key={step.num} className="portfolio-card relative">
                <div className="text-5xl font-extrabold mb-4 select-none leading-none"
                  style={{ color: '#4DD4FF', opacity: 0.25 }}>
                  {step.num}
                </div>
                <h3 className="text-base font-bold mb-2">{step.title}</h3>
                <p className="text-muted-foreground text-sm leading-relaxed">{step.desc}</p>
                {i < steps.length - 1 && (
                  <ChevronRight className="absolute -right-3 top-1/2 -translate-y-1/2 text-accent hidden lg:block w-5 h-5" />
                )}
              </div>
            ))}
          </div>

          <div className="text-center mt-10">
            <a href="#planos" className="btn-hero inline-flex items-center gap-2">
              Ativar minha Lara agora <ArrowRight className="w-4 h-4" />
            </a>
          </div>
        </div>
      </section>

      {/* ── FEATURES GRID ── */}
      <section id="funcionalidades" className="py-20 px-4">
        <div className="container mx-auto max-w-6xl">
          <div className="text-center mb-14">
            <span className="text-accent text-sm font-semibold uppercase tracking-widest">⚡ O que a Lara faz</span>
            <h2 className="text-heading mt-2">Tudo que a Lara faz pelo seu negócio</h2>
            <p className="text-muted-foreground mt-3 max-w-xl mx-auto">
              A Lara atende, vende e acompanha leads 24/7 — enquanto você foca no que realmente importa.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {features.map(({ Icon, title, desc }) => (
              <div key={title} className="portfolio-card text-center">
                <div className="w-14 h-14 rounded-2xl accent-gradient flex items-center justify-center mx-auto mb-4 shadow-hero">
                  <Icon className="w-6 h-6 text-accent-foreground" />
                </div>
                <h3 className="font-bold mb-2 text-sm">{title}</h3>
                <p className="text-muted-foreground text-xs leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── DIFFERENTIALS ── */}
      <section className="py-20 px-4 bg-secondary/30">
        <div className="container mx-auto max-w-5xl">
          <div className="text-center mb-14">
            <span className="text-accent text-sm font-semibold uppercase tracking-widest">O diferencial</span>
            <h2 className="text-heading mt-2">A Lara não é só um chatbot. É sua melhor vendedora.</h2>
            <p className="text-muted-foreground mt-3 max-w-xl mx-auto">
              Outros bots respondem mensagens. A Lara gerencia o processo de venda de ponta a ponta — e nunca esquece um follow-up.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {differentials.map(({ Icon, tag, title, desc }) => (
              <div key={title} className="portfolio-card flex gap-5">
                <div className="w-12 h-12 rounded-xl accent-gradient flex items-center justify-center flex-shrink-0 mt-0.5 shadow-hero">
                  <Icon className="w-5 h-5 text-accent-foreground" />
                </div>
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <h3 className="font-bold">{title}</h3>
                    <span className="text-xs px-2 py-0.5 rounded-full font-medium"
                      style={{ background: 'rgba(77,212,255,0.15)', color: '#4DD4FF' }}>
                      {tag}
                    </span>
                  </div>
                  <p className="text-muted-foreground text-sm leading-relaxed">{desc}</p>
                </div>
              </div>
            ))}
          </div>

          <div className="text-center mt-10">
            <a href="#planos" className="btn-hero inline-flex items-center gap-2">
              Ativar minha Lara <ArrowRight className="w-4 h-4" />
            </a>
          </div>
        </div>
      </section>

      {/* ── AUDIO SECTION ── */}
      <section className="py-20 px-4">
        <div className="container mx-auto max-w-4xl">
          <div className="portfolio-card p-10 text-center relative overflow-hidden">
            <div className="absolute inset-0 pointer-events-none"
              style={{ background: 'radial-gradient(ellipse at 50% 0%, rgba(77,212,255,0.06), transparent 70%)' }} />

            <div className="relative">
              <span className="text-accent text-sm font-semibold uppercase tracking-widest">✦ A Voz da Lara</span>
              <h2 className="text-heading mt-3 mb-4">
                A Lara fala com cada cliente{' '}
                <span className="bg-gradient-to-r from-accent to-primary bg-clip-text text-transparent">
                  como se fosse na hora.
                </span>
              </h2>
              <p className="text-muted-foreground max-w-xl mx-auto mb-10 leading-relaxed">
                Grave seu áudio uma vez. A Lara envia para cada cliente como mensagem de voz nova, no momento certo da conversa — humanizando o atendimento sem você precisar estar lá.
              </p>

              <div className="flex flex-col sm:flex-row gap-4 justify-center items-center">
                <div className="portfolio-card px-6 py-4 flex items-center gap-3 w-full sm:w-auto">
                  <div className="w-10 h-10 rounded-full bg-muted flex items-center justify-center flex-shrink-0">
                    <Volume2 className="w-4 h-4 text-muted-foreground" />
                  </div>
                  <div className="text-left">
                    <div className="text-xs text-muted-foreground mb-1">Áudio gravado por você</div>
                    <div className="flex gap-px items-end" style={{ height: 24 }}>
                      {waveformHeights.map((h, i) => (
                        <div key={i} className="w-1 rounded-full bg-muted-foreground opacity-50"
                          style={{ height: `${h * 3}px` }} />
                      ))}
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">01:24</div>
                  </div>
                </div>

                <ArrowRight className="w-6 h-6 text-accent hidden sm:block flex-shrink-0" />

                <div className="portfolio-card px-6 py-4 flex items-center gap-3 w-full sm:w-auto border"
                  style={{ borderColor: 'rgba(77,212,255,0.4)' }}>
                  <div className="w-10 h-10 rounded-full accent-gradient flex items-center justify-center flex-shrink-0">
                    <Volume2 className="w-4 h-4 text-accent-foreground" />
                  </div>
                  <div className="text-left">
                    <div className="text-xs mb-1" style={{ color: '#4DD4FF' }}>Enviado ao cliente</div>
                    <div className="flex gap-px items-end" style={{ height: 24 }}>
                      {waveformHeights.map((h, i) => (
                        <div key={i} className="w-1 rounded-full"
                          style={{ height: `${h * 3}px`, background: '#4DD4FF' }} />
                      ))}
                    </div>
                    <div className="text-xs mt-1" style={{ color: '#4DD4FF' }}>01:24 ✓✓</div>
                  </div>
                </div>
              </div>

              <p className="text-xs text-muted-foreground mt-8">
                ✦ Voz clonada em tempo real disponível a partir do{' '}
                <strong style={{ color: '#4DD4FF' }}>plano Growth</strong>
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ── COMPARISON TABLE ── */}
      <section className="py-20 px-4 bg-secondary/30">
        <div className="container mx-auto max-w-3xl">
          <div className="text-center mb-12">
            <span className="text-accent text-sm font-semibold uppercase tracking-widest">Comparativo</span>
            <h2 className="text-heading mt-2">Por que somos diferentes</h2>
          </div>

          <div className="portfolio-card overflow-hidden p-0">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left px-6 py-4 text-muted-foreground font-medium">Funcionalidade</th>
                  <th className="px-6 py-4 text-center">
                    <span className="font-bold text-accent">Lara</span>
                  </th>
                  <th className="px-6 py-4 text-center text-muted-foreground">Bot genérico</th>
                </tr>
              </thead>
              <tbody>
                {comparisonRows.map(({ label, ours, theirs }, i) => (
                  <tr key={label} className={i % 2 === 0 ? 'bg-muted/10' : ''}>
                    <td className="px-6 py-3">{label}</td>
                    <td className="px-6 py-3 text-center">
                      {ours
                        ? <Check className="w-4 h-4 text-accent inline" />
                        : <X    className="w-4 h-4 text-destructive inline" />}
                    </td>
                    <td className="px-6 py-3 text-center">
                      {theirs
                        ? <Check className="w-4 h-4 text-muted-foreground inline" />
                        : <X    className="w-4 h-4 text-destructive inline" />}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="px-6 py-4 border-t border-border bg-muted/5">
              <p className="text-xs text-muted-foreground">
                ✦ Follow-up automático, Playground e Analytics avançados inclusos no{' '}
                <strong style={{ color: '#4DD4FF' }}>Growth</strong>.
                {' '}Start inclui atendimento 24/7 + CRM + qualificação — ideal para quem está estruturando o processo.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ── SUPPORT ── */}
      <section className="py-20 px-4">
        <div className="container mx-auto max-w-5xl">
          <div className="text-center mb-14">
            <span className="text-accent text-sm font-semibold uppercase tracking-widest">Suporte completo</span>
            <h2 className="text-heading mt-2">A Lara não vem sozinha — você tem suporte real</h2>
            <p className="text-muted-foreground mt-3 max-w-xl mx-auto">
              Da primeira configuração ao dia a dia, tem alguém do lado pra te ajudar a tirar o máximo da Lara.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {[
              { icon: Zap,           title: 'Onboarding guiado',     desc: 'Reunião de boas-vindas para configurar seus primeiros fluxos.' },
              { icon: Clock,         title: 'Suporte diário ao vivo', desc: 'Sessão diária às 15h para tirar dúvidas e ver demos rápidas.' },
              { icon: MessageSquare, title: 'Chat na plataforma',     desc: 'Atendimento direto no produto, sem sair do seu fluxo de trabalho.' },
              { icon: TrendingUp,    title: 'Base de conhecimento',   desc: 'Aulas práticas de todas as áreas do produto, do básico ao avançado.' },
            ].map(({ icon: Icon, title, desc }) => (
              <div key={title} className="portfolio-card text-center">
                <div className="w-14 h-14 rounded-2xl accent-gradient flex items-center justify-center mx-auto mb-4 shadow-hero">
                  <Icon className="w-6 h-6 text-accent-foreground" />
                </div>
                <h3 className="font-bold mb-2 text-sm">{title}</h3>
                <p className="text-muted-foreground text-xs leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── BONUS STACK — MUDANÇA 3 ── */}
      <section className="py-20 px-4 bg-secondary/30">
        <div className="container mx-auto max-w-4xl">
          <div className="text-center mb-12">
            <span className="text-accent text-sm font-semibold uppercase tracking-widest">✦ O que você está recebendo</span>
            {/* MUDANÇA 3: h2 atualizado — remove R$297 como preço de compra */}
            <h2 className="text-heading mt-2">
              Campanha Fundador: você investe R$147/mês.<br />
              Sua alternativa custaria{' '}
              <span className="bg-gradient-to-r from-accent to-primary bg-clip-text text-transparent">
                R$3.500+/mês.
              </span>
            </h2>
            <p className="text-muted-foreground mt-3 max-w-xl mx-auto">
              Incluídos no plano Growth — para você sair do zero ao resultado no dia 1.
            </p>
          </div>

          <div className="space-y-4 mb-10">
            {bonuses.map(bonus => (
              <div key={bonus.num}
                className="portfolio-card flex items-start gap-5"
                style={'highlight' in bonus && bonus.highlight
                  ? { borderColor: 'rgba(77,212,255,0.4)', border: '1px solid', background: 'rgba(77,212,255,0.04)' }
                  : {}}>
                <div className="text-3xl font-extrabold select-none leading-none flex-shrink-0 pt-1"
                  style={{ color: '#4DD4FF', opacity: 'highlight' in bonus && bonus.highlight ? 0.8 : 0.35 }}>
                  {bonus.num}
                </div>
                <div className="flex-1">
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1 mb-2">
                    <h3 className={'highlight' in bonus && bonus.highlight ? 'font-bold text-base' : 'font-bold'}
                      style={'highlight' in bonus && bonus.highlight ? { color: '#4DD4FF' } : {}}>
                      {'highlight' in bonus && bonus.highlight ? '' : '✦ '}{bonus.title}
                    </h3>
                    <span className="text-sm font-bold flex-shrink-0" style={{ color: '#4DD4FF' }}>
                      {'highlight' in bonus && bonus.highlight ? '' : 'valor: '}{bonus.value}
                    </span>
                  </div>
                  <p className="text-muted-foreground text-sm leading-relaxed">{bonus.desc}</p>
                </div>
              </div>
            ))}
          </div>

          {/* P1-C — Bloco de comparação de mercado */}
          <div className="portfolio-card p-6 mb-4">
            <p className="text-xs font-semibold text-center mb-5 uppercase tracking-widest text-muted-foreground">
              Sem a Lara, você pagaria:
            </p>
            <div className="space-y-0">
              {[
                {
                  label: 'SDR humano (alto ticket)',
                  sub: 'Sem 24/7. Sem CRM integrado. Tira férias.',
                  price: 'R$3.500/mês',
                  highlight: true,
                },
                {
                  label: 'Recepcionista (serviços)',
                  sub: 'Sem follow-up automático. Sem analytics.',
                  price: 'R$2.200/mês',
                  highlight: true,
                },
                {
                  label: 'Chatbot genérico',
                  sub: 'Sem agente especializado. Sem CRM nativo.',
                  price: 'R$200+/mês',
                  highlight: false,
                },
                {
                  label: 'CRM separado (ex: HubSpot básico)',
                  sub: 'Sem IA. Sem WhatsApp nativo.',
                  price: 'R$500/mês',
                  highlight: false,
                },
              ].map(({ label, sub, price, highlight }) => (
                <div
                  key={label}
                  className="flex items-start justify-between gap-4 py-3 border-b border-border last:border-0">
                  <div>
                    <span className="text-sm text-foreground">{label}</span>
                    <span className="block text-xs text-muted-foreground opacity-60 mt-0.5">{sub}</span>
                  </div>
                  <span
                    className="text-sm font-bold flex-shrink-0"
                    style={{ color: highlight ? 'hsl(var(--destructive))' : 'hsl(var(--muted-foreground))' }}>
                    {price}
                  </span>
                </div>
              ))}
            </div>
            <div className="mt-5 pt-4 border-t border-border">
              <div className="flex items-center justify-between text-sm mb-3">
                <span className="text-muted-foreground">Total alternativo:</span>
                <span className="font-bold text-foreground">R$3.500 – R$6.200/mês</span>
              </div>
              <div
                className="text-center text-sm font-semibold py-2 px-4 rounded-lg"
                style={{ background: 'rgba(77,212,255,0.1)', color: '#4DD4FF' }}>
                A Lara faz tudo isso por{' '}
                <strong>R$147/mês</strong>
                {' '}— menos de R$5/dia.
              </div>
            </div>
          </div>

          {/* MUDANÇA 3 — card de resumo atualizado para campanha Fundador */}
          <div className="portfolio-card p-6 border" style={{ borderColor: 'rgba(77,212,255,0.4)' }}>
            <div className="text-center space-y-2">
              <div className="text-sm text-muted-foreground">
                Campanha Fundador: você investe{' '}
                <span className="font-bold text-accent text-lg">R$147/mês</span>
                {' '}pelos primeiros 12 meses
              </div>
              <div className="text-xs text-muted-foreground">
                Depois:{' '}
                <strong style={{ color: '#4DD4FF' }}>R$197/mês para sempre</strong>
                {' '}— enquanto novos clientes pagarão{' '}
                <span className="line-through opacity-50">R$297/mês</span>
              </div>
              <div className="text-xs text-muted-foreground mt-2">
                Equivalente a contratar: SDR humano (R$3.500/mês) ou recepcionista (R$2.200/mês).
                A Lara faz os dois por menos.
              </div>
              <div className="text-xs text-muted-foreground mt-2 opacity-70">
                Garantia incondicional de 30 dias — você entra, usa, e decide. O risco é nosso.
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── LAUNCH ACCESS — MUDANÇA 2 — vira "O que significa entrar como Fundador?" ── */}
      <section className="py-20 px-4">
        <div className="container mx-auto max-w-3xl text-center">
          <span className="text-accent text-sm font-semibold uppercase tracking-widest">✦ Preço de Fundador</span>
          {/* MUDANÇA 2: título sem preço */}
          <h2 className="text-heading mt-2 mb-4">
            O que significa entrar como Fundador?
          </h2>
          {/* MUDANÇA 2: parágrafo sem referência isolada de preço */}
          <p className="text-muted-foreground max-w-xl mx-auto mb-10 leading-relaxed">
            Fundadores são os primeiros parceiros da Lara. Você entra antes do lançamento público,
            com preço menor, e esse preço fica travado para sempre — mesmo quando o Growth subir
            para R$297/mês para novos clientes.
            <br /><br />
            Você nunca paga mais do que R$197/mês. Para sempre.
            E os primeiros 12 meses saem por ainda menos.
          </p>
          <div className="portfolio-card p-8 max-w-lg mx-auto border" style={{ borderColor: 'rgba(77,212,255,0.35)' }}>
            <div className="text-4xl mb-4">🔒</div>
            {/* MUDANÇA 2: h3 sem "vagas apenas" */}
            <h3 className="font-bold text-lg mb-2" style={{ color: '#4DD4FF' }}>5 vagas disponíveis esta semana</h3>
            {/* MUDANÇA 2: p1 atualizado */}
            <p className="text-muted-foreground text-sm mb-3 leading-relaxed">
              O onboarding ao vivo acontece toda terça — <strong className="text-foreground">10 vagas por sessão</strong>. Fundadores têm sessão 1:1 prioritária: saem ativos no dia 1, não em semanas.
            </p>
            {/* MUDANÇA 2: p2 sem número de preço isolado */}
            <p className="text-xs text-muted-foreground mb-6 opacity-75">
              Depois dos primeiros 12 meses, seu preço trava em R$197/mês — para sempre.
              Novos clientes que entrarem depois da campanha pagarão R$297/mês.
            </p>
            <a href="#planos" className="btn-hero inline-flex items-center gap-2">
              Garantir minha vaga de Fundador <ArrowRight className="w-4 h-4" />
            </a>
            {/* MUDANÇA 2: badge atualizado */}
            <p className="text-xs text-muted-foreground mt-4" style={{ color: '#4DD4FF' }}>
              ✦ Ativo agora — campanha encerra quando as vagas acabarem
            </p>
          </div>
        </div>
      </section>

      {/* ── QUALIFIER ── */}
      <section className="py-20 px-4">
        <div className="container mx-auto max-w-4xl">
          <div className="text-center mb-12">
            <span className="text-accent text-sm font-semibold uppercase tracking-widest">Seja honesto</span>
            <h2 className="text-heading mt-2">A Lara é pra você?</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            <div className="portfolio-card" style={{ borderColor: 'rgba(239,68,68,0.2)', border: '1px solid' }}>
              <h3 className="font-bold text-base mb-6 flex items-center gap-2 text-destructive">
                <X className="w-5 h-5" />
                Isso NÃO é pra você se:
              </h3>
              <ul className="space-y-5 text-sm">
                {[
                  { cond: 'Você recebe menos de 20 leads por mês no WhatsApp', why: 'A Lara precisa de volume mínimo pra mostrar resultado — abaixo disso, o ROI não fecha.' },
                  { cond: 'Você quer um robô que responda igual a FAQ', why: 'Isso qualquer chatbot faz — a Lara é diferente e exige configuração.' },
                  { cond: 'Você não quer acompanhar os primeiros 7 dias', why: 'A Lara aprende com você. Os primeiros dias definem os resultados do mês.' },
                ].map(({ cond, why }) => (
                  <li key={cond}>
                    <span className="flex items-start gap-2 text-muted-foreground">
                      <X className="w-4 h-4 text-destructive flex-shrink-0 mt-0.5" />
                      <span>{cond}</span>
                    </span>
                    <span className="block text-xs text-muted-foreground opacity-60 ml-6 mt-1">({why})</span>
                  </li>
                ))}
              </ul>
            </div>

            <div className="portfolio-card" style={{ borderColor: 'rgba(77,212,255,0.35)', border: '1px solid' }}>
              <h3 className="font-bold text-base mb-6 flex items-center gap-2" style={{ color: '#4DD4FF' }}>
                <CheckCircle className="w-5 h-5" />
                Isso É pra você se:
              </h3>
              <ul className="space-y-5 text-sm">
                {[
                  'Você perde vendas por não responder rápido o suficiente',
                  'Você já teve leads quentes que "esfriaram" porque esqueceu de dar follow-up',
                  'Você recebe entre 20 e 100 leads/mês e quer organizar o processo (Start)',
                  'Você recebe 100+ leads/mês e quer escalar sem contratar mais gente (Growth)',
                ].map(item => (
                  <li key={item} className="flex items-start gap-2">
                    <Check className="w-4 h-4 flex-shrink-0 mt-0.5" style={{ color: '#4DD4FF' }} />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* ── SOCIAL PROOF ── */}
      <section className="py-20 px-4">
        <div className="container mx-auto max-w-4xl">
          <div className="text-center mb-12">
            <span className="text-accent text-sm font-semibold uppercase tracking-widest">✦ Quem já usa a Lara</span>
            <h2 className="text-heading mt-2">Resultados reais, de negócios reais</h2>
          </div>

          <div className={`grid grid-cols-1 ${testimonials.length >= 3 ? 'md:grid-cols-3' : testimonials.length === 2 ? 'md:grid-cols-2' : 'max-w-lg mx-auto'} gap-6 mb-8`}>
            {testimonials.map((t) => (
              <div key={t.name} className="portfolio-card border" style={{ borderColor: 'rgba(77,212,255,0.25)' }}>
                <div className="flex items-center gap-1 mb-4">
                  {[1,2,3,4,5].map(i => (
                    <span key={i} className="text-sm" style={{ color: '#4DD4FF' }}>★</span>
                  ))}
                </div>
                <p className="text-sm leading-relaxed mb-5">"{t.quote}"</p>
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-full accent-gradient flex items-center justify-center flex-shrink-0">
                    <span className="text-sm font-bold text-accent-foreground">{t.initial}</span>
                  </div>
                  <div>
                    <div className="text-sm font-semibold">{t.name}</div>
                    <div className="text-xs text-muted-foreground">{t.role}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── PLANS — MUDANÇA 1 ── */}
      <section id="planos" className="py-20 px-4 bg-secondary/30">
        <div className="container mx-auto max-w-6xl">
          <div className="text-center mb-10">
            <span className="text-accent text-sm font-semibold uppercase tracking-widest">✦ Planos da Lara</span>
            <h2 className="text-heading mt-2">Escolha o plano e a Lara começa hoje</h2>
            <p className="text-muted-foreground mt-3">Sem fidelidade. Cancele quando quiser.</p>
            <p className="text-sm text-muted-foreground mt-2 opacity-70">
              20–100 leads/mês? Comece pelo Start. 100+ leads? O Growth é o seu plano.
            </p>
          </div>

          {/* Guarantee banner */}
          <div className="portfolio-card p-7 mb-12 relative overflow-hidden border"
            style={{ borderColor: 'rgba(77,212,255,0.35)' }}>
            <div className="absolute inset-0 pointer-events-none"
              style={{ background: 'radial-gradient(ellipse at 50% 0%, rgba(77,212,255,0.05), transparent 70%)' }} />
            <div className="relative">
              <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4 mb-5">
                <Shield className="w-8 h-8 flex-shrink-0" style={{ color: '#4DD4FF' }} />
                <div>
                  <h3 className="font-bold text-base mb-1">Garantia dupla — o risco é 100% nosso</h3>
                  <p className="text-muted-foreground text-sm leading-relaxed">
                    <strong className="text-foreground">Camada 1 — Incondicional:</strong> ativou a Lara, usou por 30 dias, não gostou por qualquer motivo — devolvemos 100%. Sem perguntas. Só manda uma mensagem.
                  </p>
                </div>
              </div>
              <div className="border-t border-border pt-5">
                <p className="text-sm text-muted-foreground">
                  <strong className="text-foreground" style={{ color: '#4DD4FF' }}>Camada 2 — Performance:</strong>{' '}
                  Se você ativar a Lara, seguir o onboarding e em 30 dias não recuperar pelo menos 1 venda que daria como perdida — devolvemos o dinheiro <em>e</em> fazemos 1 sessão extra 1:1 de graça para entender o que aconteceu. Você não pode sair no prejuízo.
                </p>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
            {plans.map(plan => (
              <div key={plan.name}
                className={`portfolio-card flex flex-col relative ${plan.highlight ? 'ring-2' : ''} ${plan.comingSoon ? 'opacity-60' : ''}`}
                style={plan.highlight ? { '--tw-ring-color': '#4DD4FF' } as React.CSSProperties : {}}>
                {plan.badge && (
                  <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 text-xs font-bold px-4 py-1 rounded-full whitespace-nowrap"
                    style={plan.comingSoon
                      ? { background: 'hsl(var(--muted))', color: 'hsl(var(--muted-foreground))' }
                      : { background: '#4DD4FF', color: '#0D0A17' }}>
                    {plan.badge}
                  </div>
                )}

                <div className="mb-6">
                  <h3 className="text-lg font-bold mb-1">{plan.name}</h3>

                  {/* MUDANÇA 1B — micro-badge de escassez exclusivo do Growth */}
                  {plan.campaignPrice && (
                    <span className="inline-block text-xs px-2 py-0.5 rounded-full font-medium mb-2"
                      style={{ background: 'rgba(77,212,255,0.15)', color: '#4DD4FF' }}>
                      5 vagas restantes
                    </span>
                  )}

                  {plan.description && (
                    <p className="text-xs text-muted-foreground mb-3 leading-snug">{plan.description}</p>
                  )}

                  {/* MUDANÇA 1B — bloco de preço: âncora R$297 tachado + R$147 ativo para Growth */}
                  {plan.campaignPrice ? (
                    <>
                      <div className="mb-1">
                        <span
                          className="text-sm line-through text-muted-foreground opacity-60 mr-1"
                          aria-label="Preço regular">
                          R${plan.price}
                        </span>
                        <span className="text-xs text-muted-foreground opacity-60">/mês</span>
                      </div>
                      <div className="flex items-baseline gap-1">
                        <span className="text-4xl font-extrabold text-accent">R${plan.campaignPrice}</span>
                        <span className="text-muted-foreground text-sm">/mês</span>
                      </div>
                      <p className="text-xs text-muted-foreground mt-1">pelos primeiros 12 meses</p>
                      {/* MUDANÇA 1C — footer de dois níveis */}
                      <div className="text-xs text-muted-foreground mt-1 space-y-0.5">
                        <p style={{ color: '#4DD4FF' }} className="font-medium">
                          Depois: R$197/mês para sempre — preço travado
                        </p>
                        <p>
                          Novos clientes pagarão R$297/mês · Excedente: R$0,50/conversa
                        </p>
                      </div>
                    </>
                  ) : (
                    <>
                      <div className="flex items-baseline gap-1">
                        <span className="text-4xl font-extrabold text-accent">R${plan.price}</span>
                        <span className="text-muted-foreground text-sm">/mês</span>
                      </div>
                      {plan.footer && (
                        <p className="text-xs text-muted-foreground mt-1">{plan.footer}</p>
                      )}
                    </>
                  )}
                </div>

                <ul className="space-y-3 flex-1 mb-8">
                  {plan.features.map(f => (
                    <li key={f} className="flex items-start gap-2 text-sm">
                      <Check className="w-4 h-4 text-accent flex-shrink-0 mt-0.5" />
                      <span className={f.startsWith('✦') || f.startsWith('🔒') ? 'font-medium' : 'text-muted-foreground'}
                        style={f.startsWith('✦') || f.startsWith('🔒') ? { color: '#4DD4FF' } : {}}>
                        {f}
                      </span>
                    </li>
                  ))}
                </ul>

                <a href="#"
                  className={`text-center text-sm ${plan.highlight ? 'btn-hero' : 'btn-primary'} ${plan.comingSoon ? 'pointer-events-none' : ''}`}>
                  {plan.cta}
                </a>
                {!plan.comingSoon && (
                  <p className="text-xs text-muted-foreground text-center mt-3">✓ Sem fidelidade • Cancele quando quiser</p>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── FAQ ── */}
      <section id="faq" className="py-20 px-4">
        <div className="container mx-auto max-w-3xl">
          <div className="text-center mb-12">
            <span className="text-accent text-sm font-semibold uppercase tracking-widest">Dúvidas frequentes</span>
            <h2 className="text-heading mt-2">FAQ</h2>
          </div>

          <div className="space-y-3">
            {faqs.map((faq, i) => (
              <div key={i} className="portfolio-card cursor-pointer"
                onClick={() => setActiveFaq(activeFaq === i ? null : i)}>
                <div className="flex items-center justify-between gap-4">
                  <span className="font-semibold text-sm">{faq.q}</span>
                  <ChevronDown
                    className="w-4 h-4 text-accent flex-shrink-0 transition-smooth"
                    style={{ transform: activeFaq === i ? 'rotate(180deg)' : 'rotate(0deg)' }} />
                </div>
                {activeFaq === i && (
                  <p className="text-muted-foreground text-sm mt-3 leading-relaxed">{faq.a}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── FINAL CTA ── */}
      <section className="py-28 px-4 hero-gradient relative overflow-hidden">
        <div className="absolute inset-0 pointer-events-none"
          style={{ background: 'radial-gradient(ellipse at 50% 0%, rgba(77,212,255,0.08), transparent 70%)' }} />

        <div className="container mx-auto max-w-3xl text-center relative">
          <h2 className="text-heading mb-4">
            Enquanto você lê isso,{' '}
            <span className="bg-gradient-to-r from-accent to-primary bg-clip-text text-transparent">
              um lead seu está esperando resposta.
            </span>
          </h2>
          <p className="text-muted-foreground text-lg mb-10 max-w-xl mx-auto leading-relaxed">
            A Lara atenderia ele agora — você ainda não. Comece hoje e nunca mais perca uma venda por falta de resposta.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <a href="#planos" className="btn-hero flex items-center justify-center gap-2 text-lg px-10 py-5">
              Ativar minha Lara agora <ArrowRight className="w-5 h-5" />
            </a>
            <a href="#" className="flex items-center justify-center gap-2 px-8 py-5 rounded-xl font-semibold border border-white/20 hover:bg-white/10 transition-smooth">
              <MessageSquare className="w-4 h-4" /> Falar no WhatsApp
            </a>
          </div>
          <p className="text-muted-foreground text-sm mt-6 opacity-70">
            ✓ Garantia de 30 dias &nbsp;·&nbsp; ✓ Sem fidelidade &nbsp;·&nbsp; ✓ Suporte incluído
          </p>
        </div>
      </section>

      {/* ── FOOTER ── */}
      <footer className="bg-primary text-primary-foreground py-16">
        <div className="container mx-auto px-4 lg:px-8">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-10 mb-12">
            <div>
              <div className="flex items-center mb-4">
                <div className="w-10 h-10 rounded-xl accent-gradient flex items-center justify-center mr-3">
                  <div className="w-6 h-6 bg-primary rounded-sm" />
                </div>
                <div>
                  <span className="text-xl font-bold leading-none">Lara</span>
                  <span className="block text-xs text-primary-foreground/50 leading-none -mt-0.5">by DigitalPro</span>
                </div>
              </div>
              <p className="text-primary-foreground/70 text-sm leading-relaxed max-w-xs">
                A Lara é a IA que atende, qualifica e faz follow-up pelo WhatsApp — para quem quer vender mais sem depender de uma equipe grande.
              </p>
            </div>

            <div>
              <h4 className="font-semibold mb-4">Produto</h4>
              <ul className="space-y-2 text-sm text-primary-foreground/70">
                {['Funcionalidades', 'Planos', 'FAQ', 'Blog'].map(l => (
                  <li key={l}><a href="#" className="hover:text-accent transition-smooth">{l}</a></li>
                ))}
              </ul>
            </div>

            <div>
              <h4 className="font-semibold mb-4">Contato</h4>
              <div className="space-y-2 text-sm text-primary-foreground/70">
                <div className="flex items-center gap-2"><Mail  className="w-4 h-4 text-accent" /> contato@digitalpro.com</div>
                <div className="flex items-center gap-2"><Phone className="w-4 h-4 text-accent" /> +55 11 9 9999-9999</div>
              </div>
            </div>
          </div>

          <div className="border-t border-primary-foreground/20 pt-6 flex flex-col md:flex-row justify-between items-center gap-4">
            <p className="text-sm text-primary-foreground/60">© 2026 DigitalPro — Lara. Todos os direitos reservados.</p>
            <div className="flex items-center gap-6 text-sm text-primary-foreground/60">
              <a href="#" className="hover:text-accent transition-smooth">Privacidade</a>
              <a href="#" className="hover:text-accent transition-smooth">Termos</a>
              <button onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
                className="w-8 h-8 rounded-full bg-accent text-accent-foreground flex items-center justify-center hover:scale-110 transition-bounce">
                <ArrowUp className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </footer>

    </div>
  );
}
